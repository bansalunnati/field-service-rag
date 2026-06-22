"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getAllReports, previewReport } from "@/services/reports";
import { Eye, Loader2, FileText } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_STYLES: Record<string, string> = {
  under_review: "bg-blue-100 text-blue-700",
  needs_hitl: "bg-amber-100 text-amber-700",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

export default function AdminReportsPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const { notify } = useConfirmDialog();

  const load = async () => {
    try {
      const data = await getAllReports();
      setReports(Array.isArray(data) ? data : []);
    } catch {
      // ignore — interceptor will retry once auth hydrates
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handlePreview = async (id: string) => {
    setPreviewingId(id);
    try {
      await previewReport(id);
    } catch {
      await notify("Preview failed. The file may no longer be available.", { destructive: true });
    } finally {
      setPreviewingId(null);
    }
  };

  const visible = statusFilter === "all" ? reports : reports.filter((r) => r.status === statusFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">All Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every report submitted by employees, with the AI reviewer's verdict and reasoning.
          </p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded border px-3 py-2 text-sm bg-background"
        >
          <option value="all">All statuses</option>
          <option value="under_review">Under review</option>
          <option value="needs_hitl">Needs HITL</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <Card>
        <CardContent className="p-5">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <div className="py-12 text-center">
              <FileText size={36} className="mx-auto text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">No reports match this filter.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {visible.map((r: any) => (
                <div key={r.id} className="rounded-lg border px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium flex items-center gap-2 flex-wrap">
                        {r.title}
                        {r.ocr_used && (
                          <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-medium">
                            OCR
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {r.submitted_by ?? "Unknown submitter"} · {r.report_type} ·{" "}
                        {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${
                          STATUS_STYLES[r.status] ?? "bg-muted"
                        }`}
                      >
                        {r.status.replace("_", " ")}
                      </span>
                      <button
                        onClick={() => handlePreview(r.id)}
                        disabled={previewingId === r.id}
                        title="Preview submitted file"
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition disabled:opacity-50"
                      >
                        {previewingId === r.id ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Eye size={14} />
                        )}
                        Preview
                      </button>
                    </div>
                  </div>

                  {r.ai_summary && (
                    <p className="text-xs text-muted-foreground mt-2 italic">
                      &ldquo;{r.ai_summary}&rdquo;
                    </p>
                  )}
                  {r.hitl_reason && (
                    <p className="text-xs text-amber-700 mt-2 bg-amber-50 rounded px-2 py-1">
                      Escalated: {r.hitl_reason}
                    </p>
                  )}
                  {r.matched_sources?.length > 0 && (
                    <p className="text-[11px] text-muted-foreground mt-1.5">
                      Checked against: {r.matched_sources.join(", ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
