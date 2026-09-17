"""Kiddo Assist — Parent dashboard (Iteration 14 / Phase 9; extension EXT-01)."""
from __future__ import annotations

import sqlite3
import json
import logging
from typing import Any

import db

logger = logging.getLogger("kiddo.parent")


def read_config(learner_id: str, conn=None) -> dict:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        row = db_conn.execute(
            "SELECT restricted_topics, screen_time_min, language FROM config WHERE learner_id = ?",
            (learner_id,),
        ).fetchone()
        if row:
            return {
                "restricted_topics": json.loads(row[0] or "[]"),
                "screen_time_min": row[1] if row[1] is not None else 60,
                "language": row[2] if row[2] else "en",
            }
        return {"restricted_topics": [], "screen_time_min": 60, "language": "en"}
    finally:
        if close:
            db_conn.close()


def write_config(
    learner_id: str,
    *,
    restricted_topics: list[str] | None = None,
    screen_time_min: int | None = None,
    language: str | None = None,
    conn=None,
) -> bool:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        # Read current
        row = db_conn.execute(
            "SELECT restricted_topics, screen_time_min, language FROM config WHERE learner_id = ?",
            (learner_id,),
        ).fetchone()
        current = {
            "restricted_topics": json.loads(row[0] or "[]") if row else [],
            "screen_time_min": row[1] if row and row[1] is not None else 60,
            "language": row[2] if row and row[2] else "en",
        }
        if restricted_topics is not None:
            current["restricted_topics"] = restricted_topics
        if screen_time_min is not None:
            current["screen_time_min"] = screen_time_min
        if language is not None:
            current["language"] = language
        db_conn.execute(
            "INSERT INTO config (learner_id, restricted_topics, screen_time_min, language) VALUES (?, ?, ?, ?) ON CONFLICT(learner_id) DO UPDATE SET restricted_topics=excluded.restricted_topics, screen_time_min=excluded.screen_time_min, language=excluded.language",
            (learner_id, json.dumps(current["restricted_topics"]), current["screen_time_min"], current["language"]),
        )
        db_conn.commit()
        return True
    finally:
        if close:
            db_conn.close()


def is_topic_restricted(learner_id: str, topic: str, conn=None) -> bool:
    cfg = read_config(learner_id, conn=conn)
    # Partial-match: if any restricted term appears in the topic text
    topic_lower = topic.lower()
    for t in cfg.get("restricted_topics", []):
        if t.lower() in topic_lower:
            return True
    return False


def get_reports(learner_id: str, conn=None) -> dict:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        # Progress items with watched and quiz
        rows = db_conn.execute(
            "SELECT p.item_id, p.watched_seconds, p.quiz_score, c.title FROM progress p JOIN content_items c ON p.item_id = c.id WHERE p.learner_id = ?",
            (learner_id,),
        ).fetchall()
        progress_items = [{"item_id": r[0], "title": r[3], "watched_seconds": r[1], "quiz_score": r[2]} for r in rows]
        # Safety events
        events = db_conn.execute(
            "SELECT event_type, severity, ts FROM safety_events WHERE learner_id = ? ORDER BY ts DESC LIMIT 10",
            (learner_id,),
        ).fetchall()
        safety_flags = [{"event_type": r[0], "severity": r[1], "ts": r[2]} for r in events]
        # Weekly digest stub
        config_row = db_conn.execute("SELECT restricted_topics FROM config WHERE learner_id = ?", (learner_id,)).fetchone()
        restricted = json.loads(config_row[0]) if config_row else []
        return {
            "learner_id": learner_id,
            "progress_items": progress_items,
            "safety_flags": safety_flags,
            "restricted_topics": restricted,
            "weekly_digest": "Weekly digest available (EXT-01).",
        }
    finally:
        if close:
            db_conn.close()
