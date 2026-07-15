import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="auth-page">
      <div className="panel auth-card stack" style={{ maxWidth: 720, width: "100%" }}>
        <h1>Terms of Service — AstraCortex OS</h1>
        <p className="muted">Last updated: 2026-07-15</p>
        <p>
          By using AstraCortex OS you agree to use it lawfully. AI outputs may be wrong — review them
          before acting. You are responsible for content you upload and for securing your API keys.
        </p>
        <h2>Offline / hybrid</h2>
        <p className="muted">
          Local mode uses Ollama on your network and does not require the public internet. Cloud
          features need network access and optional provider keys.
        </p>
        <h2>API tokens</h2>
        <p className="muted">
          <code>sk-astra-*</code> keys are metered. Revoke lost keys immediately.
        </p>
        <Link href="/login">
          <button className="secondary">Back to login</button>
        </Link>
      </div>
    </div>
  );
}
