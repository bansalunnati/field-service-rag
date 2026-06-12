import axios from "axios";
import Cookies from "js-cookie";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = Cookies.get("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      Cookies.remove("token");
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---- Auth ----
// NOTE: adjust these paths to match backend/app/auth/router.py exactly
export const loginUser = (email: string, password: string) =>
  api.post("/auth/login", { email, password });

export const registerUser = (email: string, password: string, name?: string) =>
  api.post("/auth/register", { email, password, name });

// ---- Chat ----
// NOTE: adjust these paths to match backend/app/chat/router.py exactly
export const getSessions = () => api.get("/chat/sessions");

export const createSession = () => api.post("/chat/sessions");

export const getMessages = (sessionId: string) =>
  api.get(`/chat/sessions/${sessionId}/messages`);

export const sendMessage = (sessionId: string, message: string) =>
  api.post(`/chat/sessions/${sessionId}/messages`, { message });

// ---- Ingestion (admin upload) ----
// NOTE: adjust this path to match backend/app/ingestion/ingest_router.py
export const uploadDocument = (file: File, category: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  return api.post("/ingestion/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export default api;