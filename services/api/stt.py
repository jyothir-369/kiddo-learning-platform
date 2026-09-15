"""Speech-to-text — faster-whisper multilingual (Iteration 8 / Phase 5, part A).

faster-whisper `small`, INT8 — CPU-friendly, multilingual (covers Hindi
for Phase 6 / EXT-02). Low-confidence transcripts engage the speech-miss
path (§5.4) — never dead-end on a missed word.
"""
from __future__ import annotations

import os
from pathlib import Path

# faster-whisper is imported at call time (lazy) so the module loads
# quickly even before the model weights are pulled.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")


def transcribe(path: str | Path, language: str | None = None) -> dict:
    """Transcribe an audio file; return {text, confidence, segments}.

    `confidence` is the mean segment-level probability (0..1). Below ~0.6
    the chat endpoint should trigger the speech-miss line (§5.4).
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper not installed — install with `pip install faster-whisper`"
        ) from exc

    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE,
    )
    segments, info = model.transcribe(
        str(path),
        beam_size=5,
        language=language,
    )
    texts = []
    confidences = []
    for seg in segments:
        texts.append(seg.text)
        # faster-whisper exposes avg_logprob per segment; approximate
        # confidence via a heuristic mapping for the caller.
        confidences.append(min(1.0, max(0.0, float(seg.avg_logprob) / 2.0)))
    full = " ".join(texts).strip()
    mean_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0
    return {
        "text": full,
        "confidence": mean_conf,
        "language": info.language if info else None,
        "segments": len(texts),
    }
