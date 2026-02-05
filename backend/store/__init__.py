from .todos import (
    ensure_collection as ensure_todos_collection,
    generate_id,
    save_todo,
    load_todo,
    list_todos,
    delete_todo,
    search_todos,
    find_todo_by_title,
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
    "generate_id",
    "save_todo",
    "load_todo",
    "list_todos",
    "delete_todo",
    "search_todos",
    "find_todo_by_title",
    "SearchResult",
    "save_fact",
    "search_facts",
    "list_facts",
    "FactSearchResult",
    "load_freewrite",
]
