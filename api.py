#!/usr/bin/env python3
"""FastAPI server for Bangla TTS — Gemma normalisation + gTTS synthesis."""

import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from tts import normalize, synthesize, GEMMA_MODEL

app = FastAPI(
    title="Bangla TTS API",
    description="Text-to-Speech for Bangla using Gemma (normalisation) + gTTS (synthesis)",
    version="1.0.0",
)


class TTSRequest(BaseModel):
    text: str
    model: str = GEMMA_MODEL
    normalize: bool = True
    slow: bool = False


@app.get("/")
def root():
    return {"status": "ok", "service": "Bangla TTS API"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/tts")
def tts(req: TTSRequest):
    """Convert Bangla text to speech. Returns an MP3 audio file."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")

    try:
        text = req.text
        normalized_text = None

        if req.normalize:
            normalized_text = normalize(text, model=req.model)
            text = normalized_text

        audio_path = synthesize(text, slow=req.slow)

        # Stream file then clean up
        import urllib.parse
        response = FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="output.mp3",
            headers={
                "X-Original-Text": urllib.parse.quote(req.text),
                "X-Normalized-Text": urllib.parse.quote(normalized_text or req.text),
            },
        )
        # Delete temp file after response is sent
        response.background = _cleanup(audio_path)
        return response

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/normalize")
def normalize_text(req: TTSRequest):
    """Normalize Bangla text using Gemma without synthesising speech."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")
    try:
        result = normalize(req.text, model=req.model)
        return {"original": req.text, "normalized": result, "model": req.model}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── background cleanup helper ─────────────────────────────────────────────────

from starlette.background import BackgroundTask

def _cleanup(path: str) -> BackgroundTask:
    def delete():
        try:
            os.unlink(path)
        except OSError:
            pass
    return BackgroundTask(delete)


# ── run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
