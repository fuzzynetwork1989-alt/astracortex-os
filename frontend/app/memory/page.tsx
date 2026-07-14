"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function MemoryPage() {
  const [episodic, setEpisodic] = useState<Record<string, unknown>[]>([]);
  const [semantic, setSemantic] = useState<Record<string, unknown>[]>([]);
  const [reflections, setReflections] = useState<Record<string, unknown>[]>([]);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  async function refresh() {
    const auth = loadAuth();
    if (!auth) return;
    const [e, s, r] = await Promise.all([
      api<Record<string, unknown>[]>("/memory/episodic", {}, auth.access_token),
      api<Record<string, unknown>[]>("/memory/semantic", {}, auth.access_token),
      api<Record<string, unknown>[]>("/memory/reflections", {}, auth.access_token),
    ]);
    setEpisodic(e);
    setSemantic(s);
    setReflections(r);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function addSemantic() {
    const auth = loadAuth();
    if (!auth || !key || !value) return;
    await api(
      "/memory/semantic",
      { method: "POST", body: JSON.stringify({ key, value, confidence: 0.9 }) },
      auth.access_token
    );
    setKey("");
    setValue("");
    await refresh();
  }

  return (
    <Shell>
      <h1>Governed memory</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Working · episodic · semantic · reflective — with provenance and conflict arbitration.
      </p>

      <div className="panel stack">
        <h2>Write semantic fact</h2>
        <input placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
        <textarea
          rows={3}
          placeholder="value"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button onClick={addSemantic}>Store (conflict-aware)</button>
      </div>

      <div className="panel">
        <h2>Semantic</h2>
        <div className="card-list">
          {semantic.map((m) => (
            <div key={String(m.id)} className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{String(m.key)}</strong>
                <span className="chip">conf {String(m.confidence)}</span>
              </div>
              <p className="muted">{String(m.value)}</p>
              {m.conflict_of ? <span className="chip warn">conflict linked</span> : null}
            </div>
          ))}
          {!semantic.length && <p className="muted">No semantic memories yet.</p>}
        </div>
      </div>

      <div className="panel">
        <h2>Episodic</h2>
        <div className="card-list">
          {episodic.map((m) => (
            <div key={String(m.id)} className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="chip">{String(m.memory_type)}</span>
                <span className="muted">imp {String(m.importance)}</span>
              </div>
              <p className="stream" style={{ fontSize: "0.9rem" }}>
                {String(m.memory_text)}
              </p>
            </div>
          ))}
          {!episodic.length && <p className="muted">No episodes yet — run a goal.</p>}
        </div>
      </div>

      <div className="panel">
        <h2>Reflections</h2>
        <div className="card-list">
          {reflections.map((r) => (
            <div key={String(r.id)} className="card">
              <div className="muted" style={{ marginBottom: 6 }}>
                {String(r.goal)}
              </div>
              <p>{String(r.critique)}</p>
              {r.goal_drift ? <span className="chip danger">goal drift</span> : null}
            </div>
          ))}
          {!reflections.length && <p className="muted">No reflections yet.</p>}
        </div>
      </div>
    </Shell>
  );
}
