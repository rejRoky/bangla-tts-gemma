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

# ── audio result store — filesystem-backed so all gunicorn workers can share ──

_TTL = 300  # seconds
_AUDIO_DIR = os.path.join(tempfile.gettempdir(), "btts_audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)


def _audio_path(audio_id: str) -> str:
    return os.path.join(_AUDIO_DIR, f"{audio_id}.mp3")


def store_audio(path: str) -> str:
    audio_id = secrets.token_urlsafe(12)
    dest = _audio_path(audio_id)
    os.replace(path, dest)
    _evict_expired()
    return audio_id


def pop_audio(audio_id: str) -> str | None:
    # Validate token shape to prevent path traversal
    if not audio_id.replace("-", "").replace("_", "").isalnum():
        return None
    p = _audio_path(audio_id)
    if not os.path.exists(p):
        return None
    if time.time() - os.path.getmtime(p) > _TTL:
        try:
            os.unlink(p)
        except OSError:
            pass
        return None
    return p


def _evict_expired() -> None:
    now = time.time()
    try:
        for fname in os.listdir(_AUDIO_DIR):
            fp = os.path.join(_AUDIO_DIR, fname)
            try:
                if now - os.path.getmtime(fp) > _TTL:
                    os.unlink(fp)
            except OSError:
                pass
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


# ── audio merge (pydub + ffmpeg) ─────────────────────────────────────────────

def _merge_sync(paths: list[str]) -> str:
    fd, out = tempfile.mkstemp(suffix=".mp3", prefix="btts_merged_")
    os.close(fd)
    try:
        # prefer pydub + ffmpeg for clean crossfade-free joins
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for p in paths:
            combined += AudioSegment.from_mp3(p)
        combined.export(out, format="mp3", bitrate="64k")
    except Exception:
        # fallback: raw byte concat (works for same-bitrate edge-tts output)
        logger.warning("pydub/ffmpeg unavailable, using raw MP3 concat")
        with open(out, "wb") as fout:
            for p in paths:
                with open(p, "rb") as fin:
                    fout.write(fin.read())
    finally:
        for p in paths:
            try:
                os.unlink(p)
            except OSError:
                pass
    logger.debug("merged %d chunks → %s (%d bytes)", len(paths), out, os.path.getsize(out))
    return out


async def merge_audio(paths: list[str]) -> str:
    """Merge a list of MP3 files into one. Cleans up input files."""
    if len(paths) == 1:
        return paths[0]
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_merge_sync, paths))


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
