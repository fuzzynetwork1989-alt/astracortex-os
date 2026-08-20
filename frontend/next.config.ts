import type { NextConfig } from "next";
import path from "path";

/**
 * PERMANENT RULE:
 * Do NOT add rewrites that proxy /backend/* → FastAPI for app data/LLM calls.
 * Next.js rewrite proxy drops long requests (ECONNRESET / socket hang up).
 * The browser talks to FastAPI directly; CORS is open on the API.
 *
 * Optional legacy rewrite is DISABLED by default. Only enable with
 * ENABLE_LEGACY_API_PROXY=1 for debugging static assets — never for chat.
 */
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "connect-src 'self' https: wss:",
      "frame-ancestors 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // Avoid proxy entirely
  async rewrites() {
    if (process.env.ENABLE_LEGACY_API_PROXY === "1") {
      const target = (
        process.env.API_PROXY_TARGET ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://127.0.0.1:8000"
      ).replace(/\/$/, "");
      return [{ source: "/backend/:path*", destination: `${target}/:path*` }];
    }
    return [];
  },
};

export default nextConfig;
