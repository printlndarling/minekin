import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import type { KinReadAdapter, ReadFailure, ReadResult } from "../domain/adapter";
import type { IdentityInfo, RenameRequest, RenameResult } from "../domain/model";
import { POLL_INTERVAL_MS } from "./useKinReads";

/**
 * The identity surface `docs/stable-player-name-2026-09-29.md` authorizes: it polls who a
 * Kin currently is on the same 5 s cadence as the read-only panels, and it is the ONLY
 * place the shell commits a write. That write is one confirmed rename while the Kin is
 * stopped — nothing here can start, stop, move or otherwise touch a session.
 */

/** The settled result of a rename attempt: either Core's before/after, or the refusal. */
export interface RenameOutcome {
  readonly ok: boolean;
  readonly result: RenameResult | null;
  readonly failure: ReadFailure | null;
}

export interface IdentityRead {
  readonly identity: IdentityInfo | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly sourceRef: string | null;
}

/**
 * The read alone, so the shell's always-on context strip and the identity page share one
 * query key instead of opening two polls for the same answer.
 */
export function useIdentityRead(adapter: KinReadAdapter): IdentityRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["identity", descriptor.id],
    queryFn: ({ signal }) => adapter.identity(signal) as Promise<ReadResult<IdentityInfo>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  return useMemo<IdentityRead>(() => {
    const data = query.data;
    return {
      identity: data !== undefined && data.ok ? data.value : null,
      failure: data !== undefined && !data.ok ? data.failure : null,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      sourceRef: data !== undefined && data.ok ? data.sourceRef : null,
    };
  }, [query.data, query.isLoading, query.isFetching]);
}

export interface IdentityController extends IdentityRead {
  readonly pending: boolean;
  readonly outcome: RenameOutcome | null;
  submit(request: RenameRequest): void;
  clearOutcome(): void;
}

export function useIdentityController(adapter: KinReadAdapter): IdentityController {
  const descriptor = adapter.describe();
  const queryClient = useQueryClient();
  const read = useIdentityRead(adapter);

  const mutation = useMutation({
    mutationFn: (request: RenameRequest) => adapter.renameIdentity(request),
    // A server refusal is an answer the write surface gave on purpose, not an exception, so
    // it resolves here too and the panel renders the named reason. Only an accepted rename
    // changes stored identity — refetch so the panel shows Core's new name/revision/UUID
    // rather than echoing what the form happened to type.
    onSuccess: (result: ReadResult<RenameResult>) => {
      if (result.ok) void queryClient.invalidateQueries({ queryKey: ["identity", descriptor.id] });
    },
  });

  return useMemo<IdentityController>(() => {
    const settled = mutation.data;
    return {
      ...read,
      pending: mutation.isPending,
      outcome:
        settled === undefined
          ? null
          : settled.ok
            ? { ok: true, result: settled.value, failure: null }
            : { ok: false, result: null, failure: settled.failure },
      submit: (request: RenameRequest) => mutation.mutate(request),
      clearOutcome: () => mutation.reset(),
    };
    // `mutation.mutate`/`reset` are stable references TanStack keeps across renders; naming
    // the fields actually read keeps the memo honest without re-binding on every poll.
  }, [read, mutation.data, mutation.isPending, mutation.mutate, mutation.reset, descriptor.id, queryClient]);
}
