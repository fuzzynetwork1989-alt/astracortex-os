"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, loadAuth } from "@/lib/api";
import { useEffect, useState } from "react";

const primary = [
  { href: "/", label: "Dashboard", icon: "◉" },
  { href: "/chat", label: "Chat", icon: "✦" },
  { href: "/goals", label: "Goals / OS Loop", icon: "◎" },
  { href: "/documents", label: "Knowledge", icon: "▤" },
  { href: "/memory", label: "Memory", icon: "◈" },
  { href: "/workflows", label: "Workflows", icon: "⬡" },
  { href: "/tasks", label: "Tasks", icon: "☑" },
  { href: "/traces", label: "Traces", icon: "⎇" },
];

const system = [
  { href: "/keys", label: "API Keys / Tokens", icon: "🔑" },
  { href: "/billing", label: "Billing / Plans", icon: "$" },
  { href: "/settings", label: "Settings", icon: "⚙" },
  { href: "/xr", label: "XR / Spatial", icon: "◎" },
  { href: "/privacy", label: "Privacy", icon: "ⓘ" },
  { href: "/terms", label: "Terms", icon: "§" },
];

export default function Shell({
  children,
  title,
  fullBleed,
}: {
  children: React.ReactNode;
  title?: string;
  fullBleed?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const auth = loadAuth();
    if (!auth) {
      router.replace("/login");
      return;
    }
    setEmail(auth.email);
  }, [router]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A</div>
          <div>
            <strong>ASTRA CORTEX</strong>
            <span>Cognitive OS · Hybrid Brain</span>
          </div>
        </div>

        <button
          className="nav-item"
          style={{
            marginBottom: 10,
            background: "linear-gradient(135deg,#5b8cff,#2ee6a6)",
            color: "#041018",
            fontWeight: 700,
            borderRadius: 12,
            padding: "11px 12px",
            border: 0,
            cursor: "pointer",
            width: "100%",
          }}
          onClick={() => router.push("/chat")}
        >
          + New chat
        </button>

        <div className="nav-section">Workspace</div>
        <nav className="nav">
          {primary.map((l) => (
            <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
              <span className="icon">{l.icon}</span>
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="nav-section">System</div>
        <nav className="nav">
          {system.map((l) => (
            <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
              <span className="icon">{l.icon}</span>
              {l.label}
            </Link>
          ))}
        </nav>

        <div style={{ marginTop: "auto", padding: "14px 8px 4px" }}>
          <div className="muted" style={{ fontSize: "0.8rem", marginBottom: 8 }}>
            {email}
          </div>
          <button
            className="secondary"
            style={{ width: "100%" }}
            onClick={() => {
              clearAuth();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        {!fullBleed && (
          <div className="topbar">
            <div>
              <strong>{title || "AstraCortex"}</strong>
            </div>
            <div className="row">
              <span className="chip blue">Hybrid</span>
              <span className="chip">Local + Cloud</span>
            </div>
          </div>
        )}
        {fullBleed ? children : <div className="main-body">{children}</div>}
      </div>
    </div>
  );
}
