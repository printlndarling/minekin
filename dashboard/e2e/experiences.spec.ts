import { expect, test } from "@playwright/test";
import { buildMockIdentity } from "../src/fixtures/mockFixtures";

// Browser transport fixtures only: this is not real-game or real-model evidence.
test("identity page reads bounded experiences and exposes provenance without replay controls", async ({ page }, testInfo) => {
  const record = {
    event_id: "experience-one", event_position: 8, run_id: "past-run", session_id: null,
    observed_at_utc: "2026-10-04T00:00:00+00:00", source: "CORE", trust_class: "CORE",
    skill: "consume_item", result: "UNKNOWN", reason: "NO_CONFIRMING_OBSERVATION", decision_source: "model",
  };
  await page.route("**/api/v1/dashboard/**", async (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/identity")) {
      await route.fulfill({ json: {
        ...buildMockIdentity("fields_unknown", Date.now()), experiences: { value: [record] },
      } });
    } else await route.abort();
  });
  await page.setViewportSize({ width: 360, height: 900 });
  await page.goto("/?adapter=gateway&gateway=/gateway#identity");
  const panel = page.getByTestId("panel-experiences");
  await expect(panel).toContainText("consume_item · 结果未知");
  await expect(panel).toContainText("不是某次模型调用的精确输入");
  await panel.getByText("事件与运行引用").click();
  await expect(panel.getByText(/event=experience-one/)).toBeVisible();
  await expect(panel.getByText(/run=past-run/)).toBeVisible();
  await expect(panel.getByRole("button")).toHaveCount(0);
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth }));
  expect(dimensions.width).toBeLessThanOrEqual(dimensions.viewport + 1);
  await panel.screenshot({ path: testInfo.outputPath("experiences-fixture-360.png") });
});
