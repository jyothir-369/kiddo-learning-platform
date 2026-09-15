"""Kiddo Assist — TTS (Iteration 5, Phase 3, part B): Kokoro voice, cached WAV.

Kokoro (APACHE-2.0, warm `af_heart`-style voice) is served via `kokoro-onnx`
(ONNX Runtime, CPU) with phonemization through the bundled phonemizer/espeak-ng
wheels — no torchaudio, no compiler needed.

`synthesize()` returns WAV bytes, cached at `data/audio/{sha256(text+voice+lang)}.wav`
so a repeated answer is a read, not a synth (guide §12 risk 6: latency on CPU →
caching audio answers).

Two backends:
  - Real:  `kokoro_onnx.Kokoro(kokoro-v1.0.onnx, voices-v1.0.bin)`.
           create(text, voice, speed, lang) -> (float32 samples, sample_rate).
  - Sim:   deterministic 0.2 s of silence as a minimal valid WAV.  Enabled by
           KIDDO_TTS_BACKEND=sim; used by the offline test suite (no downloads).

Soft-failing: missing model files / broken backend → returns None and logs;
the chat turn never crashes (audio_url just stays null).  The voice-always
invariant lands in Iteration 9 and is enforced by the eval gate thereafter.
"""
from __future__ import annotations

import hashlib
import logging
import os
import struct
import threading
from pathlib import Path

import config

logger = logging.getLogger("kiddo.tts")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Canonical warm English voice (Kokoro-82M VOICES.md).
VOICE = os.getenv("KIDDO_TTS_VOICE", "af_heart")
# Slightly slower than default for a friendlier, kid-appropriate pace.
SPEED = float(os.getenv("KIDDO_TTS_SPEED", "1.0"))
# Kokoro lang tag for English (American).
TTS_LANG = os.getenv("KIDDO_TTS_LANG", "en-us")

# 24 kHz is Kokoro's native output rate.
SAMPLE_RATE = 24000

# Guard against path tricks in the /api/audio/{id} route.
AUDIO_ID_RE = r"^[a-f0-9]{64}$"

_ENGINE_LOCK = threading.Lock()
_ENGINE = None  # cached Kokoro instance (real backend)


def sim_mode() -> bool:
    """True when the deterministic offline backend is requested (tests)."""
    return os.getenv("KIDDO_TTS_BACKEND", "").lower() == "sim"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def cache_path(text: str, *, voice: str = VOICE, lang: str = TTS_LANG) -> Path:
    """The cached WAV path for this text (stable hash → idempotent writes)."""
    key = hashlib.sha256(f"{text}|{voice}|{lang}".encode("utf-8")).hexdigest()
    return config.AUDIO_DIR / f"{key}.wav"


def get_audio_bytes(audio_id: str) -> bytes | None:
    """Read a cached WAV by its hex id (None if absent / invalid)."""
    if not audio_id or len(audio_id) != 64 or any(c not in "0123456789abcdef" for c in audio_id):
        return None
    path = config.AUDIO_DIR / f"{audio_id}.wav"
    if not path.is_file():
        return None
    return path.read_bytes()


# ---------------------------------------------------------------------------
# WAV writers
# ---------------------------------------------------------------------------


def _write_wav(path: Path, samples: "list[float]", sample_rate: int = SAMPLE_RATE) -> None:
    """Write 16-bit mono PCM WAV via the stdlib `wave` — no torchaudio needed."""
    import wave

    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for s in samples:
            # clamp to int16
            v = max(-1.0, min(1.0, float(s)))
            frames += struct.pack("<h", int(v * 32767))
        w.writeframes(bytes(frames))


def _sim_wav_bytes() -> bytes:
    """A tiny valid WAV of ~0.2 s silence — deterministic for offline tests."""
    duration = 0.2
    n = int(SAMPLE_RATE * duration)
    payload = b"\x00\x00" * n  # 16-bit PCM silence
    # RIFF header, 16-bit mono 24 kHz
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(payload))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(payload))
    )
    return header + payload


# ---------------------------------------------------------------------------
# Real backend
# ---------------------------------------------------------------------------


def _load_engine():
    """Lazily load the Kokoro ONNX engine once (thread-safe)."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            return _ENGINE

        if not config.KOKORO_MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"Kokoro model missing at {config.KOKORO_MODEL_PATH}. "
                "Download kokoro-v1.0.onnx + voices-v1.0.bin into data/models/kokoro/."
            )
        from kokoro_onnx import Kokoro

        engine = Kokoro(str(config.KOKORO_MODEL_PATH), str(config.KOKORO_VOICES_PATH))
        _ENGINE = engine
        return engine


def _real_synthesize_wav(path: Path, text: str, *, voice: str, lang: str, speed: float) -> None:
    """Synthesize with the real engine and write the cached WAV."""
    engine = _load_engine()
    samples, sr = engine.create(text, voice=voice, speed=speed, lang=lang)
    _write_wav(path, samples, sample_rate=sr)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def synthesize(text: str, *, lang: str = TTS_LANG) -> bytes | None:
    """Synthesize `text` to WAV bytes (cached).  Returns None on soft failure.

    Caching contract: same (text, voice, lang) → same file.  If the cache hit
    exists the file is returned as-is; the bytes are always then-served.
    """
    if not text or not text.strip():
        logger.debug("Empty TTS text; returning None")
        return None

    path = cache_path(text, lang=lang)
    try:
        if path.is_file():
            return path.read_bytes()

        if sim_mode():
            return _write_sim_cache(path)

        _real_synthesize_wav(path, text, voice=VOICE, lang=lang, speed=SPEED)
        return path.read_bytes()
    except Exception as exc:
        logger.warning(f"TTS synthesis failed (audio_url will be null): {exc}")
        return None


def _write_sim_cache(path: Path) -> bytes:
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    data = _sim_wav_bytes()
    path.write_bytes(data)
    return data


def audio_url_for(text: str, *, lang: str = TTS_LANG) -> str | None:
    """Synthesize (or retrieve cache) and return the /api/audio/{hash} URL.

    Returns None when synthesis fails so the caller leaves audio_url null
    instead of pointing at a missing file.
    """
    if not text or not text.strip():
        return None
    path = cache_path(text, lang=lang)
    if not path.is_file():
        if synthesize(text, lang=lang) is None:
            return None
    return f"/api/audio/{path.stem}"