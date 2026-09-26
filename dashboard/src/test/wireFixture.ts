import type { KinSnapshot } from "../domain/model";
import type { Signal } from "../domain/signals";

/** Encodes a snapshot into the wire shape the gateway adapter expects. */
export function wireSignal<T>(signal: Signal<T>): Record<string, unknown> {
  const base: Record<string, unknown> = {
    status: signal.status,
    value: signal.value,
    sourceRef: signal.sourceRef,
    observedAt: signal.observedAt,
    staleAfterMs: signal.staleAfterMs,
  };
  if (signal.status !== "known") {
    base.reason = signal.reason;
  }
  return base;
}

export function wireSnapshot(snapshot: KinSnapshot): Record<string, unknown> {
  return {
    schemaVersion: snapshot.schemaVersion,
    kinId: wireSignal(snapshot.kinId),
    runtimeState: wireSignal(snapshot.runtimeState),
    bridgeLink: wireSignal(snapshot.bridgeLink),
    serverLink: wireSignal(snapshot.serverLink),
    session: wireSignal(snapshot.session),
    world: wireSignal(snapshot.world),
    versions: wireSignal(snapshot.versions),
    bridgeHeartbeat: wireSignal(snapshot.bridgeHeartbeat),
    selfState: wireSignal(snapshot.selfState),
    evidence: wireSignal(snapshot.evidence),
    liveView: wireSignal(snapshot.liveView),
  };
}
