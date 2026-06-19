"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  FolderOpen,
  Users,
  ShieldCheck,
  CheckSquare,
  Bell,
  BarChart2,
  FileLock2,
} from "lucide-react";

const menuItems = [
  { name: "Dashboard",    href: "/admin",              icon: LayoutDashboard, exact: true },
  { name: "Analytics",    href: "/admin/analytics",    icon: BarChart2 },
  { name: "Policy Chat",  href: "/admin/chat",         icon: MessageSquare },
  { name: "Documents",    href: "/admin/documents",    icon: FolderOpen },
  { name: "Assign Files", href: "/admin/assign-files", icon: FileLock2 },
  { name: "Groups",       href: "/admin/groups",       icon: Users },
  { name: "HITL Review",  href: "/admin/hitl",         icon: ShieldCheck },
  { name: "Tasks",        href: "/admin/tasks",        icon: CheckSquare },
  { name: "Notifications",href: "/admin/notifications",icon: Bell },
];

export default function AdminSidebar() {
  const pathname = usePathname();

  const isActive = (item: (typeof menuItems)[0]) => {
    if (item.exact) return pathname === item.href;
    return pathname.startsWith(item.href);
  };

  return (
    <aside className="w-60 shrink-0 min-h-screen border-r bg-background flex flex-col">
      <div className="p-5 border-b">
        <h2 className="text-lg font-bold tracking-tight">FSRA</h2>
        <p className="text-xs text-muted-foreground mt-0.5">Admin Portal</p>
      </div>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon size={17} />
              {item.name}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
