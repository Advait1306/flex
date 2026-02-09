import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from logging_config import get_logger

load_dotenv()

log = get_logger("config")


_app_name = "Flex"


def set_app_name(name: str) -> None:
    """Set the application name used in LLM request headers."""
    global _app_name
    _app_name = name


def get_llm() -> ChatOpenAI:
    """Get the configured LLM instance."""
    provider = os.getenv("PROVIDER", "OpenAI").lower()
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")

    if provider == "cerebras":
        model = os.getenv("LLM", "openai/gpt-oss-120b")

        log.info(f"Initializing Cerebras LLM via OpenRouter: {model}")

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            default_headers={
                "X-Title": _app_name,
                "HTTP-Referer": "https://flex.consciousengines.com/",
            },
            extra_body={"provider": {"order": ["cerebras"]}},
        )
    else:
        # Default: OpenAI
        model = os.getenv("LLM", "openai/gpt-5-mini")
        log.info(f"Initializing OpenAI LLM: {model}")

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            default_headers={
                "X-Title": _app_name,
                "HTTP-Referer": "https://flex.consciousengines.com/",
            },
        )
