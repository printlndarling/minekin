import type { Alert, KinSnapshot, TimelineEvent, TimelineKind } from "./model";
import { gap, type DataSourceKind, type SignalContext } from "./signals";

export type ReadFailureKind =
  | "not_configured"
  | "disconnected"
  | "timeout"
  | "contract_mismatch"
  | "permission_denied"
  | "cancelled"
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
 */
export interface KinReadAdapter {
  describe(): AdapterDescriptor;
  snapshot(signal?: AbortSignal): Promise<ReadResult<KinSnapshot>>;
  timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>>;
  alerts(signal?: AbortSignal): Promise<ReadResult<readonly Alert[]>>;
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
