# Architecture

## 1. System diagram

```
 Next.js (App Router, Tailwind, Shadcn)
 ┌───────────────────────────────────────────────────────────┐
 │ SetupPanel   PlanSidebar   AvatarStage   VisualBoard      │
 │      │            │          │  ▲            ▲            │
 │      │            │   lip-sync  │  board spec │            │
 │      └────── useTeacher ────────┴─────────────┘            │
 │                   │  fetch (JSON, base64 mp3 + word timings)│
 └───────────────────┼───────────────────────────────────────┘
                     ▼
 FastAPI  ┌──────────────────────────────────────────────────┐
          │ /api/upload    → rag_pipeline.ingest             │
          │ /api/lesson/*  → lesson_planner (UNDERSTAND+PLAN)│
          │ /api/teach/*   → teaching_agent (the loop)       │
          │ /api/tts       → tts.synthesize                  │
          └───────┬───────────────┬──────────────┬───────────┘
                  ▼               ▼              ▼
             ChromaDB        Groq / Llama-3   Edge-TTS
          (MiniLM vectors)   (LangChain)      (neural voices)
```

## 2. The state machine

`teaching_agent.TeachingAgent` is stateless; all state hangs off `Session`.

```
              ┌──────────────── next() ────────────────┐
              ▼                                        │
 idle ─► intro ─► explain ─► question ─► [answer()] ─► evaluate ──► (next step)
                     ▲                        │                          │
                     │                        ▼  wrong                   │
                     └──────────── remediate ◄┘  (attempt 1,2,3+)        │
                                       │                                 │
                                       └── correct / attempt≥4 ──────────┘
                                                                          ▼
                                                        assessment ─► report ─► done
```

Transitions are decided server-side. The frontend only ever says
"advance" (`/next`), "here is my answer" (`/answer`) or "I have a doubt" (`/ask`) — so the
teaching policy can change without touching the UI.

### State carried per session

| Field | Purpose |
|---|---|
| `plan` | the LessonPlan being executed |
| `step_index`, `phase`, `attempt` | where we are in the loop |
| `concepts[step_id]` | attempts, score history, misconceptions, **used analogies** |
| `transcript` | continuity for the explainer and the doubt handler |
| `quiz`, `quiz_scores` | final assessment progress |

`ConceptState.mastery` is recency-weighted: `Σ score_i · 1.4^i / Σ 1.4^i`.

## 3. Prompt architecture (`app/core/prompts.py`)

| Prompt | Stage | Key constraint it enforces |
|---|---|---|
| `INTAKE_PROMPT` | Understand | free text → `{topic, level, language, minutes, goal, scope}` |
| `PLANNER_PROMPT` | Plan | time budgeting bands, dependency ordering, subject→visual mapping, grounding |
| `EXPLAIN_PROMPT` | Explain | hard word budget, exactly one analogy, board spec, no markdown in speech |
| `QUESTION_PROMPT` | Question | tests application not recall; MCQ distractors must encode misconceptions |
| `EVALUATE_PROMPT` | Evaluate | judge meaning not wording; name the misconception; withhold the answer |
| `REMEDIATE_PROMPT` | Adapt | the 3-rung ladder; forbidden to reuse an analogy domain |
| `DOUBT_PROMPT` | Interrupt | answer briefly, stay grounded, return to the lesson |
| `ASSESSMENT_PROMPT` | Assess | weights questions toward weak concepts |
| `REPORT_PROMPT` | Report | score, strong/weak, misconceptions, what to revise next |

All prompts share `PERSONA`, which pins learner card, language rule (with an explicit Hinglish
definition), level rule and the "this text will be spoken aloud" rule.

Templating uses `{{marker}}` + `prompts.render()` rather than f-strings, because every prompt
contains literal JSON braces.

## 4. Reliability choices for a live demo

* `llm.json_call` — JSON mode, fence stripping, trailing-comma repair, outermost-brace extraction,
  2 retries with a corrective message, then a caller-supplied fallback dict.
* `lesson_planner._fallback_plan` — the UI never shows a blank screen if the planner fails.
* `tts.safe_synthesize` — a TTS failure degrades to text-only, it never kills the turn.
* Plan minutes are rescaled to 85 % of the student's budget regardless of what the model returned.
* Every parsed field is clamped: enums validated, scores clamped to [0,1], list lengths capped.

## 5. Mapping to the evaluation criteria

| Criterion | Weight | Where it lives |
|---|---|---|
| Human-like teaching & adaptation | 20 | `teaching_agent.py` loop + `REMEDIATE_PROMPT` ladder + `_adaptation_block` + recency-weighted mastery |
| AI/ML & LLM implementation | 15 | dual-model Groq routing, structured JSON contracts, defensive parsing |
| RAG & knowledge grounding | 15 | `rag_pipeline.py`: per-doc collections, outline extraction, page/section citations, anti-hallucination clause |
| AI teaching video | 15 | `AvatarStage` canvas + board + `MediaRecorder` export |
| Multilingual | 10 | persona language rule, 14+ voice map, `/api/teach/language` mid-lesson switch |
| Voice & avatar | 10 | Edge-TTS + word timings → amplitude lip-sync + karaoke captions |
| Innovation | 5 | word-timing-driven lip-sync, misconception tracking, analogy-domain memory |
| UX | 5 | plan sidebar with live mastery, MCQ buttons, citation chips, replay |
| Documentation | 5 | this file + README |

## 6. Extension points

* **Speech-to-text**: wire `webkitSpeechRecognition` into `ChatPanel` → `onAnswer`.
* **Photoreal avatar**: replace `AvatarStage`'s canvas with a D-ID/HeyGen stream; keep the
  amplitude hook so the rest of the UI is unchanged.
* **Persistence**: `session_store._SESSIONS` → Redis; `_LEARNER_MEMORY` → Postgres for
  cross-session learner memory.
* **Server-side MP4**: `/api/tts/stream` returns raw mp3; pair it with headless-Chrome frames and
  ffmpeg for an MP4 render pipeline.
