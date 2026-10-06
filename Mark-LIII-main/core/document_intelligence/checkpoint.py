"""
core/document_intelligence/checkpoint.py — error recovery (spec §8) and
checkpoint state (spec §9).

This is deliberately small: a JSON file per task under memory/doc_tasks/, a
bounded retry helper, and per-file error isolation. It gives a long
multi-document job a state that can be inspected and resumed — it is not a
LangGraph-style execution graph, and the spec explicitly says not to build
one ("KHÔNG cần cài toàn bộ LangGraph").
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import time
import uuid
from pathlib import Path
from typing import Callable, TypeVar

from .types import DocumentTask

T = TypeVar("T")


def _tasks_dir() -> Path:
    # memory/ already exists and is the app's one durable-storage folder;
    # a subfolder keeps this contained without inventing a new location.
    base = Path(__file__).resolve().parent.parent.parent / "memory" / "doc_tasks"
    base.mkdir(parents=True, exist_ok=True)
    return base


def new_task(document_ids: list[str]) -> DocumentTask:
    return DocumentTask(task_id=str(uuid.uuid4()), documents=list(document_ids))


def save_task(task: DocumentTask) -> Path:
    task.touch()
    path = _tasks_dir() / f"{task.task_id}.json"
    path.write_text(json.dumps(dataclasses.asdict(task), indent=2, ensure_ascii=False),
                     encoding="utf-8")
    return path


def load_task(task_id: str) -> DocumentTask | None:
    path = _tasks_dir() / f"{task_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return DocumentTask(**data)


def list_tasks() -> list[str]:
    return [p.stem for p in _tasks_dir().glob("*.json")]


class RetryExhausted(Exception):
    def __init__(self, last_error: Exception, attempts: int):
        super().__init__(f"failed after {attempts} attempt(s): {last_error}")
        self.last_error = last_error
        self.attempts = attempts


def retry_with_backoff(fn: Callable[[], T], *, retries: int = 2,
                        timeout_secs: float = 30.0, backoff_secs: float = 1.5) -> T:
    """Bounded retry (spec §8: "retry có giới hạn", "không retry vô hạn") with
    a hard per-attempt timeout, run in a worker thread so a hung call (e.g. a
    stalled network read) cannot block forever even once retries run out."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 2):  # first try + `retries` retries
        # Not a `with` block on purpose: ThreadPoolExecutor.__exit__ calls
        # shutdown(wait=True), which would block here until the hung call
        # finally returns — defeating the timeout entirely. shutdown(wait=False)
        # lets this function return as soon as the timeout fires; the stray
        # thread is abandoned to finish (or not) on its own.
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = ex.submit(fn)
        try:
            result = future.result(timeout=timeout_secs)
            ex.shutdown(wait=False)
            return result
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"timed out after {timeout_secs}s")
            ex.shutdown(wait=False)
        except Exception as e:
            last_error = e
            ex.shutdown(wait=False)
        if attempt <= retries:
            time.sleep(backoff_secs * attempt)
    raise RetryExhausted(last_error, retries + 1)


def run_batch_isolated(items: list[T], fn: Callable[[T], None],
                        on_error: Callable[[T, Exception], None]) -> None:
    """Spec §8: 'lỗi một file không làm mất toàn bộ task' — run fn(item) for
    every item; an exception from one item is reported via on_error and the
    loop continues to the rest instead of aborting."""
    for item in items:
        try:
            fn(item)
        except Exception as e:
            on_error(item, e)
