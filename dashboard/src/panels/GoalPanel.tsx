import type { KinReadAdapter } from "../domain/adapter";
import { useGoalRead } from "../hooks/useGoalController";
import { Panel } from "../components/Panel";
import styles from "./goal.module.css";

const SOURCE_NOTE =
  "这是下次运行使用的已存目标。合成计划显示总材料预算（非背包已有），包含需要制作的工作台；实际进展请查看会话动作记录。";

function goalIsStale(observedAt: string, staleAfterMs: number, nowMs: number): boolean {
  const at = Date.parse(observedAt);
  if (Number.isNaN(at)) return true;
  return nowMs - at > staleAfterMs;
}

/**
 * Which known limit a null plan names, in the operator's words. Two boundaries reach this panel
 * and they are not the same sentence: one says the catalog has no recipe for the product, the
 * other says the recipe is known but a step needs a grid wider than this build can open. The raw
 * token always rides along in the render, so the panel never paraphrases a boundary into hiding
 * the exact word the read returned.
 */
function boundaryCopy(precondition: string): string {
  if (precondition === "CRAFT_GRID_TOO_SMALL") {
    return "该配方需要更大的合成网格，当前配方知识没有提供可达到该网格的前提。";
  }
  if (precondition === "CRAFT_RECIPE_UNAVAILABLE") {
    return "该产物不在当前精选目录内，因此没有可投影的合成计划。这是目录覆盖的已知边界，不是通用合成能力；小目录只是暂时回退，不能冒充全量知识来源。";
  }
  return "该目标因一处前提限制无法投影出合成计划。这是已知边界，不是通用合成能力。";
}

/**
 * The 任务 page. It consumes the pure goal read (`gateway/goal_read.py`) through the adapter seam and
 * renders exactly what that document claims: the standing milestone, the gross build plan the curated
 * catalog implies, or — when the goal stops short of a runnable plan — the one named boundary that
 * says why (an out-of-cover recipe, or a grid this build cannot yet open).
 * There is no write here; a goal is set on the config page, and this panel deliberately reports no live
 * progress (the read carries gross counts, never a bag snapshot) so it can neither fake advancement nor
 * leak a token the seam already refuses to surface.
 */
export function GoalPanel({ adapter, nowMs }: { readonly adapter: KinReadAdapter; readonly nowMs: number }) {
  const { goal, failure, isLoading } = useGoalRead(adapter);

  return (
    <Panel
      title="任务 · 目标与合成计划"
      note="查看已保存的目标与合成材料预算。前往配置页修改目标。"
      testId="panel-goal"
    >
      {isLoading && goal === null ? (
        <p className={styles.state} data-testid="goal-loading">
          正在读取目标…
        </p>
      ) : null}

      {failure !== null && goal === null ? (
        <p className={styles.readFailure} data-testid="goal-read-failure">
          目标读数失败（{failure.kind}）：{failure.message}
        </p>
      ) : null}

      {goal === null ? null : (
        <>
          {goal.loadError !== null ? (
            <p className={styles.loadError} data-testid="goal-load-error">
              已存目标无法解析：{goal.loadError}。这里按空状态呈现，配置页保存一份干净文档后即恢复。
            </p>
          ) : null}

          <p className={styles.freshness} data-testid="goal-freshness">
            {goalIsStale(goal.observedAt, goal.staleAfterMs, nowMs)
              ? "读数已陈旧：以最新一次成功读取为准。"
              : `读数新鲜（观测于 ${goal.observedAt}）。`}
          </p>

          {goal.configured === false ? (
            <p className={styles.empty} data-testid="goal-empty">
              尚未设置目标。在配置页填写产物、数量、来源物品与说明并保存后，这里会显示对应的里程碑与合成计划。
            </p>
          ) : (
            <>
              <div className={styles.milestone} data-testid="goal-milestone">
                <p className={styles.direction}>{goal.milestone?.direction ?? ""}</p>
                <dl className={styles.facts}>
                  <div className={styles.fact}>
                    <dt>产物</dt>
                    <dd data-testid="goal-product">{goal.milestone?.productId ?? ""}</dd>
                  </div>
                  <div className={styles.fact}>
                    <dt>数量</dt>
                    <dd data-testid="goal-quantity">{goal.milestone?.quantity ?? 0}</dd>
                  </div>
                  <div className={styles.fact}>
                    <dt>来源物品</dt>
                    <dd data-testid="goal-source">{goal.milestone?.sourceItemId ?? ""}</dd>
                  </div>
                </dl>
              </div>

              {goal.precondition !== null ? (
                <p className={styles.boundary} data-testid="goal-boundary">
                  合成边界：{boundaryCopy(goal.precondition)}（{goal.precondition}）
                </p>
              ) : null}

              {goal.plan !== null ? (
                <div className={styles.plan} data-testid="goal-plan">
                  <p className={styles.planTitle}>目录推得的合成计划（按合成顺序，先配料后成品）</p>
                  <ol className={styles.steps}>
                    {goal.plan.map((step) => (
                      <li key={step.productId} className={styles.step} data-testid={`goal-step-${step.productId}`}>
                        <p className={styles.stepHead}>
                          <span className={styles.stepProduct}>{step.productId}</span>
                          <span className={styles.stepCount}>需 {step.requiredTotal} 个（总量）</span>
                        </p>
                        <ul className={styles.materials}>
                          {step.materials.map((material) => (
                            <li key={material.itemId} className={styles.material}>
                              <span>{material.itemId}</span>
                              <span className={styles.materialCount}>每批 ×{material.count}</span>
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ol>
                  <p className={styles.planCaveat}>
                    「需 N 个（总量）」是该目标推得的总量、非背包已有；「每批 ×M」是单次合成的消耗。二者都不是执行确认。
                  </p>
                </div>
              ) : null}
            </>
          )}

          <p className={styles.stability}>{SOURCE_NOTE}</p>
        </>
      )}
    </Panel>
  );
}
