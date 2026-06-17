"use client";

import { useEffect, useState } from "react";

import {
  getHitlQueue,
  approveReport,
  rejectReport,
} from "@/services/hitl";

export default function HitlPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [notes, setNotes] = useState("");

  const loadQueue = async () => {
    const data = await getHitlQueue();
    setQueue(data);
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleApprove = async (
    reportId: string
  ) => {
    await approveReport(
      reportId,
      notes
    );

    setNotes("");
    loadQueue();
  };

  const handleReject = async (
    reportId: string
  ) => {
    await rejectReport(
      reportId,
      notes
    );

    setNotes("");
    loadQueue();
  };

  return (
    <div className="space-y-6">

      <h1 className="text-3xl font-bold">
        HITL Review Queue
      </h1>

      {queue.map((item) => (
        <div
          key={item.review_id}
          className="border rounded-lg p-5 space-y-4"
        >
          <div>
            <h2 className="font-bold">
              {item.title}
            </h2>

            <p>
              Status:
              {" "}
              {item.status}
            </p>
          </div>

          <textarea
            placeholder="Review notes..."
            value={notes}
            onChange={(e) =>
              setNotes(
                e.target.value
              )
            }
            className="border rounded p-2 w-full"
          />

          <div className="flex gap-2">

            <button
              onClick={() =>
                handleApprove(
                  item.report_id
                )
              }
              className="bg-green-600 text-white px-4 py-2 rounded"
            >
              Approve
            </button>

            <button
              onClick={() =>
                handleReject(
                  item.report_id
                )
              }
              className="bg-red-600 text-white px-4 py-2 rounded"
            >
              Reject
            </button>

          </div>
        </div>
      ))}
    </div>
  );
}