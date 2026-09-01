"""UNDERSTAND -> PLAN endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app import lesson_planner as planner
from app.core.session_store import create_session, get_session
from app.schemas import LessonPlan, StartSessionRequest, StudentProfile
from app.teaching_agent import agent

log = logging.getLogger("ai-teacher.lesson")
router = APIRouter(prefix="/api/lesson", tags=["lesson"])


@router.post("/start", response_model=dict)
async def start_lesson(req: StartSessionRequest) -> dict:
    if not req.topic and not req.doc_id and not req.instruction:
        raise HTTPException(400, "Provide a topic, an instruction, or an uploaded doc_id")

    profile: StudentProfile = req.profile
    intake = planner.parse_instruction(req.instruction, profile)
    profile, parsed_topic = planner.apply_intake(profile, intake)
    
    # Inject teacher_id after apply_intake so the LLM doesn't overwrite it
    profile.style = f"{profile.style.split('|')[0]}|{req.teacher_id}"
    
    topic = req.topic or parsed_topic

    plan, citations = planner.build_plan(
        profile=profile,
        topic=topic,
        doc_id=req.doc_id,
        scope=str(intake.get("source_scope", "")),
    )

    session = create_session(profile=profile, doc_id=req.doc_id, topic=plan.topic)
    session.plan = plan
    session.wants_quiz = bool(intake.get("wants_quiz", True))

    turn = await agent.intro(session, speak=req.speak)
    return {
        "session_id": session.session_id,
        "profile": profile.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "intake": intake,
        "citations": citations,
        "turn": turn.model_dump(mode="json"),
    }


@router.get("/{session_id}/plan")
async def get_plan(session_id: str) -> LessonPlan:
    try:
        session = get_session(session_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not session.plan:
        raise HTTPException(404, "no plan on this session")
    return session.plan


@router.post("/path")
async def learning_path(profile: StudentProfile, topic: str) -> dict:
    return {"path": planner.build_learning_path(topic, profile)}
