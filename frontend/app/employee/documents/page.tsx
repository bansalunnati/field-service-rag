"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getFiles } from "@/services/files";
import { FileText, Eye, Loader2 } from "lucide-react";
import api from "@/lib/api";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

const FILE_TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  docx: "Word",
  txt: "Text",
  csv: "CSV",
  md: "Markdown",
};

export default function EmployeeDocumentsPage() {
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewing, setViewing] = useState<string | null>(null);
  const { notify } = useConfirmDialog();

  useEffect(() => {
    getFiles()
      .then(setFiles)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleView = async (fileId: string) => {
    setViewing(fileId);
    try {
      const res = await api.get(`/api/ingest/files/${fileId}/view`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const win = window.open(url, "_blank");
      // revoke after the tab has had time to load
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      if (!win) await notify("Pop-up blocked — please allow pop-ups for this site.", { destructive: true });
    } catch {
      await notify("Could not open file. You may not have permission.", { destructive: true });
    } finally {
      setViewing(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Documents</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Documents your team has been granted access to. Read-only.
        </p>
      </div>

      <Card>
        <CardContent className="p-5">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
            </div>
          ) : files.length === 0 ? (
            <div className="py-12 text-center">
              <FileText size={36} className="mx-auto text-muted-foreground mb-3" />
              <p className="font-medium">No documents assigned yet.</p>
              <p className="text-sm text-muted-foreground mt-1">
                Your administrator hasn't granted your team access to any documents.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {files.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center gap-4 rounded-lg border px-4 py-3 hover:bg-muted/40 transition"
                >
                  <FileText size={18} className="shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{f.original_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      <span className="capitalize">{f.pipeline.replace(/_/g, " ")}</span>
                      {" · "}
                      <span>{FILE_TYPE_LABELS[f.file_type] ?? f.file_type.toUpperCase()}</span>
                      {" · "}
                      <span>{f.chunk_count} sections</span>
                    </p>
                  </div>
                  {f.viewable ? (
                    <button
                      onClick={() => handleView(f.id)}
                      disabled={viewing === f.id}
                      className="flex items-center gap-1.5 shrink-0 rounded-lg bg-primary/10 text-primary px-3 py-1.5 text-xs font-medium hover:bg-primary/20 transition disabled:opacity-50"
                    >
                      {viewing === f.id
                        ? <Loader2 size={13} className="animate-spin" />
                        : <Eye size={13} />}
                      View
                    </button>
                  ) : (
                    <span className="text-xs text-muted-foreground shrink-0">Not viewable</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
