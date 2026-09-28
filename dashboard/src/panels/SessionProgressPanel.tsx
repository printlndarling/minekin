import type { ReadFailure } from "../domain/adapter";
import type { SessionProgress } from "../domain/sessionProgress";
import { formatAge, formatDateTime } from "../lib/format";
import { Panel } from "../components/Panel";
import { Pill } from "../components/Pill";
import styles from "./session.module.css";

export interface SessionProgressPanelProps {
  readonly progress: SessionProgress;
  readonly nowMs: number;
  readonly isLoading: boolean;
  readonly failure: ReadFailure | null;
}

/** Core's own wording for an empty ledger, so the two surfaces never disagree. */
const EMPTY_LEDGER = "台账里没有任何事件行：这个 Kin 还没有启动过会话。";

const GAPS: readonly string[] = [
  "客户端 bundle 的准备进度（下载文件数、字节、耗时）没有台账行：run document 只出现在 CLI 标准输出，冻结契约的三个只读端点里没有它的字段。",
  "登录握手失败的服务端原文不在契约暴露字段内：此处只显示 Core 自己写下的 reason。",
];

export function SessionProgressPanel({ progress, nowMs, isLoading, failure }: SessionProgressPanelProps) {
  return (
    <Panel
      title="当前会话阶段（逐条来自台账）"
      note="阶段只按 Core 写下的事件行成立；没有对应行就是「未观测」，不画进度条、不沿用上一次会话的读数。"
      testId="panel-session-progress"
    >
      {failure ? (
        <p className={styles.empty} data-testid="progress-failure">
          时间线读取失败（{failure.kind}）：进度全部按未知呈现，不展示缓存阶段。
        </p>
      ) : isLoading && !progress.hasRows ? (
        <p className={styles.empty} data-testid="progress-loading">
          首次读取台账中…
        </p>
      ) : !progress.hasRows ? (
        <p className={styles.empty} data-testid="progress-empty">
          {EMPTY_LEDGER}
        </p>
      ) : (
        <>
          {!progress.pinned ? (
            <p className={styles.stopped} data-testid="progress-unpinned">
              窗口内没有「客户端进程已启动」行：以下读数无法锚定到单次会话，可能跨多次尝试。
            </p>
          ) : null}
          <ul className={styles.list}>
            {progress.stages.map((stage) => (
              <li key={stage.key} className={stage.state === "observed" ? styles.item : `${styles.item} ${styles.absent}`}>
                <Pill text={stage.state === "observed" ? "已观测" : "未观测"} tone={stage.state === "observed" ? "ok" : "muted"} />
                <span className={styles.label}>{stage.label}</span>
                <span className={styles.time}>
                  {stage.at === null ? "—" : `${formatDateTime(stage.at)} · ${formatAge(stage.at, nowMs)}`}
                </span>
                {stage.detail ? <span className={styles.detail}>{stage.detail}</span> : null}
              </li>
            ))}
          </ul>
          <p className={styles.counts} data-testid="progress-counts">
            <span>最远到：{progress.furthest?.label ?? "无已观测阶段"}</span>
            <span>租约授予 {progress.granted} 次</span>
            <span>释放 {progress.released} 次</span>
            <span>拒止 {progress.refused} 次</span>
          </p>
          {progress.terminal ? (
            <p className={styles.stopped} data-testid="progress-terminal">
              会话已停止 · {progress.terminal.label}
              {progress.terminal.failed ? "（失败）" : "（正常离场）"} · {formatDateTime(progress.terminal.at)}
              {progress.terminal.detail ? ` · ${progress.terminal.detail}` : ""}
            </p>
          ) : (
            <p className={styles.stopped} data-testid="progress-running">
              台账里没有终态行：本会话尚未离场，也未被判为中断。
            </p>
          )}
          {progress.refusalReasons.length > 0 ? (
            <ul className={styles.gaps} data-testid="progress-refusals">
              {progress.refusalReasons.map((reason) => (
                <li key={reason}>输入被拒：{reason}</li>
              ))}
            </ul>
          ) : null}
          <ul className={styles.gaps}>
            {GAPS.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
