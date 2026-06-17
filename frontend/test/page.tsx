"use client";

import api from "@/services/api";

export default function TestPage() {
  async function testApi() {
    console.log(
      process.env.NEXT_PUBLIC_API_URL
    );
  }

  return (
    <button
      onClick={testApi}
      className="border p-4"
    >
      Test API
    </button>
  );
}