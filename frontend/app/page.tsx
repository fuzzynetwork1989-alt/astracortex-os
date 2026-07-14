"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const auth = loadAuth();
    if (!auth) return;
    api<Record<string, unknown>>("/metrics", {}, auth.access_token)
      .then(setMetrics)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const brain = (metrics?.brain || {}) as Record<string, unknown>;
  const rec = (brain.recommended || {}) as Record<string, string>;

  return (
    <Shell title="Dashboard">
      <h1>Cognitive control plane</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Hybrid mega-brain · memory · tools · sellable API tokens · multi-platform ready
      </p>

      {error && <div className="error panel">{error}</div>}

      <div className="row" style={{ marginBottom: 14 }}>
        <span className="chip">{brain.ollama_online ? "Ollama online" : "Ollama offline"}</span>
        <span className="chip blue">{brain.cloud_configured ? "Cloud ready" : "Cloud optional"}</span>
        <span className="chip warn">Mode: {String(brain.inference_mode || "hybrid")}</span>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Workspace stats</h2>
          <div className="card-list">
            {[
              ["Tasks", metrics?.tasks],
              ["Documents", metrics?.documents],
              ["Episodic memories", metrics?.episodic_memories],
              ["Semantic memories", metrics?.semantic_memories],
              ["Workflows", metrics?.workflows],
              ["Token balance", metrics?.token_balance],
              ["Tokens used", metrics?.tokens_consumed],
            ].map(([k, v]) => (
              <div key={String(k)} className="card row" style={{ justifyContent: "space-between" }}>
                <span className="muted">{k as string}</span>
                <strong>{String(v ?? "—")}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <h2>Recommended brain map</h2>
          <div className="card-list">
            {Object.entries(rec).map(([k, v]) => (
              <div key={k} className="card row" style={{ justifyContent: "space-between" }}>
                <span className="muted">{k}</span>
                <code style={{ fontSize: "0.85rem" }}>{v}</code>
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 14 }}>
            <Link href="/chat"><button>Open chat</button></Link>
            <Link href="/keys"><button className="secondary">API keys</button></Link>
            <Link href="/settings"><button className="secondary">Settings</button></Link>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Navigate</h2>
        <div className="row">
          {[
            ["/chat", "Chat"],
            ["/goals", "OS Loop"],
            ["/documents", "Knowledge"],
            ["/memory", "Memory"],
            ["/workflows", "Workflows"],
            ["/traces", "Traces"],
            ["/xr", "XR Mode"],
          ].map(([href, label]) => (
            <Link key={href} href={href}><button className="secondary">{label}</button></Link>
          ))}
        </div>
      </div>
    </Shell>
  );
}
