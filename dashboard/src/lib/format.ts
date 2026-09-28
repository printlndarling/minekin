import { SIGNAL_STATUS_LABELS } from "../domain/labels";
import type { Field } from "../domain/model";

export function formatDateTime(iso: string | null): string {
  if (iso === null) return "—";
  const at = Date.parse(iso);
  if (!Number.isFinite(at)) return "—";
  return new Date(at).toLocaleString("zh-CN", { hour12: false });
}

export function formatAge(observedAt: string | null, nowMs: number): string {
  if (observedAt === null) return "无时间戳";
  const at = Date.parse(observedAt);
  if (!Number.isFinite(at)) return "无时间戳";
  const seconds = Math.max(0, Math.round((nowMs - at) / 1_000));
  if (seconds < 60) return `${seconds} 秒前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function formatNumber(value: number, digits: number = 1): string {
  return value.toFixed(digits);
}

/**
 * Wall time as a span rather than a point in the past. The disconnect counter
 * needs it: "连续 N 次" says nothing about how long the panel has been deaf, and
 * `formatAge` would render the outage start as「15 秒前」, a timestamp, not a duration.
 */
export function formatSpan(elapsedMs: number): string {
  const seconds = Math.max(0, Math.floor(elapsedMs / 1_000));
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分 ${seconds % 60} 秒`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
}

/**
 * How one member of a `known` group renders: its formatted value, or the gap's
 * own status label plus Core's reason verbatim. A gap never collapses into a
 * default here either.
 */
export function fieldText<T>(field: Field<T>, format: (value: T) => string): string {
  if ("value" in field) return format(field.value);
  return `${SIGNAL_STATUS_LABELS[field.gap.status]}（${field.gap.reason}）`;
}
