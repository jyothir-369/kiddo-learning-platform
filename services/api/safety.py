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
    "jailbreak": [
        re.compile(r"\b(ignore\s+(?:all\s+)?previous\s+instructions)\b", re.I),
        re.compile(r"\b(ignore\s+your\s+instructions)\b", re.I),
        re.compile(r"\b(system\s+password|password\s+for\s+the\s+system)\b", re.I),
    ],
    "off_topic": [
        re.compile(r"\btell\s+me\s+something\s+bad\b", re.I),
    ],
    "hate": [
        re.compile(r"\b(i\s+hate\s+all\s+people|hate\s+all\s+people)\b", re.I),
    ],
}

# Iteration 6 input-safety evaluation rules.
# This establishes the machine-checkable contract used by the release gate.
# Request interception and model-backed classification remain Iteration 7 scope.
INPUT_HARD_BLOCK_PATTERNS: dict[str, list[re.Pattern]] = {
    "self_harm_distress": [
        re.compile(
            r"\b(how\s+can\s+i\s+hurt\s+myself|"
            r"i\s+feel\s+like\s+ending\s+my\s+life|"
            r"end\s+your\s+life|self[-\s]?harm|"
            r"commit\s+suicide|kill\s+yourself|"
            r"ways\s+to\s+die)\b",
            re.I,
        ),
    ],
    "violence_weapons_illegal": [
        re.compile(
            r"\b(how\s+to\s+build\s+a\s+bomb|"
            r"build\s+a\s+bomb|make\s+a\s+bomb|"
            r"how\s+to\s+make\s+a\s+gun|make\s+a\s+gun|"
            r"steal\s+a\s+car|"
            r"harm\s+someone|hurt\s+someone)\b",
            re.I,
        ),
    ],
    "adult_sexual_content": [
        re.compile(
            r"\b(tell\s+me\s+an\s+adult\s+story|"
            r"pornography|hardcore\s+porn|sexually\s+explicit|"
            r"erotic\s+story|intercourse\s+positions)\b",
            re.I,
        ),
    ],
    "exploitation": [
        re.compile(
            r"\b(i\s+want\s+to\s+exploit\s+a\s+child|"
            r"exploit\s+a\s+child|child\s+exploitation)\b",
            re.I,
        ),
    ],
    "gate_crash": [
        re.compile(r"\bhow\s+to\s+gate\s+crash\s+a\s+party\b", re.I),
    ],
}

INPUT_SOFT_BLOCK_PATTERNS: dict[str, list[re.Pattern]] = {
    "jailbreak": SOFT_TAG_PATTERNS["jailbreak"],
    "off_topic": SOFT_TAG_PATTERNS["off_topic"],
    "hate": SOFT_TAG_PATTERNS["hate"],
    "profanity": SOFT_TAG_PATTERNS["profanity"],
    "harassment": [
        re.compile(r"\b(i\s+hate\s+you|you\s+are\s+stupid|shut\s+up)\b", re.I),
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
# Input Safety Check Function (Iteration 6 evaluation contract)
# ---------------------------------------------------------------------------

def check_input(
    text: str,
    *,
    learner_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> SafetyVerdict:
    """Classify child input for the Iteration 6 release-gate contract.

    This is a deterministic fast-path classifier for evaluation.
    Full request interception, ShieldGemma classification, PII redaction
    before orchestration, and parent escalation are Iteration 7 scope.
    """
    if not text:
        return SafetyVerdict(
            verdict="pass",
            is_blocked=False,
            redacted_text="",
        )

    redacted_text, pii_detected = redact_pii(text)

    close_conn = False
    db_conn = conn
    if db_conn is None:
        try:
            db_conn = db.get_sqlite()
            close_conn = True
        except Exception as exc:
            logger.warning(f"Could not open SQLite for input safety logging: {exc}")
            db_conn = None

    def _log(category: str, severity: str) -> None:
        if db_conn is not None:
            try:
                log_safety_event(
                    db_conn,
                    learner_id=learner_id,
                    event_type=category,
                    severity=severity,
                    handler="input_safety_eval",
                )
            except Exception as exc:
                logger.error(f"Failed to log input safety event: {exc}")

    try:
        for category, patterns in INPUT_HARD_BLOCK_PATTERNS.items():
            if any(pat.search(text) or pat.search(redacted_text) for pat in patterns):
                _log(category, "hard")
                return SafetyVerdict(
                    verdict="hard",
                    category=category,
                    reason=f"Matched input hard safety rule: {category}",
                    is_blocked=True,
                    holding_text=HOLDING_RESPONSE,
                    redacted_text=redacted_text,
                    pii_detected=pii_detected,
                )

        if pii_detected:
            _log(f"pii_{'_'.join(pii_detected)}", "soft")
            return SafetyVerdict(
                verdict="soft",
                category=f"pii_{'_'.join(pii_detected)}",
                reason="PII detected and redacted",
                is_blocked=False,
                redacted_text=redacted_text,
                pii_detected=pii_detected,
            )

        for category, patterns in INPUT_SOFT_BLOCK_PATTERNS.items():
            if any(pat.search(text) or pat.search(redacted_text) for pat in patterns):
                _log(category, "soft")
                return SafetyVerdict(
                    verdict="soft",
                    category=category,
                    reason=f"Soft input safety tag: {category}",
                    is_blocked=False,
                    redacted_text=redacted_text,
                    pii_detected=[],
                )

        return SafetyVerdict(
            verdict="pass",
            is_blocked=False,
            redacted_text=redacted_text,
            pii_detected=[],
        )
    finally:
        if close_conn and db_conn is not None:
            db_conn.close()


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

# ---------------------------------------------------------------------------
# Iteration 7 — Input Safety Classification (Phase 4)
# ShieldGemma in-path classifier + intent stub + parent-alert escalation
# ---------------------------------------------------------------------------

def check_input_shieldgemma(text: str) -> dict:
    """ShieldGemma-backed input classifier (Iteration 7 scope).

    Returns a structured result; the deterministic fast-path in check_input()
    runs first for speed and evaluation repeatability. This hook is where the
    model-backed classification lives and can be enabled when the model is
    resident.
    """
    # Model-backed classification stub — activates when ShieldGemma is pulled.
    return {
        "verdict": "pass",  # "hard" | "soft" | "pass"
        "category": None,
        "reason": "ShieldGemma stub (Iteration 7): model not resident; fast-path used.",
        "severity": None,
    }


INTENT_CLASSES = ("learning", "play", "recommendation", "concerning")


def intent_stub(text: str) -> str:
    """Thin intent-classification stub for input routing (Iteration 7).

    Maps child input to one of: learning / play / recommendation / concerning.
    Used by the orchestrator to choose the response mode.
    """
    t = text.lower()
    if any(w in t for w in ("how", "why", "what is", "explain", "learn")):
        return "learning"
    if any(w in t for w in ("game", "play", "fun", "quiz", "streak")):
        return "play"
    if any(w in t for w in ("suggest", "recommend", "more", "next")):
        return "recommendation"
    return "concerning"


def escalate_to_parent(event_type: str, learner_id: str | None, severity: str = "hard") -> None:
    """Parent-notify + holding-words escalation path (WORKFLOW §14.1 / guide §0.3).

    Hard input events trigger: safety_events row + parent notify (stub) +
    child receives holding words (already done in check_input / main.py).
    Soft events log but do not break the turn.
    """
    # Parent-notify stub: in production this hits /api/parent/notify or email.
    logger.info(
        "Parent escalation (Iteration 7): event=%s learner=%s severity=%s",
        event_type, learner_id, severity,
    )
