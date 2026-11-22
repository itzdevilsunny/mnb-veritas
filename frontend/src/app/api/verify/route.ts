import { NextRequest, NextResponse } from "next/server";
import type { VerifyRequest, VerifyResponse } from "@/types/veritas";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

export async function POST(req: NextRequest) {
  try {
    const body: VerifyRequest = await req.json();
    if (!body.query || !body.query.trim()) {
      return NextResponse.json({ detail: "Query is required" }, { status: 400 });
    }

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (BACKEND_API_KEY) {
      headers["X-Veritas-Key"] = BACKEND_API_KEY;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/verify`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const data: VerifyResponse = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to connect to backend engine";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
