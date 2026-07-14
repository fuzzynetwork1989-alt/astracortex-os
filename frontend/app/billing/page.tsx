"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function BillingPage() {
  const [plans, setPlans] = useState<Record<string, unknown> | null>(null);
  const [sub, setSub] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);

  async function refresh() {
    const auth = loadAuth();
    if (!auth) return;
    const [p, s] = await Promise.all([
      api<Record<string, unknown>>("/billing/plans", {}, auth.access_token),
      api<Record<string, unknown>>("/billing/subscription", {}, auth.access_token),
    ]);
    setPlans(p);
    setSub(s);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function activate(planId: string) {
    const auth = loadAuth();
    if (!auth) return;
    const res = await api<{ api_key?: string; plan: string; token_grant: number }>(
      "/billing/activate",
      { method: "POST", body: JSON.stringify({ plan_id: planId }) },
      auth.access_token
    );
    setMsg(`Activated ${res.plan} · granted ${res.token_grant} tokens`);
    if (res.api_key) setNewKey(res.api_key);
    await refresh();
  }

  async function buyPack(packId: string) {
    const auth = loadAuth();
    if (!auth) return;
    const res = await api<{ added: number; api_key?: string }>(
      "/billing/token-pack",
      { method: "POST", body: JSON.stringify({ pack_id: packId }) },
      auth.access_token
    );
    setMsg(`Added ${res.added} tokens`);
    if (res.api_key) setNewKey(res.api_key);
    await refresh();
  }

  const planList = (plans?.plans as Record<string, unknown>[]) || [];
  const packs = (plans?.token_packs as Record<string, unknown>[]) || [];
  const xr = (plans?.xr_addons as Record<string, unknown>[]) || [];

  return (
    <Shell title="Billing">
      <h1>Plans & monetization</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Self-serve SaaS tiers + sellable API token packs. Tokens work immediately on{" "}
        <code>/v1/chat/completions</code>.
      </p>
      {msg && <div className="chip" style={{ marginBottom: 12 }}>{msg}</div>}
      {newKey && (
        <div className="panel">
          <strong>New API key (save now)</strong>
          <pre className="event-log">{newKey}</pre>
        </div>
      )}

      <div className="panel">
        <h2>Current subscription</h2>
        <pre className="event-log">{JSON.stringify(sub, null, 2)}</pre>
      </div>

      <div className="grid-2">
        {planList.map((p) => (
          <div key={String(p.id)} className="panel stack">
            <h2>{String(p.name)}</h2>
            <div className="chip blue">
              {p.price_monthly_usd != null ? `$${p.price_monthly_usd}/mo` : "Custom"}
            </div>
            <div className="muted">Tokens: {String(p.token_grant)}</div>
            <ul className="muted">
              {((p.features as string[]) || []).map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            {p.price_monthly_usd != null && (
              <button onClick={() => activate(String(p.id))}>Activate {String(p.id)}</button>
            )}
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Token packs</h2>
        <div className="row">
          {packs.map((pack) => (
            <button key={String(pack.id)} className="secondary" onClick={() => buyPack(String(pack.id))}>
              {String(pack.tokens)} tokens · ${String(pack.price_usd)}
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>XR add-ons (roadmap pricing)</h2>
        <div className="card-list">
          {xr.map((a) => (
            <div key={String(a.id)} className="card">
              <strong>{String(a.name)}</strong>
              <div className="muted">{JSON.stringify(a)}</div>
            </div>
          ))}
        </div>
      </div>
    </Shell>
  );
}
