"use client";

import Link from "next/link";
import { LayoutDashboard, MessageSquare, FolderOpen, Users, FileText, CheckSquare, ShieldCheck, Bell } from "lucide-react";

const menuItems = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Chat",
    href: "/chat",
    icon: MessageSquare,
  },
  {
    name: "Files",
    href: "/files",
    icon: FolderOpen,
  },
  {
    name: "Groups",
    href: "/groups",
    icon: Users,
  },
  {
    name: "Reports",
    href: "/reports",
    icon: FileText,
  },
  {
    name: "Tasks",
    href: "/tasks",
    icon: CheckSquare,
  },
  {
    name: "HITL",
    href: "/hitl",
    icon: ShieldCheck,
  },
  {
    name: "Notifications",
    href: "/notifications",
    icon: Bell,
  },
];

export default function Sidebar() {
  return (
    <aside className="w-64 min-h-screen border-r bg-background">
      <div className="p-6">
        <h2 className="text-xl font-bold">
          FSRA
        </h2>

        <p className="text-sm text-muted-foreground">
          Admin Portal
        </p>
      </div>

      <nav className="px-3 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-muted transition"
            >
              <Icon size={18} />
              {item.name}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}