import { expect, test } from "@playwright/test";

// Point MINEKIN_GATEWAY_TARGET at a disposable initialized Kin root (MINEKIN_ENV_FILE at an
// empty file and no MINEKIN_MODEL_* overrides in the Gateway process), then run with
// E2E_CONFIG_POLICY_LIVE=1. This proves the shipped browser -> Vite proxy -> real Gateway ->
// operator_config path: an explicit `rules` choice is saved, persisted to the document, and
// read back by the same field the panel edits — and clearing it round-trips to unset, which
// is the model default. No model call, no game, no network beyond loopback.
test("a saved rules choice persists through the live Gateway and back into the panel", async ({
  page,
}) => {
  test.skip(process.env.E2E_CONFIG_POLICY_LIVE !== "1", "Requires a disposable local Gateway root.");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?adapter=gateway&gateway=/gateway#config");
  const select = page.getByTestId("config-input-decision_policy");
  await expect(select).toHaveValue("");
  await expect(page.getByTestId("config-group-note-decision")).toContainText("不是 LLM 自主");

  await select.selectOption("rules");
  await page.getByTestId("config-submit").click();
  await expect(page.getByTestId("config-result")).toContainText("已保存");

  await page.reload();
  await expect(page.getByTestId("config-input-decision_policy")).toHaveValue("rules");

  // The whole-document save writes an omitted field as unset: clearing the choice must come
  // back as the unset affordance, whose meaning is the model default.
  await page.getByTestId("config-input-decision_policy").selectOption("");
  await page.getByTestId("config-submit").click();
  await expect(page.getByTestId("config-result")).toContainText("已保存");
  await page.reload();
  await expect(page.getByTestId("config-input-decision_policy")).toHaveValue("");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
