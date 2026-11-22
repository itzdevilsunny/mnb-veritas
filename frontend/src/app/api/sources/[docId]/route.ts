import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

function getHeaders(): Record<string, string> {
  return BACKEND_API_KEY
    ? { "Content-Type": "application/json", "X-Veritas-Key": BACKEND_API_KEY }
    : { "Content-Type": "application/json" };
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ docId: string }> }
) {
  const { docId } = await context.params;
  const body = await req.json();
  const res = await fetch(`${BACKEND_URL}/v1/sources/${encodeURIComponent(docId)}/expiry`, {
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
  const { docId } = await context.params;
  const res = await fetch(`${BACKEND_URL}/v1/sources/${encodeURIComponent(docId)}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  return new NextResponse(null, { status: res.status });
}
