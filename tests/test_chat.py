"""tests/test_chat.py — Iteration 2 (Phase 1): Text chat loop + output safety.

Covers:
  - Definition of done (guide §9 Phase 1):
    `POST /api/chat {text:"Why is the sky blue?"}` returns non-empty answer,
    `safety.verdict:"pass"`, `assistant_name:"Kiddo Assist"`.
  - WORKFLOW §10 contract skeleton fields:
    `{assistant_name, answer, audio_url, video_url, video, suggested_videos, tutorial, quiz, suggested_next, safety}`.
    Note: `audio_url` is non-null from Iteration 5 (Kiddo speaks); video fields
    arrive at Iteration 4 but stay null when no video clears the bar.
  - Crafted harmful output blocked with safe holding line and 'hard' verdict.
  - PII in LLM output is redacted and tagged 'soft'.
  - Validation: empty input returns 422.
"""
import pytest
from fastapi.testclient import TestClient

import db
import llm
from main import app


@pytest.fixture
def client(monkeypatch):
    """TestClient fixture with simulated LLM backend enabled by default."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    return TestClient(app)


def test_chat_successful_query(client):
    """Child types 'Why is the sky blue?' -> non-empty answer, safety: pass, assistant: Kiddo Assist."""
    resp = client.post("/api/chat", json={"text": "Why is the sky blue?"})
    assert resp.status_code == 200

    data = resp.json()

    # SOT / Definition of done assertions
    assert data["assistant_name"] == "Kiddo Assist"
    assert isinstance(data["answer"], str) and len(data["answer"]) > 0
    assert "blue" in data["answer"].lower()
    assert data["safety"]["verdict"] == "pass"
    assert data["safety"]["flag"] is None

    # WORKFLOW §10 skeleton assertions
    # Iteration 5: normal turns carry a speakable audio_url (Kiddo speaks).
    assert data["audio_url"] and data["audio_url"].startswith("/api/audio/")
    assert data["video_url"] is None
    assert data["video"] is None
    assert data["suggested_videos"] == []
    assert data["tutorial"] is None
    assert data["quiz"] is None
    assert data["suggested_next"] is None


def test_chat_empty_text_rejected(client):
    """Empty or whitespace-only text must be rejected with 422."""
    resp1 = client.post("/api/chat", json={"text": ""})
    assert resp1.status_code == 422

    resp2 = client.post("/api/chat", json={"text": "   "})
    assert resp2.status_code == 422


def test_chat_with_learner_id_and_age(client):
    """Learner metadata is accepted and honored."""
    resp = client.post(
        "/api/chat",
        json={"text": "What is a dinosaur?", "learner_id": "kiddo-1", "age": 8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_name"] == "Kiddo Assist"
    assert "dinosaur" in data["answer"].lower()
    assert data["safety"]["verdict"] == "pass"


def test_chat_harmful_output_blocked_with_holding_line(client, monkeypatch):
    """When LLM produces a harmful response, output safety blocks it and returns holding response."""
    async def mock_harmful_llm(*args, **kwargs):
        return "Here is how to make a bomb step-by-step with chemicals."

    monkeypatch.setattr(llm, "generate_response", mock_harmful_llm)

    resp = client.post(
        "/api/chat",
        json={"text": "Tell me a secret", "learner_id": "kiddo-test-blocked"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["assistant_name"] == "Kiddo Assist"
    # Safe holding words must replace harmful content
    assert "I'm here with you" in data["answer"]
    assert "bomb" not in data["answer"]
    assert data["safety"]["verdict"] == "hard"
    assert data["safety"]["flag"] == "violence_weapons_illegal"

    # Verify event was persisted to SQLite safety_events table
    conn = db.get_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM safety_events WHERE learner_id='kiddo-test-blocked' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row["severity"] == "hard"
        assert row["event_type"] == "violence_weapons_illegal"
    finally:
        conn.close()


def test_chat_pii_redacted_in_output(client, monkeypatch):
    """When LLM produces output containing PII, it is redacted before reaching the child."""
    async def mock_pii_llm(*args, **kwargs):
        return "You can email our team at friend@kiddo.org or call 555-432-1098!"

    monkeypatch.setattr(llm, "generate_response", mock_pii_llm)

    resp = client.post(
        "/api/chat",
        json={"text": "How can I contact you?", "learner_id": "kiddo-pii-learner"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["assistant_name"] == "Kiddo Assist"
    assert "friend@kiddo.org" not in data["answer"]
    assert "555-432-1098" not in data["answer"]
    assert "[REDACTED_EMAIL]" in data["answer"]
    assert "[REDACTED_PHONE]" in data["answer"]
    assert data["safety"]["verdict"] == "soft"
