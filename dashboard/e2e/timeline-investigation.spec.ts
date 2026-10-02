import { expect, test } from "@playwright/test";

test("timeline search filters loaded events without a server write", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url());
  });
  await page.goto("/?adapter=mock&scenario=healthy_run_07#timeline");
  const panel = page.getByTestId("panel-timeline");
  await expect(panel.getByRole("status")).toContainText("条已加载事件");
  const search = panel.getByRole("searchbox", { name: "搜索事件" });
  await search.fill("no-such-event-unique");
  await expect(panel).toContainText("当前无匹配事件。");
  await panel.getByRole("button", { name: "清除筛选" }).click();
  await expect(search).toHaveValue("");
  await expect(panel.getByRole("button", { name: "清除筛选" })).toBeDisabled();
  await expect(panel).not.toContainText("当前无匹配事件。");
  await panel.getByRole("combobox", { name: "事件结果" }).selectOption("rejected");
  await expect(panel.getByRole("combobox", { name: "事件结果" })).toHaveValue("rejected");
  expect(writes).toEqual([]);
});
