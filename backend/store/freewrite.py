import json
from pathlib import Path

from ai.logging_config import get_logger

log = get_logger("store.freewrite")

FREEWRITE_FILE = Path(__file__).parent.parent.parent / "storage" / "freewrite.json"


def load_freewrite() -> list[dict] | None:
    """Load freewrite content from storage."""
    if not FREEWRITE_FILE.exists():
        log.warning(f"Freewrite file not found: {FREEWRITE_FILE}")
        return None

    with open(FREEWRITE_FILE, "r") as f:
        data = json.load(f)

    content = data.get("content", [])
    if not content:
        log.warning("Freewrite content is empty")
        return None

    log.debug("Loaded freewrite content")
    return content
