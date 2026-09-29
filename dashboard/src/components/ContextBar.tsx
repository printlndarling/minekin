import type { AlertsEnvelope, KinSnapshot } from "../domain/model";
import { fieldValue } from "../domain/model";
import { KIN_STATE_LABELS, LINK_STATE_LABELS, SIGNAL_STATUS_LABELS } from "../domain/labels";
import { freshnessOf, isKnown, type Signal } from "../domain/signals";
import type { IdentityRead } from "../hooks/useIdentityController";
import type { ReadHealth } from "../hooks/useKinReads";
import type { SessionProgress } from "../domain/sessionProgress";
import type { ReadFailure } from "../domain/adapter";
import { FAILURE_KIND_LABELS } from "../shell/readStatus";
import { formatNumber } from "../lib/format";
import styles from "./ContextBar.module.css";

export interface ContextBarProps {
  readonly snapshot: KinSnapshot;
  readonly nowMs: number;
  readonly identityRead: IdentityRead;
  readonly snapshotHealth: ReadHealth;
  readonly progress: SessionProgress;
  readonly timelineFailure: ReadFailure | null;
  readonly alertsEnvelope: AlertsEnvelope | null;
  readonly alertsFailure: ReadFailure | null;
}

type Tone = "ok" | "warn" | "bad" | "muted";

/** A card answers one of the four questions the back office exists for. */
interface Cell {
  readonly id: string;
  readonly question: string;
  readonly lines: readonly string[];
  readonly tone: Tone;
}

function gapRead(failure: ReadFailure | null, fallback: string): string {
  return failure === null ? fallback : `读取失败 · ${FAILURE_KIND_LABELS[failure.kind]}：${failure.message}`;
}

/** A gap signal says which kind of gap it is and carries Core's own reason. */
function signalText<T>(signal: Signal<T>, render: (value: T) => string): string {
  return isKnown(signal) ? render(signal.value) : `${SIGNAL_STATUS_LABELS[signal.status]}（${signal.reason}）`;
}

function fieldText<T>(field: Parameters<typeof fieldValue>[0], render: (value: T) => string, absent: string): string {
  const value = fieldValue(field);
  return value === null ? absent : render(value as T);
}

/**
 * The part that never changes page: who this Kin is, which world it stands in, how far the
 * current attempt got, and what is holding it back.
 *
 * Every line reads an existing real source — the frozen snapshot route, the identity route,
 * and ledger rows already served on the timeline. A card with nothing to show names why,
 * because an empty card would otherwise read as「一切正常」.
 */
export function ContextBar(props: ContextBarProps) {
  const { snapshot, nowMs, progress, identityRead } = props;
  const identity = identityRead.identity;

  const world = isKnown(snapshot.world) ? snapshot.world.value : null;
  const state = isKnown(snapshot.runtimeState) ? snapshot.runtimeState.value : null;
  const bridgeLink = isKnown(snapshot.bridgeLink) ? snapshot.bridgeLink.value : null;
  const serverLink = isKnown(snapshot.serverLink) ? snapshot.serverLink.value : null;
  const self = isKnown(snapshot.selfState) ? snapshot.selfState.value : null;
  const lease = isKnown(snapshot.bridgeHeartbeat) ? fieldValue(snapshot.bridgeHeartbeat.value.inputLeaseHeld) : null;
  const joined = world === null ? null : fieldValue(world.joined);

  const who: Cell = {
    id: "who",
    question: "它是谁",
    tone: identity === null ? "warn" : "ok",
    lines: [
      identity === null
        ? gapRead(identityRead.failure, identityRead.isLoading ? "身份读取中" : "这一轮没有读到身份")
        : `${identity.username} · 身份修订 ${identity.identityRevision} · 离线 UUID ${identity.uuidCanonical}`,
      `Kin ID ${signalText(snapshot.kinId, (v) => v)}`,
    ],
  };

  const where: Cell = {
    id: "where",
    question: "在哪个世界",
    tone: joined === true ? "ok" : joined === false ? "muted" : "warn",
    lines: [
      world === null
        ? signalText(snapshot.world, () => "")
        : `${fieldText(world.profileName, (v: string) => v, "名称未知")} · ${fieldText(world.worldContext, (v: string) => v, "上下文未知")}`,
      world === null
        ? ""
        : `版本 ${fieldText(world.resolvedVersion, (v: string) => v, "未知")} · epoch ${fieldText(world.epoch, (v: number) => String(v), "未知")} · ${joined === true ? "已入服" : "未入服"}`,
      freshnessOf(snapshot.kinId, nowMs) === "stale" ? "读数已陈旧：按观测时刻解释，不要当作现在。" : "",
    ].filter((line) => line !== ""),
  };

  const doing: Cell = {
    id: "doing",
    question: "正在干什么",
    tone: state === "running" ? "ok" : state === null ? "warn" : "muted",
    lines: [
      `运行态 ${state === null ? signalText(snapshot.runtimeState, (v: string) => v) : KIN_STATE_LABELS[state]}`,
      `最远阶段 ${progress.furthest?.label ?? (progress.hasRows ? "窗口内没有阶段行" : "暂无台账行")}`,
      `链路 Bridge ${bridgeLink === null ? "未知" : LINK_STATE_LABELS[bridgeLink]} · 服务器 ${serverLink === null ? "未知" : LINK_STATE_LABELS[serverLink]}`,
      `输入租约 ${lease === null ? "未知" : lease ? "持有" : "无"}${self === null ? "" : ` · 生命 ${formatNumber(self.health)} · 饥饿 ${formatNumber(self.food, 0)}`}`,
    ],
  };

  const blockers: string[] = [];
  if (props.snapshotHealth.failureStreak > 0) {
    blockers.push(`快照已连续 ${props.snapshotHealth.failureStreak} 次读取未落地。`);
  }
  if (progress.terminal !== null) {
    blockers.push(`会话收尾：${progress.terminal.label}${progress.terminal.detail === null ? "" : ` · ${progress.terminal.detail}`}`);
  }
  if (progress.refused > 0) {
    blockers.push(`输入被拒 ${progress.refused} 次：${progress.refusalReasons.join("、")}`);
  }
  if (!progress.pinned && progress.hasRows) {
    blockers.push("窗口锚不到本次会话：阶段行可能来自不同 attempt。");
  }
  if (props.timelineFailure !== null) {
    blockers.push(gapRead(props.timelineFailure, "时间线读取失败"));
  }
  if (props.alertsFailure !== null) {
    blockers.push(gapRead(props.alertsFailure, "告警读取失败"));
  } else if (props.alertsEnvelope !== null && props.alertsEnvelope.status !== "known") {
    blockers.push(`告警面无源可读：${props.alertsEnvelope.reason}`);
  } else if (props.alertsEnvelope !== null) {
    const active = props.alertsEnvelope.alerts.filter((alert) => alert.state === "active");
    if (active.length > 0) blockers.push(`活动告警 ${active.length} 条：${active.map((alert) => alert.title).join("、")}`);
  }

  const why: Cell = {
    id: "why",
    question: "为什么没运行 / 没完成",
    tone: blockers.length === 0 ? "ok" : progress.terminal?.failed === true ? "bad" : "warn",
    // 三条读路同时失败时它们的具名原因逐字相同；重复列出会把一格阻断挤成噪声。
    lines: blockers.length === 0 ? ["当前读数里没有可见的阻断。"] : [...new Set(blockers)],
  };

  return (
    <div className={styles.bar} data-testid="context-bar">
      {[who, where, doing, why].map((cell) => (
        <div key={cell.id} className={`${styles.cell} ${styles[cell.tone]}`} data-testid={`context-${cell.id}`}>
          <p className={styles.question}>{cell.question}</p>
          <ul className={styles.lines}>
            {cell.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
