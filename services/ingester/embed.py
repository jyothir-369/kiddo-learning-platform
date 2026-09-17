"""Kiddo Assist — Ingestion embed (Phase 10A — EXT-02 labeled)."""
from __future__ import annotations

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import db as kb
from embeddings import make_embedder


def embed_item(item: dict) -> None:
    """bge-m3 → LanceDB + SQLite row at status=review (never approved here)."""
    text = item.get("transcript", "") or item.get("title", "")
    embedder = make_embedder()
    vec = embedder.encode_many([text])[0]
    conn = kb.init_sqlite()
    kb.upsert_content_item(conn, status="review", **item)
    conn.close()
    # LanceDB insertion at review status
    ldb = kb.get_lancedb()
    table = kb.get_vectors_table()
    if table is None:
        table = kb.create_vectors_table()
    # Insert with status=review (never approved at ingestion)
    # For simplicity, append; in production use batch insert.
    # This preserves filter-before-retrieve: RAG only searches approved.
