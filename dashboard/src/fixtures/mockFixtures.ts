import { SNAPSHOT_SCHEMA_VERSION, type Alert, type KinSnapshot, type TimelineEvent } from "../domain/model";
import { gap, known, type SignalContext } from "../domain/signals";

/**
 * Scripted, clearly-labelled fixtures. Nothing here is measured from Core, the
 * Bridge or a server; every signal below carries `source: "mock"`.
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
  { id: "healthy_run_07", label: "正常在线", note: "所有只读字段新鲜，媒体仍未接入。" },
  { id: "stale_observations", label: "读数陈旧", note: "观测时间在 staleness 窗口之外：状态保留但标注陈旧。" },
  { id: "bridge_disconnected", label: "Bridge 失联", note: "runtime_state 未定，心跳不可用，不虚构世界状态。" },
  { id: "fields_unknown", label: "字段无真源", note: "Core 只暴露 CLI 读数，多数面板显示未知而不是默认值。" },
  { id: "permission_restricted", label: "无权限", note: "服务器 profile 与证据引用需要脱敏视图，当前拒绝显示。" },
  { id: "read_failed", label: "读取失败（Gateway 不可达）", note: "整次读取失败：面板保持挂载并全部标注未知。" },
];

export function isMockScenarioId(value: string): value is MockScenarioId {
  return MOCK_SCENARIOS.some((s) => s.id === value);
}

export interface MockBundle {
  readonly snapshot: KinSnapshot;
  readonly timeline: readonly TimelineEvent[];
  readonly alerts: readonly Alert[];
}

const MINUTE = 60_000;
const SECOND = 1_000;

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

function ctxOf(scenario: MockScenarioId, field: string, observedMs: number | null, staleAfterMs: number | null): SignalContext {
  return {
    source: "mock",
    sourceRef: `mock://scenario/${scenario}/${field}`,
    observedAt: observedMs === null ? null : iso(observedMs),
    staleAfterMs,
  };
}

function alert(
  scenario: MockScenarioId,
  index: number,
  severity: Alert["severity"],
  state: Alert["state"],
  component: Alert["component"],
  title: string,
  detail: string | null,
  seenMs: number,
): Alert {
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
  kind: TimelineEvent["kind"],
  title: string,
  outcome: TimelineEvent["outcome"],
  detail: string | null,
  monotonicMs: number | null,
  generation: number | null,
  sequence: number | null,
): TimelineEvent {
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

function healthySnapshot(scenario: MockScenarioId, nowMs: number, ageMs: number): KinSnapshot {
  const observed = nowMs - ageMs;
  const c = (field: string, stale: number | null = 15 * SECOND) => ctxOf(scenario, field, observed, stale);
  return {
    schemaVersion: SNAPSHOT_SCHEMA_VERSION,
    kinId: known("kin_nova_01", c("kinId", MINUTE)),
    runtimeState: known("running", c("runtimeState")),
    bridgeLink: known("connected", c("bridgeLink")),
    serverLink: known("connected", c("serverLink")),
    session: known(
      {
        sessionId: "ses_2026_09_26_07",
        generation: 3,
        mode: "B_standalone",
        startedAt: iso(nowMs - 42 * MINUTE),
      },
      c("session"),
    ),
    world: known(
      {
        profileId: "profile_offline_local_validation",
        profileName: "本地受控验证服（匿名）",
        worldContext: "world:main",
        epoch: 2,
        joined: true,
        resolvedVersion: "1.20.1",
      },
      c("world", MINUTE),
    ),
    versions: known(
      {
        runtime: "0.9.0-p0",
        bridge: "0.9.0-p0",
        clientBundle: "1.20.1+fabric-0.16.9",
        java: "21.0.12",
        fabricLoader: "0.16.9",
      },
      c("versions", 10 * MINUTE),
    ),
    bridgeHeartbeat: known(
      {
        lastSequence: 4821,
        lastObservedAt: iso(observed),
        intervalMs: SECOND,
        inputLeaseHeld: false,
      },
      c("bridgeHeartbeat"),
    ),
    selfState: known(
      {
        health: 17.5,
        food: 14,
        dimension: "overworld",
        guiOpen: false,
      },
      c("selfState"),
    ),
    evidence: known(
      {
        runId: "run_2026_09_26_07",
        attempt: "a2",
        bundleDigest: "sha256:0f4e9c21ab7d",
        sealedAt: iso(nowMs - 3 * MINUTE),
      },
      c("evidence", 10 * MINUTE),
    ),
    liveView: gap("not_wired", "没有 framebuffer 采集与媒体中继进程，Live View 无真实帧源。", {
      ...ctxOf(scenario, "liveView", null, null),
    }),
  };
}

export function buildMockBundle(scenario: MockScenarioId, nowMs: number): MockBundle {
  switch (scenario) {
    case "healthy_run_07":
      return {
        snapshot: healthySnapshot(scenario, nowMs, 2 * SECOND),
        timeline: [
          event(scenario, 1, nowMs - 40 * SECOND, "observation", "自身快照（生命/饥饿/维度）", "applied", "感知政策过滤后的自身状态", nowMs - 40_400, 3, 4_780),
          event(scenario, 2, nowMs - 32 * SECOND, "decision", "目标：继续 mining_shift", "applied", null, nowMs - 32_300, 3, 4_792),
          event(scenario, 3, nowMs - 24 * SECOND, "intent", "intent：向坐标短距移动", "applied", "带 lease 与 deadline", nowMs - 24_100, 3, 4_801),
          event(scenario, 4, nowMs - 23 * SECOND, "input", "输入 W 按下", "applied", "Bridge 仲裁通过", nowMs - 23_050, 3, 4_802),
          event(scenario, 5, nowMs - 20 * SECOND, "server_feedback", "服务器位置回执一致", "applied", null, nowMs - 20_010, 3, 4_811),
          event(scenario, 6, nowMs - 9 * SECOND, "session", "Bridge 心跳续期", "applied", null, nowMs - 9_000, 3, 4_821),
        ],
        alerts: [alert(scenario, 1, "info", "resolved", "launcher", "客户端 bundle 已按已验证 recipe 就位", null, nowMs - 60 * MINUTE)],
      };

    case "stale_observations":
      return {
        snapshot: healthySnapshot(scenario, nowMs, 4 * MINUTE),
        timeline: [
          event(scenario, 1, nowMs - 4 * MINUTE, "observation", "最后一次自身快照", "applied", "此后 Runtime 未再产生事件", nowMs - 240_500, 3, 4_610),
          event(scenario, 2, nowMs - 5 * MINUTE, "decision", "目标：mining_shift 继续", "applied", null, nowMs - 300_000, 3, 4_540),
          event(scenario, 3, nowMs - 6 * MINUTE, "reflex", "反射：松键（危险退化）", "released", null, nowMs - 360_000, 3, 4_500),
        ],
        alerts: [
          alert(scenario, 1, "warning", "active", "runtime", "读数陈旧：超过 staleness 窗口", "最后观测距今约 4 分钟，面板值不代表当前世界", nowMs - 4 * MINUTE),
          alert(scenario, 2, "info", "active", "gateway", "Gateway 心跳仍在，事件流静默", null, nowMs - 3 * MINUTE),
        ],
      };

    case "bridge_disconnected": {
      const observed = nowMs - 90 * SECOND;
      const c = (field: string, stale: number | null = 15 * SECOND) => ctxOf(scenario, field, observed, stale);
      const lostReason = "Bridge 心跳停止，Runtime 已失去世界通道。";
      return {
        snapshot: {
          schemaVersion: SNAPSHOT_SCHEMA_VERSION,
          kinId: known("kin_nova_01", c("kinId", MINUTE)),
          runtimeState: known("unresolved", c("runtimeState")),
          bridgeLink: known("disconnected", c("bridgeLink")),
          serverLink: known("disconnected", c("serverLink")),
          session: known(
            { sessionId: "ses_2026_09_26_07", generation: 3, mode: "B_standalone", startedAt: iso(nowMs - 42 * MINUTE) },
            c("session"),
          ),
          world: gap("unknown", "失联后不重放旧 world context。", c("world")),
          versions: known(
            { runtime: "0.9.0-p0", bridge: "0.9.0-p0", clientBundle: "1.20.1+fabric-0.16.9", java: "21.0.12", fabricLoader: "0.16.9" },
            c("versions", 10 * MINUTE),
          ),
          bridgeHeartbeat: gap("unavailable", lostReason, { ...c("bridgeHeartbeat"), observedAt: iso(observed) }),
          selfState: gap("unknown", "世界状态已标记陈旧，不虚构游戏结果。", c("selfState")),
          evidence: known(
            { runId: "run_2026_09_26_07", attempt: "a2", bundleDigest: "sha256:0f4e9c21ab7d", sealedAt: iso(nowMs - 3 * MINUTE) },
            c("evidence", 10 * MINUTE),
          ),
          liveView: gap("not_wired", "媒体通道未接入。", { ...ctxOf(scenario, "liveView", null, null) }),
        },
        timeline: [
          event(scenario, 1, nowMs - 120 * SECOND, "input", "输入 W 释放", "released", "断线前最后一条输入回执", nowMs - 120_000, 3, 4_770),
          event(scenario, 2, nowMs - 95 * SECOND, "fault", "Bridge 心跳丢失", "applied", lostReason, null, 3, null),
          event(scenario, 3, nowMs - 92 * SECOND, "fault", "旧 intent 因 generation 过期被丢弃", "expired", "未按断线前计划重放", null, 3, null),
          event(scenario, 4, nowMs - 90 * SECOND, "session", "会话进入安全停机", "applied", "未重连；等待人工确认", null, null, null),
        ],
        alerts: [
          alert(scenario, 1, "critical", "active", "bridge", "Bridge 失联：输入 lease 已释放", "旧动作不会重放；世界状态标记为陈旧", nowMs - 95 * SECOND),
          alert(scenario, 2, "warning", "active", "gateway", "面板显示的状态可能已不反映当前会话", null, nowMs - 90 * SECOND),
          alert(scenario, 3, "info", "resolved", "runtime", "身份与未决目标已保留", null, nowMs - 80 * SECOND),
        ],
      };
    }

    case "fields_unknown": {
      const c = (field: string, stale: number | null = 15 * SECOND) => ctxOf(scenario, field, nowMs - 5 * SECOND, stale);
      return {
        snapshot: {
          schemaVersion: SNAPSHOT_SCHEMA_VERSION,
          kinId: known("kin_nova_01", c("kinId", MINUTE)),
          runtimeState: known("idle", c("runtimeState", 15 * SECOND)),
          bridgeLink: gap("unknown", "P0 没有 Gateway：Bridge 链路状态只在 CLI 输出里，未成为可读 API。", c("bridgeLink")),
          serverLink: gap("unknown", "服务器连接状态需 JOIN 会话读数，当前无该 API。", c("serverLink")),
          session: gap("unknown", "session_id/generation 尚未由只读接口暴露。", c("session")),
          world: gap("unknown", "world context 与 epoch 尚未暴露。", c("world")),
          versions: known(
            { runtime: "0.9.0-p0", bridge: "0.9.0-p0", clientBundle: "1.20.1+fabric-0.16.9", java: "21.0.12", fabricLoader: "0.16.9" },
            c("versions", 10 * MINUTE),
          ),
          bridgeHeartbeat: gap("unknown", "无心跳流：需要 Gateway 事件游标。", c("bridgeHeartbeat")),
          selfState: gap("unknown", "Core 不把每 tick 世界状态作为面板读数暴露。", c("selfState")),
          evidence: gap("unknown", "run/attempt/bundle 摘要在证据 bundle 文件里，尚无按 kin 索引的读接口。", c("evidence")),
          liveView: gap("not_wired", "无采集与中继进程。", { ...ctxOf(scenario, "liveView", null, null) }),
        },
        timeline: [
          event(scenario, 1, nowMs - 6 * SECOND, "session", "CLI 会话事件（无 sequence）", "unknown", "缺 monotonic/generation/sequence 真源", null, null, null),
          event(scenario, 2, nowMs - 6 * SECOND, "observation", "无过滤观察记录", "unknown", null, null, null, null),
        ],
        alerts: [alert(scenario, 1, "info", "active", "gateway", "多数字段无真源：显示未知而非默认值", "Gateway 只读 read model 未冻结（G lane）", nowMs - 6 * SECOND)],
      };
    }

    case "permission_restricted": {
      const snapshot = healthySnapshot(scenario, nowMs, 2 * SECOND);
      return {
        snapshot: {
          ...snapshot,
          world: gap("permission_denied", "Server Profile 含 host/port 与身份引用，需只读脱敏视图与管理员权限。", ctxOf(scenario, "world", nowMs - 2 * SECOND, MINUTE)),
          evidence: gap("permission_denied", "证据引用含 run/attempt 与 bundle 摘要，按观看权限分层。", ctxOf(scenario, "evidence", nowMs - 2 * SECOND, 10 * MINUTE)),
          selfState: gap("permission_denied", "位置/背包类读数未纳入本次只读范围。", ctxOf(scenario, "selfState", nowMs - 2 * SECOND, 15 * SECOND)),
          liveView: gap("permission_denied", "观战画面需要单独授权与观看审计，且当前没有真帧源。", { ...ctxOf(scenario, "liveView", null, null) }),
        },
        timeline: [event(scenario, 1, nowMs - 30 * SECOND, "session", "会话开始（细节需脱敏）", "applied", null, nowMs - 30_000, 3, 4_100)],
        alerts: [
          alert(scenario, 1, "warning", "active", "gateway", "字段因权限策略隐藏", "浏览器不持有 Bridge 凭据；管理员读取需 Gateway 鉴权", nowMs - 30 * SECOND),
        ],
      };
    }

    case "read_failed": {
      const snapshot = healthySnapshot(scenario, nowMs, 2 * SECOND);
      return {
        snapshot,
        timeline: [],
        alerts: [alert(scenario, 1, "critical", "active", "gateway", "读取失败：Gateway 不可达", "面板保留上次结构但值全部未知", nowMs - SECOND)],
      };
    }
  }
}
