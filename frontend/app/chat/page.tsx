"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

type Msg = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  // Seed = qwen2.5:3b (fast). Nexus/Sovereign load bigger models and feel "stuck" on first load.
  const [tier, setTier] = useState("seed");
  const [useRag, setUseRag] = useState(false);
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
    setStatus("Generating… first reply after boot can take 20–60s (model load)");

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    const timeoutId = window.setTimeout(() => ac.abort(), 120_000);

    try {
      const reply = await api<{
        session_id: string;
        answer: string;
        model?: string;
        provider?: string;
        latency_ms?: number;
      }>(
        "/converse/reply",
        {
          method: "POST",
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
            tier,
            use_rag: useRag,
          }),
          signal: ac.signal,
        },
        auth.access_token
      );

      setSessionId(reply.session_id);
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: reply.answer || "(empty reply from model)",
        };
        return copy;
      });
      setStatus(
        `Done · ${reply.provider || "ollama"} · ${reply.model || tier} · ${reply.latency_ms ?? "?"}ms`
      );
    } catch (err) {
      const msg =
        (err as Error).name === "AbortError"
          ? "Timed out after 120s. Stay on Seed tier and ensure Ollama is running (ollama serve)."
          : err instanceof Error
            ? err.message
            : "Chat failed";
      setError(msg);
      setStatus("Error");
      setMessages((prev) => {
        const copy = [...prev];
        if (copy[copy.length - 1]?.role === "assistant" && !copy[copy.length - 1].content) {
          copy[copy.length - 1] = { role: "assistant", content: `Error: ${msg}` };
        }
        return copy;
      });
    } finally {
      window.clearTimeout(timeoutId);
      setRunning(false);
    }
  }

  function newChat() {
    abortRef.current?.abort();
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
          {sessionId && (
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              {sessionId.slice(0, 8)}…
            </span>
          )}
        </div>
        <div className="row">
          <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ width: 170 }}>
            <option value="seed">Seed · hybrid local 3B</option>
            <option value="nexus">Nexus · hybrid local 8B</option>
            <option value="sovereign">Sovereign · cloud first</option>
          </select>
          <button className="secondary" onClick={() => setUseRag((v) => !v)}>
            RAG {useRag ? "on" : "off"}
          </button>
          <button className="secondary" onClick={newChat}>
            New chat
          </button>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-messages">
          {!messages.length && (
            <div className="panel" style={{ marginTop: 40 }}>
              <h1>How can I help you work?</h1>
              <p className="muted">
                Uses a reliable full-reply path (not a frozen stream). Keep tier on{" "}
                <strong>Seed</strong> for quick answers. First message after starting Ollama can take
                ~30s while the model loads into memory.
              </p>
              <div className="row" style={{ marginTop: 14 }}>
                {["Say hello in one sentence", "What can you help me with?", "What is 2+2?"].map(
                  (s) => (
                    <button key={s} className="secondary" onClick={() => setInput(s)}>
                      {s}
                    </button>
                  )
                )}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className={`avatar ${m.role}`}>{m.role === "user" ? "U" : "A"}</div>
              <div className="msg-body">
                {m.content || (running && i === messages.length - 1 ? "…" : "")}
              </div>
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
