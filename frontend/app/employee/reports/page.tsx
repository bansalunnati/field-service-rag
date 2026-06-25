"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { submitReport, getMyReports, previewReport } from "@/services/reports";
import { getTasks, Task } from "@/services/tasks";
import { Upload, Loader2, Eye, MessageCircle } from "lucide-react";
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
  const router = useRouter();
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [reportType, setReportType] = useState("other");
  const [submitResult, setSubmitResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [taskId, setTaskId] = useState("");
  const { notify } = useConfirmDialog();

  // Only tasks still in progress are valid things to submit a report
  // against — once a task is "done" there's nothing left to attach evidence
  // to, and the AI reviewer needs to know exactly which task a report is
  // for rather than guessing from file content alone.
  const activeTasks = tasks.filter((t) => t.status !== "done");

  // Group submissions by the task they were submitted for, so it's clear
  // at a glance which reports belong to which task instead of one flat list.
  const groupedByTask = useMemo(() => {
    const map = new Map<string, { taskId: string | null; taskTitle: string; reports: any[] }>();
    for (const r of reports) {
      const key = r.task_id ?? "__unlinked__";
      if (!map.has(key)) {
        map.set(key, {
          taskId: r.task_id ?? null,
          taskTitle: r.task_title ?? "No task linked",
          reports: [],
        });
      }
      map.get(key)!.reports.push(r);
    }
    return Array.from(map.values()).sort((a, b) => b.reports.length - a.reports.length);
  }, [reports]);

  const loadTasks = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } finally {
      setTasksLoading(false);
    }
  };

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
    loadTasks();
  }, []);

  const handleSubmit = async () => {
    const file = fileRef.current?.files?.[0];
    if (!taskId) {
      await notify("Choose which task this report is for", { title: "Missing information" });
      return;
    }
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
      fd.append("task_id", taskId);
      fd.append("file", file);
      await submitReport(fd);
      setTitle("");
      setReportType("other");
      setTaskId("");
      if (fileRef.current) fileRef.current.value = "";
      setSubmitResult("Report submitted successfully. It is now under review.");
      await load();
      await loadTasks();
    } catch (err: any) {
      setSubmitResult(err?.response?.data?.detail ?? "Submission failed. Please try again.");
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

          {!tasksLoading && activeTasks.length === 0 ? (
            <p className="text-sm rounded px-3 py-2 bg-amber-50 text-amber-700">
              You have no active tasks assigned right now — there's nothing to submit a
              report for. Ask your admin to assign a task first.
            </p>
          ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Which task is this report for?
              </label>
              <select
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
                disabled={tasksLoading}
                className="w-full rounded border px-3 py-2 text-sm bg-background"
              >
                <option value="">Select an assigned task…</option>
                {activeTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} ({t.status === "in_progress" ? "In Progress" : "Open"})
                  </option>
                ))}
              </select>
            </div>
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
          )}
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
            <div className="space-y-5">
              {groupedByTask.map((group) => (
                <div key={group.taskId ?? "__unlinked__"}>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-sm font-semibold">{group.taskTitle}</h3>
                    {group.taskId && (
                      <span className="font-mono text-[10px] text-muted-foreground">
                        #{group.taskId.slice(0, 8)}
                      </span>
                    )}
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                      {group.reports.length} submission{group.reports.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {group.reports.map((r: any) => (
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
                          {r.ai_summary && (
                            <p className="text-xs text-muted-foreground mt-1 italic">
                              &ldquo;{r.ai_summary}&rdquo;
                            </p>
                          )}
                          {r.matched_sources?.length > 0 && (
                            <p className="text-[11px] text-muted-foreground mt-0.5">
                              Checked against: {r.matched_sources.join(", ")}
                            </p>
                          )}
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
                          {(r.status === "rejected" || r.status === "needs_hitl") && (
                            <button
                              onClick={() => router.push(`/employee/chat?reportId=${r.id}`)}
                              title="Discuss this report's rejection in Policy Chat"
                              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition"
                            >
                              <MessageCircle size={14} />
                              Discuss in Policy Chat
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
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
