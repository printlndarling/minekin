import { expect, test } from "@playwright/test";

test("config draft can be discarded, while invalid fields explain why saving is blocked", async ({ page }) => {
  await page.goto("/?adapter=mock&scenario=healthy_run_07#config");
  const name = page.getByTestId("config-input-model_name");
  await expect(name).toHaveValue("deepseek-chat");
  await name.fill("draft-model");
  await expect(page.getByTestId("config-unsaved")).toContainText("未保存修改");
  await page.getByRole("button", { name: "放弃修改，读取已存配置" }).click();
  await expect(name).toHaveValue("deepseek-chat");
  await expect(page.getByTestId("config-unsaved")).toHaveCount(0);
  const goal = page.getByTestId("config-input-goal_product_id");
  await goal.fill("Invalid Id");
  await expect(goal).toHaveAttribute("aria-invalid", "true");
  await expect(goal).toHaveAccessibleDescription("必须是游戏里写法的物品 id（namespace:path，小写）。");
  await expect(page.getByTestId("config-submit")).toBeDisabled();
  await page.getByRole("button", { name: "放弃修改，读取已存配置" }).click();
  await expect(page.getByTestId("config-submit")).toBeEnabled();
});

test("model test rejects mock success and requires saving the draft first", async ({ page }) => {
  await page.goto("/?adapter=mock&scenario=healthy_run_07#config");
  const button = page.getByTestId("model-test-submit");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(page.getByTestId("model-test-result")).toContainText("模拟数据不能验证真实模型连接");
  await page.getByTestId("config-input-model_name").fill("unsaved-model");
  await expect(button).toBeDisabled();
  await expect(page.getByTestId("model-test-result")).toHaveCount(0);
  await page.getByRole("button", { name: "放弃修改，读取已存配置" }).click();
  await expect(button).toBeEnabled();
});

test("决策模式可用键盘选择：rules 进入草稿，帮助文案说明它不是 LLM 自主", async ({ page }) => {
  await page.goto("/?adapter=mock&scenario=healthy_run_07#config");
  const note = page.getByTestId("config-group-note-decision");
  await expect(note).toContainText("不是 LLM 自主");
  await expect(note).toContainText("不会自动切换");
  const select = page.getByTestId("config-input-decision_policy");
  await expect(select).toHaveValue("");
  await select.focus();
  await expect(select).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(select).toHaveValue("rules");
  await expect(page.getByTestId("config-unsaved")).toContainText("未保存修改");
  await page.getByRole("button", { name: "放弃修改，读取已存配置" }).click();
  await expect(select).toHaveValue("");
});
