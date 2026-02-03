import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from .logging_config import get_logger

load_dotenv()

log = get_logger("config")


def get_embedding_model() -> str:
    """Get the configured embedding model name."""
    return os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")


def get_qdrant_host() -> str:
    """Get the Qdrant host."""
    return os.getenv("QDRANT_HOST", "localhost")


def get_qdrant_port() -> int:
    """Get the Qdrant port."""
    return int(os.getenv("QDRANT_PORT", "6333"))


def get_llm() -> ChatOpenAI:
    """Get the configured LLM instance using OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM", "openai/gpt-5-mini")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")

    if not model:
        raise ValueError("LLM is not set")

    log.info(f"Initializing LLM: {model}")

    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
        default_headers={
            "X-Title": "Flex",
            "HTTP-Referer": "https://flex.consciousengines.com/",
        },
    )
