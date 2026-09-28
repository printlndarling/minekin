import {
  fail,
  ok,
  type AdapterDescriptor,
  type KinReadAdapter,
  type ReadResult,
  type TimelineQuery,
} from "../domain/adapter";
import type { AlertsEnvelope, KinSnapshot, TimelineEvent } from "../domain/model";
import { MOCK_SCENARIOS, buildMockBundle, type MockScenarioId } from "../fixtures/mockFixtures";
import { decodeAlertsPayload, decodeSnapshotPayload, decodeTimelinePayload } from "./gatewayAdapter";

/**
 * Scripted stand-in for the Gateway read API. It produces wire-shaped documents
 * and feeds them through the SAME decoders the gateway adapter uses, so a mock
 * reading and a gateway reading of the same bytes cannot drift. A fixture that
 * ever fails to decode is reported as `contract_mismatch`, not rendered anyway.
 */
export function createMockAdapter(scenario: MockScenarioId, latencyMs: number): KinReadAdapter {
  const meta = MOCK_SCENARIOS.find((s) => s.id === scenario);
  const describe = (): AdapterDescriptor => ({
    id: `mock:${scenario}`,
    kind: "mock",
    label: `模拟数据 · ${meta?.label ?? scenario}`,
    mock: true,
    note: meta?.note ?? "无 Gateway 基址：使用明确标注的模拟读数，绝不当作活体 Kin 呈现。",
  });

  const settle = async (): Promise<void> => {
    if (latencyMs <= 0) return;
    await new Promise<void>((resolve) => {
      setTimeout(resolve, latencyMs);
    });
  };

  return {
    describe,
    async snapshot(signal?: AbortSignal): Promise<ReadResult<KinSnapshot>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：Gateway 只读接口不可达。");
      }
      const decoded = decodeSnapshotPayload(buildMockBundle(scenario, Date.now()).snapshot, "mock");
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟数据与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.snapshot, "mock", `mock://scenario/${scenario}/snapshot`);
    },
    async timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：时间线读取失败。");
      }
      const decoded = decodeTimelinePayload(buildMockBundle(scenario, Date.now()).timeline);
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟数据与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      const wanted = query.kinds.length === 0 ? decoded.events : decoded.events.filter((e) => query.kinds.includes(e.kind));
      return ok(wanted.slice(0, Math.max(0, query.limit)), "mock", `mock://scenario/${scenario}/timeline`);
    },
    async alerts(signal?: AbortSignal): Promise<ReadResult<AlertsEnvelope>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：告警读取失败。");
      }
      const decoded = decodeAlertsPayload(buildMockBundle(scenario, Date.now()).alerts);
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟数据与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.envelope, "mock", `mock://scenario/${scenario}/alerts`);
    },
  };
}
