import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // In development the backend runs separately; in production Caddy routes /api/*.
  async rewrites() {
    const apiUrl = process.env.JARVIS_API_URL;
    return apiUrl ? [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }] : [];
  },
};

export default config;
