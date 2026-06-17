import api from "@/lib/api";

export const getHitlQueue = async () => {
  const res = await api.get("/hitl/queue");
  return res.data;
};

export const approveReport = async (
  reportId: string,
  notes: string
) => {
  const res = await api.patch(
    `/hitl/${reportId}/approve`,
    { notes }
  );

  return res.data;
};

export const rejectReport = async (
  reportId: string,
  notes: string
) => {
  const res = await api.patch(
    `/hitl/${reportId}/reject`,
    { notes }
  );

  return res.data;
};