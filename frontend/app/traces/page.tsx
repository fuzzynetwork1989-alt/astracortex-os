"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

export default function TracesPage() {
  const [taskId, setTaskId] = useState("");
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [graph, setGraph] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const auth = loadAuth();
    if (!auth) return;
    api<Record<string, unknown>>("/traces/graph", {}, auth.access_token)
      .then(setGraph)
      .catch(() => setGraph(null));
  }, []);

  async function loadTrace() {
    const auth = loadAuth();
    if (!auth || !taskId.trim()) return;
    setError(null);
    try {
      const data = await api<Record<string, unknown>>(
        `/traces/task/${taskId.trim()}`,
        {},
        auth.access_token
      );
      setTrace(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setTrace(null);
    }
  }

  return (
    <Shell>
      <h1>Traces & cognitive graph</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Replay every plan version, tool call, reflection, and memory write — enterprise-grade
        trust layer.
      </p>

      <div className="panel stack">
        <div className="row">
          <input
            placeholder="Task UUID"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
          />
          <button onClick={loadTrace}>Replay trace</button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="panel">
        <h2>Graph overview</h2>
        <pre className="event-log" style={{ maxHeight: 240 }}>
          {JSON.stringify(graph, null, 2)}
        </pre>
      </div>

      <div className="panel">
        <h2>Task trace</h2>
        <pre className="event-log" style={{ maxHeight: 480 }}>
          {trace ? JSON.stringify(trace, null, 2) : "Load a task UUID to inspect the full run."}
        </pre>
      </div>
    </Shell>
  );
}
