import { NextRequest, NextResponse } from "next/server";
import type { BatchVerifyRequest, BatchVerifyResponse } from "@/types/veritas";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const backendUrl = getBackendUrl();
    const apiKey = getBackendApiKey();
    const body: BatchVerifyRequest = await req.json();

    if (!body.items || !Array.isArray(body.items) || body.items.length === 0) {
      return NextResponse.json({ detail: "Items list cannot be empty" }, { status: 400 });
    }
    if (body.items.length > 50) {
      return NextResponse.json({ detail: "Batch size exceeds maximum limit of 50 items" }, { status: 422 });
    }

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const upstream = await fetch(`${backendUrl}/v1/verify/batch`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const data: BatchVerifyResponse = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to connect to backend engine";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
