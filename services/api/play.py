"""Kiddo Assist — Play layer: streaks, badges, mini-games (Iteration 13 / Phase 8B)."""
from __future__ import annotations

import sqlite3
import json
import logging
from typing import Any

import db

logger = logging.getLogger("kiddo.play")

# Forgiving: missed day does NOT wipe; only reset after 2+ days
MISSING_DAYS_BEFORE_WIPE = 2


def get_streak(learner_id: str, conn=None) -> dict:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        row = db_conn.execute(
            "SELECT current, best, last_active FROM streaks WHERE learner_id = ?", (learner_id,)
        ).fetchone()
        if row:
            return {"current": row[0] or 0, "best": row[1] or 0, "last_active": row[2]}
        return {"current": 0, "best": 0, "last_active": None}
    finally:
        if close:
            db_conn.close()


def update_streak(learner_id: str, conn=None) -> dict:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        # Ensure learner exists (fix FK failure on fresh DB)
        db_conn.execute("INSERT OR IGNORE INTO learners (id, name, age, language) VALUES (?, ?, ?, ?)", (learner_id, "Demo", 8, "en"))
        db_conn.commit()
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        streak = get_streak(learner_id, conn=db_conn)
        current = streak.get("current", 0) or 0
        best = streak.get("best", 0) or 0
        last = streak.get("last_active")
        if last and last < today:
            # Check missed days
            from datetime import datetime as dt
            try:
                last_dt = dt.strptime(last, "%Y-%m-%d")
                today_dt = dt.strptime(today, "%Y-%m-%d")
                gap = (today_dt - last_dt).days
                if gap == 0:
                    # Same day — keep current
                    pass
                elif gap == 1:
                    current += 1
                elif gap >= MISSING_DAYS_BEFORE_WIPE:
                    current = 1  # reset but start today, forgiving
                else:
                    current = 1
            except Exception:
                current = 1
        else:
            # No gap / same-day — preserve current streak exactly
            pass  # current stays as-is
        best = max(best, current)
        db_conn.execute(
            "INSERT INTO streaks (learner_id, current, best, last_active) VALUES (?, ?, ?, ?) ON CONFLICT(learner_id) DO UPDATE SET current=excluded.current, best=excluded.best, last_active=excluded.last_active",
            (learner_id, current, best, today),
        )
        db_conn.commit()
        return {"current": current, "best": best, "last_active": today}
    finally:
        if close:
            db_conn.close()


def earn_badge(learner_id: str, badge: str, conn=None) -> bool:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        db_conn.execute(
            "INSERT OR IGNORE INTO badges (learner_id, badge, earned_ts) VALUES (?, ?, datetime('now'))",
            (learner_id, badge),
        )
        db_conn.commit()
        return True
    finally:
        if close:
            db_conn.close()


def get_badges(learner_id: str, conn=None) -> list[str]:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        rows = db_conn.execute("SELECT badge FROM badges WHERE learner_id = ?", (learner_id,)).fetchall()
        return [r[0] for r in rows]
    finally:
        if close:
            db_conn.close()


def milestone_badge(streak_current: int, watched_items: int) -> str | None:
    if streak_current >= 7 and watched_items >= 3:
        return "Week Explorer"
    if streak_current >= 3:
        return "Day Starter"
    if watched_items >= 5:
        return "Curious Minds"
    return None


def generate_game(learner_id: str, topic: str = "animals") -> dict:
    # Parameterized match/quiz template where the learning fact is part of gameplay
    facts = {
        "animals": ["birds fly with wings", "fish live in water", "cats have whiskers"],
        "space": ["sun is a star", "moon orbits earth", "planets orbit sun"],
        "colors": ["red + blue = purple", "yellow + blue = green"],
    }
    selected = facts.get(topic, facts["animals"])
    correct = selected[0]
    return {
        "type": "match",
        "title": f"Let’s play with {topic}!",
        "fact": correct,
        "question": f"What is true about {topic}?",
        "options": selected,
        "correct_index": 0,
        "reward_badge": "Playful Learner" if len(get_badges(learner_id)) < 2 else None,
    }
