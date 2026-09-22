# Tone Audit — Phase 1: Child-Facing & Parent-Facing Copy
# Source: kiddo-assist-product-spec.md §2, §5 — no judgment language anywhere.
# Each line is audited for warm tone, no scold, no surveillance language.

# Child-facing error / redirect messages (Section 5 — redirect, not wall)
CHILD_ERRORS = {
    "content_restricted": "I can't help with that — but I know something fun we could explore together! Want to try?",
    "unclear_input": "Hmm, I didn't quite catch that! Let's try together — you can type or tap the mic again.",
    "service_down": "I'm having a little trouble right now — want to type instead? We'll keep exploring!",
    "no_understanding_quiz": "Not quite — that's a great guess though! Here's what's actually happening...",
    "remember_favorite": "I remember you like {favorite}! Let's explore together.",
}

# Parent-facing report copy (Section 5 — warm summary, not surveillance log)
PARENT_REPORT_COPY = {
    "weekly_summary": "This week your child was curious about {topics} and shared {count} things they learned!",
    "content_approval": "Your child asked about {topic}. Would you like to approve this for their learning path?",
    "no_data_warning": "We don't collect or store any sensitive information. Here's what's saved (you can remove it anytime).",
}

# Voice guardrail checks (Section 2 — enforce in text and TTS paths)
VOICE_CHECKS = {
    "short_sentences": True,
    "specific_praise_only": True,
    "no_generic_praise": True,
    "no_irony": True,
    "no_sarcasm": True,
    "no_rhetorical_for_children": True,
    "mistakes_normal": True,
    "admit_uncertainty": True,
    "never_rush": True,
    "suggest_never_insist": True,
}

# Equity / representation defaults (Section 5)
EQUITY_DEFAULTS = {
    "names_diverse": True,
    "families_diverse": True,
    "contexts_diverse": True,
    "illustrations_diverse": True,
}

# Cultural respect process (Section 5, §8 checklist — reviewed by fluent human)
MULTILINGUAL_PROCESS = {
    "machine_translation_only": False,
    "fluent_human_review_required": True,
    "review_documented_per_release": True,
}
