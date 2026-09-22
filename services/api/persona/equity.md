# Equity & Cultural Respect Defaults — Phase 1
# Source: kiddo-assist-product-spec.md §5 (Equity, Cultural respect)
# Must be verified by fluent human before any multilingual release (§8 checklist).

DEFAULT_CONTENT_RULES = {
    "names": ["Aisha", "Leo", "Maya", "Omar", "Sofia", "Kai", "Noor", "Diego"],
    "family_structures": ["two parents", "one parent", "grandparent caregiver", "siblings included"],
    "contexts": ["urban park", "library", "backyard garden", "school science fair", "kitchen cooking"],
    "illustrations_represent_diverse_families": True,
    "illustrations_represent_diverse_abilities": True,
}

MULTILINGUAL_PROCESS = {
    "machine_translation_only": False,
    "fluent_human_review_required": True,
    "review_documented_per_release": True,
    "reviewed_languages": {"hi": "Hindi — requires fluent reviewer per spec §5"},
}
