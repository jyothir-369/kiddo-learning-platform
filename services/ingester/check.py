"""Kiddo Assist — Ingestion gates: license, completeness, safety, quality, pedagogy (Phase 10A — EXT-02)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kiddo.ingest.check")

ALLOWLIST = {"CC BY", "CC BY-SA", "CC0", "public domain", "US public domain"}
REJECTED = {"unknown", "NC", "CC BY-NC", "CC BY-NC-SA"}  # NC = embed-only / reject

# Safety: ShieldGemma stub (same patterns as input safety)
def shield_check(text: str) -> str:
    import re
    bad = re.compile(r"(self[-\s]?harm|suicide|kill|bomb|porn)", re.I)
    if bad.search(text):
        return "hard"
    return "pass"


def license_check(license_str: str) -> tuple[str, bool]:
    """License allowlist. NC = embed-only (rejected for playable URL). Unknown = reject."""
    lic = (license_str or "").lower()
    # NC variants
    if "nc" in lic and ("by" in lic or "-" in lic):
        return ("rejected_nc_embed_only", False)
    for ok_lic in ALLOWLIST:
        if ok_lic.lower() in lic:
            return ("approved", True)
    return ("rejected_unknown", False)


def completeness_check(item: dict[str, Any]) -> tuple[str, bool, str]:
    """Per content-type completeness gate. Returns (verdict, ok, reason)."""
    itype = item.get("type", "")
    # Video: must have transcript + attribution + topic
    if itype == "video":
        if not item.get("transcript"):
            return ("incomplete", False, "video missing transcript")
        if not item.get("attribution"):
            return ("incomplete", False, "video missing attribution")
        if not item.get("license"):
            return ("incomplete", False, "video missing license")
        # Topic implied by skills or title
        if not item.get("skills") and not item.get("title"):
            return ("incomplete", False, "video missing topic/skills")
        return ("approved", True, "complete")
    # Tutorial: ordered steps + goal + check
    if itype == "tutorial":
        steps = item.get("tutorial_steps")
        if not steps or not isinstance(steps, list) or len(steps) == 0:
            return ("incomplete", False, "tutorial missing ordered steps")
        for s in steps:
            if not s.get("check"):
                return ("incomplete", False, "tutorial step missing check-in")
        return ("approved", True, "complete")
    # Source: full work or clearly labeled excerpt
    if itype == "source":
        transcript = item.get("transcript", "")
        if not transcript:
            return ("incomplete", False, "source missing transcript/text")
        # Check for excerpt label
        text = (item.get("title", "") + " " + transcript).lower()
        if "excerpt" in text or "summary" in text or "partial" in text:
            return ("approved", True, "labeled excerpt")
        # Otherwise require full work indicator
        if len(transcript) < 30:
            return ("incomplete", False, "source text too brief — likely orphan clip")
        return ("approved", True, "complete")
    # Game: minimal completeness
    if itype == "game":
        return ("approved", True, "complete")
    # Unknown type
    return ("rejected", False, "unknown content type")


def quality_pedagogy_gate(item: dict[str, Any]) -> tuple[str, bool, str]:
    itype = item.get("type", "")
    # Age-range match
    age = item.get("age_range", "6-10")
    # Difficulty must be one of known levels
    if item.get("difficulty", "beginner") not in ("beginner", "intermediate", "advanced"):
        return ("incomplete", False, "unknown difficulty")
    # Transcript must be non-empty for video/tutorial
    if itype in ("video", "tutorial", "source") and not item.get("transcript"):
        return ("incomplete", False, "missing transcript/text for quality review")
    return ("approved", True, "quality_ok")


def check_all(item: dict[str, Any]) -> dict[str, Any]:
    # 1. Safety on text first
    text_to_check = item.get("transcript", "") + " " + item.get("title", "")
    shield_verd = shield_check(text_to_check)
    if shield_verd == "hard":
        item["status"] = "review"
        return {"status": "review", "verdict": "hard_block", "reason": "shieldgemma_hard", "approved": False}
    # 2. License gate
    lic_verd, lic_ok = license_check(item.get("license", ""))
    if not lic_ok:
        item["status"] = "review"
        return {"status": "review", "verdict": lic_verd, "reason": "license_gate_failed", "approved": False}
    # 3. Completeness
    comp_verd, comp_ok, comp_reason = completeness_check(item)
    if not comp_ok:
        item["status"] = "incomplete"
        return {"status": "review", "verdict": "incomplete", "reason": comp_reason, "approved": False, "quarantine": True}
    # 4. Quality / pedagogy
    qual_verd, qual_ok, qual_reason = quality_pedagogy_gate(item)
    if not qual_ok:
        item["status"] = "review"
        return {"status": "review", "verdict": qual_verd, "reason": qual_reason, "approved": False}
    # All gates passed — lands at review (never approved at ingestion)
    item["status"] = "review"
    return {"status": "review", "verdict": "pass", "reason": "all_gates_passed", "approved": False}
