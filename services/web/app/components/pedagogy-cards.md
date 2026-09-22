# Chat Surface — Phase 3 Integration (Section 6.2 — tutorials, quizzes rendered inline)
# These cards replace silent dropping of API contract fields.

CHAT_CARD_TYPES = {
    "quiz": {"render": "single_friendly_question", "feedback": "immediate_warm", "no_red_x": True},
    "tutorial": {"render": "step_through_next", "affordance": "next_button"},
    "suggested_next": {"render": "soft_suggestion", "autonomy": "suggest_never_insist"},
    "learning_path": {"render": "stepping_stones_visual", "mastery_note": "never_gate"},
}

# Video accessibility — poster + captions (Section 6.2)
VIDEO_ACCESSIBILITY = {
    "poster_state": True,
    "captions_toggle": "large_text",
    "sound_off_support": True,
}
