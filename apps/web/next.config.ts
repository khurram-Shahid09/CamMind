import type { NextConfig } from "next";

// docs/14-security-privacy.md: the dashboard is never framed or sniffed. Live video arrives
// over WebRTC from go2rtc, so the page itself never needs camera or microphone access.
// (HSTS is set by Caddy in production; a script CSP needs nonces and is a v0.2 item.)
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  devIndicators: false, // keeps demo recordings and screenshots clean
  experimental: { cpus: 2 }, // fewer build workers: builds run out of memory on small machines
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
