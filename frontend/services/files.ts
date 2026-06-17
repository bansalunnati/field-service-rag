import api from "@/lib/api";

export const getFiles = async () => {
  const res = await api.get("/ingest/files");
  return res.data;
};

export const uploadFile = async (
  file: File,
  pipeline: string
) => {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("pipeline", pipeline);

  const res = await api.post(
    "/ingest/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return res.data;
};