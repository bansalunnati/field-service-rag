"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getFiles } from "@/services/files";
import { getGroups } from "@/services/groups";
import api from "@/lib/api";
import { FileText, Users, CheckCircle, XCircle } from "lucide-react";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

export default function AssignFilesPage() {
  const [files, setFiles] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] = useState<any>(null);
  const [fileGrants, setFileGrants] = useState<any[]>([]); // groups that have access to selected file
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const { notify } = useConfirmDialog();

  const load = async () => {
    try {
      const [f, g] = await Promise.all([getFiles(), getGroups()]);
      setFiles(f);
      setGroups(g);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const loadFileGrants = async (fileId: string) => {
    const { data } = await api.get(`/api/ingest/files/${fileId}/access`);
    setFileGrants(data); // [{group_id, group_name}]
  };

  const handleSelectFile = async (file: any) => {
    setSelectedFile(file);
    await loadFileGrants(file.id);
  };

  const isGranted = (groupId: string) =>
    fileGrants.some((g) => g.group_id === groupId);

  const handleToggle = async (groupId: string) => {
    if (!selectedFile) return;
    setToggling(groupId);
    try {
      if (isGranted(groupId)) {
        await api.delete(`/api/ingest/files/${selectedFile.id}/access/${groupId}`);
      } else {
        await api.post(`/api/ingest/files/${selectedFile.id}/access/${groupId}`);
      }
      await loadFileGrants(selectedFile.id);
    } catch {
      await notify("Action failed", { destructive: true });
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Assign Files to Groups</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Control which groups can view each uploaded document.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Left — file list */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-3 flex items-center gap-2">
              <FileText size={16} /> Uploaded Documents
            </h2>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-muted" />)}
              </div>
            ) : files.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No documents uploaded yet. Go to{" "}
                <a href="/admin/documents" className="text-primary hover:underline">Documents</a>{" "}
                to upload one.
              </p>
            ) : (
              <div className="space-y-1">
                {files.map((f) => (
                  <div
                    key={f.id}
                    onClick={() => handleSelectFile(f)}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 cursor-pointer hover:bg-muted transition ${
                      selectedFile?.id === f.id ? "bg-primary/10 ring-1 ring-primary/20" : ""
                    }`}
                  >
                    <FileText size={15} className="shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{f.original_name}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {f.pipeline} · {f.chunk_count} chunks
                      </p>
                    </div>
                    {selectedFile?.id === f.id && (
                      <span className="text-xs text-primary font-medium shrink-0">Selected</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right — group access toggles */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-1 flex items-center gap-2">
              <Users size={16} /> Group Access
            </h2>
            {!selectedFile ? (
              <div className="flex items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground h-40 mt-3">
                Select a document on the left
              </div>
            ) : (
              <>
                <p className="text-xs text-muted-foreground mb-4 truncate">
                  File: <span className="font-medium text-foreground">{selectedFile.original_name}</span>
                </p>
                {groups.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No groups yet. Go to{" "}
                    <a href="/admin/groups" className="text-primary hover:underline">Groups</a>{" "}
                    to create one.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {groups.map((g) => {
                      const granted = isGranted(g.id);
                      const busy = toggling === g.id;
                      return (
                        <div
                          key={g.id}
                          className={`flex items-center justify-between rounded-lg border px-4 py-3 transition ${
                            granted ? "border-emerald-200 bg-emerald-50/50" : "hover:bg-muted/50"
                          }`}
                        >
                          <div>
                            <p className="text-sm font-medium">{g.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {g.member_count ?? 0} members
                            </p>
                          </div>
                          <button
                            onClick={() => handleToggle(g.id)}
                            disabled={busy}
                            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                              granted
                                ? "bg-emerald-100 text-emerald-700 hover:bg-red-100 hover:text-red-700"
                                : "bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary"
                            } disabled:opacity-50`}
                          >
                            {granted ? (
                              <>
                                <CheckCircle size={13} /> Granted
                              </>
                            ) : (
                              <>
                                <XCircle size={13} /> No Access
                              </>
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
