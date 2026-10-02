import { useState } from "react";
import type { ReadFailure } from "../domain/adapter";
import {
  ALERT_COMPONENT_LABELS,
  ALERT_SEVERITY_LABELS,
  ALERT_STATE_LABELS,
  SIGNAL_STATUS_LABELS,
} from "../domain/labels";
import type { AlertsEnvelope, Alert } from "../domain/model";
import { formatDateTime } from "../lib/format";
import { Panel } from "../components/Panel";
import { Pill, type Tone } from "../components/Pill";
import styles from "./alerts.module.css";

export interface AlertsPanelProps {
  readonly envelope: AlertsEnvelope | null;
  readonly isLoading: boolean;
  readonly failure: ReadFailure | null;
}

const SEVERITY_TONE: Record<Alert["severity"], Tone> = {
  info: "muted",
  warning: "warn",
  critical: "bad",
};

function itemsOf(envelope: AlertsEnvelope | null): readonly Alert[] {
  return envelope === null ? [] : envelope.alerts;
}

/**
 * Three facts, three renderings (§5.3): real alerts listed; a source that
 * answered with nothing (「没有告警」); or no alert source at all
 * （「无告警源」 + the reason）. The last two are separate DOM branches — an
 * empty list from a live source must never look like the absence of a source.
 */
export function AlertsPanel({ envelope, isLoading, failure }: AlertsPanelProps) {
  const [severity, setSeverity] = useState<Alert["severity"] | "all">("all");
  const [state, setState] = useState<Alert["state"] | "all">("all");
  const items = itemsOf(envelope);
  const hasSource = envelope !== null && envelope.status === "known";
  const readable = !failure && !isLoading && hasSource;
  const shown = readable ? items.filter((item) =>
    (severity === "all" || item.severity === severity) && (state === "all" || item.state === state)) : [];
  return (
    <Panel title="告警与健康摘要" note="告警只呈现，不在此确认或消除；确认动作属于未来的管理写接口。" testId="panel-alerts">
      {readable && items.length > 0 ? <>
        <div className={styles.filters}>
          <label>严重程度
            <select value={severity} onChange={(event) => setSeverity(event.target.value as Alert["severity"] | "all")}>
              <option value="all">全部级别</option>
              {Object.entries(ALERT_SEVERITY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>告警状态
            <select value={state} onChange={(event) => setState(event.target.value as Alert["state"] | "all")}>
              <option value="all">全部状态</option>
              {Object.entries(ALERT_STATE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <button type="button" disabled={severity === "all" && state === "all"}
            onClick={() => { setSeverity("all"); setState("all"); }}>清除筛选</button>
        </div>
        <p className={styles.empty} role="status">显示 {shown.length} / {items.length} 条已加载告警</p>
        {shown.length === 0 ? <p className={styles.empty}>当前筛选无匹配告警，不代表没有告警。</p> : null}
      </> : null}
      {failure ? <p className={styles.empty}>读取失败（{failure.kind}）：不展示任何缓存告警。</p> : null}
      {isLoading ? <p className={styles.empty}>首次读取中…</p> : null}
      {!failure && !isLoading && envelope === null ? (
        <p className={styles.empty} data-testid="alerts-no-source">
          无告警源：尚未读到告警信封。
        </p>
      ) : null}
      {!failure && !isLoading && envelope !== null && hasSource && items.length === 0 ? (
        <p className={styles.empty} data-testid="alerts-empty">
          没有告警：告警源已读到，当前清单为空。
        </p>
      ) : null}
      {!failure && !isLoading && envelope !== null && !hasSource ? (
        <p className={styles.noSource} data-testid="alerts-no-source">
          无告警源（{SIGNAL_STATUS_LABELS[envelope.status]}）：{envelope.reason}
        </p>
      ) : null}
      <ul className={styles.list}>
        {shown.map((alertItem) => (
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
