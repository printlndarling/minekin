import { describe, expect, it } from "vitest";
import { decodeRecipeCoveragePayload, RECIPE_ENDPOINTS } from "./gatewayAdapter";
import { buildMockRecipeCoverage } from "../fixtures/mockFixtures";
import { RECIPE_SCHEMA_VERSION } from "../domain/model";

/**
 * The recipe-coverage read is a pure projection of the curated catalog's own coverage boundary, and
 * its decoder is the single seam both the Gateway and the mock feed bytes through. These readings pin
 * the contract the 配方知识 page relies on: a flat document decoded whole-or-not-at-all, the document's
 * own honesty invariant (`universal` must be the catalog's hard-wired `false`) enforced at the seam so a
 * `true` byte can never reach the panel, the provenance enum restricted to the two words the catalog
 * actually uses, and per-row grid-fit read as a boolean. There is no CSRF on this wire — the read has no
 * write partner — so none is dropped or kept, and a byte that carries one stays out of the model.
 */

function row(over: Record<string, unknown>): Record<string, unknown> {
  return {
    product_id: "minecraft:oak_planks",
    recipe_id: "minecraft:oak_planks",
    grid_width: 1,
    grid_height: 1,
    yields: 4,
    fits_player_grid: true,
    provenance: "live_confirmed",
    ingredients: [{ item_id: "minecraft:oak_log", count: 1 }],
    ...over,
  };
}

function doc(over: Record<string, unknown>): Record<string, unknown> {
  return {
    schemaVersion: RECIPE_SCHEMA_VERSION,
    observedAt: "2026-10-01T00:00:00+00:00",
    staleAfterMs: 8_000,
    game_version: "1.20.1",
    universal: false,
    player_grid_side: 2,
    covered: ["minecraft:oak_planks"],
    live_confirmed: ["minecraft:oak_planks"],
    curated_unwatched: [],
    recipes: [row({})],
    ...over,
  };
}

describe("decodeRecipeCoveragePayload：整份解码", () => {
  it("合法目录文档：整份接住，snake→camel 只在解码器发生", () => {
    const decoded = decodeRecipeCoveragePayload(doc({}));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.coverage.gameVersion).toBe("1.20.1");
    expect(decoded.coverage.universal).toBe(false);
    expect(decoded.coverage.playerGridSide).toBe(2);
    expect(decoded.coverage.covered).toEqual(["minecraft:oak_planks"]);
    expect(decoded.coverage.liveConfirmed).toEqual(["minecraft:oak_planks"]);
    expect(decoded.coverage.curatedUnwatched).toEqual([]);
    const first = decoded.coverage.recipes[0];
    if (first === undefined) throw new Error("解码结果应含一行配方");
    expect(first.productId).toBe("minecraft:oak_planks");
    expect(first.recipeId).toBe("minecraft:oak_planks");
    expect(first.gridWidth).toBe(1);
    expect(first.gridHeight).toBe(1);
    expect(first.yields).toBe(4);
    expect(first.fitsPlayerGrid).toBe(true);
    expect(first.provenance).toBe("live_confirmed");
    expect(first.ingredients).toEqual([{ itemId: "minecraft:oak_log", count: 1 }]);
  });

  it("universal:true 视为契约不符：有限回退不得自称通用合成源，面板永远拿不到可渲染的 true", () => {
    const decoded = decodeRecipeCoveragePayload(doc({ universal: true }));
    expect(decoded.ok).toBe(false);
    if (decoded.ok) return;
    expect(decoded.issues.join("；")).toContain("universal");
  });

  it("universal 非布尔（字符串/缺失）同样整份拒解", () => {
    expect(decodeRecipeCoveragePayload(doc({ universal: "true" })).ok).toBe(false);
    const missing = doc({});
    delete missing.universal;
    expect(decodeRecipeCoveragePayload(missing).ok).toBe(false);
  });

  it("provenance 越出目录实际使用的两个词：整份拒解", () => {
    const decoded = decodeRecipeCoveragePayload(
      doc({ recipes: [row({ provenance: "llm_hypothesis" })] }),
    );
    expect(decoded.ok).toBe(false);
    if (decoded.ok) return;
    expect(decoded.issues.join("；")).toContain("provenance");
  });

  it("fits_player_grid 非布尔：整份拒解，不默认填充", () => {
    expect(decodeRecipeCoveragePayload(doc({ recipes: [row({ fits_player_grid: "yes" })] })).ok).toBe(false);
  });

  it("配料形状不符（缺 count）：整份拒解", () => {
    expect(
      decodeRecipeCoveragePayload(doc({ recipes: [row({ ingredients: [{ item_id: "minecraft:oak_log" }] })] })).ok,
    ).toBe(false);
  });

  it("缺字段（无 game_version）：整份拒解", () => {
    const missing = doc({});
    delete missing.game_version;
    const decoded = decodeRecipeCoveragePayload(missing);
    expect(decoded.ok).toBe(false);
    if (decoded.ok) return;
    expect(decoded.issues.some((issue) => issue.includes("game_version"))).toBe(true);
  });

  it("schemaVersion 版本不符：整份拒解", () => {
    expect(decodeRecipeCoveragePayload(doc({ schemaVersion: "kin-dashboard-recipe/9.9.9" })).ok).toBe(false);
  });

  it("recipes 不是数组：整份拒解而不是崩溃", () => {
    expect(decodeRecipeCoveragePayload(doc({ recipes: {} })).ok).toBe(false);
  });

  it("非 object 载荷：整份拒解而不是崩溃", () => {
    expect(decodeRecipeCoveragePayload(null).ok).toBe(false);
    expect(decodeRecipeCoveragePayload([]).ok).toBe(false);
  });

  it("CSRF 令牌即使出现在导线上也不进入模型：键不在解码结果里", () => {
    const decoded = decodeRecipeCoveragePayload(doc({ csrfToken: "a-live-csrf-token" }));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    const coverage = decoded.coverage as unknown as Record<string, unknown>;
    expect(coverage.csrfToken).toBeUndefined();
    expect(Object.keys(coverage)).not.toContain("csrfToken");
  });
});

describe("mock 配方覆盖与真实解码器闭环", () => {
  it("mock 目录的覆盖文档被解码器整份接住，落到 4 行且网格边界按形状给出", () => {
    const decoded = decodeRecipeCoveragePayload(buildMockRecipeCoverage("healthy_run_07", Date.now()));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.coverage.universal).toBe(false);
    expect(decoded.coverage.gameVersion).toBe("1.20.1");
    expect(decoded.coverage.playerGridSide).toBe(2);
    expect(decoded.coverage.recipes.map((r) => r.productId)).toEqual([
      "minecraft:crafting_table",
      "minecraft:oak_planks",
      "minecraft:stick",
      "minecraft:wooden_pickaxe",
    ]);
    // 木镐 3×3 超出两格可展开网格，是唯一 fitsPlayerGrid:false 的行——与任务页的 CRAFT_GRID_TOO_SMALL 同源。
    expect(decoded.coverage.recipes.find((r) => r.productId === "minecraft:wooden_pickaxe")?.fitsPlayerGrid).toBe(false);
    expect(decoded.coverage.recipes.find((r) => r.productId === "minecraft:oak_planks")?.fitsPlayerGrid).toBe(true);
    // 已看过 / 仅精选未看过 的划分与目录一致，且二者并起来正好是全部覆盖产物。
    expect(decoded.coverage.liveConfirmed).toEqual(["minecraft:oak_planks", "minecraft:stick"]);
    expect(decoded.coverage.curatedUnwatched).toEqual(["minecraft:crafting_table", "minecraft:wooden_pickaxe"]);
    expect(decoded.coverage.covered.length).toBe(
      decoded.coverage.liveConfirmed.length + decoded.coverage.curatedUnwatched.length,
    );
    // 每一行的 provenance 与其所属划分一致。
    for (const r of decoded.coverage.recipes) {
      const expected = decoded.coverage.liveConfirmed.includes(r.productId) ? "live_confirmed" : "curated_unwatched";
      expect(r.provenance).toBe(expected);
    }
  });

  it("配方覆盖读走 GET 路由 /api/v1/dashboard/recipe-coverage", () => {
    expect(RECIPE_ENDPOINTS.recipe).toBe("/api/v1/dashboard/recipe-coverage");
  });
});
