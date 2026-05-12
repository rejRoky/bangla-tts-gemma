"""Split Bangla (and mixed) text into TTS-friendly sentence chunks."""

import re

# Bangla daari (।) + standard punctuation + paragraph breaks
_SPLIT = re.compile(r'([।॥.?!]+|\n{2,})')

MAX_CHUNK_CHARS = 400   # edge-tts works best under ~500 chars


def _sentences(text: str) -> list[str]:
    parts = _SPLIT.split(text)
    out: list[str] = []
    i = 0
    while i < len(parts):
        body = parts[i]
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        s = (body + delim).strip()
        if s:
            out.append(s)
        i += 2
    return out or [text.strip()]


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Split text into chunks ≤ max_chars by grouping sentences.
    Sentences longer than max_chars are split at word boundaries.
    """
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
            # sentence itself is too long → split at word boundaries
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
