"""Kiddo Assist — LLM client (Gemma via Ollama).

Iteration 2 scope:
  - Async Ollama client pointing to OLLAMA_HOST and pinned GEMMA_TAG.
  - Persona prompt template: warm, friendly, curious, patient companion for children.
  - Age-tuned prompt adjustments (default 6-10 years old).
  - Anti-hallucination grounding instructions for retrieved context.
  - Pluggable simulation backend for fast deterministic test suites (KIDDO_LLM_BACKEND=sim).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

import config

logger = logging.getLogger("kiddo.llm")

# ---------------------------------------------------------------------------
# Persona & Prompt Templates
# ---------------------------------------------------------------------------

DEFAULT_AGE_BAND = "6-10"

BASE_SYSTEM_PROMPT = """You are {assistant_name}, a friendly, warm, and curious AI companion and learning guide for children.

Your persona principles:
1. Always be kind, patient, encouraging, and cheerful.
2. Explain concepts in simple, vivid, age-appropriate language for kids (target age: {age_desc}).
3. Use short sentences and clear paragraphs (1 to 3 short paragraphs).
4. Never be dry, condescending, or overly academic.
5. If you do not know something, say so honestly and suggest exploring it together.
6. If context is provided from approved learning materials, base your explanation directly on that context.
7. Always maintain a safe, wholesome, and positive tone suitable for young learners.
"""


def build_system_prompt(
    *,
    age: int | None = None,
    learner_name: str | None = None,
) -> str:
    """Build the persona system prompt tuned to the learner's age and name."""
    if age is not None:
        age_desc = f"{age} years old"
    else:
        age_desc = f"{DEFAULT_AGE_BAND} years old"

    system = BASE_SYSTEM_PROMPT.format(
        assistant_name=config.ASSISTANT_NAME,
        age_desc=age_desc,
    )

    if learner_name:
        system += f"\nYou are talking with your friend {learner_name}. Reference their name warmly."

    return system.strip()


def build_user_prompt(
    text: str,
    *,
    context: str | None = None,
) -> str:
    """Construct the final prompt, optionally injecting RAG context."""
    if context:
        return (
            f"Here is information from approved educational materials:\n"
            f"---\n{context.strip()}\n---\n\n"
            f"Child's question: {text.strip()}\n\n"
            f"Please explain this warmly and simply for the child using the information above:"
        )
    return text.strip()


# ---------------------------------------------------------------------------
# Simulated responses for fast, deterministic testing
# ---------------------------------------------------------------------------

_SIMULATED_ANSWERS: dict[str, str] = {
    "why is the sky blue": (
        "The sky is blue because sunlight scatters in the air! Sunlight looks white, "
        "but it is made of all the colors of the rainbow. Blue light travels in smaller, "
        "shorter waves than other colors, so it scatters in every direction when it hits "
        "the gases in our atmosphere. That is why we see a beautiful blue sky!"
    ),
    "what is a dinosaur": (
        "Dinosaurs were amazing creatures that lived on Earth millions of years ago! "
        "Some were as tall as tall buildings like the Brachiosaurus, while others were "
        "as small as a chicken. They laid eggs, and today's birds are actually distant "
        "cousins of dinosaurs!"
    ),
    "how do birds fly": (
        "Birds fly using their wings, feathers, and very light bones! When they flap "
        "their wings, the shape of the wing creates lift by making air move faster over "
        "the top. That pushes them up into the sky like a magical glider!"
    ),
}


def _get_simulated_response(prompt: str) -> str:
    """Return a deterministic simulated response for testing."""
    cleaned = prompt.strip().lower().rstrip("?!.,")
    for key, answer in _SIMULATED_ANSWERS.items():
        if key in cleaned:
            return answer
    return (
        f"That is a great question about '{prompt.strip()}'! "
        "Let's explore and discover more fun things together!"
    )


# ---------------------------------------------------------------------------
# LLM Generation
# ---------------------------------------------------------------------------

class LLMServiceError(Exception):
    """Raised when Ollama request fails and no fallback is available."""


DEFAULT_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))


async def generate_response(
    prompt: str,
    *,
    age: int | None = None,
    context: str | None = None,
    learner_name: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Generate an age-appropriate answer from Gemma via Ollama (or sim backend)."""
    # Fast path for simulated mode in test suites
    backend = os.getenv("KIDDO_LLM_BACKEND", "").lower()
    if backend == "sim" or os.getenv("KIDDO_LLM_SIM") == "1":
        return _get_simulated_response(prompt)

    system_prompt = build_system_prompt(age=age, learner_name=learner_name)
    user_prompt = build_user_prompt(prompt, context=context)

    payload: dict[str, Any] = {
        "model": config.GEMMA_TAG,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 512,
            "num_ctx": 2048,
        },
    }

    url = f"{config.OLLAMA_HOST}/api/generate"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "").strip()
            if not response_text:
                raise LLMServiceError("Ollama returned an empty response.")
            return response_text
    except httpx.RequestError as exc:
        logger.error(f"Failed to connect to Ollama at {url}: {exc}")
        # If running in environment without live Ollama, fallback to simulation if allowed
        if os.getenv("KIDDO_ALLOW_SIM_FALLBACK", "1") == "1":
            logger.warning("Falling back to simulated response because Ollama is unreachable.")
            return _get_simulated_response(prompt)
        raise LLMServiceError(f"Could not contact Ollama service: {exc}") from exc
    except Exception as exc:
        logger.error(f"Error during LLM generation: {exc}")
        raise LLMServiceError(f"LLM generation failed: {exc}") from exc
