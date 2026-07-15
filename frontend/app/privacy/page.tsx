import Link from "next/link";

export default function PrivacyPage() {
  return (
    <div className="auth-page">
      <div className="panel auth-card stack" style={{ maxWidth: 720, width: "100%" }}>
        <h1>Privacy Policy — AstraCortex OS</h1>
        <p className="muted">Last updated: 2026-07-15 · Required for App Store / Play Store</p>
        <p>
          AstraCortex OS processes account data (email, name, password hash), chat content, uploaded
          documents, and usage metrics to provide the Cognitive OS service.
        </p>
        <h2>Data we process</h2>
        <ul className="muted">
          <li>Account credentials (passwords stored as bcrypt hashes)</li>
          <li>Messages, tasks, memory records, and documents you upload</li>
          <li>API keys and token usage counters</li>
          <li>Optional device/API URL settings on mobile</li>
        </ul>
        <h2>Where data lives</h2>
        <p className="muted">
          Local/self-host mode keeps data on your machine (PostgreSQL + Ollama). Cloud deploy uses
          your configured database. We do not sell personal data.
        </p>
        <h2>AI processing</h2>
        <p className="muted">
          Prompts go to local Ollama (works offline) and/or an optional cloud provider you configure.
        </p>
        <h2>Contact</h2>
        <p className="muted">github.com/fuzzynetwork1989-alt/astracortex-os</p>
        <Link href="/login">
          <button className="secondary">Back to login</button>
        </Link>
      </div>
    </div>
  );
}
