import os

from qdrant_client import QdrantClient

from logging_config import get_logger

log = get_logger("storage.qdrant")

EMBEDDING_DIM = 1536  # text-embedding-3-small dimension

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Get cached Qdrant client."""
    global _client
    if _client is None:
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        log.info(f"Connecting to Qdrant at {url}")
        _client = QdrantClient(url=url)
    return _client
