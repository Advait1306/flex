import os

from langchain_openai import OpenAIEmbeddings

from .config import get_embedding_model
from .logging_config import get_logger

log = get_logger("embeddings")

_embeddings: OpenAIEmbeddings | None = None


def get_embeddings_client() -> OpenAIEmbeddings:
    """Get cached embeddings client."""
    global _embeddings
    if _embeddings is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")

        model = get_embedding_model()
        log.info(f"Initializing embeddings client with model: {model}")

        _embeddings = OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    return _embeddings


def get_embedding(text: str) -> list[float]:
    """Generate embedding for a single text."""
    log.debug(f"Generating embedding for text: {text[:50]}...")
    return get_embeddings_client().embed_query(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts (batch)."""
    if not texts:
        return []
    log.debug(f"Generating embeddings for {len(texts)} texts")
    return get_embeddings_client().embed_documents(texts)
