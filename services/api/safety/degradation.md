# Degradation Messages — Phase 2 (Section 8 checklist — load/degradation behavior)
# Child-facing, never silent failure. Every failure must say what's wrong kindly.

DEGRADATION_MESSAGES = {
    "ollama_down": "I'm having a little trouble hearing right now — want to type instead? We'll keep exploring!",
    "tts_down": "My voice is resting a moment — you can read my answer, and I'll try speaking again soon!",
    "stt_down": "Hmm, I didn't quite catch that! Let's try together — you can type or tap the mic again.",
    "rag_empty": "I don't have that one ready — but I'd love to find out with you. Want to try something else?",
    "llm_empty": "I'm thinking but don't have an answer yet — how about we explore together?",
    "network_interrupted": "Looks like the connection took a little nap — want to try again? No rush!",
}
