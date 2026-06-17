"use client";

import { useEffect, useState } from "react";
import {
  getGroups,
  createGroup,
  deleteGroup,
  getGroupDetails,
  removeMember,
} from "@/services/groups";

interface Group {
  id: string;
  name: string;
  description: string;
  member_count: number;
}

interface Member {
  user_id: string;
  email: string;
  role: string;
}

export default function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroup, setSelectedGroup] =
    useState<any>(null);

  const [name, setName] = useState("");
  const [description, setDescription] =
    useState("");

  const [loading, setLoading] = useState(true);

  const loadGroups = async () => {
    try {
      const data = await getGroups();
      setGroups(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadDetails = async (groupId: string) => {
    const data = await getGroupDetails(groupId);
    setSelectedGroup(data);
  };

  useEffect(() => {
    loadGroups();
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;

    await createGroup(name, description);

    setName("");
    setDescription("");

    loadGroups();
  };

  const handleDelete = async (
    groupId: string
  ) => {
    const confirmed = window.confirm(
      "Delete this group?"
    );

    if (!confirmed) return;

    await deleteGroup(groupId);

    if (
      selectedGroup &&
      selectedGroup.id === groupId
    ) {
      setSelectedGroup(null);
    }

    loadGroups();
  };

  const handleRemoveMember = async (
    groupId: string,
    userId: string
  ) => {
    await removeMember(groupId, userId);

    loadDetails(groupId);
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">
        Group Management
      </h1>

      {/* Create Group */}

      <div className="border rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">
          Create Group
        </h2>

        <input
          className="border p-2 rounded w-full"
          placeholder="Group Name"
          value={name}
          onChange={(e) =>
            setName(e.target.value)
          }
        />

        <textarea
          className="border p-2 rounded w-full"
          placeholder="Description"
          value={description}
          onChange={(e) =>
            setDescription(e.target.value)
          }
        />

        <button
          onClick={handleCreate}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Create Group
        </button>
      </div>

      {/* Groups */}

      <div className="grid md:grid-cols-2 gap-4">
        {groups.map((group) => (
          <div
            key={group.id}
            className="border rounded-xl p-4"
          >
            <h3 className="font-bold text-lg">
              {group.name}
            </h3>

            <p className="text-sm text-gray-500">
              {group.description}
            </p>

            <p className="mt-2">
              Members: {group.member_count}
            </p>

            <div className="flex gap-2 mt-4">
              <button
                onClick={() =>
                  loadDetails(group.id)
                }
                className="px-3 py-1 bg-slate-700 text-white rounded"
              >
                View
              </button>

              <button
                onClick={() =>
                  handleDelete(group.id)
                }
                className="px-3 py-1 bg-red-600 text-white rounded"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Details */}

      {selectedGroup && (
        <div className="border rounded-xl p-4">
          <h2 className="text-xl font-bold mb-4">
            {selectedGroup.name}
          </h2>

          <p>
            {selectedGroup.description}
          </p>

          <h3 className="font-semibold mt-6 mb-3">
            Members
          </h3>

          <div className="space-y-2">
            {selectedGroup.members?.map(
              (member: Member) => (
                <div
                  key={member.user_id}
                  className="flex justify-between border rounded p-3"
                >
                  <div>
                    <p>{member.email}</p>

                    <p className="text-sm text-gray-500">
                      {member.role}
                    </p>
                  </div>

                  <button
                    onClick={() =>
                      handleRemoveMember(
                        selectedGroup.id,
                        member.user_id
                      )
                    }
                    className="bg-red-500 text-white px-3 py-1 rounded"
                  >
                    Remove
                  </button>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}