"use client";

import { Award, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { LearningReport } from "@/lib/types";

export function ReportCard({ report }: { report: LearningReport }) {
  return (
    <Card className="border-emerald-500/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Award className="h-4 w-4 text-emerald-500" /> Learning report
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div>
          <div className="mb-1 flex justify-between text-xs text-muted-foreground">
            <span>Overall score</span>
            <span className="font-semibold text-foreground">{report.score_percent}%</span>
          </div>
          <Progress value={report.score_percent} />
        </div>

        {report.strong_areas.length > 0 && (
          <Row label="Strong" items={report.strong_areas} variant="success" />
        )}
        {report.weak_areas.length > 0 && (
          <Row label="Needs work" items={report.weak_areas} variant="warning" />
        )}
        {report.misconceptions.length > 0 && (
          <Row label="Misconceptions" items={report.misconceptions} variant="danger" />
        )}

        {report.recommendation && (
          <p className="rounded-md bg-secondary p-2.5 text-xs">{report.recommendation}</p>
        )}

        {report.next_topics.length > 0 && (
          <div>
            <div className="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
              <TrendingUp className="h-3 w-3" /> Learn next
            </div>
            <ol className="space-y-1 text-xs">
              {report.next_topics.map((t, i) => <li key={i}>{i + 1}. {t}</li>)}
            </ol>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Row({
  label, items, variant,
}: { label: string; items: string[]; variant: "success" | "warning" | "danger" }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted-foreground">{label}</div>
      <div className="flex flex-wrap gap-1">
        {items.map((i) => <Badge key={i} variant={variant}>{i}</Badge>)}
      </div>
    </div>
  );
}
