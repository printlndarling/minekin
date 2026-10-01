import type {
  AlertsEnvelope,
  ConfigInfo,
  ConfigSaveRequest,
  ConfigSaveResult,
  IdentityInfo,
  KinSnapshot,
  RenameRequest,
  RenameResult,
  TimelineEvent,
  TimelineKind,
} from "./model";
import { gap, type DataSourceKind, type SignalContext } from "./signals";

export type ReadFailureKind =
  | "not_configured"
  | "disconnected"
  | "timeout"
  | "contract_mismatch"
  | "permission_denied"
  | "cancelled"
  | "write_refused"
  | "unknown";

export interface ReadFailure {
  readonly kind: ReadFailureKind;
  readonly message: string;
}

export type ReadResult<T> =
  | { readonly ok: true; readonly value: T; readonly source: DataSourceKind; readonly sourceRef: string }
  | { readonly ok: false; readonly failure: ReadFailure };

export function ok<T>(value: T, source: DataSourceKind, sourceRef: string): ReadResult<T> {
  return { ok: true, value, source, sourceRef };
}

export function fail(kind: ReadFailureKind, message: string): ReadResult<never> {
  return { ok: false, failure: { kind, message } };
}

export interface AdapterDescriptor {
  readonly id: string;
  readonly kind: DataSourceKind;
  readonly label: string;
  /** True only for scripted fixtures; the UI must never present mock data as live. */
  readonly mock: boolean;
  readonly note: string;
}

export interface TimelineQuery {
  readonly limit: number;
  readonly kinds: readonly TimelineKind[];
}

/**
 * The single seam the UI reads through. Swapping the mock for the real Gateway
 * means implementing this interface; no component fetches on its own.
 *
 * `identity` and `renameIdentity` are the one authorized exception to the read-only
 * shell (`docs/stable-player-name-2026-09-29.md`): they answer who a Kin is and commit a
 * confirmed rename while that Kin is stopped. `config` and `saveConfig` extend that exception
 * to exactly one more write — persisting the operator's model and goal settings, opened by the
 * whole-project goal's Phase D. Together these are the only two writes the shell may make; none
 * of them can start, stop, move or otherwise control a session — nothing here reaches a game
 * input or a launcher.
 */
export interface KinReadAdapter {
  describe(): AdapterDescriptor;
  snapshot(signal?: AbortSignal): Promise<ReadResult<KinSnapshot>>;
  timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>>;
  /** The §5.3 envelope, never a bare array: "no alerts" and "no alert source" are different facts. */
  alerts(signal?: AbortSignal): Promise<ReadResult<AlertsEnvelope>>;
  /** The stored identity plus whether a rename is currently allowed; changes nothing. */
  identity(signal?: AbortSignal): Promise<ReadResult<IdentityInfo>>;
  /**
   * Commit a confirmed rename. A server-side refusal (not stopped, invalid name, stale
   * revision, failed source/auth check) returns a `write_refused` failure naming the reason,
   * not an exception, so the panel can render it beside the still-current identity.
   */
  renameIdentity(request: RenameRequest, signal?: AbortSignal): Promise<ReadResult<RenameResult>>;
  /**
   * The persisted operator settings, the vocabulary the form offers, and the write token. Like
   * the identity read it hands out the per-process CSRF token (kept beside the model, never in
   * it); it changes nothing and cannot expose a key — no field of `ConfigInfo` can hold one.
   */
  config(signal?: AbortSignal): Promise<ReadResult<ConfigInfo>>;
  /**
   * Persist the whole settings document. A field omitted from the request is written as unset.
   * A refusal (unknown field, bad provider, credential-shaped value, out-of-range count) returns
   * a `write_refused` failure naming the field and reason, so the panel reports it beside the
   * document that did NOT change.
   */
  saveConfig(request: ConfigSaveRequest, signal?: AbortSignal): Promise<ReadResult<ConfigSaveResult>>;
}

/**
 * A failed read keeps every panel mounted but empty: unknown/unavailable rather
 * than a cached value that could look like a live Kin.
 */
export function unreadableSnapshot(ctx: SignalContext, reason: string): KinSnapshot {
  const blank = () => gap("unknown", reason, { ...ctx, staleAfterMs: null, observedAt: null });
  return {
    schemaVersion: "",
    kinId: blank(),
    runtimeState: blank(),
    bridgeLink: blank(),
    serverLink: blank(),
    session: blank(),
    world: blank(),
    skillSteps: blank(),
    versions: blank(),
    bridgeHeartbeat: blank(),
    selfState: blank(),
    evidence: blank(),
    liveView: gap("not_wired", "媒体通道未接入：没有 framebuffer 采集与媒体中继进程。", {
      ...ctx,
      observedAt: null,
      staleAfterMs: null,
    }),
  };
}
