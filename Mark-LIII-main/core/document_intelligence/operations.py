"""
core/document_intelligence/operations.py — Document Operations (spec §5, §6).

READ, EXTRACT and SEARCH_WITHIN_DOCUMENT are pure local operations — no
network call, no API cost (spec §5: "Ưu tiên xử lý local"). SUMMARIZE,
QUESTION_ANSWER, COMPARE and MULTI_DOCUMENT_ANALYSIS need a model and call
Gemini, same as the existing actions/file_processor.py already does.

Multi-document inputs never get silently merged: each ExtractedDocument keeps
its own DocumentRecord, and every operation that spans documents tags its
output with which document each part came from (spec §6: "Không trộn dữ liệu
các tài liệu mà không giữ source").
"""
from __future__ import annotations

import json
from pathlib import Path

from .extractors import extract
from .types import ExtractedDocument


def _gemini_client():
    """Same pattern actions/file_processor.py already uses — kept local to
    this package so core/ never has to import from actions/."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        api_key = json.load(f)["gemini_api_key"]
    from google import genai
    client = genai.Client(api_key=api_key)

    class _W:
        def generate_content(self, contents):
            return client.models.generate_content(model="gemini-flash-latest", contents=contents)

    return _W()


# ── local-only operations (spec §5: prefer local) ────────────────────────────

def op_read(doc: ExtractedDocument, max_chars: int = 4000) -> str:
    return doc.full_text(max_chars=max_chars)


def op_extract(doc: ExtractedDocument) -> dict:
    """Structured extraction result — the normalized content model as a plain
    dict, for callers that want structure rather than flattened text."""
    return {
        "document_id": doc.record.document_id,
        "name": doc.record.name,
        "extraction_status": doc.record.extraction_status,
        "sections": len(doc.sections),
        "sheets": [s.name for s in doc.sheets],
        "slides": len(doc.slides),
        "text_preview": doc.full_text(max_chars=1000),
    }


def op_search_within(doc: ExtractedDocument, query: str, max_hits: int = 20) -> list[dict]:
    """Plain substring search across paragraphs/tables/sheets/slides, each hit
    carrying its SourceRef so the caller can trace back to page/sheet/slide."""
    q = query.lower().strip()
    hits: list[dict] = []
    if not q:
        return hits

    for sec in doc.sections:
        for para in sec.paragraphs:
            if q in para.text.lower():
                hits.append({"text": para.text[:280], "source": vars(para.source)})
                if len(hits) >= max_hits:
                    return hits
    for sh in doc.sheets:
        for row in sh.rows:
            row_text = " ".join(str(c) for c in row)
            if q in row_text.lower():
                hits.append({"text": row_text[:280], "source": {"file": doc.record.name, "sheet": sh.name}})
                if len(hits) >= max_hits:
                    return hits
    for sl in doc.slides:
        if q in sl.text.lower():
            hits.append({"text": sl.text[:280], "source": {"file": doc.record.name, "slide": sl.index}})
            if len(hits) >= max_hits:
                return hits
    return hits


# ── Gemini-backed operations ──────────────────────────────────────────────────

def op_summarize(doc: ExtractedDocument, instruction: str = "") -> str:
    text = doc.full_text()
    if not text.strip():
        return f"No extractable text in {doc.record.name} (extraction_status={doc.record.extraction_status})."
    prompt = instruction or f"Summarize this document concisely:\n\n{text}"
    if instruction:
        prompt = f"{instruction}\n\nDocument ({doc.record.name}):\n{text}"
    model = _gemini_client()
    return model.generate_content(prompt).text.strip()


def op_question_answer(doc: ExtractedDocument, question: str) -> str:
    text = doc.full_text()
    if not text.strip():
        return f"No extractable text in {doc.record.name} to answer from."
    prompt = f"Answer the question using ONLY this document ({doc.record.name}). If the answer isn't in it, say so.\n\nQuestion: {question}\n\nDocument:\n{text}"
    model = _gemini_client()
    return model.generate_content(prompt).text.strip()


def op_compare(docs: list[ExtractedDocument], instruction: str = "") -> str:
    """Each document's text is labelled with its own name before being
    concatenated, so the model (and the person reading the answer) can tell
    which claim came from which file."""
    blocks = []
    for d in docs:
        text = d.full_text(max_chars=20_000)
        status = d.record.extraction_status
        blocks.append(f"=== {d.record.name} (extraction: {status}) ===\n{text or '(no extractable text)'}")
    joined = "\n\n".join(blocks)
    task = instruction or "Compare these documents: what do they agree on, what differs, and any notable gaps."
    prompt = f"{task}\n\n{joined}"
    model = _gemini_client()
    return model.generate_content(prompt).text.strip()


def op_multi_document_analysis(docs: list[ExtractedDocument], instruction: str) -> str:
    blocks = []
    for d in docs:
        text = d.full_text(max_chars=15_000)
        blocks.append(f"=== {d.record.name} ===\n{text or '(no extractable text)'}")
    joined = "\n\n".join(blocks)
    prompt = f"{instruction}\n\nDocuments:\n{joined}"
    model = _gemini_client()
    return model.generate_content(prompt).text.strip()


# ── convenience: extract + run an operation by name over 1..N paths ──────────

OPERATIONS = {
    "read", "extract", "summarize", "question_answer",
    "compare", "search_within_document", "multi_document_analysis",
}


def run_operation(operation: str, paths: list[str], *, query: str = "",
                   instruction: str = "") -> tuple[str, list[ExtractedDocument]]:
    """Extracts every path (failures isolated per-file, spec §8) then runs the
    requested operation. Returns (result_text_or_json, extracted_docs) so the
    caller (the tool handler) can also report per-document extraction status."""
    op = operation.lower().strip()
    if op not in OPERATIONS:
        raise ValueError(f"Unknown operation '{operation}'. Try: {', '.join(sorted(OPERATIONS))}")

    docs = [extract(p) for p in paths]
    ok_docs = [d for d in docs if d.record.extraction_status == "ok"]

    if op == "read":
        if not ok_docs:
            return "No document could be read.", docs
        return "\n\n".join(f"=== {d.record.name} ===\n{op_read(d)}" for d in ok_docs), docs

    if op == "extract":
        return json.dumps([op_extract(d) for d in docs], indent=2, ensure_ascii=False), docs

    if op == "search_within_document":
        results = {d.record.name: op_search_within(d, query) for d in ok_docs}
        return json.dumps(results, indent=2, ensure_ascii=False), docs

    if op == "summarize":
        if not ok_docs:
            return "No document could be summarized (extraction failed for all inputs).", docs
        if len(ok_docs) == 1:
            return op_summarize(ok_docs[0], instruction), docs
        return op_multi_document_analysis(ok_docs, instruction or "Summarize each document, then give an overall summary."), docs

    if op == "question_answer":
        if not ok_docs:
            return "No document could be read to answer from.", docs
        if len(ok_docs) == 1:
            return op_question_answer(ok_docs[0], query), docs
        return op_multi_document_analysis(ok_docs, f"Answer using these documents, citing which document each fact comes from: {query}"), docs

    if op == "compare":
        if len(ok_docs) < 2:
            return "Need at least 2 successfully-extracted documents to compare.", docs
        return op_compare(ok_docs, instruction), docs

    if op == "multi_document_analysis":
        if not ok_docs:
            return "No document could be read for analysis.", docs
        return op_multi_document_analysis(ok_docs, instruction or "Analyze these documents together."), docs

    raise AssertionError("unreachable")
