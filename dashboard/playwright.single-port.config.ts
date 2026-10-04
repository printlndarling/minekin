import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const port = Number(process.env.E2E_SINGLE_PORT ?? "5188");
if (!Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error("E2E_SINGLE_PORT must be between 1024 and 65535");
}
const origin = `http://127.0.0.1:${port}`;
const token = randomUUID();

export default defineConfig({
  testDir: "./e2e-single-port",
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  metadata: { smokeOrigin: origin, smokeShutdownToken: token },
  globalTeardown: "./e2e-single-port/teardown.ts",
  use: { baseURL: origin, trace: "off", video: "off", screenshot: "only-on-failure" },
  webServer: {
    command: `uv run --frozen python -m tools.serve_dashboard_smoke --port ${port}`,
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    url: origin,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { MINEKIN_SMOKE_SHUTDOWN_TOKEN: token },
  },
});
