import type { DataSourceKind } from "../domain/signals";
import type { ReadFailure } from "../domain/adapter";

/** Provenance for readings that never arrived: no observation time, no staleness budget. */
export function ctxForFailure(source: DataSourceKind, sourceRef: string, failure: ReadFailure) {
  return {
    source,
    sourceRef: `${sourceRef}#read_failed/${failure.kind}`,
    observedAt: null,
    staleAfterMs: null,
    reason: failure.message === "" ? failure.kind : failure.message,
  };
}
