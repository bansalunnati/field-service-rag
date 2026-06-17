"use client";

import Sidebar from "./sidebar";
import Topbar from "./topbar";
import ProtectedRoute from "@/components/auth/protected-route";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <div className="flex">
        <Sidebar />

        <div className="flex-1">
          <Topbar />

          <main className="p-8 w-full">
            {children}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}