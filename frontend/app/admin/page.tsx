"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import api from "@/lib/api";
import { BarChart2, FileText, ShieldCheck, Users, CheckSquare } from "lucide-react";
import Link from "next/link";

interface Stats {
  total_reports: number;
  pending_hitl: number;
  total_files: number;
  total_tasks: number;
  total_users: number;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [reports, files, tasks, hitlRes] = await Promise.all([
          api.get("/api/reports/all"),
          api.get("/api/ingest/files"),
          api.get("/api/tasks"),
          api.get("/api/hitl/queue"),
        ]);

        setStats({
          total_reports: reports.data?.length ?? 0,
          pending_hitl: hitlRes.data?.length ?? 0,
          total_files: files.data?.length ?? 0,
          total_tasks: tasks.data?.length ?? 0,
          total_users: 0,
        });
      } catch {
        // keep null — show skeletons
      }
    };
    load();
  }, []);

  const cards = [
    {
      label: "Total Reports",
      value: stats?.total_reports,
      icon: FileText,
      color: "text-blue-500",
      href: "/admin/hitl",
    },
    {
      label: "Pending HITL",
      value: stats?.pending_hitl,
      icon: ShieldCheck,
      color: "text-amber-500",
      href: "/admin/hitl",
    },
    {
      label: "Documents",
      value: stats?.total_files,
      icon: BarChart2,
      color: "text-emerald-500",
      href: "/admin/documents",
    },
    {
      label: "Open Tasks",
      value: stats?.total_tasks,
      icon: CheckSquare,
      color: "text-violet-500",
      href: "/admin/tasks",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          System overview across all teams
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.label} href={card.href}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">{card.label}</p>
                    <Icon size={18} className={card.color} />
                  </div>
                  {stats ? (
                    <p className="mt-2 text-3xl font-bold">{card.value}</p>
                  ) : (
                    <div className="mt-2 h-9 w-16 animate-pulse rounded bg-muted" />
                  )}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-3">Quick Links</h2>
            <div className="space-y-2 text-sm">
              <Link href="/admin/hitl" className="block text-primary hover:underline">
                → Review pending HITL queue
              </Link>
              <Link href="/admin/documents" className="block text-primary hover:underline">
                → Upload new documents
              </Link>
              <Link href="/admin/tasks" className="block text-primary hover:underline">
                → Assign open tasks
              </Link>
              <Link href="/admin/analytics" className="block text-primary hover:underline">
                → View performance analytics
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold mb-3">System Status</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">API</span>
                <span className="text-emerald-500 font-medium">Online</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Vector Store</span>
                <span className="text-emerald-500 font-medium">Online</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">HITL Queue</span>
                <span
                  className={
                    (stats?.pending_hitl ?? 0) > 0
                      ? "text-amber-500 font-medium"
                      : "text-emerald-500 font-medium"
                  }
                >
                  {stats?.pending_hitl ?? "—"} pending
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
