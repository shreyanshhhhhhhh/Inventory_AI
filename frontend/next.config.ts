import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dev server is opened at 127.0.0.1. Allow that host to load dev assets.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
