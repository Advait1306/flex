from .todos import (
    ensure_collection as ensure_todos_collection,
    create_todo,
    update_todo,
    load_todo,
    list_todos,
    delete_todo,
    search_todos,
    SearchResult,
)
from .facts import (
    ensure_collection as ensure_facts_collection,
    save_fact,
    search_facts,
    list_facts,
    FactSearchResult,
)
from .freewrite import load_freewrite


def init():
    """Initialize store collections. Call once at startup."""
    ensure_todos_collection()
    ensure_facts_collection()

__all__ = [
    "create_todo",
    "update_todo",
    "load_todo",
    "list_todos",
    "delete_todo",
    "search_todos",
    "SearchResult",
    "save_fact",
    "search_facts",
    "list_facts",
    "FactSearchResult",
    "load_freewrite",
]
