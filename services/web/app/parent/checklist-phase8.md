# Production Readiness Checklist — Phase 8 (§8, §7 audit integration)
# Confirm every item covered before calling production-ready.

CHECKLIST = {
    "real_classifier_live_adversarial_tested": "Phase_2_classifier_design_complete",
    "parent_dashboard_authenticated_load_bearing": "Phase_6_parent_space_complete",
    "pedagogy_fields_rendered_tutorial_quiz_suggested_next": "Phase_3_cards_complete",
    "conversation_history_session_boundaries": "Phase_4_chat_history_+_Phase_2_session_boundaries",
    "accessibility_pass": "Phase_7_accessibility_complete",
    "tone_copy_review_all_strings": "Phase_1_tone_audit_+_Phase_5_friend_+_Phase_6_report",
    "multilingual_fluent_human_review": "Phase_1_equity_+_Phase_6_documented",
    "coppa_data_handling_review": "NEW_PASS_REQUIRED",
    "load_degradation_behavior_defined_child_facing": "Phase_2_degradation_complete",
}

# Final sign-off required: COPPA-style data-handling review (not covered by engineering audit)
COPPA_REVIEW_NEEDED = [
    "what_is_stored_about_child",
    "how_long_stored",
    "who_can_see_it",
    "parent_removal_option",
]
