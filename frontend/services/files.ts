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

export const previewFile = async (fileId: string) => {
  const res = await api.get(`/api/ingest/files/${fileId}/view`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(res.data);
  window.open(url, "_blank", "noopener,noreferrer");
};
