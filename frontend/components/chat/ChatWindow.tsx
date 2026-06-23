"use client";

import { useEffect, useRef } from "react";
import CitationCard from "./CitationCard";
import { Loader2, Send, Paperclip, X } from "lucide-react";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: any[];
}

interface AttachedFile {
  filename: string;
  extracted_text: string;
}

interface ChatWindowProps {
  messages: Message[];
  inputValue: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  loading: boolean;
  placeholder?: string;
  disabled?: boolean;
  attachedFile?: AttachedFile | null;
  onAttachFile?: (file: File) => void;
  onRemoveAttachment?: () => void;
  attaching?: boolean;
}

export default function ChatWindow({
  messages,
  inputValue,
  onInputChange,
  onSend,
  loading,
  placeholder = "Ask a question…",
  disabled = false,
  attachedFile = null,
  onAttachFile,
  onRemoveAttachment,
  attaching = false,
}: ChatWindowProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex h-full flex-col">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
            Start the conversation by asking a question.
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={msg.id ?? i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-muted rounded-bl-sm"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                <CitationCard citations={msg.citations} />
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-sm bg-muted px-4 py-3">
              <Loader2 size={16} className="animate-spin text-muted-foreground" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t p-3 space-y-2">
        {attachedFile && (
          <div className="flex items-center gap-2 rounded-lg border bg-muted px-3 py-1.5 text-xs w-fit">
            <Paperclip size={12} />
            <span className="truncate max-w-[200px]">{attachedFile.filename}</span>
            <button
              onClick={onRemoveAttachment}
              className="text-muted-foreground hover:text-foreground"
            >
              <X size={12} />
            </button>
          </div>
        )}
        <div className="flex items-center gap-2 rounded-xl border bg-background px-3 py-2 focus-within:ring-2 focus-within:ring-primary/30">
          {onAttachFile && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.txt,.md"
                title="PDF, DOCX, TXT, or MD with selectable text — scanned/image files need OCR and aren't supported here; submit those as a Field Report instead"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onAttachFile(file);
                  e.target.value = "";
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || attaching}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-40 transition"
                title="Attach a file"
              >
                {attaching ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} />}
              </button>
            </>
          )}
          <input
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            placeholder={placeholder}
            value={inputValue}
            disabled={disabled}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !loading && !disabled) {
                e.preventDefault();
                onSend();
              }
            }}
          />
          <button
            onClick={onSend}
            disabled={loading || disabled || !inputValue.trim()}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground disabled:opacity-40 hover:opacity-90 transition"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
