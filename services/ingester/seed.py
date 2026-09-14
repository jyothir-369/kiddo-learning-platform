"""Kiddo Assist — dev seed catalog (Iteration 1).

Idempotent dev seeder that builds a small, fully *approved* knowledge base so
RAG (Iteration 3) and the video-first loop (Iteration 4) have data to retrieve.

Idempotency contract: running twice yields identical SQLite + LanceDB rows
(destructive reseed: content_items are INSERT OR REPLACE, the LanceDB table is
rebuild every run).  The human approval gate (Iterations 15-16) replaces this
dev shortcut; every row here lands status=approved.

All content is openly licensed (CC-BY / CC-BY-SA / public-domain NASA) —
stream-by-reference only, never video bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Make the api service importable (db.py + config.py live there).
API_DIR = Path(__file__).resolve().parents[1] / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import config  # noqa: E402  (path above must run first)

import db as kb  # noqa: E402

# ---------------------------------------------------------------------------
# Dev catalog
# ---------------------------------------------------------------------------

# Each entry = kwargs for kb.upsert_content_item + an embedding_text.
# `text` is what gets embedded (searchable surface: title + transcript / steps).

SOURCES: list[dict[str, Any]] = [
    {
        "id": "src-water-cycle",
        "type": "source",
        "title": "The Water Cycle",
        "url": "https://en.wikipedia.org/wiki/Water_cycle",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "skills": ["science", "earth-science"],
        "license": "CC BY-SA",
        "source": "Wikipedia",
        "attribution": "Wikipedia contributors, 'Water cycle', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "The water cycle is the path that water takes as it moves around Earth. "
            "The Sun warms the oceans, and water evaporates and becomes water vapour. "
            "The vapour rises, cools, and turns into clouds — this is called condensation. "
            "When cloud droplets get heavy, they fall as rain or snow, which is precipitation. "
            "Raindrops fill rivers and lakes, and the whole cycle begins again."
        ),
    },
    {
        "id": "src-sky-blue",
        "type": "source",
        "title": "Why Is the Sky Blue?",
        "url": "https://en.wikipedia.org/wiki/Diffuse_sky_radiation",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "skills": ["science", "physics"],
        "license": "CC BY-SA",
        "source": "Wikipedia",
        "attribution": "Wikipedia contributors, 'Diffuse sky radiation', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Sunlight looks white, but it is really made of many colours mixed together. "
            "As sunlight passes through the air, tiny gas molecules bump into the light. "
            "Blue light is scattered more than other colours because its waves are shorter. "
            "So the blue light bounces around the whole sky, and that is why the sky looks blue."
        ),
    },
    {
        "id": "src-the-moon",
        "type": "source",
        "title": "Earth's Moon",
        "url": "https://science.nasa.gov/moon/",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "skills": ["space", "science"],
        "license": "US public domain",
        "source": "NASA",
        "attribution": "NASA, 'About the Moon' (public domain; attribution required)",
        "status": "approved",
        "transcript": (
            "The Moon is Earth's only natural satellite. It has no air and no water, "
            "so footprints on the Moon can last millions of years. The Moon circles Earth "
            "once about every 27 days. We always see the same side of the Moon, because it "
            "rotates at the same speed that it orbits. The Moon's gravity pulls on the oceans "
            "and helps create tides."
        ),
    },
]

VIDEOS: list[dict[str, Any]] = [
    {
        "id": "vid-sky-blue",
        "type": "video",
        "title": "Why Is the Sky Blue?",
        "url": "https://upload.wikimedia.org/wikipedia/commons/9/9b/Sky_-_deep_blue.webm",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "duration_s": 182,
        "skills": ["science", "physics"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Sky', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Have you ever asked, why is the sky blue? The Sun sends white light to Earth. "
            "White light hides all the colours of the rainbow inside it. Air is full of tiny gas molecules. "
            "Blue light has short, quick waves, so it bounces off the molecules the most. "
            "That scattered blue light fills the sky above you. At sunset, the light travels further, "
            "and blue gets scattered away, so you see orange and pink instead."
        ),
    },
    {
        "id": "vid-water-cycle",
        "type": "video",
        "title": "The Water Cycle for Kids",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/16/Water_Cycle.ogv",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "duration_s": 214,
        "skills": ["science", "earth-science"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Water Cycle', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Water is always on the move. It travels in a huge circle called the water cycle. "
            "The Sun heats the sea, and water turns into invisible vapour and rises up. "
            "Up in the cool sky the vapour becomes little droplets and joins into clouds. "
            "This is condensation. When the droplets grow heavy they fall as rain — precipitation. "
            "The rain fills the rivers, the rivers run back to the sea, and the cycle begins again."
        ),
    },
    {
        "id": "vid-bee-pollination",
        "type": "video",
        "title": "How Bees Help Flowers Grow",
        "url": "https://upload.wikimedia.org/wikipedia/commons/9/91/Bee_pollinating_a_flower.webm",
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "duration_s": 156,
        "skills": ["biology", "plants"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Bee pollinating a flower', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "A bee flies from flower to flower collecting sweet nectar. As it sips, "
            "yellow pollen dust sticks to its legs. The bee carries that pollen to the next flower. "
            "This journey is called pollination. When a flower gets pollen from another flower, "
            "it can grow seeds and fruit. That is how bees help plants make new baby plants. "
            "Fruit trees, gardens, and farmers all thank the busy bees."
        ),
    },
    {
        "id": "vid-solar-system",
        "type": "video",
        "title": "Meet the Planets of Our Solar System",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/1b/Solar_System_Animated.webm",
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "duration_s": 245,
        "skills": ["space", "science"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Solar System', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Our solar system has eight planets, and they all orbit the Sun. "
            "The four planets nearest the Sun are rocky: Mercury, Venus, Earth, and Mars. "
            "Then come the giants: Jupiter, Saturn, Uranus, and Neptune. "
            "Earth is the only one we know that has living things. "
            "Saturn is famous for its shiny rings, and Jupiter is the biggest planet of all. "
            "Space is big, and our eight planets are just our home neighbourhood."
        ),
    },
    {
        "id": "vid-plant-parts",
        "type": "video",
        "title": "Parts of a Plant and What They Do",
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/37/Plant_anatomy.webm",
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "duration_s": 168,
        "skills": ["biology", "plants"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Plant anatomy', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Look at a plant closely. The roots grow under the soil and drink up water. "
            "The stem is like a little straw that carries the water up. "
            "The leaves catch sunlight and use it to make food for the plant — this is photosynthesis. "
            "The flower makes seeds so new plants can be born. "
            "Every part of a plant has an important job. Roots, stem, leaves, and flowers work together."
        ),
    },
    {
        "id": "vid-dinosaurs",
        "type": "video",
        "title": "How Dinosaurs Lived Long Ago",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/76/Dinosaur_documentary.webm",
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "duration_s": 278,
        "skills": ["science", "history"],
        "license": "CC BY-SA",
        "source": "Wikimedia Commons",
        "attribution": "Wikimedia Commons, 'Dinosaurs', CC BY-SA 4.0",
        "status": "approved",
        "transcript": (
            "Millions of years ago, dinosaurs walked on Earth. Some were enormous, "
            "like the long-necked Brachiosaurus. Others were fast hunters, like the Velociraptor. "
            "Dinosaurs lived on land, and many laid eggs. They went extinct a long time ago, "
            "but now we study their fossils — the bones they left behind — to learn how they lived. "
            "Birds today are the far-away cousins of dinosaurs."
        ),
    },
]

TUTORIALS: list[dict[str, Any]] = [
    {
        "id": "tut-butterfly-life-cycle",
        "type": "tutorial",
        "title": "The Life Cycle of a Butterfly",
        "url": None,
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "skills": ["biology", "plants"],
        "license": "CC BY-SA",
        "source": "Kiddo Assist dev catalog",
        "attribution": "Dev seed tutorial (open educational content)",
        "status": "approved",
        "transcript": "Learn the four steps of a butterfly's amazing life cycle.",
        "tutorial_steps": [
            {
                "step": 1,
                "title": "It starts as an egg",
                "content": "A butterfly begins life as a tiny egg, usually resting on a leaf.",
                "video_url": None,
                "duration_s": 45,
                "check": "What does a butterfly begin life as?",
            },
            {
                "step": 2,
                "title": "A hungry caterpillar hatches",
                "content": "The egg hatches into a caterpillar that eats leaves and grows very fast.",
                "video_url": None,
                "duration_s": 60,
                "check": "What hatches from the egg?",
            },
            {
                "step": 3,
                "title": "Into the chrysalis",
                "content": "The caterpillar wraps itself into a chrysalis and changes inside.",
                "video_url": None,
                "duration_s": 60,
                "check": "Where does the caterpillar change?",
            },
            {
                "step": 4,
                "title": "A butterfly appears",
                "content": "Out of the chrysalis comes a butterfly with beautiful wings. It can fly and start the cycle again.",
                "video_url": None,
                "duration_s": 60,
                "check": "What comes out of the chrysalis?",
            },
        ],
    },
    {
        "id": "tut-telling-time",
        "type": "tutorial",
        "title": "How to Tell Time",
        "url": None,
        "language": "en",
        "age_range": "6-10",
        "difficulty": "beginner",
        "skills": ["math", "time"],
        "license": "CC BY-SA",
        "source": "Kiddo Assist dev catalog",
        "attribution": "Dev seed tutorial (open educational content)",
        "status": "approved",
        "transcript": "Learn to read a clock in three friendly steps.",
        "tutorial_steps": [
            {
                "step": 1,
                "title": "The clock has two hands",
                "content": "A clock has a short hand for hours and a long hand for minutes. Numbers around the edge tell you the time.",
                "video_url": None,
                "duration_s": 60,
                "check": "Which hand shows the hours?",
            },
            {
                "step": 2,
                "title": "Read the hour first",
                "content": "Look at the short hand. The number it points near is the hour, like 3 o'clock.",
                "video_url": None,
                "duration_s": 60,
                "check": "If the short hand points at 3, what hour is it?",
            },
            {
                "step": 3,
                "title": "Read the minutes next",
                "content": "Count the little marks with the long hand. Each mark is 5 minutes. Together the two hands give the full time.",
                "video_url": None,
                "duration_s": 75,
                "check": "What does each little mark on the clock stand for?",
            },
        ],
    },
]

GAMES: list[dict[str, Any]] = [
    {
        "id": "game-number-match",
        "type": "game",
        "title": "Number Match",
        "url": None,
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "skills": ["math", "counting"],
        "license": "CC BY-SA",
        "source": "Kiddo Assist dev catalog",
        "attribution": "Dev seed game (docs + q/a only; UI ships later)",
        "status": "approved",
        "transcript": "Tap the number that matches the group of dots. Five dots match the number 5!",
    },
    {
        "id": "game-animal-sounds",
        "type": "game",
        "title": "Animal Sounds Quiz",
        "url": None,
        "language": "en",
        "age_range": "4-7",
        "difficulty": "beginner",
        "skills": ["biology", "animals"],
        "license": "CC BY-SA",
        "source": "Kiddo Assist dev catalog",
        "attribution": "Dev seed game (docs + q/a only; UI ships later)",
        "status": "approved",
        "transcript": "Which animal says 'moo'? A cow! Which animal says 'meow'? A cat! Guess the sound and win a star.",
    },
]


def _embedding_text(item: dict[str, Any]) -> str:
    """The text surface to embed for a content item (title + body)."""
    parts = [item["title"]]
    if item.get("transcript"):
        parts.append(item["transcript"])
    steps = item.get("tutorial_steps") or []
    if steps:
        parts.append(" ".join(f"Step {s['step']}: {s['title']}. {s['content']}" for s in steps))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Embedding (BGE-M3 via FlagEmbedding)
# ---------------------------------------------------------------------------


class _Embedder:
    """Lazy BGE-M3 model; encodes a list of texts to 1024-d dense vectors."""

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        from FlagEmbedding import BGEM3FlagModel

        # CPU-only (guide §4). Downloads bge-m3 to the HF cache on first run.
        self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, devices="cpu")

    def encode_many(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._load()
        dense = self._model.encode(texts, return_dense=True, batch_size=8)["dense_vecs"]
        return [row.tolist() for row in dense]


class _SimEmbedder:
    """Deterministic pseudo-embedder, for offline tests only (no model download).

    Token-hash bag-of-words: each word maps to ±1 on a hashed dimension, then
    the vector is normalized. Texts that share words get higher cosine similarity,
    so search semantics are *meaningfully* ordered without bge-m3. Enabled only
    via KIDDO_SEED_BACKEND=sim — the production/verify seed path is bge-m3.
    """

    DIM = 1024

    def encode_many(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import re

        out = []
        for text in texts:
            vec = [0.0] * self.DIM
            for token in re.findall(r"[a-z']+", text.lower()):
                h = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(h[:4], "big") % self.DIM
                sign = 1.0 if h[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([v / norm for v in vec])
        return out


def _make_embedder() -> _Embedder | _SimEmbedder:
    import os

    if os.getenv("KIDDO_SEED_BACKEND", "bge") == "sim":
        return _SimEmbedder()
    return _Embedder()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed(embed: bool = True, rebuild_vectors: bool = True) -> dict:
    """Seed the dev catalog into SQLite + LanceDB. Returns a summary dict.

    Idempotent: INSERT OR REPLACE into SQLite; LanceDB table dropped + rebuilt.
    """
    conn = kb.init_sqlite()

    # --- SQLite rows -----------------------------------------------------
    all_items = SOURCES + VIDEOS + TUTORIALS + GAMES
    for item in all_items:
        kb.upsert_content_item(conn, **item)
    _seed_skills(conn)
    conn.commit()

    # --- Vectors ---------------------------------------------------------
    if embed and rebuild_vectors:
        texts = [_embedding_text(item) for item in all_items]
        embedder = _make_embedder()
        vectors = embedder.encode_many(texts)

        kb.LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
        db = kb.get_lancedb()
        # mode="overwrite" atomically replaces an existing table (lancedb 0.38) —
        # drop+create under async connections races and fails with "already exists".
        data = [
            {
                "content_item_id": item["id"],
                "embedding": vec,
                "text_chunk": text,
                "lang": item.get("language", "en"),
                "age_range": item.get("age_range", "6-10"),
                "difficulty": item.get("difficulty", "beginner"),
                "safety_tags": str(item.get("safety_tags", [])),
                "item_type": item["type"],
            }
            for item, text, vec in zip(all_items, texts, vectors)
        ]
        db.create_table(kb.VECTORS_TABLE, data=data, mode="overwrite")

    counts = kb.count_items(conn, status="approved")
    conn.close()
    return {"items_upserted": len(all_items), "counts_by_type": counts}


def _seed_skills(conn) -> None:
    """Idempotently insert the small skill graph used by the dev catalog."""
    skills = [
        ("sk-science", "science", []),
        ("sk-physics", "physics", ["sk-science"]),
        ("sk-earth", "earth-science", ["sk-science"]),
        ("sk-space", "space", ["sk-science"]),
        ("sk-biology", "biology", ["sk-science"]),
        ("sk-plants", "plants", ["sk-biology"]),
        ("sk-animals", "animals", ["sk-biology"]),
        ("sk-history", "history", []),
        ("sk-math", "math", []),
        ("sk-counting", "counting", ["sk-math"]),
        ("sk-time", "time", ["sk-math"]),
    ]
    for sid, name, parents in skills:
        conn.execute(
            "INSERT OR IGNORE INTO skills (id, name, parents) VALUES (?, ?, ?)",
            (sid, name, str(parents)),
        )
    # Link content → skill
    for item in SOURCES + VIDEOS + TUTORIALS + GAMES:
        for skill_name in item.get("skills", []):
            conn.execute(
                """INSERT OR IGNORE INTO content_skills (content_id, skill_id)
                   SELECT ?, id FROM skills WHERE name = ?""",
                (item["id"], skill_name),
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed the Kiddo Assist dev catalog.")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding (SQLite only).")
    args = parser.parse_args()

    summary = seed(embed=not args.no_embed)
    print(f"Seeded {summary['items_upserted']} approved items -> {kb.SQLITE_PATH}")
    print(f"Counts by type: {summary['counts_by_type']}")