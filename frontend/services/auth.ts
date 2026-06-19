import api from "@/lib/api";

export async function login(username: string, password: string) {
  const params = new URLSearchParams();
  params.append("username", username);
  params.append("password", password);

  const response = await api.post("/api/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });

  return response.data;
}
