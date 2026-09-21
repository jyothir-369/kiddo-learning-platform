"""Pedagogy cards — Phase 3 (visible rendering of `tutorial`, `quiz`, `suggested_next`).
Source: kiddo-assist-product-spec.md §3, §7 audit (dead code made visible).
"""
from __future__ import annotations


def build_quiz_card(quiz_meta: dict) -> dict:
    """Single friendly question — no red X, no failure score, warm feedback either way."""
    question = quiz_meta.get("question", "Let's check in — what do you think?")
    return {
        "type": "quiz",
        "question": question,
        "feedback_correct": "You noticed the pattern! Here's what's actually happening...",
        "feedback_incorrect": "Not quite — that's a great guess though! Here's what's actually happening...",
        "show_failure_score": False,
        "red_x": False,
    }


def build_tutorial_card(tutorial_meta: dict) -> dict:
    """Step-through with 'next' affordance."""
    step = tutorial_meta.get("step", 1)
    total = tutorial_meta.get("total_steps", 1)
    return {
        "type": "tutorial",
        "step": step,
        "total_steps": total,
        "affordance": "next",
        "message": f"Let's explore together — step {step} of {total}.",
    }


def build_suggested_next(suggested_text: str) -> dict:
    """Proactive suggestion — mastery only affects suggestions, never gates."""
    return {
        "type": "suggested_next",
        "message": suggested_text or "Want to explore something else? I'm here!",
        "autonomy": "suggest_never_insist",
    }


def build_stepping_stones(path_topics: list[str]) -> dict:
    """Visible stepping stones — not hidden skill graph."""
    return {
        "type": "learning_path",
        "steps": [{"topic": t, "explored": True} for t in path_topics],
        "next_suggestion": path_topics[-1] if path_topics else None,
        "mastery_note": "Mastery affects what's suggested next — never blocks your curiosity!",
    }
