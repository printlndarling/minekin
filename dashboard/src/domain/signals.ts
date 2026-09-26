/**
 * Read-model signal: every dashboard field carries its own provenance so that
 * "not observed" can never render as a plausible value.
 */

export type DataSourceKind = "mock" | "gateway" | "none";

export type SignalStatus = "known" | "unknown" | "unavailable" | "not_wired" | "permission_denied";

export interface SignalContext {
  readonly source: DataSourceKind;
  /** Where this reading came from, e.g. "mock://scenario/healthy-run-07". */
  readonly sourceRef: string;
  /** Wall clock of the underlying observation; null when nothing observed it. */
  readonly observedAt: string | null;
  /** Age after which the reading must be shown as stale; null when undefined by source. */
  readonly staleAfterMs: number | null;
}

export interface KnownSignal<T> extends SignalContext {
  readonly status: "known";
  readonly value: T;
}

export interface GapSignal extends SignalContext {
  readonly status: Exclude<SignalStatus, "known">;
  readonly value: null;
  readonly reason: string;
}

export type Signal<T> = KnownSignal<T> | GapSignal;

export function known<T>(value: T, ctx: SignalContext): Signal<T> {
  return { ...ctx, status: "known", value };
}

export function gap(status: GapSignal["status"], reason: string, ctx: SignalContext): Signal<never> {
  return { ...ctx, status, value: null, reason };
}

export function isKnown<T>(signal: Signal<T>): signal is KnownSignal<T> {
  return signal.status === "known";
}

export type Freshness = "fresh" | "stale" | "no_observation_time" | "not_applicable";

export function freshnessOf(signal: Signal<unknown>, nowMs: number): Freshness {
  if (!isKnown(signal)) return "not_applicable";
  if (signal.observedAt === null || signal.staleAfterMs === null) return "no_observation_time";
  const at = Date.parse(signal.observedAt);
  if (!Number.isFinite(at)) return "no_observation_time";
  return nowMs - at > signal.staleAfterMs ? "stale" : "fresh";
}

/** Age of an ISO timestamp against a caller-supplied clock; null when unparsable. */
export function ageMs(observedAt: string | null, nowMs: number): number | null {
  if (observedAt === null) return null;
  const at = Date.parse(observedAt);
  if (!Number.isFinite(at)) return null;
  return Math.max(0, nowMs - at);
}
