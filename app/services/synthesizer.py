import asyncio
import logging
import os
import secrets
import tempfile
import time
from functools import partial

logger = logging.getLogger(__name__)

# ── voice config ──────────────────────────────────────────────────────────────

VOICES = {
    "female-bd": "bn-BD-NabanitaNeural",
    "male-bd":   "bn-BD-PradeepNeural",
    "female-in": "bn-IN-TanishaaNeural",
    "male-in":   "bn-IN-BashkarNeural",
}
DEFAULT_VOICE = "bn-BD-NabanitaNeural"

# ── audio result cache (TTL = 5 min) ─────────────────────────────────────────

_TTL = 300
_audio_store: dict[str, tuple[str, float]] = {}  # id → (path, expires_at)


def store_audio(path: str) -> str:
    audio_id = secrets.token_urlsafe(12)
    _audio_store[audio_id] = (path, time.monotonic() + _TTL)
    _evict_expired()
    return audio_id


def pop_audio(audio_id: str) -> str | None:
    entry = _audio_store.get(audio_id)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    _audio_store.pop(audio_id, None)
    return None


def _evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (_, exp) in _audio_store.items() if exp <= now]
    for k in expired:
        path, _ = _audio_store.pop(k)
        try:
            os.unlink(path)
        except OSError:
            pass


# ── edge-tts (primary — async, Microsoft Neural) ──────────────────────────────

async def _synthesize_edge(text: str, voice: str, rate: str) -> str:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="btts_")
    os.close(fd)
    await communicate.save(path)
    logger.debug("edge-tts saved path=%s size=%d", path, os.path.getsize(path))
    return path


# ── gTTS (fallback — sync, wrapped in thread pool) ───────────────────────────

def _synthesize_gtts_sync(text: str, slow: bool) -> str:
    from gtts import gTTS
    from app.config import settings
    tts = gTTS(text=text, lang=settings.gtts_lang, slow=slow)
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="btts_")
    os.close(fd)
    tts.save(path)
    logger.debug("gTTS saved path=%s size=%d", path, os.path.getsize(path))
    return path


async def _synthesize_gtts(text: str, slow: bool) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_synthesize_gtts_sync, text, slow))


# ── public API ────────────────────────────────────────────────────────────────

async def synthesize(
    text: str,
    slow: bool = False,
    voice: str = DEFAULT_VOICE,
) -> str:
    """Synthesize Bangla speech. Tries edge-tts first, falls back to gTTS."""
    rate = "-20%" if slow else "+0%"
    try:
        return await _synthesize_edge(text, voice=voice, rate=rate)
    except Exception as exc:
        logger.warning("edge-tts failed (%s), falling back to gTTS", exc)
        return await _synthesize_gtts(text, slow=slow)
