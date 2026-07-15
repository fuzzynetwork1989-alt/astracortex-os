"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

type Doc = {
  id: string;
  file_name: string;
  status: string;
  mime_type?: string;
  created_at?: string;
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const auth = loadAuth();
    if (!auth) return;
    const list = await api<Doc[]>("/documents", {}, auth.access_token);
    setDocs(list);
  }

  useEffect(() => {
    refresh().catch(() => setDocs([]));
  }, []);

  async function onUpload(file: File | null) {
    if (!file) return;
    const auth = loadAuth();
    if (!auth) return;
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await api<Doc>(
        "/documents/upload",
        { method: "POST", body: form },
        auth.access_token
      );
      const ingested = await api<{ chunks: number }>(
        `/documents/${uploaded.id}/ingest`,
        { method: "POST" },
        auth.access_token
      );
      setMsg(`Ingested ${file.name} → ${ingested.chunks} chunks`);
      await refresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <h1>Knowledge layer</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Documents are chunked, embedded, and retrieved with hybrid scoring + citations.
      </p>

      <div className="panel stack">
        <input
          type="file"
          accept=".txt,.md,.csv,.json,.log"
          disabled={busy}
          onChange={(e) => onUpload(e.target.files?.[0] || null)}
        />
        <p className="muted">
          Prefer plain text / markdown (.txt, .md, .csv, .json, .log). Do not upload Windows shortcuts
          (.lnk) — upload the real file.
        </p>
        {msg && <div className="chip">{msg}</div>}
      </div>

      <div className="panel">
        <h2>Library</h2>
        <div className="card-list">
          {docs.map((d) => (
            <div key={d.id} className="card row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>{d.file_name}</strong>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  {d.id}
                </div>
              </div>
              <span className={d.status === "ingested" ? "chip" : "chip warn"}>{d.status}</span>
            </div>
          ))}
          {!docs.length && <p className="muted">No documents yet.</p>}
        </div>
      </div>
    </Shell>
  );
}
