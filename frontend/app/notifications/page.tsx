"use client";

import { useEffect, useState } from "react";
import {
getNotifications,
markRead,
markAllRead,
} from "@/services/notifications";

export default function NotificationsPage() {
const [notifications, setNotifications] =
useState<any[]>([]);

const [loading, setLoading] =
useState(false);

const loadNotifications = async () => {
  try {
    const data = await getNotifications();
    setNotifications(data);
  } catch (error) {
    console.error(error);
  }
};

useEffect(() => {
loadNotifications();
}, []);

return (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <h1 className="text-3xl font-bold">
        Notifications
      </h1>

      <button
        onClick={async () => {
          try {
            setLoading(true);

            await markAllRead();

            await loadNotifications();
          } finally {
            setLoading(false);
          }
        }}
        className="border rounded px-4 py-2"
      >
        Mark All Read
      </button>
    </div>

    <div className="space-y-3">
      {notifications.map((notification: any) => (
        <div
          key={notification.id}
          className={`border rounded p-4 ${
            notification.is_read ? "" : "bg-blue-50"
          }`}
        >
          <div className="flex justify-between">
            <div>
              <p className="font-medium">
                {notification.title}
              </p>

              <p className="text-sm text-gray-500">
                {notification.message}
              </p>
            </div>

            {!notification.is_read && (
              <button
                onClick={async () => {
                  await markRead(notification.id);

                  await loadNotifications();
                }}
                className="border rounded px-3 py-1"
              >
                Read
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  </div>
);
}