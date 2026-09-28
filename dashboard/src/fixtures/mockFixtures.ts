import type { AlertSeverity, AlertState, AlertComponent } from "../domain/model";

/**
 * Scripted, clearly-labelled fixtures in the EXACT wire shape the Gateway answers
 * (envelopes plus the two-level `{value}` / `{gap}` group members of
 * `docs/gateway-dashboard-readonly-contract-2026-09-28.md`). The mock adapter
 * decodes them through the same decoder path as gateway bytes, so the two
 * adapters cannot drift, and nothing here is measured from Core, the Bridge or
 * a server: every envelope carries `mock://scenario/…` provenance.
 */
export type MockScenarioId =
  | "healthy_run_07"
  | "stale_observations"
  | "bridge_disconnected"
  | "fields_unknown"
  | "permission_restricted"
  | "read_failed";

export interface MockScenarioMeta {
  readonly id: MockScenarioId;
  readonly label: string;
  readonly note: string;
}

export const MOCK_SCENARIOS: readonly MockScenarioMeta[] = [
  { id: "healthy_run_07", label: "正常在线", note: "所有只读字段新鲜，媒体与无载体字段仍显示缺口。" },
  { id: "stale_observations", label: "读数陈旧", note: "观测时间在 staleness 窗口之外：状态保留但标注陈旧；告警源为空。" },
  { id: "bridge_disconnected", label: "Bridge 失联", note: "runtime_state 未定，心跳不可用，不虚构世界状态。" },
  { id: "fields_unknown", label: "字段无真源", note: "只读投影取不到的组显示未知；告警走「无告警源」信封。" },
  { id: "permission_restricted", label: "无权限", note: "服务器 profile 与证据引用需要脱敏视图，当前拒绝显示。" },
  { id: "read_failed", label: "读取失败（Gateway 不可达）", note: "整次读取失败：面板保持挂载并全部标注未知。" },
];

export function isMockScenarioId(value: string): value is MockScenarioId {
  return MOCK_SCENARIOS.some((s) => s.id === value);
}

export interface MockWireBundle {
  readonly snapshot: Record<string, unknown>;
  readonly timeline: readonly Record<string, unknown>[];
  readonly alerts: Record<string, unknown>;
}

const MINUTE = 60_000;
const SECOND = 1_000;

// Member-gap reasons are the same sentences the Gateway answers with
// (`gateway/readmodel.py`), so a mock gap and a real gap render identically.
const MODE_GAP = "Core 尚无会话模式枚举（A_companion/B_standalone 属产品决定）。";
const PROFILE_NAME_GAP = "Core 只记 profile 的 id 与 revision，没有具名显示名载体。";
const WORLD_CONTEXT_GAP = "world_context_id 的可见性属主控/产品决定（契约 §8），只读面不替它作答。";
const EPOCH_GAP = "同 worldContext：世界坐标类信息的可见性未裁决。";
const RESOLVED_VERSION_GAP = "Core 无 resolvedVersion 具名载体。";
const LAST_SEQUENCE_GAP =
  "ControlHeartbeat 只有 generation 与 monotonic_ns；台账 position 是记账顺序，不是桥的计数器。";
const BRIDGE_VERSION_GAP = "清单只钉 bridge_digest（一枚摘要），没有桥版本串载体。";
const CLIENT_BUNDLE_GAP = "清单记 minecraft/loader/java 版本，没有 bundle 名或 bundle 版本字段。";
const SEALED_AT_GAP = "manifest.json 没有具名密封时间字段；sealed_at_utc 只在封证工具的报告里。";
const LIVE_VIEW_GAP = "没有 framebuffer 采集与媒体中继进程，画面这一面不存在。";
const NO_ALERT_SOURCE_GAP =
  "Core 无告警源：只有台账事件与 run document 的拒止计数，哪些算告警属产品决定。";

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

/** A member of a `known` group that has a carrier. */
function wireFilled(value: unknown): Record<string, unknown> {
  return { value };
}

/** A member of a `known` group that does NOT — named, never defaulted. */
function wireGapField(status: "unknown" | "unavailable" | "not_wired", reason: string): Record<string, unknown> {
  return { gap: { status, reason } };
}

function envelopeKnown(
  scenario: MockScenarioId,
  field: string,
  value: unknown,
  observedMs: number | null,
  staleAfterMs: number | null,
): Record<string, unknown> {
  return {
    status: "known",
    value,
    sourceRef: `mock://scenario/${scenario}/${field}`,
    observedAt: observedMs === null ? null : iso(observedMs),
    staleAfterMs,
  };
}

function envelopeGap(
  scenario: MockScenarioId,
  field: string,
  status: "unknown" | "unavailable" | "not_wired" | "permission_denied",
  reason: string,
  observedMs: number | null = null,
  staleAfterMs: number | null = null,
): Record<string, unknown> {
  return {
    status,
    reason,
    value: null,
    sourceRef: `mock://scenario/${scenario}/${field}`,
    observedAt: observedMs === null ? null : iso(observedMs),
    staleAfterMs,
  };
}

function alert(
  scenario: MockScenarioId,
  index: number,
  severity: AlertSeverity,
  state: AlertState,
  component: AlertComponent,
  title: string,
  detail: string | null,
  seenMs: number,
): Record<string, unknown> {
  return {
    alertId: `al_${scenario}_${index}`,
    severity,
    state,
    component,
    title,
    detail,
    firstSeenAt: iso(seenMs),
    lastSeenAt: iso(seenMs),
    sourceRef: `mock://scenario/${scenario}/alerts`,
  };
}

function event(
  scenario: MockScenarioId,
  index: number,
  atMs: number,
  kind: string,
  title: string,
  outcome: string,
  detail: string | null,
  monotonicMs: number | null,
  generation: number | null,
  sequence: number | null,
): Record<string, unknown> {
  return {
    eventId: `ev_${scenario}_${index}`,
    kind,
    at: iso(atMs),
    monotonicMs,
    generation,
    sequence,
    title,
    detail,
    outcome,
    sourceRef: `mock://scenario/${scenario}/timeline`,
  };
}

/** Alerts envelope (§5.3): `{status, reason, alerts}` — never a bare array. */
function alertsKnown(items: readonly Record<string, unknown>[]): Record<string, unknown> {
  return { status: "known", alerts: items };
}

function alertsNoSource(scenario: MockScenarioId, reason: string): Record<string, unknown> {
  return {
    status: "not_wired",
    reason,
    alerts: [],
    sourceRef: `mock://scenario/${scenario}/alerts`,
  };
}

/**
 * The group values every scenario shares. C-tier fields (`mode`, `profileName`,
 * `worldContext`, `epoch`, `resolvedVersion`, `lastSequence`, bridge/clientBundle
 * versions, `sealedAt`) are member gaps with Core's own reasons — the mock never
 * invents a value the contract says has no carrier.
 */
function sessionGroup(startedMs: number): Record<string, unknown> {
  return {
    sessionId: wireFilled("ses_2026_09_26_07"),
    generation: wireFilled(3),
    startedAt: wireFilled(iso(startedMs)),
    pid: wireFilled(4242),
    overlay: wireFilled("mock://runs/kin_nova_01/session/generation-3"),
    mode: wireGapField("not_wired", MODE_GAP),
  };
}

function worldGroup(): Record<string, unknown> {
  return {
    profileId: wireFilled("profile_offline_local_validation"),
    profileName: wireGapField("not_wired", PROFILE_NAME_GAP),
    worldContext: wireGapField("not_wired", WORLD_CONTEXT_GAP),
    epoch: wireGapField("not_wired", EPOCH_GAP),
    joined: wireFilled(true),
    resolvedVersion: wireGapField("not_wired", RESOLVED_VERSION_GAP),
  };
}

function versionsGroup(): Record<string, unknown> {
  return {
    runtime: wireFilled("1.20.1"),
    bridge: wireGapField("not_wired", BRIDGE_VERSION_GAP),
    clientBundle: wireGapField("not_wired", CLIENT_BUNDLE_GAP),
    java: wireFilled("21.0.12"),
    fabricLoader: wireFilled("0.16.9"),
  };
}

function heartbeatGroup(observedMs: number): Record<string, unknown> {
  return {
    lastSequence: wireGapField("not_wired", LAST_SEQUENCE_GAP),
    lastObservedAt: wireFilled(iso(observedMs)),
    intervalMs: wireFilled(500),
    inputLeaseHeld: wireFilled(false),
  };
}

function evidenceGroup(): Record<string, unknown> {
  return {
    runId: wireFilled("run_2026_09_26_07"),
    attempt: wireFilled(2),
    bundleDigest: wireFilled("sha256:0f4e9c21ab7d"),
    sealedAt: wireGapField("not_wired", SEALED_AT_GAP),
  };
}

function joinedRunSnapshot(scenario: MockScenarioId, nowMs: number, ageMs: number): Record<string, unknown> {
  const observed = nowMs - ageMs;
  return {
    schemaVersion: "kin-dashboard-readmodel/1.0.0",
    kinId: envelopeKnown(scenario, "kinId", "kin_nova_01", observed, MINUTE),
    runtimeState: envelopeKnown(scenario, "runtimeState", "running", observed, 15 * SECOND),
    bridgeLink: envelopeKnown(scenario, "bridgeLink", "connected", observed, 15 * SECOND),
    serverLink: envelopeKnown(scenario, "serverLink", "connected", observed, 15 * SECOND),
    session: envelopeKnown(scenario, "session", sessionGroup(nowMs - 42 * MINUTE), observed, 15 * SECOND),
    world: envelopeKnown(scenario, "world", worldGroup(), observed, MINUTE),
    versions: envelopeKnown(scenario, "versions", versionsGroup(), observed, 10 * MINUTE),
    bridgeHeartbeat: envelopeKnown(scenario, "bridgeHeartbeat", heartbeatGroup(observed), observed, 15 * SECOND),
    // health/food have a carrier (`SelfStateValue`, §3 A-tier); dimension/guiOpen do
    // not exist in the model at all any more.
    selfState: envelopeKnown(scenario, "selfState", { health: 17.5, food: 14 }, observed, 15 * SECOND),
    evidence: envelopeKnown(scenario, "evidence", evidenceGroup(), observed, 10 * MINUTE),
    liveView: envelopeGap(scenario, "liveView", "not_wired", LIVE_VIEW_GAP),
  };
}

export function buildMockBundle(scenario: MockScenarioId, nowMs: number): MockWireBundle {
  switch (scenario) {
    case "healthy_run_07":
      return {
        snapshot: joinedRunSnapshot(scenario, nowMs, 2 * SECOND),
        timeline: [
          event(scenario, 1, nowMs - 40 * SECOND, "observation", "自身快照（生命/饥饿）", "applied", "感知政策过滤后的自身状态", nowMs - 40_400, 3, 4_780),
          event(scenario, 2, nowMs - 32 * SECOND, "decision", "目标：继续 mining_shift", "applied", null, nowMs - 32_300, 3, 4_792),
          event(scenario, 3, nowMs - 24 * SECOND, "intent", "intent：向坐标短距移动", "applied", "带 lease 与 deadline", nowMs - 24_100, 3, 4_801),
          event(scenario, 4, nowMs - 23 * SECOND, "input", "输入 W 按下", "applied", "Bridge 仲裁通过", nowMs - 23_050, 3, 4_802),
          event(scenario, 5, nowMs - 20 * SECOND, "server_feedback", "服务器位置回执一致", "applied", null, nowMs - 20_010, 3, 4_811),
          event(scenario, 6, nowMs - 9 * SECOND, "session", "Bridge 心跳续期", "applied", null, nowMs - 9_000, 3, 4_821),
        ],
        alerts: alertsKnown([alert(scenario, 1, "info", "resolved", "launcher", "客户端 bundle 已按已验证 recipe 就位", null, nowMs - 60 * MINUTE)]),
      };

    case "stale_observations":
      return {
        snapshot: joinedRunSnapshot(scenario, nowMs, 4 * MINUTE),
        timeline: [
          event(scenario, 1, nowMs - 4 * MINUTE, "observation", "最后一次自身快照", "applied", "此后 Runtime 未再产生事件", nowMs - 240_500, 3, 4_610),
          event(scenario, 2, nowMs - 5 * MINUTE, "decision", "目标：mining_shift 继续", "applied", null, nowMs - 300_000, 3, 4_540),
          event(scenario, 3, nowMs - 6 * MINUTE, "reflex", "反射：松键（危险退化）", "released", null, nowMs - 360_000, 3, 4_500),
        ],
        // A source that answers with zero items: 「没有告警」, which the panel must
        // never confuse with the 「无告警源」 envelope below.
        alerts: alertsKnown([]),
      };

    case "bridge_disconnected": {
      const observed = nowMs - 90 * SECOND;
      const lostReason = "Bridge 心跳停止，Runtime 已失去世界通道。";
      return {
        snapshot: {
          schemaVersion: "kin-dashboard-readmodel/1.0.0",
          kinId: envelopeKnown(scenario, "kinId", "kin_nova_01", observed, MINUTE),
          runtimeState: envelopeKnown(scenario, "runtimeState", "unresolved", observed, 15 * SECOND),
          bridgeLink: envelopeKnown(scenario, "bridgeLink", "disconnected", observed, 15 * SECOND),
          serverLink: envelopeKnown(scenario, "serverLink", "disconnected", observed, 15 * SECOND),
          session: envelopeKnown(scenario, "session", sessionGroup(nowMs - 42 * MINUTE), observed, 15 * SECOND),
          world: envelopeGap(scenario, "world", "unknown", "失联后不重放旧 world context。", observed, 15 * SECOND),
          versions: envelopeKnown(scenario, "versions", versionsGroup(), observed, 10 * MINUTE),
          bridgeHeartbeat: envelopeGap(scenario, "bridgeHeartbeat", "unavailable", lostReason, observed, 15 * SECOND),
          selfState: envelopeGap(scenario, "selfState", "unknown", "世界状态已标记陈旧，不虚构游戏结果。", observed, 15 * SECOND),
          evidence: envelopeKnown(scenario, "evidence", evidenceGroup(), observed, 10 * MINUTE),
          liveView: envelopeGap(scenario, "liveView", "not_wired", LIVE_VIEW_GAP),
        },
        timeline: [
          event(scenario, 1, nowMs - 120 * SECOND, "input", "输入 W 释放", "released", "断线前最后一条输入回执", nowMs - 120_000, 3, 4_770),
          event(scenario, 2, nowMs - 95 * SECOND, "fault", "Bridge 心跳丢失", "applied", lostReason, null, 3, null),
          event(scenario, 3, nowMs - 92 * SECOND, "fault", "旧 intent 因 generation 过期被丢弃", "expired", "未按断线前计划重放", null, 3, null),
          event(scenario, 4, nowMs - 90 * SECOND, "session", "会话进入安全停机", "applied", "未重连；等待人工确认", null, null, null),
        ],
        alerts: alertsKnown([
          alert(scenario, 1, "critical", "active", "bridge", "Bridge 失联：输入 lease 已释放", "旧动作不会重放；世界状态标记为陈旧", nowMs - 95 * SECOND),
          alert(scenario, 2, "warning", "active", "gateway", "面板显示的状态可能已不反映当前会话", null, nowMs - 90 * SECOND),
          alert(scenario, 3, "info", "resolved", "runtime", "身份与未决目标已保留", null, nowMs - 80 * SECOND),
        ]),
      };
    }

    case "fields_unknown": {
      const observed = nowMs - 5 * SECOND;
      return {
        snapshot: {
          schemaVersion: "kin-dashboard-readmodel/1.0.0",
          kinId: envelopeKnown(scenario, "kinId", "kin_nova_01", observed, MINUTE),
          runtimeState: envelopeKnown(scenario, "runtimeState", "idle", observed, 15 * SECOND),
          bridgeLink: envelopeGap(scenario, "bridgeLink", "unknown", "台账里没有任何事件行：这个 Kin 还没有启动过会话。", null, null),
          serverLink: envelopeGap(scenario, "serverLink", "unknown", "台账里没有任何事件行：这个 Kin 还没有启动过会话。", null, null),
          session: envelopeGap(scenario, "session", "unknown", "这个 Kin 没有记录的客户端进程：还没有启动过会话，或上一次已经收摊。", null, null),
          world: envelopeGap(scenario, "world", "unknown", "台账里没有任何事件行：这个 Kin 还没有启动过会话。", null, null),
          versions: envelopeGap(scenario, "versions", "unavailable", "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。 版本五件套没有统一读接口，只有已封 bundle 的清单能答其中三个。", null, null),
          bridgeHeartbeat: envelopeGap(scenario, "bridgeHeartbeat", "unknown", "台账里没有任何事件行：这个 Kin 还没有启动过会话。", null, null),
          selfState: envelopeGap(scenario, "selfState", "unavailable", "Core 不落相干性快照行：health/food 只在会话内存里，只读投影取不到。", null, null),
          evidence: envelopeGap(scenario, "evidence", "unknown", "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。", null, null),
          liveView: envelopeGap(scenario, "liveView", "not_wired", LIVE_VIEW_GAP),
        },
        timeline: [
          event(scenario, 1, nowMs - 6 * SECOND, "session", "CLI 会话事件（无 sequence）", "unknown", "缺 monotonic/generation/sequence 真源", null, null, null),
          event(scenario, 2, nowMs - 6 * SECOND, "observation", "无过滤观察记录", "unknown", null, null, null, null),
        ],
        alerts: alertsNoSource(scenario, NO_ALERT_SOURCE_GAP),
      };
    }

    case "permission_restricted": {
      const observed = nowMs - 2 * SECOND;
      const snapshot = joinedRunSnapshot(scenario, nowMs, 2 * SECOND);
      return {
        snapshot: {
          ...snapshot,
          world: envelopeGap(scenario, "world", "permission_denied", "Server Profile 含 host/port 与身份引用，需只读脱敏视图与管理员权限。", observed, MINUTE),
          evidence: envelopeGap(scenario, "evidence", "permission_denied", "证据引用含 run/attempt 与 bundle 摘要，按观看权限分层。", observed, 10 * MINUTE),
          selfState: envelopeGap(scenario, "selfState", "permission_denied", "位置/背包类读数未纳入本次只读范围。", observed, 15 * SECOND),
          liveView: envelopeGap(scenario, "liveView", "permission_denied", "观战画面需要单独授权与观看审计，且当前没有真帧源。"),
        },
        timeline: [event(scenario, 1, nowMs - 30 * SECOND, "session", "会话开始（细节需脱敏）", "applied", null, nowMs - 30_000, 3, 4_100)],
        alerts: alertsKnown([
          alert(scenario, 1, "warning", "active", "gateway", "字段因权限策略隐藏", "浏览器不持有 Bridge 凭据；管理员读取需 Gateway 鉴权", nowMs - 30 * SECOND),
        ]),
      };
    }

    case "read_failed": {
      // The adapter fails this read before any decoding happens; the wire is the
      // healthy one so the scenario never ships half-real bytes.
      return {
        snapshot: joinedRunSnapshot(scenario, nowMs, 2 * SECOND),
        timeline: [],
        alerts: alertsKnown([]),
      };
    }
  }
}
