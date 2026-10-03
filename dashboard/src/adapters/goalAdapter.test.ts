import { describe, expect, it } from "vitest";
import { decodeGoalPayload, GOAL_ENDPOINTS } from "./gatewayAdapter";
import { buildMockGoal } from "../fixtures/mockFixtures";
import { GOAL_SCHEMA_VERSION } from "../domain/model";

/**
 * The goal read is a pure projection of the saved config, and its decoder is the single seam both the
 * Gateway and the mock feed bytes through. These readings pin the contract the panel relies on: a flat
 * document decoded whole-or-not-at-all, `configured` driving the empty-vs-populated split, a configured
 * goal carrying EXACTLY one of (plan) or (precondition) so it can never render as simultaneously planned
 * and blocked, and the per-process CSRF token staying out of the model — the seam's whole reason the UI
 * cannot leak it.
 */

function doc(over: Record<string, unknown>): Record<string, unknown> {
  return {
    schemaVersion: GOAL_SCHEMA_VERSION,
    loadError: null,
    observedAt: "2026-10-01T00:00:00+00:00",
    staleAfterMs: 8_000,
    ...over,
  };
}

describe("decodeGoalPayload：整份解码", () => {
  it("未配置目标：configured:false 且 milestone/plan/precondition 全为 null", () => {
    const decoded = decodeGoalPayload(doc({ configured: false, milestone: null, plan: null, precondition: null }));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.configured).toBe(false);
    expect(decoded.goal.milestone).toBeNull();
    expect(decoded.goal.plan).toBeNull();
    expect(decoded.goal.precondition).toBeNull();
  });

  it("目录内产物：configured:true + milestone + plan 数组，precondition 为 null", () => {
    const decoded = decodeGoalPayload(
      doc({
        configured: true,
        milestone: {
          product_id: "minecraft:wooden_pickaxe",
          quantity: 1,
          source_item_id: "minecraft:oak_log",
          direction: "先挖木头，再合成木镐",
        },
        plan: [
          { product_id: "minecraft:oak_planks", required_total: 5, materials: [{ item_id: "minecraft:oak_log", count: 1 }] },
          { product_id: "minecraft:stick", required_total: 2, materials: [{ item_id: "minecraft:oak_planks", count: 2 }] },
          {
            product_id: "minecraft:wooden_pickaxe",
            required_total: 1,
            materials: [
              { item_id: "minecraft:oak_planks", count: 3 },
              { item_id: "minecraft:stick", count: 2 },
            ],
          },
        ],
        precondition: null,
      }),
    );
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.milestone?.productId).toBe("minecraft:wooden_pickaxe");
    expect(decoded.goal.milestone?.direction).toBe("先挖木头，再合成木镐");
    expect(decoded.goal.plan?.map((step) => step.productId)).toEqual([
      "minecraft:oak_planks",
      "minecraft:stick",
      "minecraft:wooden_pickaxe",
    ]);
    expect(decoded.goal.precondition).toBeNull();
  });

  it("目录外产物：configured:true + milestone + precondition 具名，plan 为 null", () => {
    const decoded = decodeGoalPayload(
      doc({
        configured: true,
        milestone: {
          product_id: "minecraft:diamond_pickaxe",
          quantity: 1,
          source_item_id: "minecraft:diamond",
          direction: "",
        },
        plan: null,
        precondition: "CRAFT_RECIPE_UNAVAILABLE",
      }),
    );
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.plan).toBeNull();
    expect(decoded.goal.precondition).toBe("CRAFT_RECIPE_UNAVAILABLE");
  });

  it("既给 plan 又给 precondition 视为契约不符：一个目标不能同时有计划又被挡", () => {
    const decoded = decodeGoalPayload(
      doc({
        configured: true,
        milestone: {
          product_id: "minecraft:stick",
          quantity: 2,
          source_item_id: "minecraft:oak_log",
          direction: "x",
        },
        plan: [{ product_id: "minecraft:stick", required_total: 2, materials: [{ item_id: "minecraft:oak_planks", count: 2 }] }],
        precondition: "CRAFT_RECIPE_UNAVAILABLE",
      }),
    );
    expect(decoded.ok).toBe(false);
    if (decoded.ok) return;
    expect(decoded.issues.join("；")).toContain("恰有 plan 或 precondition 之一");
  });

  it("未配置却带了 milestone：整份拒解，不部分填充", () => {
    const decoded = decodeGoalPayload(
      doc({
        configured: false,
        milestone: { product_id: "minecraft:stick", quantity: 1, source_item_id: "", direction: "x" },
        plan: null,
        precondition: null,
      }),
    );
    expect(decoded.ok).toBe(false);
  });

  it("缺字段（无 configured）：整份拒解", () => {
    const decoded = decodeGoalPayload(doc({ milestone: null, plan: null, precondition: null }));
    expect(decoded.ok).toBe(false);
    if (decoded.ok) return;
    expect(decoded.issues.some((issue) => issue.includes("configured"))).toBe(true);
  });

  it("非 object 载荷：整份拒解而不是崩溃", () => {
    expect(decodeGoalPayload(null).ok).toBe(false);
    expect(decodeGoalPayload([]).ok).toBe(false);
  });

  it("CSRF 令牌只在导线上，解码后的模型里没有它", () => {
    const decoded = decodeGoalPayload(
      doc({
        configured: false,
        milestone: null,
        plan: null,
        precondition: null,
        csrfToken: "a-live-csrf-token",
      }),
    );
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    const goal = decoded.goal as unknown as Record<string, unknown>;
    expect(goal.csrfToken).toBeUndefined();
    expect(Object.keys(goal)).not.toContain("csrfToken");
  });
});

describe("mock 目标与真实解码器闭环", () => {
  it("healthy_run_07（预填木镐）解码工作台前提与材料预算", () => {
    const decoded = decodeGoalPayload(buildMockGoal("healthy_run_07", Date.now()));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.configured).toBe(true);
    expect(decoded.goal.precondition).toBeNull();
    expect(decoded.goal.plan?.map((step) => step.productId)).toEqual([
      "minecraft:oak_planks", "minecraft:stick", "minecraft:crafting_table", "minecraft:wooden_pickaxe",
    ]);
    expect(decoded.goal.plan?.[0]?.requiredTotal).toBe(9);
  });

  it("网格内产物（工作台）的 mock 目标仍落到多步行计划，闭环覆盖计划与边界两种形状", () => {
    const decoded = decodeGoalPayload(
      buildMockGoal("healthy_run_07", Date.now(), {
        goal_product_id: "minecraft:crafting_table",
        goal_quantity: "1",
      }),
    );
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.configured).toBe(true);
    expect(decoded.goal.plan?.map((step) => step.productId)).toEqual([
      "minecraft:oak_planks",
      "minecraft:crafting_table",
    ]);
    expect(decoded.goal.precondition).toBeNull();
  });

  it("目录外产物的 mock 目标落到具名边界，而不是编一个计划", () => {
    const decoded = decodeGoalPayload(
      buildMockGoal("healthy_run_07", Date.now(), { goal_product_id: "minecraft:diamond_sword", goal_quantity: "1" }),
    );
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.plan).toBeNull();
    expect(decoded.goal.precondition).toBe("CRAFT_RECIPE_UNAVAILABLE");
  });

  it("无产物的 mock 目标就是空状态，不是错误", () => {
    const decoded = decodeGoalPayload(buildMockGoal("healthy_run_07", Date.now(), {}));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.goal.configured).toBe(false);
    expect(decoded.goal.milestone).toBeNull();
  });

  it("目标读走 GET 路由 /api/v1/dashboard/goal", () => {
    expect(GOAL_ENDPOINTS.goal).toBe("/api/v1/dashboard/goal");
  });
});
