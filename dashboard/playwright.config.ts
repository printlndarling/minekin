import { defineConfig } from "@playwright/test";

const HOST = "127.0.0.1";
const PORT = Number(process.env.E2E_PORT ?? "5176");
if (!Number.isInteger(PORT) || PORT < 1024 || PORT > 65535) {
  throw new Error("E2E_PORT must be an integer between 1024 and 65535");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://${HOST}:${PORT}`,
    trace: "off",
    video: "off",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `node ./node_modules/vite/bin/vite.js preview --host ${HOST} --port ${PORT}`,
    url: `http://${HOST}:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
