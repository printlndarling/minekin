import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import { GOAL_SCHEMA_VERSION } from "../domain/model";

/**
 * The 任务 page through the shell the operator uses. These readings prove the panel shows what the
 * pure goal read actually claims and nothing it does not: the standing milestone and the gross build
 * plan for a saved covered goal; a plain empty state when no goal is set; a named failure that keeps
 * the panel mounted instead of a fabricated goal; the coverage boundary rendered as the boundary it
 * is when the product falls outside the curated catalog; and no CSRF token reaching the DOM — plus no
 * invented "already have N" progress number, since the read carries gross counts and no bag snapshot.
 */

function mockConfig(scenario: DashboardConfig["scenario"]): DashboardConfig {
  return { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
}

function openTask(scenario: DashboardConfig["scenario"]): void {
  render(<App config={mockConfig(scenario)} initialPage="task" />);
}

describe("任务面板：投影已保存的目标", () => {
  it("已存的目录内目标显示里程碑与三步行计划，页面不含 CSRF 也不含编造的已有数量", async () => {
    openTask("healthy_run_07");
    expect(await screen.findByTestId("panel-goal")).toBeInTheDocument();
    const product = await screen.findByTestId("goal-product");
    expect(product).toHaveTextContent("minecraft:wooden_pickaxe");
    expect(screen.getByTestId("goal-quantity")).toHaveTextContent("1");
    expect(screen.getByTestId("goal-source")).toHaveTextContent("minecraft:oak_log");

    const plan = await screen.findByTestId("goal-plan");
    expect(plan).toBeInTheDocument();
    expect(screen.getByTestId("goal-step-minecraft:oak_planks")).toBeInTheDocument();
    expect(screen.getByTestId("goal-step-minecraft:stick")).toBeInTheDocument();
    expect(screen.getByTestId("goal-step-minecraft:wooden_pickaxe")).toBeInTheDocument();

    // No coverage boundary appears for a planned goal, and no token or invented progress shows.
    expect(screen.queryByTestId("goal-boundary")).toBeNull();
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
    expect(document.body).not.toHaveTextContent("mock-csrf-token");
    expect(screen.getByTestId("goal-plan")).toHaveTextContent("非背包已有");
  });

  it("未设置目标是空状态，而不是错误", async () => {
    openTask("fields_unknown");
    expect(await screen.findByTestId("goal-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("goal-milestone")).toBeNull();
    expect(screen.queryByTestId("goal-plan")).toBeNull();
  });
});

describe("任务面板：失败与覆盖边界", () => {
  it("读数失败时面板保持挂载并具名报错，不铺一个假里程碑", async () => {
    openTask("read_failed");
    const failure = await screen.findByTestId("goal-read-failure");
    expect(failure).toHaveTextContent("disconnected");
    expect(screen.queryByTestId("goal-milestone")).toBeNull();
  });

  it("目录外产物把覆盖边界具名呈现，而不是冒充通用合成计划", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/goal")) {
        return new Response(
          JSON.stringify({
            schemaVersion: GOAL_SCHEMA_VERSION,
            configured: true,
            milestone: {
              product_id: "minecraft:diamond_sword",
              quantity: 1,
              source_item_id: "minecraft:diamond",
              direction: "做一把钻石剑",
            },
            plan: null,
            precondition: "CRAFT_RECIPE_UNAVAILABLE",
            loadError: null,
            csrfToken: "a-live-csrf-token",
            observedAt: new Date().toISOString(),
            staleAfterMs: 8000,
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
          initialPage="task"
        />,
      );
      const boundary = await screen.findByTestId("goal-boundary");
      expect(boundary).toHaveTextContent("CRAFT_RECIPE_UNAVAILABLE");
      expect(screen.queryByTestId("goal-plan")).toBeNull();
      // The token rode the wire; the seam and the panel both keep it out of the DOM.
      expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
      expect(document.body).not.toHaveTextContent("a-live-csrf-token");
    } finally {
      globalThis.fetch = original;
    }
  });
});
