import { NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const res = await fetch(`${backendUrl}/v1/health/circuits/reset`, {
      method: "POST",
      headers: {
        ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      // Fallback to providers/reset-all
      const fallbackRes = await fetch(`${backendUrl}/v1/health/providers/reset-all`, {
        method: "POST",
        headers: {
          ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
        },
        cache: "no-store",
      });
      if (!fallbackRes.ok) {
        const err = await fallbackRes.json().catch(() => ({}));
        return NextResponse.json(
          { detail: err.detail || `Reset failed with status ${fallbackRes.status}` },
          { status: fallbackRes.status }
        );
      }
      const fbData = await fallbackRes.json();
      return NextResponse.json(fbData);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to connect to backend" },
      { status: 502 }
    );
  }
}
