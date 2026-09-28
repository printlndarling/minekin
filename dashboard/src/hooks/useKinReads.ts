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
/**
 * A break that has already closed. The streak itself is gone with the failed reads, so
 * what survives is the two facts the operator asked for while it was deaf: how many
 * polls went unanswered, and how long the panel was deaf for.
 */
export interface ClosedOutage {
  readonly failedReads: number;
  readonly spanMs: number;
}

export interface ReadHealth {
  readonly failureStreak: number;
  /** When the streak now running began; null while nothing has failed. */
  readonly firstFailureAtMs: number | null;
  readonly lastSuccessAtMs: number | null;
  /** Breaks this panel has recovered from without being reloaded. */
  readonly recoveredCount: number;
  /** The most recent closed break; null while the page has only ever read cleanly. */
  readonly lastOutage: ClosedOutage | null;
}

/**
 * Counts settled reads, keyed on the moment the read landed rather than on the
 * result object's identity. Two consecutive failures that say exactly the same
 * thing are one fact to TanStack — structural sharing hands back the same
 * reference — so identity would freeze the streak at 1 while the polls kept
 * failing. `dataUpdatedAt` advances with every settled read, and a re-render
 * (including React's strict double-render) cannot advance it.
 *
 * A success that follows a streak closes that streak into `lastOutage` rather than
 * dropping it. Wiping the streak is correct for「连续 N 次」— the chain is over — but
 * leaving no trace at all made a page that had just gone 6 polls deaf read exactly
 * like one that had never missed a beat, so the operator could not tell a recovered
 * session from an untouched one.
 */
function useReadHealth(adapterId: string, data: ReadResult<unknown> | undefined, readAtMs: number): ReadHealth {
  const seen = useRef<{
    adapterId: string;
    readAtMs: number;
    streak: number;
    firstFailureAtMs: number | null;
    lastSuccessAtMs: number | null;
    recoveredCount: number;
    lastOutage: ClosedOutage | null;
  }>({
    adapterId,
    readAtMs: -1,
    streak: 0,
    firstFailureAtMs: null,
    lastSuccessAtMs: null,
    recoveredCount: 0,
    lastOutage: null,
  });
  if (seen.current.adapterId !== adapterId || seen.current.readAtMs !== readAtMs) {
    const previous = seen.current;
    seen.current =
      data === undefined
        ? { ...previous, adapterId, readAtMs, streak: 0, firstFailureAtMs: null }
        : data.ok
          ? previous.streak > 0
            ? {
                adapterId,
                readAtMs,
                streak: 0,
                firstFailureAtMs: null,
                lastSuccessAtMs: Date.now(),
                recoveredCount: previous.recoveredCount + 1,
                lastOutage: {
                  failedReads: previous.streak,
                  spanMs: Math.max(0, Date.now() - (previous.firstFailureAtMs ?? Date.now())),
                },
              }
            : { ...previous, adapterId, readAtMs, lastSuccessAtMs: Date.now() }
          : {
              ...previous,
              adapterId,
              readAtMs,
              streak: previous.streak + 1,
              firstFailureAtMs: previous.firstFailureAtMs ?? Date.now(),
            };
  }
  const { streak, firstFailureAtMs, lastSuccessAtMs, recoveredCount, lastOutage } = seen.current;
  return { failureStreak: streak, firstFailureAtMs, lastSuccessAtMs, recoveredCount, lastOutage };
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
