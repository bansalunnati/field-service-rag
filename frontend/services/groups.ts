import api from "@/lib/api";

export const getGroups = async () => {
  const res = await api.get("/api/groups");
  return res.data;
};

export const createGroup = async (name: string, description: string) => {
  const res = await api.post("/api/groups", { name, description });
  return res.data;
};

export const deleteGroup = async (groupId: string) => {
  await api.delete(`/api/groups/${groupId}`);
};

export const getGroupDetails = async (groupId: string) => {
  const res = await api.get(`/api/groups/${groupId}`);
  return res.data;
};

export const addMember = async (groupId: string, userEmail: string) => {
  const res = await api.post(`/api/groups/${groupId}/members`, {
    user_id: userEmail,
  });
  return res.data;
};

export const removeMember = async (groupId: string, userId: string) => {
  await api.delete(`/api/groups/${groupId}/members/${userId}`);
};
