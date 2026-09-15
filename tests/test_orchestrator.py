"""tests/test_orchestrator.py — Iteration 3 (Phase 2): learning agent + RAG.

Covers the definition of done (guide §9 Phase 2):
  'Ask "why is the sky blue?" returns an answer citing an ingested content item'
  — asserted against both the orchestrator result (`sources` metadata) and the
  live `POST /api/chat` contract (the `sources` field).
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import orchestrator
from main import app
from seed import seed


@pytest.fixture
def seeded_catalog():
    """Fresh sim-seeded catalog (SQLite + LanceDB) in the temp store."""
    seed(embed=True, rebuild_vectors=True)


@pytest.fixture
def client(monkeypatch):
    """TestClient with the simulated LLM backend (fast + deterministic)."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    return TestClient(app)


def test_learning_turn_is_grounded_in_seeded_content(seeded_catalog, monkeypatch):
    """The orchestrator answers "why is the sky blue" from the approved KB."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    result = asyncio.run(orchestrator.learning_turn("why is the sky blue"))

    assert result["answer"]
    assert "blue" in result["answer"].lower()

    # Grounding metadata exists and points at the seeded sky-blue source/video.
    assert result["sources"], "an answer grounded in the KB must carry sources"
    top = result["sources"][0]
    assert top["id"] in {"src-sky-blue", "vid-sky-blue"}
    assert top["attribution"]  # so the child can be told *where* Kiddo learned it

    # The LLM context was actually built from the retrieved transcript.
    assert result["context"] is not None
    assert "scatter" in result["context"].lower()


def test_learning_turn_without_catalog_answers_ungrounded(monkeypatch):
    """No seeded vectors (empty store) -> honest ungrounded answer, no sources."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    result = asyncio.run(orchestrator.learning_turn("why is the sky blue"))
    assert result["answer"]
    assert result["sources"] == []
    assert result["context"] is None


def test_chat_api_returns_grounding(seeded_catalog, client):
    """Phase 2 definition of done through the live contract.

    `POST /api/chat` for "why is the sky blue?" returns an answer grounded in an
    approved content item, surfaced in `sources` metadata.
    """
    resp = client.post("/api/chat", json={"text": "Why is the sky blue?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["assistant_name"] == "Kiddo Assist"
    assert data["answer"]
    assert "blue" in data["answer"].lower()
    assert data["safety"]["verdict"] == "pass"

    # RAG grounding: the answer cites an ingested content item (guide §9 Phase 2).
    assert data["sources"], "chat response must carry RAG grounding sources"
    assert data["sources"][0]["id"] in {"src-sky-blue", "vid-sky-blue"}
    assert data["sources"][0]["attribution"] in (
        "Wikipedia contributors, 'Diffuse sky radiation', CC BY-SA 4.0",
        "Wikimedia Commons, 'Sky', CC BY-SA 4.0",
    )


def test_chat_returns_empty_sources_when_unseeded(client):
    """Before any catalog exists, RAG is empty and no grounding is claimed."""
    resp = client.post("/api/chat", json={"text": "What is a dinosaur?"})
    data = resp.json()
    assert data["answer"]
    assert data["sources"] == []