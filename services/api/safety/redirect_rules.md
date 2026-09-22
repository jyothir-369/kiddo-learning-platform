# Redirect Pattern — Phase 2 (Section 5 — redirect not wall; Section 2 guardrails)
# Every restricted/unsafe topic must pair "I can't help with that" with a real redirect.

REDIRECT_PAIRS = {
    # mapped from classifier category -> child-friendly redirect + warm alternative
    "self_harm_distress": ("I'm here with you. Let's talk about something else — want to explore animals or numbers?", "animals_or_numbers"),
    "violence_weapons_illegal": ("I can't help with that — but I know something fun we could explore together! Want to try space or animals?", "space_or_animals"),
    "adult_sexual_content": ("Let's talk about something fun instead — what do you want to discover?", "fun_discovery"),
    "exploitation": ("I'm here with you. Would you like to talk with a grown-up? And let's explore something fun together.", "adult_check_plus_explore"),
    "hate_bullying_harassment": ("Let's be kind — how about we learn about kindness or a cool animal?", "kindness_or_animal"),
    "jailbreak": ("I'm here to learn with you! Let's keep exploring together.", "continue_exploring"),
    "off_topic": ("Hmm, I don't know that one — want to find out together? Or let's try a quiz?", "co_discovery_or_quiz"),
    "profanity": ("Let's use kind words — want to try a fun topic together?", "fun_topic"),
}

def redirect_for(category: str) -> str:
    msg, _ = REDIRECT_PAIRS.get(category, REDIRECT_PAIRS["off_topic"])
    return msg
