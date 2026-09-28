import type { Signal, SignalStatus } from "./signals";

/**
 * The frozen read model of `docs/gateway-dashboard-readonly-contract-2026-09-28.md`.
 * The Gateway server and this frontend must answer/consume this exact literal;
 * any other version is a `contract_mismatch`, not a fallback (§2.3).
 */
export const SNAPSHOT_SCHEMA_VERSION = "kin-dashboard-readmodel/1.0.0";

/**
 * Only the three values Core's `ObservedState` carries. `paused` and `recovering`
 * were dropped by the contract census (§3): nothing produces them, so the union
 * must not let a UI show them.
 */
export type KinRuntimeState = "idle" | "running" | "unresolved";

export type LinkState = "connected" | "connecting" | "disconnected";

export type SessionMode = "A_companion" | "B_standalone";

/**
 * One member inside a `known` group. The group has a carrier, but each member
 * either carries a value or travels as a named gap (§3: C-tier fields have no
 * producer in Core and must render as such, never as a defaulted value).
 */
export type FieldGapStatus = "unknown" | "unavailable" | "not_wired";

export interface FieldGap {
  readonly status: FieldGapStatus;
  readonly reason: string;
}

export type Field<T> = { readonly value: T } | { readonly gap: FieldGap };

export function filled<T>(value: T): Field<T> {
  return { value };
}

export function gapField<T>(status: FieldGapStatus, reason: string): Field<T> {
  return { gap: { status, reason } };
}

/** The value of a filled member, or null when it is a gap — never a default. */
export function fieldValue<T>(field: Field<T>): T | null {
  return "value" in field ? field.value : null;
}

export function fieldGap<T>(field: Field<T>): FieldGap | null {
  return "value" in field ? null : field.gap;
}

export interface SessionInfo {
  readonly sessionId: Field<string>;
  readonly generation: Field<number>;
  readonly startedAt: Field<string>;
  readonly pid: Field<number>;
  readonly overlay: Field<string>;
  readonly mode: Field<SessionMode>;
}

export interface WorldInfo {
  readonly profileId: Field<string>;
  readonly profileName: Field<string>;
  readonly worldContext: Field<string>;
  readonly epoch: Field<number>;
  readonly joined: Field<boolean>;
  readonly resolvedVersion: Field<string>;
}

export interface VersionSet {
  readonly runtime: Field<string>;
  readonly bridge: Field<string>;
  readonly clientBundle: Field<string>;
  readonly java: Field<string>;
  readonly fabricLoader: Field<string>;
}

export interface Heartbeat {
  readonly lastSequence: Field<number>;
  readonly lastObservedAt: Field<string>;
  readonly intervalMs: Field<number>;
  readonly inputLeaseHeld: Field<boolean>;
}

/**
 * `dimension` and `guiOpen` were removed: the contract census (§3) found no
 * carrier for either, and this group is a whole-group gap in practice.
 * health/food do have a carrier (`SelfStateValue`), so they stay as plain
 * numbers inside the group value.
 */
export interface SelfState {
  readonly health: number;
  readonly food: number;
}

export interface EvidenceRef {
  readonly runId: Field<string>;
  readonly attempt: Field<number>;
  readonly bundleDigest: Field<string>;
  readonly sealedAt: Field<string>;
}

export interface MediaStreamRef {
  readonly available: boolean;
  readonly transport: "webrtc" | "hls" | "mjpeg";
  readonly url: string;
  readonly startedAt: string;
}

export interface KinSnapshot {
  readonly schemaVersion: string;
  readonly kinId: Signal<string>;
  readonly runtimeState: Signal<KinRuntimeState>;
  readonly bridgeLink: Signal<LinkState>;
  readonly serverLink: Signal<LinkState>;
  readonly session: Signal<SessionInfo>;
  readonly world: Signal<WorldInfo>;
  readonly versions: Signal<VersionSet>;
  readonly bridgeHeartbeat: Signal<Heartbeat>;
  readonly selfState: Signal<SelfState>;
  readonly evidence: Signal<EvidenceRef>;
  readonly liveView: Signal<MediaStreamRef>;
}

export type TimelineKind =
  | "observation"
  | "decision"
  | "intent"
  | "input"
  | "server_feedback"
  | "reflex"
  | "fault"
  | "session";

export type TimelineOutcome = "applied" | "rejected" | "expired" | "released" | "unknown";

export interface TimelineEvent {
  readonly eventId: string;
  readonly kind: TimelineKind;
  readonly at: string;
  readonly monotonicMs: number | null;
  readonly generation: number | null;
  readonly sequence: number | null;
  readonly title: string;
  readonly detail: string | null;
  readonly outcome: TimelineOutcome;
  readonly sourceRef: string;
}

export type AlertSeverity = "info" | "warning" | "critical";

export type AlertState = "active" | "resolved" | "acknowledged";

export type AlertComponent = "runtime" | "bridge" | "launcher" | "gateway" | "media" | "database";

export interface Alert {
  readonly alertId: string;
  readonly severity: AlertSeverity;
  readonly state: AlertState;
  readonly component: AlertComponent;
  readonly title: string;
  readonly detail: string | null;
  readonly firstSeenAt: string;
  readonly lastSeenAt: string | null;
  readonly sourceRef: string;
}

/**
 * The alerts envelope frozen by §5.3 (`ALERT_SOURCE_AMBIGUITY`): a bare empty
 * array would read as "nothing is wrong" when the truth is "nothing decides
 * what wrong would be". `reason` must be non-empty whenever the status is not
 * `known`; `known` with zero alerts means 「没有告警」, any other status with
 * zero alerts means 「无告警源」— two different UI facts.
 */
export interface AlertsEnvelope {
  readonly status: SignalStatus;
  /** "" only when `status === "known"`; every gap carries Core's own reason. */
  readonly reason: string;
  readonly alerts: readonly Alert[];
}
