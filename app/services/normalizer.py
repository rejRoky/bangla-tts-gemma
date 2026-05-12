import hashlib
import logging
from collections import OrderedDict

import ollama

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a Bangla text preprocessor for a Text-to-Speech engine.
Normalize the input so it sounds natural when spoken aloud:
- Expand Bangla/Arabic numerals to Bangla words (e.g. ৩ → তিন, 2026 → দুই হাজার ছাব্বিশ)
- Expand common abbreviations to full Bangla words
- Ensure sentences end with a period or comma for natural pauses
- Remove HTML tags, URLs, and non-Bangla/punctuation characters
- Keep the output strictly in Bangla

Return ONLY the cleaned Bangla text — no explanations, no English."""


class _LRUCache:
    """Thread-safe LRU cache backed by OrderedDict."""

    def __init__(self, maxsize: int) -> None:
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> str | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

    @property
    def size(self) -> int:
        return len(self._cache)


class NormalizerService:
    def __init__(self) -> None:
        self._cache = _LRUCache(settings.cache_maxsize)
        self._client = ollama.AsyncClient(host=settings.ollama_host)

    @staticmethod
    def _key(text: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()

    async def normalize(self, text: str, model: str | None = None) -> str:
        model = model or settings.gemma_model
        key = self._key(text, model)

        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("cache hit for normalisation key=%s", key[:8])
            return cached

        logger.debug("calling Gemma model=%s", model)
        resp = await self._client.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        result: str = resp["message"]["content"].strip()
        self._cache.set(key, result)
        return result

    @property
    def cache_size(self) -> int:
        return self._cache.size


# module-level singleton
normalizer = NormalizerService()
