import { defineConfig } from "@playwright/test";

const HOST = "127.0.0.1";
const PORT = 5176;

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
