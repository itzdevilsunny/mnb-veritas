import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function DELETE(
  _req: NextRequest,
  ctx: { params: Promise<{ prefix: string }> }
) {
  const { prefix } = await ctx.params;
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const res = await fetch(`${backendUrl}/v1/auth/keys/${encodeURIComponent(prefix)}`, {
      method: "DELETE",
      headers: apiKey ? { "X-Veritas-Key": apiKey } : {},
      cache: "no-store",
    });
    if (res.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to revoke API key";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
