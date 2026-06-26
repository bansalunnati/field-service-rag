"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getHitlQueue, approveReport, rejectReport } from "@/services/hitl";
import { previewReport } from "@/services/reports";
import { CheckCircle, XCircle, Loader2, Eye } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

export default function HitlPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const { notify } = useConfirmDialog();

  const handlePreview = async (reportId: string) => {
    setPreviewingId(reportId);
    try {
      await previewReport(reportId);
    } catch {
      await notify("Preview failed. The file may no longer be available.", { destructive: true });
    } finally {
      setPreviewingId(null);
    }
  };

  const load = async () => {
    try {
      const data = await getHitlQueue();
      setQueue(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDecision = async (
    reviewId: string,
    decision: "approved" | "rejected"
  ) => {
    setProcessing(reviewId);
    try {
      if (decision === "approved") {
        await approveReport(reviewId, notes[reviewId] ?? "");
      } else {
        await rejectReport(reviewId, notes[reviewId] ?? "");
      }
      await load();
    } catch {
      await notify("Action failed", { destructive: true });
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">HITL Review Center</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {queue.length} report{queue.length !== 1 ? "s" : ""} pending review
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : queue.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No reports pending review.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {queue.map((item: any) => {
            const reportId = item.report_id ?? item.id;
            return (
              <Card key={item.review_id ?? reportId}>
                <CardContent className="p-5">
                  <div className="min-w-0">
                    <p className="font-semibold truncate">
                      {item.title ?? "Untitled Report"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Status: {item.status ?? ""} ·{" "}
                      {item.submitted_at
                        ? new Date(item.submitted_at).toLocaleString()
                        : ""}
                    </p>
                    {item.hitl_reason && (
                      <p className="text-xs text-amber-700 mt-1.5 bg-amber-50 rounded px-2 py-1">
                        Escalated: {item.hitl_reason}
                      </p>
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => handlePreview(reportId)}
                      disabled={previewingId === reportId}
                      className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm hover:bg-muted/40 disabled:opacity-50"
                    >
                      {previewingId === reportId ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Eye size={14} />
                      )}
                      Preview
                    </button>
                    <input
                      className="flex-1 min-w-40 rounded border px-3 py-1.5 text-sm bg-background"
                      placeholder="Reviewer notes (optional)"
                      value={notes[reportId] ?? ""}
                      onChange={(e) =>
                        setNotes((prev) => ({ ...prev, [reportId]: e.target.value }))
                      }
                    />
                    <button
                      onClick={() => handleDecision(reportId, "approved")}
                      disabled={processing === reportId}
                      className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:opacity-90 disabled:opacity-50"
                    >
                      {processing === reportId ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <CheckCircle size={14} />
                      )}
                      Approve
                    </button>
                    <button
                      onClick={() => handleDecision(reportId, "rejected")}
                      disabled={processing === reportId}
                      className="flex items-center gap-1.5 rounded-lg bg-destructive px-4 py-2 text-sm text-white hover:opacity-90 disabled:opacity-50"
                    >
                      <XCircle size={14} />
                      Reject
                    </button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
