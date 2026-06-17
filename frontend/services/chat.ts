import api from "@/lib/api";

export const getSessions = async () => {
  const res = await api.get("/chat/sessions");
  return res.data;
};

export const createSession = async () => {
  const res = await api.post("/chat/sessions", {
    pipeline: "safety",
    title: "New Chat",
  });

  return res.data;
};

export const getMessages = async (sessionId: string) => {
  const res = await api.get(
    `/chat/sessions/${sessionId}/messages`
  );

  return res.data;
};

export const sendMessage = async (
  sessionId: string,
  question: string
) => {
  const res = await api.post(
    `/chat/sessions/${sessionId}/query`,
    { question }
  );

  return res.data;
};