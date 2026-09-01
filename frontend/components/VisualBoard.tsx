"use client";

import { useEffect, useRef, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Board } from "@/lib/types";

/**
 * Subject-aware blackboard. The teaching agent picks `kind` from the subject
 * (maths -> formula, programming -> code, history -> timeline, biology ->
 * diagram ...), and this component renders the matching representation.
 */
export function VisualBoard({ board }: { board: Board }) {
  if (!board || board.kind === "none") {
    return null;
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-sm">{board.title || "Board"}</CardTitle>
        <Badge variant="secondary">{board.kind}</Badge>
      </CardHeader>
      <CardContent className="board-scroll max-h-[46vh] overflow-auto">
        <BoardBody board={board} />
        {board.caption && (
          <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">{board.caption}</p>
        )}
      </CardContent>
    </Card>
  );
}

function BoardBody({ board }: { board: Board }) {
  switch (board.kind) {
    case "formula":
      return <Formula latex={board.latex} items={board.items} />;
    case "code":
      return <CodeBlock code={board.code} language={board.language} />;
    case "diagram":
      return <Mermaid chart={board.mermaid} />;
    case "table":
      return <TableView columns={board.columns} rows={board.rows} />;
    case "timeline":
      return <Timeline items={board.items} />;
    case "steps":
      return (
        <ol className="space-y-2">
          {board.items.map((it, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {i + 1}
              </span>
              <span>{it}</span>
            </li>
          ))}
        </ol>
      );
    default:
      return (
        <ul className="space-y-2">
          {board.items.map((it, i) => (
            <li key={i} className="flex gap-2 text-sm">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      );
  }
}

function Formula({ latex, items }: { latex: string; items: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!ref.current || !latex) return;
    try {
      katex.render(latex, ref.current, { displayMode: true, throwOnError: false });
      setErr(false);
    } catch {
      setErr(true);
    }
  }, [latex]);

  return (
    <div>
      <div ref={ref} className="overflow-x-auto py-2" />
      {err && <pre className="text-xs text-muted-foreground">{latex}</pre>}
      {items?.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {items.map((i, k) => <li key={k}>· {i}</li>)}
        </ul>
      )}
    </div>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <div>
      {language && <Badge variant="outline" className="mb-2">{language}</Badge>}
      <pre className="board-scroll overflow-x-auto rounded-md bg-slate-950 p-4 text-xs leading-relaxed text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function Mermaid({ chart }: { chart: string }) {
  const [svg, setSvg] = useState("");
  const idRef = useRef(`mmd-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    let cancelled = false;
    if (!chart) return;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
        const { svg } = await mermaid.render(idRef.current, chart);
        if (!cancelled) setSvg(svg);
      } catch {
        if (!cancelled) setSvg("");
      }
    })();
    return () => { cancelled = true; };
  }, [chart]);

  if (!svg) return <pre className="text-xs text-muted-foreground">{chart}</pre>;
  return <div className="flex justify-center [&_svg]:max-w-full" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function TableView({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            {columns.map((c, i) => <th key={i} className="pb-2 pr-4 font-medium">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b last:border-0">
              {r.map((cell, j) => <td key={j} className="py-2 pr-4">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeline({ items }: { items: string[] }) {
  return (
    <ol className="relative space-y-4 border-l pl-5">
      {items.map((it, i) => (
        <li key={i} className="text-sm">
          <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
          {it}
        </li>
      ))}
    </ol>
  );
}
