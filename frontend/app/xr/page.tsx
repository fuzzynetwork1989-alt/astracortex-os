"use client";

import Shell from "@/components/Shell";
import { api, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

/**
 * Real WebXR-capable spatial shell.
 * Works in browsers with WebXR (Quest browser, Chrome desktop with headset, etc.)
 * AR HUD layout for RayNeo-style glasses (narrow safe viewport).
 */
export default function XRPage() {
  const [xrSupported, setXrSupported] = useState<boolean | null>(null);
  const [mode, setMode] = useState<"desktop" | "webxr" | "ar_hud">("desktop");
  const [sessionActive, setSessionActive] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [layout, setLayout] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const nav = navigator as Navigator & { xr?: { isSessionSupported: (m: string) => Promise<boolean> } };
    if (nav.xr) {
      nav.xr.isSessionSupported("immersive-vr")
        .then((ok) => setXrSupported(ok))
        .catch(() => setXrSupported(false));
    } else {
      setXrSupported(false);
    }
    const auth = loadAuth();
    if (!auth) return;
    const device = "webxr";
    api<Record<string, unknown>>(`/xr/state?device=${device}`, {}, auth.access_token)
      .then(setState)
      .catch(() => setState(null));
    api<Record<string, unknown>>(`/xr/layouts?device=${device}`, {}, auth.access_token)
      .then(setLayout)
      .catch(() => setLayout(null));
  }, []);

  async function enterWebXR() {
    const nav = navigator as Navigator & {
      xr?: {
        requestSession: (m: string, init?: object) => Promise<{
          addEventListener: (type: string, listener: () => void) => void;
          end: () => Promise<void>;
        }>;
      };
    };
    if (!nav.xr) {
      setLog((l) => [...l, "WebXR not available in this browser"]);
      return;
    }
    try {
      const session = await nav.xr.requestSession("immersive-vr", {
        optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"],
      });
      setSessionActive(true);
      setMode("webxr");
      setLog((l) => [...l, "WebXR session started — AstraCortex spatial control plane active"]);
      session.addEventListener("end", () => {
        setSessionActive(false);
        setLog((l) => [...l, "WebXR session ended"]);
      });
    } catch (e) {
      setLog((l) => [...l, `WebXR request failed: ${(e as Error).message}`]);
    }
  }

  return (
    <Shell title="XR / Spatial">
      <h1>Spatial cognitive layer</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Same AstraCortex brain, XR-ready frontends: Quest / WebXR immersive and AR glasses HUD layout.
      </p>

      <div className="row" style={{ marginBottom: 14 }}>
        <span className="chip blue">
          WebXR: {xrSupported === null ? "checking…" : xrSupported ? "supported" : "not supported here"}
        </span>
        <span className="chip">{sessionActive ? "session active" : "session idle"}</span>
        <span className="chip warn">Mode: {mode}</span>
      </div>

      <div className="panel stack">
        <div className="row">
          <button onClick={() => setMode("desktop")}>Desktop panels</button>
          <button className="secondary" onClick={() => setMode("ar_hud")}>
            AR HUD layout
          </button>
          <button className="secondary" onClick={enterWebXR} disabled={xrSupported === false}>
            Enter WebXR (VR)
          </button>
        </div>
      </div>

      {mode === "ar_hud" ? (
        <div
          className="panel"
          style={{
            maxWidth: 720,
            margin: "16px auto",
            border: "2px solid rgba(46,230,166,0.4)",
            background: "rgba(0,0,0,0.55)",
          }}
        >
          <h2>RayNeo / glasses HUD</h2>
          <p className="muted">Glanceable memory · approvals · short answers — optimized safe area.</p>
          <div className="card">
            <strong>Next action</strong>
            <div className="muted">Open Chat and pin this session for HUD stream.</div>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button>Approve</button>
            <button className="secondary">Defer</button>
            <button className="secondary">Recall memory</button>
          </div>
        </div>
      ) : (
        <div className="grid-2">
          <div className="panel">
            <h2>Spatial home base</h2>
            <p className="muted">Tasks, memory, and plans as spatial panels for Quest 3 mixed reality.</p>
            <div className="card">Floating task graph · plan nodes · approval orbs</div>
          </div>
          <div className="panel">
            <h2>Device map</h2>
            <div className="card-list">
              <div className="card">Meta Quest 3 — immersive MR workspace</div>
              <div className="card">RayNeo Air 4 Pro — USB-C AR HUD overlay</div>
              <div className="card">Desktop — full admin + cognitive chat</div>
              <div className="card">Mobile — chat + approvals + memory</div>
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <h2>Live XR state (API)</h2>
        <pre className="event-log">{JSON.stringify(state, null, 2)}</pre>
      </div>
      <div className="panel">
        <h2>Layouts catalog</h2>
        <pre className="event-log">{JSON.stringify(layout, null, 2)}</pre>
      </div>
      <div className="panel">
        <h2>XR event log</h2>
        <div className="row" style={{ marginBottom: 10 }}>
          <button
            className="secondary"
            onClick={async () => {
              const auth = loadAuth();
              if (!auth) return;
              await api(
                "/xr/events",
                {
                  method: "POST",
                  body: JSON.stringify({ event_type: "approve", device: "quest3", payload: { source: "ui" } }),
                },
                auth.access_token
              );
              setLog((l) => [...l, "Posted xr.approve event"]);
            }}
          >
            Send approve event
          </button>
        </div>
        <pre className="event-log">{log.join("\n") || "No XR events yet."}</pre>
      </div>
    </Shell>
  );
}
