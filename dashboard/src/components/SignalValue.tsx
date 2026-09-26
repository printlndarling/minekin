import { FRESHNESS_LABELS, SIGNAL_STATUS_LABELS } from "../domain/labels";
import { formatAge } from "../lib/format";
import { ageMs, freshnessOf, isKnown, type Signal } from "../domain/signals";
import { Pill, type Tone } from "./Pill";
import styles from "./ui.module.css";

export interface SignalValueProps<T> {
  readonly label: string;
  readonly signal: Signal<T>;
  readonly nowMs: number;
  readonly format: (value: T) => string;
  readonly showSource?: boolean;
}

/**
 * The one place that decides how a reading looks. A gap never renders as a
 * value: it renders its status label plus the reason the source gave.
 */
export function SignalValue<T>({ label, signal, nowMs, format, showSource = false }: SignalValueProps<T>) {
  const freshness = freshnessOf(signal, nowMs);
  const observed = isKnown(signal);
  const tone: Tone = observed
    ? freshness === "stale"
      ? "warn"
      : freshness === "fresh"
        ? "ok"
        : "muted"
    : signal.status === "permission_denied" || signal.status === "unavailable"
      ? "bad"
      : "muted";
  const statusText = observed ? FRESHNESS_LABELS[freshness] : SIGNAL_STATUS_LABELS[signal.status];
  const age = observed ? ageMs(signal.observedAt, nowMs) : null;

  return (
    <div className={styles.row}>
      <span className={styles.rowLabel}>{label}</span>
      <span className={observed ? styles.rowValue : `${styles.rowValue} ${styles.rowValueUnknown}`}>
        {observed ? format(signal.value) : statusText}
      </span>
      <span className={styles.rowAside}>
        <Pill text={statusText} tone={tone} title={`${label}：${statusText}`} />
        {observed && age !== null ? <Pill text={formatAge(signal.observedAt, nowMs)} tone="muted" /> : null}
      </span>
      {observed ? null : <span className={styles.rowReason}>{signal.reason}</span>}
      {showSource ? <span className={styles.rowMeta}>{signal.sourceRef}</span> : null}
    </div>
  );
}
