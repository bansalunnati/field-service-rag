"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  CheckSquare,
  Bell,
  Users,
  BookOpen,
} from "lucide-react";

const menuItems = [
  { name: "Dashboard",    href: "/employee",               icon: LayoutDashboard, exact: true },
  { name: "Policy Chat",  href: "/employee/chat",          icon: MessageSquare },
  { name: "My Reports",   href: "/employee/reports",       icon: FileText },
  { name: "My Tasks",     href: "/employee/tasks",         icon: CheckSquare },
  { name: "My Group",     href: "/employee/my-group",      icon: Users },
  { name: "Documents",    href: "/employee/documents",     icon: BookOpen },
  { name: "Notifications",href: "/employee/notifications", icon: Bell },
];

export default function EmployeeSidebar() {
  const pathname = usePathname();

  const isActive = (item: (typeof menuItems)[0]) => {
    if (item.exact) return pathname === item.href;
    return pathname.startsWith(item.href);
  };

  return (
    <aside className="w-60 shrink-0 min-h-screen border-r bg-background flex flex-col">
      <div className="p-5 border-b">
        <h2 className="text-lg font-bold tracking-tight">FSRA</h2>
        <p className="text-xs text-muted-foreground mt-0.5">Employee Portal</p>
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
