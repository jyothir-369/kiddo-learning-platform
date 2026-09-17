"""Iteration 12 — Progress, mastery, tutorial step-through (Phase 8A) tests."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

import db
import progress


def test_watched_not_mastered():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("p1", "C"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, status) VALUES (?, ?, ?, ?)",
                 ("tut1", "tutorial", "Stars", "approved"))
    conn.commit()
    progress.record_watch("p1", "tut1", watched_seconds=120, conn=conn)
    assert not progress.is_mastered("p1", "tut1", conn=conn)
    conn.close()


def test_failed_checkin_not_mastery():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("p2", "D"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, status) VALUES (?, ?, ?, ?)",
                 ("tut2", "tutorial", "Planets", "approved"))
    conn.commit()
    progress.record_quiz_score("p2", "tut2", score=0.3, conn=conn)
    assert not progress.is_mastered("p2", "tut2", conn=conn)
    conn.close()


def test_passing_checkin_grants_mastery():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("p3", "E"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, status) VALUES (?, ?, ?, ?)",
                 ("tut3", "tutorial", "Moon", "approved"))
    conn.commit()
    progress.record_quiz_score("p3", "tut3", score=0.9, conn=conn)
    assert progress.is_mastered("p3", "tut3", conn=conn)
    conn.close()


def test_tutorial_step_progression():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name, profile_json) VALUES (?, ?, ?)",
                 ("p4", "F", "{}"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, tutorial_steps, status) VALUES (?, ?, ?, ?, ?)",
                 ("tut4", "tutorial", "Animals", '[{"step":1},{"step":2}]', "approved"))
    conn.commit()
    step1 = progress.advance_tutorial_step("p4", "tut4", conn=conn)
    assert step1 == 2
    conn.close()


def test_frontier_suggested_next():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("p5", "G"))
    conn.execute("INSERT OR IGNORE INTO skills (id, name, parents) VALUES (?, ?, ?)",
                 ("sk1", "Light", "[]"))
    conn.execute("INSERT OR IGNORE INTO content_items (id, type, title, status) VALUES (?, ?, ?, ?)",
                 ("tut5", "tutorial", "Light", "approved"))
    conn.execute("INSERT OR IGNORE INTO content_skills (content_id, skill_id) VALUES (?, ?)",
                 ("tut5", "sk1"))
    conn.commit()
    progress.record_watch("p5", "tut5", watched_seconds=30, conn=conn)
    suggested = progress.suggested_next("p5", conn=conn)
    assert suggested is not None
    assert "Light" in suggested or "practice" in suggested
    conn.close()
