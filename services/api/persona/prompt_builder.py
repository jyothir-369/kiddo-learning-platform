"""Prompt builder that reads persona/config.yaml instead of hardcoding strings.
Source: kiddo-assist-product-spec.md §2, §5 — Phase 1 deliverable.
"""
from __future__ import annotations
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_persona() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_prompt_from_config(
    *, age: int | None = None, learner_name: str | None = None, memory_fragment: str | None = None
) -> str:
    """Build prompt from persona config — consistent, configurable, never scattered."""
    cfg = load_persona()
    persona = cfg.get("persona", {})
    traits = persona.get("traits", [])
    guard = persona.get("guardrails", {})
    values = persona.get("values", {})
    companion = persona.get("companion", {})

    lines = [
        f"You are {persona.get('name', 'Kiddo')}, a friendly, warm, curious AI companion.",
        f"Your traits: {', '.join(traits)}.",
        f"Voice rules: {guard.get('sentence_length', 'short')}, praise={guard.get('praise_style')}, irony={guard.get('irony')}, sarcasm={guard.get('sarcasm')}, mistake_framing={guard.get('mistake_framing')}.",
        f"Values: warm, honest, safe; no judgment; redirect not wall; transparent to parents / invisible to kids.",
        f"Companion: not family, not replacement; encourage sharing; autonomy={companion.get('autonomy')}; no manufactured neediness.",
    ]
    if age is not None:
        lines.append(f"Target age: {age} years old. Use simple concrete language; explain through stories and everyday comparisons.")
    if learner_name:
        lines.append(f"You are talking with {learner_name}. Reference their name warmly and naturally.")
    if memory_fragment:
        lines.append(memory_fragment)
    lines.append("Always admit uncertainty honestly instead of improvising confidently.")
    lines.append("Never rush a child, never imply they're slow, never say 'as I already said'.")
    return "\n".join(lines)
