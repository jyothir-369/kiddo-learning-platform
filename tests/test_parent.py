"""Iteration 14 — Parent dashboard (Phase 9; EXT-01) tests."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

import db
import parent


def test_parent_config_persist():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("par1", "Parent"))
    conn.execute("INSERT OR IGNORE INTO config (learner_id, restricted_topics, screen_time_min, language) VALUES (?, ?, ?, ?)",
                 ("par1", "[]", 60, "en"))
    conn.commit()
    ok = parent.write_config("par1", restricted_topics=["violence", "harm"], screen_time_min=45, language="hi", conn=conn)
    assert ok
    cfg = parent.read_config("par1", conn=conn)
    assert "violence" in cfg["restricted_topics"]
    assert cfg["screen_time_min"] == 45
    conn.close()


def test_restricted_topic_refused():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("par2", "Child"))
    conn.execute("INSERT OR IGNORE INTO config (learner_id, restricted_topics, screen_time_min, language) VALUES (?, ?, ?, ?)",
                 ("par2", '["harm"]', 60, "en"))
    conn.commit()
    assert parent.is_topic_restricted("par2", "harm is bad", conn=conn)
    assert not parent.is_topic_restricted("par2", "animals are fun", conn=conn)
    conn.close()


def test_reports_include_progress_and_safety():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("par3", "Child"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, status) VALUES (?, ?, ?, ?)",
                 ("t1", "video", "Test", "approved"))
    conn.execute("INSERT OR IGNORE INTO progress (id, learner_id, item_id, watched_seconds, quiz_score, ts) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                 ("par3:t1", "par3", "t1", 120, 0.8))
    conn.execute("INSERT OR IGNORE INTO safety_events (id, learner_id, event_type, severity, ts, handler) VALUES (?, ?, ?, ?, datetime('now'), ?)",
                 ("e1", "par3", "pii", "soft", "parent"))
    conn.commit()
    reports = parent.get_reports("par3", conn=conn)
    assert any(p["item_id"] == "t1" for p in reports["progress_items"])
    assert any(s["event_type"] == "pii" for s in reports["safety_flags"])
    conn.close()
