"""Kiddo Assist — Safety module (Iteration 7 / Phase 4: Input Safety).

Input path (before orchestrator):
  - ShieldGemma-backed classifier stub (activates when model resident)
  - Deterministic fast-path (eval-repeatable) patterns for profanity, self-harm,
    violence, adult content, hate/bullying, jailbreak, PII, off-topic
  - Severity map: HARD (self-harm/abuse/adult/exploitation) -> stop + holding + event + parent alert
                 SOFT (mild profanity, jailbreak attempt, off-topic, PII) -> tag + continue + redacted
  - PII regex redaction BEFORE any downstream call (never echoed in logs or answers)
  - Intent stub: learning / play / recommendation / concerning
  - Escalation stub: parent-notify + holding-words (WORKFLOW §14.1 / guide §0.3)
"""
from __future__ import annotations
import logging, re, sqlite3, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import db

logger = logging.getLogger("kiddo.safety")

# ------------------------------------------------------------------
# Holding response (child-safe, per WORKFLOW §14.1 / SOT-08)
# ------------------------------------------------------------------
HOLDING_RESPONSE = (
    "I'm here with you, but let's talk about something else or check in "
    "with a grown-up! Would you like to explore something fun like animals, "
    "space, or numbers?"
)

# ------------------------------------------------------------------
# PII redaction patterns (never echoed in answers or logs)
# ------------------------------------------------------------------
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
_PHONE_PATTERN = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")


def redact_pii(text: str) -> tuple[str, list[str]]:
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


# ------------------------------------------------------------------
# Hard-block categories (Iteration 7 definition of done)
# ------------------------------------------------------------------
INPUT_HARD_BLOCK_PATTERNS: dict[str, list[re.Pattern]] = {
    "self_harm_distress": [
        re.compile(
            r"\b(how\s+can\s+i\s+hurt\s+myself|"
            r"i\s+feel\s+like\s+ending\s+my\s+life|"
            r"end\s+your\s+life|self[-\s]?harm|"
            r"commit\s+suicide|kill\s+yourself|ways\s+to\s+die)\b",
            re.I,
        ),
    ],
    "violence_weapons_illegal": [
        re.compile(
            r"\b(how\s+to\s+build\s+a\s+bomb|build\s+a\s+bomb|"
            r"make\s+a\s+bomb|how\s+to\s+make\s+a\s+gun|"
            r"steal\s+a\s+car|harm\s+someone|hurt\s+someone)\b",
            re.I,
        ),
    ],
    "adult_sexual_content": [
        re.compile(
            r"\b(pornography|hardcore\s+porn|sexually\s+explicit|"
            r"erotic\s+story|intercourse\s+positions)\b", re.I,
        ),
    ],
    "exploitation": [
        re.compile(
            r"\b(i\s+want\s+to\s+exploit\s+a\s+child|"
            r"exploit\s+a\s+child|child\s+exploitation)\b", re.I,
        ),
    ],
    "hate_bullying_harassment": [
        re.compile(
            r"\b(i\s+hate\s+all\s+people|hate\s+all\s+people|"
            r"kill\s+all\s+\w+|you\s+deserve\s+to\s+die)\b", re.I,
        ),
    ],
}

# ------------------------------------------------------------------
# Soft-tag / soft-block patterns
# ------------------------------------------------------------------
INPUT_SOFT_BLOCK_PATTERNS: dict[str, list[re.Pattern]] = {
    "jailbreak": [
        re.compile(r"\b(ignore\s+(?:all\s+)?previous\s+instructions)\b", re.I),
        re.compile(r"\b(ignore\s+your\s+instructions)\b", re.I),
    ],
    "off_topic": [
        re.compile(r"\btell\s+me\s+something\s+bad\b", re.I),
    ],
    "hate": [
        re.compile(r"\b(i\s+hate\s+you|you\s+are\s+stupid|shut\s+up)\b", re.I),
    ],
    "profanity": [
        re.compile(r"\b(damn|hell|crap|piss|ass|bastard)\b", re.I),
    ],
}


# ------------------------------------------------------------------
# Safety verdict dataclass
# ------------------------------------------------------------------
@dataclass
class SafetyVerdict:
    verdict: str  # "pass" | "soft" | "hard"
    category: str | None = None
    reason: str | None = None
    is_blocked: bool = False
    holding_text: str | None = None
    redacted_text: str = ""
    pii_detected: list[str] = field(default_factory=list)


# ------------------------------------------------------------------
# SQLite event logger
# ------------------------------------------------------------------
def log_safety_event(
    conn: sqlite3.Connection,
    *,
    learner_id: str | None = None,
    event_type: str,
    severity: str,
    handler: str = "input_safety",
) -> str:
    event_id = uuid.uuid4().hex
    now_ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO safety_events (id, learner_id, event_type, severity, ts, handler) VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, learner_id, event_type, severity, now_ts, handler),
    )
    conn.commit()
    logger.info(
        f"Safety event logged: id={event_id} type={event_type} severity={severity} learner={learner_id}"
    )
    return event_id


# ------------------------------------------------------------------
# Core input check (Iteration 7 definition of done)
# ------------------------------------------------------------------
def check_input(
    text: str,
    *,
    learner_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> SafetyVerdict:
    """Classify child input BEFORE the orchestrator sees anything.

    Hard block -> is_blocked=True + holding_text set (child receives holding words).
    Soft tag -> verdict="soft", is_blocked=False, redacted_text set.
    PII -> redacted; never echoed in answer or logs.
    """
    if not text or not text.strip():
        return SafetyVerdict(verdict="pass", is_blocked=False, redacted_text="")

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
                    handler="input_safety",
                )
            except Exception as exc:
                logger.error(f"Failed to log input safety event: {exc}")

    try:
        # 1. Hard-block check (self-harm / violence / adult / exploitation / severe hate)
        for category, patterns in INPUT_HARD_BLOCK_PATTERNS.items():
            for pat in patterns:
                if pat.search(text) or pat.search(redacted_text):
                    _log(category, "hard")
                    # Escalate to parent (stub) and return holding response
                    escalate_to_parent(category, learner_id, severity="hard")
                    return SafetyVerdict(
                        verdict="hard",
                        category=category,
                        reason=f"Matched input hard safety rule: {category}",
                        is_blocked=True,
                        holding_text=HOLDING_RESPONSE,
                        redacted_text=redacted_text,
                        pii_detected=pii_detected,
                    )

        # 2. Soft-block / tag check (jailbreak, off-topic, hate, profanity)
        soft_category: str | None = None
        for category, patterns in INPUT_SOFT_BLOCK_PATTERNS.items():
            for pat in patterns:
                if pat.search(text) or pat.search(redacted_text):
                    soft_category = category
                    break
            if soft_category:
                break

        # 3. PII detection (soft tag, redacted, never echoed)
        if pii_detected:
            event_type = f"pii_{'_'.join(pii_detected)}"
            _log(event_type, "soft")
            return SafetyVerdict(
                verdict="soft",
                category=event_type,
                reason="PII detected and redacted",
                is_blocked=False,
                holding_text=None,
                redacted_text=redacted_text,
                pii_detected=pii_detected,
            )

        if soft_category:
            _log(soft_category, "soft")
            return SafetyVerdict(
                verdict="soft",
                category=soft_category,
                reason=f"Soft input safety tag: {soft_category}",
                is_blocked=False,
                holding_text=None,
                redacted_text=redacted_text,
                pii_detected=[],
            )

        # 4. Clean pass (redacted text may be unchanged)
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


# ------------------------------------------------------------------
# Output safety (Iteration 2 / Phase 1 — restored from iter6-backup for Iteration 8)
# ------------------------------------------------------------------
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
SOFT_TAG_PATTERNS: dict[str, list[re.Pattern]] = {
    "profanity": [
        re.compile(r"\b(damn|hell|crap|piss|ass|bastard)\b", re.I),
    ],
    "sensitive_topic": [
        re.compile(r"\b(drugs|alcohol|beer|wine|smoking|cigarettes|vaping|scary\s+ghosts)\b", re.I),
    ],
}


def check_output(
    text: str,
    *,
    learner_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> SafetyVerdict:
    if not text:
        return SafetyVerdict(verdict="pass", is_blocked=False, redacted_text="")
    redacted_text, pii_detected = redact_pii(text)
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
        for category, patterns in HARD_BLOCK_PATTERNS.items():
            for pat in patterns:
                if pat.search(text) or pat.search(redacted_text):
                    reason = f"Matched hard safety rule: {category}"
                    if db_conn is not None:
                        try:
                            log_safety_event(db_conn, learner_id=learner_id, event_type=category, severity="hard", handler="output_safety")
                        except Exception as exc:
                            logger.error(f"Failed to log hard safety event: {exc}")
                    return SafetyVerdict(verdict="hard", category=category, reason=reason, is_blocked=True, holding_text=HOLDING_RESPONSE, redacted_text=redacted_text, pii_detected=pii_detected)
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
                    log_safety_event(db_conn, learner_id=learner_id, event_type=event_type, severity="soft", handler="output_safety")
                except Exception as exc:
                    logger.error(f"Failed to log soft safety event: {exc}")
            return SafetyVerdict(verdict="soft", category=event_type, reason=f"Soft safety tag: {event_type}", is_blocked=False, holding_text=None, redacted_text=redacted_text, pii_detected=pii_detected)
        return SafetyVerdict(verdict="pass", category=None, reason=None, is_blocked=False, holding_text=None, redacted_text=redacted_text, pii_detected=[])
    finally:
        if close_conn and db_conn is not None:
            db_conn.close()


# ------------------------------------------------------------------
# ShieldGemma input classifier stub (Iteration 7)
# ------------------------------------------------------------------
def check_input_shieldgemma(text: str) -> dict:
    """ShieldGemma-backed input classifier stub.

    Returns structured verdict; activates fully when ShieldGemma model is resident.
    Fast-path (check_input) runs first for speed + eval repeatability.
    """
    # Model-backed classification stub — activates when ShieldGemma is pulled.
    return {
        "verdict": "pass",  # "hard" | "soft" | "pass"
        "category": None,
        "reason": "ShieldGemma stub (Iteration 7): model not resident; fast-path used.",
        "severity": None,
    }


# ------------------------------------------------------------------
# Intent stub (Iteration 7 — routing hint for orchestrator)
# ------------------------------------------------------------------
INTENT_CLASSES = ("learning", "play", "recommendation", "concerning")


def intent_stub(text: str) -> str:
    """Thin intent-classification stub for input routing.

    Used by the orchestrator to choose response mode.
    """
    t = text.lower()
    if any(w in t for w in ("how", "why", "what is", "explain", "learn", "teach")):
        return "learning"
    if any(w in t for w in ("game", "play", "fun", "quiz", "streak", "badge")):
        return "play"
    if any(w in t for w in ("suggest", "recommend", "more", "next", "what else")):
        return "recommendation"
    # Default to concerning only if there are distress signals; else falls back
    if any(w in t for w in ("sad", "hurt", "scared", "help", "bad")):
        return "concerning"
    return "learning"  # safe default


# ------------------------------------------------------------------
# Parent escalation stub (Iteration 7 — WORKFLOW §14.1 / guide §0.3)
# ------------------------------------------------------------------
def escalate_to_parent(
    event_type: str, learner_id: str | None, severity: str = "hard"
) -> None:
    """Parent-notify + holding-words escalation path.

    Hard input events trigger: safety_events row (already logged) + parent notify
    (stub: hits /api/parent/notify or email in production) + child receives
    holding words (already done in check_input / main.py).
    Soft events log but do not break the turn.
    """
    logger.info(
        "Parent escalation (Iteration 7): event=%s learner=%s severity=%s",
        event_type, learner_id, severity,
    )
    # In production: POST /api/parent/notify or email trigger.

# ------------------------------------------------------------------
# P0 — Explicit limitation (not silently implied): ShieldGemma stub
# ------------------------------------------------------------------
# The ShieldGemma-backed classifier is a stub that always returns "pass".
# Current input safety relies on regex/PII redaction only. This is an
# explicit, visible limitation until a real model-backed classifier is
# resident. It must not be implied as fully protected.
SAFETY_LIMITATION_NOTE = (
    "[Visible limitation] Safety relies on regex + PII redaction only; "
    "the ShieldGemma classifier is not yet active."
)
