/**
 * API client — permanent rules (do NOT reverse these):
 *
 * 1. NEVER route JSON/LLM traffic through Next.js rewrites (/backend/*).
 *    Next's rewrite proxy has short idle timeouts → ECONNRESET / "socket hang up"
 *    on /converse/reply, /keys, and any multi-second request.
 *
 * 2. Browser always calls the API origin directly (CORS is enabled on FastAPI).
 *    Local:  http://127.0.0.1:8000
 *    Cloud:  NEXT_PUBLIC_API_URL (Railway)
 *    Override: localStorage.astracortex_api_url
 *
 * 3. Prefer 127.0.0.1 over "localhost" on Windows (avoids IPv6 ::1 miss).
 */

function envApiUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    ""
  ).replace(/\/$/, "");
}

export type AuthState = {
  access_token: string;
  user_id: string;
  org_id: string;
  email: string;
  name?: string | null;
  api_key?: string | null;
  token_balance?: number | null;
};

/** Same base for JSON + streams — always direct to API, never Next proxy. */
export function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const override = localStorage.getItem("astracortex_api_url");
    if (override) return override.replace(/\/$/, "").replace(/\/backend\/?$/, "");
  }
  const env = envApiUrl();
  if (env) {
    // Strip accidental /backend suffix if someone set it
    return env.replace(/\/$/, "").replace(/\/backend\/?$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function getStreamApiUrl(): string {
  return getApiUrl();
}

export function loadAuth(): AuthState | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("astracortex_auth");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthState;
  } catch {
    return null;
  }
}

export function saveAuth(auth: AuthState) {
  localStorage.setItem("astracortex_auth", JSON.stringify(auth));
}

export function clearAuth() {
  localStorage.removeItem("astracortex_auth");
}

function friendlyFetchError(err: unknown, base: string): Error {
  const msg = err instanceof Error ? err.message : String(err);
  if (
    msg === "Failed to fetch" ||
    msg.includes("NetworkError") ||
    msg.includes("fetch") ||
    msg.includes("ECONNRESET") ||
    msg.includes("socket hang up")
  ) {
    return new Error(
      `API connection failed (${base}). ` +
        `1) Docker Desktop running? 2) docker compose up -d postgres redis api  ` +
        `3) curl ${base}/health  ·  Detail: ${msg}`
    );
  }
  return err instanceof Error ? err : new Error(msg);
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Fetch with retries for transient socket resets (API restart, brief blips).
 * Does NOT retry on 4xx.
 */
export async function api<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const base = getApiUrl();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const maxAttempts = 3;
  let lastErr: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch(`${base}${path}`, {
        ...options,
        headers,
        // long LLM replies — browser has no timeout; keep signal if provided
      });

      if (!res.ok) {
        const text = await res.text();
        let detail = text || res.statusText;
        try {
          const j = JSON.parse(text);
          if (j.detail) {
            detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
          }
        } catch {
          /* keep */
        }
        // Don't retry client errors
        if (res.status >= 400 && res.status < 500) {
          throw new Error(detail);
        }
        lastErr = new Error(detail);
        if (attempt < maxAttempts) {
          await sleep(400 * attempt);
          continue;
        }
        throw lastErr;
      }

      if (res.status === 204) return undefined as T;
      return (await res.json()) as T;
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const transient =
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError") ||
        msg.includes("ECONNRESET") ||
        msg.includes("socket hang up") ||
        msg.includes("Load failed");
      if (transient && attempt < maxAttempts) {
        await sleep(500 * attempt);
        continue;
      }
      throw friendlyFetchError(err, base);
    }
  }
  throw friendlyFetchError(lastErr, base);
}

export async function pingApi(): Promise<{ ok: boolean; url: string; detail?: string }> {
  const url = getApiUrl();
  try {
    const res = await fetch(`${url}/health`, { method: "GET", cache: "no-store" });
    if (!res.ok) return { ok: false, url, detail: `HTTP ${res.status}` };
    return { ok: true, url };
  } catch (err) {
    return { ok: false, url, detail: err instanceof Error ? err.message : String(err) };
  }
}

export async function readSSE(
  url: string,
  token: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal
) {
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });
  } catch (err) {
    throw friendlyFetchError(err, url);
  }
  if (!res.ok || !res.body) throw new Error(await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() || "";
    for (const line of parts) {
      if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
      else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        let data: Record<string, unknown> = {};
        try {
          data = JSON.parse(raw);
        } catch {
          data = { raw };
        }
        onEvent(currentEvent, data);
      }
    }
  }
}
