"""Kiddo Assist — orchestrator (Iteration 3 first cut, Phase 2).

Routes a child's turn. Today that is the **learning agent**:
  RAG-retrieve → grounded LLM generation.

Anti-hallucination (guide §12 risk 5): the LLM gets "answer only from
retrieved context"; when retrieval returns nothing the orchestrator answers
ungrounded *honestly* rather than inventing a source citation.

The intent router only has one arm today. The recommendation agent, safety
agent (in/out classification) and the play/progress layers land in later
iterations: input safety (Iteration 7), voice (8–9), skill-graph + mastery
(12), streaks/badges (13).
"""
from __future__ import annotations

import logging

import llm
import rag
import persona
import progress

logger = logging.getLogger("kiddo.orchestrator")

DEFAULT_LANG = "en"


def age_to_band(age: int | None) -> str | None:
    """Map a child's age to a seeded `age_range` band for filter-before-retrieve.

    Unknown age → no age filter (don't over-restrict). Teenagers → None so they
    are not locked out of the 6-10 catalog until richer bands are ingested.
    """
    if age is None:
        return None
    if age < 7:
        return "4-7"
    if age <= 12:
        return "6-10"
    return None


def _sources_from_chunks(chunks: list[dict]) -> list[dict]:
    """Grounding metadata for the API response (source id / attribution).

    This is what lets the Phase 2 definition of done assert that an answer is
    grounded in a seeded content item ("in the answer **or metadata**").
    """
    sources = []
    for c in chunks:
        sources.append(
            {
                "id": c.get("content_item_id"),
                "title": c.get("title"),
                "type": c.get("item_type") or c.get("type"),
                "attribution": c.get("attribution"),
                "source": c.get("source"),
                "license": c.get("license"),
                "url": c.get("url"),
                "score": round(float(c.get("score", 0.0)), 4),
            }
        )
    return sources


async def learning_turn(
    text: str,
    *,
    age: int | None = None,
    learner_name: str | None = None,
    lang: str = DEFAULT_LANG,
    learner_id: str | None = None,
) -> dict:
    """Learning agent: query → RAG → grounded LLM answer.

    Returns a dict with `answer` (str), `sources` (list of grounding metadata),
    `chunks` (enriched retrieval hits) and `context` (the prompt block used).
    Embedding/search failures are soft — an ungrounded answer is better than a
    crash, and `sources == []` tells the caller no citation is available.
    """
    import json, db
    chunks: list[dict] = []
    context: str | None = None
    try:
        chunks = rag.search(
            text,
            lang=lang,
            age_range=age_to_band(age),
            top_k=rag.TOP_K,
        )
    except Exception as exc:
        logger.warning(f"RAG retrieval failed; answering ungrounded: {exc}")

    if chunks:
        context = rag.build_context(chunks)

    memory_fragment = ""
    if learner_id:
        memory_fragment = persona.build_memory_prompt_fragment(learner_id, conn=None)
    # Iteration 12 — Progress / mastery / tutorial step-through
    tutorial_meta = None
    quiz_meta = None
    suggested_next_text = None
    item_id = None  # Will be derived from chunks if available
    if chunks:
        item_id = chunks[0].get("content_item_id") if chunks else None
    if learner_id and item_id:
        # Check if item is tutorial; derive step from profile_json or default 1
        try:
            conn = db.get_sqlite()
            row = conn.execute("SELECT type, tutorial_steps FROM content_items WHERE id=?", (item_id,)).fetchone()
            if row and row[0] == "tutorial" and row[1]:
                steps_list = json.loads(row[1])
                total_steps = len(steps_list) if isinstance(steps_list, list) else 1
                # Derive current step from profile or default 1
                profile_row = conn.execute("SELECT profile_json FROM learners WHERE id=?", (learner_id,)).fetchone()
                profile = json.loads(profile_row[0]) if profile_row and profile_row[0] else {}
                steps = profile.get("tutorial_steps") or {}
                current_step = steps.get(item_id, 1)
                tutorial_meta = {"id": item_id, "step": current_step, "total_steps": total_steps}
                # If step requires check-in, return quiz
                # Simple rule: every other step requires check-in for mastery
                if current_step > 0 and (current_step % 2 == 1 or current_step == total_steps):
                    quiz_meta = progress.build_checkin(learner_id, item_id, current_step, total_steps)
            conn.close()
        except Exception:
            pass
        # Frontier-based suggestion
        suggested_next_text = progress.suggested_next(learner_id)

    answer = await llm.generate_response(
        text,
        context=context or None,
        age=age,
        learner_name=learner_name,
        memory_fragment=memory_fragment,
    )

    return {
        "answer": answer,
        "sources": _sources_from_chunks(chunks),
        "chunks": chunks,
        "context": context,
        "tutorial": tutorial_meta,
        "quiz": quiz_meta,
        "suggested_next": suggested_next_text,
    }