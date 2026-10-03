import type {
  AlertsEnvelope,
  ConfigInfo,
  ConfigSaveRequest,
  ConfigSaveResult,
  ModelTestResult,
  ServerConfigInfo, ServerSaveRequest, ServerSaveResult, ServerProbeResult,
  GoalInfo,
  IdentityInfo,
  KinSnapshot,
  RenameRequest,
  RenameResult,
  RecipeCoverageInfo,
  SessionControlInfo,
  StopRequest,
  StopResult,
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
 * `identity`/`renameIdentity`, `config`/`saveConfig` and `session`/`stopSession` are the three
 * writes the whole-project goal authorizes. The rename commits a confirmed name change while the
 * Kin is stopped; the config save persists the operator's model and goal settings; the session
 * surface reads whether a stop is possible and commits an explicit, confirmed stop. None of them
 * starts, connects, moves or injects a game input — the only control verb `stopSession` performs
 * reduces activity (it releases held inputs and ends the session through Core's own
 * `stop_session`), and start/pause/resume stay recorded as unavailable reasons rather than wired.
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
  testModel(signal?: AbortSignal): Promise<ReadResult<ModelTestResult>>;
  serverConfig(signal?: AbortSignal): Promise<ReadResult<ServerConfigInfo>>;
  saveServer(request: ServerSaveRequest, signal?: AbortSignal): Promise<ReadResult<ServerSaveResult>>;
  probeServer(revision: number, allowRemote: boolean, signal?: AbortSignal): Promise<ReadResult<ServerProbeResult>>;
  /**
   * The observed session state plus what this surface can actually do about it: whether a stop is
   * allowed, which control verbs exist, and the reason each unavailable one is absent. Like the
   * identity and config reads it hands out the per-process CSRF token (kept beside the model) and
   * changes nothing on its own.
   */
  session(signal?: AbortSignal): Promise<ReadResult<SessionControlInfo>>;
  /**
   * Commit a confirmed stop. A server-side refusal (no running session, missing explicit
   * confirmation, failed source/auth check) returns a `write_refused` failure naming the reason;
   * an accepted stop returns Core's report, whose `blocked` status and unconfirmed/unresolved
   * buckets are preserved rather than folded into a bare success.
   */
  stopSession(request: StopRequest, signal?: AbortSignal): Promise<ReadResult<StopResult>>;
  /**
   * The standing goal the operator already saved, projected by `gateway/goal_read.py`: the milestone
   * label/product/quantity/source item, and either the gross build plan the curated recipe catalog
   * implies or the single named precondition saying the product sits outside that catalog's cover.
   * This is a pure READ — setting a goal stays the config write's job — so it hands out no token the
   * UI can act on, and it never claims live progress (there is no held-count here to render).
   */
  goal(signal?: AbortSignal): Promise<ReadResult<GoalInfo>>;
  /**
   * The recipe catalog's coverage boundary, projected by `gateway/recipe_read.py`: the game version,
   * the watched/curated split, and one row per known craft — so the panel can name the catalog's
   * support limit rather than only the plan one product implies. A pure READ with no write partner, so
   * it hands out no token and the decoded model keeps `universal` at the catalog's hard-wired `false`;
   * a `true` byte is a contract mismatch, since a finite curated fallback must never read as universal.
   */
  recipe(signal?: AbortSignal): Promise<ReadResult<RecipeCoverageInfo>>;
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
