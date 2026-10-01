import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import { buildMockConfig, type MockScenarioId } from "../fixtures/mockFixtures";
import { CONFIG_SCHEMA_VERSION } from "../domain/model";

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
  });
});

describe("配置面板：本机先校验，服务器仍是最终裁判", () => {
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
