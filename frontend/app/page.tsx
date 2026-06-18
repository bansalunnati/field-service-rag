"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import Link from "next/link";

export default function HomePage() {
  const { token, role } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (token) {
      router.replace(role === "admin" ? "/admin" : "/employee");
    }
  }, [token, role, router]);

  if (token) return null;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">
            Field Service RAG
          </h1>
          <p className="text-muted-foreground text-base">
            AI-powered field service report assistant. Chat with your documents,
            manage reports, and collaborate with your team.
          </p>
        </div>

        <Link
          href="/login"
          className="inline-block w-full rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground hover:opacity-90 transition"
        >
          Sign In
        </Link>
      </div>
    </main>
  );
}
