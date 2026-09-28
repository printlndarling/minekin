import { describe, expect, it } from "vitest";
import type { KinSnapshot } from "./model";
import { fieldValue, fieldGap } from "./model";
import { isKnown, type Signal } from "./signals";
import { buildMockBundle, MOCK_SCENARIOS, type MockScenarioId } from "../fixtures/mockFixtures";
import { decodeAlertsPayload, decodeSnapshotPayload, decodeTimelinePayload } from "../adapters/gatewayAdapter";

const NOW = Date.parse("2026-09-26T12:00:00.000Z");

function decodedSnapshot(scenario: MockScenarioId): KinSnapshot {
  const decoded = decodeSnapshotPayload(buildMockBundle(scenario, NOW).snapshot, "mock");
  // The mock ships wire-shaped bytes: if these ever stop decoding through the
  // gateway decoder, mock and gateway have drifted and this read must fail loud.
  if (!decoded.ok) throw new Error(`${scenario}: ${decoded.issues.join(" | ")}`);
  return decoded.snapshot;
}

function signals(snapshot: KinSnapshot): readonly (Signal<unknown> & { label: string })[] {
  return [
    { label: "kinId", ...snapshot.kinId },
    { label: "runtimeState", ...snapshot.runtimeState },
    { label: "bridgeLink", ...snapshot.bridgeLink },
    { label: "serverLink", ...snapshot.serverLink },
    { label: "session", ...snapshot.session },
    { label: "world", ...snapshot.world },
    { label: "versions", ...snapshot.versions },
    { label: "bridgeHeartbeat", ...snapshot.bridgeHeartbeat },
    { label: "selfState", ...snapshot.selfState },
    { label: "evidence", ...snapshot.evidence },
    { label: "liveView", ...snapshot.liveView },
  ] as unknown as readonly (Signal<unknown> & { label: string })[];
}

describe("mock fixtures 的自述性", () => {
  it("覆盖全部场景，且每个场景的每个信封都声明为模拟来源", () => {
    expect(MOCK_SCENARIOS.length).toBeGreaterThan(4);
    for (const scenario of MOCK_SCENARIOS) {
      const snapshot = decodedSnapshot(scenario.id);
      for (const signal of signals(snapshot)) {
        expect(signal.source, `${scenario.id}.${signal.label}`).toBe("mock");
        expect(signal.sourceRef).toContain(`mock://scenario/${scenario.id}/`);
      }
    }
  });

  it("正常场景读数新鲜，陈旧场景超出预算", () => {
    const healthy = decodedSnapshot("healthy_run_07");
    if (!isKnown(healthy.runtimeState)) throw new Error("healthy 场景应有已知状态");
    expect(healthy.runtimeState.value).toBe("running");
    expect(NOW - Date.parse(healthy.runtimeState.observedAt ?? "")).toBeLessThan(15_000);

    const stale = decodedSnapshot("stale_observations");
    if (!isKnown(stale.runtimeState)) throw new Error("stale 场景仍保留最后一次读数");
    expect(NOW - Date.parse(stale.runtimeState.observedAt ?? "")).toBeGreaterThan(stale.runtimeState.staleAfterMs ?? 0);
  });

  it("C 档成员在 mock 里同样是带理由的缺口，不发明值", () => {
    const snapshot = decodedSnapshot("healthy_run_07");
    if (!isKnown(snapshot.session) || !isKnown(snapshot.world) || !isKnown(snapshot.bridgeHeartbeat)) {
      throw new Error("healthy 场景的组应是 known");
    }
    expect(fieldGap(snapshot.session.value.mode)?.status).toBe("not_wired");
    expect(fieldGap(snapshot.world.value.resolvedVersion)?.status).toBe("not_wired");
    expect(fieldGap(snapshot.world.value.epoch)?.status).toBe("not_wired");
    expect(fieldGap(snapshot.world.value.worldContext)?.status).toBe("not_wired");
    expect(fieldGap(snapshot.world.value.profileName)?.status).toBe("not_wired");
    expect(fieldGap(snapshot.bridgeHeartbeat.value.lastSequence)?.status).toBe("not_wired");
    expect(fieldValue(snapshot.world.value.joined)).toBe(true);
    expect(fieldValue(snapshot.bridgeHeartbeat.value.intervalMs)).toBe(500);
    // 撤下的字段不能借道回来：selfState 只有 health/food。
    if (!isKnown(snapshot.selfState)) throw new Error("healthy 场景 selfState 应是 known");
    expect(snapshot.selfState.value).toEqual({ health: 17.5, food: 14 });
  });

  it("失联场景把状态判为未定并撤回世界读数", () => {
    const snapshot = decodedSnapshot("bridge_disconnected");
    expect(snapshot.runtimeState.status === "known" && snapshot.runtimeState.value).toBe("unresolved");
    expect(snapshot.bridgeLink.status === "known" && snapshot.bridgeLink.value).toBe("disconnected");
    expect(snapshot.bridgeHeartbeat.status).toBe("unavailable");
    expect(snapshot.selfState.status).toBe("unknown");
    const heartbeatReason = isKnown(snapshot.bridgeHeartbeat) ? "" : snapshot.bridgeHeartbeat.reason;
    expect(heartbeatReason).toContain("心跳");
  });

  it("无真源场景显示缺口而不是默认值", () => {
    const snapshot = decodedSnapshot("fields_unknown");
    for (const label of ["session", "world", "selfState", "evidence", "bridgeHeartbeat"] as const) {
      expect(["unknown", "unavailable"], label).toContain(snapshot[label].status);
    }
    expect(snapshot.kinId.status).toBe("known");
  });

  it("无权限场景把敏感读数标为 permission_denied", () => {
    const snapshot = decodedSnapshot("permission_restricted");
    expect(snapshot.world.status).toBe("permission_denied");
    expect(snapshot.evidence.status).toBe("permission_denied");
  });

  it("任何场景都不会宣称 Live View 可用", () => {
    for (const scenario of MOCK_SCENARIOS.map((s) => s.id) as MockScenarioId[]) {
      const liveView = decodedSnapshot(scenario).liveView;
      expect(isKnown(liveView), scenario).toBe(false);
      expect(["not_wired", "permission_denied"], scenario).toContain(liveView.status);
    }
  });

  it("告警信封覆盖三种事实：有条目 / 有源为空 / 无源", () => {
    const withItems = decodeAlertsPayload(buildMockBundle("healthy_run_07", NOW).alerts);
    if (!withItems.ok) throw new Error("应解码成功");
    expect(withItems.envelope.status).toBe("known");
    expect(withItems.envelope.alerts.length).toBeGreaterThan(0);

    const emptySource = decodeAlertsPayload(buildMockBundle("stale_observations", NOW).alerts);
    if (!emptySource.ok) throw new Error("应解码成功");
    expect(emptySource.envelope.status).toBe("known");
    expect(emptySource.envelope.alerts).toHaveLength(0);

    const noSource = decodeAlertsPayload(buildMockBundle("fields_unknown", NOW).alerts);
    if (!noSource.ok) throw new Error("应解码成功");
    expect(noSource.envelope.status).toBe("not_wired");
    expect(noSource.envelope.reason).toContain("无告警源");
    expect(noSource.envelope.alerts).toHaveLength(0);
  });

  it("时间线全部条目可解码且带 mock 出处", () => {
    for (const scenario of MOCK_SCENARIOS.map((s) => s.id) as MockScenarioId[]) {
      const decoded = decodeTimelinePayload(buildMockBundle(scenario, NOW).timeline);
      if (!decoded.ok) throw new Error(`${scenario}: ${decoded.issues.join(" | ")}`);
      for (const event of decoded.events) {
        expect(event.sourceRef, scenario).toContain(`mock://scenario/${scenario}/`);
      }
    }
  });
});
