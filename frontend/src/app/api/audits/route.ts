import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();
  const verdict = req.nextUrl.searchParams.get("verdict");
  const url = new URL(`${backendUrl}/v1/audits`);
  if (verdict && verdict !== "ALL") {
    url.searchParams.set("verdict", verdict);
  }

  try {
    const res = await fetch(url.toString(), {
      headers: apiKey ? { "X-Veritas-Key": apiKey } : {},
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
