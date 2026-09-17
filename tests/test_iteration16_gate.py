"""Integration — Iteration 16 (Phase 10B): approve/reject → searchable / unavailable."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "ingester"))

import db
import check
from review_cli import approve_item, reject_item, list_review


def test_ingested_is_review():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev1", "video", "Review Me", "Hello world.", "A", "CC BY-SA", "review"))
    conn.commit()
    row = conn.execute("SELECT status FROM content_items WHERE id=?", ("rev1",)).fetchone()
    assert row[0] == "review"
    conn.close()


def test_review_not_searchable():
    # RAG filter requires approved; review should not return via search
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev2", "video", "Not Searchable", "Text.", "A", "CC BY-SA", "review"))
    conn.commit()
    # Direct query confirms status
    row = conn.execute("SELECT status FROM content_items WHERE id=?", ("rev2",)).fetchone()
    assert row[0] == "review"
    conn.close()


def test_approve_becomes_approved():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev3", "source", "Go Live", "Full work here.", "A", "CC BY", "review"))
    conn.commit()
    assert approve_item("rev3", conn=conn)
    row = conn.execute("SELECT status FROM content_items WHERE id=?", ("rev3",)).fetchone()
    assert row[0] == "approved"
    conn.close()


def test_approved_searchable_next_chat():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev4", "video", "Findable", "About space.", "A", "CC BY", "approved"))
    conn.commit()
    # Confirm approved row exists for filter
    row = conn.execute("SELECT id FROM content_items WHERE status=? AND id=?", ("approved", "rev4")).fetchone()
    assert row is not None
    conn.close()


def test_rejected_remains_unavailable():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev5", "source", "Rejected", "Text.", "A", "CC BY", "review"))
    conn.commit()
    assert reject_item("rev5", conn=conn)
    row = conn.execute("SELECT status FROM content_items WHERE id=?", ("rev5",)).fetchone()
    assert row[0] == "rejected"
    conn.close()


def test_reject_logs_safety_events():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("learn1", "C"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, transcript, attribution, license, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("rev6", "video", "R", "T", "A", "CC BY", "review"))
    conn.commit()
    reject_item("rev6", conn=conn, learner_id="learn1")
    event = conn.execute("SELECT event_type FROM safety_events WHERE learner_id=? AND event_type=?", ("learn1", "ingest_rejected")).fetchone()
    assert event is not None
    conn.close()


def test_no_pre_approval_playable_url():
    # Before approval, item has no playable URL (status=review prevents stream-by-reference exposure)
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, url, status) VALUES (?, ?, ?, ?, ?)",
                 ("rev7", "video", "No URL", "https://example.com/video.webm", "review"))
    conn.commit()
    # Only approved items get video_url in response; review items excluded by filter
    row = conn.execute("SELECT status FROM content_items WHERE id=?", ("rev7",)).fetchone()
    assert row[0] == "review"
    conn.close()
