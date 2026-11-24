import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ auditId: string }> }
) {
  const { auditId } = await params;
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();

  try {
    const body = await req.json();
    const res = await fetch(`${backendUrl}/v1/audits/${auditId}/review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-Veritas-Key": apiKey } : {}),
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
