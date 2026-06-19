"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getRagasScores, getRagasSummary, evaluateQuery } from "@/services/ragas";
import { getQueryLogs } from "@/services/analytics";
import { FlaskConical, Loader2 } from "lucide-react";

const METRICS = [
  { key: "faithfulness",      label: "Faithfulness",       color: "text-blue-500" },
  { key: "answer_relevancy",  label: "Answer Relevancy",   color: "text-emerald-500" },
  { key: "context_precision", label: "Context Precision",  color: "text-amber-500" },
  { key: "context_recall",    label: "Context Recall",     color: "text-violet-500" },
] as const;

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function ScoreBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-muted-foreground">—</span>;
  const pctVal = value * 100;
  const color =
    pctVal >= 75 ? "text-emerald-600" : pctVal >= 50 ? "text-amber-600" : "text-destructive";
  return <span className={`text-xs font-medium ${color}`}>{pct(value)}</span>;
}

export default function RagasPage() {
  const [summary, setSummary] = useState<any>(null);
  const [scores, setScores] = useState<any>(null);
  const [logs, setLogs] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [evaluating, setEvaluating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async (p = 1) => {
    setLoading(true);
    setError(null);
    try {
      const [s, sc, l] = await Promise.all([
        getRagasSummary(),
        getRagasScores(p),
        getQueryLogs(1),
      ]);
      setSummary(s);
      setScores(sc);
      setLogs(l);
      setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleEvaluate = async (queryLogId: string) => {
    setEvaluating(queryLogId);
    setError(null);
    try {
      await evaluateQuery(queryLogId);
      await load(page);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Evaluation failed");
    } finally {
      setEvaluating(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <FlaskConical size={22} className="text-primary" />
        <h1 className="text-2xl font-bold">RAGAS Evaluation</h1>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Avg metric stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {METRICS.map(({ key, label, color }) => (
          <Card key={key}>
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground">{label}</p>
              {loading || !summary ? (
                <div className="mt-2 h-9 w-20 animate-pulse rounded bg-muted" />
              ) : (
                <p className={`mt-2 text-3xl font-bold ${color}`}>
                  {pct((summary as any)[key])}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent evaluations table */}
      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">
            Recent Evaluations
            {summary && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ({summary.total_evaluations} total)
              </span>
            )}
          </h2>

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : (scores?.items ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No evaluations yet. Use the table below to trigger one.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Question</th>
                      <th className="pb-2 font-medium">Pipeline</th>
                      <th className="pb-2 font-medium text-blue-500">Faith.</th>
                      <th className="pb-2 font-medium text-emerald-500">Ans. Rel.</th>
                      <th className="pb-2 font-medium text-amber-500">Ctx. Prec.</th>
                      <th className="pb-2 font-medium text-violet-500">Ctx. Rec.</th>
                      <th className="pb-2 font-medium">Evaluated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(scores.items as any[]).map((s) => (
                      <tr key={s.id} className="hover:bg-muted/40 transition">
                        <td className="py-2 max-w-xs">
                          <p className="truncate text-xs">{s.question ?? "—"}</p>
                        </td>
                        <td className="py-2">
                          <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium capitalize">
                            {s.pipeline ?? "—"}
                          </span>
                        </td>
                        <td className="py-2"><ScoreBadge value={s.faithfulness} /></td>
                        <td className="py-2"><ScoreBadge value={s.answer_relevancy} /></td>
                        <td className="py-2"><ScoreBadge value={s.context_precision} /></td>
                        <td className="py-2"><ScoreBadge value={s.context_recall} /></td>
                        <td className="py-2 text-xs text-muted-foreground whitespace-nowrap">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-4 text-sm">
                <span className="text-muted-foreground">
                  Page {page} · {scores.total} total
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => load(page - 1)}
                    disabled={page <= 1}
                    className="rounded border px-3 py-1 text-xs disabled:opacity-40 hover:bg-muted"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() => load(page + 1)}
                    disabled={page * 20 >= scores.total}
                    className="rounded border px-3 py-1 text-xs disabled:opacity-40 hover:bg-muted"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Trigger evaluation from recent query logs */}
      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-1">Trigger Evaluation</h2>
          <p className="text-xs text-muted-foreground mb-4">
            Select a recent query log to run RAGAS metrics on it.
          </p>

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : (logs?.items ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No query logs available.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Time</th>
                    <th className="pb-2 font-medium">Pipeline</th>
                    <th className="pb-2 font-medium">Question</th>
                    <th className="pb-2 font-medium">Ground Truth</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(logs.items as any[]).map((log: any) => (
                    <tr key={log.id} className="hover:bg-muted/40 transition">
                      <td className="py-2 text-xs text-muted-foreground whitespace-nowrap">
                        {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                      </td>
                      <td className="py-2">
                        <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium capitalize">
                          {log.pipeline}
                        </span>
                      </td>
                      <td className="py-2 max-w-xs">
                        <p className="truncate text-xs">{log.question}</p>
                      </td>
                      <td className="py-2 text-xs">
                        {log.ground_truth ? (
                          <span className="text-emerald-600 font-medium">Set</span>
                        ) : (
                          <span className="text-muted-foreground">None</span>
                        )}
                      </td>
                      <td className="py-2">
                        <button
                          onClick={() => handleEvaluate(log.id)}
                          disabled={evaluating === log.id || !!log.error}
                          className="flex items-center gap-1 rounded border px-3 py-1 text-xs hover:bg-muted disabled:opacity-40"
                        >
                          {evaluating === log.id ? (
                            <><Loader2 size={12} className="animate-spin" /> Running…</>
                          ) : (
                            "Evaluate"
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
