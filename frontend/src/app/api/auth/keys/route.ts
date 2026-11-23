import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function GET() {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const res = await fetch(`${backendUrl}/v1/auth/keys`, {
      headers: apiKey ? { "X-Veritas-Key": apiKey } : {},
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to fetch API keys";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const body = await req.json();
    const res = await fetch(`${backendUrl}/v1/auth/keys`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to create API key";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
