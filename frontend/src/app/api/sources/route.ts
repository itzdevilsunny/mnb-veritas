import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

function getHeaders(): Record<string, string> {
  return BACKEND_API_KEY
    ? { "Content-Type": "application/json", "X-Veritas-Key": BACKEND_API_KEY }
    : { "Content-Type": "application/json" };
}

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/v1/sources`, {
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
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND_URL}/v1/sources`, {
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
