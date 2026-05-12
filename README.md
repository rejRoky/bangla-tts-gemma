# bangla-tts-gemma

Production-grade Bangla (Bengali) Text-to-Speech system — **Gemma 3** normalises text via Ollama, **Microsoft edge-tts** synthesises neural audio, streamed live over SSE.

## Architecture

```text
Browser
  │
  ▼
Nginx :80
  ├── /          → Streamlit frontend  (8501)
  ├── /api/*     → FastAPI backend     (8000)
  └── /api/tts/stream  (SSE, buffering off)
                          │
                          ├── Ollama :11434  (gemma3:4b — normalisation)
                          └── edge-tts       (Microsoft Neural TTS — synthesis)
```

Key behaviours:

- Clean Bangla (no digits / Latin / abbreviations) **skips Gemma entirely** — response under 1 s
- Long text is split on `।`, `.`, `?`, `!`, `\n\n` into ≤ 400-char chunks, processed **fully in parallel**
- Audio **auto-plays** in the browser the moment synthesis is ready
- Audio files are stored on disk so all gunicorn workers can serve the same result

---

## Quick start (Docker)

```bash
# 1. Copy env template
cp .env.example .env          # edit if needed

# 2. Pull the Gemma model (one-time, ~3 GB)
ollama pull gemma3:4b

# 3. Start the stack
docker compose up --build

# 4. Open the app
open http://localhost
```

> Requires Docker ≥ 24 and a locally installed Ollama with `gemma3:4b` already pulled.  
> The compose file mounts `~/.ollama` into the container so the model is not re-downloaded.

---

## Environment variables (`.env`)

| Variable | Default | Description |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama base URL (overridden to `http://ollama:11434` in Docker) |
| `GEMMA_MODEL` | `gemma3:4b` | Ollama model used for normalisation |
| `WORKERS` | `4` | Gunicorn worker count |
| `LOG_LEVEL` | `info` | Uvicorn log level |
| `RATE_LIMIT` | `30/minute` | Per-IP rate limit (slowapi) |
| `CACHE_MAXSIZE` | `1024` | LRU cache size for normalisation results |

---

## API reference

All endpoints are reachable at `http://localhost/api/` (via Nginx).

### `POST /api/tts/stream` — SSE streaming synthesis

```json
{
  "text":      "আজকের তারিখ ১২-০৫-২০২৬",
  "model":     "gemma3:4b",
  "normalize": true,
  "slow":      false,
  "voice":     "bn-BD-NabanitaNeural"
}
```

Returns `text/event-stream`. Each `data:` line is a JSON event:

| `type` | Fields | Meaning |
| --- | --- | --- |
| `start` | `total_chunks`, `normalizing` | Job started |
| `chunk_norm` | `chunk`, `total`, `preview` | Chunk normalised |
| `chunk_done` | `chunk`, `total`, `percent` | Chunk synthesised |
| `ready` | `audio_id`, `total_chunks`, `normalized_chunks` | All done, audio ready |
| `error` | `msg` | Something went wrong |
| `done` | — | Stream closed |

### `GET /api/tts/audio/{audio_id}` — fetch audio

Returns the merged `audio/mpeg` file. Valid for **5 minutes** after generation.

### `GET /api/tts/voices` — list voices

```json
{
  "voices": {
    "female-bd": "bn-BD-NabanitaNeural",
    "male-bd":   "bn-BD-PradeepNeural",
    "female-in": "bn-IN-TanishaaNeural",
    "male-in":   "bn-IN-BashkarNeural"
  },
  "default": "bn-BD-NabanitaNeural"
}
```

### `POST /api/tts/normalize` — normalise only (no audio)

```json
{ "text": "আজকের তারিখ ১২-০৫-২০২৬", "model": "gemma3:4b" }
```

### `POST /api/tts` — blocking synthesis (no streaming)

Same request body as `/tts/stream`; returns `{ "audio_id": "...", "normalized_chunks": [...] }`.

### `GET /health`

```json
{
  "status": "ok",
  "ollama": "ok",
  "model": "gemma3:4b",
  "cache_size": 12
}
```

---

## Bangla voices

| Key | Voice | Language |
| --- | --- | --- |
| `female-bd` | bn-BD-NabanitaNeural | Bangladeshi Bangla (F) |
| `male-bd` | bn-BD-PradeepNeural | Bangladeshi Bangla (M) |
| `female-in` | bn-IN-TanishaaNeural | Indian Bengali (F) |
| `male-in` | bn-IN-BashkarNeural | Indian Bengali (M) |

---

## CLI tool (`tts.py`)

Local use without Docker:

```bash
# Install deps
pip install -r requirements.txt

# Speak text (auto-normalises)
python tts.py "আমার সোনার বাংলা"

# Save to MP3
python tts.py "বাংলাদেশ" -o output.mp3

# Specific model
python tts.py --model gemma3:4b "আজকের তারিখ ১২-০৫-২০২৬"

# Skip Gemma normalisation
python tts.py --no-normalize "বাংলাদেশ"

# Slower speech
python tts.py --slow "আমার সোনার বাংলা"
```

---

## Project structure

```text
.
├── app/
│   ├── main.py                 # FastAPI app factory, middleware
│   ├── config.py               # pydantic-settings config
│   ├── routes/
│   │   ├── tts.py              # /tts/* endpoints, SSE pipeline
│   │   └── health.py           # /health
│   └── services/
│       ├── normalizer.py       # Gemma via Ollama, LRU cache
│       ├── synthesizer.py      # edge-tts primary, gTTS fallback, audio store
│       └── chunker.py          # sentence splitter, needs_normalization()
├── frontend/
│   ├── app.py                  # Streamlit UI
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── tts.py                      # CLI entry point
├── Dockerfile                  # API multi-stage build
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Performance

| Input | Normalise | Typical latency |
| --- | --- | --- |
| Clean Bangla (no digits/Latin) | skipped | < 1 s |
| Text with numbers / abbreviations | Gemma | ~3–5 s per chunk |
| Multi-chunk, parallel | Gemma | ≈ 1 chunk time (all run concurrently) |

---

## Author

**Rejaul Islam Roky** — [github.com/rejRoky](https://github.com/rejRoky) · [rejaul.islam.roky@gmail.com](mailto:rejaul.islam.roky@gmail.com)

---

## License

MIT — see [LICENSE](LICENSE)
