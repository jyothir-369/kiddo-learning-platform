"""Kiddo Assist — SQLite + LanceDB data access layer.

SQLite holds all metadata (learners, content_items, progress, skills, config,
safety_events, streaks, badges).  LanceDB holds vector embeddings for semantic
search over content.

Schema reference: IMPLEMENTATION-GUIDE §7.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

# ---------------------------------------------------------------------------
# Paths (resolved from config.DATA_DIR)
# ---------------------------------------------------------------------------

import config

SQLITE_PATH = config.DATA_DIR / "kiddo.db"
LANCEDB_DIR = config.DATA_DIR / "vectors"

# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Learners (children using the product)
CREATE TABLE IF NOT EXISTS learners (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    age         INTEGER,
    language    TEXT DEFAULT 'en',
    parent_id   TEXT,
    profile_json TEXT DEFAULT '{}'
);

-- Parents / guardians
CREATE TABLE IF NOT EXISTS parents (
    id      TEXT PRIMARY KEY,
    email   TEXT NOT NULL,
    auth_id TEXT
);

-- Knowledge-base items (the core content catalog).
-- type domain: video | tutorial | source | game   (WORKFLOW §6.1 / SOT-11)
-- status domain: review | approved | rejected
CREATE TABLE IF NOT EXISTS content_items (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL CHECK (type IN ('video', 'tutorial', 'source', 'game')),
    title           TEXT NOT NULL,
    url             TEXT,
    transcript      TEXT,
    language        TEXT DEFAULT 'en',
    age_range       TEXT DEFAULT '6-10',
    difficulty      TEXT DEFAULT 'beginner',
    duration_s      INTEGER,
    skills          TEXT DEFAULT '[]',       -- JSON array of skill names
    safety_tags     TEXT DEFAULT '[]',       -- JSON array
    license         TEXT,
    source          TEXT,
    attribution     TEXT,
    status          TEXT NOT NULL DEFAULT 'review'
                    CHECK (status IN ('review', 'approved', 'rejected')),
    tutorial_steps  TEXT DEFAULT '[]'        -- JSON array: ordered steps for type=tutorial
);

-- Progress tracking per learner per content item
CREATE TABLE IF NOT EXISTS progress (
    id              TEXT PRIMARY KEY,
    learner_id      TEXT NOT NULL REFERENCES learners(id),
    item_id         TEXT NOT NULL REFERENCES content_items(id),
    watched_seconds INTEGER DEFAULT 0,
    quiz_score      REAL,
    ts              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Skill graph
CREATE TABLE IF NOT EXISTS skills (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    parents TEXT DEFAULT '[]'   -- JSON array of parent skill IDs
);

-- Links content items to skills
CREATE TABLE IF NOT EXISTS content_skills (
    content_id  TEXT NOT NULL REFERENCES content_items(id),
    skill_id    TEXT NOT NULL REFERENCES skills(id),
    PRIMARY KEY (content_id, skill_id)
);

-- Parent-configured controls per learner
CREATE TABLE IF NOT EXISTS config (
    learner_id       TEXT PRIMARY KEY REFERENCES learners(id),
    restricted_topics TEXT DEFAULT '[]',    -- JSON array
    screen_time_min  INTEGER DEFAULT 60,
    language         TEXT DEFAULT 'en'
);

-- Safety event log (hard-blocks, soft-tags, escalations)
CREATE TABLE IF NOT EXISTS safety_events (
    id          TEXT PRIMARY KEY,
    learner_id  TEXT,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('hard', 'soft')),
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    handler     TEXT
);

-- Streak tracking (forgiving: missed day != wipe)
CREATE TABLE IF NOT EXISTS streaks (
    learner_id  TEXT PRIMARY KEY REFERENCES learners(id),
    current     INTEGER DEFAULT 0,
    best        INTEGER DEFAULT 0,
    last_active TEXT
);

-- Badges earned by learners
CREATE TABLE IF NOT EXISTS badges (
    learner_id  TEXT NOT NULL REFERENCES learners(id),
    badge       TEXT NOT NULL,
    earned_ts   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (learner_id, badge)
);
"""

# ---------------------------------------------------------------------------
# LanceDB schema for content_vectors
# ---------------------------------------------------------------------------

VECTORS_SCHEMA = pa.schema([
    pa.field("content_item_id", pa.string()),
    pa.field("embedding", pa.list_(pa.float32(), 1024)),
    pa.field("text_chunk", pa.string()),
    pa.field("lang", pa.string()),
    pa.field("age_range", pa.string()),
    pa.field("difficulty", pa.string()),
    pa.field("safety_tags", pa.string()),  # JSON array, stored as string
    pa.field("item_type", pa.string()),     # video|tutorial|source|game
])

VECTORS_TABLE = "content_vectors"

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    """Create data directories if they don't exist."""
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LANCEDB_DIR.mkdir(parents=True, exist_ok=True)


def get_sqlite(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a new SQLite connection with WAL mode and FK enforcement."""
    path = db_path or SQLITE_PATH
    _ensure_dirs()
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite(db_path: Path | None = None) -> sqlite3.Connection:
    """Create all tables (idempotent) and return the connection."""
    conn = get_sqlite(db_path)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def get_lancedb(db_path: Path | None = None) -> lancedb.DBConnection:
    """Open (or create) the LanceDB database."""
    path = db_path or LANCEDB_DIR
    _ensure_dirs()
    return lancedb.connect(str(path))


def get_vectors_table(db_path: Path | None = None) -> lancedb.table.Table | None:
    """Return the content_vectors table, or None if it doesn't exist yet."""
    db = get_lancedb(db_path)
    try:
        return db.open_table(VECTORS_TABLE)
    except Exception:
        return None


def create_vectors_table(db_path: Path | None = None) -> lancedb.table.Table:
    """Create the content_vectors table (idempotent — drops and recreates if schema differs)."""
    db = get_lancedb(db_path)
    existing = get_vectors_table(db_path)
    if existing is not None:
        # Check if schema matches; if so, return as-is
        try:
            existing.schema  # noqa: B018
            return existing
        except Exception:
            db.drop_table(VECTORS_TABLE)
    # Create with empty initial data so the schema is set
    return db.create_table(VECTORS_TABLE, schema=VECTORS_SCHEMA)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def upsert_content_item(
    conn: sqlite3.Connection,
    *,
    id: str,
    type: str,
    title: str,
    url: str | None = None,
    transcript: str | None = None,
    language: str = "en",
    age_range: str = "6-10",
    difficulty: str = "beginner",
    duration_s: int | None = None,
    skills: list[str] | None = None,
    safety_tags: list[str] | None = None,
    license: str | None = None,
    source: str | None = None,
    attribution: str | None = None,
    status: str = "approved",
    tutorial_steps: list[dict] | None = None,
) -> None:
    """Insert or replace a content item (idempotent).

    Uses ON CONFLICT(id) DO UPDATE rather than INSERT OR REPLACE so that SQLite
    CHECK + NOT NULL constraints are still enforced on the incoming row (the
    REPLACE algorithm silently accepts NULLs on NOT NULL columns).
    """
    conn.execute(
        """
        INSERT INTO content_items
            (id, type, title, url, transcript, language, age_range, difficulty,
             duration_s, skills, safety_tags, license, source, attribution,
             status, tutorial_steps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            type=excluded.type, title=excluded.title, url=excluded.url,
            transcript=excluded.transcript, language=excluded.language,
            age_range=excluded.age_range, difficulty=excluded.difficulty,
            duration_s=excluded.duration_s, skills=excluded.skills,
            safety_tags=excluded.safety_tags, license=excluded.license,
            source=excluded.source, attribution=excluded.attribution,
            status=excluded.status, tutorial_steps=excluded.tutorial_steps
        """,
        (
            id,
            type,
            title,
            url,
            transcript,
            language,
            age_range,
            difficulty,
            duration_s,
            json.dumps(skills or []),
            json.dumps(safety_tags or []),
            license,
            source,
            attribution,
            status,
            json.dumps(tutorial_steps or []),
        ),
    )


def count_items(conn: sqlite3.Connection, status: str = "approved") -> dict[str, int]:
    """Count approved items by type."""
    cursor = conn.execute(
        "SELECT type, COUNT(*) FROM content_items WHERE status = ? GROUP BY type",
        (status,),
    )
    return dict(cursor.fetchall())


def search_content_vectors(
    table: lancedb.table.Table,
    embedding: list[float],
    *,
    limit: int = 10,
    lang: str | None = None,
    age_range: str | None = None,
    item_type: str | None = None,
) -> list[dict[str, Any]]:
    """Hybrid search over content vectors with metadata filters.

    This is the read-side path that RAG (Iteration 3) will call.
    Returns a list of dicts with content_item_id, score, text_chunk, etc.
    """
    query = table.search(embedding)

    # Build WHERE clauses (filter-before-retrieve per guide §6.6).
    # NOTE: LanceDB .where() takes a SQL-like string with quoted literals —
    # values are interpolated here (never `?` params). Only trusted enumerations
    # flow in from this module; user-driven filtering is normalized upstream.
    def _lit(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    filters: list[str] = []
    if lang:
        filters.append(f"lang = {_lit(lang)}")
    if age_range:
        filters.append(f"age_range = {_lit(age_range)}")
    if item_type:
        filters.append(f"item_type = {_lit(item_type)}")

    if filters:
        query = query.where(" AND ".join(filters))

    results = query.limit(limit).to_list()
    return results
