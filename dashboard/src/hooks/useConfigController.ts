import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import type { KinReadAdapter, ReadFailure, ReadResult } from "../domain/adapter";
import type { ConfigInfo, ConfigSaveRequest, ConfigSaveResult } from "../domain/model";
import { POLL_INTERVAL_MS } from "./useKinReads";

/**
 * The second authorized write on the Dashboard surface: the operator's model and goal settings.
 * `gateway/config_write.py` persists them through `operator_config`, whose contract is atomic,
 * validated and secret-free, which is what makes exposing it through a panel safe. Like the
 * identity rename, nothing here can start, stop, move or otherwise touch a session — it only
 * reads the saved document on the same 5 s cadence as the read-only panels and commits a whole
 * document save when the operator presses 保存.
 */

/** The settled result of a save attempt: either the now-saved document, or the refusal. */
export interface ConfigSaveOutcome {
  readonly ok: boolean;
  readonly result: ConfigSaveResult | null;
  readonly failure: ReadFailure | null;
}

export interface ConfigRead {
  readonly config: ConfigInfo | null;
  readonly failure: ReadFailure | null;
  readonly isLoading: boolean;
  readonly isFetching: boolean;
  readonly sourceRef: string | null;
}

/**
 * The read alone, so the shell's data-page rows and the config page share one query key instead
 * of opening two polls for the same answer.
 */
export function useConfigRead(adapter: KinReadAdapter): ConfigRead {
  const descriptor = adapter.describe();
  const query = useQuery({
    queryKey: ["config", descriptor.id],
    queryFn: ({ signal }) => adapter.config(signal) as Promise<ReadResult<ConfigInfo>>,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });

  return useMemo<ConfigRead>(() => {
    const data = query.data;
    return {
      config: data !== undefined && data.ok ? data.value : null,
      failure: data !== undefined && !data.ok ? data.failure : null,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      sourceRef: data !== undefined && data.ok ? data.sourceRef : null,
    };
  }, [query.data, query.isLoading, query.isFetching]);
}

export interface ConfigController extends ConfigRead {
  readonly pending: boolean;
  readonly outcome: ConfigSaveOutcome | null;
  submit(request: ConfigSaveRequest): void;
  clearOutcome(): void;
}

export function useConfigController(adapter: KinReadAdapter): ConfigController {
  const descriptor = adapter.describe();
  const queryClient = useQueryClient();
  const read = useConfigRead(adapter);

  const mutation = useMutation({
    mutationFn: (request: ConfigSaveRequest) => adapter.saveConfig(request),
    // A server refusal is an answer the write surface gave on purpose, not an exception, so it
    // resolves here too and the panel renders the named reason beside the unchanged document. Only
    // an accepted save changes the persisted fields — refetch so the panel shows what Core saved
    // rather than echoing what the form happened to type.
    onSuccess: (result: ReadResult<ConfigSaveResult>) => {
      if (result.ok) void queryClient.invalidateQueries({ queryKey: ["config", descriptor.id] });
    },
  });

  return useMemo<ConfigController>(() => {
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
      submit: (request: ConfigSaveRequest) => mutation.mutate(request),
      clearOutcome: () => mutation.reset(),
    };
    // `mutation.mutate`/`reset` are stable references TanStack keeps across renders; naming the
    // fields actually read keeps the memo honest without re-binding on every poll.
  }, [read, mutation.data, mutation.isPending, mutation.mutate, mutation.reset, descriptor.id, queryClient]);
}
