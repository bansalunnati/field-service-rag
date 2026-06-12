"use client";

import { useState } from "react";
import Sidebar from "../components/Sidebar";
import ChatWindow from "../components/ChatWindow";

export default function ChatPage() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  return (
    <div className="flex">
      <Sidebar activeSessionId={activeSessionId} onSelectSession={setActiveSessionId} />
      <ChatWindow sessionId={activeSessionId} />
    </div>
  );
}