import api from "@/lib/api";

export interface Task {
  id: string;
  title: string;
  description: string;
  assigned_to: string | null;
  status: "open" | "in_progress" | "done";
  priority: "low" | "medium" | "high";
  due_date: string | null;
  created_at: string;
  report_id: string;
}

export const getTasks = async (): Promise<Task[]> => {
  const { data } = await api.get("/api/tasks");
  return data;
};

export const createTask = async (payload: {
  title: string;
  description?: string;
  assigned_to?: string;
  priority?: string;
  due_date?: string;
  report_id?: string;
}) => {
  const { data } = await api.post("/api/tasks", payload);
  return data;
};

export const updateTaskStatus = async (
  taskId: string,
  status: string
) => {
  const { data } = await api.patch(`/api/tasks/${taskId}/status`, { status });
  return data;
};

export const deleteTask = async (taskId: string) => {
  await api.delete(`/api/tasks/${taskId}`);
};
