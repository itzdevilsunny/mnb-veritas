import { NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const res = await fetch(`${backendUrl}/v1/audits/verify-chain`, {
      headers: apiKey ? { "X-Veritas-Key": apiKey } : {},
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json({ detail: `Failed to verify audit chain: ${msg}` }, { status: 502 });
  }
}
