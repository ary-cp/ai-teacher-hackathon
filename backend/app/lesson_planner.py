"""
UNDERSTAND -> PLAN stage.

Turns (student instruction + profile + optional document) into a validated
LessonPlan. The plan is the contract the whole teaching loop runs on, so it is
schema-validated and time-normalised before it ever reaches the agent.
"""
from __future__ import annotations

import json
import logging

from app import rag_pipeline as rag
from app.core import prompts
from app.core.llm import json_call
from app.schemas import LessonPlan, LessonStep, Level, StudentProfile, VisualKind

log = logging.getLogger("ai-teacher.planner")


# --------------------------------------------------------------------------- #
#  UNDERSTAND
# --------------------------------------------------------------------------- #
def parse_instruction(instruction: str, profile: StudentProfile) -> dict:
    """'Beginner hoon, chapter 4 ko 20 min me Hindi me padhao' -> parameters."""
    if not instruction.strip():
        return {}
    prompt = prompts.render(
        prompts.INTAKE_PROMPT,
        instruction=instruction,
        profile_json=profile.model_dump_json(),
    )
    return json_call(prompt, fast=True, temperature=0.1, fallback={})


def apply_intake(profile: StudentProfile, intake: dict) -> tuple[StudentProfile, str]:
    """Merge what the student said into the profile. Explicit form values win
    only where the instruction said nothing."""
    data = profile.model_dump()
    if intake.get("level") in {l.value for l in Level}:
        data["level"] = intake["level"]
    if intake.get("language"):
        data["language"] = intake["language"]
    if intake.get("minutes"):
        try:
            data["minutes"] = max(3, min(600, int(intake["minutes"])))
        except (TypeError, ValueError):
            pass
    if intake.get("goal"):
        data["goal"] = intake["goal"]
    if intake.get("style"):
        data["style"] = intake["style"]
    return StudentProfile(**data), (intake.get("topic") or "").strip()


# --------------------------------------------------------------------------- #
#  PLAN
# --------------------------------------------------------------------------- #
def _context_for_planning(doc_id: str, topic: str, scope: str = "") -> tuple[str, list]:
    """Planner sees the document's OUTLINE plus retrieved chunks for the topic,
    so it plans around real chapters instead of guessing."""
    if not doc_id:
        return "", []
    meta = rag.get_doc(doc_id)
    query = " ".join(x for x in [topic, scope] if x) or (meta.filename if meta else "overview")
    block, citations = rag.context_for(doc_id, query, k=8)
    if meta and meta.outline:
        outline = "DOCUMENT OUTLINE:\n" + "\n".join(meta.outline[:30])
        block = f"{outline}\n\n{block}"
    return block, citations


def _fallback_plan(topic: str, profile: StudentProfile) -> LessonPlan:
    """Never leave the demo with a blank screen if the LLM misbehaves."""
    return LessonPlan(
        topic=topic or "Your topic",
        summary="Let's build this up from the basics, step by step.",
        subject="general",
        total_minutes=profile.minutes,
        language=profile.language,
        level=profile.level,
        steps=[
            LessonStep(
                id="s1",
                title=f"Introduction to {topic or 'the topic'}",
                objective="Understand what it is and why it matters",
                minutes=max(2, profile.minutes / 3),
                key_points=["core idea", "why it matters"],
                check_question="In your own words, what is this about?",
            ),
            LessonStep(
                id="s2",
                title="Core concept",
                objective="Apply the main idea to a simple example",
                minutes=max(2, profile.minutes / 3),
                key_points=["definition", "worked example"],
                check_question="Try this small example yourself — what do you get?",
            ),
        ],
        final_assessment=["Explain the main idea in your own words."],
    )


def _normalise_steps(raw_steps: list, budget: int) -> list[LessonStep]:
    steps: list[LessonStep] = []
    for i, s in enumerate(raw_steps or [], start=1):
        if not isinstance(s, dict):
            continue
        hint = str(s.get("visual_hint", "bullets")).lower()
        if hint not in {v.value for v in VisualKind}:
            hint = "bullets"
        depth = str(s.get("depth", "standard")).lower()
        if depth not in {"skim", "standard", "deep"}:
            depth = "standard"
        try:
            minutes = float(s.get("minutes", 3) or 3)
        except (TypeError, ValueError):
            minutes = 3.0
        steps.append(
            LessonStep(
                id=str(s.get("id") or f"s{i}"),
                title=str(s.get("title", f"Step {i}"))[:160],
                objective=str(s.get("objective", ""))[:300],
                depth=depth,
                minutes=max(0.5, minutes),
                key_points=[str(k)[:160] for k in (s.get("key_points") or [])][:6],
                visual_hint=VisualKind(hint),
                check_question=str(s.get("check_question", ""))[:400],
                source_hint=str(s.get("source_hint", ""))[:200],
            )
        )

    if not steps:
        return steps

    # Rescale so the plan actually fits the student's clock (85% of budget,
    # the rest is spent on questions, remediation and the quiz).
    teach_budget = budget * 0.85
    total = sum(s.minutes for s in steps) or teach_budget
    factor = teach_budget / total
    for s in steps:
        s.minutes = round(max(0.5, s.minutes * factor), 1)
    return steps


def build_plan(
    profile: StudentProfile,
    topic: str,
    doc_id: str = "",
    scope: str = "",
) -> tuple[LessonPlan, list]:
    context_block, citations = _context_for_planning(doc_id, topic, scope)
    source_mode = "document" if doc_id else "topic-only (use your own knowledge)"
    minutes = profile.minutes

    prompt = prompts.render(
        prompts.PLANNER_PROMPT,
        persona=prompts.render(
            prompts.PERSONA,
            name=profile.name,
            level=profile.level.value,
            language=profile.language,
            style=profile.style,
            goal=profile.goal,
            prior_knowledge=profile.prior_knowledge,
        ),
        topic=topic or "the uploaded material",
        minutes=minutes,
        min_total=int(minutes * 0.7),
        max_total=int(minutes * 0.9),
        source_mode=source_mode,
        context_block=context_block,
        language=profile.language,
    )

    data = json_call(prompt, temperature=0.35, fallback={})
    steps = _normalise_steps(data.get("steps", []), minutes)
    if not steps:
        log.warning("planner returned no usable steps; using fallback plan")
        return _fallback_plan(topic, profile), citations

    plan = LessonPlan(
        topic=str(data.get("topic") or topic or "Lesson"),
        summary=str(data.get("summary", "")),
        subject=str(data.get("subject", "general")).lower(),
        total_minutes=minutes,
        language=profile.language,
        level=profile.level,
        steps=steps,
        prerequisites=[str(p) for p in (data.get("prerequisites") or [])][:6],
        final_assessment=[str(q) for q in (data.get("final_assessment") or [])][:6],
    )
    log.info("plan built: %s steps for %s min on '%s'", len(plan.steps), minutes, plan.topic)
    return plan, citations


def build_learning_path(topic: str, profile: StudentProfile) -> list[dict]:
    prompt = prompts.render(
        prompts.LEARNING_PATH_PROMPT,
        topic=topic,
        level=profile.level.value,
        goal=profile.goal or "general mastery",
        minutes=profile.minutes,
    )
    data = json_call(prompt, fast=True, temperature=0.3, fallback={"path": []})
    return data.get("path", [])


def plan_to_json(plan: LessonPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)
