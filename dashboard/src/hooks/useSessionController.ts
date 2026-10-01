import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import type { KinReadAdapter, ReadFailure, ReadResult } from "../domain/adapter";
import type { SessionControlInfo, StopRequest, StopResult } from "../domain/model";
import { POLL_INTERVAL_MS } from "./useKinReads";

/**
 * The third authorized write on the Dashboard surface: a confirmed stop of the Kin's recorded
 * clients. `gateway/session_control.py` answers the read with the observed state plus the ONE verb
 * this process can perform safely today — stop, which releases held inputs before terminating a
 * client it can prove is its own. start/pause/resume come back as named `unavailableControls`, and
 * this hook never pretends otherwise: it can end a session, nothing here can begin or steer one.
 *
 * The read is on the same 5 s cadence as the read-only panels. A stop is only submitted after the
 * session read handed out the CSRF token, and `stopAllowed` mirrors the exact predicate the server
 * enforces, so the button enables for the same reason Core would act rather than a poll that raced
 * a launch.
 */

/** The settled result of a stop attempt: either Core's report, or the refusal. */
export interface StopOutcome {
  readonly ok: boolean;
  readonly result: StopResult | null;
  readonly failure: ReadFailure | null;
}

export interface SessionRead {
  readonly session: SessionControlInfo | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly sourceRef: string | null;
}

/**
 * The read alone, so the shell's data-page row and the session page share one query key instead of
 * opening two polls for the same answer.
 */
export function useSessionRead(adapter: KinReadAdapter): SessionRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["session", descriptor.id],
    queryFn: ({ signal }) => adapter.session(signal) as Promise<ReadResult<SessionControlInfo>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  return useMemo<SessionRead>(() => {
    const data = query.data;
    return {
      session: data !== undefined && data.ok ? data.value : null,
      failure: data !== undefined && !data.ok ? data.failure : null,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      sourceRef: data !== undefined && data.ok ? data.sourceRef : null,
    };
  }, [query.data, query.isLoading, query.isFetching]);
}

export interface SessionController extends SessionRead {
  readonly pending: boolean;
  readonly outcome: StopOutcome | null;
  submit(request: StopRequest): void;
  clearOutcome(): void;
}

export function useSessionController(adapter: KinReadAdapter): SessionController {
  const descriptor = adapter.describe();
  const queryClient = useQueryClient();
  const read = useSessionRead(adapter);

  const mutation = useMutation({
    mutationFn: (request: StopRequest) => adapter.stopSession(request),
    // A server refusal (idle Kin, missing confirm, skipped CSRF read) is an answer the write
    // surface gave on purpose, not an exception, so it resolves here too and the panel renders the
    // named reason. Only an accepted stop changes the session — refetch so the panel shows the state
    // Core landed in rather than what the read happened to show before the button was pressed.
    onSuccess: (result: ReadResult<StopResult>) => {
      if (result.ok) void queryClient.invalidateQueries({ queryKey: ["session", descriptor.id] });
    },
  });

  return useMemo<SessionController>(() => {
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
      submit: (request: StopRequest) => mutation.mutate(request),
      clearOutcome: () => mutation.reset(),
    };
    // `mutation.mutate`/`reset` are stable references TanStack keeps across renders; naming the
    // fields actually read keeps the memo honest without re-binding on every poll.
  }, [read, mutation.data, mutation.isPending, mutation.mutate, mutation.reset, descriptor.id, queryClient]);
}
