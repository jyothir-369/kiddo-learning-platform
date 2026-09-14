"""tests/test_llm.py — Unit tests for LLM client and prompt templates.

Covers:
  - Persona system prompt building with Kiddo Assist persona and age tuning.
  - User prompt construction (with and without RAG context).
  - Simulated generation backend for deterministic, fast testing.
"""
import asyncio
import pytest

import config
import llm


def test_build_system_prompt_includes_assistant_name():
    prompt = llm.build_system_prompt()
    assert config.ASSISTANT_NAME in prompt
    assert "Kiddo Assist" in prompt
    assert "6-10 years old" in prompt


def test_build_system_prompt_custom_age_and_learner():
    prompt = llm.build_system_prompt(age=7, learner_name="Maya")
    assert "7 years old" in prompt
    assert "Maya" in prompt


def test_build_user_prompt_without_context():
    text = "Why is the sky blue?"
    built = llm.build_user_prompt(text)
    assert built == text


def test_build_user_prompt_with_context():
    text = "Why is the sky blue?"
    context = "Sunlight scatters through atmospheric particles, favoring shorter blue wavelengths."
    built = llm.build_user_prompt(text, context=context)
    assert context in built
    assert text in built
    assert "approved educational materials" in built


def test_generate_response_simulated(monkeypatch):
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    ans = asyncio.run(llm.generate_response("Why is the sky blue?"))
    assert "blue" in ans.lower()
    assert len(ans) > 20


def test_generate_response_generic_simulated(monkeypatch):
    monkeypatch.setenv("KIDDO_LLM_BACKEND", "sim")
    ans = asyncio.run(llm.generate_response("What is a quantum computer?"))
    assert len(ans) > 10
