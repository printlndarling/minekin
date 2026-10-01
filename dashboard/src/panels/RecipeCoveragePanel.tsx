import type { KinReadAdapter } from "../domain/adapter";
import type { RecipeRow } from "../domain/model";
import { useRecipeCoverageRead } from "../hooks/useRecipeCoverageController";
import { Panel } from "../components/Panel";
import styles from "./recipe.module.css";

const SOURCE_NOTE =
  "合成知识来自 Core 精选目录的版本化读数（`gateway/recipe_read.py`）：这一页只把目录自己声明的覆盖边界投影出来，不写入、不改动，也不显示任何执行进度。目录覆盖有限、且 `universal` 恒为 false——它不是通用合成源，目录之外的产物在任务页会以具名边界另行说明。";

function coverageIsStale(observedAt: string, staleAfterMs: number, nowMs: number): boolean {
  const at = Date.parse(observedAt);
  if (Number.isNaN(at)) return true;
  return nowMs - at > staleAfterMs;
}

function provenanceLabel(row: RecipeRow): string {
  return row.provenance === "live_confirmed" ? "已在受控服务器看过" : "精选自游戏数据·未看过";
}

/**
 * The 配方知识 page. It consumes the pure recipe-coverage read (`gateway/recipe_read.py`) through the
 * adapter seam and renders exactly what that document claims: the single version the rows describe,
 * the hard-wired `universal: false` boundary, the covered region split into watched and curated, and
 * one row per known craft with its grid shape, per-batch cost, yield, and whether the two-by-two grid
 * this build opens can hold it. There is no write here and no fabricated progress: a row is catalog
 * knowledge, not a claim that anything was crafted this session. A recipe whose shape exceeds the
 * opened grid (a three-by-three pickaxe) is marked as beyond what this build can lay out — the same
 * boundary the task page names with `CRAFT_GRID_TOO_SMALL`, stated here as data rather than paraphrased.
 */
export function RecipeCoveragePanel({
  adapter,
  nowMs,
}: {
  readonly adapter: KinReadAdapter;
  readonly nowMs: number;
}) {
  const { coverage, failure, isLoading } = useRecipeCoverageRead(adapter);

  return (
    <Panel
      title="配方知识 · 覆盖边界"
      note="这一页是纯读：它显示当前版本精选目录覆盖到哪些合成、各自形状与来源，不提交、不控制会话、也不注入游戏输入。目录明确声明自己不是通用合成源。"
      testId="panel-recipe"
    >
      {isLoading && coverage === null ? (
        <p className={styles.state} data-testid="recipe-loading">
          正在读取配方覆盖…
        </p>
      ) : null}

      {failure !== null && coverage === null ? (
        <p className={styles.readFailure} data-testid="recipe-read-failure">
          配方覆盖读数失败（{failure.kind}）：{failure.message}
        </p>
      ) : null}

      {coverage === null ? null : (
        <>
          <p className={styles.freshness} data-testid="recipe-freshness">
            {coverageIsStale(coverage.observedAt, coverage.staleAfterMs, nowMs)
              ? "读数已陈旧：以最新一次成功读取为准。"
              : `读数新鲜（观测于 ${coverage.observedAt}）。`}
          </p>

          <div className={styles.boundary} data-testid="recipe-boundary">
            <p className={styles.boundaryHead}>
              版本 <code>{coverage.gameVersion}</code> · 覆盖 <code>{coverage.covered.length}</code> 个产物 ·
              当前可展开网格 {coverage.playerGridSide}×{coverage.playerGridSide}
            </p>
            <p className={styles.boundaryNote} data-testid="recipe-universal-false">
              通用合成源：{coverage.universal === false ? "否" : "是"}。{SOURCE_NOTE}
            </p>
          </div>

          <dl className={styles.split}>
            <div className={styles.splitGroup} data-testid="recipe-live">
              <dt>已看过（live_confirmed）</dt>
              <dd>
                {coverage.liveConfirmed.length === 0
                  ? "（无）"
                  : coverage.liveConfirmed.map((id) => (
                      <code key={id} className={styles.tag}>
                        {id}
                      </code>
                    ))}
              </dd>
            </div>
            <div className={styles.splitGroup} data-testid="recipe-curated">
              <dt>仅精选未看过（curated_unwatched）</dt>
              <dd>
                {coverage.curatedUnwatched.length === 0
                  ? "（无）"
                  : coverage.curatedUnwatched.map((id) => (
                      <code key={id} className={styles.tag}>
                        {id}
                      </code>
                    ))}
              </dd>
            </div>
          </dl>

          {coverage.recipes.length === 0 ? (
            <p className={styles.empty} data-testid="recipe-empty">
              目录当前没有可列出的配方行。
            </p>
          ) : (
            <ul className={styles.rows}>
              {coverage.recipes.map((row) => (
                <li
                  key={row.productId}
                  className={styles.row}
                  data-testid={`recipe-row-${row.productId}`}
                  data-fits={row.fitsPlayerGrid ? "true" : "false"}
                >
                  <p className={styles.rowHead}>
                    <span className={styles.rowProduct}>{row.productId}</span>
                    <span className={styles.rowShape}>
                      {row.gridWidth}×{row.gridHeight} · 每批产出 {row.yields}
                    </span>
                  </p>
                  <p className={styles.rowProvenance} data-testid={`recipe-provenance-${row.productId}`}>
                    来源：{provenanceLabel(row)}（{row.provenance}）
                  </p>
                  {row.fitsPlayerGrid ? null : (
                    <p className={styles.gridBoundary} data-testid={`recipe-grid-boundary-${row.productId}`}>
                      该形状 {row.gridWidth}×{row.gridHeight} 超出当前可展开的 {coverage.playerGridSide}×
                      {coverage.playerGridSide} 网格，需要先能放置或打开工作台——这是执行能力的已知边界（CRAFT_GRID_TOO_SMALL）。
                    </p>
                  )}
                  <ul className={styles.materials}>
                    {row.ingredients.map((ingredient) => (
                      <li key={ingredient.itemId} className={styles.material}>
                        <span>{ingredient.itemId}</span>
                        <span className={styles.materialCount}>每批 ×{ingredient.count}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}

          <p className={styles.caveat}>
            每行列出的是单次合成的形状、产出与配料，是目录知识而非任何执行确认；「已看过 / 仅精选未看过」区分的是这个构建是否在某次真实运行里见证过该合成，二者都不代表此刻背包里有什么。
          </p>
        </>
      )}
    </Panel>
  );
}
