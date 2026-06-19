import api from "@/lib/api";

export const getHitlQueue = async () => {
  const res = await api.get("/api/hitl/queue");
  return res.data;
};

export const approveReport = async (reportId: string, notes: string) => {
  const res = await api.patch(`/api/hitl/${reportId}/approve`, { notes });
  return res.data;
};

export const rejectReport = async (reportId: string, notes: string) => {
  const res = await api.patch(`/api/hitl/${reportId}/reject`, { notes });
  return res.data;
};
