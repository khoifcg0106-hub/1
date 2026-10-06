"""
core/document_intelligence/router.py — Document Type Router (spec §1).

One job: look at a path and say, precisely, what kind of document it is —
before anything tries to extract or process it. Two misroutes are called out
explicitly in the spec and are covered by tests:
    .xml must NOT be routed to JSON
    .doc must NOT be silently routed to DOCX (different binary format —
         python-docx cannot open it; it is reported as its own type so the
         caller can decide, rather than failing deep inside a DOCX extractor)
"""
from __future__ import annotations

from pathlib import Path

from .types import DocType

_EXT_MAP: dict[str, DocType] = {
    "pdf":  DocType.PDF,
    "docx": DocType.DOCX,
    "doc":  DocType.DOC,
    "xlsx": DocType.XLSX,
    "xlsm": DocType.XLSX,
    "xls":  DocType.XLS,
    "csv":  DocType.CSV,
    "tsv":  DocType.CSV,
    "pptx": DocType.PPTX,
    "txt":  DocType.TXT,
    "md":   DocType.TXT,
    "rst":  DocType.TXT,
    "log":  DocType.TXT,
    "xml":  DocType.XML,
    "json": DocType.JSON,
}

_CODE_EXTS = {
    "py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "h", "hpp", "cs",
    "go", "rs", "rb", "php", "swift", "kt", "sh", "bash", "ps1", "lua",
    "r", "m", "sql", "yaml", "yml", "toml", "css", "html",
}

_MIME_MAP: dict[DocType, str] = {
    DocType.PDF:  "application/pdf",
    DocType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocType.DOC:  "application/msword",
    DocType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    DocType.XLS:  "application/vnd.ms-excel",
    DocType.CSV:  "text/csv",
    DocType.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    DocType.TXT:  "text/plain",
    DocType.CODE: "text/x-source",
    DocType.XML:  "application/xml",
    DocType.JSON: "application/json",
}


def detect_type(path: Path | str) -> DocType:
    """Pure extension-based routing — deterministic and testable without
    touching the filesystem. Case-insensitive; leading dot stripped."""
    ext = Path(path).suffix.lower().lstrip(".")
    if not ext:
        return DocType.UNSUPPORTED
    if ext in _CODE_EXTS:
        return DocType.CODE
    return _EXT_MAP.get(ext, DocType.UNSUPPORTED)


def mime_for(doc_type: DocType) -> str | None:
    return _MIME_MAP.get(doc_type)


def is_supported(path: Path | str) -> bool:
    return detect_type(path) is not DocType.UNSUPPORTED
