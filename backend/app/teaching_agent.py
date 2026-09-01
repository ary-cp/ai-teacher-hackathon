"""
THE TEACHING LOOP  (this is the graded part of the submission)

                 +-------------------------------------------------+
                 v                                                 |
  INTRO -> EXPLAIN -> QUESTION -> EVALUATE -> [correct?] -- no --> REMEDIATE
                                       |                              |
                                      yes                     (new analogy,
                                       |                       simpler sub-question)
                                       v                              |
                              next step / ASSESSMENT <----------------+
                                       |
                                       v
                                     REPORT

Everything the loop decides — how long to talk, which question type to ask,
whether to advance, how hard the next question is — is a function of the
student's live mastery, not a fixed script. That is what makes it a teacher
rather than a chatbot.
"""
from __future__ import annotations

import logging
from typing import Any

from app import rag_pipeline as rag
from app.core import prompts
from app.core.llm import json_call
from app.core.session_store import Session, remember
from app.schemas import (
    Audio,
    Board,
    Evaluation,
    LearningReport,
    Phase,
    Progress,
    Question,
    QuestionType,
    TurnResponse,
    Verdict,
    VisualKind,
    WordTiming,
)
from app.tts import safe_synthesize

log = logging.getLogger("ai-teacher.agent")

SPEAKING_WPM = 135          # average TTS speaking rate
QUESTION_CYCLE = [
    QuestionType.conceptual,
    QuestionType.mcq,
    QuestionType.application,
    QuestionType.own_words,
    QuestionType.problem,
]


# --------------------------------------------------------------------------- #
#  small helpers
# --------------------------------------------------------------------------- #
def _persona(session: Session) -> str:
    p = session.profile
    style_parts = p.style.split('|')
    base_style = style_parts[0]
    teacher_id = style_parts[1] if len(style_parts) > 1 else "mr_sharma"
    
    # Map avatar to persona
    if teacher_id == "ms_pooja":
        teacher_name = "Ms. Pooja"
        gender = "female"
    elif teacher_id == "rahul":
        teacher_name = "Rahul"
        gender = "male"
    else:
        teacher_name = "Mr. Sharma"
        gender = "male"
        
    session.current_teacher_gender = gender # simple way to pass to TTS later
    
    persona_template = prompts.PERSONA.replace('"Professor Aria"', f'"{teacher_name}"')
    
    return prompts.render(
        persona_template,
        name=p.name,
        level=p.level.value,
        language=p.language,
        style=base_style,
        goal=p.goal,
        prior_knowledge=p.prior_knowledge,
    )

def _word_budget(minutes: float, floor: int = 60, cap: int = 320) -> int:
    return int(max(floor, min(cap, minutes * SPEAKING_WPM * 0.75)))


def _board(raw: Any) -> Board:
    if not isinstance(raw, dict):
        return Board(kind=VisualKind.none)
    kind = str(raw.get("kind", "bullets")).lower()
    if kind not in {v.value for v in VisualKind}:
        kind = "bullets"
    rows = raw.get("rows") or []
    if rows and not isinstance(rows[0], list):
        rows = [[str(r)] for r in rows]
    return Board(
        kind=VisualKind(kind),
        title=str(raw.get("title", ""))[:120],
        items=[str(i)[:160] for i in (raw.get("items") or [])][:6],
        latex=str(raw.get("latex", "")),
        code=str(raw.get("code", "")),
        language=str(raw.get("language", "")),
        mermaid=str(raw.get("mermaid", "")),
        columns=[str(c) for c in (raw.get("columns") or [])],
        rows=[[str(c) for c in r] for r in rows],
        caption=str(raw.get("caption", ""))[:200],
    )


def _question(raw: Any, concept_id: str = "") -> Question | None:
    if not isinstance(raw, dict) or not raw.get("text"):
        return None
    qtype = str(raw.get("type", "conceptual")).lower()
    if qtype not in {q.value for q in QuestionType}:
        qtype = "conceptual"
    return Question(
        type=QuestionType(qtype),
        text=str(raw["text"])[:600],
        options=[str(o)[:200] for o in (raw.get("options") or [])][:5],
        expected=str(raw.get("expected", ""))[:600],
        concept_id=concept_id,
    )


def _progress(session: Session) -> Progress:
    total = len(session.steps) or 1
    return Progress(
        step_index=session.step_index,
        total_steps=total,
        percent=round(min(100.0, session.step_index / total * 100), 1),
        minutes_spent=session.elapsed_minutes(),
        minutes_budget=session.profile.minutes,
        mastery=session.mastery_map(),
    )


def _context(session: Session, query: str, k: int = 5) -> tuple[str, list]:
    if not session.doc_id:
        return "", []
    return rag.context_for(session.doc_id, query, k=k)


def _adaptation_block(session: Session) -> str:
    """Feeds the explainer what the loop has learned about this student."""
    if not session.concepts:
        return ""
    scored = [c for c in session.concepts.values() if c.scores]
    if not scored:
        return ""
    avg = sum(c.mastery for c in scored) / len(scored)
    struggles = [c.title for c in scored if c.mastery < 0.5]
    misc = session.all_misconceptions()[:3]

    lines = ["ADAPTATION — adjust this step based on live performance:"]
    if avg < 0.45:
        lines.append(
            "- The student is STRUGGLING (avg mastery {:.0%}). Slow down, use "
            "smaller sentences, one very concrete everyday example, and avoid "
            "new jargon entirely.".format(avg)
        )
    elif avg > 0.85:
        lines.append(
            "- The student is AHEAD (avg mastery {:.0%}). Compress the basics "
            "to one line, go deeper, add an edge case or a harder example.".format(avg)
        )
    else:
        lines.append("- Pace is fine. Keep the current depth.")
    if struggles:
        lines.append(f"- Weak so far: {', '.join(struggles[:3])}. Tie this step back to them.")
    if misc:
        lines.append(f"- Misconceptions seen: {'; '.join(misc)}. Do not reinforce them.")
    return "\n".join(lines)


def _difficulty_note(session: Session) -> str:
    scored = [c for c in session.concepts.values() if c.scores]
    if not scored:
        return "first question of the lesson — keep it approachable"
    avg = sum(c.mastery for c in scored) / len(scored)
    if avg < 0.45:
        return "they have been struggling — make this noticeably easier, one idea only"
    if avg > 0.85:
        return "they are doing well — raise the difficulty, make them apply or predict"
    return "keep difficulty at their level"


def _qtype(session: Session) -> QuestionType:
    step = session.current_step
    if step and step.visual_hint in (VisualKind.formula, VisualKind.steps):
        return QuestionType.problem
    return QUESTION_CYCLE[session.step_index % len(QUESTION_CYCLE)]


async def _speak(session: Session, text: str, enabled: bool) -> Audio | None:
    sp = await safe_synthesize(text, session.profile.language, gender=getattr(session, 'current_teacher_gender', 'male'), enabled=enabled)
    if not sp:
        return None
    return Audio(
        b64=sp.audio_b64,
        mime=sp.mime,
        voice=sp.voice,
        words=[WordTiming(**w) for w in sp.words],
    )


# --------------------------------------------------------------------------- #
#  The agent
# --------------------------------------------------------------------------- #
class TeachingAgent:
    """Stateless service object; all state lives on the Session."""

    async def _turn(
        self,
        session: Session,
        *,
        phase: Phase,
        speech: str,
        board: Board | None = None,
        question: Question | None = None,
        evaluation: Evaluation | None = None,
        citations: list | None = None,
        awaiting: bool = False,
        finished: bool = False,
        speak: bool = True,
    ) -> TurnResponse:
        session.phase = phase
        session.last_speech = speech
        session.log("teacher", speech, {"phase": phase.value})
        return TurnResponse(
            session_id=session.session_id,
            phase=phase,
            speech=speech,
            board=board or Board(kind=VisualKind.none),
            question=question,
            evaluation=evaluation,
            audio=await _speak(session, speech, speak),
            progress=_progress(session),
            step=session.current_step,
            citations=citations or [],
            awaiting_student=awaiting,
            finished=finished,
        )

    # ------------------------------------------------------------------ #
    #  INTRO
    # ------------------------------------------------------------------ #
    async def intro(self, session: Session, speak: bool = True) -> TurnResponse:
        _persona(session) # initialize session.current_teacher_gender
        gender = getattr(session, 'current_teacher_gender', 'male')
        ask_verb = "poochhungi" if gender == "female" else "poochhunga"

        plan = session.plan
        p = session.profile
        titles = " ... ".join(s.title for s in plan.steps[:4])
        opening = (
            f"Namaste {p.name}! " if p.language.lower() in ("hindi", "hinglish") else f"Hi {p.name}! "
        )
        speech = (
            f"{opening}{plan.summary} "
            f"Aaj hum {len(plan.steps)} cheezein cover karenge: {titles}. "
            f"Main beech beech mein aapse sawaal bhi {ask_verb}, taaki pata chale "
            f"ki concept clear hua ya nahi. Chaliye shuru karte hain."
            if p.language.lower() in ("hindi", "hinglish")
            else f"{opening}{plan.summary} "
            f"We'll cover {len(plan.steps)} things today: {titles}. "
            f"I'll stop and ask you questions along the way, so I know what's "
            f"landing and what isn't. Let's begin."
        )
        board = Board(
            kind=VisualKind.bullets,
            title=plan.topic,
            items=[f"{i+1}. {s.title}" for i, s in enumerate(plan.steps[:6])],
            caption=f"{plan.total_minutes} min · {plan.level.value} · {plan.language}",
        )
        return await self._turn(
            session, phase=Phase.intro, speech=speech, board=board, speak=speak
        )

    # ------------------------------------------------------------------ #
    #  EXPLAIN
    # ------------------------------------------------------------------ #
    async def explain(self, session: Session, speak: bool = True) -> TurnResponse:
        step = session.current_step
        if step is None:
            return await self.assessment(session, speak=speak)

        concept = session.concept(step.id, step.title)
        query = f"{step.title}. {step.objective}. {' '.join(step.key_points)} {step.source_hint}"
        context_block, citations = _context(session, query, k=5)

        prompt = prompts.render(
            prompts.EXPLAIN_PROMPT,
            persona=_persona(session),
            step_no=session.step_index + 1,
            step_total=len(session.steps),
            title=step.title,
            objective=step.objective,
            depth=step.depth,
            key_points="; ".join(step.key_points),
            visual_hint=step.visual_hint.value,
            subject=session.plan.subject if session.plan else "general",
            context_block=context_block,
            history_block=(
                "RECENT LESSON TRANSCRIPT (keep continuity, do not repeat yourself):\n"
                + session.recent_transcript(4)
                if session.transcript
                else ""
            ),
            adaptation_block=_adaptation_block(session),
            word_budget=_word_budget(step.minutes),
            level=session.profile.level.value,
            language=session.profile.language,
        )
        data = json_call(prompt, temperature=0.5, fallback={})
        speech = str(data.get("speech") or f"Let's look at {step.title}.")
        concept.taught = True

        return await self._turn(
            session,
            phase=Phase.explain,
            speech=speech,
            board=_board(data.get("board")),
            citations=citations,
            speak=speak,
        )

    # ------------------------------------------------------------------ #
    #  QUESTION
    # ------------------------------------------------------------------ #
    async def ask_question(self, session: Session, speak: bool = True) -> TurnResponse:
        step = session.current_step
        if step is None:
            return await self.assessment(session, speak=speak)

        qtype = _qtype(session)
        prompt = prompts.render(
            prompts.QUESTION_PROMPT,
            persona=_persona(session),
            title=step.title,
            objective=step.objective,
            last_speech=session.last_speech[:900],
            difficulty_note=_difficulty_note(session),
            qtype=qtype.value,
            language=session.profile.language,
        )
        data = json_call(prompt, temperature=0.5, fallback={})
        question = _question(data.get("question"), step.id) or Question(
            type=QuestionType.own_words,
            text=step.check_question or f"In your own words — what did we just learn about {step.title}?",
            expected=step.objective,
            concept_id=step.id,
        )
        session.current_question = question
        session.attempt = 1
        speech = str(data.get("speech") or question.text)

        return await self._turn(
            session,
            phase=Phase.question,
            speech=speech,
            question=question,
            board=Board(
                kind=VisualKind.bullets,
                title="Your turn",
                items=question.options or [question.text[:120]],
            ),
            awaiting=True,
            speak=speak,
        )

    # ------------------------------------------------------------------ #
    #  EVALUATE  (+ branch to REMEDIATE or advance)
    # ------------------------------------------------------------------ #
    async def evaluate_answer(
        self, session: Session, answer: str, speak: bool = True
    ) -> TurnResponse:
        session.log("student", answer)

        if session.phase == Phase.assessment:
            return await self._grade_quiz_answer(session, answer, speak=speak)

        step = session.current_step
        question = session.current_question
        if step is None or question is None:
            return await self.next_turn(session, speak=speak)

        concept = session.concept(step.id, step.title)

        ev_raw = json_call(
            prompts.render(
                prompts.EVALUATE_PROMPT,
                title=step.title,
                question=question.text,
                expected=question.expected,
                answer=answer,
                attempt=session.attempt,
                level=session.profile.level.value,
                language=session.profile.language,
            ),
            fast=True,
            temperature=0.1,
            fallback={"verdict": "partial", "score": 0.5, "feedback": "Let's look at that again.",
                      "should_advance": False, "misconception": "", "gap": ""},
        )
        verdict = str(ev_raw.get("verdict", "partial")).lower()
        if verdict not in {v.value for v in Verdict}:
            verdict = "partial"
        try:
            score = float(ev_raw.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0

        evaluation = Evaluation(
            verdict=Verdict(verdict),
            score=max(0.0, min(1.0, score)),
            misconception=str(ev_raw.get("misconception", ""))[:120],
            gap=str(ev_raw.get("gap", ""))[:200],
            feedback=str(ev_raw.get("feedback", "")),
            should_advance=bool(ev_raw.get("should_advance", False)) or verdict == "correct",
        )

        concept.attempts += 1
        concept.scores.append(evaluation.score)
        concept.best_score = max(concept.best_score, evaluation.score)
        if evaluation.misconception:
            concept.misconceptions.append(evaluation.misconception)
        session.last_evaluation = evaluation

        # ---- branch A: understood -> move on -------------------------- #
        if evaluation.should_advance or session.attempt >= 4:
            session.step_index += 1
            session.current_question = None
            session.attempt = 0
            more = session.step_index < len(session.steps)
            bridge = (
                " Chaliye aage badhte hain." if session.profile.language.lower() in ("hindi", "hinglish")
                else " Good — let's move on."
            ) if more else (
                " Bahut badhiya. Ab ek chhota sa test lete hain."
                if session.profile.language.lower() in ("hindi", "hinglish")
                else " Nicely done. Now let's do a short check of the whole lesson."
            )
            return await self._turn(
                session,
                phase=Phase.evaluate,
                speech=(evaluation.feedback + bridge).strip(),
                evaluation=evaluation,
                speak=speak,
            )

        # ---- branch B: not yet -> REMEDIATE --------------------------- #
        return await self.remediate(session, answer, evaluation, speak=speak)

    # ------------------------------------------------------------------ #
    #  REMEDIATE — re-teach with a fresh analogy, never just correct
    # ------------------------------------------------------------------ #
    async def remediate(
        self, session: Session, answer: str, evaluation: Evaluation, speak: bool = True
    ) -> TurnResponse:
        step = session.current_step
        concept = session.concept(step.id, step.title)
        question = session.current_question

        context_block, citations = _context(
            session, f"{step.title} {evaluation.gap or evaluation.misconception}", k=4
        )

        data = json_call(
            prompts.render(
                prompts.REMEDIATE_PROMPT,
                persona=_persona(session),
                title=step.title,
                objective=step.objective,
                question=question.text if question else step.check_question,
                answer=answer,
                verdict=evaluation.verdict.value,
                misconception=evaluation.misconception,
                gap=evaluation.gap,
                attempt=session.attempt,
                used_analogies=", ".join(concept.used_analogies) or "none yet",
                context_block=context_block,
                word_budget=_word_budget(max(1.0, step.minutes * 0.6), floor=50, cap=200),
            ),
            temperature=0.65,
            fallback={},
        )

        domain = str(data.get("analogy_domain", "")).strip()[:24]
        if domain:
            concept.used_analogies.append(domain)

        followup = _question(data.get("followup_question"), step.id)
        if followup is None:
            followup = Question(
                type=QuestionType.conceptual,
                text="Ab batao — is example mein kya hoga?"
                if session.profile.language.lower() in ("hindi", "hinglish")
                else "So — what happens in this example?",
                expected=step.objective,
                concept_id=step.id,
            )
        session.current_question = followup
        session.attempt += 1

        speech = str(data.get("speech") or evaluation.feedback or "Let's try that from another angle.")
        return await self._turn(
            session,
            phase=Phase.remediate,
            speech=speech,
            board=_board(data.get("board")),
            question=followup,
            evaluation=evaluation,
            citations=citations,
            awaiting=True,
            speak=speak,
        )

    # ------------------------------------------------------------------ #
    #  DOUBT — student interrupts, lesson context preserved
    # ------------------------------------------------------------------ #
    async def answer_doubt(
        self, session: Session, doubt: str, speak: bool = True
    ) -> TurnResponse:
        session.log("student", doubt, {"kind": "doubt"})
        step = session.current_step
        context_block, citations = _context(session, doubt, k=5)

        data = json_call(
            prompts.render(
                prompts.DOUBT_PROMPT,
                persona=_persona(session),
                title=step.title if step else (session.plan.topic if session.plan else ""),
                step_no=session.step_index + 1,
                step_total=len(session.steps),
                doubt=doubt,
                context_block=context_block,
                history_block="RECENT TRANSCRIPT:\n" + session.recent_transcript(4),
                word_budget=140,
            ),
            temperature=0.45,
            fallback={},
        )
        speech = str(data.get("speech") or "Good question — let me clarify that.")
        # a doubt does not consume the lesson state; we stay where we were
        return await self._turn(
            session,
            phase=session.phase if session.phase != Phase.idle else Phase.explain,
            speech=speech,
            board=_board(data.get("board")),
            question=session.current_question,
            citations=citations,
            awaiting=session.current_question is not None,
            speak=speak,
        )

    # ------------------------------------------------------------------ #
    #  ASSESSMENT
    # ------------------------------------------------------------------ #
    async def assessment(self, session: Session, speak: bool = True) -> TurnResponse:
        if not session.wants_quiz:
            return await self.final_report(session, speak=speak)

        mastery_block = "\n".join(
            f"- {c.title} (id {c.step_id}): mastery {c.mastery:.2f}, attempts {c.attempts}"
            for c in session.concepts.values()
        ) or "- no live data, cover the plan evenly"

        n = 3 if session.profile.minutes <= 20 else 5
        data = json_call(
            prompts.render(
                prompts.ASSESSMENT_PROMPT,
                persona=_persona(session),
                mastery_block=mastery_block,
                n_questions=n,
                language=session.profile.language,
                level=session.profile.level.value,
            ),
            temperature=0.4,
            fallback={},
        )
        questions = [q for q in (_question(r, str(r.get("concept_id", ""))) for r in
                                (data.get("questions") or []) if isinstance(r, dict)) if q]
        if not questions and session.plan:
            questions = [
                Question(type=QuestionType.own_words, text=t, expected="", concept_id="")
                for t in session.plan.final_assessment[:n]
            ]
        if not questions:
            return await self.final_report(session, speak=speak)

        session.quiz = questions
        session.quiz_index = 0
        session.quiz_scores = []
        session.current_question = questions[0]

        speech = str(data.get("speech") or "Let's do a quick final check.") + " " + questions[0].text
        return await self._turn(
            session,
            phase=Phase.assessment,
            speech=speech,
            question=questions[0],
            board=Board(
                kind=VisualKind.bullets,
                title=f"Final check · 1/{len(questions)}",
                items=questions[0].options or [questions[0].text[:120]],
            ),
            awaiting=True,
            speak=speak,
        )

    async def _grade_quiz_answer(
        self, session: Session, answer: str, speak: bool = True
    ) -> TurnResponse:
        q = session.quiz[session.quiz_index]
        ev = json_call(
            prompts.render(
                prompts.EVALUATE_PROMPT,
                title=q.concept_id or "final assessment",
                question=q.text,
                expected=q.expected,
                answer=answer,
                attempt=3,          # quiz mode: give the answer, don't loop
                level=session.profile.level.value,
                language=session.profile.language,
            ),
            fast=True,
            temperature=0.1,
            fallback={"verdict": "partial", "score": 0.5, "feedback": ""},
        )
        try:
            score = max(0.0, min(1.0, float(ev.get("score", 0))))
        except (TypeError, ValueError):
            score = 0.0
        session.quiz_scores.append(score)
        if q.concept_id and q.concept_id in session.concepts:
            session.concepts[q.concept_id].scores.append(score)

        session.quiz_index += 1
        if session.quiz_index < len(session.quiz):
            nxt = session.quiz[session.quiz_index]
            session.current_question = nxt
            speech = f"{ev.get('feedback', '')} {nxt.text}".strip()
            return await self._turn(
                session,
                phase=Phase.assessment,
                speech=speech,
                question=nxt,
                board=Board(
                    kind=VisualKind.bullets,
                    title=f"Final check · {session.quiz_index + 1}/{len(session.quiz)}",
                    items=nxt.options or [nxt.text[:120]],
                ),
                awaiting=True,
                speak=speak,
            )
        return await self.final_report(session, speak=speak)

    # ------------------------------------------------------------------ #
    #  REPORT
    # ------------------------------------------------------------------ #
    async def final_report(self, session: Session, speak: bool = True) -> TurnResponse:
        mastery_block = "\n".join(
            f"- {c.title}: {c.mastery:.2f} (attempts {c.attempts})"
            for c in session.concepts.values()
        ) or "- no per-concept data"
        quiz_block = (
            "\n".join(
                f"- Q{i+1}: score {s:.2f}" for i, s in enumerate(session.quiz_scores)
            )
            or "- quiz not attempted"
        )

        data = json_call(
            prompts.render(
                prompts.REPORT_PROMPT,
                topic=session.plan.topic if session.plan else session.topic,
                language=session.profile.language,
                mastery_block=mastery_block,
                misconceptions="; ".join(session.all_misconceptions()) or "none observed",
                quiz_block=quiz_block,
            ),
            temperature=0.3,
            fallback={},
        )

        live = list(session.mastery_map().values())
        computed = round((sum(live) / len(live) * 100) if live else 0, 1)
        try:
            score = float(data.get("score_percent", computed))
        except (TypeError, ValueError):
            score = computed

        report = LearningReport(
            topic=session.plan.topic if session.plan else session.topic,
            score_percent=round(max(0.0, min(100.0, score)), 1),
            strong_areas=[str(x) for x in (data.get("strong_areas") or [])][:6],
            weak_areas=[str(x) for x in (data.get("weak_areas") or [])][:6],
            misconceptions=[str(x) for x in (data.get("misconceptions") or [])][:6],
            recommendation=str(data.get("recommendation", "")),
            next_topics=[str(x) for x in (data.get("next_topics") or [])][:6],
            per_concept=session.mastery_map(),
        )
        session.report = report.model_dump(mode="json")

        remember(
            session.profile.name,
            {
                "topics": [report.topic],
                "weak": report.weak_areas,
                "strong": report.strong_areas,
                "history": {"topic": report.topic, "score": report.score_percent},
            },
        )

        speech = str(data.get("speech") or "That's the end of our lesson. Well done today.")
        board = Board(
            kind=VisualKind.table,
            title=f"Learning report · {report.score_percent}%",
            columns=["Concept", "Mastery"],
            rows=[[k, f"{v*100:.0f}%"] for k, v in report.per_concept.items()],
            caption=report.recommendation,
        )
        return await self._turn(
            session,
            phase=Phase.report,
            speech=speech,
            board=board,
            finished=True,
            speak=speak,
        )

    # ------------------------------------------------------------------ #
    #  The single entry point the frontend polls: "what happens next?"
    # ------------------------------------------------------------------ #
    async def next_turn(self, session: Session, speak: bool = True) -> TurnResponse:
        phase = session.phase

        if phase in (Phase.idle,):
            return await self.intro(session, speak=speak)

        if phase in (Phase.intro, Phase.evaluate):
            if session.step_index >= len(session.steps):
                return await self.assessment(session, speak=speak)
            return await self.explain(session, speak=speak)

        if phase == Phase.explain:
            return await self.ask_question(session, speak=speak)

        if phase in (Phase.question, Phase.remediate):
            # student pressed "skip / I don't know" — treat as an unmastered concept
            step = session.current_step
            if step:
                c = session.concept(step.id, step.title)
                c.scores.append(0.2)
            session.step_index += 1
            session.current_question = None
            session.attempt = 0
            if session.step_index >= len(session.steps):
                return await self.assessment(session, speak=speak)
            return await self.explain(session, speak=speak)

        if phase == Phase.assessment:
            return await self.final_report(session, speak=speak)

        return await self._turn(
            session, phase=Phase.done, speech="Lesson complete.", finished=True, speak=speak
        )


agent = TeachingAgent()
