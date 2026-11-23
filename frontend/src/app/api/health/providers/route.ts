import { NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export async function GET() {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();
  try {
    const headers: Record<string, string> = {};
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const res = await fetch(`${backendUrl}/v1/health/providers`, {
      method: "GET",
      headers,
      cache: "no-store",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to fetch provider health";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
