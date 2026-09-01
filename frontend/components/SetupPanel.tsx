"use client";

import { useRef, useState } from "react";
import { FileUp, GraduationCap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import type { DocumentMeta, Level, StudentProfile } from "@/lib/types";

interface Props {
  doc: DocumentMeta | null;
  busy: boolean;
  onUpload: (file: File) => void;
  onStart: (profile: StudentProfile, topic: string, instruction: string) => void;
}

const LANGUAGES = ["hinglish", "hindi", "english", "bengali", "tamil", "telugu", "marathi", "gujarati", "kannada", "malayalam", "punjabi", "urdu", "spanish", "french"];

export function SetupPanel({ doc, busy, onUpload, onStart }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("Student");
  const [level, setLevel] = useState<Level>("beginner");
  const [language, setLanguage] = useState("hinglish");
  const [minutes, setMinutes] = useState(20);
  const [goal, setGoal] = useState("");
  const [topic, setTopic] = useState("");
  const [instruction, setInstruction] = useState(
    "I am a beginner. Teach me this in 20 minutes in Hinglish with simple examples. Ask me questions during the lesson and test me at the end."
  );

  const start = () =>
    onStart(
      {
        name: name || "Student",
        level,
        language,
        minutes: Number(minutes) || 20,
        goal,
        style: "friendly, example-first",
        prior_knowledge: "",
      },
      topic,
      instruction
    );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <GraduationCap className="h-4 w-4" /> Start a lesson
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label>Learning material (optional — RAG mode)</Label>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.pptx,.txt,.md"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          />
          <Button
            variant="outline"
            className="mt-1 w-full justify-start"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            <FileUp className="h-4 w-4" />
            {doc ? doc.filename : "Upload PDF / DOCX / PPTX"}
          </Button>
          {doc && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="success">{doc.pages} pages</Badge>
              <Badge variant="secondary">{doc.chunks} chunks indexed</Badge>
              {doc.outline.slice(0, 2).map((o) => (
                <Badge key={o} variant="outline" className="max-w-full truncate">{o}</Badge>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Your name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label>Level</Label>
            <Select value={level} onChange={(e) => setLevel(e.target.value as Level)} className="mt-1">
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </Select>
          </div>
          <div>
            <Label>Teaching language</Label>
            <Select value={language} onChange={(e) => setLanguage(e.target.value)} className="mt-1">
              {LANGUAGES.map((l) => (
                <option key={l} value={l}>{l[0].toUpperCase() + l.slice(1)}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Time available (min)</Label>
            <Input
              type="number" min={3} max={600} value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))} className="mt-1"
            />
          </div>
        </div>

        <div>
          <Label>Topic (leave empty to teach from the document)</Label>
          <Input
            value={topic} onChange={(e) => setTopic(e.target.value)} className="mt-1"
            placeholder="e.g. Chapter 4 — Electricity, or 'Teach me React hooks'"
          />
        </div>

        <div>
          <Label>Tell the teacher what you need</Label>
          <Textarea
            value={instruction} onChange={(e) => setInstruction(e.target.value)}
            className="mt-1" rows={3}
          />
        </div>

        <div>
          <Label>Goal (optional)</Label>
          <Input
            value={goal} onChange={(e) => setGoal(e.target.value)} className="mt-1"
            placeholder="exam revision / interview prep"
          />
        </div>

        <Button className="w-full" onClick={start} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}
          Begin lesson
        </Button>
      </CardContent>
    </Card>
  );
}
