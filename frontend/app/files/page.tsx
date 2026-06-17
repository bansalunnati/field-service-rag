"use client";

import { useEffect, useState } from "react";
import {
  getFiles,
  uploadFile,
} from "@/services/files";

export default function FilesPage() {
  const [files, setFiles] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  const [pipeline, setPipeline] =
    useState("safety");

  const [loading, setLoading] =
    useState(false);

  const loadFiles = async () => {
    try {
      const data = await getFiles();
      setFiles(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  return (
  <div className="space-y-6">
    <h1 className="text-3xl font-bold">
      File Management
    </h1>

    {/* STEP 4 - Upload UI */}
    <div className="border rounded-lg p-6 space-y-4">
      <input
        type="file"
        onChange={(e) =>
          setSelectedFile(
            e.target.files?.[0] || null
          )
        }
      />

      <select
        value={pipeline}
        onChange={(e) =>
          setPipeline(e.target.value)
        }
        className="border rounded p-2"
      >
        <option value="safety">
          Safety
        </option>

        <option value="equipment">
          Equipment
        </option>

        <option value="field_reports">
          Field Reports
        </option>
      </select>

      <button
        onClick={async () => {
          if (!selectedFile) return;

          try {
            setLoading(true);

            await uploadFile(
              selectedFile,
              pipeline
            );

            await loadFiles();

            alert("Upload complete");
          } catch (error) {
            console.error(error);
          } finally {
            setLoading(false);
          }
        }}
        className="border rounded px-4 py-2"
      >
        {loading
          ? "Uploading..."
          : "Upload"}
      </button>
    </div>

    {/* STEP 5 - Files Table */}
    <div className="border rounded-lg p-6">
      <table className="w-full">
        <thead>
          <tr>
            <th className="text-left">
              File
            </th>

            <th className="text-left">
              Pipeline
            </th>

            <th className="text-left">
              Chunks
            </th>
          </tr>
        </thead>

        <tbody>
          {files.map((file) => (
            <tr key={file.id}>
              <td>{file.filename}</td>
              <td>{file.pipeline}</td>
              <td>{file.chunk_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);
}
