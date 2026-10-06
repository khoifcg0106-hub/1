"""
core/document_intelligence — JARVIS-1 BƯỚC 3.

Turns document handling from "read a file and answer" into:
  route → extract → normalize → operate → verify output → (checkpoint if long)

Public surface:
    detect_type(path)                  → DocType                (router.py)
    extract(path)                      → ExtractedDocument       (extractors.py)
    run_operation(op, paths, ...)       → (result, docs)          (operations.py)
    verify_artifact(path, type)        → ArtifactResult          (verification.py)
    new_task / save_task / load_task   → DocumentTask persistence (checkpoint.py)
    retry_with_backoff, run_batch_isolated                        (checkpoint.py)

actions/document_intelligence.py is the only file that turns this into a
Gemini-callable tool; everything in this package is UI/tool-agnostic on
purpose so it stays reusable from tests or a future task planner.
"""
from .router import DocType, detect_type, is_supported, mime_for
from .types import (
    DocumentRecord, ExtractedDocument, Section, Paragraph, TableData,
    SheetData, SlideData, SourceRef, ArtifactResult, DocumentTask,
)
from .extractors import extract
from .operations import run_operation, OPERATIONS
from .verification import verify_artifact
from .checkpoint import (
    new_task, save_task, load_task, list_tasks,
    retry_with_backoff, run_batch_isolated, RetryExhausted,
)

__all__ = [
    "DocType", "detect_type", "is_supported", "mime_for",
    "DocumentRecord", "ExtractedDocument", "Section", "Paragraph", "TableData",
    "SheetData", "SlideData", "SourceRef", "ArtifactResult", "DocumentTask",
    "extract", "run_operation", "OPERATIONS", "verify_artifact",
    "new_task", "save_task", "load_task", "list_tasks",
    "retry_with_backoff", "run_batch_isolated", "RetryExhausted",
]
