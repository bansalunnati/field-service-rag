"use client";

import { useEffect, useState } from "react";
import ChatWindow from "@/components/chat/ChatWindow";
import HistorySidebar from "@/components/chat/HistorySidebar";
import {
  createSession,
  sendMessage,
  getSessions,
  getMessages,
} from "@/services/chat";
import api from "@/lib/api";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";

export default function AdminChatPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const { notify } = useConfirmDialog();

  const loadSessions = async () => {
    const data = await getSessions();
    setSessions(data);
  };

  const loadMessages = async (id: string) => {
    const data = await getMessages(id);
    setMessages(data);
    setSessionId(id);
  };

  const handleNewChat = async () => {
    const session = await createSession("safety", "New Chat");
    await loadSessions();
    setSessionId(session.id);
    setMessages([]);
  };

  const handleDelete = async (id: string) => {
    await api.delete(`/api/chat/sessions/${id}`);
    await loadSessions();
    if (sessionId === id) {
      setSessionId(null);
      setMessages([]);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    setLoading(true);

    let sid = sessionId;
    if (!sid) {
      const session = await createSession("safety", input.slice(0, 40));
      sid = session.id;
      setSessionId(sid);
      await loadSessions();
    }

    const userMsg = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);

    try {
      const result = await sendMessage(sid!, userMsg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.answer, citations: result.citations },
      ]);
    } catch {
      await notify("Query failed", { destructive: true });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 rounded-xl border overflow-hidden">
      {/* Sidebar */}
      <div className="w-60 shrink-0 border-r overflow-y-auto">
        <HistorySidebar
          sessions={sessions}
          activeSessionId={sessionId}
          onSelectSession={loadMessages}
          onNewChat={handleNewChat}
          onDeleteSession={handleDelete}
        />
      </div>

      {/* Chat */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow
          messages={messages}
          inputValue={input}
          onInputChange={setInput}
          onSend={handleSend}
          loading={loading}
          placeholder="Ask the policy assistant…"
        />
      </div>
    </div>
  );
}
