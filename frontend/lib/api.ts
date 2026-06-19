import axios from "axios";
import { useAuthStore } from "@/store/auth-store";

// No baseURL needed — Next.js rewrites /api/* to the backend (see next.config.ts).
// In production: Vercel proxies to BACKEND_URL (server-side env var, set in Vercel dashboard).
// In local dev: proxied to http://localhost:8000 (the default in next.config.ts).
const api = axios.create();

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
