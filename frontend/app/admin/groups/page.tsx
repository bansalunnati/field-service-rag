"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  getGroups,
  createGroup,
  deleteGroup,
  getGroupDetails,
  removeMember,
  addMembersBatch,
  searchEmployees,
} from "@/services/groups";
import { Loader2, Trash2, Plus, UserMinus, X } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

interface Employee {
  id: string;
  email: string;
}

/** Live-search employee picker with multi-select — type a few characters
 * of an email to see matches, click to add multiple before submitting. */
function EmployeePicker({
  selected,
  onChange,
  excludeIds = [],
}: {
  selected: Employee[];
  onChange: (next: Employee[]) => void;
  excludeIds?: string[];
}) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Employee[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const results = await searchEmployees(query.trim());
        const selectedIds = new Set([...selected.map((s) => s.id), ...excludeIds]);
        setSuggestions(results.filter((r) => !selectedIds.has(r.id)));
        setOpen(true);
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const addEmployee = (emp: Employee) => {
    onChange([...selected, emp]);
    setQuery("");
    setSuggestions([]);
    setOpen(false);
  };

  const removeEmployee = (id: string) => {
    onChange(selected.filter((s) => s.id !== id));
  };

  return (
    <div ref={boxRef} className="relative">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-1.5">
          {selected.map((emp) => (
            <span
              key={emp.id}
              className="flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs"
            >
              {emp.email}
              <button onClick={() => removeEmployee(emp.id)} className="hover:text-destructive">
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        className="w-full rounded border px-3 py-2 text-sm bg-background"
        placeholder="Type an email to search employees…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
      />
      {open && suggestions.length > 0 && (
        <div className="absolute z-10 mt-1 w-full rounded border bg-background shadow-md max-h-48 overflow-y-auto">
          {suggestions.map((s) => (
            <button
              key={s.id}
              onClick={() => addEmployee(s)}
              className="block w-full text-left px-3 py-2 text-sm hover:bg-muted"
            >
              {s.email}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function GroupsPage() {
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<any>(null);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [initialMembers, setInitialMembers] = useState<Employee[]>([]);
  const [membersToAdd, setMembersToAdd] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [addingMembers, setAddingMembers] = useState(false);
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
    const details = await getGroupDetails(id);
    setSelectedGroup(details);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const group = await createGroup(name, desc);
      if (initialMembers.length > 0) {
        try {
          await addMembersBatch(group.id, initialMembers.map((m) => m.id));
        } catch {
          await notify("Group created but some members could not be added.", {
            title: "Member add failed",
            destructive: true,
          });
        }
      }
      setName("");
      setDesc("");
      setInitialMembers([]);
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
    await load();
  };

  const handleAddMembers = async () => {
    if (membersToAdd.length === 0) return;
    setAddingMembers(true);
    try {
      await addMembersBatch(selectedGroup.id, membersToAdd.map((m) => m.id));
      setMembersToAdd([]);
      await loadGroup(selectedGroup.id);
      await load();
    } catch {
      await notify("Could not add the selected members.", { destructive: true });
    } finally {
      setAddingMembers(false);
    }
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
                    Add members (optional)
                  </label>
                  <EmployeePicker selected={initialMembers} onChange={setInitialMembers} />
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
                <div className="flex gap-2 mb-3 items-start">
                  <div className="flex-1">
                    <EmployeePicker
                      selected={membersToAdd}
                      onChange={setMembersToAdd}
                      excludeIds={(selectedGroup.members ?? []).map((m: any) => m.user_id)}
                    />
                  </div>
                  <button
                    onClick={handleAddMembers}
                    disabled={addingMembers || membersToAdd.length === 0}
                    className="flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground hover:opacity-90 disabled:opacity-50 shrink-0"
                  >
                    {addingMembers ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                    Add {membersToAdd.length > 0 ? `(${membersToAdd.length})` : ""}
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
