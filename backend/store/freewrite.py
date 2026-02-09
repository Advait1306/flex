from logging_config import get_logger
from db_models import FreewriteDocument

log = get_logger("store.freewrite")


async def load_freewrite(user_id: int) -> list[dict] | None:
    """Load freewrite content for a user from the database."""
    doc = await FreewriteDocument.filter(user_id=user_id).first()
    if doc is None or not doc.content:
        log.warning(f"No freewrite content for user_id={user_id}")
        return None

    log.debug(f"Loaded freewrite content for user_id={user_id}")
    return doc.content


async def save_freewrite(user_id: int, content: list[dict]) -> None:
    """Save freewrite content for a user to the database."""
    await FreewriteDocument.update_or_create(
        defaults={"content": content},
        user_id=user_id,
    )
    log.debug(f"Saved freewrite content for user_id={user_id}")
