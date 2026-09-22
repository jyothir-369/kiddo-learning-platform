# Speech-Miss Recovery — Phase 4 (§6.2 — visually differentiate from normal answer)
# Child understands WHY flow paused; retry action highlighted.

SPEECH_MISS_SPEC = {
    "visual_difference": True,
    "icon": "friendly_icon",
    "message": "Hmm, I didn't quite catch that!",
    "retry_action_highlighted": True,
    "retry_options": ["tap_mic", "tap_to_type"],
    "differentiated_from_normal_answer": True,
    "child_understands_pause_reason": True,
}
