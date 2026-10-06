"""
core/document_intelligence/verification.py — Output / Artifact verification
(spec §7). "Đã tạo file" is never enough — every artifact this layer produces
is checked: exists, non-empty, opens/reads back, format correct, basic
content present.
"""
from __future__ import annotations

from pathlib import Path

from .types import ArtifactResult

_MIN_CONTENT_BYTES = 1  # basic "not truncated to nothing" check


def verify_artifact(path: Path | str, artifact_type: str) -> ArtifactResult:
    path = Path(path)

    if not path.exists():
        return ArtifactResult(str(path), artifact_type, "failed", "file does not exist")
    if path.stat().st_size == 0:
        return ArtifactResult(str(path), artifact_type, "failed", "file is empty")

    checker = _CHECKERS.get(artifact_type.lower())
    if checker is None:
        # Unknown artifact type — exists + non-empty is the best we can do.
        return ArtifactResult(str(path), artifact_type, "verified", None)

    try:
        checker(path)
    except Exception as e:
        return ArtifactResult(str(path), artifact_type, "failed", f"re-open/read-back failed: {e}")

    return ArtifactResult(str(path), artifact_type, "verified", None)


def _check_txt(path: Path) -> None:
    content = path.read_text(encoding="utf-8", errors="strict")
    if len(content) < _MIN_CONTENT_BYTES:
        raise ValueError("no readable content")


def _check_csv(path: Path) -> None:
    import csv
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError("no rows")


def _check_json(path: Path) -> None:
    import json
    with open(path, encoding="utf-8") as f:
        json.load(f)  # raises on malformed JSON


def _check_docx(path: Path) -> None:
    from docx import Document
    d = Document(path)
    _ = len(d.paragraphs)  # forces the archive to actually open/parse


def _check_xlsx(path: Path) -> None:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    if not wb.sheetnames:
        raise ValueError("no sheets")


def _check_pdf(path: Path) -> None:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("no pages")


_CHECKERS = {
    "txt": _check_txt, "md": _check_txt, "log": _check_txt,
    "csv": _check_csv,
    "json": _check_json,
    "docx": _check_docx,
    "xlsx": _check_xlsx,
    "pdf": _check_pdf,
}
