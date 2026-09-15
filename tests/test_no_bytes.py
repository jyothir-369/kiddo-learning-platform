"""tests/test_no_bytes.py — Iteration 4: filesystem assert for stream-by-reference.

MANDATORY invariant (guide §6.9, SOT-06, WORKFLOW §12): Kiddo Assist never
stores third-party video bytes.  Video is always streamed by reference from
the licensed source (Wikimedia/NASA/...).  This test proves that invariant at
the filesystem level across the whole repo.
"""
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Binary audio/video container extensions we must never persist.
# NOTE: ".ts" (MPEG transport stream) is deliberately excluded — it collides
# with TypeScript source files in this repo and would false-positive.
_VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".ogv", ".ogg", ".avi", ".mkv", ".mov", ".flv",
    ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp",
}


def test_no_video_bytes_stored_repo_wide():
    """A repo-wide scan finds no video containers anywhere under the tree.

    This covers data/, services/, tests/ — everywhere.  The seed catalog only
    holds URLs (stream-by-reference), never the bytes themselves.
    """
    matches = []
    for p in _REPO.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _VIDEO_EXTENSIONS:
            matches.append(str(p))

    assert matches == [], (
        "Third-party video bytes found on disk — this violates stream-by-reference "
        f"(guide §6.9). Files: {matches}"
    )


def test_no_video_bytes_in_data_dir():
    """The runtime data dir (SQLite + vectors + audio cache) holds no video."""
    data_dir = _REPO / "data"
    if not data_dir.exists():
        return  # nothing to scan — invariant trivially holds

    matches = []
    for p in data_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _VIDEO_EXTENSIONS:
            matches.append(str(p))

    assert matches == [], f"data/ contains video bytes: {matches}"


def test_seeded_urls_are_https_stream_references():
    """Every seeded video row references a remote URL, not a local file path."""
    import config  # noqa: F401  (config resolves via test env)
    import db as kb
    from seed import seed

    seed(embed=False)  # autouse fixture cleared the store; vectors not needed here

    conn = kb.get_sqlite()
    try:
        rows = conn.execute(
            "SELECT id, url FROM content_items WHERE type='video'"
        ).fetchall()
    finally:
        conn.close()

    assert rows, "expected seeded video rows"
    for row in rows:
        url = (row["url"] or "").strip()
        assert url, f"video {row['id']} has no url"
        assert url.startswith("https://"), f"video {row['id']} url is not https: {url}"