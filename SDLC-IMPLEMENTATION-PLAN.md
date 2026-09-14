# Kiddo Assist — SDLC Phased Implementation Plan

**Status:** ✅ Approved — this is the delivery roadmap for building the entire Kiddo Assist product.
**Governance:** The four source docs are the authority. This plan is the execution order. If this plan disagrees with the source docs, the source docs win; if the source docs disagree with the source-of-truth file, the source-of-truth file wins.

---

## 1. Purpose

This document is the **single execution reference** for building **Kiddo Assist** — a voice-first, video-first friend AI for children that fetches the best video from its own knowledge base and plays it on-platform, speaks always, is safe by construction, and guides learning growth.

It follows the **SDLC** and is sized so that **each phase completes in one Claude Code iteration**, with a review pause between iterations.

**Document chain (dependency order):**

```
an agent for the children(kids) for.txt   ← source of truth (what / why)
        │
        ▼
kiddo-architecture.md                     ← system design (how it is shaped)
        │
        ▼
IMPLEMENTATION-GUIDE.md                   ← build book (how it is built, with which tools)
        │
        ▼
WORKFLOW.md                               ← operating + delivery workflows (how it runs)
        │
        ▼
SDLC-IMPLEMENTATION-PLAN.md (this file)   ← execution order (what we do, in what order)
```

---

## 2. How SDLC maps to this project

The docs set already completes the first two SDLC stages. Everything after is executed as gated iterations, with testing structurally embedded (per-iteration tests + a recurring release gate).

| SDLC stage | Status | Deliverable / source |
|---|---|---|
| **Requirements & Analysis** | Done | `an agent for the children(kids) for.txt` (SOT); `WORKFLOW.md` §0 normalizes it into requirement inventory **SOT-01…16**; §1–2 are the traceability matrix verifying the other docs against it |
| **Design** | Done | `kiddo-architecture.md` — system design; `IMPLEMENTATION-GUIDE.md` §1–8 — locked decisions, monorepo layout, data model, API surface; `WORKFLOW.md` §10–11 — API contract + frontend wireframe |
| **Implementation** | This plan | Iterations 0–16 |
| **Testing** | This plan | Per-iteration unit/integration tests (guide §11.1–11.2) + `eval/` suite (guide §11.3, WORKFLOW §13) built at Iteration 6, used as the recurring release gate thereafter |
| **Deployment** | This plan | Iteration 17 — compose polish, volume persistence, CPU tuning, README, final doc pass (guide §10 is the spec) |
| **Maintenance** | This plan | Ongoing: license-drift re-checks, pinned model tags, re-run `make eval` on any change, content-gap backlog, child-speech fine-tune backlog |

**Each iteration is a mini-SDLC:** plan → build → test (against that iteration's definition-of-done) → verify/retro.

---

## 3. Locked decisions (do not re-open)

| Decision | Choice | Source |
|---|---|---|
| Product / persona name | **Kiddo Assist** | `WORKFLOW.md` §14.1 |
| Pivot language | **English** (answers + voice back in the child's language) | `kiddo-architecture.md` Appendix A |
| Video hosting | **Stream-by-reference, never rehost video bytes** | `WORKFLOW.md` §14.1 |
| Runtime | Local OSS, **CPU-capable, $0/month** services | `IMPLEMENTATION-GUIDE.md` §1 |
| Filter order | **Filter-before-retrieve** while catalog is small | Guide §6.6 |
| Safety | **Classifier in-path** (in, during, out, at ingest); hard-block vs soft-tag | Guide §0.3 |
| Escalation | `safety_events` immediately + parent notify + child hears holding words | `WORKFLOW.md` §14.1 |
| Always-speak | After the voice iteration, every child-visible turn has TTS | `WORKFLOW.md` §14.1 |
| Best videos | Play top-1 in-app **and** return ranked `suggested_videos[]` | `WORKFLOW.md` §14.1 |
| Tutorials | First-class `tutorial` type with ordered steps | `WORKFLOW.md` §14.1 |
| Content types | `video \| tutorial \| source \| game` | `WORKFLOW.md` §6.1 |
| Product definition | **Kiddo Assist is not Kiddo Assist until Phase 3 (video-first) is done** | `WORKFLOW.md` §12 |

---

## 4. The core loop (never lose sight of it)

```
Child speaks to Kiddo Assist
        ↓
Kiddo Assist understands (safely)
        ↓
Fetch the best matching video from the knowledge base
        ↓
Display / play that video on this platform
        ↓
Kiddo Assist speaks around it — as a friend, as a guide
```

If a phase, API response, or UI cannot do this loop, it is not Kiddo Assist yet.

---

## 5. Repo layout (root-as-monorepo)

Repo root = `C:\Users\raghava\OneDrive\Desktop\new-project\` (holds the four docs + the code tree below). Confirmed once in Iteration 0.

```
new-project/
├─ docker-compose.yml              # ollama / api / web / ingester (+ data volume)
├─ .env.example
├─ README.md                       # run + demo instructions (final, Iteration 17)
├─ SDLC-IMPLEMENTATION-PLAN.md     # this file
├─ services/
│  ├─ api/                         # FastAPI gateway + all service workers
│  │  ├─ main.py                   # routes: /api/chat, /api/videos/{id}, /api/audio/{id}, /api/profile, /api/parent/*, /api/ingest, /api/health
│  │  ├─ config.py                 # env + model paths + ASSISTANT_NAME = "Kiddo Assist"
│  │  ├─ db.py                     # SQLite + LanceDB access
│  │  ├─ stt.py                    # faster-whisper
│  │  ├─ detect.py                 # fastText lid + code-switch (EXT-02)
│  │  ├─ translate.py              # OPUS-MT pivot (EXT-02)
│  │  ├─ safety.py                 # ShieldGemma in/out + PII redaction
│  │  ├─ orchestrator.py           # intent classifier + 3 agents
│  │  ├─ rag.py                    # bge-m3 embed + LanceDB search + rerank
│  │  ├─ llm.py                    # Ollama client (Gemma)
│  │  ├─ tts.py                    # Kokoro
│  │  ├─ video.py                  # video selection + stream-by-reference
│  │  ├─ persona.py                # companion memory (Phase 7)
│  │  ├─ play.py                   # streaks/badges/games (Phase 8)
│  │  ├─ progress.py               # skill graph / mastery (Phase 8)
│  │  └─ requirements.txt
│  ├─ ingester/                    # offline content pipeline
│  │  ├─ collect.py                # Wikimedia/NASA/PhET/OpenStax fetchers
│  │  ├─ process.py                # clean + transcript extraction
│  │  ├─ check.py                  # license + completeness + safety + quality gates
│  │  ├─ embed.py                  # bge-m3 → LanceDB + SQLite
│  │  ├─ seed.py                   # dev seeder (dev shortcut; full gate later)
│  │  ├─ review_cli.py             # human approval gate
│  │  └─ requirements.txt
│  └─ web/                         # Next.js frontend + parent dashboard
│     ├─ app/
│     │  ├─ layout.tsx
│     │  ├─ page.tsx               # "Kiddo Assist"
│     │  ├─ chat/page.tsx          # child UI: mic, avatar, video player, suggestions
│     │  └─ parent/                # dashboard (auth required, EXT-01)
├─ data/                           # kiddo.db, vectors/, audio/, model cache, .gitkeep
├─ eval/                           # kid-safe evaluation suite (§11.3)
│  └─ questions/*.json
└─ tests/                          # pytest (unit + integration)
```

---

## 6. The iteration list (0–17)

Every iteration ships against its **definition of done** below — that gate is what "done" means for that iteration.

### Iteration 0 — Bootstrap skeleton + doc-correction pass (Phase 0)
- **Goal:** Bootable monorepo (`docker compose up` runs api + web, health green, Ollama serves Gemma) **and** the WORKFLOW §15 doc corrections applied first.
- **Build:**
  - **Doc-correction pass** (`kiddo-architecture.md` + `IMPLEMENTATION-GUIDE.md`): rename product/persona → **Kiddo Assist** everywhere; add the core-loop sentence atop both docs; `tutorial` as first-class content type + completeness gate; chat API returns `suggested_videos[]` + `video_url`; mark parent dashboard and multilingual as **extensions**; close §6/§13 open questions already locked (pivot=English, filter-before-retrieve, escalation path).
  - `docker-compose.yml` — services `ollama`, `api`, `web`; named volume for `data/`; env `OLLAMA_NUM_THREADS`; pinned Gemma `@`-tag; web env `NEXT_PUBLIC_API_URL=http://api:8000`.
  - `.env.example`.
  - `services/api/main.py` — FastAPI `GET /api/health` returning `{status, ollama:"up|down"}` (pings Ollama `/api/tags`), CORS for web.
  - `services/api/config.py` — env + paths + `ASSISTANT_NAME = "Kiddo Assist"`.
  - `services/api/requirements.txt`.
  - `services/web/` — minimal Next.js App Router (`app/layout.tsx`, `app/page.tsx` titling "Kiddo Assist").
  - `data/.gitkeep`.
- **Definition of done (guide §9 Phase 0):** `docker compose up` starts api + web; `GET /api/health` green; `ollama list` shows a Gemma model; web page loads; doc corrections applied.
- **Close (verify):** compose up → curl `/api/health` → curl Ollama `:11434/api/tags` → load web page → retro (note Windows/WSL2 path caveats for volume mounts).
- ⚠️ Kernel: `ollama pull gemma3:4b` first so the model is resident before Iteration 2.

### Iteration 1 — Knowledge-base data layer + dev seed catalog
- **Goal:** KB schema, vector store, and a small approved dev catalog so RAG + video iterations have data to retrieve.
- **Build:** `services/api/db.py` (all SQLite tables per guide §7; `content_items.type = video|tutorial|source|game` with `tutorial_steps` JSON column; LanceDB `data/vectors`); `services/ingester/seed.py` (idempotent dev seeder: ~15 `approved` items — 3 sources, 2 tutorials w/ ordered steps, 6 videos w/ transcript/license/attribution/duration_s, 2 games; bge-m3 embeddings for text + transcripts).
- **Definition of done:** `seed.py` runs twice (idempotent, same counts); LanceDB hybrid search over a seeded transcript returns hits; `tutorial` in type domain; all seeded rows `approved` (dev shortcut — the review gate is Iterations 15–16).
- **Close (verify):** run seed → spot-check SQLite + LanceDB → `tests/test_db.py` (schema, type domain, seeded-approved searchable).

### Iteration 2 — Text chat loop + output safety (Phase 1)
- **Goal:** Child types → Kiddo Assist (Gemma via Ollama) answers, output screened, holding line on block.
- **Build:** `services/api/llm.py` (Ollama client, pinned Gemma tag, persona + age prompt template); `services/api/safety.py` **output** path (ShieldGemma classify answer → hard-block holding line + `safety_events` row / soft-tag / pass; PII regex redaction stub); `services/api/main.py` — `POST /api/chat` (`{text, learner_id}`) returning the **WORKFLOW §10 contract skeleton**: `{assistant_name:"Kiddo Assist", answer, audio_url:null, video_url:null, video:null, suggested_videos:[], tutorial:null, quiz:null, suggested_next:null, safety:{verdict}}`.
- **Definition of done (guide §9 Phase 1):** `POST /api/chat {text:"Why is the sky blue?"}` → non-empty answer, `safety.verdict:"pass"`; crafted harmful output blocked with holding line; `assistant_name == "Kiddo Assist"`.
- ⚠️ Kick off ShieldGemma download at session start.

### Iteration 3 — RAG (Phase 2)
- **Goal:** Answers ground in approved KB content instead of raw model memory.
- **Build:** `services/api/rag.py` — `embed()` (bge-m3 dense+sparse), `search(query, filters)` with **filter-before-retrieve** (status=approved, age_range, lang, safety_tags, duration cap; guide §6.6) → LanceDB hybrid limit(30) → bge-reranker-base → top chunks; `services/api/orchestrator.py` first cut (learning → RAG → LLM, "answer only from retrieved context" anti-hallucination).
- **Definition of done (guide §9 Phase 2):** "why is the sky blue?" returns an answer grounded in a seeded source/transcript (assert the source id/attribution appears in the answer or metadata).

### Iteration 4 — Video-first core: selection, in-app player, suggested_videos (Phase 3, part A) 🔶 **FIRST PRODUCT DEMO**
- **Goal:** Best video selected, streamed by reference, plays in-app, with 2–4 ranked suggestions.
- **Build:** `services/api/video.py` — scoring `relevance × quality × age_fit × duration_fit × completeness` (WORKFLOW §6.3); pick best video (type=video **or** tutorial step) if ≥ strict `VIDEO_BAR`, else text fallback; build `suggested_videos[]` (next 2–4, each with `reason`). `main.py` response builder returns `video_url`, `video{id,title,attribution,license,duration_s}`, `suggested_videos[]`, `tutorial{step,total_steps}`; add `GET /api/videos/{id}` (metadata + stream-by-reference URL — never proxy bytes). `services/web/app/chat/page.tsx` — in-app `<video controls autoplay>`, suggestion chips (tap → plays here), attribution under player; type box wired now (mic arrives in Iteration 8).
- **Definition of done (WORKFLOW §12 phase-3 gate + §12.1 6-step demo):** type "why is the sky blue?" → relevant approved video starts **on this platform**; 2–4 `suggested_videos` render; URL is licensed stream-by-reference with attribution; **filesystem scan proves no third-party video bytes stored**.
- **Close (verify):** `tests/test_video.py` (strong match → video; none → text fallback); integration `POST /api/chat` asserts `{video_url, suggested_videos[2..4], video.license}`; `tests/test_no_bytes.py`.

### Iteration 5 — TTS voice alongside the video (Phase 3, part B)
- **Goal:** Kiddo Assist speaks the short explanation while the video plays — completing the phase-3 product definition.
- **Build:** `services/api/tts.py` — Kokoro `synthesize(text, lang) -> WAV`, cached at `data/audio/{hash}.wav`, warm voice (`af_heart`-style). `main.py` returns + serves `audio_url`; `GET /api/audio/{id}` serves cached WAV. Web chat plays audio after the turn renders; captions as support.
- **Definition of done (guide §9 Phase 3 + WORKFLOW §12.1 step 3):** full §12.1 checklist passes — incl. "Hear Kiddo Assist speak a short explanation". **Phase 3 closed: the product is now demonstrably Kiddo Assist.**
- ⚠️ Browser autoplay policy: audio fires from the submit-click gesture.

### Iteration 6 — Eval suite + release gate (the recurring gate)
- **Goal:** A scored, machine-checkable release gate every later iteration closes against.
- **Build:** `eval/run_eval.py` implementing guide §11.3 — 20 "why" questions answered + safe; 10 playful requests → playful/safe/in-app; 15 adversarial inputs (self-harm proxy, profanity, jailbreak, PII, adult) → correct hard-block/soft-tag; video-family correctness on 10 queries; no-bytes filesystem assert; per-asset license allowlist check; child-voice/STT-fallback hook. `eval/questions/*.json`. Consolidated `tests/` (safety golden set, RAG top-1, video selection, chat flow). `make eval`.
- **Definition of done:** `make eval` green on the current build, prints per-check scores; every **subsequent** iteration ends with `make eval`.

### Iteration 7 — Input safety (Phase 4)
- **Goal:** Harmful/jailbreak/PII input hard-blocked or soft-tagged before it reaches the orchestrator.
- **Build:** Extend `services/api/safety.py` — **input** classifier (ShieldGemma) over profanity, self-harm/distress, bullying, off-topic/adult, jailbreak, PII; severity map: **hard** (self-harm/abuse/adult) → stop + `safety_events` + holding words + parent alert; **soft** → tag and continue; PII regex redaction before any downstream call; intent-classification stub (learning/play/recommendation/concerning). `main.py` — input safety before orchestrator on every chat; hard-block short-circuits.
- **Definition of done (guide §9 Phase 4):** jailbreak refused in kid language + real learning path; self-harm proxy → hard-block + `safety_events` + holding words; PII redacted, never echoed in answer or logs.

### Iteration 8 — Voice input: STT + mic + speech-miss fallback (Phase 5, part A)
- **Goal:** Speech in; the text fallback never dead-ends.
- **Build:** `services/api/stt.py` — faster-whisper multilingual `small`, INT8. `main.py` — `POST /api/chat` accepts multipart `{audio}`; transcribe → same pipeline as text. Web — **BIG MIC** (MediaRecorder → upload) + **TAP TO TYPE** always visible; low-confidence transcript → Kiddo's speech-miss line (§5.4: "I didn't catch that — want to tap it for me?").
- **Definition of done (guide §9 Phase 5 core):** mic → transcript → answer; low-confidence → miss path with working type box; **UI never dead-ends on a speech miss**.

### Iteration 9 — "Always speaks" invariant + speech repair (Phase 5, part B)
- **Goal:** Every child-visible turn produces a spoken line; silence becomes a test failure.
- **Build:** Wire TTS (Iteration 5) into **every** turn (greeting, answer, video-alongside, check-in, speech-miss apologetics — WORKFLOW §8.1). Dual-ASR / LLM post-correction hook (Vosk voter stub) inside `stt.py` as the documented repair path (guide §12 r1). Add the **always-speaks invariant** to `eval/run_eval.py`: every non-blocked chat response must carry a non-null, fetchable `audio_url` (hard-block responses exempt — they carry holding words instead).
- **Definition of done (WORKFLOW §12 phase-5 gate):** speech in → speech out every turn (eval green); captions are support; "silence is a bug". **Phase 5 closed.**

### Iteration 10 — Multilingual: Hindi in/out via English pivot (Phase 6; extension EXT-02)
- **Goal:** Hindi question → correct Hindi spoken answer, pivoting through English internally.
- **Build:** `services/api/detect.py` — fastText `lid.176` + code-switch (per-token lid + Devanagari/Latin script heuristic, guide §6.3). `services/api/translate.py` — OPUS-MT `mul-en` / `en-mul`; **skip translation when English/low confidence**. `tts.py` — Kokoro Hindi locale. `main.py` — STT/text → detect → pivot EN → safety → orchestrator → answer → back-translate → Hindi TTS; `learner.language` drives outbound language. **Label the module EXT-02**.
- **Definition of done (guide §9 Phase 6):** Hindi question → correct Hindi spoken answer; EN→HI→EN round-trip preserves meaning on 20 samples.
- ⚠️ Start OPUS-MT download at session start.

### Iteration 11 — Persona & friendship memory (Phase 7)
- **Goal:** Kiddo is a friend, not a search box — uses the child's name/favorites and speaks first.
- **Build:** `services/api/persona.py` — friendship memory on `learners.profile_json` (cap ~200 facts, **no PII**); inject into `llm.py` prompt; embed `ASSISTANT_NAME`/name check; ASGI lifespan idle check-in cron (proactive greeting/nudge, never nags, §5.2); name in web UI + spoken intro.
- **Definition of done (guide §9 Phase 7):** Kiddo references the child's name + a remembered favorite; new learner session starts with a proactive greeting; memory contains no PII.

### Iteration 12 — Progress, mastery, tutorial step-through (Phase 8, part A)
- **Goal:** Growth is real and measured: watched ≠ understood; tutorials step forward.
- **Build:** `services/api/progress.py` — progress rows (`watched_seconds`, `quiz_score`), `skills` skill-graph + `content_skills`; **mastery requires a passing embedded check-in**, not a view (guide §6.10). Orchestrator — thin recommendation agent reading frontier skills, preferring the next step of an in-progress tutorial; chat `tutorial{step,total_steps}` + `suggested_next` live; small quiz/check-in returned on `quiz` for tutorial steps.
- **Definition of done:** a completed tutorial progresses `step`; mastery only after passing check-in; `suggested_next` from frontier skills.

### Iteration 13 — Play layer: streaks, badges, mini-games (Phase 8, part B)
- **Goal:** Playful learning designed-in, gentle, forgiving.
- **Build:** `services/api/play.py` — streaks (**forgiving**: missed day ≠ wipe), badges on effort/milestones; quiz-as-game (parameterized match/quiz templates served in-app; the fact is in the play). Web — streak/badge strip on chat screen; play beat after video/step (§8.2).
- **Definition of done (guide §9 Phase 8):** streak survives one missed day; badge on milestone; "let's play" returns an in-app game that teaches. **Phase 8 complete.**

### Iteration 14 — Parent dashboard (Phase 9; extension EXT-01)
- **Goal:** Parent logs in, sees progress/reports, sets controls that change the next child turn.
- **Build:** Web — Auth.js (NextAuth v5) on `services/web/app/parent/*` (login, dashboard: progress/watched/quiz; controls: `restricted_topics`, `screen_time_min`, `language`; reports: weekly digest + `safety_events`; content approval-queue view). API — `/api/parent/*` (GET progress/reports; POST controls → upsert `config` row; orchestrator reads `config` at session start). **Label all parent surfaces EXT-01**; honor the ethics rule (child app and parent area are separate surfaces).
- **Definition of done (guide §9 Phase 9):** parent logs in; posts a restricted topic; the **next child turn refuses that topic**; reports show watched items, quiz scores, safety flags.

### Iteration 15 — Ingestion pipeline: collector + gates (Phase 10, part A)
- **Goal:** Offline pipeline pulls openly-licensed sources and runs license + completeness + safety gates before anything goes live.
- **Build:** `services/ingester/collect.py` (Wikimedia Commons, NASA, PhET, OpenStax fetchers — each tagged license + attribution); `process.py` (clean/chunk text; transcripts from source subtitles only — never transcribe downloaded bytes); `check.py` gates per WORKFLOW §6.2 — **license allowlist** (NC → embed-only, unknown → reject), **completeness** (video: transcript+attribution+topic; tutorial: ordered steps + goal + check; source: full work or labeled excerpt → else `incomplete`/not searchable), ShieldGemma on transcript/text, quality/pedagogy; `embed.py` → bge-m3 → LanceDB + SQLite row at **`status=review`**.
- **Definition of done:** NC asset can't get a playable URL; orphan clip quarantined `incomplete`; rows land `review`, never `approved`; **no video bytes stored at any stage**.

### Iteration 16 — Ingestion: human approval gate + go-live (Phase 10, part B — LAST BUILD ITERATION)
- **Goal:** A human flips `review → approved`; the item is searchable same-day; nothing is ever live before approval.
- **Build:** `services/ingester/review_cli.py` (interactive queue: list `status=review`, approve/reject — reject logs to `safety_events`); `POST /api/ingest` (admin) trigger; optional parent-dashboard approval view (read-only). Same-day search works because Iteration 3's filter already requires `status=approved`.
- **Definition of done (guide §9 Phase 10):** approve a fresh ingested item → the next `/api/chat` knows it; the review gate is enforced ("nothing goes live before approval"); reject path logs to `safety_events`. **Phase 10 complete — the full build is done.**

### Iteration 17 — Deployment, polish, doc-correction check (final)
- **Goal:** Ship-readiness and the final documentation pass.
- **Build:** Finalize `docker-compose.yml` per guide §10 — named volume for `./data` (profiles survive restart), pinned `@`-tags, `OLLAMA_NUM_THREADS` = physical cores, Q4_K_M, INT8 whisper, one resident model + context 1024–2048; README with run + demo instructions; `.env.example` final; **final §15 doc-correction check** (architecture + implementation docs match WORKFLOW §15 item-by-item). Run functional + full `make eval` gate.
- **Definition of done:** fresh-machine `docker compose up` reaches a working chat→video→voice demo from the README; `make eval` green; docs match §15 checklist. **Delivery.**

---

## 7. Recurring release gate (from Iteration 6 onward)

No iteration is "done" until:
1. Its own unit/integration tests pass.
2. `make eval` passes — including **all previously-added checks** (adversarial set, video-family, no-bytes, license allowlist, **voice-always invariant** from Iteration 9).
3. A short retro records what changed + what the next session must carry forward.

This enforces the SDLC "Testing" stage structurally rather than deferring it.

---

## 8. Critical path → first real product demo

```
It 0 (skeleton + doc corrections)
   ↓
It 1 (KB data + seed) ──┐  (1 & 2 are independent;
It 2 (text chat + o-safety)┘   both must precede 3)
   ↓
It 3 (RAG)
   ↓
It 4 (video-first core) ───┐ Phase 3 — FIRST honest demo
   ↓                        │ (WORKFLOW §12)
It 5 (TTS voice alongside)──┘
```

**Six iterations (0 → 1 → 2 → 3 → 4 → 5)** reach a demoable Kiddo Assist (five if 1 & 2 run concurrently). Nothing in Iterations 7–16 may jump this path: *"a parent dashboard without in-app relevant video is not this product."* Voice-always (SOT-15 invariant) lands at Iteration 9 and is enforced by the eval gate forever after.

---

## 9. Risks & attention points (tracked from guide §12 + WORKFLOW)

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | Model downloads + RAM (~25 GB total) | Session/run stalls | Pre-pull each iteration's model at session start; one resident model; small context (1024–2048); pinned `@`-tags; heaviest iterations (2, 4, 8, 10, 15) stage downloads to run in the background |
| 2 | Child-speech accuracy (guide §12 r1) | Wrong/failed STT on kid voices | faster-whisper `small` baseline; always-visible text fallback (It 8); dual-ASR/LLM repair hook (It 9); UI must never dead-end on a speech miss |
| 3 | Copyright from video ingestion (guide §12 r2) | Product cannot ship / DMCA | Stream-by-reference only; license on every row; NC = embed-only; eval asserts no video bytes on disk |
| 4 | Wrong-video = SOT-06 failure (WORKFLOW §6.3) | Kid gets irrelevant content | Keep `VIDEO_BAR` strict; prefer speaking + content-gap log over a wrong clip; never invent a URL |
| 5 | Always-speaks vs hard-block | Unclear invariant | Voice invariant exempts hard-block turns (holding words replace voice) |
| 6 | Browser autoplay policy (It 5/9) | Voice-out blocked | Audio fires from the submit-click gesture |
| 7 | Safety = classifier in-path, not a prompt (guide §0.3) | Unsafe content reaches child | ShieldGemma in (It 7), during generation (parallel watchdog can interrupt stream), out (It 2), and at ingest (It 15); escalation closed: `safety_events` + parent notify + holding words |
| 8 | §15 doc corrections are load-bearing | Downstream breakage | Landed from Iteration 0: `tutorial` type (It 1), `suggested_videos[]` (It 4), extensions labeled (It 10/14), invariant (It 9), final doc check (It 17) |
| 9 | Windows host boundary | Compose volume/env issues | Docker Desktop/WSL2 path handling resolved in Iteration 0 |
| 10 | Iteration-size integrity | A session stretches across two phases | Slim iterations (5, 9, 12, 13) kept deliberately small; heaviest iterations keep UI/backend slice minimal |

---

## 10. Testing strategy summary

- **Unit (guide §11.1):** safety golden set; language detect; translation round-trip (20); RAG top-1 for N queries; video vs text fallback.
- **Integration (guide §11.2):** `POST /api/chat` (audio) → `{answer, video_url, suggested_videos, audio_url}`; rate limiting; parent restriction takes effect on the next child turn.
- **Kid-safe eval suite (`eval/`, guide §11.3):** scored checklist run before every release — learning, play, adversarial, video family, no stored video bytes, license allowlist, child-voice fallback.
- **Always-speaks invariant (It 9):** every non-blocked response carries a fetchable `audio_url`.

---

## 11. Operations cheat-sheet (from WORKFLOW §16)

**Who:** children. **Who talks:** Kiddo Assist, always. **What happens after the child speaks:** fetch from knowledge base. **What they see:** the video on this platform. **Which video:** the best relevant one, with other best videos suggested. **What the library holds:** complete sources and complete tutorials, not scraps. **How it feels:** friend, guide, playful, growing. **What it never is:** harmful, silent, off-platform, a random clip.

*That is the whole product. Everything else is scaffolding.*