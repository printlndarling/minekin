import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { unreadableSnapshot, type KinReadAdapter, type ReadFailure, type ReadResult } from "../domain/adapter";
import type { AlertsEnvelope, KinSnapshot, TimelineEvent, TimelineKind } from "../domain/model";
import { ctxForFailure } from "./readContext";

export const POLL_INTERVAL_MS = 5_000;

function gapCtx(adapter: KinReadAdapter, failure: ReadFailure) {
  return ctxForFailure(adapter.describe().kind, adapter.describe().id, failure);
}

export interface SnapshotRead {
  readonly snapshot: KinSnapshot;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly health: ReadHealth;
}

/**
 * Consecutive failed polls and the last time a read actually landed. The
 * contract is poll-only, so "断连" is not an event pushed at us — it is a streak
 * of failed reads, and the honest reading of a streak is the count plus the
 * moment the chain broke.
 */
export interface ReadHealth {
  readonly failureStreak: number;
  /** When the streak now running began; null while nothing has failed. */
  readonly firstFailureAtMs: number | null;
  readonly lastSuccessAtMs: number | null;
}

/**
 * Counts settled reads, keyed on the moment the read landed rather than on the
 * result object's identity. Two consecutive failures that say exactly the same
 * thing are one fact to TanStack — structural sharing hands back the same
 * reference — so identity would freeze the streak at 1 while the polls kept
 * failing. `dataUpdatedAt` advances with every settled read, and a re-render
 * (including React's strict double-render) cannot advance it.
 */
function useReadHealth(adapterId: string, data: ReadResult<unknown> | undefined, readAtMs: number): ReadHealth {
  const seen = useRef<{
    adapterId: string;
    readAtMs: number;
    streak: number;
    firstFailureAtMs: number | null;
    lastSuccessAtMs: number | null;
  }>({ adapterId, readAtMs: -1, streak: 0, firstFailureAtMs: null, lastSuccessAtMs: null });
  if (seen.current.adapterId !== adapterId || seen.current.readAtMs !== readAtMs) {
    seen.current =
      data === undefined
        ? { adapterId, readAtMs, streak: 0, firstFailureAtMs: null, lastSuccessAtMs: null }
        : data.ok
          ? { adapterId, readAtMs, streak: 0, firstFailureAtMs: null, lastSuccessAtMs: Date.now() }
          : {
              adapterId,
              readAtMs,
              streak: seen.current.streak + 1,
              firstFailureAtMs: seen.current.firstFailureAtMs ?? Date.now(),
              lastSuccessAtMs: seen.current.lastSuccessAtMs,
            };
  }
  const { streak, firstFailureAtMs, lastSuccessAtMs } = seen.current;
  return { failureStreak: streak, firstFailureAtMs, lastSuccessAtMs };
}

/**
 * Server state goes through TanStack Query. A failed read is data, not an
 * exception: the panels stay mounted and every field renders as unknown.
 */
export function useSnapshot(adapter: KinReadAdapter): SnapshotRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["snapshot", descriptor.id],
    queryFn: ({ signal }) => adapter.snapshot(signal) as Promise<ReadResult<KinSnapshot>>,
    refetchInterval: POLL_INTERVAL_MS,
    staleTime: POLL_INTERVAL_MS - 500,
    refetchOnWindowFocus: false,
  });
  const health = useReadHealth(descriptor.id, query.data, query.dataUpdatedAt);

  return useMemo<SnapshotRead>(() => {
    const data = query.data;
    if (data !== undefined && data.ok) {
      return { snapshot: data.value, failure: null, isLoading: false, isFetching: query.isFetching, health };
    }
    const failure = data !== undefined && !data.ok ? data.failure : null;
    return {
      snapshot: unreadableSnapshot(gapCtx(adapter, failure ?? { kind: "unknown", message: "" }), failure?.message ?? "尚未完成首次读取。"),
      failure,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      health,
    };
  }, [adapter, query.data, query.isLoading, query.isFetching, health]);
}

export interface ListRead<T> {
  readonly items: readonly T[];
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
}

export function useTimeline(adapter: KinReadAdapter, kinds: readonly TimelineKind[], limit: number): ListRead<TimelineEvent> {
  const query = useQuery({
    queryKey: ["timeline", adapter.describe().id, kinds.join(","), limit],
    queryFn: ({ signal }) => adapter.timeline({ limit, kinds }, signal) as Promise<ReadResult<readonly TimelineEvent[]>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });
  return useMemo<ListRead<TimelineEvent>>(() => {
    const data = query.data;
    if (data === undefined) return { items: [], failure: null, isLoading: query.isLoading };
    return data.ok
      ? { items: data.value, failure: null, isLoading: false }
      : { items: [], failure: data.failure, isLoading: false };
  }, [query.data, query.isLoading]);
}

/**
 * The §5.3 envelope goes to the panel whole: "known with zero alerts" and
 * "no alert source" are different facts and must stay distinguishable.
 */
export interface AlertsRead {
  readonly envelope: AlertsEnvelope | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
}

export function useAlerts(adapter: KinReadAdapter): AlertsRead {
  const query = useQuery({
    queryKey: ["alerts", adapter.describe().id],
    queryFn: ({ signal }) => adapter.alerts(signal) as Promise<ReadResult<AlertsEnvelope>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });
  return useMemo<AlertsRead>(() => {
    const data = query.data;
    if (data === undefined) return { envelope: null, failure: null, isLoading: query.isLoading };
    return data.ok
      ? { envelope: data.value, failure: null, isLoading: false }
      : { envelope: null, failure: data.failure, isLoading: false };
  }, [query.data, query.isLoading]);
}
