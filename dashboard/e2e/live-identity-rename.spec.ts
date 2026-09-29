import { expect, test } from "@playwright/test";

/**
 * Live identity-rename acceptance against a real Gateway and a real Kin store.
 *
 * This is the card's "真实界面验收": a genuine Chromium drives the actual identity panel,
 * the panel's POST travels the `/gateway` proxy to a running `gateway.server`, and the
 * rename is committed by Core's own compare-and-swap into a real SQLite identity root —
 * nothing here is a stubbed `fetch`. It is opt-in because it needs all three processes:
 * an IDLE Kin root, a Gateway pointed at it, and the built panel. Without
 * `E2E_LIVE_IDENTITY=1` the case skips rather than pretend to have renamed.
 *
 * The target name is fixed (`renamed_kin`) because the harness re-seeds a fresh `minekin`
 * Kin before every run, so a rename is always a real change (never "unchanged") and the
 * revision bump is exactly +1.
 */

const IDENTITY_ENDPOINT = "/gateway/api/v1/dashboard/identity";
const TARGET_NAME = "renamed_kin";

interface IdentityWire {
  readonly username: string;
  readonly uuidCanonical: string;
  readonly identityRevision: number;
  readonly state: string;
  readonly renameAllowed: boolean;
}

test.describe("真实 Gateway 下的身份改名", () => {
  test("停止态 Kin 在面板完成一次显式确认改名，并落到 Core 存储", async ({ page, request }) => {
    test.skip(
      process.env.E2E_LIVE_IDENTITY !== "1",
      "需要真实 Gateway + 停止态 Kin：以 MINEKIN_GATEWAY_TARGET 指向本地 gateway.server，再以 E2E_LIVE_IDENTITY=1 运行本用例。",
    );

    const before = (await (await request.get(IDENTITY_ENDPOINT)).json()) as IdentityWire;
    expect(before.username, "验收从新身份默认 minekin 起步").toBe("minekin");
    expect(before.state, "验收需要一个停止态（idle）的 Kin").toBe("idle");
    expect(before.renameAllowed).toBe(true);

    await page.goto("/?adapter=gateway&gateway=/gateway");
    await expect(page.getByTestId("data-source-banner")).toContainText("真实读数");

    await page.getByRole("button", { name: "身份 · 改名" }).click();
    const panel = page.getByTestId("panel-identity");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("identity-username")).toHaveText("minekin");
    await expect(page.getByTestId("identity-state")).toHaveText("空闲");
    // 提示必须落在同一块面板上：UUID 会变、角色数据不自动迁移。
    await expect(page.getByTestId("identity-notice")).toContainText("UUID");
    await expect(page.locator("body")).toContainText("不会自动迁移");

    await page.locator("#identity-new-name").fill(TARGET_NAME);
    await page.getByRole("checkbox").check();
    await expect(page.getByTestId("identity-submit")).toBeEnabled();
    await page.getByTestId("identity-submit").click();

    await expect(page.getByTestId("identity-result")).toContainText(`已改名为 ${TARGET_NAME}`);
    await expect(page.getByTestId("identity-result")).toContainText("离线 UUID 已改变");

    // 面板轮询刷新后的读数：用户名与 revision 都前进了。
    await expect(page.getByTestId("identity-username")).toHaveText(TARGET_NAME);
    await expect(page.getByTestId("identity-revision")).toHaveText(String(before.identityRevision + 1));

    // 第二读者：直接再向 Gateway 要一次，确认真正写进了 Core 的身份存储而非前端状态。
    const after = (await (await request.get(IDENTITY_ENDPOINT)).json()) as IdentityWire;
    expect(after.username).toBe(TARGET_NAME);
    expect(after.identityRevision).toBe(before.identityRevision + 1);
    expect(after.uuidCanonical).not.toBe(before.uuidCanonical);
  });
});
