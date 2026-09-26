import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import type { DashboardConfig } from "./adapters/config";
import type { MockScenarioId } from "./fixtures/mockFixtures";

function mockConfig(scenario: MockScenarioId, initialTab?: "overview" | "timeline" | "alerts" | "live" | "mind") {
  const config: DashboardConfig = { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
  return initialTab === undefined ? { config } : { config, initialTab };
}

const ACTION_WORDS = ["启动", "暂停", "停止", "急停", "接管", "发送", "注入", "连接服务器", "执行"];

describe("关键流程：只读外壳在同一界面上呈现四种缺失", () => {
  it("正常场景：显示模拟标注 + 新鲜读数", async () => {
    render(<App {...mockConfig("healthy_run_07")} />);
    expect(screen.getByTestId("data-source-banner")).toHaveTextContent("模拟数据 MOCK");
    await screen.findByText("kin_nova_01");
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText(/read model/)).toHaveTextContent("kin-dashboard-readmodel/0.1.0-proposal");
  });

  it("失联场景：runtime 判为未定，链路显示已失联", async () => {
    render(<App {...mockConfig("bridge_disconnected")} />);
    await screen.findByText(/世界状态已标记陈旧/);
    expect(screen.getByText("未定（无法判定）")).toBeInTheDocument();
    expect(screen.getAllByText("已失联").length).toBeGreaterThan(1);
    expect(screen.getAllByText("不可用").length).toBeGreaterThan(0);
  });

  it("陈旧场景：保留最后读数并标注陈旧", async () => {
    render(<App {...mockConfig("stale_observations")} />);
    await waitFor(() => expect(screen.getAllByText("陈旧").length).toBeGreaterThan(2));
    expect(screen.getByText("kin_nova_01")).toBeInTheDocument();
  });

  it("无真源场景：多数面板显示未知而非默认值", async () => {
    render(<App {...mockConfig("fields_unknown")} />);
    await screen.findByText("kin_nova_01");
    expect(screen.getAllByText("未知").length).toBeGreaterThan(5);
    expect(document.body.textContent).not.toContain("ses_2026");
  });

  it("无权限场景：敏感读数显示无权限与原因", async () => {
    render(<App {...mockConfig("permission_restricted")} />);
    await screen.findByText(/需只读脱敏视图/);
    expect(screen.getAllByText("无权限").length).toBeGreaterThan(2);
  });

  it("读取失败：面板仍挂载并整体标为未知", async () => {
    render(<App {...mockConfig("read_failed")} />);
    await screen.findByTestId("read-failure");
    expect(screen.getByTestId("panel-kin")).toBeInTheDocument();
    expect(screen.getAllByText("未知").length).toBeGreaterThan(6);
    expect(document.body.textContent).not.toContain("kin_nova_01");
  });

  it("Gateway 适配器未配置：不发起伪读数，直接显示未配置", async () => {
    const config: DashboardConfig = { adapter: "gateway", scenario: "healthy_run_07", gatewayBaseUrl: null, latencyMs: 0 };
    render(<App config={config} />);
    expect(screen.getByTestId("data-source-banner")).toHaveTextContent("真实读数");
    const banner = await screen.findByTestId("read-failure");
    expect(banner).toHaveTextContent("未配置");
    expect(banner).toHaveTextContent("无 G lane 契约");
    expect(screen.getByTestId("panel-session")).toBeInTheDocument();
    expect(screen.getAllByText("未知").length).toBeGreaterThan(6);
  });

  it("同一界面内切换模拟场景即改变状态呈现", async () => {
    const user = userEvent.setup();
    render(<App {...mockConfig("healthy_run_07")} />);
    await screen.findByText("运行中");
    await user.selectOptions(screen.getByLabelText(/模拟场景/), "bridge_disconnected");
    await waitFor(() => expect(screen.getByText("未定（无法判定）")).toBeInTheDocument());
    expect(window.location.search).toContain("scenario=bridge_disconnected");
  });

  it("时间线与告警按只读方式列出事件", async () => {
    const user = userEvent.setup();
    render(<App {...mockConfig("healthy_run_07", "timeline")} />);
    await screen.findByText("Bridge 心跳续期");
    expect(screen.getByTestId("panel-timeline")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "输入" }));
    await waitFor(() => expect(screen.queryByText("Bridge 心跳续期")).toBeNull());
    expect(screen.getByText("输入 W 按下")).toBeInTheDocument();
  });

  it("Live View 标签不渲染任何画面元素，并说明缺什么", async () => {
    const { container } = render(<App {...mockConfig("healthy_run_07", "live")} />);
    await screen.findByTestId("liveview-statement");
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("canvas")).toBeNull();
    expect(screen.getByTestId("liveview-statement")).toHaveTextContent("没有真实帧源");
    expect(await screen.findByText(/帧缓冲采集/)).toBeInTheDocument();
  });

  it("Mind / 成本页面只声明未接入", async () => {
    render(<App {...mockConfig("healthy_run_07", "mind")} />);
    await screen.findByTestId("panel-mind");
    expect(screen.getByText(/Persona Manifest/)).toBeInTheDocument();
    expect(screen.getByTestId("panel-mind")).toHaveTextContent("未接入");
  });

  it("只读边界：没有写操作控件，也不泄漏凭据", async () => {
    render(<App {...mockConfig("healthy_run_07")} />);
    await screen.findByText("kin_nova_01");
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) {
      const text = button.textContent ?? "";
      for (const word of ACTION_WORDS) {
        expect(text, `${text} 含 ${word}`).not.toContain(word);
      }
    }
    expect(document.querySelectorAll("form")).toHaveLength(0);
    expect(document.querySelectorAll("input[type=password], input[type=text], textarea")).toHaveLength(0);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/refresh_token|client_secret|Bearer\s|api[_-]?key|password/i);
    expect(body).toContain(READ_ONLY_TEXT);
  });
});

const READ_ONLY_TEXT = "只读面板";
