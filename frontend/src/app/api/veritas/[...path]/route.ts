import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

// Server-side catch-all proxy: the browser talks to /api/veritas/*,
// this forwards to FastAPI backend and attaches X-Veritas-Key so it never reaches client bundles.
export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (!path || !path.length || path.some((p) => p === ".." || p === ".")) {
    return NextResponse.json({ detail: "Bad path" }, { status: 400 });
  }
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();
  const target = `${backendUrl}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (apiKey) headers.set("X-Veritas-Key", apiKey);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
    });
    if (upstream.status === 204) return new NextResponse(null, { status: 204 });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json({ detail: `MNB Veritas backend unreachable: ${detail}` }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
