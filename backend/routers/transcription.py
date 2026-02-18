import asyncio
import base64
import json
import logging
import os

import bcrypt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db_models import User
from mistralai import Mistral
from mistralai.models import AudioFormat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
TRANSCRIPTION_MODEL = "voxtral-mini-transcribe-realtime-2602"


async def verify_ws_token(token: str) -> dict | None:
    """Verify a base64 Basic-auth token (same logic as auth.verify_user)."""
    try:
        decoded = base64.b64decode(token).decode()
        username, password = decoded.split(":", 1)
    except Exception:
        return None
    user = await User.filter(username=username).first()
    if user is None or not bcrypt.checkpw(
        password.encode(), user.password_hash.encode()
    ):
        return None
    return {"id": user.id, "username": user.username}


async def audio_from_queue(queue: asyncio.Queue[bytes | None]):
    """Async generator that yields audio chunks from a queue until None sentinel."""
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk


@router.websocket("/ws")
async def transcription_ws(ws: WebSocket, token: str = ""):
    user = await verify_ws_token(token)
    if user is None:
        await ws.close(code=4401, reason="Unauthorized")
        return

    await ws.accept()

    if not MISTRAL_API_KEY:
        await ws.send_json({"type": "error", "message": "MISTRAL_API_KEY not configured"})
        await ws.close(code=1011)
        return

    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
    client = Mistral(api_key=MISTRAL_API_KEY)

    async def receive_audio():
        """Read binary frames from client WS and push to queue."""
        try:
            while True:
                data = await ws.receive_bytes()
                await audio_queue.put(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Error receiving audio from client")
        finally:
            await audio_queue.put(None)

    async def relay_events():
        """Consume Mistral SDK events and send JSON text frames to client."""
        try:
            async for event in client.audio.realtime.transcribe_stream(
                audio_stream=audio_from_queue(audio_queue),
                model=TRANSCRIPTION_MODEL,
                audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=16000),
            ):
                event_type = getattr(event, "type", None)
                if event_type == "session.created":
                    await ws.send_json({"type": "session.created"})
                elif event_type == "transcription.text.delta":
                    await ws.send_json(
                        {"type": "transcription.text.delta", "text": event.text}
                    )
                elif event_type == "transcription.done":
                    await ws.send_json({"type": "transcription.done"})
                elif event_type == "error":
                    msg = (
                        event.error.message
                        if hasattr(event, "error")
                        else "Unknown error"
                    )
                    await ws.send_json({"type": "error", "message": str(msg)})
        except Exception as e:
            logger.exception("Mistral transcription error")
            try:
                await ws.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

    recv_task = asyncio.create_task(receive_audio())
    relay_task = asyncio.create_task(relay_events())

    try:
        done, pending = await asyncio.wait(
            [recv_task, relay_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            if not task.cancelled() and task.exception():
                logger.error("Transcription task error: %s", task.exception())
    finally:
        recv_task.cancel()
        relay_task.cancel()
        try:
            await ws.close()
        except Exception:
            pass
