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
