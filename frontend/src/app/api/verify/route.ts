import { NextRequest, NextResponse } from "next/server";
import type { VerifyRequest, VerifyResponse } from "@/types/veritas";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function POST(req: NextRequest) {
  try {
    const backendUrl = getBackendUrl();
    const apiKey = getBackendApiKey();
    const body: VerifyRequest = await req.json();
    if (!body.query || !body.query.trim()) {
      return NextResponse.json({ detail: "Query is required" }, { status: 400 });
    }

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const upstream = await fetch(`${backendUrl}/v1/verify`, {
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
