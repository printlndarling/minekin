import { expect, test, type Page } from "@playwright/test";

const ACTION_WORDS = ["启动", "暂停", "停止", "注入", "发送", "执行", "保存", "连接服务器", "重连"];

function url(adapter: string, scenario?: string): string {
  const query = adapter === "mock" ? `?adapter=mock&scenario=${scenario ?? "healthy_run_07"}` : `?adapter=${adapter}`;
  return `/${query}`;
}

async function openMock(page: Page, scenario: string): Promise<void> {
  await page.goto(url("mock", scenario));
  await expect(page.getByTestId("data-source-banner")).toContainText("模拟数据 MOCK");
}

test.describe("只读 Dashboard 外壳关键流程", () => {
  test("健康场景：状态、会话与证据面板给出已知读数并标注模拟来源", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await expect(page.getByTestId("panel-kin")).toContainText("运行中");
    // §3 的 C 档成员渲染为 not_wired 缺口并带 Core 的理由，而不是自填的模式值。
    await expect(page.getByTestId("panel-session")).toContainText("未接入");
    await expect(page.getByTestId("panel-session")).toContainText("Core 尚无会话模式枚举");
    await expect(page.getByTestId("panel-session")).not.toContainText("B 独立");
    await expect(page.getByTestId("panel-evidence")).toContainText("mock://");
    await expect(page.getByTestId("schema-version")).toContainText("kin-dashboard-readmodel/1.0.0");
    await expect(page.getByTestId("schema-version")).not.toContainText("proposal");
  });

  test("失联场景：Bridge 显示已失联而不是猜测值", async ({ page }) => {
    await openMock(page, "bridge_disconnected");
    const panel = page.getByTestId("panel-kin");
    await expect(panel).toContainText("已失联");
    await expect(panel).toContainText("未定（无法判定）");
    await expect(panel).not.toContainText("运行中");
  });

  test("陈旧场景：观测值带陈旧标记", async ({ page }) => {
    await openMock(page, "stale_observations");
    await expect(page.getByTestId("panel-kin")).toContainText("陈旧");
  });

  test("字段未知场景：缺失字段显示未知与原因，不补默认值", async ({ page }) => {
    await openMock(page, "fields_unknown");
    const panel = page.getByTestId("panel-kin");
    await expect(panel).toContainText("未知");
    await expect(panel).toContainText("mock://");
  });

  test("无 Gateway 基址：不发起伪读数，直接显示未配置，且不发出 /api 请求", async ({ page }) => {
    const apiRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
    });
    await page.goto(url("gateway"));
    await expect(page.getByTestId("data-source-banner")).toContainText("真实读数");
    await expect(page.getByTestId("read-failure")).toContainText("not_configured");
    await expect(page.getByTestId("panel-session")).toContainText("未知");
    expect(apiRequests).toEqual([]);
  });

  test("常驻上下文条：四个问题一起在场，且都来自读数", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await expect(page.getByTestId("context-who")).toContainText("它是谁");
    await expect(page.getByTestId("context-where")).toContainText("在哪个世界");
    await expect(page.getByTestId("context-doing")).toContainText("最远阶段");
    await expect(page.getByTestId("context-why")).toContainText("为什么没运行");
    await expect(page.getByTestId("context-who")).toContainText("minekin");
  });

  test("数据源与缺口页：观战帧源按未接入具名说明，不渲染任何画面元素", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await page.getByRole("button", { name: "数据源与缺口" }).click();
    await expect(page.getByTestId("panel-capability")).toContainText("没有 framebuffer 采集");
    await expect(page.getByTestId("read-route-table")).toContainText("/api/v1/dashboard/snapshot");
    await expect(page.locator("video, canvas, img")).toHaveCount(0);
  });

  test("数据源与缺口页：未实现的心智面按缺口列，保留边界按「暂不开放」列", async ({ page }) => {
    await page.goto(`${url("mock", "healthy_run_07")}#data`);
    const panel = page.getByTestId("panel-capability");
    await expect(panel).toContainText("未接入");
    await expect(panel).toContainText("人格摘要 / 关系 / 模型调用花费与配置状态");
    await expect(panel).toContainText("自主目标 / 技能步读数 / 失败归因 / 决策来源 / 脱敏行为参数");
    // 通用写面是有意不开放，不能和「读不到」混成一种呈现。
    await expect(panel).toContainText("暂不开放");
  });

  test("时间线与告警标签：只呈现条目，不含确认或消除控件", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await page.getByRole("button", { name: "时间线" }).click();
    await expect(page.getByTestId("panel-timeline")).toContainText("观察");
    await page.getByRole("button", { name: "告警" }).click();
    await expect(page.getByTestId("panel-alerts")).toBeVisible();
    for (const word of ["确认", "消除", "忽略"]) {
      await expect(page.getByRole("button", { name: new RegExp(word) })).toHaveCount(0);
    }
    // 「没有告警」（有源为空）与「无告警源」（信封缺口）是两个不同呈现（§5.3）。
    await page.getByLabel("模拟场景").selectOption("stale_observations");
    await expect(page.getByTestId("alerts-empty")).toContainText("没有告警");
    await expect(page.getByTestId("alerts-no-source")).toHaveCount(0);
    await page.getByLabel("模拟场景").selectOption("fields_unknown");
    await expect(page.getByTestId("alerts-no-source")).toContainText("无告警源");
    await expect(page.getByTestId("alerts-empty")).toHaveCount(0);
    // 切换场景不能把操作者送回总览：页面由片段决定，片段要跟着留住。
    await expect(page).toHaveURL(/#alerts/);
  });

  test("只读边界：无表单、无文本/密码输入，按钮文案不含写操作动词", async ({ page }) => {
    // 身份页是已授权的例外，单独由 live-identity-rename 覆盖；这里只查纯只读页。
    for (const scenario of ["healthy_run_07", "bridge_disconnected", "permission_restricted", "read_failed"]) {
      await openMock(page, scenario);
      for (const entry of ["总览", "时间线", "告警", "数据源与缺口"]) {
        await page.getByRole("button", { name: entry }).click();
        await expect(page.locator("form")).toHaveCount(0);
        await expect(page.locator('input[type="text"], input[type="password"], textarea')).toHaveCount(0);
        const labels = await page.getByRole("button").allInnerTexts();
        for (const label of labels) {
          const hit = ACTION_WORDS.find((word) => label.includes(word));
          expect(hit, `${scenario}/${entry} 按钮 "${label}" 含写操作动词`).toBeUndefined();
        }
      }
      const body = (await page.locator("body").innerText()).toLowerCase();
      for (const secret of ["refresh_token", "client_secret", "bearer", "api_key", "password"]) {
        expect(body).not.toContain(secret);
      }
    }
  });

  test("直接打开片段地址会选中对应页面", async ({ page }) => {
    await page.goto(url("mock", "healthy_run_07") + "#alerts");
    await expect(page.getByTestId("page-alerts")).toBeVisible();
    await expect(page.getByTestId("data-source-banner")).toContainText("模拟数据 MOCK");
  });

  test("切换模拟场景会改变同一界面的呈现并同步 URL", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await expect(page.getByTestId("panel-kin")).toContainText("运行中");
    await page.getByLabel("模拟场景").selectOption("bridge_disconnected");
    await expect(page).toHaveURL(/scenario=bridge_disconnected/);
    await expect(page.getByTestId("panel-kin")).toContainText("已失联");
  });
});
