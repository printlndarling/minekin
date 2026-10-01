import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import type { DashboardConfig } from "./adapters/config";
import type { MockScenarioId } from "./fixtures/mockFixtures";
import type { PageId } from "./shell/navigation";

function mockConfig(scenario: MockScenarioId, initialPage?: PageId) {
  const config: DashboardConfig = { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
  return initialPage === undefined ? { config } : { config, initialPage };
}

const ACTION_WORDS = ["启动", "暂停", "停止", "急停", "接管", "发送", "注入", "连接服务器", "执行"];

beforeEach(() => {
  // The page is selected from the address fragment, so a fragment left behind by the
  // previous render would decide which panel the next one opens on.
  window.history.replaceState(null, "", window.location.pathname);
});

describe("关键流程：外壳在同一界面上呈现四种缺失", () => {
  it("正常场景：显示模拟标注 + 新鲜读数 + C 档成员按缺口呈现", async () => {
    render(<App {...mockConfig("healthy_run_07")} />);
    expect(screen.getByTestId("data-source-banner")).toHaveTextContent("模拟数据 MOCK");
    expect((await screen.findAllByText("kin_nova_01")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("运行中").length).toBeGreaterThan(0);
    expect(screen.getByText(/read model/)).toHaveTextContent("kin-dashboard-readmodel/1.0.0");
    // §3 的 C 档字段不再有自填默认值的分支：模式 / resolvedVersion / 序列号都是带理由的缺口。
    expect(screen.getByTestId("panel-session")).toHaveTextContent("未接入");
    expect(screen.getByTestId("panel-session")).toHaveTextContent("Core 尚无会话模式枚举");
    expect(document.body.textContent).not.toContain("B 独立");
    expect(document.body.textContent).not.toContain("1.20.1+fabric");
    expect(screen.getByTestId("panel-kin")).toHaveTextContent("台账 position 是记账顺序");
    // 技能步面板在同一总览页在场：最近一步与步数直接可读，花费/配置是具名缺口而不是数字。
    expect(screen.getByTestId("panel-skill-steps")).toHaveTextContent("先挖到木头，再合成木镐");
    expect(screen.getByTestId("panel-skill-steps")).toHaveTextContent("4 步");
    expect(screen.getByTestId("panel-skill-steps")).toHaveTextContent("model_calls");
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
    expect((await screen.findAllByText("kin_nova_01")).length).toBeGreaterThan(0);
  });

  it("无真源场景：多数面板显示未知而非默认值", async () => {
    render(<App {...mockConfig("fields_unknown")} />);
    expect((await screen.findAllByText("kin_nova_01")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("未知").length).toBeGreaterThan(5);
    expect(document.body.textContent).not.toContain("ses_2026");
  });

  it("无权限场景：敏感读数显示无权限与原因", async () => {
    render(<App {...mockConfig("permission_restricted")} />);
    // 同一条具名原因既在常驻上下文条里，也在它自己的面板里，两处都在场。
    expect((await screen.findAllByText(/需只读脱敏视图/)).length).toBeGreaterThan(1);
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
    expect(banner).toHaveTextContent("零网络调用");
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

  it("告警标签：条目 / 有源为空 / 无告警源是三种不同呈现（§5.3）", async () => {
    const { unmount } = render(<App {...mockConfig("healthy_run_07", "alerts")} />);
    await screen.findByText("客户端 bundle 已按已验证 recipe 就位");
    expect(screen.queryByTestId("alerts-empty")).toBeNull();
    expect(screen.queryByTestId("alerts-no-source")).toBeNull();
    unmount();

    const empty = render(<App {...mockConfig("stale_observations", "alerts")} />);
    await empty.findByTestId("alerts-empty");
    expect(screen.getByTestId("alerts-empty")).toHaveTextContent("没有告警");
    expect(screen.queryByTestId("alerts-no-source")).toBeNull();
    empty.unmount();

    render(<App {...mockConfig("fields_unknown", "alerts")} />);
    await screen.findByTestId("alerts-no-source");
    expect(screen.getByTestId("alerts-no-source")).toHaveTextContent("无告警源");
    expect(screen.getByTestId("alerts-no-source")).toHaveTextContent("Core 无告警源");
    expect(screen.queryByTestId("alerts-empty")).toBeNull();
  });

  it("未接入的能力只以具名原因列出，不渲染任何画面或人格内容", async () => {
    const { container } = render(<App {...mockConfig("healthy_run_07", "data")} />);
    await screen.findByTestId("panel-capability");
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("canvas")).toBeNull();
    expect(screen.getByTestId("panel-capability")).toHaveTextContent("没有 framebuffer 采集");
    expect(screen.getByTestId("panel-capability")).toHaveTextContent("没有真源就不显示人格摘要或花费数字");
    expect(screen.getByTestId("panel-capability")).toHaveTextContent("只在 run document 的 mind 段记录");
    // 脱敏行为参数是本轮点名的 live 面：能力清单要把它列出来，而不是继续当作不解析。
    expect(screen.getByTestId("panel-capability")).toHaveTextContent("脱敏行为参数");
    // 保留边界与缺陷分开命名：通用写面是有意不开放，不是读不到。
    expect(screen.getByTestId("panel-capability")).toHaveTextContent("暂不开放");
    expect(screen.getByTestId("read-route-table")).toHaveTextContent("/api/v1/dashboard/snapshot");
  });

  it("常驻上下文条一次回答四个问题，身份读数与阻断一起在场", async () => {
    render(<App {...mockConfig("healthy_run_07")} />);
    await screen.findByTestId("context-bar");
    expect(screen.getByTestId("context-who")).toHaveTextContent("它是谁");
    expect(screen.getByTestId("context-where")).toHaveTextContent("在哪个世界");
    expect(screen.getByTestId("context-doing")).toHaveTextContent("最远阶段");
    expect(screen.getByTestId("context-why")).toHaveTextContent("为什么没运行");
    // 身份读到的名字在总览页就在场，不需要先点开身份页。
    await waitFor(() => expect(screen.getByTestId("context-who")).toHaveTextContent("minekin"));
  });

  it("读取失败在导航上就说那条读路不读，不必打开页面才知道", async () => {
    const config: DashboardConfig = { adapter: "gateway", scenario: "healthy_run_07", gatewayBaseUrl: null, latencyMs: 0 };
    render(<App config={config} />);
    await waitFor(() => expect(screen.getAllByText("失败 · 未配置").length).toBeGreaterThan(0));
    expect(screen.getByTestId("context-why")).toHaveTextContent("未配置");
  });

  it("地址片段选择页面：#alerts 直接打开告警页", async () => {
    window.location.hash = "#alerts";
    render(<App {...mockConfig("healthy_run_07")} />);
    await screen.findByText("客户端 bundle 已按已验证 recipe 就位");
    expect(screen.getByTestId("page-alerts")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /告警/ })).toHaveAttribute("aria-current", "page");
  });

  it("导航切换写回地址片段，且不丢查询串", async () => {
    const user = userEvent.setup();
    // 片段写回走相对 URL，所以查询串（决定 adapter 的那一半）必须原样留着。
    window.history.replaceState(null, "", "?adapter=mock&scenario=healthy_run_07");
    render(<App config={{ adapter: "mock", scenario: "healthy_run_07", gatewayBaseUrl: null, latencyMs: 0 }} initialPage="overview" />);
    await screen.findByText("运行中");
    await user.click(screen.getByRole("button", { name: /身份 · 改名/ }));
    expect(window.location.hash).toBe("#identity");
    expect(window.location.search).toContain("adapter=mock");
    expect(await screen.findByTestId("panel-identity")).toBeInTheDocument();
  });

  it("只读边界：没有写操作控件，也不泄漏凭据", async () => {
    render(<App {...mockConfig("healthy_run_07")} />);
    expect((await screen.findAllByText("kin_nova_01")).length).toBeGreaterThan(0);
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
