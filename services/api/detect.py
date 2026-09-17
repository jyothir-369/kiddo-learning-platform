"""Language detection — fastText lid.176 + code-switch heuristic (Iteration 10 / EXT-02).

Per-token lid + Devanagari/Latin script check catches English+Hindi
mixed sentences so the pivot knows to translate.
"""
from __future__ import annotations
import os

# fastText lid model path (downloaded once, referenced by env)
LID_MODEL_PATH = os.getenv("FASTTEXT_LID_MODEL", "data/models/lid.176.bin")


def detect(text: str) -> dict:
    """Detect language; return {lang, confidence, is_english, is_hindi, code_switch}.

    Falls back to a simple script heuristic when the model file is absent.
    """
    result = {"lang": "en", "confidence": 1.0, "is_english": True,
              "is_hindi": False, "code_switch": False}
    # Quick heuristic: Devanagari chars => Hindi present
    has_deva = any("ऀ" <= c <= "ॿ" for c in text)
    has_latin = any(c.isascii() and c.isalpha() for c in text)
    if has_deva:
        result["is_hindi"] = True
        result["lang"] = "hi"
        result["code_switch"] = has_latin
    try:
        import fasttext
        model = fasttext.load_model(LID_MODEL_PATH)
        labels, probs = model.predict(text.replace("\n", " ").strip(), k=1)
        pred_lang = labels[0].replace("__label__", "")
        result["lang"] = pred_lang
        result["confidence"] = float(probs[0])
        result["is_english"] = pred_lang.startswith("en")
        result["is_hindi"] = pred_lang.startswith("hi")
        result["code_switch"] = has_deva and has_latin
    except Exception:
        # Model not present yet — heuristic is acceptable for EXT-02 build pass.
        pass
    return result

# EXT-02 per-token code-switch helper
DEVA_RANGE_START = "ऀ"
DEVA_RANGE_END = "ॿ"
LATIN_ALPHAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def _token_lang(token: str) -> str:
    if not token:
        return ""
    deva = sum(1 for ch in token if DEVA_RANGE_START <= ch <= DEVA_RANGE_END)
    latin = sum(1 for ch in token if ch in LATIN_ALPHAS)
    return "hi" if deva > latin else ("en" if latin > 0 else "")

def code_switch_tokens(text: str) -> list[str]:
    tokens = text.replace(",", " ").split()
    return [_token_lang(t) for t in tokens if _token_lang(t)]
