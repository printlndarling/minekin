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

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: false,
    proxy: {
      "/gateway": {
        target: gatewayTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/gateway/, ""),
      },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 5176,
    strictPort: false,
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
