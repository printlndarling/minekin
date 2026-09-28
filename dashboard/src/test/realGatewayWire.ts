/**
 * The exact bytes the real `gateway/readmodel.py` `build_snapshot()` produced
 * from a joined-run fixture (key-sorted verbatim capture, 2026-09). The decoder
 * is designed against these bytes, not against a guess of the wire shape.
 */
export const REAL_JOINED_RUN_SNAPSHOT_WIRE: Record<string, unknown> = {
  bridgeHeartbeat: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/bridgeHeartbeat",
    staleAfterMs: null,
    status: "known",
    value: {
      inputLeaseHeld: { value: false },
      intervalMs: { value: 500 },
      lastObservedAt: { value: "2000-01-01T00:00:00Z" },
      lastSequence: {
        gap: {
          reason: "ControlHeartbeat 只有 generation 与 monotonic_ns；台账 position 是记账顺序，不是桥的计数器。",
          status: "not_wired",
        },
      },
    },
  },
  bridgeLink: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/bridge_link",
    staleAfterMs: 8000,
    status: "known",
    value: "disconnected",
  },
  evidence: {
    observedAt: null,
    reason: "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。",
    sourceRef: "core://status/kin-01/evidence",
    staleAfterMs: null,
    status: "unknown",
    value: null,
  },
  kinId: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/kin_id",
    staleAfterMs: 8000,
    status: "known",
    value: "kin-01",
  },
  liveView: {
    observedAt: null,
    reason: "没有 framebuffer 采集与媒体中继进程，画面这一面不存在。",
    sourceRef: "core://status/kin-01/liveView",
    staleAfterMs: null,
    status: "not_wired",
    value: null,
  },
  runtimeState: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/state",
    staleAfterMs: 8000,
    status: "known",
    value: "unresolved",
  },
  schemaVersion: "kin-dashboard-readmodel/1.0.0",
  selfState: {
    observedAt: null,
    reason: "Core 不落相干性快照行：health/food 只在会话内存里，只读投影取不到。",
    sourceRef: "core://status/kin-01/selfState",
    staleAfterMs: null,
    status: "unavailable",
    value: null,
  },
  serverLink: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/server_link",
    staleAfterMs: 8000,
    status: "known",
    value: "disconnected",
  },
  session: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/session",
    staleAfterMs: null,
    status: "known",
    value: {
      generation: { value: 1 },
      mode: {
        gap: {
          reason: "Core 尚无会话模式枚举（A_companion/B_standalone 属产品决定）。",
          status: "not_wired",
        },
      },
      overlay: { value: "D:\\\\Temp\\\\shape-fqypyrza\\\\kin\\\\kin-01\\\\run\\\\session\\\\e14d02e5f33e48ecb3b23bc6f17418d9\\\\generation-1" },
      pid: { value: 4242 },
      sessionId: { value: "e14d02e5f33e48ecb3b23bc6f17418d9" },
      startedAt: { value: "2000-01-01T00:00:00Z" },
    },
  },
  versions: {
    observedAt: null,
    reason: "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。 版本五件套没有统一读接口，只有已封 bundle 的清单能答其中三个。",
    sourceRef: "core://status/kin-01/versions",
    staleAfterMs: null,
    status: "unavailable",
    value: null,
  },
  world: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/world",
    staleAfterMs: null,
    status: "known",
    value: {
      epoch: {
        gap: { reason: "同 worldContext：世界坐标类信息的可见性未裁决。", status: "not_wired" },
      },
      joined: { value: true },
      profileId: { value: "srv-profile-00000000000000000000" },
      profileName: {
        gap: { reason: "Core 只记 profile 的 id 与 revision，没有具名显示名载体。", status: "not_wired" },
      },
      resolvedVersion: { gap: { reason: "Core 无 resolvedVersion 具名载体。", status: "not_wired" } },
      worldContext: {
        gap: {
          reason: "world_context_id 的可见性属主控/产品决定（契约 §8），只读面不替它作答。",
          status: "not_wired",
        },
      },
    },
  },
};

/** The alerts read `gateway/readmodel.py::alerts_payload` answers today (§5.3). */
export const REAL_ALERTS_ENVELOPE_WIRE: Record<string, unknown> = {
  status: "not_wired",
  reason: "Core 无告警源：只有台账事件与 run document 的拒止计数，哪些算告警属产品决定。",
  observedAt: "2000-01-01T00:00:00Z",
  sourceRef: "core://status/kin-01/alerts",
  alerts: [],
};

/** Two rows in the shape `gateway/readmodel.py::build_timeline` answers. */
export const REAL_TIMELINE_WIRE: readonly Record<string, unknown>[] = [
  {
    eventId: "evt-2",
    kind: "session",
    at: "2000-01-01T00:00:05Z",
    monotonicMs: null,
    generation: 1,
    sequence: null,
    title: "ClientProcessExited",
    detail: null,
    outcome: "unknown",
    sourceRef: "ledger://kin-01/42",
  },
  {
    eventId: "evt-1",
    kind: "session",
    at: "2000-01-01T00:00:00Z",
    monotonicMs: null,
    generation: 1,
    sequence: null,
    title: "SessionProcessStarted",
    detail: "argv_digest=abc123, phase=launch",
    outcome: "applied",
    sourceRef: "ledger://kin-01/41",
  },
];

export interface LedgerRowSpec {
  readonly title: string;
  readonly kind: string;
  readonly outcome: string;
  readonly detail?: string | null;
}

/**
 * One attempt's worth of rows in the shape `build_timeline` answers, newest first.
 *
 * The field set, the enum values and the `ledger://{kin_id}/{position}` reference are
 * the shipped ones; only the row sequence is chosen here, so a case can describe more
 * than the two-row capture above holds. `specs` is oldest first and positions ascend
 * with it, which is what the attempt pinning reads.
 */
export function gatewayLedgerWires(specs: readonly LedgerRowSpec[], firstPosition = 41): Record<string, unknown>[] {
  const origin = Date.parse("2000-01-01T00:00:00Z");
  return specs
    .map((spec, index) => {
      const position = firstPosition + index;
      return {
        eventId: `evt-${position}`,
        kind: spec.kind,
        at: new Date(origin + position * 1_000).toISOString(),
        monotonicMs: null,
        generation: 1,
        sequence: null,
        title: spec.title,
        detail: spec.detail ?? null,
        outcome: spec.outcome,
        sourceRef: `ledger://kin-01/${position}`,
      };
    })
    .reverse();
}
