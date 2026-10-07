import { expect, test } from "@playwright/test";
import { buildMockBundle } from "../src/fixtures/mockFixtures";

test("skill outcome keeps its raw reason while diagnostics are keyboard-expandable", async ({ page }, testInfo) => {
  const wire = buildMockBundle("healthy_run_07", Date.now()).snapshot;
  const value = (wire.skillSteps as Record<string, unknown>).value as Record<string, unknown>;
  value.result = { value: "FAILED" };
  value.reason = { value: "CRAFT_MATERIALS_MISSING" };
  const writes: string[] = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url());
  });
  await page.route("**/gateway/api/v1/dashboard/snapshot", (route) => route.fulfill({ json: wire }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=/gateway#overview");
  const panel = page.getByTestId("panel-skill-steps");
  await expect(panel.getByTestId("skill-step-实际结果")).toBeVisible();
  await expect(panel.getByTestId("skill-step-结果原因")).toContainText("CRAFT_MATERIALS_MISSING");
  await expect(panel.getByTestId("skill-step-reading-guidance")).toContainText("不代表当前仍然缺料");
  await expect(panel.getByTestId("skill-step-行为参数")).not.toBeVisible();
  await panel.screenshot({ path: testInfo.outputPath("skill-reading-narrow.png") });
  const summary = panel.locator("summary").filter({ hasText: "诊断与记录详情" });
  await summary.focus();
  await summary.press("Enter");
  await expect(panel.getByTestId("skill-step-行为参数")).toBeVisible();
  await expect(panel.getByTestId("skill-step-source-note")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(writes).toEqual([]);
});
