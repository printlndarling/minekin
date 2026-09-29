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
//
// `changeOrigin` stays false on purpose. The three frozen reads ignore the `Host` header,
// but the one authorized identity write (`gateway.identity.authorize_write`) proves a
// rename is same-origin by requiring its `Origin` to equal the `Host` it reached. Rewriting
// `Host` to the target would make that check see `127.0.0.1:8787` against a browser
// `Origin` of `127.0.0.1:5176` and refuse the sanctioned rename as `cross_origin`. Passing
// the panel's own `Host` through is what lets the approved write clear the guard a
// cross-site request could not.
const gatewayProxy = {
  "/gateway": {
    target: gatewayTarget,
    changeOrigin: false,
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
