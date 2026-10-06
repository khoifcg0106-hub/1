"""
actions/document_intelligence.py — multi-document intelligence tool
(JARVIS-1, BƯỚC 3).

Auto-discovered by core/action_loader.py exactly like any other actions/*.py
that exposes a module-level TOOL dict — no change to main.py needed.

This tool is deliberately NOT a replacement for file_processor.py (spec §13:
"Không tạo hệ thống file processor thứ hai song song"). file_processor stays
the tool for single-file edit/convert/transform actions (resize an image,
convert a CSV, fix a docx…). This tool covers what file_processor's one-
file_path parameter cannot: reading/summarizing/comparing/searching across
MULTIPLE documents at once, backed by core/document_intelligence's shared
extraction layer. Use file_processor for "fix this file"; use this tool for
"compare these two PDFs" or "what do these three reports say about X".
"""
from __future__ import annotations

from pathlib import Path

from core.document_intelligence import (
    run_operation, verify_artifact, new_task, save_task,
)


def document_intelligence(parameters: dict, player=None, speak=None) -> str:
    paths_param = parameters.get("file_paths")
    if not paths_param:
        single = parameters.get("file_path", "").strip()
        paths_param = [single] if single else []
    if isinstance(paths_param, str):
        # Tolerate a comma-separated string too, in case the model sends one.
        paths_param = [p.strip() for p in paths_param.split(",") if p.strip()]

    if not paths_param:
        return "No file path(s) provided."

    missing = [p for p in paths_param if not Path(p).exists()]
    if missing:
        return f"File(s) not found: {', '.join(missing)}"

    operation   = (parameters.get("operation") or "read").strip()
    query       = parameters.get("query", "")
    instruction = parameters.get("instruction", "")

    log_msg = f"[DocIntel] {operation} | {len(paths_param)} file(s)"
    print(log_msg)
    if player:
        player.write_log(log_msg)

    # Checkpoint state — created even for a single-file call so a long batch
    # and a quick lookup go through the same, inspectable path (spec §9).
    task = new_task(document_ids=paths_param)
    task.current_operation = operation
    task.status = "running"
    save_task(task)

    try:
        result, docs = run_operation(operation, paths_param, query=query, instruction=instruction)
    except ValueError as e:
        task.status = "failed"
        save_task(task)
        return str(e)
    except Exception as e:
        task.status = "failed"
        save_task(task)
        return f"Document intelligence failed: {e}"

    for d in docs:
        if d.record.extraction_status == "ok":
            task.completed_documents.append(d.record.document_id)
        else:
            task.failed_documents[d.record.document_id] = d.record.error or "unknown error"
    task.status = "done"
    save_task(task)

    failed = [d for d in docs if d.record.extraction_status != "ok"]
    if failed:
        note = "; ".join(f"{d.record.name}: {d.record.error}" for d in failed)
        result = f"{result}\n\n(Note — could not extract: {note})"

    return result


def _verify_output_file(parameters: dict, player=None, speak=None) -> str:
    """Companion action for spec §7 — never just claim a file was written.
    Called after any tool creates a document artifact (docx/xlsx/pdf/csv/txt)
    to confirm it actually exists, is non-empty, and re-opens correctly."""
    path = parameters.get("path", "").strip()
    artifact_type = parameters.get("artifact_type") or Path(path).suffix.lstrip(".")
    if not path:
        return "No path provided to verify."
    result = verify_artifact(path, artifact_type)
    if result.verification_status == "verified":
        return f"Verified: {result.artifact_path} ({result.artifact_type})."
    return f"Verification FAILED for {result.artifact_path}: {result.verification_error}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "document_intelligence",
    "description": (
        "Reads, summarizes, compares, or searches across one or more uploaded documents "
        "(PDF, DOCX, XLSX, CSV, PPTX, TXT, code/text files). "
        "Use this for tasks spanning MULTIPLE documents at once (compare two PDFs, "
        "summarize three reports together, search a keyword across several files), "
        "or for a structured/local read of a single document. "
        "For single-file editing, conversion, resizing, or format transforms, use "
        "file_processor instead — this tool never modifies the original files."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_paths": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Full paths to one or more documents to read/analyze together.",
            },
            "file_path": {
                "type": "STRING",
                "description": "Single file path — alternative to file_paths when there's only one document.",
            },
            "operation": {
                "type": "STRING",
                "description": (
                    "read | extract | summarize | question_answer | compare | "
                    "search_within_document | multi_document_analysis. "
                    "Default: read."
                ),
            },
            "query": {
                "type": "STRING",
                "description": "The question (for question_answer) or search term (for search_within_document).",
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction for summarize/compare/multi_document_analysis, e.g. 'focus on pricing differences'.",
            },
        },
        "required": [],
    },
    "handler": document_intelligence,
}
