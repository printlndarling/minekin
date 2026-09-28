import type { TimelineEvent } from "./model";

/**
 * The session-progress reading the panels show without inventing any of it.
 *
 * Every fact here is a ledger row the Gateway already serves on the frozen
 * timeline route: the row's `title` is Core's own event-type name and its
 * `detail` carries Core's reason/phase fields. Nothing in this module reaches
 * for a value the read model does not publish — the client-bundle preparation
 * counts in particular have no ledger row at all, so they stay named as
 * missing instead of being drawn as a progress bar.
 */

export type StageState = "observed" | "absent";

export interface SessionStage {
  readonly key: string;
  readonly label: string;
  readonly state: StageState;
  readonly at: string | null;
  readonly detail: string | null;
}

export interface SessionTerminal {
  readonly label: string;
  readonly at: string;
  readonly detail: string | null;
  readonly failed: boolean;
}

/**
 * How the release rows in the current attempt divide by whether a lease was still held.
 *
 * Reads Core's own `had_lease` through the Gateway's projection. A row whose detail carries no
 * boolean — a pre-projection ledger, or a lookalike `1` that is not a boolean — counts as
 * `unrecorded` so the panel says it is unknown rather than sorting it either way.
 */
export interface ReleaseBreakdown {
  readonly total: number;
  readonly handedBack: number;
  readonly withoutLease: number;
  readonly unrecorded: number;
}

export interface SessionProgress {
  readonly stages: readonly SessionStage[];
  readonly furthest: SessionStage | null;
  readonly terminal: SessionTerminal | null;
  readonly granted: number;
  readonly released: number;
  readonly releases: ReleaseBreakdown;
  readonly refused: number;
  readonly refusalReasons: readonly string[];
  readonly attemptStartedAt: string | null;
  readonly hasRows: boolean;
  /** False when the served window holds no launch row, so rows may span attempts. */
  readonly pinned: boolean;
}

const LAUNCH_ROW = "SessionProcessStarted";

const STAGE_SPECS: readonly { key: string; label: string; eventType: string }[] = [
  { key: "launch", label: "客户端进程已启动", eventType: LAUNCH_ROW },
  { key: "hello", label: "Bridge 握手被接受", eventType: "BridgeHelloAccepted" },
  { key: "join", label: "服务端观察到入服", eventType: "JoinObserved" },
  { key: "playable", label: "会话进入可玩", eventType: "PlayableEstablished" },
  { key: "lease", label: "输入租约已授予", eventType: "InputLeaseGranted" },
  { key: "release", label: "输入租约已释放", eventType: "InputReleased" },
  { key: "exit", label: "客户端进程已离场", eventType: "ClientProcessExited" },
];

const TERMINAL_SPECS: readonly { eventType: string; label: string; failed: boolean }[] = [
  { eventType: "SessionProcessFailed", label: "客户端启动失败", failed: true },
  { eventType: "SessionInterrupted", label: "会话被中断", failed: true },
  { eventType: "ClientProcessExited", label: "客户端已离场", failed: false },
];

/** The ledger position behind a `ledger://kin/123` reference, when it is readable. */
function positionOf(event: TimelineEvent): number {
  const match = /\/(\d+)$/.exec(event.sourceRef);
  return match === null ? Number.NEGATIVE_INFINITY : Number(match[1]);
}

function newest(events: readonly TimelineEvent[]): TimelineEvent | null {
  if (events.length === 0) return null;
  return events.reduce((best, event) => (positionOf(event) > positionOf(best) ? event : best));
}

function newestOf(attempt: readonly TimelineEvent[], eventType: string): TimelineEvent | null {
  return newest(attempt.filter((event) => event.title === eventType));
}

/**
 * The current attempt is the newest launch row and every row written after it.
 *
 * A Kin's ledger keeps previous sessions, so an older row that reached 可玩 would
 * otherwise read as progress the current session never made. A launch row that is
 * missing entirely (a failed start, or a window truncated below it) leaves the whole
 * window in scope — the honest answer being `pinned: false`, since there is no later
 * attempt to anchor to.
 */
function currentAttempt(events: readonly TimelineEvent[]): { readonly rows: readonly TimelineEvent[]; readonly pinned: boolean } {
  const launch = newestOf(events, LAUNCH_ROW);
  if (launch === null) return { rows: events, pinned: false };
  const from = positionOf(launch);
  return { rows: events.filter((event) => positionOf(event) >= from), pinned: true };
}

export function deriveSessionProgress(events: readonly TimelineEvent[]): SessionProgress {
  const { rows: attempt, pinned } = currentAttempt(events);
  const stages: SessionStage[] = STAGE_SPECS.map((spec) => {
    const row = newestOf(attempt, spec.eventType);
    return {
      key: spec.key,
      label: spec.label,
      state: row === null ? "absent" : "observed",
      at: row?.at ?? null,
      detail: row?.detail ?? null,
    };
  });
  let furthest: SessionStage | null = null;
  for (const stage of stages) if (stage.state === "observed") furthest = stage;
  const terminalRow = newest(
    attempt.filter((event) => TERMINAL_SPECS.some((spec) => spec.eventType === event.title)),
  );
  const terminalSpec = terminalRow === null ? undefined : TERMINAL_SPECS.find((spec) => spec.eventType === terminalRow.title);
  const refusals = attempt.filter((event) => event.title === "InputRefused");
  const releases = breakdownOf(attempt, "InputReleased");
  return {
    stages,
    furthest,
    terminal:
      terminalRow !== null && terminalSpec !== undefined
        ? { label: terminalSpec.label, at: terminalRow.at, detail: terminalRow.detail, failed: terminalSpec.failed }
        : null,
    granted: countOf(attempt, "InputLeaseGranted"),
    released: releases.total,
    releases,
    refused: refusals.length,
    refusalReasons: [...new Set(refusals.map((event) => event.detail ?? "reason 未记录"))].sort(),
    attemptStartedAt: newestOf(attempt, LAUNCH_ROW)?.at ?? null,
    hasRows: attempt.length > 0,
    pinned,
  };
}

function countOf(events: readonly TimelineEvent[], eventType: string): number {
  return events.filter((event) => event.title === eventType).length;
}

/** Core's own boolean as the Gateway projects it into `detail`: `had_lease=True` / `had_lease=False`. */
const HAD_LEASE: RegExp = /had_lease=(True|False)(?:,|$)/;

function breakdownOf(events: readonly TimelineEvent[], eventType: string): ReleaseBreakdown {
  const rows = events.filter((event) => event.title === eventType);
  let handedBack = 0;
  let withoutLease = 0;
  let unrecorded = 0;
  for (const row of rows) {
    const match = HAD_LEASE.exec(row.detail ?? "");
    if (match === null) unrecorded += 1;
    else if (match[1] === "True") handedBack += 1;
    else withoutLease += 1;
  }
  return { total: rows.length, handedBack, withoutLease, unrecorded };
}
