"""Kiddo Assist API configuration — env-driven, with safe local defaults.

In Docker Compose, `api` overrides OLLAMA_HOST/GEMMA_TAG/DATA_DIR.
Run locally (uvicorn main:app) and the defaults point at a host Ollama.
"""
import os
from pathlib import Path

# Product name per the source of truth (SOT-14). Never change at runtime.
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Kiddo Assist")

# Ollama address. "http://ollama:11434" when running inside Docker Compose;
# "http://127.0.0.1:11434" when the API runs on the host against a local/other Ollama.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

# Pinned Gemma tag so a model rename can never silently change answers.
GEMMA_TAG = os.getenv("GEMMA_TAG", "gemma3:4b")

# Runtime data (SQLite, LanceDB vectors, cached audio). In compose this is the
# `./data` bind mount at /app/data.
DATA_DIR = Path(
    os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
).resolve()