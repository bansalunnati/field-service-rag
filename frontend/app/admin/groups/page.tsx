"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  getGroups,
  createGroup,
  deleteGroup,
  getGroupDetails,
  removeMember,
  addMember,
} from "@/services/groups";
import api from "@/lib/api";
import { Loader2, Trash2, Plus, UserMinus, UserPlus } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

const PIPELINES = ["equipment", "safety", "field_reports"];

export default function GroupsPage() {
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<any>(null);
  const [groupAccess, setGroupAccess] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [initialMember, setInitialMember] = useState("");
  const [addEmail, setAddEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { confirm, notify } = useConfirmDialog();

  const load = async () => {
    try {
      const data = await getGroups();
      setGroups(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const loadGroup = async (id: string) => {
    const [details, access] = await Promise.all([
      getGroupDetails(id),
      api.get(`/api/access/${id}`).then((r) => r.data),
    ]);
    setSelectedGroup(details);
    setGroupAccess(access.pipelines ?? []);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const group = await createGroup(name, desc);
      if (initialMember.trim()) {
        try {
          await addMember(group.id, initialMember.trim());
        } catch {
          // group created, member add failed — surface below
          await notify(`Group created but could not add member: user '${initialMember}' not found.`, {
            title: "Member not added",
            destructive: true,
          });
        }
      }
      setName("");
      setDesc("");
      setInitialMember("");
      await load();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await confirm("Delete group?", { title: "Delete group", confirmLabel: "Delete", destructive: true });
    if (!ok) return;
    await deleteGroup(id);
    if (selectedGroup?.id === id) setSelectedGroup(null);
    await load();
  };

  const handleRemoveMember = async (userId: string) => {
    await removeMember(selectedGroup.id, userId);
    await loadGroup(selectedGroup.id);
  };

  const handleAddMember = async () => {
    if (!addEmail.trim()) return;
    try {
      await addMember(selectedGroup.id, addEmail.trim());
      setAddEmail("");
      await loadGroup(selectedGroup.id);
    } catch {
      await notify("User not found or already a member.", { destructive: true });
    }
  };

  const handleTogglePipeline = async (pipeline: string, currently: boolean) => {
    if (currently) {
      await api.delete(`/api/access/${selectedGroup.id}/${pipeline}`);
    } else {
      await api.post(`/api/access/${selectedGroup.id}/${pipeline}`);
    }
    await loadGroup(selectedGroup.id);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Group Management</h1>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Left — create + list */}
        <div className="space-y-4">
          <Card>
            <CardContent className="p-5">
              <h2 className="font-semibold mb-3">Create Group</h2>
              <div className="space-y-2">
                <input
                  className="w-full rounded border px-3 py-2 text-sm bg-background"
                  placeholder="Group name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <input
                  className="w-full rounded border px-3 py-2 text-sm bg-background"
                  placeholder="Description (optional)"
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                />
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">
                    Add initial member (email, optional)
                  </label>
                  <input
                    className="w-full rounded border px-3 py-2 text-sm bg-background"
                    placeholder="employee@company.com"
                    value={initialMember}
                    onChange={(e) => setInitialMember(e.target.value)}
                  />
                </div>
                <button
                  onClick={handleCreate}
                  disabled={saving || !name.trim()}
                  className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  Create
                </button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <h2 className="font-semibold mb-3">All Groups</h2>
              {loading ? (
                <div className="space-y-2">
                  {[1, 2].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-muted" />)}
                </div>
              ) : groups.length === 0 ? (
                <p className="text-sm text-muted-foreground">No groups yet.</p>
              ) : (
                <div className="space-y-1">
                  {groups.map((g) => (
                    <div
                      key={g.id}
                      className={`flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer hover:bg-muted transition ${selectedGroup?.id === g.id ? "bg-primary/10" : ""}`}
                      onClick={() => loadGroup(g.id)}
                    >
                      <div>
                        <p className="text-sm font-medium">{g.name}</p>
                        <p className="text-xs text-muted-foreground">{g.member_count ?? 0} members</p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(g.id); }}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right — group details */}
        {selectedGroup ? (
          <div className="space-y-4">
            <Card>
              <CardContent className="p-5">
                <h2 className="font-semibold mb-3">{selectedGroup.name} — Members</h2>
                <div className="flex gap-2 mb-3">
                  <input
                    className="flex-1 rounded border px-3 py-1.5 text-sm bg-background"
                    placeholder="User email to add"
                    value={addEmail}
                    onChange={(e) => setAddEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleAddMember()}
                  />
                  <button
                    onClick={handleAddMember}
                    className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:opacity-90"
                  >
                    <UserPlus size={13} /> Add
                  </button>
                </div>
                {(selectedGroup.members ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">No members yet.</p>
                ) : (
                  <div className="space-y-1">
                    {selectedGroup.members.map((m: any) => (
                      <div
                        key={m.user_id}
                        className="flex items-center justify-between rounded px-2 py-1.5 hover:bg-muted text-sm"
                      >
                        <div>
                          <span className="font-medium">{m.email}</span>
                          <span className="ml-2 text-xs text-muted-foreground capitalize">{m.role}</span>
                        </div>
                        <button
                          onClick={() => handleRemoveMember(m.user_id)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <UserMinus size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-5">
                <h2 className="font-semibold mb-3">Pipeline Access</h2>
                <div className="space-y-2">
                  {PIPELINES.map((pl) => {
                    const granted = groupAccess.some((a: any) => a.pipeline === pl && a.granted);
                    return (
                      <label
                        key={pl}
                        className="flex items-center gap-3 rounded px-2 py-1.5 hover:bg-muted cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={granted}
                          onChange={() => handleTogglePipeline(pl, granted)}
                          className="h-4 w-4 rounded"
                        />
                        <span className="text-sm capitalize">{pl.replace(/_/g, " ")}</span>
                      </label>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="flex items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground h-40">
            Select a group to manage members and access
          </div>
        )}
      </div>
    </div>
  );
}
