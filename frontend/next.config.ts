import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // T222 (Phase 23, Docker and Local Deployment): the multi-stage
  // frontend.Dockerfile's runtime stage copies only .next/standalone +
  // .next/static + public/ — standalone output bundles a minimal
  // node_modules subset into .next/standalone itself, so the final image
  // needs no separate `npm install` layer.
  output: "standalone",
};

export default nextConfig;
