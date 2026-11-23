import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl, getBackendApiKey } from "@/lib/backend";

export async function POST(req: NextRequest): Promise<NextResponse> {
  try {
    const backendUrl = getBackendUrl();
    const apiKey = getBackendApiKey();
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
    if (apiKey) {
      headers["X-Veritas-Key"] = apiKey;
    }

    const upstream = await fetch(`${backendUrl}/v1/sources/upload`, {
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
