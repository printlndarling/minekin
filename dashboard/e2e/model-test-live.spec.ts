import { expect, test } from "@playwright/test";

// Point MINEKIN_GATEWAY_TARGET at a disposable initialized Kin root with no
// MINEKIN_MODEL_* environment overrides, then run with E2E_MODEL_TEST_LIVE=1.
// This proves the shipped browser -> Vite proxy -> actual Gateway -> provider-off path.
test("saved off configuration gives an honest zero-call result through the live Gateway", async ({ page }) => {
  test.skip(process.env.E2E_MODEL_TEST_LIVE !== "1", "Requires a disposable local Gateway root.");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=/gateway#config");
  await page.getByTestId("config-input-model_provider").selectOption("off");
  await page.getByTestId("config-submit").click();
  await expect(page.getByTestId("config-result")).toContainText("已保存");
  const button = page.getByTestId("model-test-submit");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(page.getByTestId("model-test-result")).toContainText("MODEL_NOT_CONFIGURED");
  await expect(page.getByTestId("model-test-result")).toContainText("调用记录 0");
  await expect(page.getByTestId("model-test-result")).not.toContainText("格式通过");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/model-test-settings-mobile.png", fullPage: true });
});
