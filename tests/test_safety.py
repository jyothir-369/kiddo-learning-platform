"""tests/test_safety.py — Unit tests for output safety, PII redaction, and event logging.

Covers:
  - PII regex detection and redaction (email, phone, SSN, credit cards).
  - Clean child-friendly text pass.
  - Hard-block triggers (self-harm, violence/weapons, adult content, hate).
  - Safe holding response on hard block.
  - Soft-tagging for mild profanity / sensitive items.
  - SQLite safety_events persistence with 'hard' and 'soft' severities.
"""
import sqlite3
import pytest

import db
import safety


# ---------------------------------------------------------------------------
# PII Redaction
# ---------------------------------------------------------------------------

def test_redact_pii_email():
    text = "Send your homework to teacher.jane@school.org today!"
    redacted, detected = safety.redact_pii(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "teacher.jane@school.org" not in redacted
    assert "email" in detected


def test_redact_pii_phone():
    text = "Call me at 555-123-4567 or (800) 555-0199 for help."
    redacted, detected = safety.redact_pii(text)
    assert "[REDACTED_PHONE]" in redacted
    assert "555-123-4567" not in redacted
    assert "phone" in detected


def test_redact_pii_ssn_and_credit_card():
    text = "Secret numbers: SSN 123-45-6789 and Card 4111-2222-3333-4444."
    redacted, detected = safety.redact_pii(text)
    assert "[REDACTED_ID]" in redacted
    assert "[REDACTED_CARD]" in redacted
    assert "123-45-6789" not in redacted
    assert "4111-2222-3333-4444" not in redacted
    assert "ssn" in detected
    assert "credit_card" in detected


def test_clean_text_no_pii():
    text = "The sky is blue because of Rayleigh scattering."
    redacted, detected = safety.redact_pii(text)
    assert redacted == text
    assert detected == []


# ---------------------------------------------------------------------------
# Output Safety Classification
# ---------------------------------------------------------------------------

def test_check_output_clean_passes():
    text = "Butterflies go through four life stages: egg, caterpillar, chrysalis, and adult!"
    verdict = safety.check_output(text)
    assert verdict.verdict == "pass"
    assert not verdict.is_blocked
    assert verdict.holding_text is None
    assert verdict.category is None
    assert verdict.redacted_text == text


@pytest.mark.parametrize(
    "harmful_text,expected_category",
    [
        ("Here are steps to commit suicide", "self_harm_distress"),
        ("Ways to die and end your life right now", "self_harm_distress"),
        ("Here is how to make a bomb using household chemicals", "violence_weapons_illegal"),
        ("Step-by-step instructions to build a gun at home", "violence_weapons_illegal"),
        ("Let me tell you an erotic story with sexually explicit scenes", "adult_sexual_content"),
        ("We should hate all muslims and attack them", "hate_bullying_harassment"),
    ],
)
def test_check_output_hard_block(harmful_text, expected_category):
    verdict = safety.check_output(harmful_text, learner_id="learner-123")
    assert verdict.verdict == "hard"
    assert verdict.is_blocked is True
    assert verdict.category == expected_category
    assert verdict.holding_text == safety.HOLDING_RESPONSE
    assert "I'm here with you" in verdict.holding_text

    # Verify event was logged to safety_events table
    conn = db.get_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM safety_events WHERE learner_id='learner-123' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row["severity"] == "hard"
        assert row["event_type"] == expected_category
        assert row["handler"] == "output_safety"
    finally:
        conn.close()


def test_check_output_soft_tag_profanity():
    text = "That was a damn difficult puzzle!"
    verdict = safety.check_output(text, learner_id="learner-456")
    assert verdict.verdict == "soft"
    assert verdict.is_blocked is False
    assert verdict.category == "profanity"
    assert verdict.holding_text is None

    conn = db.get_sqlite()
    try:
        row = conn.execute(
            "SELECT * FROM safety_events WHERE learner_id='learner-456' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row["severity"] == "soft"
        assert row["event_type"] == "profanity"
    finally:
        conn.close()


def test_log_safety_event_explicit():
    conn = db.get_sqlite()
    try:
        event_id = safety.log_safety_event(
            conn,
            learner_id="learner-test",
            event_type="test_event",
            severity="hard",
            handler="test_handler",
        )
        row = conn.execute(
            "SELECT * FROM safety_events WHERE id=?", (event_id,)
        ).fetchone()
        assert row is not None
        assert row["learner_id"] == "learner-test"
        assert row["event_type"] == "test_event"
        assert row["severity"] == "hard"
        assert row["handler"] == "test_handler"
    finally:
        conn.close()
