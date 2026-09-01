"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, HelpCircle, Loader2, Send, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ChatMessage, Phase, Question, WordTiming } from "@/lib/types";

interface Props {
  messages: ChatMessage[];
  question: Question | null;
  phase: Phase;
  busy: boolean;
  finished: boolean;
  activeWordIndex: number;
  onAnswer: (text: string) => void;
  onAsk: (text: string) => void;
  onNext: () => void;
  onReplay: (url: string, words: WordTiming[], text: string) => void;
}

const VERDICT_VARIANT = {
  correct: "success", partial: "warning", incorrect: "danger",
  dont_know: "warning", off_topic: "secondary",
} as const;

export function ChatPanel({
  messages, question, phase, busy, finished, activeWordIndex,
  onAnswer, onAsk, onNext, onReplay,
}: Props) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, busy]);

  const send = (mode: "answer" | "ask") => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    mode === "answer" ? onAnswer(text) : onAsk(text);
  };

  const awaiting = Boolean(question);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="board-scroll min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.map((m, idx) => (
          <Bubble
            key={m.id}
            message={m}
            isLast={idx === messages.length - 1}
            activeWordIndex={activeWordIndex}
            onReplay={onReplay}
          />
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> teacher is thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {question && (
        <Card className="border-primary/40 bg-primary/5">
          <CardContent className="space-y-2 p-3">
            <div className="flex items-center gap-2">
              <Badge>{question.type.replace("_", " ")}</Badge>
              <span className="text-xs text-muted-foreground">answer below</span>
            </div>
            <p className="text-sm font-medium">{question.text}</p>
            {question.options.length > 0 && (
              <div className="grid gap-2 sm:grid-cols-2">
                {question.options.map((o, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    className="h-auto justify-start whitespace-normal py-2 text-left text-sm"
                    disabled={busy}
                    onClick={() => onAnswer(o)}
                  >
                    <span className="mr-2 font-semibold text-primary">
                      {String.fromCharCode(65 + i)}
                    </span>
                    {o}
                  </Button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        <Textarea
          rows={2}
          value={draft}
          placeholder={
            awaiting
              ? "Type your answer… (Enter to send)"
              : "Ask a doubt, or press Continue to keep learning"
          }
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(awaiting ? "answer" : "ask");
            }
          }}
          disabled={busy}
        />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => send("answer")} disabled={busy || !draft.trim() || !awaiting}>
            <Send className="h-4 w-4" /> Answer
          </Button>
          <Button variant="outline" onClick={() => send("ask")} disabled={busy || !draft.trim()}>
            <HelpCircle className="h-4 w-4" /> Ask a doubt
          </Button>
          <Button
            variant={awaiting ? "ghost" : "default"}
            onClick={onNext}
            disabled={busy || finished}
            className="ml-auto"
          >
            {awaiting ? "Skip" : "Continue"} <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground">
          phase: <span className="font-medium">{phase}</span>
          {finished && " · lesson complete"}
        </p>
      </div>
    </div>
  );
}

function Bubble({
  message, isLast, activeWordIndex, onReplay,
}: {
  message: ChatMessage;
  isLast: boolean;
  activeWordIndex: number;
  onReplay: (url: string, words: WordTiming[], text: string) => void;
}) {
  const isTeacher = message.role === "teacher";
  const words = message.words || [];
  const highlight = isTeacher && isLast && words.length > 0 && activeWordIndex >= 0;

  return (
    <div className={cn("flex animate-fade-up", isTeacher ? "justify-start" : "justify-end")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg border px-3 py-2 text-sm shadow-sm",
          isTeacher ? "bg-card" : "border-primary bg-primary text-primary-foreground"
        )}
      >
        {message.evaluation && (
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <Badge variant={VERDICT_VARIANT[message.evaluation.verdict] ?? "secondary"}>
              {message.evaluation.verdict} · {(message.evaluation.score * 100).toFixed(0)}%
            </Badge>
            {message.evaluation.misconception && (
              <Badge variant="warning">misconception: {message.evaluation.misconception}</Badge>
            )}
          </div>
        )}

        {highlight ? (
          <p className="leading-relaxed">
            {words.map((w, i) => (
              <span key={i} className={cn(i === activeWordIndex && "word-active")}>
                {w.word}{" "}
              </span>
            ))}
          </p>
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1 border-t pt-2">
            {message.citations.slice(0, 4).map((c) => (
              <Badge key={c.n} variant="outline" title={c.snippet}>
                p.{c.page}{c.section ? ` · ${c.section.slice(0, 24)}` : ""}
              </Badge>
            ))}
          </div>
        )}

        {isTeacher && (
          <button
            className="mt-2 inline-flex items-center gap-1 text-xs opacity-70 hover:opacity-100"
            onClick={() => onReplay(message.audioUrl || "", words, message.text)}
          >
            <Volume2 className="h-3 w-3" /> replay
          </button>
        )}
      </div>
    </div>
  );
}
