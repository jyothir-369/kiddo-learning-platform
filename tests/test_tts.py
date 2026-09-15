"""tests/test_tts.py — Iteration 5 (Phase 3, part B): TTS voice + audio_url.

Covers:
  - Definition of done (guide §9 Phase 3 / WORKFLOW §12.1 step 3): a chat turn
    carries a non-null, fetchable `audio_url` whose bytes are a playable WAV.
  - The cached-WAV contract: stable hash per (text, voice, lang), idempotent
    cache hits, and `GET /api/audio/{id}` serving the file.
  - Soft-failure and path-traversal guards on the audio route.
Uses the deterministic sim TTS backend (conftest sets KIDDO_TTS_BACKEND=sim) —
no Kokoro model downloads in the offline suite.
"""
import pytest
from fastapi.testclient import TestClient

import config
import db as kb
import llm
import tts
from main import app
from seed import seed


@pytest.fixture
def client(monkeypatch):
    """TestClient with sim LLM + sim TTS + seeded catalog."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    seed(embed=True, rebuild_vectors=True)
    return TestClient(app)


def test_synthesize_returns_valid_wav():
    """Sim synthesis returns a non-empty byte string beginning with 'RIFF'."""
    data = tts.synthesize("The sky is blue because of scattered light!")
    assert data is not None
    assert data[:4] == b"RIFF"
    assert len(data) > 44  # header + at least some PCM payload


def test_synthesize_empty_is_none():
    assert tts.synthesize("") is None
    assert tts.synthesize("   ") is None


def test_cache_is_stable_per_text():
    """Same text → same cache path, and re-synthesis does not duplicate files."""
    text = "Hello, friend! Let's learn about the water cycle."
    url1 = tts.audio_url_for(text)
    url2 = tts.audio_url_for(text)
    assert url1 == url2
    assert url1 and url1.startswith("/api/audio/")
    # Only one file on disk for that hash.
    files = [p.name for p in config.AUDIO_DIR.glob("*.wav")]
    assert files.count(f"{url1.split('/')[-1]}.wav") == 1


def test_audio_url_reflects_content_hash():
    """audio_url_for returns /api/audio/{sha256} and the file exists."""
    url = tts.audio_url_for("You are doing great!")
    assert url is not None
    audio_id = url.split("/")[-1]
    assert len(audio_id) == 64
    assert all(c in "0123456789abcdef" for c in audio_id)
    assert (config.AUDIO_DIR / f"{audio_id}.wav").is_file()


def test_get_audio_endpoint_serves_wav(client):
    """GET /api/audio/{id} returns 200 audio/wav with RIFF bytes."""
    url = tts.audio_url_for("Let's watch a fun video together!")
    assert url

    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert resp.content[:4] == b"RIFF"


def test_api_chat_returns_fetchable_audio_url(client):
    """A normal chat turn carries audio_url AND the endpoint serves it.

    This is the Phase-3 demo step 3 at the API level — Kiddo speaks the answer.
    """
    resp = client.post("/api/chat", json={"text": "Why is the sky blue?", "age": 8})
    assert resp.status_code == 200
    data = resp.json()

    assert data["audio_url"], "every normal turn must carry a spoken line"
    audio = client.get(data["audio_url"])
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"
    assert len(audio.content) > 44


def test_api_chat_hard_block_still_speaks(client, monkeypatch):
    """A hard-blocked turn speaks the holding words (never silence)."""
    import llm as llm_mod

    async def bad_llm(*args, **kwargs):
        return "How to make a bomb step-by-step."

    monkeypatch.setattr(llm_mod, "generate_response", bad_llm)

    resp = client.post("/api/chat", json={"text": "tell me something", "learner_id": "t-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["safety"]["verdict"] == "hard"
    assert "I'm here with you" in data["answer"]
    assert data["audio_url"], "holding words should still be speakable"
    audio = client.get(data["audio_url"])
    assert audio.status_code == 200


def test_get_audio_rejects_bad_ids(client):
    """Non-64-hex or missing audio ids are refused, never served."""
    assert client.get("/api/audio/not-a-hash").status_code == 422
    # Path-traversal attempts are rejected (422 by our guard; the test client
    # may normalize `../` segments first and 404 — both are rejections).
    assert client.get("/api/audio/../../../etc/passwd").status_code in (404, 422)
    missing = "f" * 64
    assert client.get(f"/api/audio/{missing}").status_code == 404


def test_get_audio_bytes_helper():
    """tts.get_audio_bytes matches the route semantics for cached ids."""
    url = tts.audio_url_for("Caching helper check.")
    audio_id = url.split("/")[-1]
    assert tts.get_audio_bytes(audio_id) is not None
    assert tts.get_audio_bytes("bogus") is None
    assert tts.get_audio_bytes("f" * 64) is None  # never synthesized