import { NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

export async function GET() {
  try {
    const headers: Record<string, string> = {};
    if (BACKEND_API_KEY) {
      headers["X-Veritas-Key"] = BACKEND_API_KEY;
    }

    const res = await fetch(`${BACKEND_URL}/v1/health/providers`, {
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
