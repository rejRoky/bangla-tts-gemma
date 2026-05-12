"""Basic API tests — run with: pytest tests/"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "Bangla TTS API"


def test_health_returns_200():
    with patch("app.routes.health.ollama.AsyncClient") as mock_cls:
        mock_cls.return_value.list = AsyncMock(return_value={"models": [{"name": "gemma3:4b"}]})
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "ollama" in data


def test_tts_empty_text_returns_422():
    r = client.post("/tts", json={"text": ""})
    assert r.status_code == 422


def test_tts_text_too_long_returns_422():
    r = client.post("/tts", json={"text": "ক" * 5001})
    assert r.status_code == 422


def test_normalize_returns_json():
    with patch("app.routes.tts.normalizer.normalize", new_callable=AsyncMock) as mock_norm:
        mock_norm.return_value = "আজকের তারিখ বারো মে"
        r = client.post("/tts/normalize", json={"text": "আজকের তারিখ ১২-০৫-২০২৬"})
    assert r.status_code == 200
    data = r.json()
    assert data["original"] == "আজকের তারিখ ১২-০৫-২০২৬"
    assert data["normalized"] == "আজকের তারিখ বারো মে"


def test_tts_produces_audio():
    with (
        patch("app.routes.tts.normalizer.normalize", new_callable=AsyncMock) as mock_norm,
        patch("app.routes.tts.synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".mp3")
        os.write(fd, b"\xff\xfb" + b"\x00" * 128)  # minimal MP3-like bytes
        os.close(fd)

        mock_norm.return_value = "আমার সোনার বাংলা"
        mock_synth.return_value = tmp

        r = client.post("/tts", json={"text": "আমার সোনার বাংলা"})

    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
