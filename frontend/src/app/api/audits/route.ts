import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

export async function GET(req: NextRequest) {
  const verdict = req.nextUrl.searchParams.get("verdict");
  const url = new URL(`${BACKEND_URL}/v1/audits`);
  if (verdict && verdict !== "ALL") {
    url.searchParams.set("verdict", verdict);
  }

  try {
    const res = await fetch(url.toString(), {
      headers: BACKEND_API_KEY ? { "X-Veritas-Key": BACKEND_API_KEY } : {},
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
