"""
Storage module for todos - now uses Qdrant as the primary storage backend.

This module re-exports functions from qdrant_store for backwards compatibility.
"""

import json
from pathlib import Path

from .logging_config import get_logger
from .qdrant_store import (
    delete_todo,
    generate_id,
    list_todos,
    load_todo,
    save_todo,
)
from .search import search_todos
from .state import TodoItem

log = get_logger("storage")

# Re-export Qdrant functions for backwards compatibility
__all__ = [
    "generate_id",
    "save_todo",
    "load_todo",
    "list_todos",
    "delete_todo",
    "search_todos",
    "load_document",
    "find_todo_by_title",
]


DOCUMENTS_FILE = Path(__file__).parent.parent.parent / "storage" / "documents.json"


def load_document(document_id: str) -> list[dict] | None:
    """Load a document's content from storage."""
    if not DOCUMENTS_FILE.exists():
        log.warning(f"Documents file not found: {DOCUMENTS_FILE}")
        return None

    with open(DOCUMENTS_FILE, "r") as f:
        data = json.load(f)

    content = data.get("documents", {}).get(document_id)
    if content is None:
        log.warning(f"Document not found: {document_id}")
        return None

    log.debug(f"Loaded document: {document_id}")
    return content


def find_todo_by_title(title: str) -> TodoItem | None:
    """Find a todo by title using semantic search.

    Uses search_todos for semantic matching instead of simple string comparison.
    """
    results = search_todos(title, limit=5)
    if results:
        # Return the best match
        best_match = results[0].todo
        log.debug(f"Found todo by title '{title}': {best_match.id} (score: {results[0].score})")
        return best_match
    log.debug(f"No todo found with title: {title}")
    return None
