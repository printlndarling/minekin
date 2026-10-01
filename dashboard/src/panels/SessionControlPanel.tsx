import { useState } from "react";
import type { FormEvent } from "react";
import type { KinReadAdapter } from "../domain/adapter";
import { KIN_STATE_LABELS } from "../domain/labels";
import type { StopReport } from "../domain/model";
import { useSessionController } from "../hooks/useSessionController";
import { Panel } from "../components/Panel";
import styles from "./sessionControl.module.css";

const STOP_NOTICE =
  "停止会先释放这个 Kin 持有的输入租约，再终止能证明属于本产品的客户端进程；无法确认归属的进程一律不接管。它不会删除配置、身份或已封证据，也不会自动重新连接。";

// Only the verbs Core reports as unavailable get a Chinese label; the reason stays the server's own
// sentence, so a start/pause/resume the panel cannot offer is named, never silently dropped.
const UNAVAILABLE_VERB_LABELS: Record<string, string> = {
  start: "启动",
  pause: "暂停",
  resume: "恢复",
};

function pids(list: readonly number[]): string {
  return list.length === 0 ? "无" : list.join(", ");
}

function sessionIsStale(observedAt: string, staleAfterMs: number, nowMs: number): boolean {
  const at = Date.parse(observedAt);
  if (Number.isNaN(at)) return false;
  return at + staleAfterMs < nowMs;
}

/**
 * The session-control surface the goal authorizes (capability 6: 暂停、恢复和停止). Everything above
 * the form reports the observed session and the ONE verb this process performs safely today — stop.
 * start/pause/resume are listed as named `unavailableControls` rather than rendered as buttons that a
 * later POST would refuse. The submit mirrors the server's own gates: it is reachable only when
 * `stopAllowed` (a session that is not idle) and the operator has confirmed. A `blocked` stop report
 * — one that left inputs unconfirmed or a process unresolved — stays spelled as blocked, never folded
 * into a green one.
 */
export function SessionControlPanel({
  adapter,
  nowMs,
}: {
  readonly adapter: KinReadAdapter;
  readonly nowMs: number;
}) {
  const controller = useSessionController(adapter);
  const [confirmed, setConfirmed] = useState(false);
  const { session } = controller;

  const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (session === null || !session.stopAllowed || controller.pending) return;
    // confirm is the explicit flag; the CSRF token is held in the adapter and echoed there, never
    // through this component, so a stop cannot fire on a stray keystroke and the token never renders.
    controller.submit({ confirm: true });
  };

  const outcome = controller.outcome;

  return (
    <Panel
      title="会话 · 控制"
      note="这是第三次被授权的写入：只在本机、需显式确认、仅停止能安全执行的动作——先释放输入再停进程，不启动、不暂停、不注入游戏输入，也不持有任何凭据。"
      testId="panel-session-control"
    >
      {controller.isLoading && session === null ? (
        <p className={styles.state} data-testid="session-loading">
          正在读取会话状态…
        </p>
      ) : null}

      {controller.failure !== null && session === null ? (
        <p className={styles.readFailure} data-testid="session-read-failure">
          会话读数失败（{controller.failure.kind}）：{controller.failure.message}
        </p>
      ) : null}

      {session === null ? null : (
        <>
          <dl className={styles.fields}>
            <div className={styles.field}>
              <dt className={styles.label}>会话状态</dt>
              <dd className={styles.value} data-testid="session-state">
                {KIN_STATE_LABELS[session.state]}
              </dd>
            </div>
            <div className={styles.field}>
              <dt className={styles.label}>当前可执行</dt>
              <dd className={styles.value} data-testid="session-available">
                {session.availableControls.length === 0 ? "无" : session.availableControls.join(", ")}
              </dd>
            </div>
          </dl>

          <p className={styles.freshness} data-testid="session-freshness">
            {sessionIsStale(session.observedAt, session.staleAfterMs, nowMs)
              ? "读数已陈旧：停止以最新一次成功读取为准。"
              : `读数新鲜（观测于 ${session.observedAt}）。`}
          </p>

          {session.unavailableControls.length > 0 ? (
            <ul className={styles.unavailable} data-testid="session-unavailable">
              {session.unavailableControls.map((control) => (
                <li key={control.verb} className={styles.unavailableItem}>
                  <span className={styles.unavailableVerb}>
                    {UNAVAILABLE_VERB_LABELS[control.verb] ?? control.verb}
                  </span>
                  暂不开放——{control.reason}
                </li>
              ))}
            </ul>
          ) : null}

          <form className={styles.form} onSubmit={onSubmit}>
            <label className={styles.confirm}>
              <input
                type="checkbox"
                checked={confirmed}
                disabled={!session.stopAllowed || controller.pending}
                onChange={(event) => {
                  setConfirmed(event.target.checked);
                  if (outcome !== null) controller.clearOutcome();
                }}
              />
              <span>{STOP_NOTICE}</span>
            </label>

            <button
              type="submit"
              className={styles.submit}
              data-testid="session-stop-submit"
              disabled={!session.stopAllowed || !confirmed || controller.pending}
            >
              {controller.pending ? "提交中…" : "确认停止会话"}
            </button>

            {!session.stopAllowed ? (
              <p className={styles.caption} data-testid="session-stop-locked">
                没有运行中的会话可停止（当前状态：{KIN_STATE_LABELS[session.state]}）。
              </p>
            ) : null}
          </form>

          {outcome?.ok && outcome.result !== null ? (
            <StopReportView report={outcome.result.report} />
          ) : null}

          {outcome !== null && !outcome.ok && outcome.failure !== null ? (
            <p className={styles.refusal} data-testid="session-refusal">
              停止被拒绝（{outcome.failure.kind}）：{outcome.failure.message}
            </p>
          ) : null}
        </>
      )}
    </Panel>
  );
}

/**
 * Core's stop outcome rendered honestly: `stopped` and `blocked` are two different answers, and the
 * pid buckets name what was released and what was left unconfirmed or unresolved. A blocked report is
 * never presented as a clean success.
 */
function StopReportView({ report }: { readonly report: StopReport }) {
  const { release, outcome } = report;
  const blocked = report.status === "blocked";
  return (
    <div>
      <p
        className={blocked ? styles.blocked : styles.result}
        data-testid={blocked ? "session-result-blocked" : "session-result-stopped"}
      >
        {blocked
          ? `停止未完成（blocked）：仍有未确认释放的输入或无法确认归属的进程，不能当作已干净停止。`
          : "会话已停止：输入租约已确认释放，本产品启动的客户端进程已终止。"}
      </p>
      <p className={styles.buckets} data-testid="session-report-buckets">
        释放：已确认 {release.released.length}／未确认 {release.unconfirmed.length}／未曾持有 {release.nothingHeld.length}；
        进程：已终止 {outcome.terminated.length}／有意保留 {outcome.leftAlone.length}／无法确认 {outcome.unresolved.length}。
        已终止 pid：{pids(outcome.terminated)}；未确认 pid：{pids(release.unconfirmed)}；无法确认 pid：{pids(outcome.unresolved)}。
      </p>
    </div>
  );
}
