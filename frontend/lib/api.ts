import axios from "axios";
import { useAuthStore } from "@/store/auth-store";

if (!process.env.NEXT_PUBLIC_API_URL) {
  console.warn(
    "[api] NEXT_PUBLIC_API_URL is not set — falling back to http://localhost:8000 (dev only)"
  );
}

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;