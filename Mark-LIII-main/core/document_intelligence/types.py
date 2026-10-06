"""
core/document_intelligence/types.py — shared data shapes for the document
intelligence layer (JARVIS-1, BƯỚC 3).

Nothing in this file talks to disk, Gemini, or any specific file format.
It only defines the structures every other module in this package passes
around, so extractors, operations, verification and checkpointing all agree
on one shape instead of each inventing its own dict.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── 1. DOCUMENT TYPE ROUTER's output ─────────────────────────────────────────

class DocType(str, Enum):
    PDF      = "pdf"
    DOCX     = "docx"
    DOC      = "doc"        # legacy binary Word — routed separately, never
                             # silently treated as DOCX (spec: ".doc → DOCX" is
                             # exactly the misroute we must not make)
    XLSX     = "xlsx"
    XLS      = "xls"
    CSV      = "csv"
    PPTX     = "pptx"
    TXT      = "txt"
    CODE     = "code"
    XML      = "xml"        # never routed to JSON, even though both are
                             # "structured text" — spec: ".xml → JSON" is the
                             # other misroute we must not make
    JSON     = "json"
    UNSUPPORTED = "unsupported_format"


# ── 2. DOCUMENT RECORD ────────────────────────────────────────────────────────

@dataclass
class DocumentRecord:
    """Structured metadata for one document — the thing everything else in
    this package (extraction, operations, checkpoint) refers to by id."""
    document_id: str
    name: str
    path: str
    extension: str
    mime_type: Optional[str] = None
    size: int = 0

    page_count: Optional[int]  = None
    sheet_count: Optional[int] = None
    slide_count: Optional[int] = None

    extraction_status: str = "pending"   # pending | ok | failed | unsupported
    processing_status: str = "pending"   # pending | running | done | failed
    error: Optional[str] = None

    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def from_path(cls, path: Path) -> "DocumentRecord":
        st = path.stat() if path.exists() else None
        return cls(
            document_id=str(uuid.uuid4()),
            name=path.name,
            path=str(path),
            extension=path.suffix.lower().lstrip("."),
            size=st.st_size if st else 0,
        )

    def touch(self) -> None:
        self.updated_at = _now()

    def mark_failed(self, error: str) -> None:
        self.error = error
        self.extraction_status = "failed"
        self.processing_status = "failed"
        self.touch()


# ── 4. NORMALIZED CONTENT MODEL ───────────────────────────────────────────────
# Document → Section → Paragraph / Table ; Sheet ; Slide — each keeps enough
# "source" info to be traced back to file/page/sheet/slide/paragraph/table.

@dataclass
class SourceRef:
    file: str
    page: Optional[int]  = None
    sheet: Optional[str] = None
    slide: Optional[int] = None
    index: Optional[int] = None   # paragraph/table/row index within the page


@dataclass
class Paragraph:
    text: str
    source: SourceRef


@dataclass
class TableData:
    rows: list[list[str]]
    source: SourceRef
    headers: Optional[list[str]] = None


@dataclass
class SheetData:
    name: str
    rows: list[list[Any]]
    source: SourceRef
    headers: Optional[list[str]] = None


@dataclass
class SlideData:
    index: int
    text: str
    source: SourceRef


@dataclass
class Section:
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    tables: list[TableData]     = field(default_factory=list)


@dataclass
class ExtractedDocument:
    """The one shape every extractor returns, regardless of source format.
    Downstream operations (summarize/compare/search/…) work off this and
    never need to know whether it came from a PDF or a CSV."""
    record: DocumentRecord
    sections: list[Section]  = field(default_factory=list)
    sheets: list[SheetData]  = field(default_factory=list)
    slides: list[SlideData]  = field(default_factory=list)
    metadata: dict           = field(default_factory=dict)

    def full_text(self, max_chars: int = 60_000) -> str:
        """Flattened text view used as the default input to Gemini prompts."""
        parts: list[str] = []
        for sec in self.sections:
            if sec.title:
                parts.append(f"## {sec.title}")
            for p in sec.paragraphs:
                parts.append(p.text)
            for t in sec.tables:
                parts.append(_table_to_text(t))
        for sh in self.sheets:
            parts.append(f"## Sheet: {sh.name}")
            parts.append(_rows_to_text(sh.headers, sh.rows))
        for sl in self.slides:
            parts.append(f"## Slide {sl.index}")
            parts.append(sl.text)
        text = "\n\n".join(p for p in parts if p and p.strip())
        return text[:max_chars]


def _table_to_text(t: TableData) -> str:
    lines = []
    if t.headers:
        lines.append(" | ".join(t.headers))
    for row in t.rows[:200]:
        lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)


def _rows_to_text(headers: Optional[list[str]], rows: list[list[Any]]) -> str:
    lines = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
    for row in rows[:200]:
        lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)


# ── 7. OUTPUT / ARTIFACT ──────────────────────────────────────────────────────

@dataclass
class ArtifactResult:
    artifact_path: str
    artifact_type: str
    verification_status: str          # "verified" | "failed"
    verification_error: Optional[str] = None


# ── 9. CHECKPOINT ──────────────────────────────────────────────────────────────

@dataclass
class DocumentTask:
    """Lightweight, save-to-disk task state for a multi-document operation.
    Not a LangGraph-style execution graph — just enough state that a task can
    be inspected mid-run and resumed instead of started over (spec §9)."""
    task_id: str
    documents: list[str]                      # document_ids, in order
    current_document: Optional[str] = None
    completed_documents: list[str] = field(default_factory=list)
    failed_documents: dict[str, str] = field(default_factory=dict)  # id -> error
    current_operation: Optional[str] = None
    artifacts: list[dict] = field(default_factory=list)  # ArtifactResult as dict
    status: str = "pending"                    # pending | running | done | failed
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def remaining(self) -> list[str]:
        done = set(self.completed_documents) | set(self.failed_documents.keys())
        return [d for d in self.documents if d not in done]
