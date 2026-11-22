import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";

export async function POST(req: NextRequest): Promise<NextResponse> {
  try {
    const incomingFormData = await req.formData();
    const fileEntry = incomingFormData.get("file");

    if (!(fileEntry instanceof File)) {
      return NextResponse.json(
        { detail: "A PDF file is required under form field 'file'." },
        { status: 400 }
      );
    }

    const outgoingFormData = new FormData();
    for (const [key, value] of incomingFormData.entries()) {
      outgoingFormData.append(key, value);
    }

    const headers: Record<string, string> = {};
    if (BACKEND_API_KEY) {
      headers["X-Veritas-Key"] = BACKEND_API_KEY;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/sources/upload`, {
      method: "POST",
      headers,
      body: outgoingFormData,
      cache: "no-store",
    });

    const contentType = upstream.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await upstream.json();
      return NextResponse.json(payload, { status: upstream.status });
    }

    const text = await upstream.text();
    return NextResponse.json(
      { detail: text || "Upstream upload failed" },
      { status: upstream.status }
    );
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to proxy PDF upload to MNB Veritas backend";
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}
