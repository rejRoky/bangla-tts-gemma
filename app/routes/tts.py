import logging
import os
import urllib.parse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.background import BackgroundTask

from app.config import settings
from app.services.normalizer import normalizer
from app.services.synthesizer import synthesize

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/tts", tags=["tts"])


# ── request / response schemas ────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    model: str | None = None
    normalize: bool = True
    slow: bool = False

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


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    summary="Convert Bangla text to MP3 speech",
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio file"},
        400: {"description": "Invalid request"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)
@limiter.limit(settings.rate_limit)
async def tts_endpoint(request: Request, req: TTSRequest):
    logger.info("TTS request text_len=%d normalize=%s", len(req.text), req.normalize)

    try:
        text = req.text
        normalized_text: str | None = None

        if req.normalize:
            normalized_text = await normalizer.normalize(text, model=req.model)
            logger.debug("normalized: %r → %r", text[:60], normalized_text[:60])
            text = normalized_text

        audio_path = await synthesize(text, slow=req.slow)

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="output.mp3",
            headers={
                "X-Original-Text": urllib.parse.quote(req.text),
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
    summary="Normalize Bangla text without synthesising speech",
)
@limiter.limit(settings.rate_limit)
async def normalize_endpoint(request: Request, req: TTSRequest):
    logger.info("Normalize request text_len=%d", len(req.text))
    try:
        model = req.model or settings.gemma_model
        normalized = await normalizer.normalize(req.text, model=req.model)
        return NormalizeResponse(original=req.text, normalized=normalized, model=model)
    except Exception as exc:
        logger.exception("Normalisation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── helpers ───────────────────────────────────────────────────────────────────

def _delete_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
