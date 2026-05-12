import json
import logging
import os
import urllib.parse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.background import BackgroundTask

from app.config import settings
from app.services.normalizer import normalizer
from app.services.synthesizer import (
    DEFAULT_VOICE,
    VOICES,
    pop_audio,
    store_audio,
    synthesize,
)

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/tts", tags=["tts"])


# ── schemas ───────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    model: str | None = None
    normalize: bool = True
    slow: bool = False
    voice: str = DEFAULT_VOICE

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be empty")
        if len(v) > 5000:
            raise ValueError("text must be 5000 characters or fewer")
        return v


class NormalizeResponse(BaseModel):
    original: str
    normalized: str
    model: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _sse(event_type: str, **data) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def _delete_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ── SSE streaming endpoint ────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Stream TTS progress via Server-Sent Events",
    response_class=StreamingResponse,
)
@limiter.limit(settings.rate_limit)
async def tts_stream(request: Request, req: TTSRequest):
    """
    Returns an SSE stream with events:
      {type: 'start'}
      {type: 'progress', msg: '...'}
      {type: 'normalized', text: '...'}
      {type: 'ready', audio_id: '...'}
      {type: 'done'}
      {type: 'error', msg: '...'}
    Fetch audio at GET /tts/audio/{audio_id}
    """
    async def generate():
        try:
            yield _sse("start")

            text = req.text
            if req.normalize:
                yield _sse("progress", msg="Normalizing with Gemma…")
                text = await normalizer.normalize(text, model=req.model)
                logger.debug("normalized: %r → %r", req.text[:40], text[:40])
                yield _sse("normalized", text=text)

            yield _sse("progress", msg="Synthesizing speech with edge-tts…")
            audio_path = await synthesize(text, slow=req.slow, voice=req.voice)
            audio_id = store_audio(audio_path)

            yield _sse("ready", audio_id=audio_id)
            yield _sse("done")

        except Exception as exc:
            logger.exception("SSE TTS pipeline failed")
            yield _sse("error", msg=str(exc))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # tell nginx not to buffer SSE
            "Connection": "keep-alive",
        },
    )


# ── audio serve endpoint ──────────────────────────────────────────────────────

@router.get(
    "/audio/{audio_id}",
    summary="Fetch generated audio by ID (valid for 5 minutes)",
)
async def get_audio(audio_id: str):
    path = pop_audio(audio_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio not found or expired")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename="bangla_tts.mp3",
        background=BackgroundTask(_delete_file, path),
    )


# ── voices list ───────────────────────────────────────────────────────────────

@router.get("/voices", summary="List available Bangla TTS voices")
def list_voices():
    return {"voices": VOICES, "default": DEFAULT_VOICE}


# ── classic POST (kept for API clients) ──────────────────────────────────────

@router.post(
    "",
    summary="Convert Bangla text to MP3 (single blocking request)",
)
@limiter.limit(settings.rate_limit)
async def tts_endpoint(request: Request, req: TTSRequest):
    logger.info("TTS request len=%d normalize=%s", len(req.text), req.normalize)
    try:
        text = req.text
        normalized_text: str | None = None
        if req.normalize:
            normalized_text = await normalizer.normalize(text, model=req.model)
            text = normalized_text

        audio_path = await synthesize(text, slow=req.slow, voice=req.voice)
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="output.mp3",
            headers={
                "X-Original-Text":   urllib.parse.quote(req.text),
                "X-Normalized-Text": urllib.parse.quote(normalized_text or req.text),
                "Cache-Control": "no-store",
            },
            background=BackgroundTask(_delete_file, audio_path),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("TTS pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    summary="Normalize Bangla text only",
)
@limiter.limit(settings.rate_limit)
async def normalize_endpoint(request: Request, req: TTSRequest):
    try:
        model = req.model or settings.gemma_model
        normalized = await normalizer.normalize(req.text, model=req.model)
        return NormalizeResponse(original=req.text, normalized=normalized, model=model)
    except Exception as exc:
        logger.exception("Normalisation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
