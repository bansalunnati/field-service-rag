"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getTasks, updateTaskStatus } from "@/services/tasks";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  done: "bg-emerald-100 text-emerald-700",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  done: "Done",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "text-muted-foreground",
  medium: "text-amber-500",
  high: "text-destructive",
};

// Next logical status for forward-only progression
const NEXT_STATUS: Record<string, { value: string; label: string } | null> = {
  open: { value: "in_progress", label: "Start" },
  in_progress: { value: "done", label: "Mark Done" },
  done: null,
};

export default function EmployeeTasksPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdvance = async (id: string, nextStatus: string) => {
    setUpdating(id);
    try {
      await updateTaskStatus(id, nextStatus);
      await load();
    } finally {
      setUpdating(null);
    }
  };

  const active = tasks.filter((t) => t.status !== "done");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Tasks</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {active.length} active, {done.length} completed
        </p>
      </div>

      <Card>
        <CardContent className="p-5">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tasks assigned to you.</p>
          ) : (
            <div className="space-y-3">
              {tasks.map((t: any) => {
                const next = NEXT_STATUS[t.status];
                return (
                  <div
                    key={t.id}
                    className={`rounded-lg border px-4 py-3 ${
                      t.status === "done" ? "opacity-60" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{t.title}</p>
                        {t.description && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {t.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-1.5">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[t.status]}`}
                          >
                            {STATUS_LABELS[t.status]}
                          </span>
                          <span
                            className={`text-xs font-medium capitalize ${PRIORITY_COLORS[t.priority]}`}
                          >
                            {t.priority} priority
                          </span>
                          {t.due_date && (
                            <span className="text-xs text-muted-foreground">
                              Due {new Date(t.due_date).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      {next && (
                        <button
                          onClick={() => handleAdvance(t.id, next.value)}
                          disabled={updating === t.id}
                          className="shrink-0 rounded-lg bg-primary/10 text-primary px-3 py-1.5 text-xs font-medium hover:bg-primary/20 transition disabled:opacity-50"
                        >
                          {next.label}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
