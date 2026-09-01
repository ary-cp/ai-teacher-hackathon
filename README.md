# AI Teacher — a teacher, not a chatbot

Hackathon submission for **AI Innovation Hackathon 2026 — Round 2: "AI Teacher: Build a
Human-Like AI Educator"**.

The system takes a student's material (PDF / DOCX / PPTX) *or* a bare topic, understands the
learner, plans a lesson against their clock, teaches it with a speaking avatar and a
subject-aware blackboard, **stops to question them**, diagnoses *why* an answer was wrong,
re-teaches with a fresh analogy, and closes with a scored learning report.

```
UNDERSTAND → PLAN → EXPLAIN → QUESTION → EVALUATE → ADAPT → ASSESS → REPORT
```

---

## 1. Folder structure

```
ai-teacher/
├── backend/
│   ├── main.py                    FastAPI app: CORS, routers, health, error handling
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── config.py              env-driven settings (models, paths, chunking)
│   │   ├── schemas.py             the API contract (mirrored in frontend/lib/types.ts)
│   │   ├── rag_pipeline.py        parse → chunk → embed → Chroma → retrieve → cited context
│   │   ├── lesson_planner.py      UNDERSTAND + PLAN stages
│   │   ├── teaching_agent.py      the teaching loop / state machine
│   │   ├── tts.py                 Edge-TTS voice + word timings for lip-sync
│   │   ├── core/
│   │   │   ├── prompts.py         ★ all prompt engineering lives here
│   │   │   ├── llm.py             Groq (Llama-3.x) wrapper with JSON repair + retries
│   │   │   └── session_store.py   session state, per-concept mastery, learner memory
│   │   └── routers/
│   │       ├── upload.py          POST /api/upload
│   │       ├── lesson.py          POST /api/lesson/start
│   │       ├── teach.py           POST /api/teach/{next,answer,ask,language}
│   │       └── voice.py           POST /api/tts
│   └── data/                      chroma/, uploads/, audio/  (created on first run)
└── frontend/
    ├── app/{layout.tsx,page.tsx,globals.css}
    ├── components/
    │   ├── AvatarStage.tsx        canvas avatar, amplitude-driven lip-sync, video recorder
    │   ├── VisualBoard.tsx        KaTeX / Mermaid / code / table / timeline board
    │   ├── SetupPanel.tsx         upload + learner profile + instruction
    │   ├── PlanSidebar.tsx        live lesson plan with per-concept mastery
    │   ├── ChatPanel.tsx          conversation, MCQ buttons, verdict badges, citations
    │   ├── ReportCard.tsx         end-of-lesson learning report
    │   └── ui/                    Shadcn-style primitives
    ├── hooks/{useTeacher.ts,useSpeechAudio.ts}
    └── lib/{api.ts,types.ts,utils.ts}
```

---

## 2. Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

copy .env.example .env          # cp on macOS/Linux
# paste your free key from https://console.groq.com/keys into GROQ_API_KEY

uvicorn main:app --reload --port 8000
```

First run downloads the MiniLM embedding model (~90 MB) once, then works offline for embeddings.
Swagger UI: <http://localhost:8000/docs> · health: <http://localhost:8000/api/health>

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev            # http://localhost:3000
```

> The Shadcn primitives are already vendored in `components/ui`. If you prefer the CLI:
> `npx shadcn@latest init` then `npx shadcn@latest add button card input textarea badge progress`.

---

## 3. API

| Method | Route | What it does |
|---|---|---|
| POST | `/api/upload` | PDF/DOCX/PPTX/TXT → text → chunks → Chroma collection `doc_<id>` |
| GET | `/api/documents` | list ingested documents (pages, chunks, detected outline) |
| POST | `/api/lesson/start` | UNDERSTAND the brief → PLAN → returns `session_id`, lesson plan, intro turn (+audio) |
| POST | `/api/teach/next` | advance the state machine (intro → explain → question → …) |
| POST | `/api/teach/answer` | evaluate the student's answer, then **adapt** (advance or remediate) |
| POST | `/api/teach/ask` | student's doubt answered *without* losing lesson state |
| POST | `/api/teach/language` | switch teaching language mid-lesson, context preserved |
| GET | `/api/teach/{sid}/report` | scored learning report |
| GET | `/api/teach/{sid}/state` | live phase, mastery map, misconceptions |
| POST | `/api/tts` | standalone Edge-TTS: base64 mp3 + per-word timings |

Every teaching endpoint returns the same `TurnResponse`: `speech`, `board`, `question`,
`evaluation`, `audio` (base64 mp3 **plus word timings**), `progress`, `citations`.

---

## 4. Why this is not a chatbot

**One idea per turn.** The agent never emits the whole lesson. `word_budget = minutes × 135 × 0.75`
is injected into the prompt, so a 20-minute lesson genuinely sounds like a 20-minute lesson.

**It stops and asks.** After every concept the agent generates a question whose *type* rotates
(conceptual → MCQ → application → own-words → problem) and whose *difficulty* is a function of
live mastery. MCQ distractors are required to encode real misconceptions, not noise.

**It diagnoses instead of grading.** The evaluator returns a verdict, a score, the **gap**, and a
named **misconception** ("thinks current rises with resistance"). Meaning is judged, not wording —
an answer in Hinglish or broken English still counts as correct.

**The remediation ladder** (`REMEDIATE_PROMPT`) is the core differentiator:

| Attempt | Behaviour |
|---|---|
| 1 | Answer withheld. New analogy from an unused everyday domain. Simpler sub-question isolating the gap. |
| 2 | Answer still withheld. Broken into tiny steps; the student completes only the last one. |
| 3+ | Answer given, with an explicit "you thought X, actually Y", then an easy confirmation question so the student ends on a success. |

Used analogy domains are tracked per concept, so the teacher never repeats an analogy that
already failed.

**It adapts globally, not just locally.** `_adaptation_block()` injects live mastery into the next
explanation: below 45 % → slow down, shorter sentences, no new jargon; above 85 % → compress the
basics, add an edge case.

**Mastery is recency-weighted** (`1.4^i`) — a student who finally gets it is scored as someone who
gets it.

---

## 5. RAG / knowledge grounding

* **Parse** — PyMuPDF (per page), python-docx (headings + tables), python-pptx (slides + speaker
  notes). De-hyphenation and whitespace normalisation on the way in.
* **Outline extraction** — a regex pass finds "Chapter 4", "4.2 Ohm's Law", "अध्याय 3" and gives
  the planner a real table of contents, so "teach me chapter 4" targets chapter 4.
* **Chunk** — `RecursiveCharacterTextSplitter`, 1100/180, with `। ` in the separator list for Hindi.
* **Embed** — MiniLM locally (no embedding API cost, works offline).
* **Store** — one Chroma collection per document, metadata `{page, section, filename}`.
* **Retrieve** — the query is built from the *current step* (title + objective + key points +
  source hint), not from the raw chat message, so retrieval follows the lesson.
* **Anti-hallucination** — the context block ends with an explicit instruction: if the material
  doesn't cover it, say so in half a sentence and teach from first principles — never invent a
  citation. Page/section citations are returned to the UI and rendered as chips.

---

## 6. Voice, avatar and the teaching video

Edge-TTS is free and needs no key. Beyond the mp3, we keep the **WordBoundary** events it emits and
return them as `words[{word, start_ms, duration_ms}]`. That single extra field powers:

* **real lip-sync** — a WebAudio analyser measures live RMS amplitude of the playing voice and
  drives the avatar's mouth aperture frame by frame;
* **karaoke captions** — the current word is highlighted in the chat bubble;
* **video export** — `canvas.captureStream(30)` plus the TTS audio track goes into a
  `MediaRecorder`, so the whole lesson downloads as a `.webm` teaching video (record button on the
  avatar).

Voices are mapped per language (`hi-IN-SwaraNeural`, `bn-IN-TanishaaNeural`, `ta-IN-PallaviNeural`,
…14+ Indian and international languages).

---

## 7. Multilingual

Language is enforced in the persona block of *every* prompt, with an explicit definition of
Hinglish ("Hindi sentence structure in Roman script with English technical terms") because models
otherwise drift into pure Hindi. `POST /api/teach/language` switches mid-lesson while keeping the
plan, mastery map and transcript — and the document may be in a different language from the
teaching language, since retrieval is embedding-based, not keyword-based.

---

## 8. Third-party services disclosed

| Component | Service / model | Cost |
|---|---|---|
| LLM | Groq API — `llama-3.3-70b-versatile` (teaching), `llama-3.1-8b-instant` (evaluation/routing) | free tier |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, local CPU | free |
| Vector DB | ChromaDB, local persistence | free |
| TTS | Microsoft Edge-TTS | free, no key |
| Parsing | PyMuPDF, python-docx, python-pptx | OSS |
| Frontend | Next.js 14, Tailwind, Shadcn-style UI, KaTeX, Mermaid | OSS |

---

## 9. Known limitations

* Sessions are in-memory — restarting the backend clears them (swap `session_store` for Redis).
* Scanned PDFs need OCR; not wired up (add `pytesseract` in `rag_pipeline._parse_pdf`).
* The avatar is a canvas character, not a photoreal talking head; swap `AvatarStage` for D-ID /
  HeyGen if a photoreal avatar is required.
* Speech-to-text (student speaking their answer) is not wired; the browser's
  `SpeechRecognition` API drops into `ChatPanel` in ~20 lines.

---

## 10. Demo script (3–7 min)

1. Upload a textbook chapter → chunk/page counts and the detected outline appear.
2. "I am a beginner. Teach me Chapter 4 in 20 minutes in Hinglish." → lesson plan renders.
3. Teacher speaks with lip-sync, board shows a formula/diagram, citations show the source page.
4. It asks a question — **answer it wrong on purpose** → watch the misconception badge, the new
   analogy, and the simpler follow-up question.
5. Answer correctly → mastery bar moves, next concept begins.
6. Ask a doubt mid-lesson, then hit the `hindi` button → language switches, lesson continues.
7. Final quiz → learning report with strong/weak areas and what to revise.
8. Hit record on the avatar → download the lesson video.
