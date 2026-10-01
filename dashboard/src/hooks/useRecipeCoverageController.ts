import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { KinReadAdapter, ReadFailure, ReadResult } from "../domain/adapter";
import type { RecipeCoverageInfo } from "../domain/model";
import { POLL_INTERVAL_MS } from "./useKinReads";

/**
 * The read that backs the 配方知识 page. It is a pure GET — `gateway/recipe_read.py` hands out no
 * token and no write partner, so there is no mutation and no CSRF capture here; it only shows the
 * curated catalog's own coverage boundary. The read is on the same cadence as the other panels and
 * the shell's data-page row and this page share one query key rather than opening two polls for the
 * same document.
 */
export interface RecipeCoverageRead {
  readonly coverage: RecipeCoverageInfo | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly sourceRef: string | null;
}

export function useRecipeCoverageRead(adapter: KinReadAdapter): RecipeCoverageRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["recipe", descriptor.id],
    queryFn: ({ signal }) => adapter.recipe(signal) as Promise<ReadResult<RecipeCoverageInfo>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  return useMemo<RecipeCoverageRead>(() => {
    const data = query.data;
    return {
      coverage: data !== undefined && data.ok ? data.value : null,
      failure: data !== undefined && !data.ok ? data.failure : null,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      sourceRef: data !== undefined && data.ok ? data.sourceRef : null,
    };
  }, [query.data, query.isLoading, query.isFetching]);
}
