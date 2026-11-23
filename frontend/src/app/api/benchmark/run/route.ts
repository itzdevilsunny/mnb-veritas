import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    let body = undefined;
    try {
      body = await req.json();
    } catch {
      // No body or empty JSON
    }

    const res = await fetch(`${backendUrl}/v1/benchmark/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return NextResponse.json(
        { detail: err.detail || `Benchmark run failed with status ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to connect to backend" },
      { status: 502 }
    );
  }
}
