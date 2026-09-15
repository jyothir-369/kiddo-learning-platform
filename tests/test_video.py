"""tests/test_video.py — Iteration 4 (Phase 3, part A): video selection + suggestions.

Covers:
  - Definition of done (guide §9 Phase 3 / WORKFLOW §12):
    "why is the sky blue?" → a relevant approved video is selected and surfaced
    in the /api/chat response with a stream-by-reference URL, 2-4 ranked
    suggestions, and licensed attribution.
  - Strong match → video; weak match (nothing clears VIDEO_BAR) → text-only fallback.
  - Suggested list excludes the selected best video and is 2-4 items.
  - GET /api/videos/{id} returns stream-by-reference metadata for approved items.
"""
import pytest
from fastapi.testclient import TestClient

import db as kb
import llm
import video
from main import app
from seed import seed


@pytest.fixture
def seeded_catalog():
    """Fresh sim-seeded catalog in the temp store."""
    seed(embed=True, rebuild_vectors=True)


@pytest.fixture
def client(monkeypatch):
    """TestClient with simulated LLM backend + seeded catalog."""
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    seed(embed=True, rebuild_vectors=True)
    return TestClient(app)


def _chunks_for(query: str, age: int | None = None) -> list[dict]:
    """Run RAG and return retrieval chunks (the input to video selection)."""
    import rag

    from orchestrator import age_to_band

    return rag.search(
        query,
        age_range=age_to_band(age),
        top_k=rag.TOP_K,
    )


def test_strong_match_returns_video(seeded_catalog):
    """'why is the sky blue' selects the sky-blue video at score >= VIDEO_BAR."""
    chunks = _chunks_for("why is the sky blue")
    best, score = video.select_best_video(chunks, age=8)

    assert best is not None, "a strong sky-blue query must clear VIDEO_BAR"
    assert score >= video.VIDEO_BAR
    assert best["content_item_id"] == "vid-sky-blue"
    # Stream-by-reference: never served from local storage.
    assert best.get("url", "").startswith("https://")


def test_weak_match_returns_text_fallback(seeded_catalog):
    """A query with no video match → no best video (text fallback)."""
    # A gibberish query retrieves something but should not reach the bar.
    chunks = _chunks_for("xylophone banana kazoo")
    best, _score = video.select_best_video(chunks, age=8)

    # If a video cleared the bar, this would be a SOT-06 failure. The strict
    # VIDEO_BAR guarantees a text-only answer instead.
    assert best is None


def test_suggested_videos_count_and_shape(seeded_catalog):
    """Suggested list contains 2-4 ranked items with id/title/reason."""
    chunks = _chunks_for("why is the sky blue")
    best, _ = video.select_best_video(chunks, age=8)
    assert best is not None

    suggestions = video.build_suggested_videos(chunks, exclude_id=best["content_item_id"], age=8)
    assert 2 <= len(suggestions) <= 4
    for s in suggestions:
        assert s["id"]
        assert s["title"]
        assert s["reason"]


def test_suggested_excludes_best(seeded_catalog):
    """The currently-playing video must not also appear as a suggestion."""
    chunks = _chunks_for("why is the sky blue")
    best, _ = video.select_best_video(chunks, age=8)
    assert best is not None

    suggestions = video.build_suggested_videos(chunks, exclude_id=best["content_item_id"], age=8)
    ids = {s["id"] for s in suggestions}
    assert best["content_item_id"] not in ids


def test_build_video_response_shape(seeded_catalog):
    """build_video_response returns the WORKFLOW §10 video payload."""
    chunks = _chunks_for("why is the sky blue")
    out = video.build_video_response(chunks, age=8)

    assert out["video_url"] and out["video_url"].startswith("https://")
    assert out["video"]["id"] == "vid-sky-blue"
    assert out["video"]["license"]  # CC BY-SA etc.
    assert out["video"]["attribution"]
    assert 2 <= len(out["suggested_videos"]) <= 4
    assert out["tutorial"] is None  # video, not a tutorial


def test_api_chat_returns_video(client):
    """POST /api/chat 'why is the sky blue?' → non-null video_url + suggestions.

    This is the Phase-3 definition-of-done assertion at the API level.
    """
    resp = client.post("/api/chat", json={"text": "Why is the sky blue?", "age": 8})
    assert resp.status_code == 200
    data = resp.json()

    assert data["assistant_name"] == "Kiddo Assist"
    assert data["safety"]["verdict"] == "pass"
    assert data["video_url"] and data["video_url"].startswith("https://")
    assert data["video"] is not None
    assert data["video"]["id"] == "vid-sky-blue"
    assert data["video"]["license"]
    assert data["video"]["attribution"]
    assert 2 <= len(data["suggested_videos"]) <= 4
    # Suggested videos are the *next* best — never the playing one.
    assert all(s["id"] != "vid-sky-blue" for s in data["suggested_videos"])


def test_api_get_video_metadata(client):
    """GET /api/videos/{id} returns stream-by-reference metadata."""
    resp = client.get("/api/videos/vid-sky-blue")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "vid-sky-blue"
    assert data["title"]
    assert data["attribution"]
    assert data["license"]
    assert data["duration_s"] == 182


def test_api_get_video_not_approved_404(client):
    """A non-approved or unknown video id → 404."""
    # Unknown id
    resp = client.get("/api/videos/does-not-exist")
    assert resp.status_code == 404

    # Rejected item → 404 (only approved content is playable)
    conn = kb.get_sqlite()
    try:
        conn.execute("UPDATE content_items SET status='rejected' WHERE id='vid-solar-system'")
        conn.commit()
    finally:
        conn.close()
    resp2 = client.get("/api/videos/vid-solar-system")
    assert resp2.status_code == 404


def test_reranker_normalizes_logits_to_unit_interval():
    """BgeReranker._sigmoid maps raw cross-encoder logits into [0, 1].

    Empirical regression guard: FlagReranker.compute_score returns raw logits
    (~[-12, +12]), and VIDEO_BAR is calibrated for a [0,1] relevance.  If the
    normalization drifts, the strict bar silently breaks on the real backend.
    """
    from embeddings import BgeReranker

    strong = BgeReranker._sigmoid([8.7])[0]    # sky-blue style clear match
    negative = BgeReranker._sigmoid([-2.1])[0]  # weak/off match
    zero = BgeReranker._sigmoid([0.0])[0]

    assert zero == 0.5  # sigmoid(0)
    assert strong > 0.9
    assert 0.0 < negative < 0.5
    # Monotonic — ordering is unchanged (what RAG relies on).
    assert BgeReranker._sigmoid([-3.0, 0.0, 9.0]) == sorted(
        BgeReranker._sigmoid([-3.0, 0.0, 9.0])
    )


def test_video_score_uses_multiplying_factors():
    """Composite scoring is multiplicative — a zero factor zeroes the score."""
    good = {
        "content_item_id": "v1",
        "item_type": "video",
        "title": "Good",
        "age_range": "6-10",
        "duration_s": 120,
        "transcript": "full transcript",
        "url": "https://example.com/v.webm",
        "attribution": "Credit",
        "score": 0.9,
    }
    long = dict(good, content_item_id="v2", duration_s=3600)
    missing_meta = dict(good, content_item_id="v3", transcript="", attribution="")

    s_good = video.score_video(good, age=8)
    s_long = video.score_video(long, age=8)
    s_missing = video.score_video(missing_meta, age=8)

    assert s_good > s_long
    assert s_good > s_missing
    assert s_long == 0.0  # duration beyond 900s zeroes the composite