"""Kiddo Assist API — FastAPI gateway.

Iteration 0: liveness /health.
Iteration 2 (Phase 1): /api/chat text chat loop with LLM + output safety.
Iteration 3 (Phase 2): /api/chat routes through RAG grounding (orchestrator →
  rag retrieval → LLM); the response carries `sources` (approved content items
  the answer is grounded in).
Iteration 4 (Phase 3, part A): /api/chat selects the best video from RAG chunks,
  returns video_url + suggested_videos; GET /api/videos/{id} serves stream-by-
  reference metadata.
Iteration 5 (Phase 3, part B): /api/chat returns audio_url for the spoken
  explanation (Kokoro TTS, cached WAV); GET /api/audio/{id} serves it.
Later iterations add /api/profile, /api/parent/*, /api/ingest, and STT.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import config
from config import ASSISTANT_NAME, OLLAMA_HOST
import db
import llm
import orchestrator
import safety
import tts
import video

app = FastAPI(title=f"{ASSISTANT_NAME} API", version="0.1.0")

logger = logging.getLogger("kiddo.main")

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
# Video metadata — stream-by-reference (Iteration 4 / Phase 3, part A)
# ---------------------------------------------------------------------------

@app.get("/api/videos/{video_id}")
async def get_video(video_id: str) -> VideoMetadata:
    """Return stream-by-reference metadata for a content item.

    Never proxy video bytes — the player uses the original source URL
    (guide §6.9, SOT-06).
    """
    conn = db.get_sqlite()
    try:
        row = conn.execute(
            "SELECT id, title, url, attribution, license, duration_s, status "
            "FROM content_items WHERE id = ?",
            (video_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None or row["status"] != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found or not approved.",
        )

    return VideoMetadata(
        id=row["id"],
        title=row["title"],
        attribution=row["attribution"],
        license=row["license"],
        duration_s=row["duration_s"],
    )


# ---------------------------------------------------------------------------
# Cached spoken audio — serves the WAV produced by tts.py (Iteration 5)
# ---------------------------------------------------------------------------

@app.get("/api/audio/{audio_id}", response_class=FileResponse)
async def get_audio(audio_id: str) -> FileResponse:
    """Serve a cached Kokoro WAV by its 64-hex cache id.

    The id is a content hash of the spoken text (see tts.cache_path) — there is
    no per-user audio; re-serving a cached file is cheap and safe.
    """
    if not re.fullmatch(tts.AUDIO_ID_RE, audio_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="audio_id must be a 64-char hex content hash.",
        )
    path = config.AUDIO_DIR / f"{audio_id}.wav"
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio '{audio_id}' not found.",
        )
    return FileResponse(path, media_type="audio/wav", filename=f"{audio_id}.wav")


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

    # 3. Video selection from RAG chunks (Iteration 4 / Phase 3, part A)
    #    Skip video on hard-blocked responses — child gets holding words only.
    video_data: dict = {"video_url": None, "video": None, "suggested_videos": [], "tutorial": None}
    if not verdict.is_blocked:
        try:
            video_data = video.build_video_response(
                result.get("chunks", []),
                age=req.age,
            )
        except Exception as exc:
            logger.warning(f"Video selection failed; returning text-only: {exc}")

    # 4. Spoken answer — Kokoro TTS, cached WAV (Iteration 5 / Phase 3, part B).
    #    Runs off the event loop (CPU synthesis). Soft-fails to audio_url=None.
    audio_url: str | None = None
    try:
        audio_url = await asyncio.to_thread(tts.audio_url_for, final_answer)
    except Exception as exc:
        logger.warning(f"TTS failed; audio_url will be null: {exc}")

    # 5. Build WORKFLOW §10 response skeleton
    return ChatResponse(
        assistant_name=ASSISTANT_NAME,
        answer=final_answer,
        audio_url=audio_url,
        video_url=video_data["video_url"],
        video=video_data["video"],
        suggested_videos=video_data["suggested_videos"],
        tutorial=video_data["tutorial"],
        quiz=None,
        suggested_next=None,
        safety=safety_payload,
        sources=sources,
    )
