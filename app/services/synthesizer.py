import asyncio
import logging
import os
import tempfile
from functools import partial

from gtts import gTTS

from app.config import settings

logger = logging.getLogger(__name__)


def _synthesize_sync(text: str, slow: bool) -> str:
    """Blocking gTTS call — runs in a thread-pool executor."""
    tts = gTTS(text=text, lang=settings.gtts_lang, slow=slow)
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="btts_")
    os.close(fd)
    tts.save(path)
    logger.debug("synthesised audio path=%s size=%d", path, os.path.getsize(path))
    return path


async def synthesize(text: str, slow: bool = False) -> str:
    """Async wrapper: offloads blocking gTTS I/O to thread pool."""
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(None, partial(_synthesize_sync, text, slow))
    return path
