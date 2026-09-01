"use client";

import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import { b64ToBlobUrl } from "@/lib/utils";
import type {
  Board, ChatMessage, DocumentMeta, LearningReport, LessonPlan,
  Phase, Question, StudentProfile, TurnResponse,
} from "@/lib/types";
import { useSpeechAudio } from "./useSpeechAudio";

const EMPTY_BOARD: Board = {
  kind: "none", title: "", items: [], latex: "", code: "",
  language: "", mermaid: "", columns: [], rows: [], caption: "",
};

let seq = 0;
const nextId = () => `m${++seq}`;

export function useTeacher() {
  const audio = useSpeechAudio();

  const [sessionId, setSessionId] = useState("");
  const [plan, setPlan] = useState<LessonPlan | null>(null);
  const [doc, setDoc] = useState<DocumentMeta | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [board, setBoard] = useState<Board>(EMPTY_BOARD);
  const [phase, setPhase] = useState<Phase>("idle");
  const [question, setQuestion] = useState<Question | null>(null);
  const [progress, setProgress] = useState({ percent: 0, step_index: 0, total_steps: 0, mastery: {} as Record<string, number> });
  const [report, setReport] = useState<LearningReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [autoplay, setAutoplay] = useState(true);

  const lastAudioUrl = useRef<string>("");

  const consume = useCallback(
    (turn: TurnResponse) => {
      setPhase(turn.phase);
      setQuestion(turn.awaiting_student ? turn.question : null);
      setProgress({
        percent: turn.progress.percent,
        step_index: turn.progress.step_index,
        total_steps: turn.progress.total_steps,
        mastery: turn.progress.mastery || {},
      });
      if (turn.board && turn.board.kind !== "none") setBoard(turn.board);

      let url = "";
      if (turn.audio?.b64) {
        if (lastAudioUrl.current) URL.revokeObjectURL(lastAudioUrl.current);
        url = b64ToBlobUrl(turn.audio.b64, turn.audio.mime);
        lastAudioUrl.current = url;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "teacher",
          text: turn.speech,
          phase: turn.phase,
          question: turn.question,
          evaluation: turn.evaluation,
          citations: turn.citations,
          audioUrl: url,
          words: turn.audio?.words || [],
        },
      ]);

      if (url || turn.speech) {
        if (autoplay) void audio.play(url, turn.audio?.words || [], turn.speech);
      }
      if (turn.finished) void refreshReport(turn.session_id);
    },
    [audio, autoplay] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const refreshReport = useCallback(async (sid: string) => {
    try {
      const { report } = await api.report(sid);
      setReport(report);
    } catch { /* report is best-effort */ }
  }, []);

  const guard = async <T,>(fn: () => Promise<T>) => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e: any) {
      setError(e?.message || "Something went wrong");
      return undefined;
    } finally {
      setBusy(false);
    }
  };

  const upload = useCallback(
    (file: File) => guard(async () => {
      const meta = await api.upload(file);
      setDoc(meta);
      return meta;
    }),
    []
  );

  const start = useCallback(
    (profile: StudentProfile, topic: string, instruction: string) =>
      guard(async () => {
        const res = await api.startLesson({
          profile, topic, instruction, doc_id: doc?.doc_id || "", speak: true,
        });
        setSessionId(res.session_id);
        setPlan(res.plan);
        setMessages([]);
        setReport(null);
        consume(res.turn);
        return res;
      }),
    [doc, consume]
  );

  const next = useCallback(
    () => guard(async () => {
      if (!sessionId) return;
      consume(await api.next(sessionId));
    }),
    [sessionId, consume]
  );

  const answer = useCallback(
    (text: string) => guard(async () => {
      if (!sessionId || !text.trim()) return;
      setMessages((p) => [...p, { id: nextId(), role: "student", text }]);
      consume(await api.answer(sessionId, text));
    }),
    [sessionId, consume]
  );

  const ask = useCallback(
    (text: string) => guard(async () => {
      if (!sessionId || !text.trim()) return;
      setMessages((p) => [...p, { id: nextId(), role: "student", text }]);
      consume(await api.ask(sessionId, text));
    }),
    [sessionId, consume]
  );

  const switchLanguage = useCallback(
    (language: string) => guard(async () => {
      if (!sessionId) return;
      consume(await api.setLanguage(sessionId, language));
    }),
    [sessionId, consume]
  );

  return {
    // state
    sessionId, plan, doc, messages, board, phase, question, progress, report,
    busy, error, autoplay, setAutoplay,
    // audio
    audio,
    // actions
    upload, start, next, answer, ask, switchLanguage,
  };
}
