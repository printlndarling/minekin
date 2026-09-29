import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import { buildMockIdentity, type MockScenarioId } from "../fixtures/mockFixtures";

/**
 * The identity panel driven through the same shell the operator uses. These readings prove
 * the card's acceptance on the shipped UI: the stored identity is shown, the rename is gated
 * behind a stopped session plus an explicit confirmation, the UUID consequence is spelled out,
 * and the per-process CSRF token never reaches the rendered page.
 */

function mockIdentityConfig(scenario: MockScenarioId): DashboardConfig {
  return { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
}

function openIdentity(scenario: MockScenarioId): void {
  render(<App config={mockIdentityConfig(scenario)} initialTab="identity" />);
}

describe("身份面板：显示已持久化的身份", () => {
  it("停止场景显示用户名 / 离线 UUID / revision，并逐字给出改名警告，且不泄漏 CSRF 令牌", async () => {
    openIdentity("fields_unknown");
    expect(await screen.findByTestId("identity-username")).toHaveTextContent("minekin");
    expect(screen.getByTestId("identity-revision")).toHaveTextContent("1");
    expect(screen.getByTestId("identity-state")).toHaveTextContent("空闲");
    const uuid = (await screen.findByTestId("identity-uuid")).textContent ?? "";
    expect(uuid).toMatch(/[0-9a-f]{8}-/);
    expect(screen.getByTestId("identity-notice")).toHaveTextContent("离线 UUID");
    expect(screen.getByTestId("identity-notice")).toHaveTextContent("不迁移");

    // The token lives in the decoder and the adapter closure, never the rendered model.
    expect(document.body).not.toHaveTextContent("mock-csrf-token");
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
  });

  it("身份读数失败时面板保持挂载并具名报错，不铺一个可用的假表单", async () => {
    openIdentity("read_failed");
    const failure = await screen.findByTestId("identity-read-failure");
    expect(failure).toHaveTextContent("disconnected");
    expect(screen.queryByTestId("identity-submit")).toBeNull();
  });
});

describe("身份面板：改名只在会话停止且显式确认时可用", () => {
  it("会话运行中：提交禁用并说明原因，输入框也不可写", async () => {
    openIdentity("healthy_run_07");
    await screen.findByTestId("identity-username");
    expect(screen.getByTestId("identity-state")).toHaveTextContent("运行中");
    expect(screen.getByTestId("identity-locked")).toHaveTextContent("只有会话停止时才能改名");
    expect(screen.getByTestId("identity-submit")).toBeDisabled();
    expect(screen.getByLabelText(/新名字/)).toBeDisabled();
  });

  it("合法名 + 确认后才提交，成功后面板改报新身份并推进 revision 与 UUID", async () => {
    openIdentity("fields_unknown");
    await screen.findByTestId("identity-username");

    const input = screen.getByLabelText(/新名字/);
    const submit = screen.getByTestId("identity-submit");
    await userEvent.type(input, "nova_kin");
    // A valid name alone is not a confirmed submission.
    expect(submit).toBeDisabled();

    await userEvent.type(input, "ab!");
    expect(screen.getByTestId("identity-name-hint")).toBeInTheDocument();
    expect(submit).toBeDisabled();

    await userEvent.clear(input);
    await userEvent.type(input, "nova_kin");
    await userEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(submit).toBeEnabled());
    await userEvent.click(submit);

    const result = await screen.findByTestId("identity-result");
    expect(result).toHaveTextContent("已改名为 nova_kin");
    expect(result).toHaveTextContent("revision 2");
    expect(result).toHaveTextContent("离线 UUID 已改变");
    // The refetch (not the typed value) drives what the identity block now reports.
    await waitFor(() => expect(screen.getByTestId("identity-username")).toHaveTextContent("nova_kin"));
    expect(screen.getByTestId("identity-revision")).toHaveTextContent("2");
  });

  it("提交与当前相同的名字：明确说名称未变，不动 revision", async () => {
    openIdentity("fields_unknown");
    await screen.findByTestId("identity-username");
    await userEvent.type(screen.getByLabelText(/新名字/), "minekin");
    expect(screen.getByTestId("identity-same-name")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByTestId("identity-submit"));
    expect(await screen.findByTestId("identity-result")).toHaveTextContent("名称未变");
    expect(screen.getByTestId("identity-revision")).toHaveTextContent("1");
  });

  it("服务器具名拒止原样送到面板，且当前身份保持不变", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            schemaVersion: "kin-dashboard-identity/1.0.0",
            error: "stale_revision",
            message: "身份修订号已前进：有人先改了这个 Kin。",
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        );
      }
      const url = String(input);
      if (url.includes("/identity")) {
        return new Response(JSON.stringify(buildMockIdentity("fields_unknown", Date.now())), {
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
          initialTab="identity"
        />,
      );
      await screen.findByTestId("identity-username");
      await userEvent.type(screen.getByLabelText(/新名字/), "late_kin");
      await userEvent.click(screen.getByRole("checkbox"));
      await userEvent.click(screen.getByTestId("identity-submit"));

      const refusal = await screen.findByTestId("identity-refusal");
      expect(refusal).toHaveTextContent("write_refused");
      expect(refusal).toHaveTextContent("stale_revision");
      // A refused rename changes nothing: the panel keeps reporting the identity it already had.
      expect(screen.getByTestId("identity-username")).toHaveTextContent("minekin");
      expect(screen.getByTestId("identity-revision")).toHaveTextContent("1");
      expect(screen.queryByTestId("identity-result")).toBeNull();
    } finally {
      globalThis.fetch = original;
    }
  });
});
