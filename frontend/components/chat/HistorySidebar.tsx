"use client";

import { PlusCircle, MessageSquare, Trash2 } from "lucide-react";

interface Session {
  id: string;
  title: string;
  pipeline: string;
  updated_at: string;
}

interface HistorySidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession?: (id: string) => void;
}

function formatSessionTime(raw: string): string {
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    const sameYear = d.getFullYear() === now.getFullYear();
    return d.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      year: sameYear ? undefined : "numeric",
    });
  } catch {
    return "";
  }
}

export default function HistorySidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: HistorySidebarProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          <PlusCircle size={16} />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {sessions.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            No conversations yet
          </p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              activeSessionId === session.id
                ? "bg-primary/10 text-primary"
                : "hover:bg-muted"
            }`}
            onClick={() => onSelectSession(session.id)}
          >
            <MessageSquare size={14} className="shrink-0 opacity-60" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <span className="truncate font-medium text-xs">{session.title}</span>
                <span className="shrink-0 text-[10px] text-muted-foreground">
                  {formatSessionTime(session.updated_at)}
                </span>
              </div>
            </div>
            {onDeleteSession && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.id);
                }}
                className="hidden group-hover:block shrink-0 text-muted-foreground hover:text-destructive"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
