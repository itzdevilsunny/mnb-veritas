import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ lab: string }> }
) {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();
  try {
    const { lab } = await params;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const res = await fetch(`${backendUrl}/v1/health/providers/${lab}/reset`, {
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
