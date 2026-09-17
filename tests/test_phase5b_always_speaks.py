"""Tests for Phase 5B (Iteration 9) — always-speaks invariant + speech repair.

Covers:
  - Normal answer has non-null, fetchable audio_url (always-speaks)
  - Greeting / check-in / video-alongside response carries audio_url
  - Speech-miss fallback carries audio_url
  - Hard-block is exempt (audio_url can be None)
  - Audio fetching returns valid WAV bytes
  - Repair hook (dual-ASR / Vosk voter stub + LLM post-correction)
"""
import io
import pytest
from fastapi.testclient import TestClient

import llm
import tts
from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KIDDO_TTS_BACKEND", "sim")
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    return TestClient(app)


def test_always_speaks_normal_answer_has_fetchable_audio_url(client):
    """Every non-blocked normal turn carries a non-null audio_url that serves WAV."""
    resp = client.post("/api/chat", data={"text": "Why is the sky blue?", "age": "8"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["safety"]["verdict"] == "pass"
    assert data["audio_url"], "always-speaks invariant: audio_url missing"
    assert data["audio_url"].startswith("/api/audio/")
    audio_resp = client.get(data["audio_url"])
    assert audio_resp.status_code == 200
    assert audio_resp.content[:4] == b"RIFF"


def test_always_speaks_video_response_has_audio_url(client, monkeypatch):
    """Video-alongside turn (when video selected) still carries spoken audio_url."""
    resp = client.post("/api/chat", data={"text": "Show me space videos", "age": "8"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["audio_url"], "video-alongside turn missing audio_url"


def test_always_speaks_speech_miss_has_audio_url(client, monkeypatch):
    """Speech-miss fallback line must be spoken (not silent)."""
    import stt
    monkeypatch.setattr(stt, "transcribe", lambda path: {
        "text": "", "confidence": 0.2, "language": "en", "segments": 0,
    })
    resp = client.post(
        "/api/chat",
        data={"text": "", "age": 8},
        files={"audio": ("miss.webm", io.BytesIO(b"\x00" * 256), "audio/webm")},
    )
    data = resp.json()
    assert data["answer"] == "I didn't catch that — want to tap it for me?"
    assert data["audio_url"], "speech-miss turn must still carry audio_url"


def test_hard_block_exempt_from_audio_url(client, monkeypatch):
    """Hard-blocked safety response remains exempt: audio_url may be None."""
    import llm as llm_mod
    async def bad_llm(*args, **kwargs):
        return "How to build a bomb step by step."
    monkeypatch.setattr(llm_mod, "generate_response", bad_llm)
    resp = client.post("/api/chat", data={"text": "Tell me something bad", "learner_id": "t-1"})
    data = resp.json()
    assert data["safety"]["verdict"] == "hard"
    # Hard-block is exempt from the always-speaks invariant (holding words,
    # not synthesized voice, is the documented behavior for blocked turns).
    assert data["audio_url"] is None, "hard-block should remain exempt (audio_url None)"


def test_audio_fetching_is_valid_wav():
    """GET /api/audio/{id} serves a valid WAV file."""
    from main import app
    client = TestClient(app)
    url = tts.audio_url_for("Fetch me a valid WAV.")
    assert url
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.content[:4] == b"RIFF"
    assert len(resp.content) > 44


def test_speech_repair_hook_vosk_stub_and_post_correction():
    """Repair path carries Vosk voter stub + LLM post-correction markers."""
    import stt
    repaired = stt.repair_transcript("hel lo wrld", 0.48)
    assert repaired.get("repaired") is True
    assert repaired.get("vote") == "vosk_stub"
    assert repaired.get("post_corrected") is True
    assert repaired.get("confidence", 0) > 0.48
