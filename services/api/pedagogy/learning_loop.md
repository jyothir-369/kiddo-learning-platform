# Pedagogy — Learning Loop Cards (Phase 3)
# Source: kiddo-assist-product-spec.md §3 (How Kiddo Helps Kids Learn), §6.2
# Every card must feel like discovery, not lecture / test.

LEARNING_LOOP = [
    {"step": "curiosity_hook", "child_action": "ask_or_nudge", "kiddo_response": "short_explanation_plus_approved_video", "tone": "wonder"},
    {"step": "explore_together", "child_action": "watch_read", "kiddo_response": "framed_as_discovery", "tone": "curious"},
    {"step": "check_understanding", "child_action": "1_question_quiz", "kiddo_response": "game_not_test", "tone": "gentle"},
    {"step": "reinforce_through_doing", "child_action": "mini_game_or_tutorial_step", "kiddo_response": "apply_idea", "tone": "playful"},
    {"step": "celebrate_progress", "child_action": "badge_streak", "kiddo_response": "effort_and_curiosity", "tone": "warm"},
]

# Quiz rules — never show failure / scores
QUIZ_RULES = {
    "questions_per_quiz": 1,
    "stakes": "low",
    "red_x": False,
    "failure_scores": False,
    "feedback": "immediate_warm_either_way",
    "correct_feedback": "You noticed the pattern! Here's what's happening...",
    "incorrect_feedback": "Not quite — that's a great guess though! Here's what's actually happening...",
}

# Mastery — visible stepping stones, never gate curiosity
MASTERY_RULES = {
    "visible_path": "stepping_stones_not_spreadsheet",
    "gate_curiosity": False,
    "mastery_effect": "only_affects_proactive_suggestions",
    "regression": "re_teach_warmly_never_said_before",
    "no_reminders_of_past": True,  # never "you already learned this"
}
