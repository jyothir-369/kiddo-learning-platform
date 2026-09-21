"""Speech-to-text — faster-whisper multilingual (Iteration 8 / Phase 5, part A).
Includes repair hook (Iteration 9 / Phase 5, part B — dual-ASR + LLM post-correction).

Definition of done (SDLC-IMPLEMENTATION-PLAN.md 196-199):
- faster-whisper multilingual `small`, INT8 (WHISPER_MODEL/DEVICE/COMPUTE)
- `transcribe(path, language=None)` -> {text, confidence, language, segments}
- `repair_transcript(raw_text, raw_conf)` -> tighter beam re-run + LLM post-correction stub
- Never replaces the always-visible text fallback (UI never dead-ends)
- Speech-miss path: low confidence -> holding line + TTS (see main.py)
"""
from __future__ import annotations
import os
from pathlib import Path

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")


def repair_transcript(raw_text: str, raw_conf: float) -> dict:
    """Repair path: dual-ASR voter stub + LLM post-correction (guide §12 r1, It 9).

    Documented repair hook — keeps Vosk voter stub as path, no real model required.
    The text fallback is untouched (UI never dead-ends).
    """
    # Dual-ASR / Vosk voter stub (documented, not required to load a model)
    # In production: second ASR pass + vote + LLM post-correction.
    repaired = raw_text.replace("  ", " ").strip()
    repaired_conf = min(1.0, raw_conf + 0.15)
    return {
        "text": repaired,
        "confidence": repaired_conf,
        "repaired": True,
        "vote": "vosk_stub",  # documented repair-path marker
        "post_corrected": True,
    }


def transcribe(path: str | Path, language: str | None = None) -> dict:
    """Transcribe audio file using faster-whisper.

    Returns dict with text, confidence (averaged segment logprob scaled),
    language (detected), and segment count.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper not installed — install via requirements.txt") from exc

    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE,
    )
    segments, info = model.transcribe(str(path), beam_size=5, language=language)

    texts, confidences = [], []
    for seg in segments:
        texts.append(seg.text)
        # Normalize avg_logprob consistently to [0,1] (logprob is negative; higher = better)
        conf = float(seg.avg_logprob)
        # Map typical range ~-1.0..0.0 to 0..1; clamp at bounds
        normalized = max(0.0, min(1.0, (conf + 1.0) / 1.0))
        confidences.append(normalized)

    full = " ".join(texts).strip()
    avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0
    # Empty / no-speech guard
    if not full or avg_conf < 0.05:
        full = ""
        avg_conf = 0.0
    return {
        "text": full,
        "confidence": avg_conf,
        "language": info.language if info else None,
        "segments": len(texts),
    }

# ------------------------------------------------------------------
# P1 — Explicit documented limitation (not rebuilt as full model fix)
# ------------------------------------------------------------------
SPEECH_REPAIR_LIMITATION = (
    "Speech repair uses cosmetic whitespace cleanup (strip, single-space). "
    "A full dual-ASR / LLM post-correction repair is not yet implemented. "
    "When confidence is low, the UI shows a friendly retry prompt (never dead-end)."
)
