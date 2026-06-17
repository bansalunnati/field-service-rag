"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";
import { useRouter } from "next/navigation";

export default function Topbar() {
  const logout = useAuthStore((state) => state.logout);
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="h-16 border-b px-6 flex items-center justify-between">
      <div>
        <h1 className="font-semibold">
          Field Service Report Assistant
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          onClick={handleLogout}
        >
          Logout
        </Button>

        <Avatar>
          <AvatarFallback>
            AD
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}