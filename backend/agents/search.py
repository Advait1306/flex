from dataclasses import dataclass

from qdrant_client.models import FieldCondition, Filter, MatchText

from .embeddings import get_embedding
from .logging_config import get_logger
from .qdrant_store import COLLECTION_NAME, ensure_collection, get_client
from .state import TodoItem

log = get_logger("search")


@dataclass
class SearchResult:
    """A search result containing a todo and its relevance score."""

    todo: TodoItem
    score: float


def search_todos(query: str, limit: int = 10) -> list[SearchResult]:
    """Hybrid search: vector similarity + keyword matching.

    Combines results from both vector search and keyword search,
    deduplicating by todo ID and keeping the highest score.

    Args:
        query: Search query string
        limit: Maximum number of results to return

    Returns:
        List of SearchResult objects sorted by relevance
    """
    ensure_collection()
    client = get_client()

    log.info(f"Searching todos for: {query}")

    results_by_id: dict[str, SearchResult] = {}

    # 1. Vector search on concept embeddings
    query_embedding = get_embedding(query)
    vector_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=limit,
    )

    for point in vector_results.points:
        payload = point.payload or {}
        todo = TodoItem(
            id=str(point.id),
            title=payload.get("title", ""),
            description=payload.get("description"),
            parent_id=payload.get("parent_id"),
            status=payload.get("status", "pending"),
        )
        results_by_id[todo.id] = SearchResult(todo=todo, score=point.score or 0.0)

    log.info(f"Vector search found {len(vector_results.points)} todos")

    # 2. Keyword search on title/description
    keyword_results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            should=[
                FieldCondition(key="title", match=MatchText(text=query)),
                FieldCondition(key="description", match=MatchText(text=query)),
            ]
        ),
        limit=limit,
    )

    for point in keyword_results:
        todo_id = str(point.id)
        if todo_id not in results_by_id:
            payload = point.payload or {}
            todo = TodoItem(
                id=todo_id,
                title=payload.get("title", ""),
                description=payload.get("description"),
                parent_id=payload.get("parent_id"),
                status=payload.get("status", "pending"),
            )
            # Keyword matches get a base score of 0.5
            results_by_id[todo_id] = SearchResult(todo=todo, score=0.5)

    log.info(f"Keyword search found {len(keyword_results)} todos")

    # Sort by score descending and limit
    search_results = sorted(
        results_by_id.values(), key=lambda r: r.score, reverse=True
    )[:limit]

    log.info(f"Returning {len(search_results)} combined results")
    return search_results
