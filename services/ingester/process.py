"""Kiddo Assist — Ingestion process (Phase 10A, part A — EXT-02 labeled)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kiddo.ingest.process")

# Clean/chunk text using source subtitles only; NEVER transcribe downloaded media bytes.


def clean_text(text: str) -> str:
    return text.strip().replace("\n\n", " ")


def build_transcript_from_subtitles(subtitle_text: str | None) -> str:
    """Only source subtitles (never media bytes) feed transcripts."""
    if subtitle_text:
        return clean_text(subtitle_text)
    return ""


def chunk_text(text: str, max_len: int = 500) -> list[str]:
    words = text.split()
    chunks = []
    current = []
    length = 0
    for w in words:
        if length + len(w) + 1 > max_len:
            chunks.append(" ".join(current))
            current = [w]
            length = len(w)
        else:
            current.append(w)
            length += len(w) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks
