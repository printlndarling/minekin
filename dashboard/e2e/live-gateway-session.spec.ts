import { expect, test } from "@playwright/test";

/**
 * Live read-through against a real Gateway, so the session-progress panel is proven on
 * the shipped transport and Core's own ledger bytes rather than on a stubbed fetch.
 *
 * It is opt-in because it needs a running Gateway (`demo.sh --gateway`) and a Kin whose
 * ledger exists: without `E2E_LIVE_GATEWAY=1` the case skips instead of inventing a run.
 * The expectations are recomputed here from the wire the same proxied endpoint answers, so
 * this is a second reader of the ledger and not a restatement of the derivation.
 */

const LAUNCH_ROW = "SessionProcessStarted";

const STAGE_ROWS: readonly { label: string; eventType: string }[] = [
  { label: "客户端进程已启动", eventType: "SessionProcessStarted" },
  { label: "Bridge 握手被接受", eventType: "BridgeHelloAccepted" },
  { label: "服务端观察到入服", eventType: "JoinObserved" },
  { label: "会话进入可玩", eventType: "PlayableEstablished" },
  { label: "输入租约已授予", eventType: "InputLeaseGranted" },
  { label: "输入租约已释放", eventType: "InputReleased" },
  { label: "客户端进程已离场", eventType: "ClientProcessExited" },
];

const TERMINAL_ROWS: readonly { eventType: string; label: string }[] = [
  { eventType: "SessionProcessFailed", label: "客户端启动失败" },
  { eventType: "SessionInterrupted", label: "会话被中断" },
  { eventType: "ClientProcessExited", label: "客户端已离场" },
];

interface WireRow {
  readonly title: string;
  readonly sourceRef: string;
}

function positionOf(row: WireRow): number {
  const match = /\/(\d+)$/.exec(row.sourceRef);
  return match === null ? Number.NEGATIVE_INFINITY : Number(match[1]);
}

test.describe("真实 Gateway 下的会话进度", () => {
  test("逐行读数来自当前 attempt 的台账，不引入窗口外的阶段", async ({ page, request }) => {
    test.skip(
      process.env.E2E_LIVE_GATEWAY !== "1",
      "需要本地 Gateway：先跑 `bash test-orchestrator/runner/demo.sh --gateway`，再以 E2E_LIVE_GATEWAY=1 运行本用例。",
    );

    const snapshot = (await (await request.get("/gateway/api/v1/dashboard/snapshot")).json()) as {
      kinId: { status: string; value: string };
    };
    expect(snapshot.kinId.status).toBe("known");
    const rows = (await (await request.get("/gateway/api/v1/dashboard/timeline?limit=50")).json()) as WireRow[];
    expect(rows.length, "本地 demo 台账应有行可读").toBeGreaterThan(0);

    const launch = rows
      .filter((row) => row.title === LAUNCH_ROW)
      .sort((a, b) => positionOf(b) - positionOf(a))[0];
    if (launch === undefined) throw new Error("窗口里应有启动行，否则读数无法锚定到单次会话。");
    const attempt = rows.filter((row) => positionOf(row) >= positionOf(launch));
    const observedTypes = new Set(attempt.map((row) => row.title));
    const countOf = (eventType: string) => attempt.filter((row) => row.title === eventType).length;
    const terminal = attempt
      .filter((row) => TERMINAL_ROWS.some((spec) => spec.eventType === row.title))
      .sort((a, b) => positionOf(b) - positionOf(a))[0];

    await page.goto("/?adapter=gateway&gateway=/gateway");
    await expect(page.getByTestId("data-source-banner")).toContainText("真实读数");
    await expect(page.getByTestId("data-source-banner")).toContainText("读数正常");
    // Kin ID 来自快照信号，面板显示的就是 Gateway 自己报出的那一个。
    await expect(page.locator("body")).toContainText(snapshot.kinId.value);
    const panel = page.getByTestId("panel-session-progress");
    await expect(panel).toBeVisible();

    for (const stage of STAGE_ROWS) {
      const line = panel.locator("li").filter({ hasText: stage.label });
      await expect(line, `${stage.label} 应当呈现台账的实际状态`).toHaveCount(1);
      await expect(line).toContainText(observedTypes.has(stage.eventType) ? "已观测" : "未观测");
    }

    await expect(page.getByTestId("progress-counts")).toContainText(`租约授予 ${countOf("InputLeaseGranted")} 次`);
    await expect(page.getByTestId("progress-counts")).toContainText(`释放 ${countOf("InputReleased")} 次`);
    await expect(page.getByTestId("progress-counts")).toContainText(`拒止 ${countOf("InputRefused")} 次`);

    if (terminal === undefined) {
      await expect(page.getByTestId("progress-running")).toBeVisible();
      await expect(page.getByTestId("progress-terminal")).toHaveCount(0);
    } else {
      const label = TERMINAL_ROWS.find((spec) => spec.eventType === terminal.title)?.label;
      await expect(page.getByTestId("progress-terminal")).toContainText(`会话已停止 · ${label}`);
    }

    // 版本准备进度在冻结契约里没有台账行，面板必须点名这一缺口而不是画一条进度条。
    await expect(panel).toContainText("客户端 bundle 的准备进度");
    await expect(panel.locator("progress, [role=progressbar]")).toHaveCount(0);
  });
});
