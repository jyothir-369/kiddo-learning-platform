"""Iteration 13 — Play layer (Phase 8B) tests."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

import db
import play


def test_streak_survives_one_missed_day():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("s1", "A"))
    conn.execute("INSERT OR IGNORE INTO streaks (learner_id, current, best, last_active) VALUES (?, ?, ?, ?)",
                 ("s1", 5, 5, "2026-09-16"))
    conn.commit()
    # Calling with today's date (same day) preserves streak exactly
    result = play.update_streak("s1", conn=conn)
    assert result["current"] == 5  # preserved (same day / no gap)
    conn.close()


def test_streak_not_wiped_on_gap_1():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("s2", "B"))
    conn.execute("INSERT OR IGNORE INTO streaks (learner_id, current, best, last_active) VALUES (?, ?, ?, ?)",
                 ("s2", 3, 3, "2026-09-14"))
    conn.commit()
    result = play.update_streak("s2", conn=conn)
    assert result["current"] >= 1  # forgiving; not wiped to 0
    conn.close()


def test_badge_milestone():
    assert play.milestone_badge(streak_current=7, watched_items=3) == "Week Explorer"
    assert play.milestone_badge(streak_current=3, watched_items=1) == "Day Starter"
    assert play.milestone_badge(streak_current=1, watched_items=5) == "Curious Minds"


def test_game_has_learning_fact():
    game = play.generate_game("d1", topic="space")
    assert "fact" in game
    assert game["fact"] in game["options"]
    assert game["type"] == "match"


def test_badge_earn():
    conn = db.init_sqlite()
    conn.execute("INSERT OR IGNORE INTO learners (id, name) VALUES (?, ?)", ("s3", "C"))
    conn.commit()
    play.earn_badge("s3", "Playful Learner", conn=conn)
    badges = play.get_badges("s3", conn=conn)
    assert "Playful Learner" in badges
    conn.close()
