"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function KeysPage() {
  const [keys, setKeys] = useState<Record<string, unknown>[]>([]);
  const [usage, setUsage] = useState<Record<string, unknown>[]>([]);
  const [created, setCreated] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const auth = loadAuth();
    if (!auth) return;
    const [k, u] = await Promise.all([
      api<Record<string, unknown>[]>("/keys", {}, auth.access_token),
      api<Record<string, unknown>[]>("/keys/usage/recent", {}, auth.access_token),
    ]);
    setKeys(k);
    setUsage(u);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function createKey() {
    const auth = loadAuth();
    if (!auth) return;
    const res = await api<{ api_key: string; token_balance: number }>(
      "/keys",
      { method: "POST", body: JSON.stringify({ name: "sellable", tier: "nexus" }) },
      auth.access_token
    );
    setCreated(res.api_key);
    setMsg(`Created with ${res.token_balance} tokens — copy now`);
    await refresh();
  }

  async function topup(id: string) {
    const auth = loadAuth();
    if (!auth) return;
    await api(`/keys/${id}/topup`, { method: "POST", body: JSON.stringify({ amount: 500000 }) }, auth.access_token);
    setMsg("Topped up +500,000 tokens");
    await refresh();
  }

  return (
    <Shell title="API Keys">
      <h1>API keys & sellable tokens</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Real OpenAI-compatible API at <code>/v1/chat/completions</code>. Keys look like{" "}
        <code>sk-astra-…</code> and debit token balances you can sell.
      </p>

      <div className="panel stack">
        <button onClick={createKey}>Create new API key</button>
        {created && (
          <div className="card">
            <strong>New secret (shown once)</strong>
            <pre className="event-log">{created}</pre>
          </div>
        )}
        {msg && <div className="chip">{msg}</div>}
        <div className="event-log">
{`curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-astra-..." \\
  -H "Content-Type: application/json" \\
  -d '{"model":"astracortex-nexus","messages":[{"role":"user","content":"Hello"}]}'`}
        </div>
      </div>

      <div className="panel">
        <h2>Your keys</h2>
        <div className="card-list">
          {keys.map((k) => (
            <div key={String(k.id)} className="card row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>{String(k.name)}</strong>
                <div className="muted">{String(k.key_prefix)} · {String(k.tier)}</div>
                <div className="muted">balance {String(k.token_balance)} · used {String(k.tokens_used)}</div>
              </div>
              <div className="row">
                <span className={k.is_active ? "chip" : "chip warn"}>{k.is_active ? "active" : "revoked"}</span>
                <button className="secondary" onClick={() => topup(String(k.id))}>Top up</button>
              </div>
            </div>
          ))}
          {!keys.length && <p className="muted">No keys yet — create one or register a new account.</p>}
        </div>
      </div>

      <div className="panel">
        <h2>Recent usage</h2>
        <pre className="event-log">{JSON.stringify(usage.slice(0, 20), null, 2)}</pre>
      </div>
    </Shell>
  );
}
