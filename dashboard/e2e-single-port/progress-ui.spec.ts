import { expect, test } from "@playwright/test";

// Only this job read is simulated for UI state coverage. This is not a live download/game test.
test("controlled job readings render preparation and cache semantics on a narrow built page", async ({ page }, testInfo) => {
  let phase = "preparing";
  await page.route("**/api/v1/dashboard/session/job", (route) => route.fulfill({ json: {
    schemaVersion: "kin-dashboard-session-job/1.0.0",
    job: { jobId: "a".repeat(32), phase, reason: "", serverRevision: 0,
      fields: { host: "127.0.0.1", port: 25565 }, installed: phase === "preparing" ? 5 : 0,
      total: 10, outcome: null, inputReleaseFailed: null },
  } }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=.#session");
  const status = page.getByTestId("session-job-status");
  await expect(status.getByRole("progressbar")).toHaveAttribute("value", "5");
  await expect(status).toContainText("包含缓存核对");
  await expect(page.getByTestId("session-start-submit")).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await status.screenshot({ path: testInfo.outputPath("controlled-preparation.png") });
  phase = "supervising";
  await expect(status).toContainText("缓存复用 10");
  await expect(status.getByRole("progressbar")).toHaveCount(0);
  await expect(status).toContainText("是否入服、可操作仍以世界与会话读数为准");
});
