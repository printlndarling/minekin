import { expect, test } from "@playwright/test";

/**
 * Live read-through of the break itself, so the disconnect and recovery states are proven on
 * the shipped transport rather than on a stubbed fetch.
 *
 * The panel's only channel is the poll (the frozen contract pushes nothing), so a broken
 * gateway reaches it as an HTTP 500 from the dev/preview proxy — the byte shape measured when
 * a running `demo-lan.sh --gateway` container is stopped. Both cases are opt-in because they
 * need the preview's proxy target to be dead at page load:
 *
 *   E2E_LIVE_GATEWAY_DOWN=1  pnpm e2e e2e/live-gateway-disconnect.spec.ts
 *
 * and, for the second one, the operator brings the gateway back on that same port while the
 * page is open. The test then only waits, which is what the operator would do:
 *
 *   E2E_LIVE_GATEWAY_DOWN=1 E2E_LIVE_GATEWAY_RECOVER=1 pnpm e2e e2e/live-gateway-disconnect.spec.ts
 *   # then, ~20s later: bash test-orchestrator/runner/demo-lan.sh --gateway
 *
 * A dead target is a refusal to answer, not an empty answer: the panel must name the streak it
 * saw and must not slide into the mock descriptor, which would render readings no Kin produced.
 */

const RETRY_TEXT = "每 5 秒自动重试";
const POLL_TEXT = "每 5 秒轮询";
const RECOVER_TIMEOUT_MS = 180_000;
// The config sets no per-test timeout, so the built-in 30 s would cut the operator-paced
// restart short and report the wait as a product failure.
const RECOVER_TEST_TIMEOUT_MS = RECOVER_TIMEOUT_MS + 60_000;

test.describe("真实 Gateway 断开与恢复时面板说什么", () => {
  test("断连说清连续失败次数与重试间隔，并且不回落到模拟读数", async ({ page }) => {
    test.skip(
      process.env.E2E_LIVE_GATEWAY_DOWN !== "1",
      "需要把 preview 的 /gateway 指向一个此刻无人应答的端口：先停掉 `demo-lan.sh --gateway`，" +
        "再以 E2E_LIVE_GATEWAY_DOWN=1 运行本用例（否则这条入口无法区分断连与从未接通）。",
    );
    // Two poll intervals plus the fetches themselves, so the count below is a measured
    // streak rather than a screenshot of the first failure.
    test.setTimeout(60_000);

    await page.goto("/?adapter=gateway&gateway=/gateway");
    const banner = page.getByTestId("data-source-banner");
    await expect(banner).toContainText("真实读数");
    await expect(banner).toContainText("断连");
    await expect(banner).toContainText(/连续 \d+ 次读取失败/);
    await expect(banner).toContainText(RETRY_TEXT);
    await expect(banner).not.toContainText("模拟数据");
    await expect(banner).not.toContainText("读数正常");

    // 「连续 N 次」is only an honest reading if N advances with the polls that fail. A
    // stuck 1 would mean the panel counts the break once and then stops watching.
    await expect(banner).toContainText(/连续 (?:[2-9]|[1-9]\d) 次读取失败/, { timeout: 30_000 });
  });

  test("Gateway 重新应答后同一个页面自己回到读数正常", async ({ page }) => {
    test.skip(
      process.env.E2E_LIVE_GATEWAY_DOWN !== "1" || process.env.E2E_LIVE_GATEWAY_RECOVER !== "1",
      "恢复读数需要操作者在该页面开着时把 Gateway 起回同一个端口：" +
        "E2E_LIVE_GATEWAY_DOWN=1 E2E_LIVE_GATEWAY_RECOVER=1 pnpm e2e …，随后跑 demo-lan.sh --gateway。",
    );
    test.setTimeout(RECOVER_TEST_TIMEOUT_MS);

    await page.goto("/?adapter=gateway&gateway=/gateway");
    const banner = page.getByTestId("data-source-banner");
    await expect(banner).toContainText("断连");

    await expect(banner).toContainText("读数正常", { timeout: RECOVER_TIMEOUT_MS });
    await expect(banner).toContainText(POLL_TEXT);
    await expect(banner).not.toContainText("断连");
    await expect(banner).not.toContainText("模拟数据");
  });
});
