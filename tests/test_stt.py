"""Tests for STT (Iteration 8 / Phase 5A) — transcription, multipart, speech miss, text fallback."""
import io
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    return TestClient(app)


def test_transcribe_success_with_confidence(monkeypatch):
    """stt.transcribe -> text + confidence + segments when faster-whisper available."""
    import stt
    # Mock WhisperModel
    mock_seg = MagicMock()
    mock_seg.text = "hello world"
    mock_seg.avg_logprob = -1.5  # scales to 0.75 after /2
    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)
    with patch("stt.WhisperModel", return_value=mock_model):
        result = stt.transcribe("dummy.wav")
    assert result["text"] == "hello world"
    assert result["confidence"] == pytest.approx(0.75, abs=0.01)
    assert result["language"] == "en"
    assert result["segments"] == 1


def test_transcribe_empty_segments():
    """No segments -> empty text, 0.0 confidence."""
    import stt
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], None)
    with patch("stt.WhisperModel", return_value=mock_model):
        result = stt.transcribe("empty.wav")
    assert result["text"] == ""
    assert result["confidence"] == 0.0


def test_repair_transcript_raises_confidence():
    import stt
    repaired = stt.repair_transcript("hello  world", 0.6)
    assert repaired["text"] == "hello world"
    assert repaired["confidence"] == pytest.approx(0.75, abs=0.01)
    assert repaired["repaired"] is True


def test_chat_multipart_audio_transcription_success(client, monkeypatch):
    """POST /api/chat with audio file -> transcribed -> normal answer pipeline."""
    import stt
    # Mock STT to return high-confidence transcript
    monkeypatch.setattr(stt, "transcribe", lambda path: {
        "text": "why is sky blue",
        "confidence": 0.82,
        "language": "en",
        "segments": 1,
    })
    # Build minimal fake audio file
    audio_bytes = b"\x00\x01\x02\x03" * 1024  # dummy webm-ish bytes
    resp = client.post(
        "/api/chat",
        data={"text": "", "age": 8},
        files={"audio": ("test.webm", io.BytesIO(audio_bytes), "audio/webm")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_name"] == "Kiddo Assist"
    assert isinstance(data["answer"], str) and len(data["answer"]) > 0
    assert data["safety"]["verdict"] == "pass"


def test_chat_speech_miss_low_confidence(client, monkeypatch):
    """Low confidence (<0.55) or empty transcript -> exact speech-miss line, TTS audio, no dead-end."""
    import stt
    monkeypatch.setattr(stt, "transcribe", lambda path: {
        "text": "",
        "confidence": 0.2,
        "language": "en",
        "segments": 0,
    })
    audio_bytes = b"\xff\xfe" * 512
    resp = client.post(
        "/api/chat",
        data={"text": "", "age": 8},
        files={"audio": ("bad.webm", io.BytesIO(audio_bytes), "audio/webm")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "I didn't catch that — want to tap it for me?"
    # TTS should have been attempted; audio_url may be null in sim mode but contract kept
    assert "audio_url" in data
    # UI must never dead-end: response always carries safe answer (not 422 / crash)
    assert data["safety"]["verdict"] == "pass"


def test_chat_speech_miss_empty_text(client, monkeypatch):
    """Empty transcript with 0 confidence triggers miss path (same as low conf)."""
    import stt
    monkeypatch.setattr(stt, "transcribe", lambda path: {
        "text": "",
        "confidence": 0.0,
        "language": "en",
        "segments": 0,
    })
    resp = client.post(
        "/api/chat",
        data={"text": "", "age": 8},
        files={"audio": ("empty.webm", io.BytesIO(b"\x00" * 256), "audio/webm")},
    )
    data = resp.json()
    assert data["answer"] == "I didn't catch that — want to tap it for me?"


def test_chat_text_fallback_no_audio(client):
    """No audio provided -> existing text pipeline unchanged (Iteration 7 behavior preserved)."""
    resp = client.post("/api/chat", json={"text": "Why is sky blue?", "age": 8})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_name"] == "Kiddo Assist"
    assert "blue" in data["answer"].lower()
    assert data["safety"]["verdict"] == "pass"
