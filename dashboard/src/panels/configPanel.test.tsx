import { act, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ok } from "../domain/adapter";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import { buildMockConfig, type MockScenarioId } from "../fixtures/mockFixtures";
import { CONFIG_SCHEMA_VERSION } from "../domain/model";
import { createMockAdapter } from "../adapters/mockAdapter";
import { ConfigPanel } from "./ConfigPanel";

/**
 * The config panel driven through the same shell the operator uses. These readings prove the
 * card's acceptance on the shipped UI: the saved document is shown in a real form, the provider
 * field is a vocabulary select rather than free text, an illegal value is caught before the write
 * reaches the network, an accepted save is reported beside the document it now holds, a refusal
 * renders named instead of folding into a generic error — and the per-process CSRF token never
 * reaches the rendered page.
 */

function mockConfig(scenario: MockScenarioId): DashboardConfig {
  return { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
}

function openConfig(scenario: MockScenarioId): void {
  render(<App config={mockConfig(scenario)} initialPage="config" />);
}

describe("模型连接测试", () => {
  it("在途编辑再放弃不会复活旧成功或开放第二次调用", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    let finish!: () => void;
    const test = vi.spyOn(adapter, "testModel").mockImplementation(() => new Promise((resolve) => {
      finish = () => resolve(ok({ status: "connected", reason: "", elapsedMs: 42,
        timeoutMs: 20_000, modelCalls: 1, estimatedCostMicro: 3 }, "gateway", "gateway://model-test"));
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ConfigPanel adapter={adapter} nowMs={Date.now()} /></QueryClientProvider>);
    const button = await screen.findByTestId("model-test-submit");
    await userEvent.click(button);
    await userEvent.type(screen.getByTestId("config-input-model_name"), "-changed");
    await userEvent.click(screen.getByRole("button", { name: "放弃修改，读取已存配置" }));
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(test).toHaveBeenCalledTimes(1);
    await act(async () => finish());
    await waitFor(() => expect(button).toBeEnabled());
    expect(screen.queryByTestId("model-test-result")).toBeNull();
    expect(screen.getByText(/旧结果不适用于当前设置/)).toBeInTheDocument();
    client.clear();
  });

  it("外部配置更新使在途测试结果失效，新测试才对应新配置", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const response = ok({ status: "connected" as const, reason: "", elapsedMs: 42,
      timeoutMs: 20_000, modelCalls: 1, estimatedCostMicro: 3 }, "gateway", "gateway://model-test");
    let finish!: () => void;
    const test = vi.spyOn(adapter, "testModel").mockImplementationOnce(() => new Promise((resolve) => {
      finish = () => resolve(response);
    })).mockResolvedValue(response);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ConfigPanel adapter={adapter} nowMs={Date.now()} /></QueryClientProvider>);
    const button = await screen.findByTestId("model-test-submit");
    await userEvent.click(button);
    const saved = await adapter.config(new AbortController().signal);
    if (!saved.ok) throw new Error("fixture config unavailable");
    act(() => client.setQueryData(["config", adapter.describe().id], {
      ...saved, value: { ...saved.value, fields: { ...saved.value.fields, model_name: "new-model" } },
    }));
    await waitFor(() => expect(screen.getByTestId("config-input-model_name")).toHaveValue("new-model"));
    act(() => client.setQueryData(["config", adapter.describe().id], saved));
    await waitFor(() => expect(screen.getByTestId("config-input-model_name")).toHaveValue("deepseek-chat"));
    expect(button).toBeDisabled();
    await act(async () => finish());
    await waitFor(() => expect(button).toBeEnabled());
    expect(screen.queryByTestId("model-test-result")).toBeNull();
    await userEvent.click(button);
    expect(await screen.findByTestId("model-test-result")).toHaveTextContent("模型连接与决策格式通过");
    expect(test).toHaveBeenCalledTimes(2);
    client.clear();
  });

  it("不会把模拟数据报成真实连接成功", async () => {
    openConfig("healthy_run_07");
    await userEvent.click(await screen.findByTestId("model-test-submit"));
    expect(await screen.findByTestId("model-test-result")).toHaveTextContent("模拟数据不能验证真实模型连接");
  });

  it("只显式调用一次；显示结果和估算，编辑草稿后清除旧结果并禁用测试", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const test = vi.spyOn(adapter, "testModel").mockResolvedValue(ok({
      status: "connected", reason: "", elapsedMs: 42, timeoutMs: 20_000,
      modelCalls: 1, estimatedCostMicro: 3,
    }, "gateway", "gateway://model-test"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ConfigPanel adapter={adapter} nowMs={Date.now()} /></QueryClientProvider>);
    const button = await screen.findByTestId("model-test-submit");
    expect(test).not.toHaveBeenCalled();
    await userEvent.click(button);
    expect(await screen.findByTestId("model-test-result")).toHaveTextContent("模型连接与决策格式通过");
    expect(screen.getByTestId("model-test-result")).toHaveTextContent("42 ms");
    expect(screen.getByTestId("model-test-result")).toHaveTextContent("非账单");
    expect(test).toHaveBeenCalledTimes(1);
    await userEvent.type(screen.getByTestId("config-input-model_name"), "-changed");
    expect(button).toBeDisabled();
    expect(screen.queryByTestId("model-test-result")).toBeNull();
  });
});

describe("配置面板：显示已保存的文档", () => {
  it("预填场景把文档灌进表单，provider 是词表下拉，且页面不含 CSRF 令牌", async () => {
    openConfig("healthy_run_07");
    expect(await screen.findByTestId("panel-config")).toBeInTheDocument();
    const name = await screen.findByTestId("config-input-model_name");
    expect(name).toHaveValue("deepseek-chat");
    expect(screen.getByTestId("config-input-goal_product_id")).toHaveValue("minecraft:wooden_pickaxe");

    // The provider renders as a select fed by the read's vocabulary, not a text box to typo into.
    const provider = screen.getByTestId("config-input-model_provider");
    expect(provider.tagName).toBe("SELECT");
    expect(screen.getByRole("option", { name: "off" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "openai_compatible" })).toBeInTheDocument();

    // The token lives in the decoder and the adapter closure, never the rendered model.
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
    expect(document.body).not.toHaveTextContent("mock-csrf-token");
  });

  it("配置读数失败时面板保持挂载并具名报错，不铺一个可用的假表单", async () => {
    openConfig("read_failed");
    const failure = await screen.findByTestId("config-read-failure");
    expect(failure).toHaveTextContent("disconnected");
    expect(screen.queryByTestId("config-submit")).toBeNull();
  });

  it("空文档场景渲染可编辑的空白表单：全空即合法，保存写出一份干净文档", async () => {
    openConfig("fields_unknown");
    const submit = await screen.findByTestId("config-submit");
    expect(submit).toBeEnabled();

    await userEvent.type(screen.getByTestId("config-input-goal_direction"), "先砍树再做镐");
    await userEvent.click(submit);
    expect(await screen.findByTestId("config-result")).toHaveTextContent("已保存：写入 1 个字段");
    await waitFor(() => expect(screen.queryByTestId("config-unsaved")).not.toBeInTheDocument());
  });
});

describe("配置面板：本机先校验，服务器仍是最终裁判", () => {
  it("估算费率允许显式零，拒绝负数并说明不是供应商账单", async () => {
    openConfig("fields_unknown");
    const rate = await screen.findByTestId("config-input-model_request_rate");
    await userEvent.type(rate, "-1");
    expect(screen.getByTestId("config-error-model_request_rate")).toHaveTextContent("≥ 0");
    expect(screen.getByTestId("config-submit")).toBeDisabled();
    await userEvent.clear(rate);
    await userEvent.type(rate, "0");
    expect(screen.getByTestId("config-submit")).toBeEnabled();
    expect(rate).toHaveAccessibleDescription(/不是供应商账单/);
    await userEvent.click(screen.getByTestId("config-submit"));
    expect(await screen.findByTestId("config-result")).toHaveTextContent("写入 1 个字段");
  });

  it("非法物品 id 在提交前就被挡住：具名报错且保存按钮禁用", async () => {
    openConfig("fields_unknown");
    const goal = await screen.findByTestId("config-input-goal_product_id");
    await userEvent.type(goal, "Not A Valid Id");
    expect(await screen.findByTestId("config-error-goal_product_id")).toBeInTheDocument();
    expect(screen.getByTestId("config-submit")).toBeDisabled();
  });

  it("把密钥形状填进环境变量名字段：本机校验拒止，不进入提交", async () => {
    openConfig("fields_unknown");
    const env = await screen.findByTestId("config-input-model_api_key_env");
    await userEvent.type(env, "sk-" + "a".repeat(40));
    expect(await screen.findByTestId("config-error-model_api_key_env")).toBeInTheDocument();
    expect(screen.getByTestId("config-submit")).toBeDisabled();
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
  });

  it("服务器具名拒止原样送到面板，且当前文档保持不变", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            schemaVersion: CONFIG_SCHEMA_VERSION,
            error: "invalid_config",
            message: "goal_quantity: 不能超过 64。",
          }),
          { status: 400, headers: { "content-type": "application/json" } },
        );
      }
      const url = String(input);
      if (url.includes("/config")) {
        return new Response(JSON.stringify(buildMockConfig("healthy_run_07", Date.now())), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("{}", { status: 404, headers: { "content-type": "application/json" } });
    }) as typeof fetch;

    try {
      render(
        <App
          config={{ adapter: "gateway", scenario: "healthy_run_07", gatewayBaseUrl: "http://127.0.0.1:8000", latencyMs: 0 }}
          initialPage="config"
        />,
      );
      await screen.findByTestId("config-input-model_name");
      const qty = screen.getByTestId("config-input-goal_quantity");
      await userEvent.clear(qty);
      await userEvent.type(qty, "999999999999");

      // A value this far over the ceiling is caught locally first; drop it to a server-plausible
      // but still-refused quantity so the POST path is what answers.
      await userEvent.clear(qty);
      await userEvent.type(qty, "5");
      await userEvent.click(screen.getByTestId("config-submit"));

      const refusal = await screen.findByTestId("config-refusal");
      expect(refusal).toHaveTextContent("write_refused");
      expect(refusal).toHaveTextContent("invalid_config");
      // A refused save changes nothing: the form still reports the document it read.
      expect(screen.getByTestId("config-input-model_name")).toHaveValue("deepseek-chat");
      expect(screen.queryByTestId("config-result")).toBeNull();
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("配置草稿保护", () => {
  it("clears the dirty state after an accepted save even if the document is unchanged", async () => {
    openConfig("healthy_run_07");
    const user = userEvent.setup();
    const name = await screen.findByTestId("config-input-model_name");
    await user.clear(name);
    await user.type(name, "deepseek-chat");
    await user.click(screen.getByTestId("config-submit"));
    await screen.findByTestId("config-result");
    await waitFor(() => expect(screen.queryByTestId("config-unsaved")).not.toBeInTheDocument());
  });

  it("can explicitly discard changes and clears the unsaved warning", async () => {
    openConfig("healthy_run_07");
    const user = userEvent.setup();
    const name = await screen.findByTestId("config-input-model_name");
    await user.clear(name);
    await user.type(name, "local-model");
    expect(screen.getByTestId("config-unsaved")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "放弃修改，读取已存配置" }));
    expect(name).toHaveValue("deepseek-chat");
    expect(screen.queryByTestId("config-unsaved")).not.toBeInTheDocument();
  });

  it("keeps a dirty draft on a changed poll and blocks overwriting that external change", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const saved = await adapter.config(new AbortController().signal);
    if (!saved.ok) throw new Error("fixture config unavailable");
    render(<QueryClientProvider client={client}><ConfigPanel adapter={adapter} nowMs={Date.now()} /></QueryClientProvider>);
    const user = userEvent.setup();
    const name = await screen.findByTestId("config-input-model_name");
    await user.clear(name);
    await user.type(name, "my-draft");
    act(() => {
      client.setQueryData(["config", adapter.describe().id], {
        ...saved, value: { ...saved.value, fields: { ...saved.value.fields, model_name: "external-model" } },
      });
    });
    await waitFor(() => expect(screen.getByTestId("config-unsaved")).toHaveTextContent("在别处发生变化"));
    expect(name).toHaveValue("my-draft");
    expect(screen.getByTestId("config-submit")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "放弃修改，读取已存配置" }));
    expect(name).toHaveValue("external-model");
    expect(screen.getByTestId("config-submit")).toBeEnabled();
    client.clear();
  });

  it("links invalid fields to their visible explanation", async () => {
    openConfig("fields_unknown");
    const goal = await screen.findByTestId("config-input-goal_product_id");
    await userEvent.type(goal, "Bad Id");
    expect(goal).toHaveAttribute("aria-invalid", "true");
    expect(goal).toHaveAccessibleDescription("必须是游戏里写法的物品 id（namespace:path，小写）。");
  });
});
