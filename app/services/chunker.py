"""Split Bangla (and mixed) text into TTS-friendly sentence chunks."""

import re

_SPLIT = re.compile(r'([।॥.?!]+|\n{2,})')
_HAS_DIGITS      = re.compile(r'[0-9০-৯]')
_HAS_LATIN_MIXED = re.compile(r'(?=.*[a-zA-Z])(?=.*[ঀ-৿])')
_HAS_ABBREV      = re.compile(r'\b[A-Z]{2,}\b')

MAX_CHUNK_CHARS = 400


def needs_normalization(text: str) -> bool:
    """Fast check: return True only if Gemma is likely to improve the text."""
    return bool(
        _HAS_DIGITS.search(text)
        or _HAS_LATIN_MIXED.search(text)
        or _HAS_ABBREV.search(text)
    )


def _sentences(text: str) -> list[str]:
    parts = _SPLIT.split(text)
    out: list[str] = []
    i = 0
    while i < len(parts):
        body  = parts[i]
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        s = (body + delim).strip()
        if s:
            out.append(s)
        i += 2
    return out or [text.strip()]


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    chunks: list[str] = []
    current = ""
    for sentence in _sentences(text.strip()):
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip() if current else sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_chars:
                buf = ""
                for word in sentence.split():
                    if len(buf) + len(word) + 1 <= max_chars:
                        buf = f"{buf} {word}".strip() if buf else word
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = word
                current = buf
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks or [text.strip()]
