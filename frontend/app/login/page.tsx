"use client";

import { api, getApiUrl, pingApi, saveAuth } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type TokenOut = {
  access_token: string;
  user_id: string;
  org_id: string;
  email: string;
  name?: string | null;
  api_key?: string | null;
  token_balance?: number | null;
};

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [apiKeyNotice, setApiKeyNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState<string>("checking…");

  useEffect(() => {
    pingApi().then((r) => {
      setApiStatus(r.ok ? `API online · ${r.url}` : `API offline · ${r.url} · ${r.detail || ""}`);
    });
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, name: name || "Operator", org_name: "Astra Workspace" };
      const data = await api<TokenOut>(path, { method: "POST", body: JSON.stringify(body) });
      saveAuth(data);
      if (data.api_key) {
        setApiKeyNotice(data.api_key);
        localStorage.setItem("astracortex_last_api_key", data.api_key);
      }
      router.push("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="panel auth-card stack">
        <div>
          <h1>AstraCortex OS</h1>
          <p className="muted">Hybrid cognitive OS · chat · API tokens · multi-platform</p>
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: 8 }}>
            {apiStatus}
          </p>
        </div>
        <div className="row">
          <button
            type="button"
            className={mode === "register" ? "" : "secondary"}
            onClick={() => setMode("register")}
          >
            Register
          </button>
          <button
            type="button"
            className={mode === "login" ? "" : "secondary"}
            onClick={() => setMode("login")}
          >
            Login
          </button>
        </div>
        <form className="stack" onSubmit={submit}>
          {mode === "register" && (
            <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          )}
          <input
            type="email"
            placeholder="Email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password (min 8)"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="error">{error}</div>}
          {apiKeyNotice && (
            <div className="card">
              <strong>Your sellable API key (save it)</strong>
              <pre className="event-log">{apiKeyNotice}</pre>
            </div>
          )}
          <button type="submit" disabled={loading}>
            {loading ? "Working…" : mode === "login" ? "Enter OS" : "Create workspace + API key"}
          </button>
        </form>
        <p className="muted" style={{ fontSize: "0.75rem" }}>
          API: {typeof window !== "undefined" ? getApiUrl() : "…"} · Offline-first via local Ollama
          <br />
          <Link href="/privacy">Privacy</Link>
          {" · "}
          <Link href="/terms">Terms</Link>
        </p>
      </div>
    </div>
  );
}
