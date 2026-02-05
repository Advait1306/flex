from fastapi import APIRouter

from pipeline.logging_config import get_logger
from store import list_facts

log = get_logger("api.facts")

router = APIRouter(prefix="/api", tags=["facts"])


@router.get("/facts")
async def get_facts():
    """Get all facts."""
    log.debug("Listing all facts")
    facts = list_facts()
    return {"facts": [f.model_dump(exclude_none=True) for f in facts]}
