from fastapi import APIRouter, Depends

from ai.logging_config import get_logger
from auth import verify_user
from store import list_facts

log = get_logger("api.facts")

router = APIRouter(prefix="/api", tags=["facts"])


@router.get("/facts")
async def get_facts(user: dict = Depends(verify_user)):
    """Get all facts."""
    log.debug("Listing all facts")
    facts = list_facts(user_id=user["id"])
    return {"facts": [f.model_dump(exclude_none=True) for f in facts]}
