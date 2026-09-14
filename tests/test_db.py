"""tests/test_db.py — Iteration 1: KB data layer + dev seed catalog.

Covers (per SDLC Iteration 1 definition of done):
  - SQLite schema: all tables per Implementation Guide §7 exist.
  - Type domain: content_items.type ∈ {video, tutorial, source, game}.
  - Status domain: content_items.status ∈ {review, approved, rejected}.
  - Dev seed: idempotent (same counts on re-run) and every row approved.
  - Searchability: LanceDB search over a seeded transcript returns hits.
"""
import json
import sqlite3

import pytest

import db
import seed


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "learners",
    "parents",
    "content_items",
    "progress",
    "skills",
    "content_skills",
    "config",
    "safety_events",
    "streaks",
    "badges",
}


def test_sqlite_schema_creates_all_tables():
    conn = db.init_sqlite()
    try:
        got = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert EXPECTED_TABLES <= got, f"missing tables: {EXPECTED_TABLES - got}"


def test_sqlite_schema_is_idempotent():
    db.init_sqlite()
    db.init_sqlite()  # must not raise
    conn = db.get_sqlite()
    try:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] > 0
    finally:
        conn.close()


def test_content_items_columns_present():
    conn = db.init_sqlite()
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(content_items)")}
    finally:
        conn.close()
    for required in (
        "id", "type", "title", "url", "transcript", "language", "age_range",
        "difficulty", "duration_s", "skills", "safety_tags", "license",
        "source", "attribution", "status", "tutorial_steps",
    ):
        assert required in cols, f"content_items missing column {required}"


def test_tutorial_steps_is_json_column_roundtrip():
    conn = db.init_sqlite()
    try:
        db.upsert_content_item(
            conn,
            id="tut-rt",
            type="tutorial",
            title="Roundtrip Tutorial",
            status="approved",
            tutorial_steps=[
                {"step": 1, "title": "One", "content": "First step", "check": "What's first?"},
                {"step": 2, "title": "Two", "content": "Second step", "check": "What's next?"},
            ],
        )
        conn.commit()
        row = conn.execute(
            "SELECT tutorial_steps FROM content_items WHERE id='tut-rt'"
        ).fetchone()
    finally:
        conn.close()
    loaded = json.loads(row["tutorial_steps"])
    assert loaded[0]["step"] == 1 and loaded[1]["title"] == "Two"
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# Type / status domains (CHECK constraints)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_type", ["podcast", "book", "", "VIDEO", None])
def test_invalid_type_rejected(bad_type):
    conn = db.init_sqlite()
    try:
        try:
            db.upsert_content_item(conn, id="bad", type=bad_type, title="x", status="approved")
            conn.commit()
            conn.execute("SELECT 1")  # flush deferred IntegrityError, if any
        except sqlite3.IntegrityError:
            return  # constraint enforced
        # No error raised at all → the CHECK is NOT enforced. Fail loudly.
        pytest.fail(f"type={bad_type!r} was accepted; CHECK constraint not enforced")
    finally:
        conn.close()


@pytest.mark.parametrize("good_type", ["video", "tutorial", "source", "game"])
def test_valid_types_accepted(good_type):
    conn = db.init_sqlite()
    try:
        db.upsert_content_item(conn, id=f"ok-{good_type}", type=good_type, title="x", status="approved")
        conn.commit()  # must not raise
        row = conn.execute(
            "SELECT type FROM content_items WHERE id=?", (f"ok-{good_type}",)
        ).fetchone()
    finally:
        conn.close()
    assert row["type"] == good_type


@pytest.mark.parametrize("bad_status", ["live", "PUBLISHED", None])
def test_invalid_status_rejected(bad_status):
    conn = db.init_sqlite()
    try:
        try:
            db.upsert_content_item(
                conn, id="bad-status", type="video", title="x", status=bad_status
            )
            conn.commit()
            conn.execute("SELECT 1")  # flush deferred IntegrityError, if any
        except sqlite3.IntegrityError:
            return  # constraint enforced
        pytest.fail(f"status={bad_status!r} was accepted; CHECK constraint not enforced")
    finally:
        conn.close()


@pytest.mark.parametrize("good_status", ["review", "approved", "rejected"])
def test_valid_statuses_accepted(good_status):
    conn = db.init_sqlite()
    try:
        db.upsert_content_item(conn, id=f"st-{good_status}", type="video", title="x", status=good_status)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dev seed: idempotency + approval + composition
# ---------------------------------------------------------------------------


def test_seed_runs_and_is_fully_approved():
    summary = seed.seed(embed=True)
    assert summary["items_upserted"] == 13
    assert sum(summary["counts_by_type"].values()) == 13

    conn = db.get_sqlite()
    try:
        approved = conn.execute(
            "SELECT COUNT(*) FROM content_items WHERE status='approved'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert approved == 13  # dev shortcut: every seeded row approved


def test_seed_is_idempotent_same_counts():
    first = seed.seed(embed=True)
    second = seed.seed(embed=True)
    assert first["counts_by_type"] == second["counts_by_type"]
    assert first["items_upserted"] == second["items_upserted"]
    assert first["counts_by_type"] == {
        "video": 6, "tutorial": 2, "source": 3, "game": 2,
    }


def test_seed_vectors_rebuilt_consistently():
    seed.seed(embed=True)
    table = db.get_vectors_table()
    assert table is not None
    assert table.count_rows() == 13
    # Re-seed must not accumulate duplicate vector rows.
    seed.seed(embed=True)
    # Re-open table handle (underlying table is drop+created each run).
    table2 = db.get_vectors_table()
    assert table2 is not None
    assert table2.count_rows() == 13


def test_seed_catalog_composition():
    """Tutorials have ordered steps; videos have transcript/license/attribution/duration."""
    seed.seed(embed=False)
    conn = db.get_sqlite()
    try:
        rows = conn.execute("SELECT * FROM content_items WHERE status='approved'")
        items = [dict(r) for r in rows]
    finally:
        conn.close()

    videos = [i for i in items if i["type"] == "video"]
    tutorials = [i for i in items if i["type"] == "tutorial"]
    for v in videos:
        assert v["transcript"], f"{v['id']} missing transcript"
        assert v["license"], f"{v['id']} missing license"
        assert v["attribution"], f"{v['id']} missing attribution"
        assert v["duration_s"] and v["duration_s"] > 0, f"{v['id']} missing duration_s"
    for t in tutorials:
        steps = json.loads(t["tutorial_steps"])
        assert len(steps) >= 2, f"{t['id']} needs real ordered steps"
        nums = [s["step"] for s in steps]
        assert nums == sorted(nums) == list(range(1, len(steps) + 1))


# ---------------------------------------------------------------------------
# Searchability (LanceDB over seeded transcripts)
# ---------------------------------------------------------------------------


def test_lancedb_search_over_seeded_transcript_returns_hits():
    seed.seed(embed=True)
    table = db.get_vectors_table()
    assert table is not None

    # Query embedded with the SAME sim backend used at seed time.
    query_text = "Why is the sky blue - the blue light scattering in the air"
    query_vec = seed._SimEmbedder().encode_many([query_text])[0]

    results = db.search_content_vectors(table, query_vec, limit=5)
    assert results, "no hits returned over seeded transcript"

    top = results[0]
    assert top["content_item_id"] in {"vid-sky-blue", "src-sky-blue"}
    # The embedded chunk must carry the seeded transcript surface.
    assert "blue" in top["text_chunk"].lower()


def test_lancedb_metadata_filters_apply():
    seed.seed(embed=True)
    table = db.get_vectors_table()
    query_vec = seed._SimEmbedder().encode_many(["counting numbers one two three"])[0]
    # Filtering to a space video must exclude the counting game.
    results = db.search_content_vectors(
        table, query_vec, limit=5, item_type="video", lang="en"
    )
    assert results
    assert all(r["item_type"] == "video" for r in results)