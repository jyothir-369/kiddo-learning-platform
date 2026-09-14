# Kiddo Learning Platform — Implementation Guide

This document is the build book for turning `kiddo-architecture.md` into a working, local, **100% open-source, $0/month** product. Read it end-to-end once before starting; then use each phase's "definition of done" as your gate.

---

## 0. Guiding principles (read first)

1. **Open-source, free, local.** No paid APIs. Every service runs on your machine via Docker + Ollama. The only recurring cost is electricity.
2. **Video-first.** A child speaks → Kiddo fetches the best video → it plays in the in-app player, with Kiddo's voice explaining alongside. Everything in this guide serves that loop.
3. **Safe by construction, not by hope.** Safety is a classifier in the request path, not a prompt. It screens both the child's input *and* Kiddo's output.
4. **Stream, don't rehost.** We never download/re-serve third-party videos. We store transcript + metadata and point the player at the licensed source URL.
5. **Build in the order given.** Each phase ships and is testable on its own. Do not skip ahead — the phases chain together.

---

## 1. Decisions locked in (product owner consent)

| Decision | Choice | Where it matters |
|---|---|---|
| Documentation location | `IMPLEMENTATION-GUIDE.md` + Appendix A in the architecture doc | — |
| Runtime hardware | **CPU-only laptop**, small quantized models | §4, §6.7, §10 |
| Video strategy | **Stream-by-reference** from openly-licensed catalogs | §6.9, §6.11 |
| Pivot language | **English** internal pivot; answers + voice back in the child's language | §6.3 |

---

## 2. System recap

Three cooperating systems plus one personality thread (from the architecture doc):

- **Live request flow** — child → STT → safety → orchestrator (3 agents) → RAG+LLM → output safety → video player + TTS
- **Content ingestion** — offline: collect openly-licensed content → transcript → safe → approve → embed → DBs
- **Parent system** — authenticated dashboard: progress, controls, reports, config
- **Kiddo persona** — friendly companion with memory; play layer; growth progression (§2.8–§2.10 of the architecture doc)

---

## 3. Open-source technology stack (final)

| Layer | Tool | Licence | Why this one |
|---|---|---|---|
| Frontend | Next.js 14/15 (App Router) | MIT | Authorized by architecture; free |
| API gateway / services | FastAPI + Uvicorn | MIT | Free, async, Python (matches ML stack) |
| Speech-to-text | faster-whisper, model `small` (multilingual), INT8 | MIT | 4× faster than Whisper, CPU-friendly, multilíngual (needed for Hindi) |
| Language detection | fastText `lid.176` | BSD | Small, fast, ~176 languages |
| Code-switch detection | fastText per-token + Devanagari/Latin script heuristic | BSD | Cheap way to catch English+Hindi in one sentence |
| Pivot translation | Helsinki OPUS-MT `mul-en` / `en-mul` (transformers) | CC-BY 4.0 | Free licence (NLLB is CC-BY-NC — excluded). Many-to/from-English covers the pivot |
| Embeddings | BAAI/bge-m3 (1024-dim, dense + sparse) | MIT | 100+ languages; hybrid retrieval in one model |
| Vector/hybrid store | LanceDB (embedded; vector + full-text + metadata filter) | Apache-2.0 | No server to run; metadata filters map to arch §2.6 |
| Reranking | BAAI/bge-reranker-base | MIT | Second-stage relevance pass |
| LLM | Gemma 4 (or Gemma 3) quantized via Ollama | Open weights, free | ~4B model runs on CPU; strong, safe-by-default open model |
| Input/output safety | ShieldGemma classifier (transformers) | Open weights | Classifies prompts AND responses against a policy |
| TTS | Kokoro (82M params), warm English/Hindi voice | Apache-2.0 | Piper is archived/GPL; Kokoro is Apache + high quality |
| Video | Stream-by-reference (HTML5 `<video>` / embed) | — | Legal, cheap, no rehosting |
| Profiles / progress | SQLite | MIT | Zero-config; perfect first-pass persistence |
| Parent auth | Auth.js (NextAuth v5) | MIT | Native to Next.js, free |
| Orchestration | Docker Compose + Ollama | Apache-2.0 / MIT | One command to start everything |
| Ingestion tooling | Python scripts + CLI review queue | — | Simple, auditable |

**Excluded on purpose (licence/tech risk):** Piper (archived → GPL successor), NLLB translation (CC-BY-NC), Coqui/Edge-TTS (matured/closed), cloud LLM APIs (paid).

---

## 4. Prerequisites & hardware

- A laptop/desktop with ≥ **8 GB RAM** (16 GB recommended) and **~25 GB free disk** for models.
- CPU-only is fine. Optional: any NVIDIA GPU with ≥ 6 GB VRAM speeds things up; nothing here *requires* it.
- Install: **Docker + Docker Compose** (or Python 3.11+ locally), **Git**, **Ollama**.
- Windows note: everything below uses Docker + WSL2 or plain `python` on Windows — both work.

---

## 5. Repository layout (proposed monorepo)

```
kiddo/
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ services/
│  ├─ api/                 # FastAPI gateway + all service workers
│  │  ├─ main.py           # own routes: /api/chat, /api/parent, /api/health
│  │  ├─ config.py         # env + model paths
│  │  ├─ stt.py            # faster-whisper wrapper
│  │  ├─ detect.py         # fastText lid + code-switch
│  │  ├─ translate.py      # OPUS-MT pivot (→ EN)
│  │  ├─ safety.py         # ShieldGemma input/output classification
│  │  ├─ orchestrator.py   # intent classifier + 3 agents
│  │  ├─ rag.py            # bge-m3 embed + LanceDB search + rerank
│  │  ├─ llm.py            # Ollama client (Gemma)
│  │  ├─ tts.py            # Kokoro wrapper
│  │  ├─ video.py          # video selection + stream-by-reference
│  │  ├─ persona.py        # companion memory (2.8)
│  │  ├─ play.py           # streaks/badges (2.9)
│  │  ├─ progress.py       # skill graph (2.10)
│  │  └─ db.py             # SQLite + LanceDB access
│  ├─ ingester/            # offline content pipeline (arch §3)
│  │  ├─ collect.py        # openly-licensed source fetchers
│  │  ├─ process.py        # clean + transcribe/extract transcript
│  │  ├─ check.py          # safety + quality checks
│  │  ├─ embed.py          # bge-m3 → LanceDB + SQLite
│  │  └─ review_cli.py     # human approval gate
│  └─ web/                 # Next.js frontend + parent dashboard
│     ├─ app/
│     │  ├─ chat/          # child UI: input, avatar, video player
│     │  ├─ parent/        # dashboard (auth required)
│     │  └─ ...
├─ data/                   # SQLite file, LanceDB dir, model cache
└─ eval/                    # kid-safe evaluation suite (§11.3)
```

---

## 6. Component-by-component implementation

### 6.1 Frontend — Next.js (arch §2.1)

- Chat screen with: mic button → audio upload; text box; animated avatar; video player pane; streak/badge strip.
- Only UI the child sees. Keep it big-button, colorful, low-cognitive-load.
- Video pane renders `<video controls autoplay>` with the URL from `/api/videos/{id}` (stream-by-reference).

### 6.2 API gateway — FastAPI (arch §2.2)

- Routes: `POST /api/chat` (text or audio multipart), `GET /api/videos/{id}`, `GET /api/health`.
- Middleware: session auth (child uses a low-privilege session), **rate limiting** (e.g. slowapi), request logging → parent reports.
- Note: the "gateway" and the "service workers" are the same FastAPI app in this build — every backend concern is a module, which keeps one deployable unit.

### 6.3 Multilingual layer (arch §2.3) — pivot = English

Flow: `audio → faster-whisper (text)`, then `text → fastText lid.176 (language)`, then `per-token lid + script heuristic (code-switch?)`, then `OPUS-MT mul-en (pivot to EN)`. Output side: take the final answer → `OPUS-MT en-mul (child's language)` → `Kokoro TTS (that language)`.

- If language detection confidence is low or input is English, **skip translation** — never degrade a short child sentence through a round-trip translator unless needed.
- Whisper model: use the **multilingual** `small` (not distil-whisper `.en` — distil is English-only and your code-switch case needs a multi script).
- Kokoro: `pip install kokoro misaki`; pick a warm voice (`af_heart`-style); for the child's language, use the matching Kokoro locale (Hindi supported). A truly *child* voice = fine-tuned voice pack (§12).

### 6.4 Input safety (arch §2.4)

- ShieldGemma classifier over: profanity, self-harm/distress, bullying, off-topic/adult, jailbreak, PII presence.
- Output of classifier = categories + severity. Map: **hard-block + escalate** (self-harm/abuse) vs **soft-tag** (ambiguous, continues but flagged) vs **pass**.
- Plus a small PII regex layer (name, phone, address, school) that redacts before any downstream call.
- Runs before orchestrator **and** again after LLM (output safety, §6.8).

### 6.5 Orchestrator — 3 agents (arch §2.5)

- `intent classifier` → routes to **learning agent** (direct questions), **recommendation agent** ("what should I do next" / idle), or **safety agent** (concerning → holds + escalates).
- Safety agent also runs **in parallel** on every turn and can interrupt the learning/recommendation agent mid-generation (implemented as a threaded watch that checks ShieldGemma on streaming partial output).

### 6.6 RAG + content ranking (arch §2.6) — the "best video" brain

1. **Query construction** — resolve anaphora ("what about *that one*?") using the last 2–3 turns.
2. **Embed** — bge-m3 via `FlagEmbedding` (dense 1024-d + sparse tokens).
3. **Search** — LanceDB: `table.search(q_emb).where("age_range=? AND safety=? AND lang=?", ...).limit(30)` (filter-before-retrieve — the catalog stays small, so hard filters first is correct; revisit if the catalog grows past ~100k rows).
4. **Rerank** — bge-reranker-base over survivors.
5. **Format & video selection** — score `relevance × quality × age_fit × duration_fit`; pick the **single best video** (`type=video`) when its score clears the bar; otherwise fall back to a text + quiz answer.
6. **LLM** — Gemma explains around the chosen video.

### 6.7 LLM — Ollama + Gemma (arch §2.6)

- `ollama pull` a Gemma model sized for the laptop: `gemma3:4b` (Q4). (Use the Gemma 4 equivalent tag if published; adjust only to a *smaller* model for very weak laptops.)
- One long-running prompt template encoding: Kiddo's persona, age band, pivot-English, and "use the provided retrieved context", plus **no-hallucination** and **call-for-parent** triggers.
- Keep the model version pinned (e.g. `@latest` tag in compose) so a UI change can never silently break answers.

### 6.8 Output safety (arch §2.6)

- ShieldGemma passes over the LLM answer (same classifier as input). Hard-block → fall back to a safe holding response; soft-flag → attach a parent-report entry in `safety_events`.

### 6.9 Video player + delivery (arch §2.7)

- **Never store video bytes.** `content_items` row = `url` (fastly/https source), `license`, `source`, `attribution`.
- Player = HTML5 `<video>` or embed for the source domain. Show attribution line (CC-BY requires crediting).
- Flow: answer chosen → `video.py` selects best URL → media returned with `video_url` → frontend plays it → avatar/voice (TTS) runs alongside → follow-up question or mini-game → next-step suggestion.

### 6.10 Companion persona, play layer, progression (arch §2.8–2.10)

- **Persona (2.8):** a `profile` table row holds friendship memory (name, favorites, pets, wins). Persona prompt injects these. Proactive nudges: a lightweight cron in the api mentions check-ins if the child is idle.
- **Play (2.9):** streaks/badges computed from `progress` table; mini-games = parameterized quiz templates delivered as UI routes.
- **Progression (2.10):** `skills` table links content → skill → skill graph; "mastery" requires a passing embedded check-in score, not just a view; recommendation agent reads the child's frontier skills for "next step."

### 6.11 Content ingestion (arch §3)

- **Collect:** fetchers for openly-licensed catalogs.
  - **Any use:** **Wikimedia Commons** (CC-BY / CC-BY-SA / public domain), **NASA** (US public-domain media, attribution required), **PhET** (CC-BY 4.0), OpenStax text.
  - **Embed-only** (free/non-commercial limits): **Khan Academy** (its content is generally **CC-BY-NC-SA** — non-commercial + share-alike), **CK-12** and **TED-Ed** (**CC-BY-NC**).
  - **Enforce at ingest:** verify the specific license on each asset, store it in `content_items.license`, and reject items that conflict with your use case. This field is a hard gate, not a label.
- **Process:** clean text; if video, save `transcript` (from the source's subtitles/transcript API; never rely on us transcribing uploaded media).
- **Safety + quality checks:** ShieldGemma on transcript + human eyeball.
- **Human approval gate:** new rows land in `content_items.status=review`; `review_cli.py` (or a tiny parent-dashboard admin page) flips them to `approved`. Nothing goes live before approval.
- **Embed:** bge-m3 → LanceDB; write `content_items` metadata to SQLite simultaneously (arch's "all three DBs at once" — in this build that's LanceDB vectors + SQLite metadata; the third "content DB" is the same SQLite row carrying the URL).

### 6.12 Parent system (arch §4)

- Next.js `/parent` behind **Auth.js** login.
- Views: progress (from `progress` + `profile`), controls (restricted topics → orchestrator config table), reports (weekly digest of watched items, quiz performance, `safety_events`).
- Ethics note: the child-facing app and parent area are separated; parents approve content, never spy mid-session in a way the child could notice.

---

## 7. Data model

**SQLite (`kiddo.db`)**

- `learners(id, name, age, language, parent_id, profile_json)` — profile_json = friendship memory + interests
- `parents(id, email, auth_id)`
- `content_items(id, type[video|text|game], title, url, transcript, language, age_range, difficulty, duration_s, skills, safety_tags, license, source, attribution, status[review|approved|rejected])`
- `progress(id, learner_id, item_id, watched_seconds, quiz_score, ts)`
- `skills(id, name, parents)` — the skill graph
- `content_skills(content_id, skill_id)`
- `config(learner_id, restricted_topics, screen_time_min, language)` — parent controls, read by orchestrator
- `safety_events(id, learner_id, event_type, severity, ts, handler)`
- `streaks(learner_id, current, best, last_active)` / `badges(learner_id, badge, earned_ts)`

**LanceDB (`vectors/`)**

- `content_vectors(content_item_id, embedding[1024], sparse_weights, lang, age_range, difficulty, safety_tags)` — searchable, filterable.

---

## 8. API surface

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | liveness |
| `/api/chat` | POST | main loop; body: `{text}` or `{audio}` (multipart). Returns `{answer, video_url?, audio_url?, quiz?, suggested_next}` |
| `/api/videos/{id}` | GET | stream-by-reference metadata (URL for player) |
| `/api/audio/{id}` | GET | cached Kokoro WAV (optional; can be returned inline) |
| `/api/profile` | GET/POST | child-facing profile (interests etc., cosy UI) |
| `/api/parent/*` | GET/POST | progress, controls, reports, approvals (auth). |
| `/api/ingest` | POST | ingester trigger (admin). |

---

## 9. Build plan — phases with definitions of done

| Phase | Ship this | Definition of done |
|---|---|---|
| 0 | Skeleton | `docker compose up` starts api + web; `/api/health` green; Ollama reachable |
| 1 | Text chat loop | Child types → Gemma answers with output safety; safe holding on block |
| 2 | RAG | Ask "why is the sky blue?" returns answer citing an ingested content item |
| 3 | **Video-first** | Question → best video selected → plays in in-app player; TTS voice explains |
| 4 | Input safety | Bad/jailbreak prompt → hard-block or soft-tag correctly |
| 5 | Voice I/O | Speech in → text; answer → spoken voice out |
| 6 | Multilingual | Hindi question → correct Hindi spoken answer (pivot EN internally) |
| 7 | Persona | Kiddo references the child's name/favorites; proactive greeting |
| 8 | Play + progress | Streak increments; badge on milestone; "next step" suggestion |
| 9 | Parent dashboard | Parent logs in; sees progress + reports; sets controls that take effect |
| 10 | Ingestion + approval | New approved content searchable same-day; review gate enforced |

---

## 10. Deployment & run (Docker Compose)

`docker-compose.yml` services:

- **`ollama`** — volume-mounts model cache; serves `gemma*` (+ optionally ShieldGemma). Exposes `:11434` internal.
- **`api`** — FastAPI; mounts `./data` (SQLite + LanceDB); env: model tags, paths.
- **`web`** — Next.js; `NEXT_PUBLIC_API_URL=http://api:8000`.
- **`ingester`** — one-shot / cron-triggered; needs `./data` too.
- Add one **volume** for `./data` so profiles survive restarts.

`ollama pull` once (or bake into a build step): `gemma3:4b` (+ `gemma3:270m` if RAM-constrained). Pin `@`-tags in compose so restarts never surprise.

**CPU tuning:** set `OLLAMA_NUM_THREADS` to physical cores; use quantized `Q4_K_M`; whisper INT8; keep one model resident and one context window small (1024–2048) to hold RAM. Expect answer latency of a few seconds — acceptable for a patient kid pacing.

---

## 11. Testing & verification (the "won't break" proof)

### 11.1 Unit
- Safety classifier: golden set of prompts → expected verdicts.
- Language detect: known short sentences per language.
- Translation round-trip: EN→HI→EN preserves meaning on 20 sample sentences.
- RAG: seeded catalog → assert top-1 for N known queries.
- Video selection: query with a strong video match returns video; with none, returns text fallback.

### 11.2 Integration
- One end-to-end: `POST /api/chat` with audio → assert `{answer, video_url, audio_url}` and that video URL is openly-licensed metadata + attribution.
- Rate limit triggers after N rapid calls.
- Parent login → fetch reports; set a restriction → orchestrator refuses that topic.

### 11.3 Kid-safe evaluation suite (`eval/`)
A scored checklist run before every release:
- 20 "why is ___" learning questions → all answered, all safe.
- 10 playful / fun requests → playful tone, play-layer response.
- 15 adversarial inputs (self-harm proxy, profanity, jailbreak, PII request, adult topic) → none reach the child unmasked; correct hard-block/soft-tag.
- Video correctness on 10 queries → right video family, age-appropriate.
- No third-party video bytes stored (assert on filesystem).
- Child-voice audio (a consented sample) → transcription correct, and if not, the text-input/dual-ASR fallback path engages cleanly.
- Every ingested asset carries a `license` value that passes a per-source allowlist check (NC sources flagged embed-only).

---

## 12. Risks & mitigations (the "won't break" section)

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Child speech accuracy** | Wrong/failed STT on kid voices | faster-whisper multilingual `small` as baseline. Open child-speech corpora are **scarce and often not freely licensed** (CMU Kids = paid LDC; no license-verified open alternative), so the realistic fix is a small **parent-consented child-audio set (50–200 clips) to fine-tune**, plus **dual-ASR voting** (add Vosk) and **LLM post-correction**. **Always** allow text input as fallback — the child UI must never dead-end on a speech miss |
| 2 | **Copyright from video ingestion** | Product cannot ship / DMCA | Stream-by-reference only; verify each asset's license at ingest and store it in `content_items.license`; keep NC sources embed-only; store transcript + metadata, never bytes; keep attribution |
| 3 | **Code-switched Hindi+English** | Translation breaks meaning | Pivot EN via `mul-en`; script heuristic for detection; skip translation when signal is weak; conversation context as hint |
| 4 | **Prompt injection / jailbreak** | Kid gets unsafe content | ShieldGemma BEFORE and AFTER; PII redaction; rate limiting; fallback holding response |
| 5 | **Model hallucination** | Wrong facts to kids | RAG-constrained generation; "answer only from retrieved context" prompt; human-approved content base |
| 6 | **Latency on CPU** | Unresponsive feel | Small quantized models; streaming tokens; beat-skipped TTS; caching audio answers |
| 7 | **Licence drift (OSS projects die/change)** | Broken stack | Pin versions in compose; Piper→Kokoro is exactly this lesson — note GPL trap of piper1-gpl |
| 8 | **Profile bloat** | Privacy creep / cost | Cap stored memory at N=200 facts/facts older than X; PII in memory is forbidden |
| 9 | **Escalation delay** | Harm scenario | `safety_events` written on hard-block immediately; parent email/webhook; child sees safe holding message + a trusted-adult prompt |

---

## 13. Open questions still to decide

- **Video relevance bar** (arch §6): the exact score cutoff for "good enough to play" vs text fallback — start strict, relax with catalog growth.
- **Gamification limits** per age band (arch §6): how much streak/badge pressure; define "gentle" concretely.
- **Companion depth** vs privacy (arch §6): cap on friendship memory; parent visibility.
- **Curriculum standards** for the skill graph (arch §6): align to a public syllabus (e.g. NCERT/Grade-level science) or stay internal.
- **Language startup set:** guarantee one pair first (English+Hindi), add others after.

---

## 14. Sources (licences verified 2026-09)

- faster-whisper (MIT): https://github.com/SYSTRAN/faster-whisper
- LanceDB (Apache-2.0, hybrid + metadata filters): https://github.com/lancedb/lancedb
- Kokoro TTS (Apache-2.0, multilingual incl. Hindi): https://github.com/hexgrad/kokoro
- Piper archived → piper1-gpl (GPL-3.0, excluded): https://github.com/rhasspy/piper , https://github.com/OHF-Voice/piper1-gpl
- bge-m3 embeddings (MIT, 100+ languages, hybrid): https://huggingface.co/BAAI/bge-m3
- Helsinki OPUS-MT (CC-BY 4.0): https://github.com/Helsinki-NLP/Opus-MT
- Gemma open models (free weights): https://deepmind.google/models/gemma
- ShieldGemma safety classifier (open weights): https://ai.google.dev/gemma/docs/shieldgemma
- fastText (BSD): https://github.com/facebookresearch/fastText
- Auth.js (MIT): https://authjs.dev
- CMU Kids = paid LDC corpus (LDC97S63): https://catalog.ldc.upenn.edu/LDC97S63
- PhET simulations (CC-BY 4.0): https://phet.colorado.edu/en/licensing
- NASA media policy (US public domain, attribution required): https://www.nasa.gov/nasa-brand-center/images-and-media/