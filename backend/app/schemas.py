"""Pydantic contracts shared by the API and (mirrored in TS) by the frontend."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
#  Learner profile
# --------------------------------------------------------------------------- #
class Level(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class StudentProfile(BaseModel):
    name: str = "Student"
    level: Level = Level.beginner
    language: str = Field(
        "hinglish",
        description="english | hindi | hinglish | bengali | tamil | ... free text is fine",
    )
    minutes: int = Field(20, ge=3, le=600, description="Time budget for the whole lesson")
    goal: str = ""
    style: str = Field("friendly, example-first", description="Preferred teaching style")
    prior_knowledge: str = ""


# --------------------------------------------------------------------------- #
#  Lesson plan
# --------------------------------------------------------------------------- #
class VisualKind(str, Enum):
    bullets = "bullets"
    formula = "formula"
    steps = "steps"
    code = "code"
    diagram = "diagram"   # mermaid source
    table = "table"
    timeline = "timeline"
    none = "none"


class Board(BaseModel):
    """The 'blackboard' that the avatar writes on while speaking."""
    kind: VisualKind = VisualKind.bullets
    title: str = ""
    items: list[str] = []          # bullets / steps / timeline rows
    latex: str = ""                # for kind == formula
    code: str = ""                 # for kind == code
    language: str = ""             # code language
    mermaid: str = ""              # for kind == diagram
    columns: list[str] = []        # for kind == table
    rows: list[list[str]] = []     # for kind == table
    caption: str = ""


class LessonStep(BaseModel):
    id: str
    title: str
    objective: str
    depth: Literal["skim", "standard", "deep"] = "standard"
    minutes: float = 3
    key_points: list[str] = []
    visual_hint: VisualKind = VisualKind.bullets
    check_question: str = ""
    source_hint: str = ""          # chapter / section the RAG layer should target


class LessonPlan(BaseModel):
    topic: str
    summary: str
    subject: str = "general"
    total_minutes: int = 20
    language: str = "hinglish"
    level: Level = Level.beginner
    steps: list[LessonStep]
    final_assessment: list[str] = []
    prerequisites: list[str] = []


# --------------------------------------------------------------------------- #
#  Teaching loop
# --------------------------------------------------------------------------- #
class Phase(str, Enum):
    idle = "idle"
    intro = "intro"
    explain = "explain"
    question = "question"
    evaluate = "evaluate"
    remediate = "remediate"
    assessment = "assessment"
    report = "report"
    done = "done"


class QuestionType(str, Enum):
    conceptual = "conceptual"
    mcq = "mcq"
    short = "short"
    problem = "problem"
    application = "application"
    own_words = "own_words"


class Question(BaseModel):
    type: QuestionType = QuestionType.conceptual
    text: str
    options: list[str] = []
    expected: str = ""          # rubric answer, never sent to the UI verbatim
    concept_id: str = ""


class Verdict(str, Enum):
    correct = "correct"
    partial = "partial"
    incorrect = "incorrect"
    off_topic = "off_topic"
    dont_know = "dont_know"


class Evaluation(BaseModel):
    verdict: Verdict
    score: float = Field(0, ge=0, le=1)
    misconception: str = ""      # short label, "" when none detected
    gap: str = ""                # what exactly is missing
    feedback: str = ""           # spoken, constructive, never just "wrong"
    should_advance: bool = False


class WordTiming(BaseModel):
    word: str
    start_ms: int
    duration_ms: int


class Audio(BaseModel):
    b64: str = ""                # audio/mpeg base64
    mime: str = "audio/mpeg"
    voice: str = ""
    words: list[WordTiming] = [] # drives caption highlight + avatar lip-sync


class Progress(BaseModel):
    step_index: int = 0
    total_steps: int = 0
    percent: float = 0
    minutes_spent: float = 0
    minutes_budget: float = 0
    mastery: dict[str, float] = {}


class TurnResponse(BaseModel):
    session_id: str
    phase: Phase
    speech: str                      # what the avatar says (spoken text)
    board: Board = Board()
    question: Optional[Question] = None
    evaluation: Optional[Evaluation] = None
    audio: Optional[Audio] = None
    progress: Progress = Progress()
    step: Optional[LessonStep] = None
    citations: list[dict[str, Any]] = []
    awaiting_student: bool = False
    finished: bool = False


class LearningReport(BaseModel):
    topic: str
    score_percent: float
    strong_areas: list[str] = []
    weak_areas: list[str] = []
    misconceptions: list[str] = []
    recommendation: str = ""
    next_topics: list[str] = []
    per_concept: dict[str, float] = {}


# --------------------------------------------------------------------------- #
#  Request bodies
# --------------------------------------------------------------------------- #
class StartSessionRequest(BaseModel):
    profile: StudentProfile
    topic: str = ""                  # free-text topic (topic-only mode)
    doc_id: str = ""                 # uploaded document (RAG mode)
    instruction: str = ""            # raw natural-language brief from the student
    teacher_id: str = "mr_sharma"
    speak: bool = True


class NextRequest(BaseModel):
    session_id: str
    teacher_id: str = "mr_sharma"
    speak: bool = True


class AnswerRequest(BaseModel):
    session_id: str
    answer: str
    teacher_id: str = "mr_sharma"
    speak: bool = True


class AskRequest(BaseModel):
    """Student interrupts with a doubt without losing lesson context."""
    session_id: str
    question: str
    teacher_id: str = "mr_sharma"
    speak: bool = True


class LanguageRequest(BaseModel):
    session_id: str
    language: str
