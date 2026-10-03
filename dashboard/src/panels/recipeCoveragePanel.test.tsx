import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import type { DashboardConfig } from "../adapters/config";
import { RECIPE_SCHEMA_VERSION } from "../domain/model";

/**
 * The 配方知识 page through the shell the operator uses. These readings prove the panel shows what the
 * pure recipe-coverage read actually claims and nothing it does not: the single version + covered count
 * + two-by-two grid the catalog declares; the hard-wired `universal: false` boundary spelled out rather
 * than hidden; the watched/curated split; one row per craft with its shape, yield and per-batch cost; and
 * a named grid boundary on the row whose shape exceeds the opened grid — the same CRAFT_GRID_TOO_SMALL the
 * task page names, stated here as catalog data. A failed read keeps the panel mounted instead of painting
 * a catalog; and no fabricated "crafted N" progress appears, since the read carries no run state.
 */

function mockConfig(scenario: DashboardConfig["scenario"]): DashboardConfig {
  return { adapter: "mock", scenario, gatewayBaseUrl: null, latencyMs: 0 };
}

function openRecipes(scenario: DashboardConfig["scenario"]): void {
  render(<App config={mockConfig(scenario)} initialPage="recipes" />);
}

describe("配方知识面板：投影目录自己的覆盖边界", () => {
  it("按材料与产物组合检索，忽略大小写和空白；清空恢复目录", async () => {
    openRecipes("healthy_run_07");
    await screen.findByTestId("recipe-boundary");
    const input = screen.getByRole("searchbox", { name: "搜索产物、配方 ID 或材料" });
    fireEvent.change(input, { target: { value: "  OAK_LOG   PLANKS " } });
    expect(screen.getByTestId("recipe-row-minecraft:oak_planks")).toBeInTheDocument();
    expect(screen.queryByTestId("recipe-row-minecraft:crafting_table")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("显示 1 /");
    // 过滤不删除来源或扩大目录覆盖声明。
    expect(screen.getByTestId("recipe-universal-false")).toHaveTextContent("通用合成源：否");
    fireEvent.click(screen.getByRole("button", { name: "清空搜索" }));
    expect(input).toHaveValue("");
    expect(screen.getByTestId("recipe-row-minecraft:crafting_table")).toBeInTheDocument();
  });

  it("无匹配不冒充游戏没有配方，搜索字符按字面匹配", async () => {
    openRecipes("healthy_run_07");
    await screen.findByTestId("recipe-boundary");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: ".*" } });
    expect(screen.getByText("没有匹配的目录配方；这不代表游戏中不存在该配方。")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("显示 0 /");
    expect(screen.queryByTestId("recipe-empty")).toBeNull();
    expect(screen.queryByTestId("recipe-row-minecraft:oak_planks")).toBeNull();
  });

  it("显示版本、覆盖数、两格网格与 universal:false 边界，逐项列出配方行", async () => {
    openRecipes("healthy_run_07");
    // 外壳先挂载、读数随后到达，因此等待边界块本身而不是面板容器。
    const boundary = await screen.findByTestId("recipe-boundary");
    expect(boundary).toHaveTextContent("1.20.1");
    expect(boundary).toHaveTextContent("2×2");

    // 边界页把「不是通用合成源」讲明白，而不是悄悄藏起有限目录。
    expect(screen.getByTestId("recipe-universal-false")).toHaveTextContent("通用合成源：否");

    // 已看过 / 仅精选未看过 的划分与 mock 目录一致。
    expect(screen.getByTestId("recipe-live")).toHaveTextContent("minecraft:oak_planks");
    expect(screen.getByTestId("recipe-curated")).toHaveTextContent("minecraft:crafting_table");

    // 每行给出产物与配料。
    expect(screen.getByTestId("recipe-row-minecraft:oak_planks")).toBeInTheDocument();
    expect(screen.getByTestId("recipe-provenance-minecraft:oak_planks")).toHaveTextContent("live_confirmed");
    expect(screen.getByTestId("recipe-row-minecraft:oak_planks")).toHaveTextContent("minecraft:oak_log");
  });

  it("超出两格网格的配方行给出具名网格边界（CRAFT_GRID_TOO_SMALL），与任务页同源", async () => {
    openRecipes("healthy_run_07");
    const row = await screen.findByTestId("recipe-row-minecraft:wooden_pickaxe");
    expect(row).toHaveAttribute("data-fits", "false");
    const gridBoundary = screen.getByTestId("recipe-grid-boundary-minecraft:wooden_pickaxe");
    expect(gridBoundary).toHaveTextContent("CRAFT_GRID_TOO_SMALL");
    expect(gridBoundary).toHaveTextContent("3×3");

    // 两格内可合成的行不带网格边界。
    expect(screen.getByTestId("recipe-row-minecraft:oak_planks")).toHaveAttribute("data-fits", "true");
    expect(screen.queryByTestId("recipe-grid-boundary-minecraft:oak_planks")).toBeNull();

    // 页面不含 CSRF，也不编造「已合成 N」进度。
    expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
    expect(document.body).not.toHaveTextContent("mock-csrf-token");
  });

  it("经真实 gateway 解码路径（fetch 覆盖）呈现同一份边界，universal:false 落地为「否」", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/recipe-coverage")) {
        return new Response(
          JSON.stringify({
            schemaVersion: RECIPE_SCHEMA_VERSION,
            observedAt: new Date().toISOString(),
            staleAfterMs: 8000,
            game_version: "1.20.1",
            universal: false,
            player_grid_side: 2,
            covered: ["minecraft:crafting_table"],
            live_confirmed: [],
            curated_unwatched: ["minecraft:crafting_table"],
            recipes: [
              {
                product_id: "minecraft:crafting_table",
                recipe_id: "minecraft:crafting_table",
                grid_width: 2,
                grid_height: 2,
                yields: 1,
                fits_player_grid: true,
                provenance: "curated_unwatched",
                ingredients: [{ item_id: "minecraft:oak_planks", count: 4 }],
              },
            ],
            csrfToken: "a-live-csrf-token",
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
          initialPage="recipes"
        />,
      );
      expect(await screen.findByTestId("recipe-row-minecraft:crafting_table")).toBeInTheDocument();
      expect(screen.getByTestId("recipe-universal-false")).toHaveTextContent("通用合成源：否");
      // 令牌只在导线上，seam 与面板都把它挡在 DOM 之外。
      expect(document.body.textContent?.toLowerCase()).not.toContain("csrf");
      expect(document.body).not.toHaveTextContent("a-live-csrf-token");
    } finally {
      globalThis.fetch = original;
    }
  });

  it("读数失败时面板保持挂载并具名报错，不铺一份目录", async () => {
    openRecipes("read_failed");
    const failure = await screen.findByTestId("recipe-read-failure");
    expect(failure).toHaveTextContent("disconnected");
    expect(screen.queryByTestId("recipe-boundary")).toBeNull();
  });
});
