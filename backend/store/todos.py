import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    MatchText,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

from ai.logging_config import get_logger
from models import TodoItem

from .embeddings import get_embedding, get_embeddings
from .qdrant import EMBEDDING_DIM, get_client

log = get_logger("store.todos")

COLLECTION_NAME = "todos"


def ensure_collection() -> None:
    """Ensure the todos collection exists with proper schema."""
    client = get_client()

    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if not exists:
        log.info(f"Creating collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM
                ),
            ),
        )

        log.info("Creating text indexes for title and description")
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="title",
            field_schema=TextIndexParams(
                type=TextIndexType.TEXT,
                tokenizer=TokenizerType.WORD,
                lowercase=True,
            ),
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="description",
            field_schema=TextIndexParams(
                type=TextIndexType.TEXT,
                tokenizer=TokenizerType.WORD,
                lowercase=True,
            ),
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="user_id",
            field_schema="integer",
        )
        log.info(f"Collection {COLLECTION_NAME} created successfully")
    else:
        log.debug(f"Collection {COLLECTION_NAME} already exists")


def _todo_from_payload(todo_id: str, payload: dict) -> TodoItem:
    return TodoItem(
        id=todo_id,
        title=payload.get("title", ""),
        description=payload.get("description"),
        parent_id=payload.get("parent_id"),
        status=payload.get("status", "pending"),
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
    )


def _save(todo: TodoItem, tags: list[str] | None = None, *, user_id: int) -> TodoItem:
    """Persist a TodoItem to Qdrant with multivector embeddings."""
    client = get_client()

    if tags:
        texts_to_embed = tags
    else:
        texts_to_embed = [todo.title]
        if todo.description:
            texts_to_embed.append(todo.description)

    log.debug(f"Embedding {len(texts_to_embed)} texts for todo {todo.id}")
    embeddings = get_embeddings(texts_to_embed)

    payload: dict[str, str | list[str] | int | None] = {
        "title": todo.title,
        "status": todo.status,
        "user_id": user_id,
    }

    if todo.description:
        payload["description"] = todo.description
    if todo.parent_id:
        payload["parent_id"] = todo.parent_id
    if tags:
        payload["tags"] = tags
    if todo.created_at:
        payload["created_at"] = todo.created_at
    if todo.updated_at:
        payload["updated_at"] = todo.updated_at

    point = PointStruct(
        id=todo.id,
        vector=embeddings,
        payload=payload,
    )

    client.upsert(collection_name=COLLECTION_NAME, points=[point])
    log.debug(f"Todo {todo.id} saved to Qdrant")

    return todo


def create_todo(
    title: str,
    description: str | None = None,
    parent_id: str | None = None,
    tags: list[str] | None = None,
    *,
    user_id: int,
) -> TodoItem:
    """Create a new todo and save it to the store."""
    now = datetime.now(timezone.utc).isoformat()
    todo = TodoItem(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        parent_id=parent_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    _save(todo, tags=tags, user_id=user_id)
    log.info(f"Created todo: {todo.id} - {title}")
    return todo


def update_todo(
    todo_id: str,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    *,
    user_id: int,
) -> TodoItem:
    """Update an existing todo. Raises ValueError if not found."""
    existing = load_todo(todo_id)
    if not existing:
        raise ValueError(f"Todo not found: {todo_id}")

    data = existing.model_dump()
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if status is not None:
        data["status"] = status
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    updated = TodoItem.model_validate(data)
    _save(updated, tags=tags, user_id=user_id)
    log.info(f"Updated todo: {todo_id}")
    return updated


def load_todo(todo_id: str) -> TodoItem | None:
    """Retrieve todo by ID (direct point lookup, no search)."""
    client = get_client()

    log.debug(f"Loading todo: {todo_id}")

    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[todo_id])
    if not points:
        log.warning(f"Todo not found: {todo_id}")
        return None

    point = points[0]
    payload = point.payload or {}
    return _todo_from_payload(str(point.id), payload)


def list_todos(*, user_id: int) -> list[TodoItem]:
    """List all todos for a user."""
    client = get_client()

    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=1000,
    )

    todos = []
    for point in results:
        payload = point.payload or {}
        todo = _todo_from_payload(str(point.id), payload)
        todos.append(todo)

    log.info(f"Listed {len(todos)} todos for user {user_id}")
    return todos


def delete_todo(todo_id: str) -> bool:
    """Delete todo by ID."""
    client = get_client()

    log.info(f"Deleting todo: {todo_id}")

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=[todo_id],
    )

    log.debug(f"Todo {todo_id} deleted from Qdrant")
    return True


@dataclass
class SearchResult:
    """A search result containing a todo and its relevance score."""

    todo: TodoItem
    score: float


def search_todos(query: str, *, user_id: int, limit: int = 10) -> list[SearchResult]:
    """Hybrid search: vector similarity + keyword matching."""
    client = get_client()

    user_filter = FieldCondition(key="user_id", match=MatchValue(value=user_id))

    log.info(f"Searching todos for: {query}")

    results_by_id: dict[str, SearchResult] = {}

    # 1. Vector search
    query_embedding = get_embedding(query)
    vector_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=Filter(must=[user_filter]),
        limit=limit,
    )

    for point in vector_results.points:
        payload = point.payload or {}
        todo = _todo_from_payload(str(point.id), payload)
        results_by_id[todo.id] = SearchResult(todo=todo, score=point.score or 0.0)

    log.info(f"Vector search found {len(vector_results.points)} todos")

    # 2. Keyword search
    keyword_results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[user_filter],
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
            todo = _todo_from_payload(todo_id, payload)
            results_by_id[todo_id] = SearchResult(todo=todo, score=0.5)

    log.info(f"Keyword search found {len(keyword_results)} todos")

    search_results = sorted(
        results_by_id.values(), key=lambda r: r.score, reverse=True
    )[:limit]

    log.info(f"Returning {len(search_results)} combined results")
    return search_results