import api from "@/lib/api";

export const evaluateQuery = async (queryLogId: string) => {
  const { data } = await api.post(`/api/ragas/evaluate/${queryLogId}`);
  return data;
};

export const getRagasScores = async (page = 1) => {
  const { data } = await api.get("/api/ragas/scores", { params: { page, limit: 20 } });
  return data;
};

export const getRagasSummary = async () => {
  const { data } = await api.get("/api/ragas/summary");
  return data;
};
