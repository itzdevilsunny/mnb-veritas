import { NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const res = await fetch(`${backendUrl}/v1/audits/relink-chain`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return NextResponse.json(
        { detail: err.detail || `Relink chain failed with status ${res.status}` },
        { status: res.status }
      );
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
