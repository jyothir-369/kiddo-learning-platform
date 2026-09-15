"""Kiddo Assist — video selection engine (Iteration 4, Phase 3, part A).

Implements WORKFLOW §6 steps 6-9 + IMPLEMENTATION-GUIDE §6.6 step 5:

  score = relevance × quality × age_fit × duration_fit × completeness

Each factor is 0.0-1.0.  The composite score must clear VIDEO_BAR for the
video to be played; otherwise Kiddo Assist falls back to a spoken text answer.

Stream-by-reference only (guide §6.9): video_url is always the original
source URL (Wikimedia, NASA, etc.) — never proxy or store video bytes.

\"VIDEO_BAR starts strict (better to speak and wait than to play a wrong
video).  Relax only as the catalog grows.  Wrong-video is a SOT-06 failure.\"
— WORKFLOW §6
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("kiddo.video")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Strict minimum composite score to play a video (WORKFLOW §14.2).
VIDEO_BAR = float(os.getenv("KIDDO_VIDEO_BAR", "0.35"))

# Min/max number of suggested videos (SOT-05).
SUGGESTED_MIN = 2
SUGGESTED_MAX = 4

# Duration thresholds (seconds).
_DURATION_SHORT = 300      # ≤ 5 min → full fit
_DURATION_MAX = 900        # > 15 min → zero fit

# age_range bands we recognise for matching.
_AGE_BANDS = {"4-7", "6-10"}

# ---------------------------------------------------------------------------
# Scoring factors
# ---------------------------------------------------------------------------


def _age_fit(age: int | None, item_age_range: str | None) -> float:
    """How well does the item's age range match the child?

    - Match → 1.0
    - No child age specified → 0.7 (neutral — don't over-penalise)
    - Mismatch → 0.5 (still playable, just not ideal)
    """
    if age is None:
        return 0.7
    if item_age_range is None:
        return 0.7

    # Map child age to expected band.
    if age < 7:
        expected = "4-7"
    elif age <= 12:
        expected = "6-10"
    else:
        return 0.7  # no band for teens yet

    if item_age_range == expected:
        return 1.0
    # Overlap check: "4-7" and "6-10" share age 6-7.
    if expected == "4-7" and item_age_range == "6-10" and age <= 7:
        return 0.9
    if expected == "6-10" and item_age_range == "4-7" and age >= 6:
        return 0.9
    return 0.5


def _duration_fit(duration_s: int | None) -> float:
    """Duration suitability for a child audience.

    Short videos (≤ 5 min) are ideal.  Linear decay 5-15 min.  Beyond 15 min
    → 0.0 (too long for young attention).  Unknown duration (sources, tutorials)
    → 0.8 default.
    """
    if duration_s is None or duration_s <= 0:
        return 0.8  # sources / tutorials / unknown
    if duration_s <= _DURATION_SHORT:
        return 1.0
    if duration_s >= _DURATION_MAX:
        return 0.0
    return max(0.0, 1.0 - (duration_s - _DURATION_SHORT) / (_DURATION_MAX - _DURATION_SHORT))


def _completeness(chunk: dict) -> float:
    """How complete is the content item's metadata?

    Required fields for a rich experience: transcript, url, attribution.
    Each missing field degrades the score.
    """
    has_transcript = bool((chunk.get("transcript") or "").strip())
    has_url = bool((chunk.get("url") or "").strip())
    has_attribution = bool((chunk.get("attribution") or "").strip())

    present = sum([has_transcript, has_url, has_attribution])
    if present == 3:
        return 1.0
    if present == 2:
        return 0.7
    if present == 1:
        return 0.5
    return 0.4


# ---------------------------------------------------------------------------
# Composite video scoring
# ---------------------------------------------------------------------------


def score_video(chunk: dict[str, Any], age: int | None = None) -> float:
    """Compute the composite score for a RAG retrieval chunk.

    Only scores chunks where item_type is 'video' or 'tutorial'.
    Returns 0.0 for non-video/tutorial types.
    """
    item_type = chunk.get("item_type") or chunk.get("type")
    if item_type not in ("video", "tutorial"):
        return 0.0

    # Relevance: use the rerank score from RAG (already a relevance signal).
    relevance = float(chunk.get("rerank_score") or chunk.get("score") or 0.0)
    # Clamp to [0, 1] — reranker scores can exceed 1.0 in some backends.
    relevance = max(0.0, min(1.0, relevance))

    quality = 1.0  # placeholder — all approved content is quality=1.0
    age = _age_fit(age, chunk.get("age_range"))
    dur = _duration_fit(chunk.get("duration_s"))
    comp = _completeness(chunk)

    return round(relevance * quality * age * dur * comp, 6)


# ---------------------------------------------------------------------------
# Video selection
# ---------------------------------------------------------------------------


def select_best_video(
    chunks: list[dict[str, Any]],
    age: int | None = None,
) -> tuple[dict[str, Any] | None, float]:
    """Pick the single best video from RAG retrieval chunks.

    Returns (best_chunk, best_score) or (None, 0.0) when nothing clears
    VIDEO_BAR.  Logs near-misses for catalog quality tuning.
    """
    if not chunks:
        return None, 0.0

    scored: list[tuple[dict[str, Any], float]] = []
    for chunk in chunks:
        s = score_video(chunk, age=age)
        if s > 0.0:
            scored.append((chunk, s))

    if not scored:
        return None, 0.0

    scored.sort(key=lambda x: x[1], reverse=True)
    best_chunk, best_score = scored[0]

    if best_score < VIDEO_BAR:
        logger.info(
            f"Best video score {best_score:.4f} < VIDEO_BAR {VIDEO_BAR:.4f}; "
            f"falling back to text.  item={best_chunk.get('content_item_id')}"
        )
        return None, best_score

    logger.info(
        f"Selected video: {best_chunk.get('content_item_id')} "
        f"(score={best_score:.4f}, title={best_chunk.get('title', '?')})"
    )
    return best_chunk, best_score


# ---------------------------------------------------------------------------
# Suggested videos
# ---------------------------------------------------------------------------


def build_suggested_videos(
    chunks: list[dict[str, Any]],
    exclude_id: str,
    age: int | None = None,
    count_range: tuple[int, int] = (SUGGESTED_MIN, SUGGESTED_MAX),
) -> list[dict[str, Any]]:
    """Build a ranked suggestion list from remaining RAG chunks.

    Excludes the already-selected best video.  Returns 2-4 items (or fewer
    if not enough candidates).  Each item has {id, title, reason}.
    """
    scored: list[tuple[dict[str, Any], float]] = []
    for chunk in chunks:
        cid = chunk.get("content_item_id", "")
        if cid == exclude_id:
            continue
        s = score_video(chunk, age=age)
        if s > 0.0:
            scored.append((chunk, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    min_n, max_n = count_range
    selected = scored[:max_n]

    suggestions: list[dict[str, Any]] = []
    for chunk, score in selected:
        # Generate a simple reason based on score rank.
        if score >= 0.6:
            reason = "closely related topic"
        elif score >= 0.4:
            reason = "related content you might enjoy"
        else:
            reason = "explore more"

        suggestions.append({
            "id": chunk.get("content_item_id", ""),
            "title": chunk.get("title", ""),
            "reason": reason,
        })

    # Ensure minimum count if possible.
    return suggestions[:max(min_n, len(suggestions))]


# ---------------------------------------------------------------------------
# Response builder (called from main.py after orchestrator + safety)
# ---------------------------------------------------------------------------


def build_video_response(
    chunks: list[dict[str, Any]],
    age: int | None = None,
) -> dict[str, Any]:
    """Build the video portion of the WORKFLOW §10 response.

    Returns a dict with keys: video_url, video, suggested_videos, tutorial.
    Called from main.py after the orchestrator and safety check.

    Semantics (Iteration 4, part A):
      - A selected item with a playable `url` → video_url + video metadata.
      - A selected tutorial (with or without a playable step yet) → tutorial
        metadata; video_url stays null until the tutorial has a video step
        (iteration 12 brings step-through).
      - Otherwise → text-only fallback (all four fields null/empty).
    """
    best, score = select_best_video(chunks, age=age)

    if best is None:
        return {
            "video_url": None,
            "video": None,
            "suggested_videos": [],
            "tutorial": None,
        }

    item_type = best.get("item_type") or best.get("type")
    title = best.get("title", "")
    item_id = best.get("content_item_id", "")
    video_url = best.get("url") or None

    # A tutorial match surfaces the tutorial path regardless of step videos.
    tutorial_meta = None
    if item_type == "tutorial":
        tutorial_steps = best.get("tutorial_steps")
        total = len(tutorial_steps) if isinstance(tutorial_steps, list) else 0
        tutorial_meta = {
            "id": item_id,
            "title": title,
            "step": 1,          # iteration 12 adds real step-through
            "total_steps": total,
        }

    # Only a playable URL produces video_url + video metadata.  A bare tutorial
    # (no url) falls back to text guidance around its steps, never an empty
    # video player.
    video_meta = None
    if video_url:
        video_meta = {
            "id": item_id,
            "title": title,
            "attribution": best.get("attribution"),
            "license": best.get("license"),
            "duration_s": best.get("duration_s"),
        }

    suggestions = [] if video_url is None else build_suggested_videos(
        chunks, exclude_id=item_id, age=age
    )

    return {
        "video_url": video_url,
        "video": video_meta,
        "suggested_videos": suggestions,
        "tutorial": tutorial_meta,
    }
