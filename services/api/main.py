"""Kiddo Assist API — FastAPI gateway.

Iteration 0 (skeleton) scope: liveness /health only.
Later iterations add /api/chat, /api/videos/{id}, /api/audio/{id},
/api/profile, /api/parent/*, /api/ingest and the service modules
(safety, orchestrator, rag, llm, tts, stt, video, persona, ...).
"""
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ASSISTANT_NAME, OLLAMA_HOST

app = FastAPI(title=f"{ASSISTANT_NAME} API", version="0.1.0")

# Dev-wide CORS; tighten origins in Iteration 17 (deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _ollama_status() -> str:
    """Reports whether the Ollama service is reachable (not whether a model is loaded)."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
        return "up" if resp.status_code == 200 else "down"
    except Exception:
        return "down"


@app.get("/api/health")
async def health() -> dict:
    """Liveness: application status + whether Ollama is reachable."""
    ollama = await _ollama_status()
    return {
        "status": "ok" if ollama == "up" else "degraded",
        "assistant": ASSISTANT_NAME,
        "ollama": ollama,
    }