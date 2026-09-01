"""Standalone TTS endpoints (also used by the frontend 'replay' button)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.tts import VOICES, synthesize_async


class TTSRequest(BaseModel):
    text: str
    language: str = "english"
    gender: str = "female"
    rate: str = "+0%"


router = APIRouter(prefix="/api/tts", tags=["voice"])


@router.get("/voices")
async def voices() -> dict:
    return {"voices": {k: {"female": v[0], "male": v[1]} for k, v in VOICES.items()}}


@router.post("")
async def tts(req: TTSRequest) -> dict:
    if not req.text.strip():
        raise HTTPException(400, "empty text")
    sp = await synthesize_async(req.text, req.language, req.gender, req.rate)
    return {"audio_b64": sp.audio_b64, "mime": sp.mime, "voice": sp.voice, "words": sp.words}


@router.post("/stream")
async def tts_stream(req: TTSRequest) -> Response:
    """Raw audio/mpeg — handy for <audio src> and for ffmpeg video export."""
    sp = await synthesize_async(req.text, req.language, req.gender, req.rate)
    return Response(content=base64.b64decode(sp.audio_b64), media_type="audio/mpeg")
