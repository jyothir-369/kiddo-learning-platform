"""Kiddo Assist API — FastAPI gateway.

Iteration 0: liveness /health.
Iteration 2 (Phase 1): /api/chat text chat loop with LLM + output safety.
Iteration 3 (Phase 2): /api/chat routes through RAG grounding (orchestrator →
  rag retrieval → LLM); the response carries `sources` (approved content items
  the answer is grounded in).
Later iterations add /api/videos/{id}, /api/audio/{id}, /api/profile,
/api/parent/*, /api/ingest, and ML service layers (TTS, STT, video...).
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import ASSISTANT_NAME, OLLAMA_HOST
import llm
import orchestrator
import safety

app = FastAPI(title=f"{ASSISTANT_NAME} API", version="0.1.0")

# Dev-wide CORS; tighten origins in Iteration 17 (deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas for API Contracts (WORKFLOW §10)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000, description="Child's typed message or transcribed input")
    learner_id: Optional[str] = Field(None, description="Optional learner ID")
    age: Optional[int] = Field(None, ge=3, le=18, description="Child's age for age-tuning")


class VideoMetadata(BaseModel):
    id: str
    title: str
    attribution: Optional[str] = None
    license: Optional[str] = None
    duration_s: Optional[int] = None


class SuggestedVideoItem(BaseModel):
    id: str
    title: str
    reason: Optional[str] = None


class TutorialMetadata(BaseModel):
    id: str
    title: str
    step: int
    total_steps: int


class SafetyPayload(BaseModel):
    verdict: str  # "pass" | "soft" | "hard"
    flag: Optional[str] = None


class SourceItem(BaseModel):
    """Grounding metadata for a RAG retrieval hit (Iteration 3 / Phase 2).

    Carries the source id + attribution so an answer can be traced to an
    approved content item — the definition of done for RAG (guide §9 Phase 2 —
    "citing an ingested content item", in the answer *or* this metadata).
    """
    id: str
    title: Optional[str] = None
    type: Optional[str] = None          # video|tutorial|source|game
    attribution: Optional[str] = None
    source: Optional[str] = None
    license: Optional[str] = None
    url: Optional[str] = None
    score: Optional[float] = None       # rerank relevance, higher = better


class ChatResponse(BaseModel):
    assistant_name: str = ASSISTANT_NAME
    answer: str
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    video: Optional[VideoMetadata] = None
    suggested_videos: list[SuggestedVideoItem] = Field(default_factory=list)
    tutorial: Optional[TutorialMetadata] = None
    quiz: Optional[dict[str, Any]] = None
    suggested_next: Optional[str] = None
    safety: SafetyPayload
    sources: list[SourceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health / Liveness
# ---------------------------------------------------------------------------

async def _ollama_status() -> str:
    """Reports whether the Ollama service is reachable."""
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


# ---------------------------------------------------------------------------
# Core Chat Loop (Iteration 2 / Phase 1)
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Core chat endpoint (WORKFLOW §10).

    Takes the child's text, generates an age-tuned response from Gemma,
    screens output via the safety classifier, and returns the response skeleton.
    """
    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message text cannot be empty.",
        )

    # 1. Orchestrate the turn: RAG retrieve (Iteration 3) → grounded LLM answer.
    #    `sources` carries the approved content items the answer is grounded in.
    try:
        result = await orchestrator.learning_turn(
            clean_text,
            age=req.age,
            learner_id=req.learner_id,
        )
        raw_answer = result["answer"]
        sources = result["sources"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Assistant generation unavailable: {exc}",
        ) from exc

    # 2. Output safety classification + PII redaction
    verdict = safety.check_output(raw_answer, learner_id=req.learner_id)

    if verdict.is_blocked:
        final_answer = verdict.holding_text or safety.HOLDING_RESPONSE
        safety_payload = SafetyPayload(
            verdict="hard",
            flag=verdict.category,
        )
    elif verdict.verdict == "soft":
        final_answer = verdict.redacted_text
        safety_payload = SafetyPayload(
            verdict="soft",
            flag=verdict.category,
        )
    else:
        final_answer = verdict.redacted_text
        safety_payload = SafetyPayload(
            verdict="pass",
            flag=None,
        )

    # 3. Build WORKFLOW §10 response skeleton (+ sources grounding, Iteration 3)
    return ChatResponse(
        assistant_name=ASSISTANT_NAME,
        answer=final_answer,
        audio_url=None,
        video_url=None,
        video=None,
        suggested_videos=[],
        tutorial=None,
        quiz=None,
        suggested_next=None,
        safety=safety_payload,
        sources=sources,
    )
