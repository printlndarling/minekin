import { expect, test } from "@playwright/test";

// Opt-in read-only acceptance against an actual Gateway and reviewed Kin ledger.
// The supplied root may be a readonly validation copy; no input/session writes are sent.
test("real Gateway history reaches the identity page without rewriting past verdicts", async ({ page, request }, testInfo) => {
  test.skip(process.env.E2E_LIVE_EXPERIENCES !== "1", "Requires a real local Gateway with recorded skill experiences.");
  const response = await request.get("/gateway/api/v1/dashboard/identity");
  expect(response.ok()).toBe(true);
  const identity = await response.json();
  const records = identity.experiences.value;
  expect(Array.isArray(records)).toBe(true);
  expect(records.length).toBeGreaterThan(0);
  expect(records.length).toBeLessThanOrEqual(8);
  const writes: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/") && req.method() !== "GET") writes.push(req.method());
  });
  await page.setViewportSize({ width: 768, height: 900 });
  await page.goto("/?adapter=gateway&gateway=/gateway#identity");
  const panel = page.getByTestId("panel-experiences");
  await expect(panel.getByRole("list", { name: "最近行为经历" }).getByRole("listitem")).toHaveCount(records.length);
  const first = panel.getByRole("listitem").first();
  await expect(first).toContainText(records[0].skill);
  const expectedLabels: Record<string, string> = {
    CONFIRMED: "已确认", UNKNOWN: "结果未知", FAILED: "失败", INTERRUPTED: "已中断", STARTED: "已开始",
  };
  const expectedLabel = expectedLabels[records[0].result as string];
  // A result token with no label is a reading this test cannot judge; failing on the
  // missing label keeps the assertion from passing on an empty substring instead.
  expect(expectedLabel, `unknown experience result token: ${records[0].result}`).toBeDefined();
  await expect(first).toContainText(expectedLabel as string);
  await first.getByText("事件与运行引用").click();
  await expect(first.getByText(`event=${records[0].event_id} · position=${records[0].event_position}`)).toBeVisible();
  await expect(panel).toContainText("过去结果不证明当前世界");
  await expect(panel.getByRole("button", { name: /重放|执行/ })).toHaveCount(0);
  // Read-side filtering is allowed; it must preserve the actual Gateway records.
  await panel.getByRole("searchbox", { name: "搜索经历" }).fill(records[0].event_id);
  await expect(panel.getByRole("listitem")).toHaveCount(1);
  await expect(panel.getByRole("listitem")).toContainText(records[0].skill);
  await panel.getByRole("button", { name: "清除经历筛选" }).click();
  await expect(panel.getByRole("listitem")).toHaveCount(records.length);
  expect(writes).toEqual([]);
  await panel.screenshot({ path: testInfo.outputPath("experiences-real-ledger.png") });
});
