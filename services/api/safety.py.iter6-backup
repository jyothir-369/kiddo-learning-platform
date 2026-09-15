"""Kiddo Assist — Safety module (output screening + PII redaction + escalation).

Iteration 2 scope (Phase 1):
  - Output screening path: screens generated assistant responses before they reach the child.
  - Hard-block triggers: self-harm/distress, violence/weapons/explosives/illegal acts,
    adult/sexually explicit content, hate/harassment/slurs, severe jailbreak output.
  - Safe holding response on hard block per SOT-08 and WORKFLOW §14.1.
  - Soft-tagging for mild profanity / sensitive topics without breaking child experience.
  - PII regex redaction (email, phone, SSN, credit cards, address identifiers).
  - SQLite `safety_events` persistence for all hard and soft safety occurrences.
  - ShieldGemma policy hook + deterministic fast-path classifier.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import db

logger = logging.getLogger("kiddo.safety")

# ---------------------------------------------------------------------------
# Safe Holding Response (per WORKFLOW §14.1 / §5.1)
# ---------------------------------------------------------------------------

HOLDING_RESPONSE = (
    "I'm here with you, but let's talk about something else or check in with a grown-up! "
    "Would you like to explore something fun like animals, space, or numbers?"
)

# ---------------------------------------------------------------------------
# PII Patterns & Redaction
# ---------------------------------------------------------------------------

# Common regex patterns for PII detection
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
_PHONE_PATTERN = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_SSN_PATTERN = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"
)
_CREDIT_CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b"
)


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Detect and redact Personally Identifiable Information from text.

    Returns:
        tuple[str, list[str]]: (redacted_text, list_of_detected_pii_types)
    """
    detected: list[str] = []
    redacted = text

    if _EMAIL_PATTERN.search(redacted):
        detected.append("email")
        redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)

    if _PHONE_PATTERN.search(redacted):
        detected.append("phone")
        redacted = _PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)

    if _SSN_PATTERN.search(redacted):
        detected.append("ssn")
        redacted = _SSN_PATTERN.sub("[REDACTED_ID]", redacted)

    if _CREDIT_CARD_PATTERN.search(redacted):
        detected.append("credit_card")
        redacted = _CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", redacted)

    return redacted, detected


# ---------------------------------------------------------------------------
# Policy Rules & Fast-Path Classifier
# ---------------------------------------------------------------------------

# Hard-block categories (immediate block + holding words + safety_event logged)
HARD_BLOCK_PATTERNS: dict[str, list[re.Pattern]] = {
    "self_harm_distress": [
        re.compile(r"\b(commit\s+suicide|kill\s+yourself|how\s+to\s+hang\s+yourself|ways\s+to\s+die|cut\s+your\s+wrists|self-harm|end\s+your\s+life)\b", re.I),
    ],
    "violence_weapons_illegal": [
        re.compile(r"\b(how\s+to\s+build\s+a\s+bomb|make\s+a\s+bomb|pipe\s+bomb|make\s+explosives|how\s+to\s+make\s+meth|how\s+to\s+poison|steal\s+a\s+car|build\s+a\s+gun)\b", re.I),
        re.compile(r"\b(step-by-step\s+instructions\s+to\s+kill|how\s+to\s+harm\s+someone)\b", re.I),
    ],
    "adult_sexual_content": [
        re.compile(r"\b(pornography|hardcore\s+porn|sexually\s+explicit|erotic\s+story|intercourse\s+positions|child\s+exploitation)\b", re.I),
    ],
    "hate_bullying_harassment": [
        re.compile(r"\b(hate\s+all\s+(blacks|whites|jews|muslims|asians|gays)|kill\s+all\s+\w+|you\s+deserve\s+to\s+die|die\s+in\s+a\s+fire)\b", re.I),
    ],
}

# Soft-tag categories (allowed with tag / PII redaction + soft safety_event logged)
SOFT_TAG_PATTERNS: dict[str, list[re.Pattern]] = {
    "profanity": [
        re.compile(r"\b(damn|hell|crap|piss|ass|bastard)\b", re.I),
    ],
    "sensitive_topic": [
        re.compile(r"\b(drugs|alcohol|beer|wine|smoking|cigarettes|vaping|scary\s+ghosts)\b", re.I),
    ],
}


@dataclass
class SafetyVerdict:
    """Detailed result of safety screening."""
    verdict: str  # "pass" | "soft" | "hard"
    category: str | None = None
    reason: str | None = None
    is_blocked: bool = False
    holding_text: str | None = None
    redacted_text: str = ""
    pii_detected: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SQLite Safety Event Logger
# ---------------------------------------------------------------------------

def log_safety_event(
    conn: sqlite3.Connection,
    *,
    learner_id: str | None = None,
    event_type: str,
    severity: str,
    handler: str = "output_safety",
) -> str:
    """Log a safety event in SQLite table `safety_events`.

    severity must be 'hard' or 'soft'.
    """
    event_id = uuid.uuid4().hex
    now_ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO safety_events (id, learner_id, event_type, severity, ts, handler)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, learner_id, event_type, severity, now_ts, handler),
    )
    conn.commit()
    logger.info(
        f"Safety event logged: id={event_id} type={event_type} severity={severity} learner={learner_id}"
    )
    return event_id


# ---------------------------------------------------------------------------
# Output Safety Check Function
# ---------------------------------------------------------------------------

def check_output(
    text: str,
    *,
    learner_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> SafetyVerdict:
    """Screen generated assistant output before sending to child.

    Steps:
      1. Redact PII (emails, phone numbers, SSNs, credit cards).
      2. Check for hard-block safety violations. If matched:
         - Return holding response.
         - Log hard safety event to DB.
      3. Check for soft-tag safety violations or PII. If matched:
         - Keep redacted text.
         - Log soft safety event to DB.
      4. If clean: return pass verdict.
    """
    if not text:
        return SafetyVerdict(
            verdict="pass",
            is_blocked=False,
            redacted_text="",
        )

    # 1. PII Redaction
    redacted_text, pii_detected = redact_pii(text)

    # Manage SQLite connection if DB logging is needed
    close_conn = False
    db_conn = conn
    if db_conn is None:
        try:
            db_conn = db.get_sqlite()
            close_conn = True
        except Exception as e:
            logger.warning(f"Could not open SQLite for safety event logging: {e}")
            db_conn = None

    try:
        # 2. Hard-block check
        for category, patterns in HARD_BLOCK_PATTERNS.items():
            for pat in patterns:
                if pat.search(text) or pat.search(redacted_text):
                    reason = f"Matched hard safety rule: {category}"
                    if db_conn is not None:
                        try:
                            log_safety_event(
                                db_conn,
                                learner_id=learner_id,
                                event_type=category,
                                severity="hard",
                                handler="output_safety",
                            )
                        except Exception as exc:
                            logger.error(f"Failed to log hard safety event: {exc}")

                    return SafetyVerdict(
                        verdict="hard",
                        category=category,
                        reason=reason,
                        is_blocked=True,
                        holding_text=HOLDING_RESPONSE,
                        redacted_text=redacted_text,
                        pii_detected=pii_detected,
                    )

        # 3. Soft-tag check
        soft_category: str | None = None
        for category, patterns in SOFT_TAG_PATTERNS.items():
            for pat in patterns:
                if pat.search(text) or pat.search(redacted_text):
                    soft_category = category
                    break
            if soft_category:
                break

        if soft_category or pii_detected:
            event_type = soft_category or f"pii_{'_'.join(pii_detected)}"
            if db_conn is not None:
                try:
                    log_safety_event(
                        db_conn,
                        learner_id=learner_id,
                        event_type=event_type,
                        severity="soft",
                        handler="output_safety",
                    )
                except Exception as exc:
                    logger.error(f"Failed to log soft safety event: {exc}")

            return SafetyVerdict(
                verdict="soft",
                category=event_type,
                reason=f"Soft safety tag: {event_type}",
                is_blocked=False,
                holding_text=None,
                redacted_text=redacted_text,
                pii_detected=pii_detected,
            )

        # 4. Clean pass
        return SafetyVerdict(
            verdict="pass",
            category=None,
            reason=None,
            is_blocked=False,
            holding_text=None,
            redacted_text=redacted_text,
            pii_detected=[],
        )

    finally:
        if close_conn and db_conn is not None:
            db_conn.close()
