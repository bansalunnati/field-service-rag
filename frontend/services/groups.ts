import api from "@/lib/api";

export const getGroups = async () => {
  const res = await api.get("/groups");
  return res.data;
};

export const createGroup = async (
  name: string,
  description: string
) => {
  const res = await api.post("/groups", {
    name,
    description,
  });

  return res.data;
};

export const deleteGroup = async (groupId: string) => {
  await api.delete(`/groups/${groupId}`);
};

export const getGroupDetails = async (groupId: string) => {
  const res = await api.get(`/groups/${groupId}`);
  return res.data;
};

export const addMember = async (
  groupId: string,
  userId: string
) => {
  const res = await api.post(
    `/groups/${groupId}/members`,
    {
      user_id: userId,
    }
  );

  return res.data;
};

export const removeMember = async (
  groupId: string,
  userId: string
) => {
  await api.delete(
    `/groups/${groupId}/members/${userId}`
  );
};