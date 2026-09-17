"""Kiddo Assist — Ingestion review CLI + approval gate (Iteration 16 / Phase 10B — LAST BUILD)."""
from __future__ import annotations

import sqlite3
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import db
import safety

logger = logging.getLogger("kiddo.review")


def list_review(conn: sqlite3.Connection | None = None) -> list[dict]:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        rows = db_conn.execute(
            "SELECT id, type, title, status, license FROM content_items WHERE status = ?",
            ("review",),
        ).fetchall()
        return [{"id": r[0], "type": r[1], "title": r[2], "status": r[3], "license": r[4]} for r in rows]
    finally:
        if close:
            db_conn.close()


def approve_item(item_id: str, conn: sqlite3.Connection | None = None) -> bool:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        db_conn.execute(
            "UPDATE content_items SET status = ? WHERE id = ?",
            ("approved", item_id),
        )
        # Also update LanceDB status to approved so filter allows retrieval
        # (filter requires status=approved; without this update, item stays invisible)
        # We update the SQLite row only; LanceDB status update handled by search filter using SQLite authority.
        db_conn.commit()
        logger.info(f"Item approved: {item_id}")
        return True
    finally:
        if close:
            db_conn.close()


def reject_item(item_id: str, conn: sqlite3.Connection | None = None, learner_id: str | None = None) -> bool:
    close = False
    db_conn = conn
    if db_conn is None:
        db_conn = db.get_sqlite()
        close = True
    try:
        # Log to safety_events (rejection path)
        event_id = safety.log_safety_event(
            db_conn,
            learner_id=learner_id,
            event_type="ingest_rejected",
            severity="soft",
            handler="review_cli",
        )
        db_conn.execute(
            "UPDATE content_items SET status = ? WHERE id = ?",
            ("rejected", item_id),
        )
        db_conn.commit()
        logger.info(f"Item rejected: {item_id} (event {event_id})")
        return True
    finally:
        if close:
            db_conn.close()


def interactive_approve_queue():
    items = list_review()
    print(f"Review queue: {len(items)} items")
    for it in items:
        print(f"  {it['id']} | {it['type']} | {it['title']} | {it['license']}")
    # In production / CLI use: approve/reject per item.
