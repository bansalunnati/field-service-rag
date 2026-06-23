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

export const sendMessage = async (
  sessionId: string,
  question: string,
  attachedText?: string,
  attachedFilename?: string
) => {
  const res = await api.post(`/api/chat/sessions/${sessionId}/query`, {
    question,
    attached_text: attachedText,
    attached_filename: attachedFilename,
  });
  return res.data;
};

export const uploadChatFile = async (sessionId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post(
    `/api/chat/sessions/${sessionId}/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data as { filename: string; extracted_text: string };
};

export const attachReportToChat = async (sessionId: string, reportId: string) => {
  const res = await api.post(
    `/api/chat/sessions/${sessionId}/upload?report_id=${encodeURIComponent(reportId)}`,
    new FormData()
  );
  return res.data as { filename: string; extracted_text: string };
};

export const deleteSession = async (sessionId: string) => {
  await api.delete(`/api/chat/sessions/${sessionId}`);
};
