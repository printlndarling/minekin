import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { DashboardConfig } from "./adapters/config";
import { READ_ENDPOINTS } from "./adapters/gatewayAdapter";
import { POLL_INTERVAL_MS } from "./hooks/useKinReads";
import {
  REAL_ALERTS_ENVELOPE_WIRE,
  REAL_AFTER_SESSION_SNAPSHOT_WIRE,
  REAL_IN_SESSION_SNAPSHOT_WIRE,
  REAL_IN_SESSION_TIMELINE_WIRE,
  REAL_JOINED_RUN_SNAPSHOT_WIRE,
  REAL_TIMELINE_WIRE,
  gatewayLedgerWires,
  type LedgerRowSpec,
} from "./test/realGatewayWire";

/**
 * The gateway transport end to end: real wire bytes come off a stubbed fetch, the
 * frozen decoders parse them, and the panels render what the ledger actually says.
 * `App.test.tsx` covers the mock shell; these readings would be vacuous if the new
 * session-progress derivation were only ever exercised against mock fixtures, whose
 * timeline titles are Chinese display strings and whose `sourceRef` carries no
 * ledger position.
 */

const BASE_URL = "http://127.0.0.1:8712";
const CONFIG: DashboardConfig = { adapter: "gateway", scenario: "healthy_run_07", gatewayBaseUrl: BASE_URL, latencyMs: 0 };

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.useRealTimers();
});

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

function serveTimeline(
  rows: readonly Record<string, unknown>[],
  snapshot: Record<string, unknown> = REAL_JOINED_RUN_SNAPSHOT_WIRE,
): string[] {
  const requested: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    if (url.includes(READ_ENDPOINTS.snapshot)) return jsonResponse(snapshot);
    if (url.includes(READ_ENDPOINTS.timeline)) return jsonResponse(rows);
    if (url.includes(READ_ENDPOINTS.alerts)) return jsonResponse(REAL_ALERTS_ENVELOPE_WIRE);
    return jsonResponse({ detail: "not found" }, 404);
  }) as unknown as typeof fetch;
  return requested;
}

const CLEAN_RUN: readonly LedgerRowSpec[] = [
  { title: "SessionProcessStarted", kind: "session", outcome: "applied", detail: "argv_digest=abc123, phase=launch" },
  { title: "AuthPolicyFrozen", kind: "decision", outcome: "applied" },
  { title: "BridgeHelloAccepted", kind: "session", outcome: "applied" },
  { title: "JoinObserved", kind: "server_feedback", outcome: "applied" },
  { title: "PlayableEstablished", kind: "session", outcome: "applied" },
  { title: "InputLeaseGranted", kind: "input", outcome: "applied" },
  { title: "InputRefused", kind: "input", outcome: "rejected", detail: "reason=lease_not_granted" },
  { title: "InputRefused", kind: "input", outcome: "rejected", detail: "reason=world_not_playable" },
  { title: "InputRefused", kind: "input", outcome: "rejected", detail: "reason=lease_not_granted" },
  { title: "InputReleased", kind: "input", outcome: "released" },
  { title: "ClientProcessExited", kind: "session", outcome: "unknown", detail: "reason=operator_stop" },
];

const STILL_PLAYING: readonly LedgerRowSpec[] = CLEAN_RUN.slice(0, 8);
const UNPINNED_WINDOW: readonly LedgerRowSpec[] = CLEAN_RUN.slice(3);

/** The shape the live LAN joiner's ledger actually holds: half the hand-backs found no lease. */
const LEASE_SPLIT: readonly LedgerRowSpec[] = [
  { title: "SessionProcessStarted", kind: "session", outcome: "applied", detail: "argv_digest=abc123, phase=launch" },
  { title: "InputReleased", kind: "input", outcome: "released", detail: "reason=TIMEOUT, had_lease=True" },
  { title: "InputReleased", kind: "input", outcome: "released", detail: "reason=EXPLICIT, had_lease=False" },
];

describe("Gateway 真实传输：会话阶段只从台账行读出", () => {
  it("干净入服并停止：七个阶段全部已观测，终态带 Core 的 reason", async () => {
    const requested = serveTimeline(gatewayLedgerWires(CLEAN_RUN));
    render(<App config={CONFIG} />);

    expect(await screen.findByTestId("data-source-banner")).toHaveTextContent("真实读数");
    expect((await screen.findAllByText("kin-01")).length).toBeGreaterThan(0);
    expect(screen.getByTestId("schema-version")).toHaveTextContent("kin-dashboard-readmodel/1.0.0");

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("租约授予 1 次"));
    const panel = screen.getByTestId("panel-session-progress");
    expect(panel).not.toHaveTextContent("窗口内没有");
    expect(within(panel).getAllByText("已观测")).toHaveLength(7);
    expect(within(panel).queryAllByText("未观测")).toHaveLength(0);
    expect(panel).toHaveTextContent("服务端观察到入服");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("最远到：客户端进程已离场");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("释放 1 次");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("拒止 3 次");

    expect(screen.getByTestId("progress-terminal")).toHaveTextContent("会话已停止 · 客户端已离场（正常离场）");
    expect(screen.getByTestId("progress-terminal")).toHaveTextContent("reason=operator_stop");
    expect(screen.queryByTestId("progress-running")).toBeNull();

    // 三条拒止行只有两个 reason：去重后逐条列出，不合并计数。
    const refusals = screen.getByTestId("progress-refusals").querySelectorAll("li");
    expect(refusals).toHaveLength(2);
    expect(refusals[0]).toHaveTextContent("输入被拒：reason=lease_not_granted");
    expect(refusals[1]).toHaveTextContent("输入被拒：reason=world_not_playable");

    expect(requested).toContain(`${BASE_URL}${READ_ENDPOINTS.snapshot}`);
    expect(requested.some((url) => url.includes(`${READ_ENDPOINTS.timeline}?limit=50`))).toBe(true);
  });

  it("释放的分拆逐行来自台账：交还租约与空手归还各报各的次数", async () => {
    serveTimeline(gatewayLedgerWires(LEASE_SPLIT));
    render(<App config={CONFIG} />);

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("释放 2 次"));
    expect(screen.getByTestId("release-breakdown")).toHaveTextContent("其中 1 次交还了租约、1 次手上已无租约");
    expect(screen.queryByTestId("release-unrecorded")).toBeNull();
  });

  it("释放行没写有没有租约时，面板说没记录，不把它塞进任一类", async () => {
    serveTimeline(gatewayLedgerWires(CLEAN_RUN));
    render(<App config={CONFIG} />);

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("释放 1 次"));
    expect(screen.queryByTestId("release-breakdown")).toBeNull();
    expect(screen.getByTestId("release-unrecorded")).toHaveTextContent("1 次的行没写有没有租约");
  });

  it("仍在会话中：释放与离场按未观测呈现，终态行说还没有离场", async () => {
    serveTimeline(gatewayLedgerWires(STILL_PLAYING));
    render(<App config={CONFIG} />);

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("拒止 2 次"));
    expect(screen.getByTestId("progress-running")).toHaveTextContent("本会话尚未离场");
    expect(screen.queryByTestId("progress-terminal")).toBeNull();
    const panel = screen.getByTestId("panel-session-progress");
    expect(within(panel).getAllByText("未观测")).toHaveLength(2);
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("最远到：输入租约已授予");
  });

  it("版本准备进度仍是具名缺口，不画成进度条", async () => {
    serveTimeline(gatewayLedgerWires(CLEAN_RUN));
    render(<App config={CONFIG} />);

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("租约授予 1 次"));
    expect(screen.getByTestId("panel-session-progress")).toHaveTextContent(
      "客户端 bundle 的准备进度（下载文件数、字节、耗时）没有台账行",
    );
  });

  it("窗口截断到启动行之后：不锚定单次会话，改为具名提示", async () => {
    serveTimeline(gatewayLedgerWires(UNPINNED_WINDOW));
    render(<App config={CONFIG} />);

    expect(await screen.findByTestId("progress-unpinned")).toHaveTextContent("无法锚定到单次会话");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("租约授予 1 次");
  });

  it("用真实捕获的两行读数：启动与离场已观测，入服未观测", async () => {
    serveTimeline(REAL_TIMELINE_WIRE);
    render(<App config={CONFIG} />);

    const panel = screen.getByTestId("panel-session-progress");
    expect(await screen.findByTestId("progress-counts")).toBeInTheDocument();
    expect(within(panel).getAllByText("已观测")).toHaveLength(2);
    expect(within(panel).getAllByText("未观测")).toHaveLength(5);
    expect(screen.getByTestId("progress-terminal")).toHaveTextContent("会话已停止 · 客户端已离场（正常离场）");
  });

  it("不可达：断连计数、重试间隔与时间线失败一起说，面板不展示缓存阶段", async () => {
    globalThis.fetch = (async () => {
      throw new Error("Connection refused");
    }) as unknown as typeof fetch;
    render(<App config={CONFIG} />);

    expect(await screen.findByTestId("read-failure")).toHaveTextContent("disconnected");
    expect(screen.getByTestId("poll-state")).toHaveTextContent(
      /^断连 · 连续 1 次读取失败 · 已持续 \d+ 秒 · 尚无成功读数 · 每 5 秒自动重试$/,
    );
    expect(screen.getByTestId("progress-failure")).toHaveTextContent("时间线读取失败（disconnected）");
    expect(screen.queryByTestId("progress-counts")).toBeNull();
    expect(screen.getByTestId("data-source-banner")).toHaveTextContent("真实读数");
  });

  it("断连计数跟着每次失败的轮询走，断开时长从首次失败起算", async () => {
    // The live shape this guards: every failed poll says exactly the same thing, so
    // TanStack's structural sharing hands back the same result reference. Counting by
    // that reference left the banner reading 「连续 1 次」 after half a minute of outage.
    let polls = 0;
    globalThis.fetch = (async () => {
      polls += 1;
      throw new Error("Connection refused");
    }) as unknown as typeof fetch;

    vi.useFakeTimers();
    render(<App config={CONFIG} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByTestId("poll-state")).toHaveTextContent("断连 · 连续 1 次读取失败");
    expect(screen.getByTestId("poll-state")).toHaveTextContent(/已持续 \d+ 秒/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3 * POLL_INTERVAL_MS);
    });
    // Non-vacuity: the wait really spanned several intervals, so the count cannot be 1
    // because only one read ever happened.
    expect(polls).toBeGreaterThanOrEqual(3);
    expect(screen.getByTestId("poll-state")).toHaveTextContent(/连续 ([3-9]|\d{2,}) 次读取失败/);
    // And the span must be measured from the first failure, not re-stamped by the last
    // one: re-stamping would hold it under one poll interval (≤ 5 秒) forever.
    expect(screen.getByTestId("poll-state")).toHaveTextContent(/已持续 ([1-5]\d|60) 秒/);
    expect(screen.getByTestId("data-source-banner")).toHaveTextContent("真实读数");
    expect(screen.getByTestId("data-source-banner")).not.toHaveTextContent("模拟数据");
  });
});

describe("Gateway 活体捕获：会话内与会话后各自渲染自己的读数（§2.97）", () => {
  it("会话进行中：两条链路都报已连接，阶段锚定在本次会话且不报离场", async () => {
    serveTimeline(REAL_IN_SESSION_TIMELINE_WIRE, REAL_IN_SESSION_SNAPSHOT_WIRE);
    render(<App config={CONFIG} />);

    expect(await screen.findByTestId("data-source-banner")).toHaveTextContent("真实读数");
    expect((await screen.findAllByText("kin-lan87b-join")).length).toBeGreaterThan(0);

    const kin = screen.getByTestId("panel-kin");
    await waitFor(() => expect(within(kin).getAllByText("已连接")).toHaveLength(2));
    expect(kin).not.toHaveTextContent("已失联");

    await waitFor(() => expect(screen.getByTestId("progress-counts")).toHaveTextContent("租约授予 2 次"));
    expect(screen.queryByTestId("progress-unpinned")).toBeNull();
    const panel = screen.getByTestId("panel-session-progress");
    expect(within(panel).getAllByText("已观测")).toHaveLength(6);
    expect(within(panel).getAllByText("未观测")).toHaveLength(1);
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("最远到：输入租约已释放");
    expect(screen.getByTestId("progress-running")).toHaveTextContent("本会话尚未离场");
    expect(screen.queryByTestId("progress-terminal")).toBeNull();
  });

  it("会话结束后：同一面板改报两条已失联，链路读数跟着台账行序走", async () => {
    serveTimeline(REAL_IN_SESSION_TIMELINE_WIRE, REAL_AFTER_SESSION_SNAPSHOT_WIRE);
    render(<App config={CONFIG} />);

    const kin = screen.getByTestId("panel-kin");
    await waitFor(() => expect(within(kin).getAllByText("已失联")).toHaveLength(2));
    expect(kin).not.toHaveTextContent("已连接");
    expect((await screen.findAllByText("kin-lan87b-join")).length).toBeGreaterThan(0);
  });

  it("同一份捕获截掉启动行：锚定消失，阶段计数不变 —— 前一条不是恒真", async () => {
    // The newest eight rows are the same bytes minus `SessionProcessStarted` and the rows
    // between it and the window head: everything the panel counts still arrives, only the
    // attempt anchor is gone. Without this reading the eight-row cut would pass silently.
    serveTimeline(REAL_IN_SESSION_TIMELINE_WIRE.slice(0, 8), REAL_IN_SESSION_SNAPSHOT_WIRE);
    render(<App config={CONFIG} />);

    expect(await screen.findByTestId("progress-unpinned")).toHaveTextContent("无法锚定到单次会话");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("租约授予 2 次");
    expect(screen.getByTestId("progress-counts")).toHaveTextContent("最远到：输入租约已释放");
  });
});
