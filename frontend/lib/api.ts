const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

export type AuthState = {
  access_token: string;
  user_id: string;
  org_id: string;
  email: string;
  name?: string | null;
  api_key?: string | null;
  token_balance?: number | null;
};

export function getApiUrl() {
  if (typeof window !== "undefined") {
    const override = localStorage.getItem("astracortex_api_url");
    if (override) return override.replace(/\/$/, "");
  }
  return API_URL.replace(/\/$/, "");
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

export async function api<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${getApiUrl()}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function readSSE(
  url: string,
  token: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal
) {
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
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
