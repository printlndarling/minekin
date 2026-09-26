import type { ReadFailure } from "../domain/adapter";
import { ALERT_COMPONENT_LABELS, ALERT_SEVERITY_LABELS, ALERT_STATE_LABELS } from "../domain/labels";
import type { Alert } from "../domain/model";
import { formatDateTime } from "../lib/format";
import { Panel } from "../components/Panel";
import { Pill, type Tone } from "../components/Pill";
import styles from "./alerts.module.css";

export interface AlertsPanelProps {
  readonly items: readonly Alert[];
  readonly isLoading: boolean;
  readonly failure: ReadFailure | null;
}

const SEVERITY_TONE: Record<Alert["severity"], Tone> = {
  info: "muted",
  warning: "warn",
  critical: "bad",
};

export function AlertsPanel({ items, isLoading, failure }: AlertsPanelProps) {
  return (
    <Panel title="告警与健康摘要" note="告警只呈现，不在此确认或消除；确认动作属于未来的管理写接口。" testId="panel-alerts">
      {failure ? <p className={styles.empty}>读取失败（{failure.kind}）：不展示任何缓存告警。</p> : null}
      {isLoading ? <p className={styles.empty}>首次读取中…</p> : null}
      {!failure && !isLoading && items.length === 0 ? <p className={styles.empty}>当前无告警。</p> : null}
      <ul className={styles.list}>
        {items.map((alertItem) => (
          <li key={alertItem.alertId} className={styles.item}>
            <div className={styles.head}>
              <Pill text={ALERT_SEVERITY_LABELS[alertItem.severity]} tone={SEVERITY_TONE[alertItem.severity]} />
              <Pill text={ALERT_COMPONENT_LABELS[alertItem.component]} tone="muted" />
              <Pill text={ALERT_STATE_LABELS[alertItem.state]} tone={alertItem.state === "active" ? "warn" : "muted"} />
              <span className={styles.title}>{alertItem.title}</span>
            </div>
            <span className={styles.meta}>
              首次 {formatDateTime(alertItem.firstSeenAt)} · 最近 {alertItem.lastSeenAt === null ? "未知" : formatDateTime(alertItem.lastSeenAt)} ·{" "}
              {alertItem.sourceRef}
            </span>
            {alertItem.detail ? <span className={styles.detail}>{alertItem.detail}</span> : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
