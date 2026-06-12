"use client";

import { useState } from "react";
import { Send } from "lucide-react";

export default function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 border-t border-[var(--border)]">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about a policy, procedure, or technical issue..."
        disabled={disabled}
        className="flex-1 bg-[var(--surface-2)] border border-[var(--border)] rounded-md px-4 py-2 text-sm focus:border-[var(--accent)] transition-colors disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled}
        className="bg-[var(--accent)] text-black rounded-md px-4 py-2 disabled:opacity-50 hover:opacity-90 transition-opacity"
      >
        <Send size={16} />
      </button>
    </form>
  );
}