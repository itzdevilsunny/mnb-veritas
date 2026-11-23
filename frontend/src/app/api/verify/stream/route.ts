import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function POST(req: NextRequest) {
  try {
    const backendUrl = getBackendUrl();
    const apiKey = getBackendApiKey();
    const body = await req.json();

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const upstream = await fetch(`${backendUrl}/v1/verify/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });

    if (!upstream.ok || !upstream.body) {
      const err = await upstream.text().catch(() => "");
      return new NextResponse(err || "Failed to stream verification", { status: upstream.status });
    }

    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to connect to backend engine";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
