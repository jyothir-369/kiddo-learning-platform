"""Pytest configuration for Kiddo Assist.

Key job: point DATA_DIR at a throwaway temp dir BEFORE any module imports
config/db, so tests never touch the real `data/kiddo.db` or `data/vectors/`.
Also puts services/api on sys.path so `db.py`/`config.py` import cleanly.
Tests use the deterministic sim embedding backend (see seed._SimEmbedder) so
they don't download bge-m3.
"""
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_API_DIR = _REPO / "services" / "api"
_INGESTER_DIR = _REPO / "services" / "ingester"

# Isolation FIRST — config.py bakes DATA_DIR at import time.
_TMP_DATA = Path(tempfile.mkdtemp(prefix="kiddo_test_data_"))
os.environ["DATA_DIR"] = str(_TMP_DATA)
os.environ["KIDDO_SEED_BACKEND"] = "sim"

if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
if str(_INGESTER_DIR) not in sys.path:
    sys.path.insert(0, str(_INGESTER_DIR))

# Import AFTER env is set, so db/config resolve to the temp dir.
import pytest  # noqa: E402

import config  # noqa: E402,F401
import db  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_data_store():
    """Give every test a fresh store under the session's temp DATA_DIR.

    Truncates every SQLite table (in FK-safe order) instead of deleting files —
    Windows file locking makes removing the dir/DB unreliable. The LanceDB vector
    table is self-cleaning: seed.seed() builds it with mode="overwrite".
    """
    conn = db.get_sqlite()
    try:
        _ = db.init_sqlite()  # ensure all tables exist even if never seeded
        conn.execute("PRAGMA foreign_keys=OFF")
        # Child tables first so FK references never block the DELETEs.
        for table in (
            "content_skills", "progress", "badges", "streaks", "safety_events",
            "config", "content_items", "skills", "parents", "learners",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()
    yield