from fastapi import APIRouter, Depends
from pydantic import BaseModel

from logging_config import get_logger
from ai.queue_manager import get_queue_manager
from auth import verify_user

log = get_logger("api.daemon")

router = APIRouter(prefix="/api/daemon", tags=["daemon"])


class DaemonSnapshot(BaseModel):
    app_name: str
    bundle_id: str
    app_category: str
    content: str
    content_hash: str


@router.post("/snapshot")
async def post_snapshot(body: DaemonSnapshot, user: dict = Depends(verify_user)):
    """Receive an app content snapshot from the daemon and queue it for processing."""
    if not body.content.strip():
        return {"status": "skipped", "reason": "empty content"}

    queue_manager = get_queue_manager()
    await queue_manager.enqueue_daemon(
        app_name=body.app_name,
        bundle_id=body.bundle_id,
        app_category=body.app_category,
        content=body.content,
        content_hash=body.content_hash,
        user_id=user["id"],
    )

    status = queue_manager.get_status()
    log.info(f"Snapshot queued for {body.app_name} ({body.bundle_id}), hash={body.content_hash}")

    return {"status": "queued", "queue_size": status["queue_size"]}
