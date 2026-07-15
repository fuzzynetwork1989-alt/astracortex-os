"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [advanced, setAdvanced] = useState<Record<string, unknown>>({});
  const [brain, setBrain] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  async function load() {
    const auth = loadAuth();
    if (!auth) return;
    const data = await api<{ settings: Record<string, unknown>; system: Record<string, unknown> }>(
      "/settings",
      {},
      auth.access_token
    );
    setSettings(data.settings);
    setAdvanced((data.settings.advanced as Record<string, unknown>) || {});
    setBrain((data.system.brain as Record<string, unknown>) || null);
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  async function save() {
    const auth = loadAuth();
    if (!auth) return;
    await api(
      "/settings",
      {
        method: "PUT",
        body: JSON.stringify({ ...settings, advanced }),
      },
      auth.access_token
    );
    setMsg("Settings saved");
    await load();
  }

  function setField(key: string, value: unknown) {
    setSettings((s) => ({ ...s, [key]: value }));
  }

  return (
    <Shell title="Settings">
      <h1>Settings</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Product preferences and advanced cognitive runtime controls.
      </p>
      {msg && <div className="chip" style={{ marginBottom: 12 }}>{msg}</div>}

      <div className="panel stack">
        <h2>General</h2>
        <label className="muted">Tier (hybrid routing)</label>
        <select value={String(settings.tier || "seed")} onChange={(e) => setField("tier", e.target.value)}>
          <option value="seed">Seed — Ollama 3B first, xAI failover</option>
          <option value="nexus">Nexus — Ollama 8B first, xAI failover</option>
          <option value="sovereign">Sovereign — cloud xAI first, local failover</option>
        </select>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Runtime mode is set on the API: <strong>hybrid</strong> = local Ollama + cloud xAI. See Brain status below.
        </p>
        <label className="muted">Autonomy</label>
        <select
          value={String(settings.autonomy || "act_with_approval")}
          onChange={(e) => setField("autonomy", e.target.value)}
        >
          <option value="suggest">Suggest only</option>
          <option value="act_with_approval">Act with approval</option>
          <option value="full">Full autonomy</option>
        </select>
        <label className="muted">Theme</label>
        <select value={String(settings.theme || "dark")} onChange={(e) => setField("theme", e.target.value)}>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
        <label className="muted">XR mode</label>
        <select value={String(settings.xr_mode || "off")} onChange={(e) => setField("xr_mode", e.target.value)}>
          <option value="off">Off</option>
          <option value="webxr">WebXR immersive</option>
          <option value="ar_hud">AR HUD / glasses</option>
        </select>
        <div className="row">
          <button className="secondary" onClick={() => setField("use_rag", !settings.use_rag)}>
            RAG: {settings.use_rag === false ? "off" : "on"}
          </button>
          <button className="secondary" onClick={() => setField("human_like", !settings.human_like)}>
            Human-like core: {settings.human_like === false ? "off" : "on"}
          </button>
          <button className="secondary" onClick={() => setField("stream_tokens", !settings.stream_tokens)}>
            Streaming: {settings.stream_tokens === false ? "off" : "on"}
          </button>
        </div>
      </div>

      <div className="panel stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Advanced settings</h2>
          <button className="secondary" onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? "Hide" : "Show"}
          </button>
        </div>
        {showAdvanced && (
          <>
            <label className="muted">Temperature ({String(advanced.temperature ?? 0.35)})</label>
            <input
              type="number"
              step="0.05"
              min={0}
              max={1.5}
              value={Number(advanced.temperature ?? 0.35)}
              onChange={(e) => setAdvanced((a) => ({ ...a, temperature: Number(e.target.value) }))}
            />
            <label className="muted">Max plan steps</label>
            <input
              type="number"
              value={Number(advanced.max_steps ?? 12)}
              onChange={(e) => setAdvanced((a) => ({ ...a, max_steps: Number(e.target.value) }))}
            />
            <label className="muted">Semantic write threshold</label>
            <input
              type="number"
              step="0.05"
              value={Number(advanced.semantic_write_threshold ?? 0.65)}
              onChange={(e) =>
                setAdvanced((a) => ({ ...a, semantic_write_threshold: Number(e.target.value) }))
              }
            />
            <label className="muted">Memory decay days</label>
            <input
              type="number"
              value={Number(advanced.memory_decay_days ?? 90)}
              onChange={(e) => setAdvanced((a) => ({ ...a, memory_decay_days: Number(e.target.value) }))}
            />
          </>
        )}
      </div>

      <div className="panel">
        <h2>Brain status</h2>
        <pre className="event-log">{JSON.stringify(brain, null, 2)}</pre>
      </div>

      <button onClick={save}>Save settings</button>
    </Shell>
  );
}
