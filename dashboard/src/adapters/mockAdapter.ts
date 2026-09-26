import { fail, ok, type AdapterDescriptor, type KinReadAdapter, type ReadResult, type TimelineQuery } from "../domain/adapter";
import type { Alert, KinSnapshot, TimelineEvent } from "../domain/model";
import { buildMockBundle, MOCK_SCENARIOS, type MockScenarioId } from "../fixtures/mockFixtures";

function abortable<T>(work: () => T, signal?: AbortSignal): ReadResult<T> {
  if (signal?.aborted === true) {
    return fail("cancelled", "读取已取消。");
  }
  return ok(work(), "mock", "mock://adapter");
}

/**
 * Scripted stand-in for the future Gateway read API. It never claims to be live:
 * the descriptor is `mock: true` and every signal carries `source: "mock"`.
 */
export function createMockAdapter(scenario: MockScenarioId, latencyMs: number): KinReadAdapter {
  const meta = MOCK_SCENARIOS.find((s) => s.id === scenario);
  const describe = (): AdapterDescriptor => ({
    id: `mock:${scenario}`,
    kind: "mock",
    label: `模拟数据 · ${meta?.label ?? scenario}`,
    mock: true,
    note: meta?.note ?? "无 Gateway API：使用明确标注的模拟读数。",
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
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：Gateway 只读接口不可达（真实 Gateway 尚未存在）。");
      }
      return abortable(() => buildMockBundle(scenario, Date.now()).snapshot, signal);
    },
    async timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>> {
      await settle();
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：时间线读取失败。");
      }
      return abortable(() => {
        const events = buildMockBundle(scenario, Date.now()).timeline;
        const wanted = query.kinds.length === 0 ? events : events.filter((e) => query.kinds.includes(e.kind));
        return wanted.slice(0, Math.max(0, query.limit));
      }, signal);
    },
    async alerts(signal?: AbortSignal): Promise<ReadResult<readonly Alert[]>> {
      await settle();
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：告警读取失败。");
      }
      return abortable(() => buildMockBundle(scenario, Date.now()).alerts, signal);
    },
  };
}
