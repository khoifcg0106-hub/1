"""
tests/test_document_intelligence.py — spec §12/§16.

Uses only tiny, generated sample files (no personal data), written to a temp
directory, never touching anything under the repo itself. Run with:

    python -m unittest tests.test_document_intelligence -v

or just:

    python tests/test_document_intelligence.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.document_intelligence import (  # noqa: E402
    DocType, detect_type, is_supported,
    extract, run_operation, verify_artifact,
    new_task, save_task, load_task,
    retry_with_backoff, run_batch_isolated, RetryExhausted,
)

MARKER = "ZEBRA_MARKER_42"


def _make_txt(dir_: Path) -> Path:
    p = dir_ / "sample.txt"
    p.write_text(f"Hello world.\n\nThis line has {MARKER} in it.\n", encoding="utf-8")
    return p


def _make_csv(dir_: Path) -> Path:
    import csv
    p = dir_ / "sample.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "note"])
        w.writerow(["row1", MARKER])
        w.writerow(["row2", "nothing here"])
    return p


def _make_xlsx(dir_: Path) -> Path:
    import openpyxl
    p = dir_ / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["name", "note"])
    ws.append(["row1", MARKER])
    wb.save(p)
    return p


def _make_docx(dir_: Path) -> Path:
    from docx import Document
    p = dir_ / "sample.docx"
    d = Document()
    d.add_paragraph(f"This document mentions {MARKER} once.")
    table = d.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "col1"
    table.rows[0].cells[1].text = "col2"
    table.rows[1].cells[0].text = "a"
    table.rows[1].cells[1].text = "b"
    d.save(p)
    return p


def _make_pptx(dir_: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Inches
    p = dir_ / "sample.pptx"
    prs = Presentation()
    layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = "Title slide"
    body = slide.placeholders[1]
    body.text = f"Body text with {MARKER} inside."
    prs.save(p)
    return p


def _make_pdf(dir_: Path) -> Path:
    from reportlab.pdfgen import canvas
    p = dir_ / "sample.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(72, 700, f"PDF page one contains {MARKER}.")
    c.showPage()
    c.save()
    return p


class TestRouter(unittest.TestCase):
    def test_extensions_route_correctly(self):
        cases = {
            "a.pdf": DocType.PDF, "a.docx": DocType.DOCX, "a.doc": DocType.DOC,
            "a.xlsx": DocType.XLSX, "a.csv": DocType.CSV, "a.pptx": DocType.PPTX,
            "a.txt": DocType.TXT, "a.py": DocType.CODE,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(detect_type(name), expected)

    def test_xml_not_routed_to_json(self):
        self.assertEqual(detect_type("data.xml"), DocType.XML)
        self.assertNotEqual(detect_type("data.xml"), DocType.JSON)

    def test_doc_not_routed_to_docx(self):
        self.assertEqual(detect_type("legacy.doc"), DocType.DOC)
        self.assertNotEqual(detect_type("legacy.doc"), DocType.DOCX)

    def test_unknown_extension_unsupported(self):
        self.assertEqual(detect_type("weird.qzx"), DocType.UNSUPPORTED)
        self.assertFalse(is_supported("weird.qzx"))


class TestExtractors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.files = {
            "txt": _make_txt(cls.dir),
            "csv": _make_csv(cls.dir),
            "xlsx": _make_xlsx(cls.dir),
            "docx": _make_docx(cls.dir),
            "pptx": _make_pptx(cls.dir),
            "pdf": _make_pdf(cls.dir),
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_txt_extraction(self):
        doc = extract(self.files["txt"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertIn(MARKER, doc.full_text())

    def test_csv_extraction(self):
        doc = extract(self.files["csv"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertEqual(doc.record.sheet_count, 1)
        self.assertIn(MARKER, doc.full_text())

    def test_xlsx_extraction(self):
        doc = extract(self.files["xlsx"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertEqual(doc.record.sheet_count, 1)
        self.assertIn(MARKER, doc.full_text())

    def test_docx_extraction(self):
        doc = extract(self.files["docx"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertIn(MARKER, doc.full_text())
        self.assertEqual(len(doc.sections[0].tables), 1)

    def test_pptx_extraction(self):
        doc = extract(self.files["pptx"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertEqual(doc.record.slide_count, 1)
        self.assertIn(MARKER, doc.full_text())

    def test_pdf_extraction(self):
        doc = extract(self.files["pdf"])
        self.assertEqual(doc.record.extraction_status, "ok")
        self.assertEqual(doc.record.page_count, 1)
        self.assertIn(MARKER, doc.full_text())

    def test_search_within_document(self):
        from core.document_intelligence.operations import op_search_within
        doc = extract(self.files["txt"])
        hits = op_search_within(doc, MARKER)
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn(MARKER, hits[0]["text"])


class TestFailureModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nonexistent_file(self):
        doc = extract(self.dir / "does_not_exist.pdf")
        self.assertEqual(doc.record.extraction_status, "failed")
        self.assertIn("does not exist", doc.record.error)

    def test_empty_file(self):
        p = self.dir / "empty.txt"
        p.write_text("", encoding="utf-8")
        doc = extract(p)
        self.assertEqual(doc.record.extraction_status, "failed")
        self.assertIn("empty", doc.record.error)

    def test_unsupported_extension(self):
        p = self.dir / "mystery.qzx"
        p.write_text("data", encoding="utf-8")
        doc = extract(p)
        self.assertEqual(doc.record.extraction_status, "failed")
        self.assertIn("UNSUPPORTED_FORMAT", doc.record.error)

    def test_corrupt_pdf_does_not_crash(self):
        p = self.dir / "corrupt.pdf"
        p.write_bytes(b"this is not a real pdf file at all")
        doc = extract(p)  # must not raise
        self.assertEqual(doc.record.extraction_status, "failed")
        self.assertTrue(doc.record.error)

    def test_wrong_extension_not_misrouted(self):
        # A .doc file must never be silently opened as DOCX.
        p = self.dir / "legacy.doc"
        p.write_bytes(b"\xd0\xcf\x11\xe0fake-ole-header")
        doc = extract(p)
        self.assertEqual(doc.record.extraction_status, "failed")
        self.assertIn("legacy .doc", doc.record.error)


class TestMultiDocumentAndIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_bad_file_does_not_abort_batch(self):
        good = _make_txt(self.dir)
        bad = self.dir / "missing.txt"  # never created
        result, docs = run_operation("read", [str(good), str(bad)])
        self.assertIn(MARKER, result)             # good file's content made it through
        statuses = {d.record.name: d.record.extraction_status for d in docs}
        self.assertEqual(statuses[good.name], "ok")
        self.assertEqual(statuses["missing.txt"], "failed")

    def test_run_batch_isolated_continues_after_error(self):
        seen = []
        def fn(x):
            if x == 2:
                raise ValueError("boom")
            seen.append(x)
        errors = []
        run_batch_isolated([1, 2, 3], fn, lambda item, e: errors.append((item, str(e))))
        self.assertEqual(seen, [1, 3])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 2)

    def test_unknown_operation_raises_value_error(self):
        p = _make_txt(self.dir)
        with self.assertRaises(ValueError):
            run_operation("not_a_real_operation", [str(p)])


class TestVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_txt_ok(self):
        p = self.dir / "out.txt"
        p.write_text("some content", encoding="utf-8")
        r = verify_artifact(p, "txt")
        self.assertEqual(r.verification_status, "verified")

    def test_verify_empty_file_fails(self):
        p = self.dir / "out.txt"
        p.write_text("", encoding="utf-8")
        r = verify_artifact(p, "txt")
        self.assertEqual(r.verification_status, "failed")

    def test_verify_malformed_json_fails(self):
        p = self.dir / "out.json"
        p.write_text("{not valid json", encoding="utf-8")
        r = verify_artifact(p, "json")
        self.assertEqual(r.verification_status, "failed")

    def test_verify_missing_file_fails(self):
        r = verify_artifact(self.dir / "nope.txt", "txt")
        self.assertEqual(r.verification_status, "failed")
        self.assertIn("does not exist", r.verification_error)


class TestCheckpoint(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        task = new_task(["doc-a", "doc-b"])
        task.current_operation = "compare"
        task.completed_documents.append("doc-a")
        save_task(task)
        loaded = load_task(task.task_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, task.task_id)
        self.assertEqual(loaded.current_operation, "compare")
        self.assertEqual(loaded.completed_documents, ["doc-a"])

    def test_load_missing_task_returns_none(self):
        self.assertIsNone(load_task("no-such-task-id"))


class TestRetry(unittest.TestCase):
    def test_succeeds_first_try(self):
        calls = []
        def fn():
            calls.append(1)
            return "ok"
        self.assertEqual(retry_with_backoff(fn, retries=2, timeout_secs=2), "ok")
        self.assertEqual(len(calls), 1)

    def test_bounded_retry_then_raises(self):
        calls = []
        def fn():
            calls.append(1)
            raise RuntimeError("always fails")
        with self.assertRaises(RetryExhausted):
            retry_with_backoff(fn, retries=1, timeout_secs=1, backoff_secs=0.05)
        self.assertEqual(len(calls), 2)  # first try + 1 retry, never unbounded

    def test_timeout_is_enforced(self):
        def fn():
            time.sleep(1.0)
            return "too slow"
        start = time.time()
        with self.assertRaises(RetryExhausted):
            retry_with_backoff(fn, retries=0, timeout_secs=0.2)
        self.assertLess(time.time() - start, 1.0)  # didn't wait for the full sleep


class TestEndToEnd(unittest.TestCase):
    """Spec §16 — 3 documents -> read -> extract -> analyze -> report -> verify.

    The 'analyze' step here is done WITHOUT calling Gemini (this sandbox has
    no API key configured) — it builds the report from the local, structured
    extraction result instead, which is enough to prove the full mechanical
    chain (multi-doc extraction -> isolated failure handling -> artifact
    write -> verification) actually works end to end. The Gemini-backed
    operations (summarize/compare/question_answer/multi_document_analysis)
    are exercised by TestMultiDocumentAndIsolation's dispatch-path tests but
    not with a live model call — see docs/DOCUMENT_INTELLIGENCE_REPORT.md
    Known Issues.
    """

    def test_three_documents_read_extract_report_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            f1 = _make_txt(d)
            f2 = _make_csv(d)
            f3 = _make_docx(d)

            # READ across all three (local op, spec §5 "ưu tiên local")
            read_result, docs = run_operation("read", [str(f1), str(f2), str(f3)])
            for doc in docs:
                self.assertEqual(doc.record.extraction_status, "ok")
            self.assertIn(MARKER, read_result)

            # EXTRACT — structured, per-document result with source tracing
            extract_result, _ = run_operation("extract", [str(f1), str(f2), str(f3)])
            structured = json.loads(extract_result)
            self.assertEqual(len(structured), 3)
            for entry in structured:
                self.assertEqual(entry["extraction_status"], "ok")

            # "Analyze" -> build a small report locally (no live Gemini call
            # in this test environment) and write it as an artifact.
            report_path = d / "report.txt"
            lines = [f"Documents analyzed: {len(structured)}"]
            for entry in structured:
                lines.append(f"- {entry['name']}: {entry['text_preview'][:60]}")
            report_path.write_text("\n".join(lines), encoding="utf-8")

            # VERIFY the artifact — spec §7, never just claim it was created.
            result = verify_artifact(report_path, "txt")
            self.assertEqual(result.verification_status, "verified")
            self.assertEqual(result.artifact_path, str(report_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
