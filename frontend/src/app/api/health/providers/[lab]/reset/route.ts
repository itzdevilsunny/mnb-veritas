import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ lab: string }> }
) {
  try {
    const { lab } = await params;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (BACKEND_API_KEY) {
      headers["X-Veritas-Key"] = BACKEND_API_KEY;
    }

    const res = await fetch(`${BACKEND_URL}/v1/health/providers/${lab}/reset`, {
      method: "POST",
      headers,
      cache: "no-store",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to reset provider circuit";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
