import api from "@/lib/api";

export const getSessions = async () => {
  const res = await api.get("/api/chat/sessions");
  return res.data;
};

export const createSession = async (
  pipeline = "safety",
  title = "New Chat"
) => {
  const res = await api.post("/api/chat/sessions", { pipeline, title });
  return res.data;
};

export const getMessages = async (sessionId: string) => {
  const res = await api.get(`/api/chat/sessions/${sessionId}/messages`);
  return res.data;
};

export const sendMessage = async (sessionId: string, question: string) => {
  const res = await api.post(`/api/chat/sessions/${sessionId}/query`, {
    question,
  });
  return res.data;
};

export const deleteSession = async (sessionId: string) => {
  await api.delete(`/api/chat/sessions/${sessionId}`);
};
