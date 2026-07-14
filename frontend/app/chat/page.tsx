"use client";

import Shell from "@/components/Shell";
import { api, getApiUrl, loadAuth, readSSE } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

type Msg = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [tier, setTier] = useState("nexus");
  const [useRag, setUseRag] = useState(true);
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, running]);

  async function send() {
    const auth = loadAuth();
    if (!auth || !input.trim() || running) return;
    const text = input.trim();
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setRunning(true);
    setStatus("Thinking…");
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const start = await api<{ session_id: string; stream_url: string }>(
        "/converse",
        {
          method: "POST",
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
            tier,
            use_rag: useRag,
          }),
        },
        auth.access_token
      );
      setSessionId(start.session_id);
      const qs = new URLSearchParams({ tier, use_rag: String(useRag) });
      const url = `${getApiUrl()}/converse/stream/${start.session_id}?${qs}`;
      await readSSE(
        url,
        auth.access_token,
        (event, data) => {
          if (event === "token") {
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") {
                copy[copy.length - 1] = {
                  role: "assistant",
                  content: last.content + String(data.token || ""),
                };
              }
              return copy;
            });
            setStatus("Streaming");
          } else if (event === "retrieval") {
            setStatus(`Retrieved ${((data.citations as unknown[]) || []).length} sources`);
          } else if (event === "status") {
            setStatus(String(data.status || "working"));
          } else if (event === "done") {
            if (data.answer) {
              setMessages((prev) => {
                const copy = [...prev];
                copy[copy.length - 1] = { role: "assistant", content: String(data.answer) };
                return copy;
              });
            }
            setStatus("Done");
          } else if (event === "error") {
            setError(String(data.detail || "error"));
          }
        },
        ac.signal
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof Error ? err.message : "Chat failed");
        setStatus("Error");
      }
    } finally {
      setRunning(false);
    }
  }

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setStatus("Ready");
    setError(null);
  }

  return (
    <Shell fullBleed title="Chat">
      <div className="topbar">
        <div className="row">
          <strong>Chat</strong>
          <span className="chip">{status}</span>
          {sessionId && <span className="muted" style={{ fontSize: "0.8rem" }}>{sessionId.slice(0, 8)}…</span>}
        </div>
        <div className="row">
          <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ width: 140 }}>
            <option value="seed">Seed</option>
            <option value="nexus">Nexus</option>
            <option value="sovereign">Sovereign</option>
          </select>
          <button className="secondary" onClick={() => setUseRag((v) => !v)}>
            RAG {useRag ? "on" : "off"}
          </button>
          <button className="secondary" onClick={newChat}>New chat</button>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-messages">
          {!messages.length && (
            <div className="panel" style={{ marginTop: 40 }}>
              <h1>How can I help you work?</h1>
              <p className="muted">
                AstraCortex hybrid brain — local Ollama (deepseek-r1 / llama3.1) + optional cloud.
                Chat normally, or use Goals for full plan→act→reflect OS loops.
              </p>
              <div className="row" style={{ marginTop: 14 }}>
                {[
                  "Summarize my knowledge base with citations",
                  "Plan a product launch workflow",
                  "What do you remember about my goals?",
                ].map((s) => (
                  <button key={s} className="secondary" onClick={() => setInput(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className={`avatar ${m.role}`}>{m.role === "user" ? "U" : "A"}</div>
              <div className="msg-body">{m.content || (running && i === messages.length - 1 ? "…" : "")}</div>
            </div>
          ))}
          {error && <div className="error">{error}</div>}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          <textarea
            rows={2}
            placeholder="Message AstraCortex…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <div className="composer-actions">
            <button onClick={send} disabled={running || !input.trim()}>
              {running ? "…" : "Send"}
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}
