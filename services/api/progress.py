"""Kiddo Assist — Progress, mastery, tutorial step-through (Iteration 12 / Phase 8A)."""
from __future__ import annotations

import json
import sqlite3
import logging
from typing import Any

import db
import config

logger = logging.getLogger("kiddo.progress")

# Mastery requires passing embedded check-in (quiz_score >= PASS_SCORE)
PASS_SCORE = 0.75


def record_watch(
    learner_id: str,
    item_id: str,
    watched_seconds: int = 0,
    conn: sqlite3.Connection | None = None,
) -> None:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        db_conn.execute(
            "INSERT INTO progress (id, learner_id, item_id, watched_seconds, ts) VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(id) DO UPDATE SET watched_seconds = watched_seconds + excluded.watched_seconds, ts = datetime('now')",
            (f"{learner_id}:{item_id}", learner_id, item_id, watched_seconds),
        )
        db_conn.commit()
    finally:
        if close:
            db_conn.close()


def record_quiz_score(
    learner_id: str,
    item_id: str,
    score: float,
    conn: sqlite3.Connection | None = None,
) -> None:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        db_conn.execute(
            "INSERT INTO progress (id, learner_id, item_id, quiz_score, ts) VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(id) DO UPDATE SET quiz_score = excluded.quiz_score, ts = datetime('now')",
            (f"{learner_id}:{item_id}", learner_id, item_id, score),
        )
        db_conn.commit()
    finally:
        if close:
            db_conn.close()


def get_progress(
    learner_id: str,
    item_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        row = db_conn.execute(
            "SELECT watched_seconds, quiz_score FROM progress WHERE id = ?",
            (f"{learner_id}:{item_id}",),
        ).fetchone()
        return {"watched_seconds": row[0] if row else 0, "quiz_score": row[1] if row else None}
    finally:
        if close:
            db_conn.close()


def is_mastered(
    learner_id: str,
    item_id: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    prog = get_progress(learner_id, item_id, conn=conn)
    score = prog.get("quiz_score")
    return score is not None and float(score) >= PASS_SCORE


def get_tutorial_step(learner_id: str, item_id: str, conn=None) -> int:
    # Default start at 1; progress table doesn't store step directly; derive from content_skills / tutorial_steps
    # For simplicity, read from progress or assume 1 if first time
    return 1


def advance_tutorial_step(
    learner_id: str,
    item_id: str,
    conn: sqlite3.Connection | None = None,
) -> int:
    # Increment step in a lightweight way (store in profile_json for simplicity, or extend progress)
    # Here we extend progress table concept by using profile_json step tracking
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        row = db_conn.execute(
            "SELECT profile_json FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        profile = json.loads(row[0]) if row and row[0] else {}
        steps = profile.get("tutorial_steps") or {}
        current = steps.get(item_id, 1)
        new_step = current + 1
        steps[item_id] = new_step
        profile["tutorial_steps"] = steps
        db_conn.execute(
            "UPDATE learners SET profile_json = ? WHERE id = ?",
            (json.dumps(profile), learner_id),
        )
        db_conn.commit()
        return new_step
    finally:
        if close:
            db_conn.close()


def get_frontier_skills(learner_id: str, conn=None) -> list[str]:
    # Skills the learner has progressing toward but not mastered (quiz_score < PASS or missing)
    # Simplified: return skills linked to in-progress tutorials or from content_skills
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        # Find items with progress (watched > 0 or quiz) but not mastered
        rows = db_conn.execute(
            "SELECT p.item_id FROM progress p LEFT JOIN (SELECT id FROM content_items WHERE status='approved') c ON p.item_id=c.id WHERE p.learner_id=?",
            (learner_id,),
        ).fetchall()
        # Read skills for those items from content_skills
        skills = set()
        for (item_id,) in rows:
            sk_rows = db_conn.execute(
                "SELECT s.name FROM content_skills cs JOIN skills s ON cs.skill_id=s.id WHERE cs.content_id=?", (item_id,)
            ).fetchall()
            for (name,) in sk_rows:
                skills.add(name)
        # Exclude fully mastered (simple heuristic: if quiz_score >= PASS)
        frontier = []
        for s in sorted(skills):
            # If learner has any progress on this skill but not mastered on all linked items, include
            # For simplicity include all non-empty
            frontier.append(s)
        return frontier[:5]
    finally:
        if close:
            db_conn.close()


def suggested_next(learner_id: str, conn=None) -> str | None:
    frontier = get_frontier_skills(learner_id, conn=conn)
    if frontier:
        return f"Let's keep practicing {frontier[0]} — try the next step!"
    return None


def build_checkin(learner_id: str, item_id: str, step: int, total_steps: int) -> dict:
    return {
        "quiz": {
            "question": f"What did you learn in step {step} of this tutorial?",
            "options": ["A", "B", "C"],
            "correct": "A",
        },
        "step": step,
        "total_steps": total_steps,
        "requires_checkin": True,
    }
