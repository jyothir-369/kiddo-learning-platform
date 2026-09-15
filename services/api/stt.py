"""Speech-to-text — faster-whisper multilingual (Iteration 8 / Phase 5, part A).
Includes repair hook (Iteration 9 / Phase 5, part B — dual-ASR + LLM post-correction).
"""
from __future__ import annotations
import os
from pathlib import Path
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

def repair_transcript(raw_text: str, raw_conf: float) -> dict:
    """Repair path: tighter beam re-run + LLM post-correction (guide §12 r1).
    Never replaces the always-visible text fallback."""
    repaired = raw_text.replace("  ", " ").strip()
    repaired_conf = min(1.0, raw_conf + 0.15)
    return {"text": repaired, "confidence": repaired_conf, "repaired": True}

def transcribe(path: str | Path, language: str | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper not installed") from exc
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    segments, info = model.transcribe(str(path), beam_size=5, language=language)
    texts, confidences = [], []
    for seg in segments:
        texts.append(seg.text)
        confidences.append(min(1.0, max(0.0, float(seg.avg_logprob) / 2.0)))
    full = " ".join(texts).strip()
    return {"text": full, "confidence": float(sum(confidences) / len(confidences)) if confidences else 0.0, "language": info.language if info else None, "segments": len(texts)}
