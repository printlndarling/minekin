import { expect, test } from "@playwright/test";

// Local disposable Docker Gateway and Minecraft 1.20.1 server on container loopback.
// MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8789 E2E_SERVER_CONFIG_LIVE=1
test("save, reload and probe the actual local server at mobile width", async ({ page }) => {
  test.skip(process.env.E2E_SERVER_CONFIG_LIVE !== "1", "Requires controlled local Minecraft and Gateway.");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=/gateway#server");
  await expect(page.getByTestId("server-save")).toBeEnabled();
  await page.getByTestId("server-host").fill("127.0.0.1");
  await page.getByTestId("server-port").fill("");
  await page.getByTestId("server-port").fill("25566");
  await expect(page.getByTestId("server-probe")).toBeDisabled();
  await page.getByTestId("server-save").click();
  await expect(page.getByTestId("server-save-result")).toContainText("已保存");
  await page.reload();
  await expect(page.getByTestId("server-port")).toHaveValue("25566");
  await page.getByTestId("server-probe").click();
  const result = page.getByTestId("server-probe-result");
  await expect(result).toContainText("OBSERVED");
  await expect(result).toContainText("1.20.1");
  await expect(result).toContainText("763");
  await expect(result).toContainText("RESOLVED");
  await expect(result).toContainText("linux");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/server-settings-mobile.png", fullPage: true });
  await page.getByTestId("server-port").fill("25567");
  await expect(page.getByTestId("server-probe")).toBeDisabled();
  await expect(result).toHaveCount(0);
  await page.getByRole("button", { name: "放弃服务器草稿" }).click();
  await expect(page.getByTestId("server-port")).toHaveValue("25566");
});
