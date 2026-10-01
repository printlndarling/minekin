import type { AlertSeverity, AlertState, AlertComponent, ConfigValue } from "../domain/model";

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

/**
 * The per-process CSRF token the mock hands out over its identity read and requires back on
 * a rename. It is a fixed string because there is no server process here, but the panel and
 * the mock adapter treat it exactly like the real token: captured from the read, echoed on
 * the write, never rendered in the UI.
 */
export const MOCK_IDENTITY_CSRF = "mock-csrf-token";

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
// Skill-step sentences are `gateway/readmodel.py`'s own constants, verbatim: the group
// gap and every member gap a mock shows must render exactly as the real projection's.
const NO_SKILL_STEPS_GAP =
  "台账里没有技能步行（SkillStepRecorded）：最近这个 run 没有跑过世界技能——" +
  "只连接、只演示输入的运行不会有这类行，这里不把它折成「0 步」。";
const SKILL_CONFIRMED_REASON_GAP = "这一步的结果是 CONFIRMED：没有失败原因可报，Core 按约定把 reason 写成空串。";
const SKILL_CONFIRMED_ATTRIBUTION_GAP =
  "已确认的步骤没有失败可归因：attribution 只在失败步携带 mind 的 FailureCode 名。";
const SKILL_MODEL_ANSWERED_GAP = "模型作答了这一步：model_refusal 是空串，没有拒止可报。";
const SKILL_MODEL_COST_GAP =
  "调用花费（model_calls / model_spent_micro / model_cap_refusals）只在 run document 的 " +
  "mind 段里记录，技能步行不携带；未封的 run 只读面取不到，封证后也要读 bundle 里的 " +
  "run document，本投影不解析它。";
const SKILL_MODEL_CONFIG_GAP =
  "模型配置状态（model_enabled 与所配置的 provider）与花费同处：只在 run document 的 " +
  "mind 段里记录，台账行不携带，本投影只读台账与已封 bundle 的清单。";

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

/**
 * The newest concluded step of a scripted autonomous run: a model-chosen craft that the
 * later world readings confirmed. A confirmed step carries no failure reason, no
 * attribution and no refusal — each one a member gap with the Gateway's own sentence,
 * never `""`. Cost and model config are `not_wired` member gaps: Core records them only
 * in the run document, which the read surface does not parse. `behaviorParameters` is
 * the one run-document field the projection DOES parse, so a sealed run whose newest
 * step is a craft shows the honoured, redacted arguments here (`target_item`/`quantity`).
 */
function skillStepsGroup(): Record<string, unknown> {
  return {
    goal: wireFilled("先挖到木头，再合成木镐"),
    stepIndex: wireFilled(4),
    skill: wireFilled("craft"),
    result: wireFilled("CONFIRMED"),
    reason: wireGapField("unavailable", SKILL_CONFIRMED_REASON_GAP),
    attribution: wireGapField("unavailable", SKILL_CONFIRMED_ATTRIBUTION_GAP),
    decisionSource: wireFilled("DECISION_FROM_MODEL"),
    modelRefusal: wireGapField("unavailable", SKILL_MODEL_ANSWERED_GAP),
    stepCount: wireFilled(4),
    modelCost: wireGapField("not_wired", SKILL_MODEL_COST_GAP),
    modelConfig: wireGapField("not_wired", SKILL_MODEL_CONFIG_GAP),
    behaviorParameters: wireFilled("quantity=1, target_item=minecraft:wooden_pickaxe"),
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
    skillSteps: envelopeKnown(scenario, "skillSteps", skillStepsGroup(), observed, null),
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
          // 该场景是只连了桥、没跑过世界技能就失联的 run：与真实投影一致，组级缺口而不是 0 步。
          skillSteps: envelopeGap(scenario, "skillSteps", "unknown", NO_SKILL_STEPS_GAP),
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
          skillSteps: envelopeGap(scenario, "skillSteps", "unknown", NO_SKILL_STEPS_GAP),
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

/**
 * A mock offline UUID: deterministic from the name (so the same name always resolves the
 * same value, and a rename always changes it), UUID-shaped so the panel exercises the real
 * display width. It is NOT `offline_player_uuid` — the mock never claims to run Core's MD5
 * rule; the descriptor and every `sourceRef` mark these readings as mock.
 */
export function mockOfflineUuid(username: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < username.length; i += 1) {
    h ^= username.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  const hex = (salt: number): string => {
    let x = (h ^ salt) >>> 0;
    let out = "";
    for (let i = 0; i < 8; i += 1) {
      out += ((x >>> (i * 3)) & 0xf).toString(16);
    }
    return out;
  };
  return `${hex(1)}-${hex(2).slice(0, 4)}-3${hex(3).slice(0, 3)}-a${hex(4).slice(0, 3)}-${hex(5)}${hex(6)}${hex(2)}`.slice(0, 36);
}

/** The session state the identity read reports for a scenario, mirroring its snapshot. */
export function mockIdentityState(scenario: MockScenarioId): "idle" | "running" | "unresolved" {
  switch (scenario) {
    case "fields_unknown":
      return "idle";
    case "bridge_disconnected":
      return "unresolved";
    default:
      return "running";
  }
}

const MOCK_IDENTITY_NOTICE =
  "离线玩家的 UUID 由名字本身推导而来。改名会解析出新的离线 UUID：已加入过的服务器会把它当作另一个玩家，" +
  "背包、位置与进度都不迁移。请只在会话停止时改名。";

/**
 * The identity document `gateway/identity.py::identity_read` answers, in the exact wire
 * shape the shared `decodeIdentityPayload` parses. A Kin defaults to `minekin` at revision 1
 * and keeps its name; `renameAllowed` is true only for the stopped (`idle`) scenario, so the
 * mock reproduces the same "rename only while stopped" fact the real write enforces.
 */
export function buildMockIdentity(scenario: MockScenarioId, nowMs: number, username = "minekin", identityRevision = 1): Record<string, unknown> {
  const state = mockIdentityState(scenario);
  return {
    schemaVersion: "kin-dashboard-identity/1.0.0",
    kinId: "kin_nova_01",
    username,
    uuidCanonical: mockOfflineUuid(username),
    identityRevision,
    state,
    renameAllowed: state === "idle",
    notice: MOCK_IDENTITY_NOTICE,
    csrfToken: MOCK_IDENTITY_CSRF,
    observedAt: iso(nowMs),
    staleAfterMs: 8_000,
  };
}

/**
 * The field vocabulary `gateway/config_write.py` projects, spelled exactly as it sorts them
 * (`sorted(_KNOWN_FIELDS)`, `sorted(_INT_FIELDS)`, `sorted(KNOWN_PROVIDERS)`), so a mock config
 * read and a real one feed the shared `decodeConfigPayload` the same way and the panel's provider
 * select offers the same two names.
 */
const MOCK_CONFIG_KNOWN_FIELDS = [
  "goal_direction",
  "goal_product_id",
  "goal_quantity",
  "goal_source_item_id",
  "model_api_key_env",
  "model_base_url",
  "model_name",
  "model_provider",
  "model_run_cost_cap",
  "model_timeout_ms",
];
const MOCK_CONFIG_INT_FIELDS = ["goal_quantity", "model_run_cost_cap", "model_timeout_ms"];
export const MOCK_CONFIG_PROVIDERS = ["off", "openai_compatible"];

/**
 * The saved document each scenario starts on. Only `healthy_run_07` is pre-filled — a realistic
 * `openai_compatible` preset with a placeholder endpoint and NO key (the closest field,
 * `model_api_key_env`, holds a variable NAME). Every other scenario begins from an empty document,
 * which is a supported shape (a fresh root): the form renders blank, and a save from blank writes
 * blank. `read_failed` never reaches a config read (the adapter fails first).
 */
export function mockConfigInitialFields(scenario: MockScenarioId): Record<string, ConfigValue> {
  if (scenario !== "healthy_run_07") return {};
  return {
    model_provider: "openai_compatible",
    model_base_url: "https://model.example.com/v1",
    model_name: "deepseek-chat",
    model_api_key_env: "MINEKIN_MODEL_API_KEY",
    model_timeout_ms: 30000,
    model_run_cost_cap: 5000000,
    goal_product_id: "minecraft:wooden_pickaxe",
    goal_quantity: 1,
    goal_source_item_id: "minecraft:oak_log",
    goal_direction: "先挖木头，再合成木镐",
  };
}

/**
 * The config document `gateway/config_write.py::config_read` answers, in the exact wire shape the
 * shared `decodeConfigPayload` parses. `fields` is the caller's current populated-only document
 * (the adapter's mutable store), so the next read reflects the last accepted save — the same
 * observable sequence `operator_config` produces between a save and the following read. Like the
 * identity fixture, `csrfToken` is the shared mock token the adapter echoes back on a save, never
 * rendered. `loadError` stays null here; the panel's unreadable-document path is exercised by a
 * decoder test that feeds a hand-shaped document directly.
 */
export function buildMockConfig(
  scenario: MockScenarioId,
  nowMs: number,
  fields: Record<string, ConfigValue> = mockConfigInitialFields(scenario),
): Record<string, unknown> {
  return {
    schemaVersion: "kin-dashboard-config/1.0.0",
    fields,
    knownFields: MOCK_CONFIG_KNOWN_FIELDS,
    intFields: MOCK_CONFIG_INT_FIELDS,
    providers: MOCK_CONFIG_PROVIDERS,
    maxBodyBytes: 8192,
    loadError: null,
    csrfToken: MOCK_IDENTITY_CSRF,
    observedAt: iso(nowMs),
    staleAfterMs: 8_000,
  };
}

/**
 * The three control verbs the session surface withholds, spelled exactly as
 * `gateway/session_control.py::_UNAVAILABLE_CONTROLS` records them, so a mock read and a real one
 * feed the panel the same boundary. The mock never fakes these as available: stop is the only verb
 * this product can perform safely today, and a stopped-only surface is what the fixture answers.
 */
const MOCK_SESSION_UNAVAILABLE_CONTROLS: Record<string, string> = {
  start:
    "starting a session launches a client and joins a world; that must be hosted by the live `session start` process, which the read-only Gateway is not",
  pause: "the session state machine has no PAUSED state yet, so there is nothing to pause into",
  resume: "the session state machine has no PAUSED state yet, so there is nothing to resume",
};

/**
 * The session document `gateway/session_control.py::session_read` answers, in the exact wire shape
 * the shared `decodeSessionPayload` parses. The state mirrors the identity read (the same
 * `read_status` source the real server trusts), and `stopAllowed` follows the same predicate — a
 * session that is not idle. Like identity/config, `csrfToken` is the shared mock token the adapter
 * echoes back on the stop, never rendered. `availableControls` pins only `stop`; the withheld verbs
 * arrive as the `{verb: reason}` object the decoder turns into ordered rows.
 */
export function buildMockSession(scenario: MockScenarioId, nowMs: number): Record<string, unknown> {
  const state = mockIdentityState(scenario);
  return {
    schemaVersion: "kin-dashboard-session/1.0.0",
    state,
    stopAllowed: state !== "idle",
    availableControls: ["stop"],
    unavailableControls: MOCK_SESSION_UNAVAILABLE_CONTROLS,
    csrfToken: MOCK_IDENTITY_CSRF,
    observedAt: iso(nowMs),
    staleAfterMs: 8_000,
  };
}

/**
 * A stop the mock accepts (HTTP 200), in the exact wire shape `decodeStopPayload` parses: Core's
 * `StopReport.as_dict` flattens the outcome buckets beside a nested `release`. It is keyed on the
 * state the mock observed when the stop ran. A `running` session stops cleanly (the one recorded
 * client pid released and terminated); an `unresolved` one comes back `blocked` with that pid in
 * `unconfirmed`/`unresolved` — the honest case the panel must not read as success. An `idle` Kin
 * never reaches here: the mock adapter refuses it as `session_not_running` before building any
 * report, mirroring the real 409.
 */
export function buildMockStopReport(state: "running" | "unresolved", kinId = "kin_nova_01"): Record<string, unknown> {
  if (state === "unresolved") {
    return {
      schema_version: 1,
      command: "session stop",
      status: "blocked",
      kin_id: kinId,
      release: { asked: [4242], released: [], nothing_held: [], unconfirmed: [4242] },
      terminated: [],
      left_alone: [],
      unresolved: [4242],
    };
  }
  return {
    schema_version: 1,
    command: "session stop",
    status: "stopped",
    kin_id: kinId,
    release: { asked: [4242], released: [4242], nothing_held: [], unconfirmed: [] },
    terminated: [4242],
    left_alone: [],
    unresolved: [],
  };
}
