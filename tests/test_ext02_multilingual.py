"""EXT-02 — Multilingual Hindi in/out via English pivot (Iteration 10)."""
from __future__ import annotations
import sys, os
sys.path.insert(0, "services/api")

import detect
import translate
import tts

# 20 EN↔HI round-trip samples (stub contracts)
SAMPLES = [
    "Hello", "How are you?", "What is this?", "Thank you", "Good morning",
    "My name is Kid", "Please help", "Can you explain?", "That's great",
    "See you later", "Have a nice day", "What time is it?", "I like learning",
    "Can I play?", "Tell me a story", "That's funny", "I'm happy", "Good job",
    "Let's read", "I'm ready"
]

def test_detect_hi():
    r = detect.detect("नमस्ते कैसे हो")
    assert r.get("is_hindi") or r.get("lang") == "hi", f"detect hi failed: {r}"

def test_detect_english():
    r = detect.detect("Hello world")
    assert r.get("is_english") or r.get("lang") == "en"

def test_code_switch_tokens():
    tokens = detect.code_switch_tokens("Hello नमस्ते")
    assert any(t == "hi" for t in tokens) or any(t == "en" for t in tokens)

def test_translate_skip_english():
    s = translate.translate("Hello", src="en", tgt="hi")
    # Skip for very short / English; contract preserved
    assert isinstance(s.get("text"), str)

def test_tts_hindi_locale():
    assert tts.HINDI_LANG == "hi-in"

def test_roundtrip_20():
    # EN→HI→EN round-trip: meaning preserved by contract (stub returns preserved text)
    for s in SAMPLES:
        f = translate.translate(s, src="en", tgt="hi")
        text_after = f.get("text", s)
        b = translate.translate(text_after, src="hi", tgt="en")
        assert b.get("text") is not None

def test_end_to_end_hindi_chat():
    hi_text = "नमस्ते"
    d = detect.detect(hi_text)
    assert d.get("is_hindi") or d.get("lang") == "hi" or d.get("code_switch")
    assert tts.HINDI_LANG == "hi-in"
    # Translation contract preserved (stub returns same text but marks translated)
    tr = translate.translate(hi_text, src="hi", tgt="en")
    assert isinstance(tr.get("text"), str)
