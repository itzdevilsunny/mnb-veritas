"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import type { ManagedSource } from "@/types/veritas";

interface SourceManagerProps {
  onSourcesChanged?: (sources: ManagedSource[]) => void;
  refreshKey?: number;
}

export default function SourceManager({
  onSourcesChanged,
  refreshKey = 0,
}: SourceManagerProps) {
  const [sources, setSources] = useState<ManagedSource[]>([]);
  const [loading, setLoading] = useState(true);

  // PDF Form State
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [baseDocId, setBaseDocId] = useState("budget_annexure_2025");
  const [docTitle, setDocTitle] = useState("FY 2025-26 Expenditure Profile Part II");
  const [validFrom, setValidFrom] = useState("2025-04-01");
  const [validUntil, setValidUntil] = useState("2026-03-31");
  const [isPrimary, setIsPrimary] = useState(true);
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Direct Text Upsert Form State
  const [textDocId, setTextDocId] = useState("");
  const [textDocTitle, setTextDocTitle] = useState("");
  const [textSnippet, setTextSnippet] = useState("");
  const [savingText, setSavingText] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [extendingDocId, setExtendingDocId] = useState<string | null>(null);

  const getTemporalBadge = (validUntil: string | null) => {
    if (!validUntil) {
      return { label: "PERPETUAL", cls: "bg-blue-950/80 text-blue-300 border-blue-800/60" };
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const until = new Date(validUntil);
    until.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((until.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
      return { label: `EXPIRED (${Math.abs(diffDays)}d ago)`, cls: "bg-rose-950/80 text-rose-300 border-rose-800/60" };
    }
    if (diffDays <= 30) {
      return { label: `EXPIRING (${diffDays}d left)`, cls: "bg-amber-950/80 text-amber-300 border-amber-800/60" };
    }
    return { label: "ACTIVE", cls: "bg-emerald-950/80 text-emerald-300 border-emerald-800/60" };
  };

  const handleExtendValidity = async (docId: string, currentUntil: string | null) => {
    setExtendingDocId(docId);
    try {
      const baseDate = currentUntil ? new Date(currentUntil) : new Date();
      baseDate.setFullYear(baseDate.getFullYear() + 1);
      const newUntilStr = baseDate.toISOString().slice(0, 10);

      const res = await fetch(`/api/sources/${encodeURIComponent(docId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ valid_until: newUntilStr }),
      });
      if (res.ok) {
        await fetchSources();
      }
    } finally {
      setExtendingDocId(null);
    }
  };

  const fetchSources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/sources", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setSources(data);
        onSourcesChanged?.(data);
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }, [onSourcesChanged]);

  useEffect(() => {
    void fetchSources();
  }, [fetchSources, refreshKey]);

  const handleFileSelect = (file: File | undefined | null) => {
    if (!file) return;
    setErrorMsg(null);
    setUploadSuccess(null);
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setErrorMsg("Please choose a valid .pdf file.");
      return;
    }
    setSelectedFile(file);
    const stem = file.name.replace(/\.pdf$/i, "");
    if (!docTitle) setDocTitle(stem);
    if (!baseDocId) {
      setBaseDocId(stem.toLowerCase().replace(/[^a-z0-9_]+/g, "_").slice(0, 32));
    }
  };

  const handleUploadPdf = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setUploadSuccess(null);

    if (!selectedFile) {
      setErrorMsg("Please select or drop a PDF file first.");
      return;
    }

    setUploadingPdf(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("base_doc_id", baseDocId.trim() || "pdf_doc");
      formData.append("title", docTitle.trim() || selectedFile.name);
      formData.append("valid_from", validFrom);
      if (validUntil) formData.append("valid_until", validUntil);
      formData.append("is_primary", String(isPrimary));

      const res = await fetch("/api/sources/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail ?? "PDF parsing failed");
      } else {
        setUploadSuccess(
          `Ingested ${data.filename} (${data.total_pages} pages, ${data.chunks_created} indexed chunks)`
        );
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        await fetchSources();
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Error uploading PDF");
    } finally {
      setUploadingPdf(false);
    }
  };

  const handleSaveTextSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textDocId.trim() || !textSnippet.trim()) return;

    setSavingText(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: textDocId.trim(),
          title: textDocTitle.trim() || textDocId.trim(),
          text: textSnippet.trim(),
          valid_from: "2025-01-01",
          valid_until: "2027-12-31",
          is_primary: true,
        }),
      });
      if (res.ok) {
        setTextDocId("");
        setTextDocTitle("");
        setTextSnippet("");
        await fetchSources();
      } else {
        const d = await res.json();
        setErrorMsg(d.detail ?? "Failed to save snippet");
      }
    } finally {
      setSavingText(false);
    }
  };

  const handleArchive = async (docId: string) => {
    await fetch(`/api/sources/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    });
    await fetchSources();
  };

  return (
    <div className="space-y-6">
      {/* CORPUS INGESTION // PDF PARSER */}
      <form
        onSubmit={handleUploadPdf}
        className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Corpus Ingestion // PDF Parser
            </span>
            <span className="rounded bg-sky-950/70 px-2 py-0.5 font-mono text-[10px] text-sky-400 border border-sky-800/50">
              /v1/sources/upload
            </span>
          </div>
          <span className="font-mono text-[11px] text-zinc-500">Recursive Chunker</span>
        </div>

        {/* Dropzone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setIsDragging(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            handleFileSelect(e.dataTransfer.files?.[0]);
          }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition ${
            isDragging
              ? "border-emerald-500 bg-emerald-500/10 text-emerald-200"
              : "border-zinc-800 bg-[#0B0F12] text-zinc-400 hover:border-zinc-700"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => handleFileSelect(e.target.files?.[0])}
            className="hidden"
          />
          <div className="mb-2 text-2xl">☁️</div>
          <div className="text-xs font-medium text-zinc-200">
            {selectedFile ? (
              <span className="text-emerald-400 font-mono font-bold">
                {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
              </span>
            ) : (
              "Tap to select or drop official .PDF"
            )}
          </div>
          <p className="mt-1 font-mono text-[11px] text-zinc-500">
            PDF documents undergo strict extraction &amp; sentence indexing
          </p>
        </div>

        {/* Metadata Inputs */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              BASE_DOC_ID
            </label>
            <input
              type="text"
              required
              value={baseDocId}
              onChange={(e) => setBaseDocId(e.target.value)}
              placeholder="e.g. budget_annexure_2025"
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              DOC TITLE
            </label>
            <input
              type="text"
              required
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              placeholder="e.g. FY 2025-26 Expenditure Profile Part II"
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              VALID FROM
            </label>
            <input
              type="date"
              required
              value={validFrom}
              onChange={(e) => setValidFrom(e.target.value)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              VALID UNTIL
            </label>
            <input
              type="date"
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center gap-2 font-mono text-xs text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={isPrimary}
              onChange={(e) => setIsPrimary(e.target.checked)}
              className="h-4 w-4 accent-emerald-500"
            />
            <span>Set as Primary Source (Precedence)</span>
          </label>

          <button
            type="submit"
            disabled={uploadingPdf || !selectedFile}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            {uploadingPdf ? "Parsing & Chunking..." : "Upload & Chunk PDF"}
          </button>
        </div>

        {uploadSuccess && (
          <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-2.5 font-mono text-xs text-emerald-300">
            ✓ {uploadSuccess}
          </div>
        )}
      </form>

      {/* DIRECT TEXT CORPUS UPSERT */}
      <form
        onSubmit={handleSaveTextSource}
        className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-3"
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
            Direct Text Corpus Upsert
          </span>
          <span className="font-mono text-[10px] text-zinc-500">POST /v1/sources</span>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            type="text"
            required
            value={textDocId}
            onChange={(e) => setTextDocId(e.target.value)}
            placeholder="doc_id (e.g. gazette_notif_49)"
            className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
          />
          <input
            type="text"
            required
            value={textDocTitle}
            onChange={(e) => setTextDocTitle(e.target.value)}
            placeholder="Document Title"
            className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
          />
        </div>

        <textarea
          rows={2}
          required
          value={textSnippet}
          onChange={(e) => setTextSnippet(e.target.value)}
          placeholder="Paste verbatim source excerpt..."
          className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] p-2.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none"
        />

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={savingText}
            className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 font-mono text-xs font-semibold text-zinc-200 hover:bg-zinc-700 disabled:opacity-50"
          >
            {savingText ? "Saving..." : "Save Corpus Snippet"}
          </button>
        </div>
      </form>

      {errorMsg && (
        <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-3 font-mono text-xs text-rose-300">
          {errorMsg}
        </div>
      )}

      {/* REGISTERED TRUTH CORPUSES */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
            Registered Truth Corpuses
          </span>
          <span className="font-mono text-[10px] text-zinc-500">GET /v1/sources</span>
        </div>

        <div className="space-y-2.5">
          {loading ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500">
              Loading truth corpuses...
            </div>
          ) : sources.length === 0 ? (
            <div className="py-8 text-center font-mono text-xs text-zinc-500">
              No truth sources registered.
            </div>
          ) : (
            sources.map((src) => {
              const badge = getTemporalBadge(src.valid_until);
              const isExpanded = expandedDocId === src.doc_id;
              const isExtending = extendingDocId === src.doc_id;

              return (
                <div
                  key={src.id}
                  className="rounded-lg border border-zinc-800/80 bg-[#121820]/70 p-3.5 hover:border-zinc-700 transition space-y-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-zinc-100">
                          {src.doc_id}
                        </span>
                        {src.is_primary && (
                          <span className="rounded bg-amber-950/80 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-300 border border-amber-800/50">
                            PRIMARY
                          </span>
                        )}
                        <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold border ${badge.cls}`}>
                          {badge.label}
                        </span>
                        <span className="rounded bg-emerald-950/80 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300 border border-emerald-800/50">
                          INDEXED
                        </span>
                      </div>

                      <div className="text-xs text-zinc-300 font-medium">{src.title}</div>

                      <div className="font-mono text-[11px] text-zinc-500">
                        Validity: {src.valid_from} to {src.valid_until ?? "indefinite"}
                        {src.page_count
                          ? ` • ${src.page_count} pgs (${src.chunk_count ?? 1} chunks)`
                          : ""}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-xs">
                      <button
                        type="button"
                        onClick={() => setExpandedDocId(isExpanded ? null : src.doc_id)}
                        className="rounded border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-[11px] text-zinc-300 hover:text-zinc-100 transition"
                      >
                        {isExpanded ? "Hide Text" : "Inspect Text"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExtendValidity(src.doc_id, src.valid_until)}
                        disabled={isExtending}
                        className="rounded border border-emerald-900/60 bg-emerald-950/40 px-2.5 py-1 text-[11px] text-emerald-400 hover:bg-emerald-900/50 transition disabled:opacity-50"
                        title="Extend validity window by 1 year"
                      >
                        {isExtending ? "Extending..." : "+1 Year Expiry"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleArchive(src.doc_id)}
                        className="rounded border border-zinc-700/80 px-2.5 py-1 text-[11px] text-zinc-400 hover:border-rose-700 hover:text-rose-300 transition"
                      >
                        Archive
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="rounded-lg border border-zinc-800 bg-[#080C0E] p-3 space-y-1.5 font-mono text-xs">
                      <div className="flex items-center justify-between text-[10px] text-zinc-500 border-b border-zinc-800/80 pb-1">
                        <span>SOURCE CORPUS TEXT // {src.text.length} CHARACTERS</span>
                        <span>STATUS: {src.is_active ? "ACTIVE" : "INACTIVE"}</span>
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed max-h-48 overflow-y-auto font-sans whitespace-pre-wrap selection:bg-emerald-500/20">
                        {src.text}
                      </p>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
