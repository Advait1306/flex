import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

from dataclasses import dataclass

from .config import get_qdrant_host, get_qdrant_port
from .embeddings import get_embedding, get_embeddings
from .logging_config import get_logger
from .state import FactItem, TodoItem

log = get_logger("qdrant_store")

COLLECTION_NAME = "todos"
FACTS_COLLECTION_NAME = "facts"
EMBEDDING_DIM = 1536  # text-embedding-3-small dimension

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Get cached Qdrant client."""
    global _client
    if _client is None:
        host = get_qdrant_host()
        port = get_qdrant_port()
        log.info(f"Connecting to Qdrant at {host}:{port}")
        _client = QdrantClient(host=host, port=port)
    return _client


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

        # Add text indexes for keyword search
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
        log.info(f"Collection {COLLECTION_NAME} created successfully")
    else:
        log.debug(f"Collection {COLLECTION_NAME} already exists")


def generate_id() -> str:
    """Generate a unique ID for a todo."""
    return str(uuid.uuid4())


def save_todo(todo: TodoItem, tags: list[str] | None = None) -> TodoItem:
    """Save todo with variable-length multivector based on tags."""
    ensure_collection()
    client = get_client()

    log.info(f"Saving todo: {todo.id} - {todo.title}")

    # Use tags if provided, otherwise create default tag from title
    if tags:
        texts_to_embed = tags
    else:
        texts_to_embed = [todo.title]
        if todo.description:
            texts_to_embed.append(todo.description)

    log.debug(f"Embedding {len(texts_to_embed)} texts for todo {todo.id}")
    embeddings = get_embeddings(texts_to_embed)

    # Build payload
    payload: dict[str, str | list[str] | None] = {
        "title": todo.title,
        "status": todo.status,
    }
 
    if todo.description:
        payload["description"] = todo.description
    if todo.parent_id:
        payload["parent_id"] = todo.parent_id
    if tags:
        payload["tags"] = tags

    # Single point with multiple vectors
    point = PointStruct(
        id=todo.id,
        vector=embeddings,  # List of vectors (variable length)
        payload=payload,
    )

    client.upsert(collection_name=COLLECTION_NAME, points=[point])
    log.debug(f"Todo {todo.id} saved to Qdrant")

    return todo


def load_todo(todo_id: str) -> TodoItem | None:
    """Retrieve todo by ID (direct point lookup, no search)."""
    ensure_collection()
    client = get_client()

    log.debug(f"Loading todo: {todo_id}")

    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[todo_id])
    if not points:
        log.warning(f"Todo not found: {todo_id}")
        return None

    point = points[0]
    payload = point.payload or {}
    return TodoItem(
        id=str(point.id),
        title=payload.get("title", ""),
        description=payload.get("description"),
        parent_id=payload.get("parent_id"),
        status=payload.get("status", "pending"),
    )


def list_todos() -> list[TodoItem]:
    """List all todos."""
    ensure_collection()
    client = get_client()

    results, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000)

    todos = []
    for point in results:
        payload = point.payload or {}
        todo = TodoItem(
            id=str(point.id),
            title=payload.get("title", ""),
            description=payload.get("description"),
            parent_id=payload.get("parent_id"),
            status=payload.get("status", "pending"),
        )
        todos.append(todo)

    log.info(f"Listed {len(todos)} todos")
    return todos


def delete_todo(todo_id: str) -> bool:
    """Delete todo by ID."""
    ensure_collection()
    client = get_client()

    log.info(f"Deleting todo: {todo_id}")

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=[todo_id],
    )

    log.debug(f"Todo {todo_id} deleted from Qdrant")
    return True


# --- Facts Collection ---


def ensure_facts_collection() -> None:
    """Ensure the facts collection exists with proper schema."""
    client = get_client()

    collections = client.get_collections().collections
    exists = any(c.name == FACTS_COLLECTION_NAME for c in collections)

    if not exists:
        log.info(f"Creating collection: {FACTS_COLLECTION_NAME}")
        client.create_collection(
            collection_name=FACTS_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM
                ),
            ),
        )

        # Add text index for keyword search on fact field
        log.info("Creating text index for fact field")
        client.create_payload_index(
            collection_name=FACTS_COLLECTION_NAME,
            field_name="fact",
            field_schema=TextIndexParams(
                type=TextIndexType.TEXT,
                tokenizer=TokenizerType.WORD,
                lowercase=True,
            ),
        )

        # Add keyword index for category filtering
        log.info("Creating keyword index for category field")
        client.create_payload_index(
            collection_name=FACTS_COLLECTION_NAME,
            field_name="category",
            field_schema="keyword",
        )
        log.info(f"Collection {FACTS_COLLECTION_NAME} created successfully")
    else:
        log.debug(f"Collection {FACTS_COLLECTION_NAME} already exists")


def save_fact(fact: FactItem, tags: list[str] | None = None) -> FactItem:
    """Save fact with variable-length multivector based on tags."""
    ensure_facts_collection()
    client = get_client()

    log.info(f"Saving fact: {fact.id} - {fact.fact[:50]}...")

    # Use tags if provided, otherwise use fact's tags, or fact text as fallback
    texts_to_embed = tags or fact.tags or [fact.fact]

    log.debug(f"Embedding {len(texts_to_embed)} texts for fact {fact.id}")
    embeddings = get_embeddings(texts_to_embed)

    # Build payload
    payload: dict[str, str | list[str] | None] = {
        "fact": fact.fact,
        "category": fact.category,
    }

    if fact.tags:
        payload["tags"] = fact.tags
    if fact.source_trigger:
        payload["source_trigger"] = fact.source_trigger
    if fact.created_at:
        payload["created_at"] = fact.created_at

    # Single point with multiple vectors
    point = PointStruct(
        id=fact.id,
        vector=embeddings,
        payload=payload,
    )

    client.upsert(collection_name=FACTS_COLLECTION_NAME, points=[point])
    log.debug(f"Fact {fact.id} saved to Qdrant")

    return fact


@dataclass
class FactSearchResult:
    """A search result containing a fact and its relevance score."""

    fact: FactItem
    score: float


def search_facts(query: str, limit: int = 10) -> list[FactSearchResult]:
    """Hybrid search: vector similarity + keyword matching.

    Combines results from both vector search and keyword search,
    deduplicating by fact ID and keeping the highest score.

    Args:
        query: Search query string
        limit: Maximum number of results to return

    Returns:
        List of FactSearchResult objects sorted by relevance
    """
    ensure_facts_collection()
    client = get_client()

    log.info(f"Searching facts for: {query}")

    results_by_id: dict[str, FactSearchResult] = {}

    # 1. Vector search on concept embeddings
    query_embedding = get_embedding(query)
    vector_results = client.query_points(
        collection_name=FACTS_COLLECTION_NAME,
        query=query_embedding,
        limit=limit,
    )

    for point in vector_results.points:
        payload = point.payload or {}
        fact = FactItem(
            id=str(point.id),
            fact=payload.get("fact", ""),
            category=payload.get("category", "other"),
            tags=payload.get("tags", []),
            source_trigger=payload.get("source_trigger"),
            created_at=payload.get("created_at"),
        )
        results_by_id[fact.id] = FactSearchResult(fact=fact, score=point.score or 0.0)

    log.info(f"Vector search found {len(vector_results.points)} facts")

    # 2. Keyword search on fact field
    keyword_results, _ = client.scroll(
        collection_name=FACTS_COLLECTION_NAME,
        scroll_filter=Filter(
            should=[
                FieldCondition(key="fact", match=MatchText(text=query)),
            ]
        ),
        limit=limit,
    )

    for point in keyword_results:
        fact_id = str(point.id)
        if fact_id not in results_by_id:
            payload = point.payload or {}
            fact = FactItem(
                id=fact_id,
                fact=payload.get("fact", ""),
                category=payload.get("category", "other"),
                tags=payload.get("tags", []),
                source_trigger=payload.get("source_trigger"),
                created_at=payload.get("created_at"),
            )
            # Keyword matches get a base score of 0.5
            results_by_id[fact_id] = FactSearchResult(fact=fact, score=0.5)

    log.info(f"Keyword search found {len(keyword_results)} facts")

    # Sort by score descending and limit
    search_results = sorted(
        results_by_id.values(), key=lambda r: r.score, reverse=True
    )[:limit]

    log.info(f"Returning {len(search_results)} combined results")
    return search_results


def list_facts() -> list[FactItem]:
    """List all facts."""
    ensure_facts_collection()
    client = get_client()

    results, _ = client.scroll(collection_name=FACTS_COLLECTION_NAME, limit=1000)

    facts = []
    for point in results:
        payload = point.payload or {}
        fact = FactItem(
            id=str(point.id),
            fact=payload.get("fact", ""),
            category=payload.get("category", "other"),
            tags=payload.get("tags", []),
            source_trigger=payload.get("source_trigger"),
            created_at=payload.get("created_at"),
        )
        facts.append(fact)

    log.info(f"Listed {len(facts)} facts")
    return facts
