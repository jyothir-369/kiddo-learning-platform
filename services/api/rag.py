"""Kiddo Assist — RAG (Iteration 3, Phase 2): embed → hybrid search → rerank.

Implements `IMPLEMENTATION-GUIDE.md` §6.6 "RAG + content ranking":
  1. embed(query)     — bge-m3 dense 1024-d. The sparse/lexical half of hybrid
                        retrieval rides on the LanceDB full-text index over
                        `text_chunk` (bge-m3 sparse == lexical overlap in
                        practice; the guide's hybrid limit(30) is satisfied by
                        unioning vector + FTS survivors).
  2. search(query, )  — **filter-before-retrieve** (guide §6.6 step 3): apply
                        hard metadata filters (status=approved, lang, age_range,
                        safety_tags, duration cap) in LanceDB *before* retrieval,
                        then vector + FTS search (~30 survivors), merge by
                        content_item_id, refine with cosine, and second-pass
                        rerank with bge-reranker-base.
  3. build_context(.) — format the top chunks into a grounded prompt block for
                        the LLM ("answer only from retrieved context").

Embedding/rerank backends live in embeddings.py (FlagEmbedding first, direct
transformers fallback; deterministic sim for tests). Everything here is
soft-failing: no vector table → []; no FTS index → vector-only; no reranker
model → retrieval-order scores. The orchestrator turns an empty result into an
honest ungrounded generation, never a crash.
"""
from __future__ import annotations

import logging
from typing import Any

import config
import db as kb

from embeddings import make_embedder, make_reranker

logger = logging.getLogger("kiddo.rag")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Survivors before rerank (guide §6.6 step 3: limit(30)).
RETRIEVE_LIMIT = 30
# Chunks handed to the orchestrator after rerank.
TOP_K = 5
# Context cap fed into the LLM prompt (fits a 2048-token num_ctx comfortably).
MAX_CONTEXT_CHARS = 4000


# ---------------------------------------------------------------------------
# Embedding (backend lives in embeddings.py; rag.* keeps a thin accessor)
# ---------------------------------------------------------------------------


def embed(text: str) -> list[float]:
    """Embed a query to a 1024-d dense vector (bge-m3, or sim in tests)."""
    return make_embedder().encode_many([text])[0]


def _l2norm(vec: list[float]) -> list[float]:
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


# ---------------------------------------------------------------------------
# Filter-before-retrieve (guide §6.6 step 3)
# ---------------------------------------------------------------------------


def _lit(value: str) -> str:
    """Escape a literal for a LanceDB SQL-like where clause."""
    return "'" + str(value).replace("'", "''") + "'"


def _build_where(
    *,
    lang: str | None = None,
    age_range: str | None = None,
    item_types: list[str] | None = None,
    max_duration_s: int | None = None,
) -> str:
    """Build the hard pre-filter. status=approved is always enforced.

    Only a closed set of enumerations flows in here (language codes, the
    approved age bands from the seed catalog, item types, ints) — never
    free-form user text. duration_s=0 means "no recorded duration" (sources,
    tutorials, games) and passes an explicit cap.
    """
    parts = [f"status = {_lit('approved')}"]
    if lang:
        parts.append(f"lang = {_lit(lang)}")
    if age_range:
        parts.append(f"age_range = {_lit(age_range)}")
    if item_types:
        allowed = ", ".join(_lit(t) for t in item_types)
        parts.append(f"item_type IN ({allowed})")
    if max_duration_s is not None:
        parts.append(f"duration_s <= {int(max_duration_s)}")
    return " AND ".join(parts)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def _vector_search(
    table: kb.lancedb.table.Table,
    query_vec: list[float],
    where: str,
    limit: int,
) -> list[dict[str, Any]]:
    results = (
        table.search(query_vec, query_type="vector")
        .where(where)
        .limit(limit)
        .to_list()
    )
    return [dict(r) for r in results]


def _fts_search(
    table: kb.lancedb.table.Table,
    query_text: str,
    where: str,
    limit: int,
) -> list[dict[str, Any]]:
    results = (
        table.search(query_text, query_type="fts")
        .where(where)
        .limit(limit)
        .to_list()
    )
    return [dict(r) for r in results]


def _merge_survivors(
    vec_rows: list[dict[str, Any]],
    fts_rows: list[dict[str, Any]],
    query_vec: list[float],
) -> list[dict[str, Any]]:
    """Union vector + FTS survivors by (content_item_id, text_chunk).

    Scores a survivor by cosine over the query vector (independent of the
    index distance metric), with a small lexical boost when the full-text and
    vector halves both surfaced it.
    """
    q = _l2norm(query_vec)
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for row in vec_rows + fts_rows:
        key = (row.get("content_item_id", ""), row.get("text_chunk", ""))
        entry = merged.get(key)
        if entry is None:
            entry = dict(row)
            merged[key] = entry
        # score() is LanceDB's full-text relevance; _distance is the vector metric.
        if "score" in row:
            entry["_fts_score"] = max(float(entry.get("_fts_score", 0.0)), float(row["score"]))
        if "_distance" in row:
            entry["_vdist"] = min(float(entry.get("_vdist", 1e9)), float(row["_distance"]))

    chunks: list[dict[str, Any]] = []
    for entry in merged.values():
        vec = entry.get("embedding")
        if not vec:
            continue
        cosine = _cosine(q, _l2norm(vec))
        entry["score"] = cosine
        entry["belongs_to_both"] = entry.get("_vdist") is not None and entry.get("_fts_score") is not None
        chunks.append(entry)
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _sort_survivors(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order survivors: agreed hits first, then raw cosine."""
    chunks.sort(key=lambda c: (c["belongs_to_both"], c["score"]), reverse=True)
    return chunks


# ---------------------------------------------------------------------------
# Rerank (bge-reranker-base; backend from embeddings.py)
# ---------------------------------------------------------------------------


def _rerank(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Second-pass relevance (bge-reranker-base). Fails soft → keep retrieval order."""
    reranker = make_reranker()
    try:
        scores = reranker.rerank(query, chunks)
    except Exception as exc:  # model not downloaded / backend broken
        logger.warning(f"Reranker unavailable; falling back to retrieval scores: {exc}")
        scores = [float(c.get("score", 0.0)) for c in chunks]
    for chunk, s in zip(chunks, scores):
        chunk["rerank_score"] = round(float(s), 6)
        chunk["score"] = float(s)
    chunks.sort(key=lambda c: c["score"], reverse=True)
    return chunks


# ---------------------------------------------------------------------------
# Enrich with SQLite metadata (title, attribution, license, url, ...)
# ---------------------------------------------------------------------------


def _enrich_from_sqlite(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join retrieval hits against content_items so grounding carries attribution."""
    if not chunks:
        return chunks
    ids = [c["content_item_id"] for c in chunks]
    placeholders = ",".join("?" * len(ids))
    conn = kb.get_sqlite()
    try:
        rows = conn.execute(
            f"""SELECT id, type, title, url, transcript, license, source, attribution, skills
                FROM content_items WHERE id IN ({placeholders})""",
            ids,
        ).fetchall()
    finally:
        conn.close()
    meta = {row["id"]: dict(row) for row in rows}
    for chunk in chunks:
        chunk.update(meta.get(chunk["content_item_id"], {}))
    return chunks


# ---------------------------------------------------------------------------
# Public search API
# ---------------------------------------------------------------------------


def search(
    query: str,
    *,
    lang: str | None = None,
    age_range: str | None = None,
    item_types: list[str] | None = None,
    max_duration_s: int | None = None,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Filter-before-retrieve hybrid search over approved content.

    Returns up to `top_k` enriched chunks, ranked by rerank score, each carrying
    content_item_id, text_chunk, score, and SQLite metadata (title, attribution,
    license, url, ...). Returns [] when the catalog is empty or unseeded.
    """
    table = kb.get_vectors_table()
    if table is None:
        logger.debug("No content_vectors table yet; nothing to retrieve.")
        return []
    if table.count_rows() == 0:
        return []

    where = _build_where(
        lang=lang,
        age_range=age_range,
        item_types=item_types,
        max_duration_s=max_duration_s,
    )
    query_vec = embed(query.strip())

    vec_rows: list[dict[str, Any]] = []
    try:
        vec_rows = _vector_search(table, query_vec, where, RETRIEVE_LIMIT)
    except Exception as exc:
        logger.warning(f"Vector retrieval failed: {exc}")

    fts_rows: list[dict[str, Any]] = []
    if query.strip():
        try:
            fts_rows = _fts_search(table, query.strip(), where, RETRIEVE_LIMIT)
        except Exception as exc:
            logger.debug(f"FTS retrieval unavailable (vector-only): {exc}")

    survivors = _merge_survivors(vec_rows, fts_rows, query_vec)
    if not survivors:
        return []
    survivors = _sort_survivors(survivors)
    survivors = _rerank(query, survivors)
    survivors = _enrich_from_sqlite(survivors[:top_k])
    return survivors


def build_context(
    chunks: list[dict[str, Any]],
    *,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """Format top chunks into the grounded context block for the LLM prompt.

    Includes attribution so Kiddo Assist can honestly tell the child where the
    answer came from (guide §6.6 step 5; SOT-03 attribution).
    """
    if not chunks:
        return ""
    lines = []
    for i, c in enumerate(chunks, start=1):
        heading = c.get("title") or c.get("content_item_id")
        attribution = c.get("attribution") or c.get("source") or ""
        body = (c.get("text_chunk") or "").strip()
        lines.append(f"[{i}] {heading}")
        if attribution:
            lines.append(f"    source: {attribution}")
        lines.append(body)
    return "\n\n".join(lines)[:max_chars]