"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";
import { useRouter } from "next/navigation";
import NotificationPanel from "./NotificationPanel";

export default function Topbar() {
  const logout = useAuthStore((state) => state.logout);
  const role = useAuthStore((state) => state.role);
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const initials = role === "admin" ? "AD" : "EMP";

  return (
    <header className="h-16 border-b px-6 flex items-center justify-between">
      <div>
        <h1 className="font-semibold">Field Service Report Assistant</h1>
      </div>

      <div className="flex items-center gap-3">
        <NotificationPanel />

        <Button variant="outline" size="sm" onClick={handleLogout}>
          Logout
        </Button>

        <Avatar>
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
