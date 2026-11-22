import { NextRequest, NextResponse } from "next/server";

// Server-side catch-all proxy: the browser talks to /api/veritas/*,
// this forwards to FastAPI backend and attaches X-Veritas-Key so it never reaches client bundles.
export const dynamic = "force-dynamic";

const BACKEND_URL = (process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (!path || !path.length || path.some((p) => p === ".." || p === ".")) {
    return NextResponse.json({ detail: "Bad path" }, { status: 400 });
  }
  const target = `${BACKEND_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (BACKEND_API_KEY) headers.set("X-Veritas-Key", BACKEND_API_KEY);

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
