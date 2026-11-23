export function getBackendUrl(): string {
  let url = (process.env.VERITAS_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  // If pointed directly to an onrender.com host that runs the unified container,
  // route through /api/veritas to reach the internal FastAPI backend.
  if (url.includes("onrender.com") && !url.includes("/api/veritas")) {
    url = `${url}/api/veritas`;
  }
  return url;
}

export function getBackendApiKey(): string {
  return process.env.VERITAS_API_KEY ?? "veritas-local-dev-key-2026";
}
