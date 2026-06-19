"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  getAnalyticsOverview,
  getQueryLogs,
  getHitlMetrics,
} from "@/services/analytics";
import { BarChart2, Clock, ShieldCheck, Zap } from "lucide-react";

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<any>(null);
  const [hitl, setHitl] = useState<any>(null);
  const [logs, setLogs] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [logPage, setLogPage] = useState(1);

  const load = async (page = 1) => {
    setLoading(true);
    try {
      const [ov, h, l] = await Promise.all([
        getAnalyticsOverview(),
        getHitlMetrics(),
        getQueryLogs(page),
      ]);
      setOverview(ov);
      setHitl(h);
      setLogs(l);
      setLogPage(page);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const maxCount = Math.max(
    1,
    ...(overview?.pipeline_breakdown ?? []).map((p: any) => p.count)
  );

  const PIPELINE_COLORS: Record<string, string> = {
    equipment: "bg-blue-500",
    safety: "bg-emerald-500",
    field_reports: "bg-violet-500",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Performance Dashboard</h1>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          {
            label: "Total Queries",
            value: overview?.total_queries,
            icon: Zap,
            color: "text-blue-500",
          },
          {
            label: "Avg Latency",
            value: overview ? `${overview.avg_latency_ms} ms` : undefined,
            icon: Clock,
            color: "text-amber-500",
          },
          {
            label: "HITL Pending",
            value: overview?.hitl_pending,
            icon: ShieldCheck,
            color: "text-violet-500",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label}>
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">{card.label}</p>
                  <Icon size={18} className={card.color} />
                </div>
                {loading || card.value === undefined ? (
                  <div className="mt-2 h-9 w-24 animate-pulse rounded bg-muted" />
                ) : (
                  <p className="mt-2 text-3xl font-bold">{card.value}</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Pipeline bar chart */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <BarChart2 size={16} /> Queries by Pipeline
            </h2>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-7 animate-pulse rounded bg-muted" />
                ))}
              </div>
            ) : (overview?.pipeline_breakdown ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No data yet.</p>
            ) : (
              <div className="space-y-3">
                {(overview.pipeline_breakdown as any[]).map((p) => (
                  <div key={p.pipeline}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="capitalize font-medium">
                        {p.pipeline.replace("_", " ")}
                      </span>
                      <span className="text-muted-foreground">
                        {p.count} queries · {p.avg_latency_ms} ms avg
                      </span>
                    </div>
                    <div className="h-5 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          PIPELINE_COLORS[p.pipeline] ?? "bg-primary"
                        }`}
                        style={{ width: `${(p.count / maxCount) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* HITL metrics */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <ShieldCheck size={16} /> HITL Metrics
            </h2>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-6 animate-pulse rounded bg-muted" />
                ))}
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                {[
                  ["Total Reviews", hitl?.total_reviews ?? 0],
                  ["Approved", hitl?.approved ?? 0],
                  ["Rejected", hitl?.rejected ?? 0],
                  ["Pending", hitl?.pending ?? 0],
                  ["Avg Review Time", `${hitl?.avg_review_time_hours ?? 0} hrs`],
                ].map(([label, value]) => (
                  <div key={label as string} className="flex justify-between">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-medium">{value}</span>
                  </div>
                ))}

                {hitl && hitl.total_reviews > 0 && (
                  <div className="mt-3">
                    <div className="flex gap-0 rounded-full overflow-hidden h-4">
                      <div
                        className="bg-emerald-500"
                        style={{
                          width: `${(hitl.approved / hitl.total_reviews) * 100}%`,
                        }}
                        title={`Approved: ${hitl.approved}`}
                      />
                      <div
                        className="bg-destructive"
                        style={{
                          width: `${(hitl.rejected / hitl.total_reviews) * 100}%`,
                        }}
                        title={`Rejected: ${hitl.rejected}`}
                      />
                      <div
                        className="bg-muted flex-1"
                        title={`Pending: ${hitl.pending}`}
                      />
                    </div>
                    <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                        Approved
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-destructive" />
                        Rejected
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground" />
                        Pending
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent query logs */}
      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">Recent Query Logs</h2>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : (logs?.items ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No queries logged yet.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Time</th>
                      <th className="pb-2 font-medium">Pipeline</th>
                      <th className="pb-2 font-medium">Question</th>
                      <th className="pb-2 font-medium">Latency</th>
                      <th className="pb-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(logs.items as any[]).map((log) => (
                      <tr key={log.id} className="hover:bg-muted/40 transition">
                        <td className="py-2 text-xs text-muted-foreground whitespace-nowrap">
                          {log.timestamp
                            ? new Date(log.timestamp).toLocaleString()
                            : "—"}
                        </td>
                        <td className="py-2">
                          <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium capitalize">
                            {log.pipeline}
                          </span>
                        </td>
                        <td className="py-2 max-w-sm">
                          <p className="truncate text-xs">{log.question}</p>
                        </td>
                        <td className="py-2 text-xs text-muted-foreground">
                          {log.latency_ms ? `${log.latency_ms} ms` : "—"}
                        </td>
                        <td className="py-2">
                          {log.error ? (
                            <span className="text-xs text-destructive font-medium">Error</span>
                          ) : (
                            <span className="text-xs text-emerald-600 font-medium">OK</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4 text-sm">
                <span className="text-muted-foreground">
                  Page {logPage} · {logs.total} total
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => load(logPage - 1)}
                    disabled={logPage <= 1}
                    className="rounded border px-3 py-1 text-xs disabled:opacity-40 hover:bg-muted"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() => load(logPage + 1)}
                    disabled={logPage * 20 >= logs.total}
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
    </div>
  );
}
