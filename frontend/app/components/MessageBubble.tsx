import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  pipeline?: "general" | "policy" | "technical";
}

const pipelineLabels: Record<string, { label: string; color: string }> = {
  general: { label: "GENERAL", color: "var(--pipeline-general)" },
  policy: { label: "POLICY", color: "var(--pipeline-policy)" },
  technical: { label: "TECHNICAL", color: "var(--pipeline-technical)" },
};

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const pipeline = message.pipeline ? pipelineLabels[message.pipeline] : null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        {pipeline && (
          <span
            className="font-mono-tech text-[10px] tracking-widest px-2 py-0.5 rounded-full border w-fit"
            style={{ color: pipeline.color, borderColor: pipeline.color }}
          >
            {pipeline.label}
          </span>
        )}
        <div
          className={`rounded-lg px-4 py-2 text-sm leading-relaxed ${
            isUser
              ? "bg-[var(--accent)] text-black"
              : "bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)]"
          }`}
        >
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}