"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { getNotifications, markRead, markAllRead } from "@/services/notifications";
import { Bell, CheckCheck } from "lucide-react";

export default function EmployeeNotificationsPage() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await getNotifications();
      setNotifications(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleMarkRead = async (id: string) => {
    await markRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
  };

  const handleMarkAll = async () => {
    await markAllRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  const unread = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Notifications</h1>
          <p className="text-sm text-muted-foreground mt-1">{unread} unread</p>
        </div>
        {unread > 0 && (
          <button
            onClick={handleMarkAll}
            className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm hover:bg-muted"
          >
            <CheckCheck size={15} /> Mark all read
          </button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-5 space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <div className="py-12 text-center">
              <Bell size={32} className="mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No notifications</p>
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => !n.is_read && handleMarkRead(n.id)}
                  className={`px-5 py-4 cursor-pointer hover:bg-muted/50 transition ${
                    !n.is_read ? "bg-primary/5" : ""
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {!n.is_read && (
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
                    )}
                    <div className={!n.is_read ? "" : "pl-5"}>
                      <p
                        className={`text-sm ${
                          !n.is_read ? "font-medium" : "text-muted-foreground"
                        }`}
                      >
                        {n.message}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
