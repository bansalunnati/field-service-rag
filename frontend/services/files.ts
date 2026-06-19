import api from "@/lib/api";

export const getFiles = async () => {
  const res = await api.get("/api/ingest/files");
  return res.data;
};

export const uploadFile = async (file: File, pipeline: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("pipeline", pipeline);
  const res = await api.post("/api/ingest/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};
