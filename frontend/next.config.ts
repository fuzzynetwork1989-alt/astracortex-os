import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Docker image can re-enable standalone; local `next start` uses default output.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
