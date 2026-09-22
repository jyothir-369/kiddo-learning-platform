# Conversation History — Phase 4 (§6.2 — scrollable thread, persistent across turns)
# Current gap: each new answer replaces the last. This fixes it.

CHAT_HISTORY_SPEC = {
    "thread_type": "scrollable",
    "visible_elements": ["child_questions", "kiddo_answers", "video_cards", "quiz_cards", "tutorial_cards"],
    "persistent": True,
    "revisit_favorite_explanations": True,
    "revisit_favorite_video": True,
    "no_replacement_per_turn": True,
}
