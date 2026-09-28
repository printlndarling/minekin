import { describe, expect, it } from "vitest";
import { decodeAlertsPayload, decodeSnapshotPayload, READ_ENDPOINTS } from "./gatewayAdapter";
import { DEFAULT_TIMEOUT_MS } from "./config";
import { SNAPSHOT_SCHEMA_VERSION, fieldValue, fieldGap } from "../domain/model";
import { isKnown } from "../domain/signals";
import { cloneWire, wireFilled } from "../test/wireFixture";
import { REAL_ALERTS_ENVELOPE_WIRE, REAL_JOINED_RUN_SNAPSHOT_WIRE } from "../test/realGatewayWire";

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

  it("缺口状态没有理由的顶层信封 ⇒ 拒绝（§2.2 第 2 条）", () => {
    const wire = realWire();
    wire.evidence = { status: "unknown", value: null, sourceRef: "core://x", observedAt: null, staleAfterMs: null };
    const decoded = decodeSnapshotPayload(wire, "gateway");
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join("；")).toContain("evidence.reason");
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
