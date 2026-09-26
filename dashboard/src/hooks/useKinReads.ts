import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { unreadableSnapshot, type KinReadAdapter, type ReadFailure, type ReadResult } from "../domain/adapter";
import type { Alert, KinSnapshot, TimelineEvent, TimelineKind } from "../domain/model";
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
}

/**
 * Server state goes through TanStack Query. A failed read is data, not an
 * exception: the panels stay mounted and every field renders as unknown.
 */
export function useSnapshot(adapter: KinReadAdapter): SnapshotRead {
  const query = useQuery({
    queryKey: ["snapshot", adapter.describe().id],
    queryFn: ({ signal }) => adapter.snapshot(signal) as Promise<ReadResult<KinSnapshot>>,
    refetchInterval: POLL_INTERVAL_MS,
    staleTime: POLL_INTERVAL_MS - 500,
    refetchOnWindowFocus: false,
  });

  return useMemo<SnapshotRead>(() => {
    const data = query.data;
    if (data !== undefined && data.ok) {
      return { snapshot: data.value, failure: null, isLoading: false, isFetching: query.isFetching };
    }
    const failure = data !== undefined && !data.ok ? data.failure : null;
    return {
      snapshot: unreadableSnapshot(gapCtx(adapter, failure ?? { kind: "unknown", message: "" }), failure?.message ?? "尚未完成首次读取。"),
      failure,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
    };
  }, [adapter, query.data, query.isLoading, query.isFetching]);
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

export function useAlerts(adapter: KinReadAdapter): ListRead<Alert> {
  const query = useQuery({
    queryKey: ["alerts", adapter.describe().id],
    queryFn: ({ signal }) => adapter.alerts(signal) as Promise<ReadResult<readonly Alert[]>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });
  return useMemo<ListRead<Alert>>(() => {
    const data = query.data;
    if (data === undefined) return { items: [], failure: null, isLoading: query.isLoading };
    return data.ok
      ? { items: data.value, failure: null, isLoading: false }
      : { items: [], failure: data.failure, isLoading: false };
  }, [query.data, query.isLoading]);
}
