import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import type { MockScenarioId } from "../fixtures/mockFixtures";

/**
 * The session-control panel driven through the same shell the operator uses. These readings prove the
 * card's acceptance on the shipped UI: the observed session is shown, the stop is gated behind a
 * non-idle session plus an explicit confirmation, the withheld start/pause/resume verbs are named
 * rather than rendered as buttons, a clean stop and a blocked stop read apart, a server refusal stays
 * named — and the per-process CSRF token never reaches the rendered page.
 */

function mockSession(scenario: MockScenarioId): DashboardConfig {
  return { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
}

function openSession(scenario: MockScenarioId): void {
  render(<App config={mockSession(scenario)} initialPage="session" />);
}

describe("会话面板：显示观察到的会话", () => {
  it("运行场景显示 运行中 / 可执行 stop / 三个暂不开放动词，且不泄漏 CSRF 令牌", async () => {
    openSession("healthy_run_07");
    expect(await screen.findByTestId("panel-session-control")).toBeInTheDocument();
    await screen.findByTestId("session-state");
    expect(screen.getByTestId("session-state")).toHaveTextContent("运行中");
    expect(screen.getByTestId("session-available")).toHaveTextContent("stop");
    const unavailable = screen.getByTestId("session-unavailable");
    expect(unavailable).toHaveTextContent("启动");
    expect(unavailable).toHaveTextContent("暂停");
    expect(unavailable).toHaveTextContent("恢复");
    // The token lives in the decoder and the adapter closure, never the rendered model.
    expect(document.body).not.toHaveTextContent("mock-csrf-token");
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
  });

  it("会话读数失败时面板保持挂载并具名报错，不铺一个可用的假表单", async () => {
    openSession("read_failed");
    const failure = await screen.findByTestId("session-read-failure");
    expect(failure).toHaveTextContent("disconnected");
    expect(screen.queryByTestId("session-stop-submit")).toBeNull();
  });
});

describe("会话面板：停止只在会话非空闲且显式确认时可用", () => {
  it("空闲会话：提交禁用并说明没有可停止的会话，勾选框也不可勾", async () => {
    openSession("fields_unknown");
    await screen.findByTestId("session-state");
    expect(screen.getByTestId("session-state")).toHaveTextContent("空闲");
    expect(screen.getByTestId("session-stop-locked")).toHaveTextContent("没有运行中的会话");
    expect(screen.getByTestId("session-stop-submit")).toBeDisabled();
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("运行会话：确认后才提交，成功后如实报告已停止并列出已终止进程", async () => {
    openSession("healthy_run_07");
    await screen.findByTestId("session-state");
    const submit = screen.getByTestId("session-stop-submit");
    // A non-idle session alone is not a confirmed submission.
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    expect(submit).toBeEnabled();
    await userEvent.click(submit);

    expect(await screen.findByTestId("session-result-stopped")).toBeInTheDocument();
    const buckets = screen.getByTestId("session-report-buckets");
    expect(buckets).toHaveTextContent("已确认 1");
    expect(buckets).toHaveTextContent("4242");
    expect(screen.queryByTestId("session-result-blocked")).toBeNull();
  });

  it("未定会话：停止回报 blocked，未确认释放不折成干净的已停止", async () => {
    openSession("bridge_disconnected");
    await screen.findByTestId("session-state");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByTestId("session-stop-submit"));

    expect(await screen.findByTestId("session-result-blocked")).toBeInTheDocument();
    const buckets = screen.getByTestId("session-report-buckets");
    expect(buckets).toHaveTextContent("未确认 1");
    expect(screen.queryByTestId("session-result-stopped")).toBeNull();
  });

  it("服务器具名拒止原样送到面板，不塌成通用成功", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            schemaVersion: "kin-dashboard-session/1.0.0",
            error: "session_not_running",
            message: "这个 Kin 没有运行中的会话可以停止。",
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        );
      }
      const url = String(input);
      if (url.includes("/dashboard/session")) {
        return new Response(
          JSON.stringify({
            schemaVersion: "kin-dashboard-session/1.0.0",
            state: "running",
            stopAllowed: true,
            availableControls: ["stop"],
            unavailableControls: { start: "由实时进程承载", pause: "无 PAUSED 态", resume: "无 PAUSED 态" },
            csrfToken: "mock-csrf-token",
            observedAt: new Date().toISOString(),
            staleAfterMs: 8_000,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response("{}", { status: 404, headers: { "content-type": "application/json" } });
    }) as typeof fetch;

    try {
      render(
        <App
          config={{ adapter: "gateway", scenario: "healthy_run_07", gatewayBaseUrl: "http://127.0.0.1:8000", latencyMs: 0 }}
          initialPage="session"
        />,
      );
      await screen.findByTestId("session-state");
      await userEvent.click(screen.getByRole("checkbox"));
      await userEvent.click(screen.getByTestId("session-stop-submit"));

      const refusal = await screen.findByTestId("session-refusal");
      expect(refusal).toHaveTextContent("write_refused");
      expect(refusal).toHaveTextContent("session_not_running");
      // A refused stop reports no success.
      expect(screen.queryByTestId("session-result-stopped")).toBeNull();
      expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
    } finally {
      globalThis.fetch = original;
    }
  });
});
