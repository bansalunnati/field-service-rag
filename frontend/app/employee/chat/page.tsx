"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import ChatWindow from "@/components/chat/ChatWindow";
import HistorySidebar from "@/components/chat/HistorySidebar";
import {
  createSession,
  sendMessage,
  getSessions,
  getMessages,
  deleteSession,
  uploadChatFile,
  attachReportToChat,
} from "@/services/chat";
import api from "@/lib/api";

interface AttachedFile {
  filename: string;
  extracted_text: string;
}

function extractErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const res = (err as any).response;
    if (res?.status === 403) {
      return (
        res.data?.detail ||
        "You don't have access to any documents yet. Please contact your administrator."
      );
    }
    if (res?.data?.detail) return res.data.detail;
  }
  return "Something went wrong. Please try again.";
}

export default function EmployeeChatPage() {
  return (
    <Suspense fallback={null}>
      <EmployeeChatPageInner />
    </Suspense>
  );
}

function EmployeeChatPageInner() {
  const searchParams = useSearchParams();
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [noAccess, setNoAccess] = useState(false);
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);
  const [attaching, setAttaching] = useState(false);

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch {}
  };

  const loadMessages = async (id: string) => {
    try {
      const data = await getMessages(id);
      setMessages(data);
      setSessionId(id);
    } catch {}
  };

  const handleNewChat = async () => {
    try {
      const session = await createSession("safety", "New Chat");
      await loadSessions();
      setSessionId(session.id);
      setMessages([]);
    } catch {}
  };

  const handleSend = async (questionOverride?: string) => {
    const userMsg = (questionOverride ?? input).trim();
    if (!userMsg || loading || noAccess) return;
    setLoading(true);

    let sid = sessionId;
    const attachment = attachedFile;
    try {
      if (!sid) {
        const session = await createSession("safety", userMsg.slice(0, 40));
        sid = session.id;
        setSessionId(sid);
        await loadSessions();
      }

      setInput("");
      setAttachedFile(null);
      setMessages((prev) => [...prev, { role: "user", content: userMsg }]);

      const result = await sendMessage(
        sid!,
        userMsg,
        attachment?.extracted_text,
        attachment?.filename
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          citations: result.citations,
        },
      ]);
    } catch (err) {
      const is403 = (err as any)?.response?.status === 403;
      if (is403) setNoAccess(true);
      const msg = extractErrorMessage(err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: msg, citations: [] },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleAttachFile = async (file: File) => {
    setAttaching(true);
    try {
      let sid = sessionId;
      if (!sid) {
        const session = await createSession("safety", `Re: ${file.name}`);
        sid = session.id;
        setSessionId(sid);
        await loadSessions();
      }
      const result = await uploadChatFile(sid!, file);
      setAttachedFile(result);
    } catch (err) {
      const msg = extractErrorMessage(err);
      setMessages((prev) => [...prev, { role: "assistant", content: msg, citations: [] }]);
    } finally {
      setAttaching(false);
    }
  };

  const handleDeleteSession = async (id: string) => {
    await deleteSession(id);
    await loadSessions();
    if (sessionId === id) {
      setSessionId(null);
      setMessages([]);
      setNoAccess(false);
    }
  };

  useEffect(() => { loadSessions(); }, []);

  // "Discuss in Policy Chat" from a report (rejected or under HITL review)
  // deep-links here with ?reportId=... — auto-create a session and
  // pre-attach the report's own content + matched templates so the
  // employee can ask whatever they want about it, with no canned opener.
  useEffect(() => {
    const reportId = searchParams.get("reportId");
    if (!reportId) return;

    (async () => {
      setAttaching(true);
      try {
        const session = await createSession("safety", "Report discussion");
        setSessionId(session.id);
        await loadSessions();
        const attachment = await attachReportToChat(session.id, reportId);
        setAttachedFile(attachment);
      } catch (err) {
        const msg = extractErrorMessage(err);
        setMessages((prev) => [...prev, { role: "assistant", content: msg, citations: [] }]);
      } finally {
        setAttaching(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] gap-0">
      {noAccess && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800 mb-2 flex items-center justify-between">
          <span>
            <span className="font-medium">No document access.</span> Your group hasn't been granted access to any documents yet. Contact your administrator.
          </span>
          <button
            onClick={() => setNoAccess(false)}
            className="ml-4 text-amber-600 hover:text-amber-800 font-medium text-xs"
          >
            Dismiss
          </button>
        </div>
      )}
      <div className="flex flex-1 rounded-xl border overflow-hidden">
        <div className="w-60 shrink-0 border-r overflow-y-auto">
          <HistorySidebar
            sessions={sessions}
            activeSessionId={sessionId}
            onSelectSession={(id) => { setNoAccess(false); loadMessages(id); }}
            onNewChat={() => { setNoAccess(false); handleNewChat(); }}
            onDeleteSession={handleDeleteSession}
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <ChatWindow
            messages={messages}
            inputValue={input}
            onInputChange={setInput}
            onSend={() => handleSend()}
            loading={loading}
            placeholder={noAccess ? "No pipeline access — contact your admin" : "Ask a policy question…"}
            disabled={noAccess}
            attachedFile={attachedFile}
            onAttachFile={handleAttachFile}
            onRemoveAttachment={() => setAttachedFile(null)}
            attaching={attaching}
          />
        </div>
      </div>
    </div>
  );
}
