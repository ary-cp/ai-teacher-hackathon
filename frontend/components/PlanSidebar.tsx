"use client";

import { CheckCircle2, Circle, Clock, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { LessonPlan } from "@/lib/types";

interface Props {
  plan: LessonPlan;
  stepIndex: number;
  percent: number;
  mastery: Record<string, number>;
}

export function PlanSidebar({ plan, stepIndex, percent, mastery }: Props) {
  return (
    <Card>
      <CardHeader className="space-y-2">
        <CardTitle className="text-base">{plan.topic}</CardTitle>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="secondary">{plan.subject}</Badge>
          <Badge variant="secondary">{plan.level}</Badge>
          <Badge variant="secondary">{plan.language}</Badge>
          <Badge variant="outline"><Clock className="mr-1 h-3 w-3" />{plan.total_minutes} min</Badge>
        </div>
        <Progress value={percent} />
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">{plan.summary}</p>

        <ol className="space-y-2">
          {plan.steps.map((s, i) => {
            const done = i < stepIndex;
            const active = i === stepIndex;
            const score = mastery[s.title];
            return (
              <li
                key={s.id}
                className={cn(
                  "rounded-md border p-2.5 text-sm transition-colors",
                  active && "border-primary bg-primary/5",
                  done && "opacity-70"
                )}
              >
                <div className="flex items-start gap-2">
                  {done ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                  ) : active ? (
                    <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
                  ) : (
                    <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0">
                    <div className="font-medium leading-tight">{s.title}</div>
                    <div className="text-xs text-muted-foreground">{s.objective}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge variant="outline">{s.minutes} min</Badge>
                      <Badge variant="outline">{s.visual_hint}</Badge>
                      {typeof score === "number" && (
                        <Badge variant={score >= 0.7 ? "success" : score >= 0.4 ? "warning" : "danger"}>
                          mastery {(score * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        {plan.prerequisites.length > 0 && (
          <div className="border-t pt-3">
            <div className="text-xs font-medium text-muted-foreground">Prerequisites</div>
            <ul className="mt-1 space-y-1 text-xs">
              {plan.prerequisites.map((p) => <li key={p}>· {p}</li>)}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
