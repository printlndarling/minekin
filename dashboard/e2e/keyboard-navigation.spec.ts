import { expect, test } from "@playwright/test";

test("skip navigation focuses the current panel without replacing its hash route", async ({ page }) => {
  await page.goto("/?adapter=mock&scenario=healthy_run_07#timeline");
  await expect(page.getByTestId("panel-timeline")).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "跳到当前面板" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("page-timeline")).toBeFocused();
  await expect(page).toHaveURL(/#timeline$/);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("searchbox", { name: "搜索事件" })).toBeFocused();
});
