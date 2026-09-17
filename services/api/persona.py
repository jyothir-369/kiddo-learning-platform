"""Kiddo Assist — Persona & friendship memory (Iteration 11 / Phase 7).

Friendship memory stored in `learners.profile_json`, capped at ~200 facts,
explicitly excluding PII (no names of family, addresses, phone/email, SSN).
Safe writes/reads, deterministic, never nags.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

import db
import config

logger = logging.getLogger("kiddo.persona")

MAX_FACTS = 200
# PII-like key patterns never stored as memory facts
_PII_KEY_PATTERNS = ("address", "street", "city", "zip", "phone", "email", "ssn",
                     "credit", "card", "password", "secret", "school_name",
                     "teacher_name", "parent_name", "mom", "dad", "sibling")


def _is_pii_key(key: str) -> bool:
    kl = key.lower()
    return any(p in kl for p in _PII_KEY_PATTERNS)


def _safe_fact(key: str, value: Any) -> bool:
    if _is_pii_key(key):
        return False
    if isinstance(value, str) and len(value) > 200:
        # Truncate long strings; still safe
        value = value[:200]
    # Reject values that look like raw PII payloads
    if isinstance(value, str) and ("@" in value or value.replace("-", "").replace(" ", "").isdigit()):
        # Simple email / phone-like heuristics; allow only if clearly not PII
        if "@" in value or (len(value) > 7 and value.replace("-", "").replace(" ", "").isdigit()):
            # Could be a number (favorite number) — allow if short/numeric
            if len(value) <= 4 and value.isdigit():
                pass  # okay as number
            else:
                return False
    return True


def read_memory(learner_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Read friendship memory from learners.profile_json."""
    close = False
    db_conn = conn
    if db_conn is None:
        try:
            db_conn = db.get_sqlite()
            close = True
        except Exception:
            return {}
    try:
        row = db_conn.execute(
            "SELECT profile_json FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        if not row or not row[0]:
            return {}
        profile = json.loads(row[0])
        memory = profile.get("memory") or profile.get("friendship_memory") or {}
        if not isinstance(memory, dict):
            memory = {}
        return memory
    finally:
        if close and db_conn is not None:
            db_conn.close()


def write_memory(
    learner_id: str,
    facts: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Write safe facts into profile_json memory, capped at ~200."""
    safe_facts: dict[str, Any] = {}
    for k, v in facts.items():
        if _is_pii_key(k):
            logger.warning(f"PII key rejected from memory: {k}")
            continue
        if not _safe_fact(k, v):
            logger.warning(f"Unsafe fact rejected: {k}")
            continue
        safe_facts[k] = v
    # Cap
    if len(safe_facts) > MAX_FACTS:
        # Deterministic trim: sort by key, keep first MAX_FACTS
        safe_facts = dict(sorted(safe_facts.items())[:MAX_FACTS])
    close = False
    db_conn = conn
    if db_conn is None:
        try:
            db_conn = db.get_sqlite()
            close = True
        except Exception:
            return False
    try:
        row = db_conn.execute(
            "SELECT profile_json FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        profile = {}
        if row and row[0]:
            try:
                profile = json.loads(row[0])
            except Exception:
                profile = {}
        profile["friendship_memory"] = safe_facts
        # Also keep top-level favorites / name in profile for quick access
        for key in ("name", "favorite_color", "favorite_animal", "favorite_topic"):
            if key in safe_facts:
                profile[key] = safe_facts[key]
        db_conn.execute(
            "UPDATE learners SET profile_json = ? WHERE id = ?",
            (json.dumps(profile), learner_id),
        )
        db_conn.commit()
        return True
    finally:
        if close and db_conn is not None:
            db_conn.close()


def add_fact(learner_id: str, key: str, value: Any, conn=None) -> bool:
    memory = read_memory(learner_id, conn=conn)
    memory[key] = value
    return write_memory(learner_id, memory, conn=conn)


def get_favorite_memory(learner_id: str, conn=None) -> dict[str, Any]:
    memory = read_memory(learner_id, conn=conn)
    favorites = {}
    for k, v in memory.items():
        if "favorite" in k.lower() or k in ("favorite_color", "favorite_animal",
                                            "favorite_topic", "favorite_song"):
            favorites[k] = v
    return favorites


def get_learner_name(learner_id: str, conn=None) -> str | None:
    close = False
    db_conn = conn
    if db_conn is None:
        try:
            db_conn = db.get_sqlite()
            close = True
        except Exception:
            return None
    try:
        row = db_conn.execute(
            "SELECT name, profile_json FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        if row and row[0]:
            return row[0]
        if row and row[1]:
            profile = json.loads(row[1])
            return profile.get("name") or profile.get("learner_name")
        return None
    finally:
        if close and db_conn is not None:
            db_conn.close()


def greet_new_session(learner_id: str, conn=None) -> str:
    """Proactive greeting — never nags; only when session is genuinely new."""
    memory = read_memory(learner_id, conn=conn)
    name = get_learner_name(learner_id, conn=conn)
    favorites = get_favorite_memory(learner_id, conn=conn)
    parts = []
    if name:
        parts.append(f"Hello {name}! I'm {config.ASSISTANT_NAME}.")
    else:
        parts.append(f"Hello! I'm {config.ASSISTANT_NAME}.")
    if favorites:
        # Pick first favorite deterministically
        first = sorted(favorites.items())[0]
        parts.append(f"I remember you like {first[1]} — let's explore together!")
    else:
        parts.append("I'd love to learn what you like — ask me anything!")
    return " ".join(parts)


def build_memory_prompt_fragment(learner_id: str, conn=None) -> str:
    """Safe, deterministic memory injection for LLM prompt."""
    memory = read_memory(learner_id, conn=conn)
    if not memory:
        return ""
    name = get_learner_name(learner_id, conn=conn)
    lines = []
    if name:
        lines.append(f"The learner's name is {name}.")
    favorites = get_favorite_memory(learner_id, conn=conn)
    if favorites:
        fav_str = ", ".join(f"{k}={v}" for k, v in sorted(favorites.items())[:3])
        lines.append(f"Remembered favorites: {fav_str}.")
    # Only include non-sensitive, non-PII items
    safe_items = []
    for k, v in sorted(memory.items()):
        if _is_pii_key(k):
            continue
        if isinstance(v, str) and len(str(v)) > 30:
            v = str(v)[:30] + "..."
        safe_items.append(f"{k}: {v}")
    if safe_items:
        lines.append("Friendship memory (safe, no PII): " + "; ".join(safe_items[:10]) + ".")
    return " ".join(lines)
