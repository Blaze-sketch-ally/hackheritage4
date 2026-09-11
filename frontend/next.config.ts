import path from "node:path";
import os from "node:os";

import type { NextConfig } from "next";

function getLocalDevOrigins(): string[] {
  const origins = new Set<string>(["localhost", "127.0.0.1"]);
  try {
    const interfaces = os.networkInterfaces();
    for (const netList of Object.values(interfaces)) {
      if (!netList) continue;
      for (const net of netList) {
        if (net.family === "IPv4" && !net.internal) {
          origins.add(net.address);
        }
      }
    }
  } catch {}
  if (process.env.ALLOWED_DEV_ORIGINS) {
    process.env.ALLOWED_DEV_ORIGINS.split(",").forEach((o) => {
      const trimmed = o.trim();
      if (trimmed) origins.add(trimmed);
    });
  }
  return Array.from(origins);
}

const nextConfig: NextConfig = {
  // Pin the workspace root to this directory. Without it, Turbopack walks
  // up the tree and finds an unrelated ~/package-lock.json, logging a
  // "inferred workspace root" warning on every start.
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Allows development asset chunks and HMR access when testing over local Wi-Fi / IP
  // (e.g. physical mobile devices) without triggering 403 Forbidden dev-security blocks.
  allowedDevOrigins: getLocalDevOrigins(),
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl.replace(/\/$/, "")}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
