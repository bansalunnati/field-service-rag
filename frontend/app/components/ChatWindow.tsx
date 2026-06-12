"use client";

import { useEffect, useRef, useState } from "react";
import { getMessages, sendMessage } from "../lib/api";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

interface Message {
  role: "user" | "assistant";
  content: string;
  pipeline?: "general" | "policy" | "technical";
}

export default function ChatWindow({ sessionId }: { sessionId: string | null }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    getMessages(sessionId)
      .then((res) => setMessages(res.data))
      .catch(() => setMessages([]));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text: string) => {
    if (!sessionId) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);
    try {
      const res = await sendMessage(sessionId, text);
      // adjust field names (answer / source_pipeline) to match your backend response
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.data.answer,
          pipeline: res.data.source_pipeline,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center text-[var(--muted)] text-sm">
        Select or start a new chat to begin.
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-screen">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-[var(--muted)]">
            Ask a question about a policy, procedure, or technical issue. The assistant will
            route it to the right knowledge base automatically.
          </p>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {sending && (
          <p className="font-mono-tech text-xs text-[var(--muted)]">Routing and retrieving...</p>
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}