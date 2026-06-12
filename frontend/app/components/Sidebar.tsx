"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus, LogOut, Wrench } from "lucide-react";
import { getSessions, createSession } from "../lib/api";
import { useAuth } from "../lib/auth-context";

interface Session {
  id: string;
  title?: string;
  created_at?: string;
}

export default function Sidebar({
  activeSessionId,
  onSelectSession,
}: {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
}) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const { logout } = useAuth();
  const pathname = usePathname();

  const loadSessions = async () => {
    try {
      const res = await getSessions();
      setSessions(res.data);
    } catch {
      setSessions([]);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleNewChat = async () => {
    const res = await createSession();
    const newId = res.data.id;
    setSessions((prev) => [res.data, ...prev]);
    onSelectSession(newId);
  };

  return (
    <aside className="w-64 h-screen bg-[var(--surface)] border-r border-[var(--border)] flex flex-col">
      <div className="p-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={16} className="text-[var(--accent)]" />
          <span className="font-mono-tech text-xs tracking-widest text-[var(--accent)]">
            FIELD-SERVICE
          </span>
        </div>
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-md py-2 text-sm hover:border-[var(--accent)] transition-colors"
        >
          <Plus size={14} />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelectSession(s.id)}
            className={`w-full text-left px-3 py-2 rounded-md text-sm truncate transition-colors ${
              activeSessionId === s.id
                ? "bg-[var(--surface-2)] text-[var(--text)]"
                : "text-[var(--muted)] hover:bg-[var(--surface-2)]"
            }`}
          >
            {s.title || "New conversation"}
          </button>
        ))}
      </div>

      <div className="p-2 border-t border-[var(--border)] space-y-1">
        <Link
          href="/admin"
          className={`block px-3 py-2 rounded-md text-sm transition-colors ${
            pathname === "/admin"
              ? "bg-[var(--surface-2)] text-[var(--text)]"
              : "text-[var(--muted)] hover:bg-[var(--surface-2)]"
          }`}
        >
          Document upload
        </Link>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-[var(--muted)] hover:bg-[var(--surface-2)] transition-colors"
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </aside>
  );
}