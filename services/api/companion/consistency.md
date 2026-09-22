# Consistency & Memory Continuity — Phase 5 (§2, §4 — small continuity matters)
# Make `persona.py` memory explicit/visible, not hidden.

CONSISTENCY_FEATURES = {
    "remember_name": True,
    "remember_favorite_animal": True,
    "remember_favorite_topic": True,
    "remember_ongoing_project": True,
    "remember_sibling_name": True,
    "visibility": "small_continuity_shown_naturally_not_performatively",
    "source": "persona.build_memory_prompt_fragment + profile_json",
    "avoid_performative": True,  # never over-dramatic "Remember when...?" just natural
}
