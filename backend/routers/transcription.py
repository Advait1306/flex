import os

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import verify_user

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_SESSION_URL = "https://api.openai.com/v1/realtime/transcription_sessions"


@router.post("/session")
async def create_transcription_session(user: dict = Depends(verify_user)):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENAI_SESSION_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-transcribe",
                    "language": "en",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
                "input_audio_noise_reduction": {
                    "type": "near_field",
                },
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"OpenAI API error: {response.text}",
        )

    data = response.json()
    return {
        "client_secret": data["client_secret"],
        "expires_at": data.get("expires_at"),
    }
