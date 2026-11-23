import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

function getHeaders(): Record<string, string> {
  const apiKey = getBackendApiKey();
  return apiKey
    ? { "Content-Type": "application/json", "X-Veritas-Key": apiKey }
    : { "Content-Type": "application/json" };
}

export async function GET() {
  const backendUrl = getBackendUrl();
  try {
    const res = await fetch(`${backendUrl}/v1/sources`, {
      headers: getHeaders(),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const backendUrl = getBackendUrl();
  try {
    const body = await req.json();
    const res = await fetch(`${backendUrl}/v1/sources`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
