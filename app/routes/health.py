import logging

import ollama
from fastapi import APIRouter

from app.config import settings
from app.services.normalizer import normalizer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/", summary="Root")
def root():
    return {"service": "Bangla TTS API", "version": "1.0.0", "docs": "/docs"}


@router.get("/health", summary="Health check with dependency status")
async def health():
    ollama_ok = False
    available_models: list[str] = []

    try:
        client = ollama.AsyncClient(host=settings.ollama_host)
        resp = await client.list()
        models = resp.models if hasattr(resp, "models") else resp.get("models", [])
        available_models = [
            m.model if hasattr(m, "model") else m.get("model", m.get("name", str(m)))
            for m in models
        ]
        ollama_ok = True
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)

    model_ready = any(settings.gemma_model in m for m in available_models)

    return {
        "status": "healthy" if (ollama_ok and model_ready) else "degraded",
        "ollama": {"reachable": ollama_ok, "models": available_models},
        "model": {"name": settings.gemma_model, "ready": model_ready},
        "cache": {"size": normalizer.cache_size, "maxsize": settings.cache_maxsize},
    }
