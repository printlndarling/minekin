import { describe, expect, it } from "vitest";
import { decodeAlertsPayload, decodeSnapshotPayload, READ_ENDPOINTS } from "./gatewayAdapter";
import { DEFAULT_TIMEOUT_MS } from "./config";
import { SNAPSHOT_SCHEMA_VERSION, fieldValue, fieldGap } from "../domain/model";
import type { Signal } from "../domain/signals";
import { isKnown } from "../domain/signals";
import { cloneWire, wireFilled, wireGapField } from "../test/wireFixture";
import {
  REAL_AFTER_SESSION_SNAPSHOT_WIRE,
  REAL_ALERTS_ENVELOPE_WIRE,
  REAL_IN_SESSION_SNAPSHOT_WIRE,
  REAL_JOINED_RUN_SNAPSHOT_WIRE,
} from "../test/realGatewayWire";

/** A gap where the capture says `known` is a decode failure, not a null to tolerate. */
function mustKnow<T>(signal: Signal<T>, what: string): T {
  if (!isKnown(signal)) throw new Error(`${what} 应是 known，实际 ${signal.status}：${signal.reason}`);
  return signal.value;
}

/** The joined-run bytes plus one `known` selfState group, so member tests have a live group. */
function realWire(): Record<string, unknown> {
  const wire = cloneWire(REAL_JOINED_RUN_SNAPSHOT_WIRE);
  wire.selfState = {
    status: "known",
    value: { health: 17.5, food: 14 },
    sourceRef: "core://status/kin-01/selfState",
    observedAt: "2000-01-01T00:00:00Z",
    staleAfterMs: null,
  };
  return wire;
}

describe("真实 Gateway 字节：解码器必须按现字节工作，而不是按猜测", () => {
  it("joined-run 快照零问题解码", () => {
    const decoded = decodeSnapshotPayload(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    // The decode union only carries `issues` on the failure side: `ok` here IS
    // the zero-issues statement.
    if (!decoded.ok) throw new Error(`issues: ${decoded.issues.join(" | ")}`);
    expect(decoded.snapshot.schemaVersion).toBe(SNAPSHOT_SCHEMA_VERSION);
  });

  it("session.mode 渲染为带 Core 原文理由的缺口，绝不落入默认模式", () => {
    const decoded = decodeSnapshotPayload(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const session = decoded.snapshot.session;
    if (!isKnown(session)) throw new Error("session 组应是 known");
    const gap = fieldGap(session.value.mode);
    expect(gap?.status).toBe("not_wired");
    expect(gap?.reason).toBe("Core 尚无会话模式枚举（A_companion/B_standalone 属产品决定）。");
    expect(fieldValue(session.value.mode)).toBeNull();
  });

  it("world.joined 读出 true，四个 C 档世界成员保持 not_wired", () => {
    const decoded = decodeSnapshotPayload(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const world = decoded.snapshot.world;
    if (!isKnown(world)) throw new Error("world 组应是 known");
    expect(fieldValue(world.value.joined)).toBe(true);
    expect(fieldValue(world.value.profileId)).toBe("srv-profile-00000000000000000000");
    expect(fieldGap(world.value.profileName)?.status).toBe("not_wired");
    expect(fieldGap(world.value.worldContext)?.status).toBe("not_wired");
    expect(fieldGap(world.value.epoch)?.status).toBe("not_wired");
    expect(fieldGap(world.value.resolvedVersion)?.status).toBe("not_wired");
  });

  it("bridgeHeartbeat.lastSequence 是缺口，intervalMs 是 500", () => {
    const decoded = decodeSnapshotPayload(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const heartbeat = decoded.snapshot.bridgeHeartbeat;
    if (!isKnown(heartbeat)) throw new Error("心跳组应是 known");
    expect(fieldGap(heartbeat.value.lastSequence)?.status).toBe("not_wired");
    expect(fieldValue(heartbeat.value.intervalMs)).toBe(500);
    expect(fieldValue(heartbeat.value.inputLeaseHeld)).toBe(false);
  });

  it("versions/selfState/evidence 作为整组缺口保留各自的状态与理由", () => {
    const decoded = decodeSnapshotPayload(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    expect(decoded.snapshot.versions.status).toBe("unavailable");
    expect(decoded.snapshot.selfState.status).toBe("unavailable");
    expect(decoded.snapshot.evidence.status).toBe("unknown");
    expect(decoded.snapshot.liveView.status).toBe("not_wired");
  });
});

describe("当前构建的活体网关字节：会话内 / 会话后（§2.97）", () => {
  it("两份捕获都零问题解码", () => {
    for (const wire of [REAL_IN_SESSION_SNAPSHOT_WIRE, REAL_AFTER_SESSION_SNAPSHOT_WIRE]) {
      const decoded = decodeSnapshotPayload(wire, "gateway");
      if (!decoded.ok) throw new Error(`issues: ${decoded.issues.join(" | ")}`);
      expect(decoded.snapshot.schemaVersion).toBe(SNAPSHOT_SCHEMA_VERSION);
    }
  });

  it("会话中：两条链路都 connected、世界已入服，租约与状态仍是跨容器的具名缺口", () => {
    const decoded = decodeSnapshotPayload(REAL_IN_SESSION_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const snapshot = decoded.snapshot;
    expect(mustKnow(snapshot.kinId, "kinId")).toBe("kin-lan87b-join");
    expect(mustKnow(snapshot.bridgeLink, "bridgeLink")).toBe("connected");
    expect(mustKnow(snapshot.serverLink, "serverLink")).toBe("connected");
    expect(fieldValue(mustKnow(snapshot.world, "world").joined)).toBe(true);
    // §2.96.6 留下的两格：被操作的客户端活在另一个容器里，网关的存活探针取不到它的 pid，
    // 所以会话进行中 runtimeState 仍是 idle、租约仍读 false。这里按原样钉住，不粉饰。
    expect(mustKnow(snapshot.runtimeState, "runtimeState")).toBe("idle");
    expect(fieldValue(mustKnow(snapshot.bridgeHeartbeat, "bridgeHeartbeat").inputLeaseHeld)).toBe(false);
    expect(snapshot.evidence.status).toBe("unknown");
    expect(snapshot.versions.status).toBe("unavailable");
  });

  it("会话后：链路回落 disconnected、已入服转 false，封证与版本改由清单作答", () => {
    const decoded = decodeSnapshotPayload(REAL_AFTER_SESSION_SNAPSHOT_WIRE, "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const snapshot = decoded.snapshot;
    expect(mustKnow(snapshot.bridgeLink, "bridgeLink")).toBe("disconnected");
    expect(mustKnow(snapshot.serverLink, "serverLink")).toBe("disconnected");
    expect(fieldValue(mustKnow(snapshot.world, "world").joined)).toBe(false);

    const evidence = mustKnow(snapshot.evidence, "evidence");
    expect(fieldValue(evidence.runId)).toBe("c131e8e782954991bf13d2c2ba4c1742");
    expect(fieldValue(evidence.attempt)).toBe(7);
    expect(fieldValue(evidence.bundleDigest)).toBe("ae6a52e4536d6168edad88bdbdc4117e32806e0e21a271106fcbdcd5425e9472");
    expect(fieldGap(evidence.sealedAt)?.status).toBe("not_wired");

    const versions = mustKnow(snapshot.versions, "versions");
    expect(fieldValue(versions.runtime)).toBe("1.20.1");
    expect(fieldValue(versions.fabricLoader)).toBe("0.19.5");
    expect(fieldValue(versions.java)).toContain("Temurin-21.0.12.1+1");
    expect(fieldGap(versions.bridge)?.status).toBe("not_wired");
    expect(fieldGap(versions.clientBundle)?.status).toBe("not_wired");
  });

  it("同一 Kin 根的两份字节在派生字段上真的相反：链路断言不是恒真", () => {
    const inSession = decodeSnapshotPayload(REAL_IN_SESSION_SNAPSHOT_WIRE, "gateway");
    const closed = decodeSnapshotPayload(REAL_AFTER_SESSION_SNAPSHOT_WIRE, "gateway");
    if (!inSession.ok || !closed.ok) throw new Error("两份捕获都应解码成功");
    expect(inSession.snapshot.bridgeLink.value).not.toBe(closed.snapshot.bridgeLink.value);
    expect(inSession.snapshot.serverLink.value).not.toBe(closed.snapshot.serverLink.value);
    expect(inSession.snapshot.evidence.status).not.toBe(closed.snapshot.evidence.status);
    // 具名值只出现在自己那份里：把它们写反了就抓不住。
    expect(closed.snapshot.bridgeLink.value).toBe("disconnected");
  });
});

describe("信封与组内成员的判别式（失败关闭，不补默认值）", () => {
  it("抽掉任一封面的 sourceRef ⇒ 整读判 contract_mismatch（§6.2）", () => {
    for (const field of ["session", "world", "bridgeHeartbeat", "kinId"] as const) {
      const wire = realWire();
      delete (wire[field] as Record<string, unknown>).sourceRef;
      const decoded = decodeSnapshotPayload(wire, "gateway");
      expect(decoded.ok, field).toBe(false);
      if (!decoded.ok) expect(decoded.issues.join("；"), field).toContain("provenance");
    }
  });

  it("组内成员换成 {value: null} ⇒ 拒绝，而不是降级为 null 或默认值", () => {
    const wire = realWire();
    ((wire.session as Record<string, unknown>).value as Record<string, unknown>).generation = wireFilled(null);
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("session.generation");
  });

  it("组内成员整体消失 ⇒ 拒绝", () => {
    const wire = realWire();
    delete ((wire.session as Record<string, unknown>).value as Record<string, unknown>).pid;
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("session.pid");
  });

  it("成员同时给出 value 与 gap ⇒ 拒绝（一个成员不能既是值又是缺口）", () => {
    const wire = realWire();
    ((wire.session as Record<string, unknown>).value as Record<string, unknown>).generation = {
      value: 1,
      gap: { status: "not_wired", reason: "x" },
    };
    expect(decodeSnapshotPayload(wire, "gateway").ok).toBe(false);
  });

  it("成员缺口没有理由 ⇒ 拒绝", () => {
    const wire = realWire();
    ((wire.session as Record<string, unknown>).value as Record<string, unknown>).mode = { gap: { status: "not_wired", reason: "" } };
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("session.mode");
  });

  it("runtimeState 给出 paused ⇒ 拒绝：Core 的 ObservedState 只有三值，paused/recovering 无载体（契约 §3）", () => {
    const wire = realWire();
    (wire.runtimeState as Record<string, unknown>).value = "paused";
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("runtimeState");
  });

  it("known 组给出 dimension/guiOpen ⇒ 拒绝：被撤下的 C 档字段不能借道回来", () => {
    const wire = realWire();
    (wire.selfState as Record<string, unknown>).value = { health: 20, food: 20, guiOpen: false };
    expect(decodeSnapshotPayload(wire, "gateway").ok).toBe(false);
  });

  it.each([
    { health: -1, food: 10 },
    { health: 20, food: -1 },
    { health: 20, food: 21 },
    { health: 20, food: 3.5 },
  ])("拒绝不可能的 HUD 数值 %j", (value) => {
    const wire = realWire();
    (wire.selfState as Record<string, unknown>).value = value;
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("selfState.value");
  });

  it.each([
    { health: 0, food: 0 },
    { health: 17.5, food: 20 },
    { health: 40, food: 10 },
  ])("保留合法 HUD 数值，不假设最大生命固定为 20：%j", (value) => {
    const wire = realWire();
    (wire.selfState as Record<string, unknown>).value = value;
    expect(decodeSnapshotPayload(wire, "gateway").ok).toBe(true);
  });

  it("缺口状态没有理由的顶层信封 ⇒ 拒绝（§2.2 第 2 条）", () => {
    const wire = realWire();
    wire.evidence = { status: "unknown", value: null, sourceRef: "core://x", observedAt: null, staleAfterMs: null };
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("evidence.reason");
  });
});

describe("skillSteps 组：缺组的旧字节、带组的新字节与成员判别", () => {
  /** 当前 Gateway 快照（`build_snapshot` 的 skillSteps 组）按 `readmodel.py` 形状落在旧捕获上。 */
  function withSkillSteps(wire: Record<string, unknown>, value: Record<string, unknown>): Record<string, unknown> {
    const patched = cloneWire(wire);
    patched.skillSteps = {
      status: "known",
      // 成员对象也深拷贝一份：变异测试改的是拷贝，绝不允许把传入的常量（如 FAILED_STEP）本身写脏。
      value: cloneWire(value),
      sourceRef: "core://status/kin-01/skillSteps",
      observedAt: "2000-01-01T00:00:00Z",
      staleAfterMs: null,
    };
    return patched;
  }

  const FAILED_STEP: Record<string, unknown> = {
    goal: wireFilled("先挖到木头，再合成木镐"),
    stepIndex: wireFilled(2),
    skill: wireFilled("craft"),
    result: wireFilled("FAILED"),
    reason: wireFilled("SCREEN_NOT_CONFIRMED"),
    attribution: wireFilled("ACTION_NOT_EFFECTIVE"),
    decisionSource: wireFilled("DECISION_FROM_MODEL"),
    modelRefusal: wireGapField("unavailable", "模型作答了这一步：model_refusal 是空串，没有拒止可报。"),
    stepCount: wireFilled(2),
    modelCost: wireGapField(
      "not_wired",
      "调用花费（model_calls / model_spent_micro / model_cap_refusals）只在 run document 的 mind 段里记录，" +
        "技能步行不携带；未封的 run 只读面取不到，封证后也要读 bundle 里的 run document，本投影不解析它。",
    ),
    modelConfig: wireGapField(
      "not_wired",
      "模型配置状态（model_enabled 与所配置的 provider）与花费同处：只在 run document 的 mind 段里记录，" +
        "台账行不携带，本投影只读台账与已封 bundle 的清单。",
    ),
  };

  it("三份历史捕获没有 skillSteps 组 ⇒ 仍零问题解码，并合成具名的组级 not_wired 缺口", () => {
    for (const wire of [REAL_JOINED_RUN_SNAPSHOT_WIRE, REAL_IN_SESSION_SNAPSHOT_WIRE, REAL_AFTER_SESSION_SNAPSHOT_WIRE]) {
      expect("skillSteps" in wire, "捕获必须保持逐字原样：本不该有这个组").toBe(false);
      const decoded = decodeSnapshotPayload(wire, "gateway");
      if (!decoded.ok) throw new Error(`issues: ${decoded.issues.join(" | ")}`);
      const group = decoded.snapshot.skillSteps;
      expect(group.status).toBe("not_wired");
      if (isKnown(group)) throw new Error("缺组字节应合成为缺口");
      expect(group.reason).toContain("skillSteps");
      expect(group.sourceRef).toBe("snapshot://absent/skillSteps");
    }
  });

  it("带组的当前字节逐成员解码：值照收，按构造为空处以具名缺口而非默认值", () => {
    const decoded = decodeSnapshotPayload(withSkillSteps(realWire(), FAILED_STEP), "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const group = mustKnow(decoded.snapshot.skillSteps, "skillSteps");
    expect(fieldValue(group.goal)).toBe("先挖到木头，再合成木镐");
    expect(fieldValue(group.stepIndex)).toBe(2);
    expect(fieldValue(group.result)).toBe("FAILED");
    expect(fieldValue(group.reason)).toBe("SCREEN_NOT_CONFIRMED");
    expect(fieldValue(group.decisionSource)).toBe("DECISION_FROM_MODEL");
    expect(fieldGap(group.modelRefusal)?.status).toBe("unavailable");
    expect(fieldValue(group.modelCost)).toBeNull();
    expect(fieldGap(group.modelConfig)?.status).toBe("not_wired");
    expect(fieldGap(group.modelCost)?.reason).toContain("run document");
    // 向后兼容：FAILED_STEP 这份字节早于 behaviorParameters 成员，缺席要合成具名缺口、
    // 而不是把整组判成解码失败——面板因此仍能读到其余十一名成员。
    expect(fieldValue(group.behaviorParameters)).toBeNull();
    expect(fieldGap(group.behaviorParameters)?.status).toBe("not_wired");
    expect(fieldGap(group.behaviorParameters)?.reason).toContain("行为参数");
  });

  it("脚本运行：goal 是 unavailable 具名缺口，拒止标注「不经过模型」，不冒充空值", () => {
    const scripted = { ...FAILED_STEP };
    scripted.goal = wireGapField("unavailable", "这是一次 --skill-plan 脚本运行：操作者写下的序列按构造没有自主目标，Core 把 goal 记为空串。");
    scripted.decisionSource = wireFilled("OPERATOR_PLAN");
    scripted.modelRefusal = wireGapField("unavailable", "这一步的决策来源不经过模型（DECISION_FROM_LOCAL 或 OPERATOR_PLAN）：拒止概念不适用。");
    const decoded = decodeSnapshotPayload(withSkillSteps(realWire(), scripted), "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    const group = mustKnow(decoded.snapshot.skillSteps, "skillSteps");
    expect(fieldValue(group.goal)).toBeNull();
    expect(fieldGap(group.goal)?.status).toBe("unavailable");
    expect(fieldGap(group.goal)?.reason).toContain("--skill-plan");
    expect(fieldGap(group.modelRefusal)?.reason).toContain("不经过模型");
  });

  it("成员判别：抽掉 stepIndex、缺口无理由、多出 action_id 都整读拒绝", () => {
    const missingMember = withSkillSteps(realWire(), FAILED_STEP);
    delete ((missingMember.skillSteps as Record<string, unknown>).value as Record<string, unknown>).stepIndex;
    const missing = decodeSnapshotPayload(missingMember, "gateway");
    expect(missing.ok).toBe(false);
    if (!missing.ok) expect(missing.issues.join("；")).toContain("skillSteps.stepIndex");

    const reasonless = withSkillSteps(realWire(), FAILED_STEP);
    ((reasonless.skillSteps as Record<string, unknown>).value as Record<string, unknown>).modelCost = { gap: { status: "not_wired", reason: "" } };
    expect(decodeSnapshotPayload(reasonless, "gateway").ok).toBe(false);

    // §4 的恒规：action_id 属于台账内部标识，绝不允许出现在投影里——出现即契约不匹配。
    const withActionId = { ...FAILED_STEP, action_id: wireFilled("act-1") };
    const canary = decodeSnapshotPayload(withSkillSteps(realWire(), withActionId), "gateway");
    expect(canary.ok).toBe(false);
    if (!canary.ok) expect(canary.issues.join("；")).toContain("skillSteps.value");
  });

  it("Core 之后的新 result token 仍按原值渲染：不钉死三值枚举而把新 verdict 拒成整读失败", () => {
    const futureToken = { ...FAILED_STEP, result: wireFilled("INTERRUPTED") };
    const decoded = decodeSnapshotPayload(withSkillSteps(realWire(), futureToken), "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    expect(fieldValue(mustKnow(decoded.snapshot.skillSteps, "skillSteps").result)).toBe("INTERRUPTED");
  });

  it("behaviorParameters 有值：已封 bundle 解析出的脱敏参数原样解码为 value", () => {
    const withValue = { ...FAILED_STEP, behaviorParameters: wireFilled("quantity=4, target_item=minecraft:stick") };
    const decoded = decodeSnapshotPayload(withSkillSteps(realWire(), withValue), "gateway");
    if (!decoded.ok) throw new Error("应解码成功");
    expect(fieldValue(mustKnow(decoded.snapshot.skillSteps, "skillSteps").behaviorParameters)).toBe(
      "quantity=4, target_item=minecraft:stick",
    );
  });

  it("behaviorParameters 具名缺口照收；成员存在却畸形 ⇒ 整读拒绝（向后兼容只放行缺席，不放行坏值）", () => {
    const asGap = {
      ...FAILED_STEP,
      behaviorParameters: wireGapField("not_wired", "行为参数只在已封 bundle 的 run document 里解析，未封的 run 只读面取不到。"),
    };
    const gapDecoded = decodeSnapshotPayload(withSkillSteps(realWire(), asGap), "gateway");
    if (!gapDecoded.ok) throw new Error("应解码成功");
    expect(fieldGap(mustKnow(gapDecoded.snapshot.skillSteps, "skillSteps").behaviorParameters)?.status).toBe("not_wired");

    const malformed = { ...FAILED_STEP, behaviorParameters: { value: null } };
    expect(decodeSnapshotPayload(withSkillSteps(realWire(), malformed), "gateway").ok).toBe(false);
  });
});

describe("alerts 信封（§5.3 ALERT_SOURCE_AMBIGUITY）", () => {
  it("not_wired 且理由为空 ⇒ 拒绝", () => {
    const decoded = decodeAlertsPayload({ status: "not_wired", reason: "", alerts: [] });
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("reason");
  });

  it("not_wired 且带理由与空数组 ⇒ 解码为「无告警源」信封", () => {
    const decoded = decodeAlertsPayload({ status: "not_wired", reason: "Core 无告警源。", alerts: [] });
    if (!decoded.ok) throw new Error("应解码成功");
    expect(decoded.envelope.status).toBe("not_wired");
    expect(decoded.envelope.alerts).toHaveLength(0);
  });

  it("真实 Gateway 的 alerts 信封可解码", () => {
    const decoded = decodeAlertsPayload(REAL_ALERTS_ENVELOPE_WIRE);
    if (!decoded.ok) throw new Error("应解码成功");
    expect(decoded.envelope.reason).toContain("无告警源");
  });

  it("裸数组不再被接受：alerts 必须走信封", () => {
    expect(decodeAlertsPayload([]).ok).toBe(false);
    expect(decodeAlertsPayload([{ alertId: "a" }]).ok).toBe(false);
  });

  it("known + 空数组 ⇒ 「没有告警」（与无告警源不同的事实）", () => {
    const decoded = decodeAlertsPayload({ status: "known", alerts: [] });
    if (!decoded.ok) throw new Error("应解码成功");
    expect(decoded.envelope.status).toBe("known");
    expect(decoded.envelope.alerts).toHaveLength(0);
  });

  it("非 known 状态却携带条目 ⇒ 拒绝：自相矛盾的读数不渲染", () => {
    const item = {
      alertId: "al_1",
      severity: "warning",
      state: "active",
      component: "gateway",
      title: "t",
      detail: null,
      firstSeenAt: "2000-01-01T00:00:00Z",
      lastSeenAt: null,
      sourceRef: "core://status/kin-01/alerts",
    };
    expect(decodeAlertsPayload({ status: "unknown", reason: "r", alerts: [item] }).ok).toBe(false);
  });
});

describe("接线钉住契约字面量（对照 gateway/readmodel.py，逐字）", () => {
  it("三条只读 GET 路径与 Gateway 常量逐字一致", () => {
    // Literals as written in `gateway/readmodel.py`: SNAPSHOT_PATH / TIMELINE_PATH / ALERTS_PATH.
    expect(READ_ENDPOINTS).toEqual({
      snapshot: "/api/v1/dashboard/snapshot",
      timeline: "/api/v1/dashboard/timeline",
      alerts: "/api/v1/dashboard/alerts",
    });
  });

  it("版本字面量与超时按 §2.1/§2.3 冻结", () => {
    expect(SNAPSHOT_SCHEMA_VERSION).toBe("kin-dashboard-readmodel/1.0.0");
    expect(DEFAULT_TIMEOUT_MS).toBe(3_000);
  });
});
