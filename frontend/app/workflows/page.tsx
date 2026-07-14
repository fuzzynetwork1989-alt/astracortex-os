"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function WorkflowsPage() {
  const [goal, setGoal] = useState("");
  const [list, setList] = useState<Record<string, unknown>[]>([]);
  const [compiled, setCompiled] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const auth = loadAuth();
    if (!auth) return;
    setList(await api("/workflows", {}, auth.access_token));
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function compile() {
    const auth = loadAuth();
    if (!auth || !goal.trim()) return;
    setBusy(true);
    try {
      const res = await api<Record<string, unknown>>(
        "/workflows/compile",
        { method: "POST", body: JSON.stringify({ goal, save: true }) },
        auth.access_token
      );
      setCompiled(res);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell title="Workflows">
      <h1>Goal → workflow compiler</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Turns plain-language goals into reusable cognitive recipes (versioned, savable, monetizable).
      </p>

      <div className="panel stack">
        <textarea
          rows={4}
          placeholder="e.g. Every Monday, research competitors, summarize product changes, draft exec brief with citations."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
        />
        <button onClick={compile} disabled={busy || !goal.trim()}>
          {busy ? "Compiling…" : "Compile workflow"}
        </button>
      </div>

      {compiled && (
        <div className="panel">
          <h2>Last compile</h2>
          <pre className="event-log">{JSON.stringify(compiled, null, 2)}</pre>
        </div>
      )}

      <div className="panel">
        <h2>Saved workflows</h2>
        <div className="card-list">
          {list.map((w) => (
            <div key={String(w.id)} className="card">
              <strong>{String(w.name)}</strong>
              <div className="muted">{String(w.goal_pattern)}</div>
            </div>
          ))}
          {!list.length && <p className="muted">No workflows yet.</p>}
        </div>
      </div>
    </Shell>
  );
}
