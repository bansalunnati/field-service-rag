"use client";

import { useEffect, useState, useRef } from "react";
import {
  createSession,
  sendMessage,
  getSessions,
  getMessages,
} from "@/services/chat";

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (error) {
      console.error(error);
    }
  };

  const loadMessages = async (id: string) => {
    try {
      const data = await getMessages(id);
      setSessionId(id);
      setMessages(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  const handleSend = async () => {
  if (!message.trim()) return;

  try {
    setLoading(true);

    let currentSession = sessionId;

    if (!currentSession) {
      const session = await createSession();

      currentSession = session.id;
      setSessionId(session.id);

      await loadSessions();
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: message,
      },
    ]);

    const userQuestion = message;
    setMessage("");

    if (!currentSession) {
      throw new Error("Session creation failed");
    }

    const response = await sendMessage(
      currentSession,
      userQuestion
    );

    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: response.answer,
      },
    ]);
  } catch (error) {
    console.error(error);
    alert("Failed to send message");
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="h-[80vh] flex">
      {/* Sidebar */}
      <div className="w-72 border-r p-4">
        <button
          onClick={async () => {
            const session = await createSession();
            await loadSessions();
            setSessionId(session.id);
            setMessages([]);
          }}
          className="w-full border rounded p-2 mb-4"
        >
          + New Chat
        </button>

        <div className="space-y-2">
          {sessions.map((session: any) => (
            <div
              key={session.id}
              onClick={() => loadMessages(session.id)}
              className={`border rounded p-2 cursor-pointer ${
                sessionId === session.id
                  ? "bg-blue-100"
                  : "hover:bg-gray-100"
              }`}
            >
              <div className="font-medium">{session.title}</div>
              <div className="text-xs text-gray-500">{session.pipeline}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col p-4">
        <h1 className="text-3xl font-bold mb-4">Chat Assistant</h1>

        <div className="flex-1 border rounded-lg p-4 overflow-y-auto">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`mb-4 flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[70%] rounded-lg px-4 py-2 ${
                  msg.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100"
                }`}
              >
                <strong>{msg.role === "user" ? "You" : "Assistant"}:</strong>{" "}
                {msg.content}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        <div className="flex gap-2 mt-4">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) {
                handleSend();
              }
            }}
            placeholder="Ask a question..."
            className="flex-1 border rounded px-3 py-2"
          />

          <button
            onClick={handleSend}
            disabled={loading}
            className="border rounded px-4"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
