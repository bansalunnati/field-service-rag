import api from "@/lib/api";

export const submitReport = async (
  formData: FormData
) => {
  const res = await api.post(
    "/reports/submit",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return res.data;
};

export const getMyReports = async () => {
  const res = await api.get("/reports/my");
  return res.data;
};

export const getAllReports = async () => {
  const res = await api.get("/reports/all");
  return res.data;
};

export const reviewReport = async (
  reportId: string,
  decision: "approved" | "rejected",
  notes: string
) => {
  const res = await api.patch(
    `/reports/${reportId}/hitl`,
    {
      decision,
      notes,
    }
  );

  return res.data;
};