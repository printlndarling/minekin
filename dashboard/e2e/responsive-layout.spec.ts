import { expect, test } from "@playwright/test";

// These checks use explicit MOCK data to exercise layout, not game acceptance.
for (const width of [360, 768, 1440]) {
  test(`console keeps its navigation and data inside a ${width}px viewport`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?adapter=mock&scenario=healthy_run_07#overview");
    await expect(page.getByTestId("panel-kin")).toBeVisible();
    await expect(page.getByTestId("panel-kin")).toContainText("运行中");
    await expect(page.getByTestId("data-source-banner")).toContainText("MOCK");
    await page.screenshot({ path: testInfo.outputPath(`overview-${width}.png`), fullPage: true });
    for (const route of ["overview", "timeline", "config", "identity", "session", "recipes", "data"]) {
      await page.goto(`/?adapter=mock&scenario=healthy_run_07#${route}`);
      await expect(page.getByTestId(`page-${route}`)).toBeVisible();
      if (route === "overview") await expect(page.getByTestId("panel-kin")).toContainText("运行中");
      if (route === "timeline") await expect(page.getByTestId("panel-timeline")).toContainText("观察");
      const dimensions = await page.evaluate(() => ({
        content: document.documentElement.scrollWidth,
        viewport: document.documentElement.clientWidth,
      }));
      expect(dimensions.content, `${route} overflows at ${width}px`).toBeLessThanOrEqual(dimensions.viewport + 1);
    }
    const nav = page.getByRole("navigation", { name: "面板" });
    await nav.getByRole("button", { name: "时间线" }).click();
    await expect(page.getByTestId("page-timeline")).toBeVisible();
    const button = nav.getByRole("button", { name: "时间线" });
    await expect(button).toHaveAttribute("aria-current", "page");
    expect((await button.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  });
}
