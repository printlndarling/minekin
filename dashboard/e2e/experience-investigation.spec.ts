import { expect, test } from "@playwright/test";
import { buildMockIdentity } from "../src/fixtures/mockFixtures";

test("experience investigation filters loaded provenance without sending a write", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url());
  });
  await page.route("**/gateway/api/v1/dashboard/identity", (route) => route.fulfill({
    json: {
      ...buildMockIdentity("fields_unknown", Date.now()),
      experiences: { value: [
        { event_id: "model-attempt", event_position: 2, run_id: "run-model", session_id: null,
          observed_at_utc: "2026-10-07T00:00:00+00:00", source: "CORE", trust_class: "CORE",
          skill: "collect_dropped", result: "UNKNOWN", reason: "COLLECT_APPROACH_STALLED", decision_source: "model" },
        { event_id: "rule-attempt", event_position: 1, run_id: "run-rule", session_id: null,
          observed_at_utc: "2026-10-07T00:00:00+00:00", source: "CORE", trust_class: "CORE",
          skill: "turn_to", result: "CONFIRMED", reason: "", decision_source: "local_reflection" },
      ] },
    },
  }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=/gateway#identity");
  const panel = page.getByTestId("panel-experiences");
  await expect(panel.getByRole("status")).toContainText("显示 2 / 2");
  await panel.getByRole("combobox", { name: "经历决策来源" }).selectOption("model");
  await panel.getByRole("combobox", { name: "经历结果" }).selectOption("UNKNOWN");
  await panel.getByRole("searchbox", { name: "搜索经历" }).fill("collect_approach");
  await expect(panel).toContainText("显示 1 / 2");
  await expect(panel).not.toContainText("turn_to · 已确认");
  await panel.getByRole("button", { name: "清除经历筛选" }).click();
  await expect(panel).toContainText("turn_to · 已确认");
  expect(writes).toEqual([]);
});
