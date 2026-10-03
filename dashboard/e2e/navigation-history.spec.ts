import { expect, test } from "@playwright/test";

test("back and forward restore panels without losing the data source", async ({ page }) => {
  await page.goto("/?adapter=mock&scenario=healthy_run_07#task");
  await expect(page.getByTestId("panel-goal")).toBeVisible();
  await page.getByRole("navigation", { name: "面板" }).getByRole("button", { name: /^时间线/ }).click();
  await expect(page.getByTestId("panel-timeline")).toBeVisible();
  await page.getByRole("navigation", { name: "面板" }).getByRole("button", { name: /^告警/ }).click();
  await expect(page.getByTestId("panel-alerts")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId("panel-timeline")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId("panel-goal")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("panel-timeline")).toBeVisible();
  expect(new URL(page.url()).searchParams.get("adapter")).toBe("mock");
  expect(new URL(page.url()).searchParams.get("scenario")).toBe("healthy_run_07");
});
