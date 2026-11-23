import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

function getHeaders(): Record<string, string> {
  const apiKey = getBackendApiKey();
  return apiKey
    ? { "Content-Type": "application/json", "X-Veritas-Key": apiKey }
    : { "Content-Type": "application/json" };
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ docId: string }> }
) {
  const backendUrl = getBackendUrl();
  const { docId } = await context.params;
  const body = await req.json();
  const res = await fetch(`${backendUrl}/v1/sources/${encodeURIComponent(docId)}/expiry`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  _req: NextRequest,
  context: { params: Promise<{ docId: string }> }
) {
  const backendUrl = getBackendUrl();
  const { docId } = await context.params;
  const res = await fetch(`${backendUrl}/v1/sources/${encodeURIComponent(docId)}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  return new NextResponse(null, { status: res.status });
}
