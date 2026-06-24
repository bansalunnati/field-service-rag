"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getTasks, createTask, updateTaskStatus, deleteTask } from "@/services/tasks";
import { Plus, Trash2, Loader2, AlertTriangle } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  pending_review: "bg-purple-100 text-purple-700",
  done: "bg-emerald-100 text-emerald-700",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "text-muted-foreground",
  medium: "text-amber-500",
  high: "text-destructive",
};

export default function AdminTasksPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    title: "",
    description: "",
    assigned_to: "",
    priority: "medium",
    due_date: "",
  });
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const { confirm, notify } = useConfirmDialog();

  const load = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      await createTask({
        title: form.title,
        description: form.description,
        assigned_to: form.assigned_to || undefined,
        priority: form.priority,
        due_date: form.due_date || undefined,
      });
      setForm({ title: "", description: "", assigned_to: "", priority: "medium", due_date: "" });
      setShowForm(false);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.message ?? "Failed to create task";
      await notify(detail, { title: "Error", destructive: true });
    } finally {
      setSaving(false);
    }
  };

  const handleStatus = async (id: string, status: string) => {
    await updateTaskStatus(id, status);
    await load();
  };

  const handleDelete = async (id: string) => {
    const ok = await confirm("Delete task?", { title: "Delete task", confirmLabel: "Delete", destructive: true });
    if (!ok) return;
    await deleteTask(id);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Task Assignment</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90"
        >
          <Plus size={15} /> New Task
        </button>
      </div>

      {/* Warn about open tasks with no assignee */}
      {!loading && tasks.some((t) => !t.assigned_to && t.status !== "done") && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" />
          <span>
            <span className="font-medium">
              {tasks.filter((t) => !t.assigned_to && t.status !== "done").length} task(s)
            </span>{" "}
            have no assignee. Assign them below so employees are notified.
          </span>
        </div>
      )}

      {showForm && (
        <Card>
          <CardContent className="p-5 space-y-3">
            <h2 className="font-semibold">Create Task</h2>
            <input
              className="w-full rounded border px-3 py-2 text-sm bg-background"
              placeholder="Title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <textarea
              className="w-full rounded border px-3 py-2 text-sm bg-background"
              rows={2}
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <div className="flex flex-wrap gap-3">
              <input
                className="flex-1 min-w-40 rounded border px-3 py-2 text-sm bg-background"
                placeholder="Assign to (user email)"
                value={form.assigned_to}
                onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
              />
              <select
                className="rounded border px-3 py-2 text-sm bg-background"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <input
                type="date"
                className="rounded border px-3 py-2 text-sm bg-background"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              />
            </div>
            <button
              onClick={handleCreate}
              disabled={saving || !form.title.trim()}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              Save Task
            </button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-5">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tasks yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">ID</th>
                    <th className="pb-2 font-medium">Title</th>
                    <th className="pb-2 font-medium">Assigned To</th>
                    <th className="pb-2 font-medium">Priority</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Due</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {tasks.map((t: any) => (
                    <tr key={t.id} className="hover:bg-muted/40 transition">
                      <td className="py-2.5">
                        <button
                          type="button"
                          title={`Click to copy full ID: ${t.id}`}
                          onClick={() => navigator.clipboard?.writeText(t.id)}
                          className="font-mono text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                        >
                          {t.id?.slice(0, 8)}
                        </button>
                      </td>
                      <td className="py-2.5">
                        <p className="font-medium truncate max-w-xs">{t.title}</p>
                        {t.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-xs">
                            {t.description}
                          </p>
                        )}
                      </td>
                      <td className="py-2.5 text-muted-foreground">
                        {t.assigned_to_email ?? "Unassigned"}
                      </td>
                      <td className="py-2.5">
                        <span className={`font-medium capitalize ${PRIORITY_COLORS[t.priority]}`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <select
                          value={t.status}
                          onChange={(e) => handleStatus(t.id, e.target.value)}
                          className={`rounded-full px-2 py-0.5 text-xs font-medium border-0 cursor-pointer ${STATUS_COLORS[t.status]}`}
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In Progress</option>
                          <option value="pending_review">Pending Review</option>
                          <option value="done">Done</option>
                        </select>
                      </td>
                      <td className="py-2.5 text-muted-foreground text-xs">
                        {t.due_date ? new Date(t.due_date).toLocaleDateString() : "—"}
                      </td>
                      <td className="py-2.5">
                        <button
                          onClick={() => handleDelete(t.id)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 size={14} />
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
