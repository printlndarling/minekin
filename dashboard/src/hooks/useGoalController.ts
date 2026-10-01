import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { KinReadAdapter, ReadFailure, ReadResult } from "../domain/adapter";
import type { GoalInfo } from "../domain/model";
import { POLL_INTERVAL_MS } from "./useKinReads";

/**
 * The read that backs the 任务 page. It is a pure GET — `gateway/goal_read.py` hands out no token
 * this surface can act on and reports no live progress, so there is no mutation and no CSRF capture
 * here; a goal is submitted through the config write, and this hook only shows what that write
 * saved. The read is on the same 5 s cadence as the other panels, and the shell's data-page row and
 * the task page share one query key rather than opening two polls for the same document.
 */
export interface GoalRead {
  readonly goal: GoalInfo | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly sourceRef: string | null;
}

export function useGoalRead(adapter: KinReadAdapter): GoalRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["goal", descriptor.id],
    queryFn: ({ signal }) => adapter.goal(signal) as Promise<ReadResult<GoalInfo>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  return useMemo<GoalRead>(() => {
    const data = query.data;
    return {
      goal: data !== undefined && data.ok ? data.value : null,
      failure: data !== undefined && !data.ok ? data.failure : null,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      sourceRef: data !== undefined && data.ok ? data.sourceRef : null,
    };
  }, [query.data, query.isLoading, query.isFetching]);
}
