import { expect, test } from "@playwright/test";

test("built console persists config and identity through real same-origin Gateway", async ({ page, request }) => {
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (req) => requests.push(req.url()));
  await page.goto("/");
  await expect(page).toHaveURL(/adapter=gateway&gateway=\./);
  await expect(page.getByTestId("data-source-banner")).toContainText("真实读数");
  await page.getByRole("button", { name: "配置 · 模型与目标" }).click();
  await page.getByTestId("config-input-goal_direction").fill("Inspect the nearby safe area");
  await page.getByTestId("config-input-model_request_rate").fill("0");
  await page.getByTestId("config-input-model_response_rate").fill("2000");
  await page.getByTestId("config-submit").click();
  await expect(page.getByTestId("config-result")).toContainText("已保存");
  await page.reload();
  await expect(page.getByTestId("config-input-goal_direction")).toHaveValue("Inspect the nearby safe area");
  const config = await (await request.get("/api/v1/dashboard/config")).json();
  expect(config.fields.goal_direction).toBe("Inspect the nearby safe area");
  expect(config.fields.model_request_rate).toBe(0);
  expect(config.fields.model_response_rate).toBe(2000);
  await expect(page.getByTestId("config-input-model_request_rate")).toHaveValue("0");
  await expect(page.getByTestId("config-input-model_response_rate")).toHaveValue("2000");

  await page.getByRole("button", { name: "身份 · 改名" }).click();
  await expect(page.getByTestId("identity-username")).toHaveText("minekin");
  await page.locator("#identity-new-name").fill("smoke_kin");
  await page.getByRole("checkbox").check();
  await page.getByTestId("identity-submit").click();
  await expect(page.getByTestId("identity-result")).toContainText("已改名为 smoke_kin");
  await page.reload();
  await expect(page.getByTestId("identity-username")).toHaveText("smoke_kin");
  const identity = await (await request.get("/api/v1/dashboard/identity")).json();
  expect(identity.username).toBe("smoke_kin");
  expect(identity.identityRevision).toBe(2);

  expect(errors).toEqual([]);
  expect(requests.filter((url) => !url.startsWith(new URL(page.url()).origin + "/"))).toEqual([]);
  expect(requests.some((url) => url.includes("/model/test") || url.includes("/session/start") || url.includes("/server/probe"))).toBe(false);
});

test("same-origin UI does not grant cross-origin writes or repository access", async ({ request }) => {
  const config = await (await request.get("/api/v1/dashboard/config")).json();
  const denied = await request.post("/api/v1/dashboard/config/save", {
    headers: { Origin: "http://evil.invalid", "X-Minekin-CSRF-Token": config.csrfToken },
    data: { fields: {} },
  });
  expect(denied.status()).toBe(403);
  expect((await denied.json()).error).toBe("cross_origin");
  for (const path of ["/env.txt", "/.git/config", "/assets/secret.js.map", "/api/v1/unknown"]) {
    const result = await request.get(path);
    expect(result.status()).toBe(404);
    expect(result.headers()["content-type"]).toContain("application/json");
  }
});
