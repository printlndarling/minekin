import type { KinReadAdapter } from "../domain/adapter";
import { useGoalRead } from "../hooks/useGoalController";
import { Panel } from "../components/Panel";
import styles from "./goal.module.css";

const SOURCE_NOTE =
  "目标是在配置页保存、由 Core 落进环境后读回的：这里只把那份已存目标投影出来，不提交、不改动，也不显示实时进度。合成计划是按配方推得的总量（gross），不是背包里已有多少——这个读数拿不到背包快照，所以从不编一个已完成数出来。";

function goalIsStale(observedAt: string, staleAfterMs: number, nowMs: number): boolean {
  const at = Date.parse(observedAt);
  if (Number.isNaN(at)) return true;
  return nowMs - at > staleAfterMs;
}

/**
 * The 任务 page. It consumes the pure goal read (`gateway/goal_read.py`) through the adapter seam and
 * renders exactly what that document claims: the standing milestone, the gross build plan the curated
 * catalog implies, or — when the product is outside the catalog's cover — the named coverage boundary.
 * There is no write here; a goal is set on the config page, and this panel deliberately reports no live
 * progress (the read carries gross counts, never a bag snapshot) so it can neither fake advancement nor
 * leak a token the seam already refuses to surface.
 */
export function GoalPanel({ adapter, nowMs }: { readonly adapter: KinReadAdapter; readonly nowMs: number }) {
  const { goal, failure, isLoading } = useGoalRead(adapter);

  return (
    <Panel
      title="任务 · 目标与合成计划"
      note="这一页是纯读：它显示配置页已存的目标，不提交目标、不控制会话、也不注入游戏输入。密钥从不进入这个读数。"
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
                  配方覆盖边界：该产物不在当前精选目录内（{goal.precondition}），因此没有可投影的合成计划。
                  这是目录的已知边界，不是通用合成能力；小目录只是暂时回退，不能冒充全量知识来源。
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
