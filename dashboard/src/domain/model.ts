import type { Signal } from "./signals";

/**
 * Candidate read model for the future Kin Gateway dashboard API. P0 Core exposes
 * none of this over HTTP yet, so the version is marked as a proposal and every
 * field is a Signal rather than a bare value.
 */
export const SNAPSHOT_SCHEMA_VERSION = "kin-dashboard-readmodel/0.1.0-proposal";

export type KinRuntimeState = "idle" | "running" | "paused" | "recovering" | "unresolved";

export type LinkState = "connected" | "connecting" | "disconnected";

export type SessionMode = "A_companion" | "B_standalone";

export interface SessionInfo {
  readonly sessionId: string;
  readonly generation: number;
  readonly mode: SessionMode;
  readonly startedAt: string;
}

export interface WorldInfo {
  readonly profileId: string;
  readonly profileName: string;
  readonly worldContext: string;
  readonly epoch: number;
  readonly joined: boolean;
  readonly resolvedVersion: string;
}

export interface VersionSet {
  readonly runtime: string;
  readonly bridge: string;
  readonly clientBundle: string;
  readonly java: string;
  readonly fabricLoader: string;
}

export interface Heartbeat {
  readonly lastSequence: number;
  readonly lastObservedAt: string;
  readonly intervalMs: number;
  /** Bridge-side lease state; only present when the source actually reports it. */
  readonly inputLeaseHeld: boolean;
}

export interface SelfState {
  readonly health: number;
  readonly food: number;
  readonly dimension: string;
  readonly guiOpen: boolean;
}

export interface EvidenceRef {
  readonly runId: string;
  readonly attempt: string;
  readonly bundleDigest: string;
  readonly sealedAt: string;
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
