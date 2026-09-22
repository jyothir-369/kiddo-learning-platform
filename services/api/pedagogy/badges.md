# Badge / Play Space — Phase 3 (Section 3 §5 — badges/streaks tied to effort + curiosity)
# Not just chat-strip; separate Play screen; celebrates curiosity not only correct answers.

BADGE_RULES = {
    "correct_answer_only": False,
    "effort_celebrated": True,
    "curiosity_celebrated": True,
    "examples": [
        {"badge": "Curious Explorer", "trigger": "asked_5_questions_about_space"},
        {"badge": "Question Asker", "trigger": "asked_10_questions_this_week"},
        {"badge": "Kind Friend", "trigger": "used_specific_praise_or_shared_learning"},
    ],
    "animation": "gentle_bounce_badge_pop",
    "no_distraction": True,
}
