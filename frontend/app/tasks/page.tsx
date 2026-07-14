"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function TasksPage() {
  const [sessions, setSessions] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    const auth = loadAuth();
    if (!auth) return;
    api<Record<string, unknown>[]>("/sessions", {}, auth.access_token)
      .then(setSessions)
      .catch(() => setSessions([]));
  }, []);

  return (
    <Shell>
      <h1>Sessions & tasks</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Persistent identity across sessions — resume long-horizon work anytime.
      </p>

      <div className="panel">
        <h2>Recent sessions</h2>
        <div className="card-list">
          {sessions.map((s) => (
            <div key={String(s.id)} className="card row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>{String(s.title || "Untitled")}</strong>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  {String(s.id)}
                </div>
              </div>
              <span className="chip">{String(s.status)}</span>
            </div>
          ))}
          {!sessions.length && (
            <p className="muted">
              No sessions yet. Start one from <Link href="/chat">Cognitive Chat</Link>.
            </p>
          )}
        </div>
      </div>
    </Shell>
  );
}
