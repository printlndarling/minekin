/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Where the dev server forwards `/gateway/*`. The Gateway is the frozen read-only
// contract (three GETs, and it answers no CORS preflight of its own) while the panel
// is served from another port, so a direct cross-origin fetch would be refused by the
// browser. Proxying under a path prefix keeps the panel same-origin and leaves the
// Gateway's bytes untouched: the request that leaves the browser is
// `/gateway/api/v1/dashboard/snapshot` and the one that arrives is the contract's own
// `/api/v1/dashboard/snapshot`. The target is overridable because the demo publishes
// the Gateway on a port the operator picks.
const gatewayTarget = process.env.MINEKIN_GATEWAY_TARGET ?? "http://127.0.0.1:8787";

// The same forward for `vite dev` and `vite preview`, so the built panel the demo
// ships reads a live Gateway the same way the dev server does.
const gatewayProxy = {
  "/gateway": {
    target: gatewayTarget,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/gateway/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: false,
    proxy: gatewayProxy,
  },
  preview: {
    host: "127.0.0.1",
    port: 5176,
    strictPort: false,
    proxy: gatewayProxy,
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
