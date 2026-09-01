"use client";

import { useMemo } from "react";
import { Languages, Sparkles } from "lucide-react";
import { Avatar3D } from "@/components/Avatar3D";
import { ChatPanel } from "@/components/ChatPanel";
import { PlanSidebar } from "@/components/PlanSidebar";
import { ReportCard } from "@/components/ReportCard";
import { SetupPanel } from "@/components/SetupPanel";
import { VisualBoard } from "@/components/VisualBoard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTeacher } from "@/hooks/useTeacher";

const QUICK_LANGUAGES = ["hinglish", "hindi", "english"];

export default function Home() {
  const t = useTeacher();
  const finished = t.phase === "report" || t.phase === "done";

  const headerBadges = useMemo(() => {
    if (!t.plan) return null;
    return (
      <div className="hidden items-center gap-1.5 md:flex">
        <Badge variant="secondary">{t.plan.subject}</Badge>
        <Badge variant="secondary">{t.plan.level}</Badge>
        <Badge variant="outline">
          step {Math.min(t.progress.step_index + 1, t.progress.total_steps || 1)}/
          {t.progress.total_steps || t.plan.steps.length}
        </Badge>
      </div>
    );
  }, [t.plan, t.progress]);

  return (
    <main className="mx-auto flex h-screen w-full max-w-[1800px] flex-col gap-4 p-4 lg:p-4 overflow-hidden bg-muted/20">
      <header className="flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">AI Teacher</h1>
            <p className="text-xs font-medium text-muted-foreground/80">
              Understand → Plan → Explain → Question → Evaluate → Adapt
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {headerBadges}
          {t.sessionId && (
            <div className="flex items-center gap-1 bg-background/50 backdrop-blur px-2 py-1.5 rounded-lg border">
              <Languages className="h-4 w-4 text-muted-foreground mr-2" />
              {QUICK_LANGUAGES.map((l) => (
                <Button
                  key={l}
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs px-2.5 hover:bg-primary/10 hover:text-primary"
                  disabled={t.busy}
                  onClick={() => t.switchLanguage(l)}
                >
                  {l.toUpperCase()}
                </Button>
              ))}
            </div>
          )}
        </div>
      </header>

      {t.error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive shrink-0 shadow-sm">
          {t.error}
        </div>
      )}

      <div className="grid flex-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)_380px] min-h-0">
        {/* left: setup + plan */}
        <div className="flex flex-col gap-4 overflow-y-auto board-scroll pr-1 pb-4">
          {!t.plan && (
            <SetupPanel doc={t.doc} busy={t.busy} onUpload={t.upload} onStart={t.start} />
          )}
          {t.plan && (
            <PlanSidebar
              plan={t.plan}
              stepIndex={t.progress.step_index}
              percent={t.progress.percent}
              mastery={t.progress.mastery}
            />
          )}
          {t.report && <ReportCard report={t.report} />}
        </div>

        {/* center: massive 3D stage with floating board */}
        <div className="relative rounded-2xl overflow-hidden shadow-2xl border bg-black flex min-h-[400px]">
          <div className="absolute inset-0">
            <Avatar3D
              levelRef={t.audio.levelRef}
              speaking={t.audio.playing}
              muted={t.audio.muted}
              onToggleMute={t.audio.toggleMute}
              getAudioStream={t.audio.getAudioStream}
              phase={t.phase}
              stepTitle={t.plan?.steps[t.progress.step_index]?.title}
            />
          </div>
          
          {t.board && t.board.kind !== "none" && (
            <div className="absolute bottom-6 left-6 right-6 z-10 lg:w-[600px] lg:right-auto transition-all duration-500 animate-in slide-in-from-bottom-8 opacity-100">
              <div className="rounded-xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] border border-white/10 bg-background/95 backdrop-blur-xl">
                <VisualBoard board={t.board} />
              </div>
            </div>
          )}
        </div>

        {/* right: conversation */}
        <div className="flex flex-col rounded-2xl border bg-card shadow-xl overflow-hidden min-h-[500px] p-4">
          <ChatPanel
            messages={t.messages}
            question={t.question}
            phase={t.phase}
            busy={t.busy}
            finished={finished}
            activeWordIndex={t.audio.wordIndex}
            onAnswer={t.answer}
            onAsk={t.ask}
            onNext={t.next}
            onReplay={(url, words, text) => t.audio.play(url, words, text)}
          />
        </div>
      </div>
    </main>
  );
}
