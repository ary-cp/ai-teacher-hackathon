"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Video, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Phase } from "@/lib/types";

interface Props {
  levelRef: React.MutableRefObject<number>;
  speaking: boolean;
  muted: boolean;
  onToggleMute: () => void;
  getAudioStream: () => MediaStream | null;
  phase: Phase;
  stepTitle?: string;
}

const PHASE_LABEL: Record<Phase, string> = {
  idle: "Ready", intro: "Introducing", explain: "Teaching", question: "Asking you",
  evaluate: "Checking your answer", remediate: "Re-explaining",
  assessment: "Final quiz", report: "Feedback", done: "Done",
};

/**
 * Canvas-rendered AI teacher.
 * Mouth opening is driven by the live RMS amplitude of the TTS audio, so the
 * avatar speaks in sync with the voice instead of looping a fixed animation.
 * The same canvas is captured (canvas.captureStream + TTS audio track) to
 * export the session as a teaching video.
 */
export function AvatarStage({
  levelRef, speaking, muted, onToggleMute, getAudioStream, phase, stepTitle,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const [recording, setRecording] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = (canvas.width = 520);
    const H = (canvas.height = 420);
    let raf = 0;
    let blink = 0;
    let t = 0;

    const draw = () => {
      t += 1;
      const level = levelRef.current;

      // backdrop
      const g = ctx.createLinearGradient(0, 0, W, H);
      g.addColorStop(0, "#4f46e5");
      g.addColorStop(1, "#7c3aed");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);

      // speaking halo
      if (level > 0.02) {
        ctx.beginPath();
        ctx.arc(W / 2, H / 2 - 10, 150 + level * 45, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${0.05 + level * 0.10})`;
        ctx.fill();
      }

      const bob = Math.sin(t / 45) * 4 + level * 5;
      const cx = W / 2;
      const cy = H / 2 - 12 + bob;

      // shoulders
      ctx.beginPath();
      ctx.ellipse(cx, H + 40, 175, 120, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#1e1b4b";
      ctx.fill();

      // neck
      ctx.fillStyle = "#e8b48c";
      ctx.fillRect(cx - 22, cy + 70, 44, 60);

      // head
      ctx.beginPath();
      ctx.ellipse(cx, cy, 88, 104, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#f2c39c";
      ctx.fill();

      // hair
      ctx.beginPath();
      ctx.ellipse(cx, cy - 62, 90, 56, 0, Math.PI, 0);
      ctx.fillStyle = "#221a17";
      ctx.fill();

      // eyes (with blink)
      blink = blink > 0 ? blink - 1 : Math.random() < 0.006 ? 9 : 0;
      const eyeH = blink > 0 ? 1.5 : 9;
      [-32, 32].forEach((dx) => {
        ctx.beginPath();
        ctx.ellipse(cx + dx, cy - 12, 15, eyeH, 0, 0, Math.PI * 2);
        ctx.fillStyle = "#fff";
        ctx.fill();
        if (blink === 0) {
          ctx.beginPath();
          ctx.arc(cx + dx + Math.sin(t / 120) * 2, cy - 12, 5.5, 0, Math.PI * 2);
          ctx.fillStyle = "#1f2937";
          ctx.fill();
        }
      });

      // brows lift slightly while speaking
      ctx.strokeStyle = "#221a17";
      ctx.lineWidth = 4;
      [-32, 32].forEach((dx) => {
        ctx.beginPath();
        ctx.moveTo(cx + dx - 16, cy - 34 - level * 3);
        ctx.quadraticCurveTo(cx + dx, cy - 42 - level * 5, cx + dx + 16, cy - 34 - level * 3);
        ctx.stroke();
      });

      // nose
      ctx.beginPath();
      ctx.moveTo(cx, cy - 4);
      ctx.lineTo(cx - 8, cy + 20);
      ctx.lineTo(cx + 6, cy + 20);
      ctx.strokeStyle = "#d79b73";
      ctx.lineWidth = 3;
      ctx.stroke();

      // mouth — the lip-sync
      const open = Math.max(3, level * 44);
      const width = 34 + level * 12;
      ctx.beginPath();
      ctx.ellipse(cx, cy + 48, width, open, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#7f1d1d";
      ctx.fill();
      if (open > 10) {
        ctx.beginPath();
        ctx.ellipse(cx, cy + 48 + open * 0.35, width * 0.6, open * 0.3, 0, 0, Math.PI * 2);
        ctx.fillStyle = "#ef7c7c";
        ctx.fill();
      }
      // upper teeth
      ctx.fillStyle = "#fff";
      ctx.fillRect(cx - width * 0.62, cy + 44 - open * 0.5, width * 1.24, Math.min(6, open * 0.4));

      // caption strip
      ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.fillRect(0, H - 46, W, 46);
      ctx.fillStyle = "#fff";
      ctx.font = "600 16px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText((stepTitle || "AI Teacher").slice(0, 52), W / 2, H - 18);

      raf = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(raf);
  }, [levelRef, stepTitle]);

  const toggleRecord = () => {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasStream = canvas.captureStream(30);
    const audioStream = getAudioStream();
    audioStream?.getAudioTracks().forEach((tr) => canvasStream.addTrack(tr));

    const rec = new MediaRecorder(canvasStream, { mimeType: "video/webm" });
    chunksRef.current = [];
    rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ai-teacher-lesson-${Date.now()}.webm`;
      a.click();
      URL.revokeObjectURL(url);
    };
    rec.start();
    recorderRef.current = rec;
    setRecording(true);
  };

  return (
    <div className="relative overflow-hidden rounded-lg border bg-card shadow-sm">
      <canvas ref={canvasRef} className="block h-auto w-full" />
      <div className="absolute left-3 top-3 flex gap-2">
        <Badge variant={speaking ? "success" : "secondary"}>
          {speaking ? "speaking" : PHASE_LABEL[phase]}
        </Badge>
      </div>
      <div className="absolute right-3 top-3 flex gap-2">
        <Button size="icon" variant="secondary" onClick={onToggleMute} title="Mute voice">
          {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </Button>
        <Button
          size="icon"
          variant={recording ? "destructive" : "secondary"}
          onClick={toggleRecord}
          title={recording ? "Stop and download the lesson video" : "Record this lesson as video"}
        >
          {recording ? <Square className="h-4 w-4" /> : <Video className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
