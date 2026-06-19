"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import api from "@/lib/api";
import { FileText, CheckSquare, Bell } from "lucide-react";
import Link from "next/link";

export default function EmployeeDashboard() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [reports, tasks, notifs] = await Promise.all([
          api.get("/api/reports/my"),
          api.get("/api/tasks"),
          api.get("/api/notifications"),
        ]);
        setStats({
          total_reports: reports.data?.length ?? 0,
          open_tasks: (tasks.data ?? []).filter(
            (t: any) => t.status !== "done"
          ).length,
          unread_notifications: (notifs.data ?? []).filter(
            (n: any) => !n.is_read
          ).length,
        });
      } catch {
        // keep null
      }
    };
    load();
  }, []);

  const cards = [
    {
      label: "My Reports",
      value: stats?.total_reports,
      icon: FileText,
      color: "text-blue-500",
      href: "/employee/reports",
    },
    {
      label: "Open Tasks",
      value: stats?.open_tasks,
      icon: CheckSquare,
      color: "text-violet-500",
      href: "/employee/tasks",
    },
    {
      label: "Unread Alerts",
      value: stats?.unread_notifications,
      icon: Bell,
      color: "text-amber-500",
      href: "/employee/notifications",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Your activity overview</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
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
            <h2 className="font-semibold mb-3">Quick Actions</h2>
            <div className="space-y-2 text-sm">
              <Link href="/employee/reports" className="block text-primary hover:underline">
                → Submit a new field report
              </Link>
              <Link href="/employee/chat" className="block text-primary hover:underline">
                → Ask the policy assistant
              </Link>
              <Link href="/employee/tasks" className="block text-primary hover:underline">
                → View my assigned tasks
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
