"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { submitReport, getMyReports, previewReport } from "@/services/reports";
import { Upload, Loader2, Eye } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  under_review: "bg-blue-100 text-blue-700",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

const REPORT_TYPES: { value: string; label: string }[] = [
  { value: "hazmat_inspection", label: "Hazmat Inspection" },
  { value: "tower_sop", label: "Tower SOP" },
  { value: "equipment_fault", label: "Equipment Fault" },
  { value: "safety_incident", label: "Safety Incident" },
  { value: "other", label: "Other" },
];

export default function EmployeeReportsPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [reportType, setReportType] = useState("other");
  const [submitResult, setSubmitResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const { notify } = useConfirmDialog();

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

  const load = async () => {
    try {
      const data = await getMyReports();
      setReports(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSubmit = async () => {
    const file = fileRef.current?.files?.[0];
    if (!title.trim() || !file) {
      await notify("Title and file are required", { title: "Missing information" });
      return;
    }
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const fd = new FormData();
      fd.append("title", title);
      fd.append("report_type", reportType);
      fd.append("file", file);
      await submitReport(fd);
      setTitle("");
      setReportType("other");
      if (fileRef.current) fileRef.current.value = "";
      setSubmitResult("Report submitted successfully. It is now under review.");
      await load();
    } catch {
      setSubmitResult("Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Field Reports</h1>

      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">Submit New Report</h2>
          <div className="space-y-3">
            <input
              className="w-full rounded border px-3 py-2 text-sm bg-background"
              placeholder="Report title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  Report Type
                </label>
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value)}
                  className="rounded border px-3 py-2 text-sm bg-background"
                >
                  {REPORT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  Attach Report File (PDF, DOCX, TXT, PNG, JPG)
                  <span className="ml-1 rounded bg-primary/10 text-primary px-1.5 py-0.5 text-[10px] font-medium">
                    field_reports pipeline
                  </span>
                  <span className="ml-1 rounded bg-amber-100 text-amber-700 px-1.5 py-0.5 text-[10px] font-medium">
                    images OCR&apos;d automatically
                  </span>
                </label>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
                  className="text-sm"
                />
              </div>
            </div>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Upload size={15} />
              )}
              Submit Report
            </button>
            {submitResult && (
              <p
                className={`text-sm rounded px-3 py-2 ${
                  submitResult.includes("success")
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-red-50 text-red-700"
                }`}
              >
                {submitResult}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">My Submissions</h2>
          {loading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : reports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No reports submitted yet.</p>
          ) : (
            <div className="space-y-2">
              {reports.map((r: any) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-lg border px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium flex items-center gap-2">
                      {r.title}
                      {r.ocr_used && (
                        <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-medium">
                          OCR
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {r.report_type} ·{" "}
                      {r.submitted_at
                        ? new Date(r.submitted_at).toLocaleDateString()
                        : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
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
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
