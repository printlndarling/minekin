import { describe, expect, it } from "vitest";
import type { KinSnapshot } from "./model";
import { isKnown, type Signal } from "./signals";
import { buildMockBundle, MOCK_SCENARIOS, type MockScenarioId } from "../fixtures/mockFixtures";

const NOW = Date.parse("2026-09-26T12:00:00.000Z");

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
  it("覆盖全部场景，且每个场景都声明为模拟来源", () => {
    expect(MOCK_SCENARIOS.length).toBeGreaterThan(4);
    for (const scenario of MOCK_SCENARIOS) {
      const bundle = buildMockBundle(scenario.id, NOW);
      for (const signal of signals(bundle.snapshot)) {
        expect(signal.source, `${scenario.id}.${signal.label}`).toBe("mock");
        expect(signal.sourceRef).toContain(`mock://scenario/${scenario.id}/`);
      }
    }
  });

  it("正常场景读数新鲜，陈旧场景超出预算", () => {
    const healthy = buildMockBundle("healthy_run_07", NOW).snapshot;
    if (!isKnown(healthy.runtimeState)) throw new Error("healthy 场景应有已知状态");
    expect(healthy.runtimeState.value).toBe("running");
    expect(NOW - Date.parse(healthy.runtimeState.observedAt ?? "")).toBeLessThan(15_000);

    const stale = buildMockBundle("stale_observations", NOW).snapshot;
    if (!isKnown(stale.runtimeState)) throw new Error("stale 场景仍保留最后一次读数");
    expect(NOW - Date.parse(stale.runtimeState.observedAt ?? "")).toBeGreaterThan(stale.runtimeState.staleAfterMs ?? 0);
  });

  it("失联场景把状态判为未定并撤回世界读数", () => {
    const snapshot = buildMockBundle("bridge_disconnected", NOW).snapshot;
    expect(snapshot.runtimeState.status === "known" && snapshot.runtimeState.value).toBe("unresolved");
    expect(snapshot.bridgeLink.status === "known" && snapshot.bridgeLink.value).toBe("disconnected");
    expect(snapshot.bridgeHeartbeat.status).toBe("unavailable");
    expect(snapshot.selfState.status).toBe("unknown");
    const heartbeatReason = isKnown(snapshot.bridgeHeartbeat) ? "" : snapshot.bridgeHeartbeat.reason;
    expect(heartbeatReason).toContain("心跳");
  });

  it("无真源场景显示缺口而不是默认值", () => {
    const snapshot = buildMockBundle("fields_unknown", NOW).snapshot;
    for (const label of ["session", "world", "selfState", "evidence", "bridgeHeartbeat"] as const) {
      expect(snapshot[label].status, label).toBe("unknown");
    }
    expect(snapshot.kinId.status).toBe("known");
  });

  it("无权限场景把敏感读数标为 permission_denied", () => {
    const snapshot = buildMockBundle("permission_restricted", NOW).snapshot;
    expect(snapshot.world.status).toBe("permission_denied");
    expect(snapshot.evidence.status).toBe("permission_denied");
  });

  it("任何场景都不会宣称 Live View 可用", () => {
    for (const scenario of MOCK_SCENARIOS.map((s) => s.id) as MockScenarioId[]) {
      const liveView = buildMockBundle(scenario, NOW).snapshot.liveView;
      expect(isKnown(liveView), scenario).toBe(false);
      expect(["not_wired", "permission_denied"], scenario).toContain(liveView.status);
    }
  });
});
