// Mirrors backend/app/schemas.py — keep the two in sync.

export type Level = "beginner" | "intermediate" | "advanced";

export type Phase =
  | "idle" | "intro" | "explain" | "question" | "evaluate"
  | "remediate" | "assessment" | "report" | "done";

export type VisualKind =
  | "bullets" | "formula" | "steps" | "code" | "diagram" | "table" | "timeline" | "none";

export interface StudentProfile {
  name: string;
  level: Level;
  language: string;
  minutes: number;
  goal: string;
  style: string;
  prior_knowledge: string;
}

export interface Board {
  kind: VisualKind;
  title: string;
  items: string[];
  latex: string;
  code: string;
  language: string;
  mermaid: string;
  columns: string[];
  rows: string[][];
  caption: string;
}

export interface LessonStep {
  id: string;
  title: string;
  objective: string;
  depth: "skim" | "standard" | "deep";
  minutes: number;
  key_points: string[];
  visual_hint: VisualKind;
  check_question: string;
  source_hint: string;
}

export interface LessonPlan {
  topic: string;
  summary: string;
  subject: string;
  total_minutes: number;
  language: string;
  level: Level;
  steps: LessonStep[];
  final_assessment: string[];
  prerequisites: string[];
}

export interface Question {
  type: string;
  text: string;
  options: string[];
  expected?: string;
  concept_id: string;
}

export interface Evaluation {
  verdict: "correct" | "partial" | "incorrect" | "off_topic" | "dont_know";
  score: number;
  misconception: string;
  gap: string;
  feedback: string;
  should_advance: boolean;
}

export interface WordTiming { word: string; start_ms: number; duration_ms: number }

export interface AudioPayload {
  b64: string;
  mime: string;
  voice: string;
  words: WordTiming[];
}

export interface Progress {
  step_index: number;
  total_steps: number;
  percent: number;
  minutes_spent: number;
  minutes_budget: number;
  mastery: Record<string, number>;
}

export interface Citation {
  n: number; page: number | string; section: string; filename: string; snippet: string;
}

export interface TurnResponse {
  session_id: string;
  phase: Phase;
  speech: string;
  board: Board;
  question: Question | null;
  evaluation: Evaluation | null;
  audio: AudioPayload | null;
  progress: Progress;
  step: LessonStep | null;
  citations: Citation[];
  awaiting_student: boolean;
  finished: boolean;
}

export interface DocumentMeta {
  doc_id: string; filename: string; pages: number; chunks: number;
  chars: number; outline: string[]; preview: string;
}

export interface LearningReport {
  topic: string;
  score_percent: number;
  strong_areas: string[];
  weak_areas: string[];
  misconceptions: string[];
  recommendation: string;
  next_topics: string[];
  per_concept: Record<string, number>;
}

export interface ChatMessage {
  id: string;
  role: "teacher" | "student";
  text: string;
  phase?: Phase;
  question?: Question | null;
  evaluation?: Evaluation | null;
  citations?: Citation[];
  audioUrl?: string;
  words?: WordTiming[];
}
