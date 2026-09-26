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
    await expect(page.getByTestId("panel-session")).toContainText("B 独立");
    await expect(page.getByTestId("panel-evidence")).toContainText("mock://");
    await expect(page.getByTestId("schema-version")).toContainText("proposal");
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

  test("Live View 标签：没有帧源时只有声明与前置条件，没有画面元素", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await page.getByRole("button", { name: "Live View" }).click();
    await expect(page.getByTestId("panel-liveview")).toContainText("未接入");
    await expect(page.getByTestId("liveview-statement")).toContainText("没有真实帧源");
    await expect(page.locator("video, canvas, img")).toHaveCount(0);
  });

  test("Mind / 成本标签：整页按未接入呈现", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await page.getByRole("button", { name: "Mind / 成本" }).click();
    await expect(page.getByTestId("panel-mind")).toContainText("未接入");
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
  });

  test("只读边界：无表单、无文本/密码输入，按钮文案不含写操作动词", async ({ page }) => {
    for (const scenario of ["healthy_run_07", "bridge_disconnected", "permission_restricted", "read_failed"]) {
      await openMock(page, scenario);
      for (const tab of ["总览", "时间线", "告警", "Live View", "Mind / 成本"]) {
        await page.getByRole("button", { name: tab, exact: true }).click();
        await expect(page.locator("form")).toHaveCount(0);
        await expect(page.locator('input[type="text"], input[type="password"], textarea')).toHaveCount(0);
        const labels = await page.getByRole("button").allInnerTexts();
        for (const label of labels) {
          const hit = ACTION_WORDS.find((word) => label.includes(word));
          expect(hit, `${scenario}/${tab} 按钮 "${label}" 含写操作动词`).toBeUndefined();
        }
      }
      const body = (await page.locator("body").innerText()).toLowerCase();
      for (const secret of ["refresh_token", "client_secret", "bearer", "api_key", "password"]) {
        expect(body).not.toContain(secret);
      }
    }
  });

  test("切换模拟场景会改变同一界面的呈现并同步 URL", async ({ page }) => {
    await openMock(page, "healthy_run_07");
    await expect(page.getByTestId("panel-kin")).toContainText("运行中");
    await page.getByLabel("模拟场景").selectOption("bridge_disconnected");
    await expect(page).toHaveURL(/scenario=bridge_disconnected/);
    await expect(page.getByTestId("panel-kin")).toContainText("已失联");
  });
});
