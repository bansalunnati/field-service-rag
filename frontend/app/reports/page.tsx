"use client";

import { useEffect, useState } from "react";
import {
  submitReport,
  getMyReports,
  getAllReports,
  reviewReport,
} from "@/services/reports";

interface Report {
  id: string;
  title: string;
  report_type: string;
  status: string;
  submitted_at: string;
  updated_at: string;
  ai_summary?: string;
  hitl_reason?: string;
  submitted_by?: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);

  const [title, setTitle] = useState("");
  const [reportType, setReportType] =
    useState("field_report");

  const [file, setFile] =
    useState<File | null>(null);

  const [loading, setLoading] =
    useState(false);

  const loadReports = async () => {
    try {
      const data = await getMyReports();
      setReports(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  const handleSubmit = async () => {
    if (!file || !title) return;

    try {
      setLoading(true);

      const formData = new FormData();

      formData.append("title", title);
      formData.append(
        "report_type",
        reportType
      );
      formData.append("file", file);

      await submitReport(formData);

      setTitle("");
      setFile(null);

      loadReports();

      alert(
        "Report submitted successfully."
      );
    } catch (error) {
      console.error(error);
      alert("Submission failed.");
    } finally {
      setLoading(false);
    }
  };

  const statusColor = (
    status: string
  ) => {
    switch (status) {
      case "approved":
        return "bg-green-500";

      case "rejected":
        return "bg-red-500";

      case "needs_hitl":
        return "bg-orange-500";

      default:
        return "bg-blue-500";
    }
  };

  return (
    <div className="p-6 space-y-8">

      <h1 className="text-3xl font-bold">
        Reports
      </h1>

      {/* Submit Report */}

      <div className="border rounded-xl p-5 space-y-4">

        <h2 className="font-semibold">
          Submit Report
        </h2>

        <input
          className="border p-2 rounded w-full"
          placeholder="Report title"
          value={title}
          onChange={(e) =>
            setTitle(e.target.value)
          }
        />

        <select
          className="border p-2 rounded w-full"
          value={reportType}
          onChange={(e) =>
            setReportType(
              e.target.value
            )
          }
        >
          <option value="field_report">
            Field Report
          </option>

          <option value="tower_sop">
            Tower SOP
          </option>

          <option value="hazmat_inspection">
            Hazmat Inspection
          </option>
        </select>

        <input
          type="file"
          onChange={(e) =>
            setFile(
              e.target.files?.[0] || null
            )
          }
        />

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          {loading
            ? "Submitting..."
            : "Submit Report"}
        </button>
      </div>

      {/* Report History */}

      <div className="border rounded-xl p-5">

        <h2 className="font-semibold mb-4">
          My Reports
        </h2>

        <div className="overflow-auto">

          <table className="w-full">

            <thead>
              <tr className="border-b">
                <th className="text-left p-2">
                  Title
                </th>

                <th className="text-left p-2">
                  Type
                </th>

                <th className="text-left p-2">
                  Status
                </th>

                <th className="text-left p-2">
                  Submitted
                </th>
              </tr>
            </thead>

            <tbody>
              {reports.map((report) => (
                <tr
                  key={report.id}
                  className="border-b"
                >
                  <td className="p-2">
                    {report.title}
                  </td>

                  <td className="p-2">
                    {report.report_type}
                  </td>

                  <td className="p-2">

                    <span
                      className={`text-white px-2 py-1 rounded text-xs ${statusColor(
                        report.status
                      )}`}
                    >
                      {report.status}
                    </span>

                  </td>

                  <td className="p-2">
                    {new Date(
                      report.submitted_at
                    ).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>

          </table>

        </div>
      </div>

    </div>
  );
}