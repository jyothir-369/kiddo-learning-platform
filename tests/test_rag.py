"""tests/test_rag.py — Iteration 3 (Phase 2): RAG retrieval.

Covers guide §6.6 filter-before-retrieve + hybrid retrieval:
  - A seeded query grounds in the approved sky-blue source/transcript.
  - The approved-only gate is always applied.
  - lang, age_range and duration_cap pre-filters exclude non-matching content.
  - Retrieval is empty (soft) when the catalog is unseeded.
The sim backend (KIDDO_SEED_BACKEND=sim in conftest) keeps this deterministic
and download-free — rag._sim_mode() inherits it.
"""
import pytest

import db as kb
import rag
from seed import seed


@pytest.fixture
def seeded_catalog():
    """Fresh sim-seeded SQLite + LanceDB catalog in the temp store."""
    seed(embed=True, rebuild_vectors=True)


def test_unseeded_search_is_empty():
    """No content seeded (autouse fixture clears SQLite; vectors never built)
    -> search returns [] rather than raising."""
    assert rag.search("why is the sky blue") == []


def test_search_grounds_sky_blue_query(seeded_catalog):
    """Top hit for 'why is the sky blue' is the seeded sky-blue content."""
    chunks = rag.search("why is the sky blue", top_k=5)
    assert chunks, "expected retrieval hits for a seeded query"

    top = chunks[0]
    assert top["content_item_id"] in {"src-sky-blue", "vid-sky-blue"}
    # Whole (title + transcript) is retrieved — the grounding source.
    assert "sky" in top["text_chunk"].lower()
    assert "blue" in top["text_chunk"].lower()

    # Enriched metadata is present (SQLite join). SOT-03 attribution travels
    # with the answer via build_context / the API `sources` field.
    assert top["attribution"]
    assert top["license"]
    assert top["status"] == "approved"


def test_approx_vectors_agree_with_lexical(seeded_catalog):
    """Both hybrid legs (vector + FTS) surface the obvious water-cycle match."""
    from rag import _build_where, _fts_search, _vector_search

    table = kb.get_vectors_table()
    where = _build_where()
    query_vec = rag.embed("the water cycle evaporation rain")
    vec_rows = _vector_search(table, query_vec, where, rag.RETRIEVE_LIMIT)
    fts_rows = _fts_search(table, "the water cycle evaporation rain", where, rag.RETRIEVE_LIMIT)
    assert vec_rows, "vector retrieval should find water-cycle content"
    ids = {r["content_item_id"] for r in fts_rows}
    assert "src-water-cycle" in ids or "vid-water-cycle" in ids


def test_approved_gate_always_on(seeded_catalog):
    """Every returned chunk is an approved content item (filter-before-retrieve)."""
    chunks = rag.search("dinosaurs", top_k=10)
    assert chunks
    assert all(c["status"] == "approved" for c in chunks)


def test_lang_filter_excludes_non_matching(seeded_catalog):
    """No Hindi content is seeded -> an explicit Hindi search returns []."""
    assert rag.search("the water cycle", lang="hi") == []


def test_age_range_filter_excludes_content(seeded_catalog):
    """Sky-blue content is seeded for 6-10; a 4-7 band must not retrieve it."""
    chunks = rag.search("why is the sky blue", age_range="4-7", top_k=10)
    ids = {c["content_item_id"] for c in chunks}
    assert "src-sky-blue" not in ids
    assert "vid-sky-blue" not in ids


def test_duration_cap_excludes_long_videos(seeded_catalog):
    """A zero-second duration cap must exclude every seeded video (dur > 0)."""
    chunks = rag.search("planets of our solar system", max_duration_s=0, top_k=20)
    for c in chunks:
        assert c["duration_s"] <= 0, f"{c['content_item_id']} should be capped out"
    ids = {c["content_item_id"] for c in chunks}
    assert "vid-solar-system" not in ids


def test_build_context_includes_attribution(seeded_catalog):
    """build_context carries attribution so the LLM can cite its source."""
    chunks = rag.search("why is the sky blue", top_k=1)
    ctx = rag.build_context(chunks)
    assert "sky" in ctx.lower()
    assert chunks[0]["attribution"].split(",")[0] in ctx