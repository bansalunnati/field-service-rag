"use client";

import { useState } from "react";
import { UploadCloud, CheckCircle2, XCircle } from "lucide-react";
import { uploadDocument } from "../lib/api";

export default function UploadPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("general");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    try {
      await uploadDocument(file, category);
      setStatus("success");
      setFile(null);
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="max-w-lg bg-[var(--surface)] border border-[var(--border)] rounded-lg p-6 space-y-4">
      <div>
        <label className="block text-sm text-[var(--muted)] mb-1">Knowledge base</label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-3 py-2 text-sm"
        >
          <option value="general">General</option>
          <option value="policy">Policy</option>
          <option value="technical">Technical</option>
        </select>
      </div>

      <div>
        <label className="block text-sm text-[var(--muted)] mb-1">Document</label>
        <label className="flex flex-col items-center justify-center gap-2 border border-dashed border-[var(--border)] rounded-md py-8 cursor-pointer hover:border-[var(--accent)] transition-colors">
          <UploadCloud size={24} className="text-[var(--muted)]" />
          <span className="text-sm text-[var(--muted)]">
            {file ? file.name : "Click to choose a PDF, DOCX, or TXT file"}
          </span>
          <input
            type="file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
      </div>

      <button
        onClick={handleUpload}
        disabled={!file || status === "uploading"}
        className="w-full bg-[var(--accent)] text-black font-medium rounded-md py-2 text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {status === "uploading" ? "Ingesting..." : "Upload and ingest"}
      </button>

      {status === "success" && (
        <p className="flex items-center gap-2 text-sm text-green-400">
          <CheckCircle2 size={14} /> Document ingested successfully.
        </p>
      )}
      {status === "error" && (
        <p className="flex items-center gap-2 text-sm text-red-400">
          <XCircle size={14} /> Upload failed. Check the file and try again.
        </p>
      )}
    </div>
  );
}