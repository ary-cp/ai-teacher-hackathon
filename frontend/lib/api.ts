import type {
  DocumentMeta, LearningReport, LessonPlan, StudentProfile, TurnResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,

  health: () => get<{ ok: boolean; groq_key_loaded: boolean }>("/api/health"),

  async upload(file: File): Promise<DocumentMeta> {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}/api/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.text()) || "upload failed");
    const json = await res.json();
    return json.document as DocumentMeta;
  },

  startLesson: (payload: {
    profile: StudentProfile;
    topic?: string;
    doc_id?: string;
    instruction?: string;
    speak?: boolean;
  }) =>
    post<{
      session_id: string;
      plan: LessonPlan;
      profile: StudentProfile;
      turn: TurnResponse;
    }>("/api/lesson/start", { ...payload, teacher_id: localStorage.getItem("ai_teacher_id") || "mr_sharma" }),

  next: (session_id: string, speak = true) =>
    post<TurnResponse>("/api/teach/next", { session_id, speak, teacher_id: localStorage.getItem("ai_teacher_id") || "mr_sharma" }),

  answer: (session_id: string, answer: string, speak = true) =>
    post<TurnResponse>("/api/teach/answer", { session_id, answer, speak, teacher_id: localStorage.getItem("ai_teacher_id") || "mr_sharma" }),

  ask: (session_id: string, question: string, speak = true) =>
    post<TurnResponse>("/api/teach/ask", { session_id, question, speak, teacher_id: localStorage.getItem("ai_teacher_id") || "mr_sharma" }),

  setLanguage: (session_id: string, language: string) =>
    post<TurnResponse>("/api/teach/language", { session_id, language }),

  report: (session_id: string) =>
    get<{ report: LearningReport }>(`/api/teach/${session_id}/report`),

  tts: (text: string, language: string) =>
    post<{ audio_b64: string; mime: string; words: unknown[] }>("/api/tts", { text, language }),
};
