"""In-memory session + learner-memory store.

Swap `_SESSIONS` for Redis/Postgres for production; the interface below is the
only thing the agent touches, so the change is one file.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.schemas import (
    Evaluation,
    LessonPlan,
    Phase,
    Question,
    StudentProfile,
)


@dataclass
class ConceptState:
    step_id: str
    title: str
    attempts: int = 0
    best_score: float = 0.0
    scores: list[float] = field(default_factory=list)
    misconceptions: list[str] = field(default_factory=list)
    used_analogies: list[str] = field(default_factory=list)
    taught: bool = False

    @property
    def mastery(self) -> float:
        if not self.scores:
            return 0.0
        # latest answer weighs most — learning is recency-biased
        weights = [1.4 ** i for i in range(len(self.scores))]
        return round(sum(s * w for s, w in zip(self.scores, weights)) / sum(weights), 3)


@dataclass
class Session:
    session_id: str
    profile: StudentProfile
    doc_id: str = ""
    topic: str = ""
    plan: Optional[LessonPlan] = None
    phase: Phase = Phase.idle
    step_index: int = 0
    attempt: int = 0
    current_question: Optional[Question] = None
    last_speech: str = ""
    last_evaluation: Optional[Evaluation] = None
    concepts: dict[str, ConceptState] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    quiz: list[Question] = field(default_factory=list)
    quiz_index: int = 0
    quiz_scores: list[float] = field(default_factory=list)
    report: Optional[dict[str, Any]] = None
    started_at: float = field(default_factory=time.time)
    minutes_spent: float = 0.0
    wants_quiz: bool = True

    # ---------------- helpers ----------------
    @property
    def steps(self) -> list:
        return self.plan.steps if self.plan else []

    @property
    def current_step(self):
        if self.plan and 0 <= self.step_index < len(self.plan.steps):
            return self.plan.steps[self.step_index]
        return None

    def concept(self, step_id: str, title: str = "") -> ConceptState:
        if step_id not in self.concepts:
            self.concepts[step_id] = ConceptState(step_id=step_id, title=title)
        return self.concepts[step_id]

    def mastery_map(self) -> dict[str, float]:
        return {c.title or c.step_id: c.mastery for c in self.concepts.values()}

    def all_misconceptions(self) -> list[str]:
        out: list[str] = []
        for c in self.concepts.values():
            for m in c.misconceptions:
                if m and m not in out:
                    out.append(m)
        return out

    def log(self, role: str, text: str, meta: dict[str, Any] | None = None) -> None:
        self.transcript.append(
            {"role": role, "text": text, "t": round(time.time() - self.started_at, 1), **(meta or {})}
        )

    def recent_transcript(self, n: int = 6) -> str:
        rows = self.transcript[-n:]
        return "\n".join(f"{r['role']}: {r['text'][:400]}" for r in rows)

    def elapsed_minutes(self) -> float:
        return round((time.time() - self.started_at) / 60, 2)


_SESSIONS: dict[str, Session] = {}


def create_session(profile: StudentProfile, doc_id: str = "", topic: str = "") -> Session:
    sid = uuid.uuid4().hex[:12]
    s = Session(session_id=sid, profile=profile, doc_id=doc_id, topic=topic)
    _SESSIONS[sid] = s
    return s


def get_session(session_id: str) -> Session:
    if session_id not in _SESSIONS:
        raise KeyError(f"unknown session '{session_id}'")
    return _SESSIONS[session_id]


def drop_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


# --------------------------------------------------------------------------- #
#  Long-term learner memory (survives across sessions, keyed by student name)
# --------------------------------------------------------------------------- #
_LEARNER_MEMORY: dict[str, dict[str, Any]] = {}


def remember(student: str, payload: dict[str, Any]) -> None:
    mem = _LEARNER_MEMORY.setdefault(
        student, {"topics": [], "weak": [], "strong": [], "history": []}
    )
    for key in ("topics", "weak", "strong"):
        for v in payload.get(key, []) or []:
            if v not in mem[key]:
                mem[key].append(v)
    if payload.get("history"):
        mem["history"].append(payload["history"])


def recall(student: str) -> dict[str, Any]:
    return _LEARNER_MEMORY.get(student, {"topics": [], "weak": [], "strong": [], "history": []})
