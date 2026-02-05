import os

from qdrant_client import QdrantClient

from pipeline.logging_config import get_logger

log = get_logger("storage.qdrant")

EMBEDDING_DIM = 1536  # text-embedding-3-small dimension

_client: QdrantClient | None = None


def get_qdrant_host() -> str:
    return os.getenv("QDRANT_HOST", "localhost")


def get_qdrant_port() -> int:
    return int(os.getenv("QDRANT_PORT", "6333"))


def get_client() -> QdrantClient:
    """Get cached Qdrant client."""
    global _client
    if _client is None:
        host = get_qdrant_host()
        port = get_qdrant_port()
        log.info(f"Connecting to Qdrant at {host}:{port}")
        _client = QdrantClient(host=host, port=port)
    return _client
