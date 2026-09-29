import type { ReadFailure, ReadFailureKind } from "../domain/adapter";
import type { ReadHealth } from "../hooks/useKinReads";
import type { Tone } from "../components/Pill";
import { formatSpan } from "../lib/format";

export const FAILURE_KIND_LABELS: Record<ReadFailureKind, string> = {
  not_configured: "未配置",
  disconnected: "断连",
  timeout: "超时",
  contract_mismatch: "契约不符",
  permission_denied: "无权限",
  cancelled: "已取消",
  write_refused: "被拒绝",
  unknown: "读数异常",
};

export interface ReadLike {
  readonly isLoading: boolean;
  readonly failure: ReadFailure | null;
}

export interface ReadStatus {
  readonly tone: Tone;
  readonly text: string;
}

/**
 * One shape for “is this read channel answering”.
 *
 * The frozen contract gives the panel a poll and nothing else, so a dead channel is only
 * ever visible as reads that did not land. Each of the three ways that happens has to be
 * named apart: a read that never started, a read that just failed once, and a chain of
 * failed polls are three different operator actions.
 */
export function readStatusOf(
  read: ReadLike,
  options: { readonly nowMs: number; readonly health?: ReadHealth },
): ReadStatus {
  const { nowMs, health } = options;
  if (read.failure !== null) {
    return { tone: "bad", text: `失败 · ${FAILURE_KIND_LABELS[read.failure.kind]}` };
  }
  if (health !== undefined && health.failureStreak > 0) {
    const since =
      health.firstFailureAtMs === null ? "" : ` · ${formatSpan(nowMs - health.firstFailureAtMs)}`;
    return { tone: "bad", text: `连续 ${health.failureStreak} 次未落${since}` };
  }
  if (read.isLoading) return { tone: "muted", text: "读取中" };
  return { tone: "ok", text: "在读" };
}
