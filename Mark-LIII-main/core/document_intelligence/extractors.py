"""
core/document_intelligence/extractors.py — Extraction Layer (spec §3, §4).

Every extractor takes a path + a DocumentRecord and returns an
ExtractedDocument. None of them ever raise: a broken/corrupt file marks the
record failed (record.mark_failed) and returns an ExtractedDocument with
empty content, so one bad file in a multi-document batch never kills the
whole task (spec §8) — the caller just sees extraction_status="failed".

Optional third-party libraries (pdfplumber, python-docx, pandas, python-pptx)
are imported lazily inside each extractor, exactly like the existing
actions/file_processor.py does, so importing this module never requires all
of them to be installed.
"""
from __future__ import annotations

from pathlib import Path

from .router import DocType, detect_type
from .types import (
    DocumentRecord, ExtractedDocument, Section, Paragraph, TableData,
    SheetData, SlideData, SourceRef,
)


class DocumentExtractor:
    """Base class — subclasses implement _extract(); extract() is the shared
    try/except wrapper so no subclass has to repeat the failure handling."""

    def extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        try:
            doc = self._extract(path, record)
            record.extraction_status = "ok"
            record.touch()
            return doc
        except Exception as e:
            record.mark_failed(f"extraction failed: {e}")
            return ExtractedDocument(record=record)

    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        raise NotImplementedError


class PDFExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        try:
            import pdfplumber
        except ImportError as e:
            raise RuntimeError("pdfplumber not installed — pip install pdfplumber") from e

        sections: list[Section] = []
        with pdfplumber.open(path) as pdf:
            record.page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                paras = [
                    Paragraph(text=t.strip(), source=SourceRef(file=path.name, page=i, index=j))
                    for j, t in enumerate(text.split("\n\n")) if t.strip()
                ]
                tables = []
                for j, raw in enumerate(page.extract_tables() or []):
                    if not raw:
                        continue
                    tables.append(TableData(
                        rows=[[c or "" for c in row] for row in raw[1:]],
                        headers=[c or "" for c in raw[0]] if raw else None,
                        source=SourceRef(file=path.name, page=i, index=j),
                    ))
                if paras or tables:
                    sections.append(Section(title=f"Page {i}", paragraphs=paras, tables=tables))
        return ExtractedDocument(record=record, sections=sections)


class DOCXExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        try:
            from docx import Document as _Docx
        except ImportError as e:
            raise RuntimeError("python-docx not installed — pip install python-docx") from e

        d = _Docx(path)
        paras = [
            Paragraph(text=p.text.strip(), source=SourceRef(file=path.name, index=i))
            for i, p in enumerate(d.paragraphs) if p.text.strip()
        ]
        tables = []
        for ti, table in enumerate(d.tables):
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            headers = rows[0] if rows else None
            tables.append(TableData(rows=rows[1:] if rows else [], headers=headers,
                                     source=SourceRef(file=path.name, index=ti)))
        record.page_count = None  # docx has no reliable page count without rendering
        return ExtractedDocument(record=record, sections=[Section(title="", paragraphs=paras, tables=tables)])


class XLSXExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        try:
            import openpyxl
        except ImportError as e:
            raise RuntimeError("openpyxl not installed — pip install openpyxl") from e

        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        record.sheet_count = len(wb.sheetnames)
        sheets = []
        for name in wb.sheetnames:
            ws = wb[name]
            rows_iter = ws.iter_rows(values_only=True)
            all_rows = [list(r) for r in rows_iter]
            headers = [str(c) if c is not None else "" for c in all_rows[0]] if all_rows else None
            body = all_rows[1:] if all_rows else []
            sheets.append(SheetData(name=name, rows=body, headers=headers,
                                     source=SourceRef(file=path.name, sheet=name)))
        return ExtractedDocument(record=record, sheets=sheets)


class CSVExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        import csv as _csv
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = list(_csv.reader(f))
        headers = reader[0] if reader else None
        body = reader[1:] if reader else []
        record.sheet_count = 1
        sheet = SheetData(name=path.stem, rows=body, headers=headers,
                           source=SourceRef(file=path.name, sheet=path.stem))
        return ExtractedDocument(record=record, sheets=[sheet])


class PPTXExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        try:
            from pptx import Presentation
        except ImportError as e:
            raise RuntimeError("python-pptx not installed — pip install python-pptx") from e

        prs = Presentation(path)
        record.slide_count = len(prs.slides)
        slides = []
        for i, slide in enumerate(prs.slides, start=1):
            texts = [shape.text.strip() for shape in slide.shapes
                     if hasattr(shape, "text") and shape.text.strip()]
            slides.append(SlideData(index=i, text="\n".join(texts),
                                     source=SourceRef(file=path.name, slide=i)))
        return ExtractedDocument(record=record, slides=slides)


class TextExtractor(DocumentExtractor):
    def _extract(self, path: Path, record: DocumentRecord) -> ExtractedDocument:
        content = path.read_text(encoding="utf-8", errors="replace")
        paras = [
            Paragraph(text=t.strip(), source=SourceRef(file=path.name, index=i))
            for i, t in enumerate(content.split("\n\n")) if t.strip()
        ]
        return ExtractedDocument(record=record, sections=[Section(title="", paragraphs=paras)])


class CodeExtractor(TextExtractor):
    """Code files are read as text for the intelligence layer's purposes
    (search/summarize/compare). actions/code_helper.py remains the tool for
    actually editing/running code — this extractor only reads."""
    pass


_EXTRACTORS: dict[DocType, DocumentExtractor] = {
    DocType.PDF:  PDFExtractor(),
    DocType.DOCX: DOCXExtractor(),
    DocType.XLSX: XLSXExtractor(),
    DocType.CSV:  CSVExtractor(),
    DocType.PPTX: PPTXExtractor(),
    DocType.TXT:  TextExtractor(),
    DocType.CODE: CodeExtractor(),
    DocType.XML:  TextExtractor(),   # structured-text fallback, never routed as JSON
    DocType.JSON: TextExtractor(),
}


def extract(path: Path | str) -> ExtractedDocument:
    """Top-level entrypoint: detect type, run the matching extractor, always
    return an ExtractedDocument (never raises) so callers can batch many
    documents without a try/except around every one."""
    path = Path(path)
    record = DocumentRecord.from_path(path)

    if not path.exists():
        record.mark_failed("file does not exist")
        return ExtractedDocument(record=record)
    if path.stat().st_size == 0:
        record.mark_failed("file is empty")
        return ExtractedDocument(record=record)

    doc_type = detect_type(path)
    record.mime_type = doc_type.value
    if doc_type is DocType.UNSUPPORTED or doc_type is DocType.DOC:
        # DOC (legacy binary .doc) is intentionally not auto-extracted — no
        # dependable pure-Python reader for it; report the precise reason
        # instead of guessing via the DOCX path.
        reason = "UNSUPPORTED_FORMAT" if doc_type is DocType.UNSUPPORTED else \
                 "legacy .doc binary format is not supported for extraction (convert to .docx)"
        record.mark_failed(reason)
        return ExtractedDocument(record=record)

    extractor = _EXTRACTORS.get(doc_type)
    if extractor is None:
        record.mark_failed("UNSUPPORTED_FORMAT")
        return ExtractedDocument(record=record)

    return extractor.extract(path, record)
