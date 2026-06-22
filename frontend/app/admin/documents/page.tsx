"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getFiles, uploadFile } from "@/services/files";
import { Upload, FileText, ToggleLeft, ToggleRight, Loader2, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

interface UploadedFile {
  id: string;
  filename: string;
  original_name: string;
  pipeline: string;
  chunk_count: number;
  file_type: string;
  uploaded_at: string;
  is_active?: boolean;
  ocr_used?: boolean;
  ocr_confidence?: number | null;
  status?: "ready" | "processing" | "failed";
  error_message?: string | null;
}

const PIPELINES = ["equipment", "safety", "field_reports"];

export default function DocumentsPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [pipeline, setPipeline] = useState("safety");
  const fileRef = useRef<HTMLInputElement>(null);
  const { confirm, notify } = useConfirmDialog();

  const load = async () => {
    try {
      const data = await getFiles();
      setFiles(Array.isArray(data) ? data : []);
    } catch {
      // 401 before login hydration — silently ignore, interceptor will retry
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // While any file is still being OCR'd in the background, poll for updates
  // so the chunk count / status flips from "Processing" to ready without
  // the admin needing to manually refresh.
  useEffect(() => {
    const hasProcessing = files.some((f) => f.status === "processing");
    if (!hasProcessing) return;
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [files]);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadFile(file, pipeline);
      await load();
      if (fileRef.current) fileRef.current.value = "";
      if (result?.status === "processing") {
        await notify(result.message, { title: "Processing in background" });
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.message ?? "Upload failed";
      await notify(detail, { title: "Upload failed", destructive: true });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    const ok = await confirm(`Delete "${name}"? This cannot be undone.`, {
      title: "Delete document",
      confirmLabel: "Delete",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api.delete(`/api/ingest/files/${id}`);
      setFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err: any) {
      await notify(err?.response?.data?.detail ?? "Delete failed", {
        title: "Delete failed",
        destructive: true,
      });
    }
  };

  const handleToggle = async (id: string) => {
    try {
      await api.patch(`/api/ingest/files/${id}/toggle`);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, is_active: !(f.is_active ?? true) } : f
        )
      );
    } catch {
      await notify("Toggle failed", { title: "Error", destructive: true });
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Document Management</h1>

      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">Upload Document</h2>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Pipeline
              </label>
              <select
                value={pipeline}
                onChange={(e) => setPipeline(e.target.value)}
                className="rounded border px-3 py-2 text-sm bg-background"
              >
                {PIPELINES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                File (PDF, DOCX, TXT, CSV, MD, PNG, JPG)
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.txt,.csv,.md,.png,.jpg,.jpeg"
                className="text-sm"
              />
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {uploading ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Upload size={15} />
              )}
              Upload
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <h2 className="font-semibold mb-4">Uploaded Files</h2>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : files.length === 0 ? (
            <p className="text-sm text-muted-foreground">No files uploaded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Name</th>
                    <th className="pb-2 font-medium">Pipeline</th>
                    <th className="pb-2 font-medium">Chunks</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium">OCR</th>
                    <th className="pb-2 font-medium">Uploaded</th>
                    <th className="pb-2 font-medium">Active</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {files.map((f) => (
                    <tr key={f.id} className="hover:bg-muted/40 transition">
                      <td className="py-2 flex items-center gap-2">
                        <FileText size={14} className="shrink-0 text-muted-foreground" />
                        <span className="truncate max-w-xs">{f.original_name}</span>
                      </td>
                      <td className="py-2">
                        <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
                          {f.pipeline}
                        </span>
                      </td>
                      <td className="py-2">
                        {f.status === "processing" ? (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                            <Loader2 size={12} className="animate-spin" /> Processing…
                          </span>
                        ) : f.status === "failed" ? (
                          <span
                            className="text-xs text-destructive cursor-help"
                            title={f.error_message ?? "OCR failed"}
                          >
                            Failed
                          </span>
                        ) : (
                          f.chunk_count
                        )}
                      </td>
                      <td className="py-2 uppercase text-xs text-muted-foreground">
                        {f.file_type}
                      </td>
                      <td className="py-2">
                        {f.ocr_used ? (
                          <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-xs font-medium whitespace-nowrap">
                            OCR {f.ocr_confidence != null ? `${f.ocr_confidence}%` : ""}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {new Date(f.uploaded_at).toLocaleDateString()}
                      </td>
                      <td className="py-2">
                        <button
                          onClick={() => handleToggle(f.id)}
                          title="Toggle active"
                          className="text-muted-foreground hover:text-primary transition"
                        >
                          {(f.is_active ?? true) ? (
                            <ToggleRight size={22} className="text-emerald-500" />
                          ) : (
                            <ToggleLeft size={22} />
                          )}
                        </button>
                      </td>
                      <td className="py-2">
                        <button
                          onClick={() => handleDelete(f.id, f.original_name)}
                          title="Delete file"
                          className="text-muted-foreground hover:text-destructive transition"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
