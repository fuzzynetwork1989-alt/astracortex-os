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
const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
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
