"""The interactive teaching loop endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.session_store import get_session, recall
from app.schemas import AnswerRequest, AskRequest, LanguageRequest, NextRequest, TurnResponse
from app.teaching_agent import agent

log = logging.getLogger("ai-teacher.teach")
router = APIRouter(prefix="/api/teach", tags=["teaching-loop"])


def _session(session_id: str):
    try:
        return get_session(session_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/next", response_model=TurnResponse)
async def next_turn(req: NextRequest) -> TurnResponse:
    """Advance the state machine: intro -> explain -> question -> ..."""
    session = _session(req.session_id)
    session.profile.style = f"{session.profile.style.split('|')[0]}|{req.teacher_id}"
    return await agent.next_turn(session, speak=req.speak)


@router.post("/answer", response_model=TurnResponse)
async def answer(req: AnswerRequest) -> TurnResponse:
    """Student answered the teacher's question: evaluate, then adapt."""
    session = _session(req.session_id)
    session.profile.style = f"{session.profile.style.split('|')[0]}|{req.teacher_id}"
    if not req.answer.strip():
        raise HTTPException(400, "empty answer")
    return await agent.evaluate_answer(session, req.answer.strip(), speak=req.speak)


@router.post("/ask", response_model=TurnResponse)
async def ask(req: AskRequest) -> TurnResponse:
    """Student interrupts with a doubt; lesson context is preserved."""
    session = _session(req.session_id)
    session.profile.style = f"{session.profile.style.split('|')[0]}|{req.teacher_id}"
    return await agent.answer_doubt(session, req.question, speak=req.speak)


@router.post("/language", response_model=TurnResponse)
async def switch_language(req: LanguageRequest) -> TurnResponse:
    session = _session(req.session_id)
    session.profile.language = req.language
    if session.plan:
        session.plan.language = req.language
    return await agent.answer_doubt(
        session, f"From now on, teach me in {req.language}.", speak=True
    )


@router.get("/{session_id}/state")
async def state(session_id: str) -> dict:
    s = _session(session_id)
    return {
        "session_id": s.session_id,
        "phase": s.phase.value,
        "step_index": s.step_index,
        "attempt": s.attempt,
        "mastery": s.mastery_map(),
        "misconceptions": s.all_misconceptions(),
        "minutes_spent": s.elapsed_minutes(),
        "profile": s.profile.model_dump(mode="json"),
    }


@router.get("/{session_id}/transcript")
async def transcript(session_id: str) -> dict:
    return {"transcript": _session(session_id).transcript}


@router.get("/{session_id}/report")
async def report(session_id: str) -> dict:
    s = _session(session_id)
    if not s.report:
        turn = await agent.final_report(s, speak=False)
        return {"report": s.report, "turn": turn.model_dump(mode="json")}
    return {"report": s.report}


@router.get("/memory/{student}")
async def learner_memory(student: str) -> dict:
    """Long-term learner memory across sessions."""
    return recall(student)
