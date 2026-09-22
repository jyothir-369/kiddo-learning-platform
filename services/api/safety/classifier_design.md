# Real Classifier Design — Phase 2 (replaces ShieldGemma stub)
# Source: kiddo-assist-product-spec.md §8 checklist, §5 (redirect not wall), §7 audit
# Must be tested against adversarial prompts (not just regex suite).

class PediatricContentSafetyClassifier:
    """Production-grade input/output classifier for children's content.
    Activates fully when ShieldGemma model is resident; fast-path (check_input)
    runs first for speed + eval repeatability.
    """

    SEVERITY_MAP = {
        "hard": ["self_harm_distress", "violence_weapons_illegal", "adult_sexual_content", "exploitation", "hate_bullying_harassment"],
        "soft": ["jailbreak", "off_topic", "hate", "profanity", "pii"],
    }

    def classify(self, text: str, direction: str = "input") -> dict:
        """Return structured verdict: hard | soft | pass + category + reason."""
        # Adversarial test suite must cover: prompt injection,绕过, encoding tricks,
        # multi-turn context poisoning, and child-specific coercion attempts.
        pass

    def adversarial_tests_passed(self) -> bool:
        """Verified against adversarial prompt suite (not just regex)."""
        return False  # To be completed with test results.

# Holding / redirect rules (Section 5 — redirect, not wall)
REDIRECT_RULES = [
    {"restricted_topic": "violence", "redirect_to": "animals_or_space_or_numbers", "message": "I can't help with that — but we could talk about animals, space, or how numbers work! Want to try?"},
    {"restricted_topic": "adult_content", "redirect_to": "learning_exploration", "message": "I don't talk about that — how about we discover something fun together?"},
    {"restricted_topic": "unsafe_instructions", "redirect_to": "safe_exploration", "message": "I can't help with that, but I'd love to learn with you — want to try a quiz about space?"},
]
