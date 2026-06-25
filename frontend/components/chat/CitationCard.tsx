"use client";

interface Citation {
  source?: string;
  page?: number | string;
  excerpt?: string;
  ref?: string;
}

interface CitationCardProps {
  citations: Citation[];
}

export default function CitationCard({ citations }: CitationCardProps) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        Sources
      </p>
      {citations.map((c, i) => (
        <div
          key={i}
          className="rounded border bg-muted/40 px-3 py-2 text-xs"
        >
          <div className="flex items-center gap-2 font-medium flex-wrap">
            <span className="inline-flex h-4 shrink-0 items-center justify-center rounded-full bg-primary/10 px-1.5 text-[10px] text-primary font-bold whitespace-nowrap">
              {c.ref ?? i + 1}
            </span>
            <span className="truncate min-w-0">{c.source ?? "Unknown source"}</span>
            {c.page && (
              <span className="ml-auto shrink-0 text-muted-foreground whitespace-nowrap">
                p.{c.page}
              </span>
            )}
          </div>
          {c.excerpt && (
            <p className="mt-1 text-muted-foreground line-clamp-2">
              {c.excerpt}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
