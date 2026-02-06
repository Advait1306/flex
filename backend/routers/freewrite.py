from typing import Any, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai.logging_config import get_logger
from ai.queue_manager import get_queue_manager
from auth import verify_user
from store import load_freewrite, save_freewrite

log = get_logger("api.freewrite")

router = APIRouter(prefix="/api", tags=["freewrite"])


class FreewriteContent(BaseModel):
    content: List[Any]


def extract_text_from_blocks(blocks: List[Any]) -> str:
    """Extract all text content from BlockNote blocks."""
    texts = []
    for block in blocks:
        if isinstance(block, dict) and "content" in block:
            content = block["content"]
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
        if isinstance(block, dict) and "children" in block:
            texts.append(extract_text_from_blocks(block["children"]))
    return "".join(texts)


def truncate_to_last_n_words(text: str, max_words: int = 10000) -> str:
    """Truncate text to the last N words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[-max_words:])


@router.get("/freewrite")
async def get_freewrite(user: dict = Depends(verify_user)):
    """Get freewrite content."""
    content = await load_freewrite(user["id"])
    return {"content": content or []}


@router.put("/freewrite")
async def put_freewrite(body: FreewriteContent, user: dict = Depends(verify_user)):
    """Save freewrite content and trigger pipeline on new content."""
    old_content = await load_freewrite(user["id"]) or []
    old_text = extract_text_from_blocks(old_content)

    new_text = extract_text_from_blocks(body.content)

    # Find the new/changed text and queue pipeline trigger
    trigger_text = None
    if new_text.startswith(old_text):
        diff = new_text[len(old_text):]
        if diff.strip():
            trigger_text = diff.strip()
            log.info(f"[NEW] {trigger_text}")
    elif new_text != old_text:
        trigger_text = new_text.strip()
        log.info(f"[CHANGED] {trigger_text}")

    # Save first
    await save_freewrite(user["id"], body.content)

    # Queue pipeline trigger if there's new content
    if trigger_text:
        full_doc_text = extract_text_from_blocks(body.content)
        doc_context = truncate_to_last_n_words(full_doc_text, max_words=10000)

        queue_manager = get_queue_manager()
        await queue_manager.enqueue(
            trigger=trigger_text,
            document_id=f"freewrite:{user['id']}",
            user_id=user["id"],
            document_context=doc_context,
        )
        status = queue_manager.get_status()
        return {
            "status": "saved",
            "pipeline_queued": True,
            "queue_size": status["queue_size"],
        }

    return {"status": "saved", "pipeline_queued": False}
