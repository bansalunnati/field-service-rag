"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import Topbar from "@/components/layout/topbar";
import EmployeeSidebar from "@/components/layout/employee-sidebar";

export default function EmployeeLayout({ children }: { children: React.ReactNode }) {
  const { token, role } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    } else if (role === "admin") {
      router.replace("/admin");
    }
  }, [token, role, router]);

  if (!token || role === "admin") return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <EmployeeSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
