"use client";

import { useState } from "react";
import Sidebar from "../components/Sidebar";
import UploadPanel from "../components/UploadPanel";

export default function AdminPage() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  return (
    <div className="flex">
      <Sidebar activeSessionId={activeSessionId} onSelectSession={setActiveSessionId} />
      <div className="flex-1 p-8">
        <h1 className="text-xl font-semibold mb-1">Document ingestion</h1>
        <p className="text-sm text-[var(--muted)] mb-6">
          Add documents to the General, Policy, or Technical knowledge bases.
        </p>
        <UploadPanel />
      </div>
    </div>
  );
}