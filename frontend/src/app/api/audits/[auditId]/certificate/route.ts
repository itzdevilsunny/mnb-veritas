import { NextRequest, NextResponse } from "next/server";
import { getBackendApiKey, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ auditId: string }> }
) {
  const { auditId } = await params;
  const backendUrl = getBackendUrl();
  const apiKey = getBackendApiKey();
  const format = req.nextUrl.searchParams.get("format") || "json";

  const targetUrl = new URL(`${backendUrl}/v1/audits/${encodeURIComponent(auditId)}/certificate`);
  targetUrl.searchParams.set("format", format);

  try {
    const res = await fetch(targetUrl.toString(), {
      headers: apiKey ? { "X-Veritas-Key": apiKey } : {},
      cache: "no-store",
    });

    if (format.toLowerCase() === "pdf") {
      const pdfBytes = await res.arrayBuffer();
      return new NextResponse(pdfBytes, {
        status: res.status,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `attachment; filename="veritas-certificate-${auditId}.pdf"`,
        },
      });
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json({ detail: `Failed to fetch certificate: ${msg}` }, { status: 502 });
  }
}
