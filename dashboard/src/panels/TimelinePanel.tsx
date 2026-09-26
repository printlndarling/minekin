import { useState } from "react";
import type { ReadFailure } from "../domain/adapter";
import { TIMELINE_KIND_LABELS, TIMELINE_KIND_ORDER, TIMELINE_OUTCOME_LABELS } from "../domain/labels";
import type { TimelineEvent, TimelineKind } from "../domain/model";
import { formatDateTime } from "../lib/format";
import { Panel } from "../components/Panel";
import { Pill } from "../components/Pill";
import styles from "./timeline.module.css";

export interface TimelinePanelProps {
  readonly items: readonly TimelineEvent[];
  readonly isLoading: boolean;
  readonly failure: ReadFailure | null;
}

function optionalNumber(value: number | null, suffix: string): string {
  return value === null ? `${suffix}未知` : `${suffix}${value}`;
}

export function TimelinePanel({ items, isLoading, failure }: TimelinePanelProps) {
  const [kinds, setKinds] = useState<readonly TimelineKind[]>([]);

  const toggle = (kind: TimelineKind): void => {
    setKinds((prev) => (prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind]));
  };

  const shown = kinds.length === 0 ? items : items.filter((event) => kinds.includes(event.kind));

  return (
    <Panel title="时间线（观察 → 决定 → 意图 → 输入 → 反馈）" note="只读事件流；缺字段显示未知，不补默认值。" testId="panel-timeline">
      <div className={styles.filters} role="group" aria-label="事件类型过滤">
        {TIMELINE_KIND_ORDER.map((kind) => (
          <button
            key={kind}
            type="button"
            className={kinds.includes(kind) ? styles.chipActive : styles.chip}
            aria-pressed={kinds.includes(kind)}
            onClick={() => toggle(kind)}
          >
            {TIMELINE_KIND_LABELS[kind]}
          </button>
        ))}
      </div>
      {failure ? <p className={styles.empty}>读取失败（{failure.kind}）：不展示任何缓存事件。</p> : null}
      {isLoading && items.length === 0 ? <p className={styles.empty}>首次读取中…</p> : null}
      {!failure && !isLoading && shown.length === 0 ? <p className={styles.empty}>当前无匹配事件。</p> : null}
      <ul className={styles.list}>
        {shown.map((event) => (
          <li key={event.eventId} className={styles.item}>
            <span className={styles.time}>{formatDateTime(event.at)}</span>
            <Pill text={TIMELINE_KIND_LABELS[event.kind]} tone="muted" />
            <span className={styles.title}>{event.title}</span>
            <Pill
              text={TIMELINE_OUTCOME_LABELS[event.outcome]}
              tone={event.outcome === "applied" ? "ok" : event.outcome === "unknown" ? "muted" : "warn"}
            />
            <span className={styles.meta}>
              {optionalNumber(event.monotonicMs, "monotonic ")} · {optionalNumber(event.generation, "gen ")} ·{" "}
              {optionalNumber(event.sequence, "seq ")} · {event.sourceRef}
            </span>
            {event.detail ? <span className={styles.detail}>{event.detail}</span> : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
