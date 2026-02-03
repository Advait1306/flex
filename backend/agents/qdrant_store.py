import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

from .config import get_qdrant_host, get_qdrant_port
from .embeddings import get_embeddings
from .logging_config import get_logger
from .state import TodoItem

log = get_logger("qdrant_store")

COLLECTION_NAME = "todos"
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
