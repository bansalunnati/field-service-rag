import api from "@/lib/api";

export const getNotifications = async () => {
  const res = await api.get("/api/notifications");
  return res.data;
};

export const markRead = async (id: string) => {
  const res = await api.patch(`/api/notifications/${id}/read`);
  return res.data;
};

export const markAllRead = async () => {
  const res = await api.patch("/api/notifications/read-all");
  return res.data;
};
