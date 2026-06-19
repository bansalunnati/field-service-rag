import api from "@/lib/api";

export const getAnalyticsOverview = async () => {
  const { data } = await api.get("/api/analytics/overview");
  return data;
};

export const getQueryLogs = async (page = 1, pipeline?: string) => {
  const params: Record<string, string | number> = { page, limit: 20 };
  if (pipeline) params.pipeline = pipeline;
  const { data } = await api.get("/api/analytics/queries", { params });
  return data;
};

export const getHitlMetrics = async () => {
  const { data } = await api.get("/api/analytics/hitl");
  return data;
};

export const getPipelineStats = async () => {
  const { data } = await api.get("/api/analytics/pipelines");
  return data;
};
