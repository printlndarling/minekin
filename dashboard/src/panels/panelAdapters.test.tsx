import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createGatewayAdapter, READ_ENDPOINTS } from "../adapters/gatewayAdapter";
import { createMockAdapter } from "../adapters/mockAdapter";
import { buildMockBundle, type MockScenarioId } from "../fixtures/mockFixtures";
import type { AlertsEnvelope, KinSnapshot } from "../domain/model";
import type { KinReadAdapter, ReadResult } from "../domain/adapter";
import type { DataSourceKind } from "../domain/signals";
import { AlertsPanel } from "./AlertsPanel";
import { OverviewPanel } from "./OverviewPanel";
import { TimelinePanel } from "./TimelinePanel";

/**
 * One table, both adapters: every wire document is served through the gateway
 * adapter (fetch stub) AND through the mock adapter, and both must produce the
 * same decoded readings and the same rendered panels. This is the structural
 * guarantee that mock never drifts from the gateway contract path.
 */

const SHARED_SCENARIOS: readonly MockScenarioId[] = [
  "healthy_run_07",
  "stale_observations",
  "bridge_disconnected",
  "fields_unknown",
  "permission_restricted",
];

const originalFetch = globalThis.fetch;

// The mock adapter stamps `Date.now()` at read time and the fetch stub stamps it at
// install time; freezing the clock makes both sides see byte-identical documents,
// so the drift check compares decoding, not milliseconds.
const FIXED_NOW = Date.parse("2026-09-26T12:00:00.000Z");

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  vi.useRealTimers();
  globalThis.fetch = originalFetch;
});

/** The same wire bytes the mock adapter reads locally, served as gateway responses. */
function serveWire(scenario: MockScenarioId): void {
  const bundle = buildMockBundle(scenario, Date.now());
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname;
    const data =
      path === READ_ENDPOINTS.snapshot ? bundle.snapshot
      : path === READ_ENDPOINTS.timeline ? bundle.timeline
      : path === READ_ENDPOINTS.alerts ? bundle.alerts
      : null;
    if (data === null) return new Response(JSON.stringify({ error: "not found" }), { status: 404 });
    return new Response(JSON.stringify(data), { status: 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
}

function makeAdapters(scenario: MockScenarioId): { mock: KinReadAdapter; gateway: KinReadAdapter } {
  serveWire(scenario);
  return {
    mock: createMockAdapter(scenario, 0),
    gateway: createGatewayAdapter({ baseUrl: "http://gateway.test", timeoutMs: 1_000 }),
  };
}

function mustBeOk<T>(result: ReadResult<T>): T {
  if (!result.ok) throw new Error(`读取失败：${result.failure.kind} ${result.failure.message}`);
  return result.value;
}

/** Only the provenance `source` differs by transport; everything else must match. */
function withSource(snapshot: KinSnapshot, source: DataSourceKind): KinSnapshot {
  const patched: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(snapshot)) {
    patched[key] = key === "schemaVersion" ? value : { ...(value as object), source };
  }
  return patched as unknown as KinSnapshot;
}

describe.each(SHARED_SCENARIOS)("同一套面板测试 · %s", (scenario) => {
  it("mock 与 gateway 解码同一字节得到同一读数（仅 provenance 来源不同）", async () => {
    const adapters = makeAdapters(scenario);
    const mockSnap = mustBeOk(await adapters.mock.snapshot());
    const gatewaySnap = mustBeOk(await adapters.gateway.snapshot());
    expect(withSource(mockSnap, "gateway")).toEqual(gatewaySnap);

    const mockTimeline = mustBeOk(await adapters.mock.timeline({ limit: 50, kinds: [] }));
    const gatewayTimeline = mustBeOk(await adapters.gateway.timeline({ limit: 50, kinds: [] }));
    expect(gatewayTimeline).toEqual(mockTimeline);

    const mockAlerts = mustBeOk(await adapters.mock.alerts());
    const gatewayAlerts = mustBeOk(await adapters.gateway.alerts());
    expect(gatewayAlerts).toEqual(mockAlerts);
  });

  it("两个适配器渲染出完全相同的面板文本", async () => {
    const adapters = makeAdapters(scenario);
    const snapshot = mustBeOk(await adapters.gateway.snapshot());
    const events = mustBeOk(await adapters.gateway.timeline({ limit: 50, kinds: [] }));
    const envelope = mustBeOk(await adapters.gateway.alerts());
    const nowMs = Date.now();

    const gatewayView = render(
      <div>
        <OverviewPanel snapshot={snapshot} nowMs={nowMs} />
        <TimelinePanel items={events} isLoading={false} failure={null} />
        <AlertsPanel envelope={envelope} isLoading={false} failure={null} />
      </div>,
    ).container;

    const mockSnapshotValue = mustBeOk(await adapters.mock.snapshot());
    const mockEvents = mustBeOk(await adapters.mock.timeline({ limit: 50, kinds: [] }));
    const mockEnvelope = mustBeOk(await adapters.mock.alerts());
    const mockView = render(
      <div>
        <OverviewPanel snapshot={mockSnapshotValue} nowMs={nowMs} />
        <TimelinePanel items={mockEvents} isLoading={false} failure={null} />
        <AlertsPanel envelope={mockEnvelope} isLoading={false} failure={null} />
      </div>,
    ).container;

    expect(mockView.textContent).toBe(gatewayView.textContent);
  });
});

describe("alerts 的三种事实（两个适配器同表）", () => {
  async function envelopeFromBoth(scenario: MockScenarioId): Promise<{ mock: AlertsEnvelope; gateway: AlertsEnvelope }> {
    const adapters = makeAdapters(scenario);
    return {
      mock: mustBeOk(await adapters.mock.alerts()),
      gateway: mustBeOk(await adapters.gateway.alerts()),
    };
  }

  it("有源为空 ⇒ 「没有告警」；无源 ⇒ 「无告警源」——两者是不同的 DOM", async () => {
    const emptySource = await envelopeFromBoth("stale_observations");
    const noSource = await envelopeFromBoth("fields_unknown");
    expect(emptySource.mock).toEqual(emptySource.gateway);
    expect(noSource.mock).toEqual(noSource.gateway);

    const emptyRender = render(<AlertsPanel envelope={emptySource.gateway} isLoading={false} failure={null} />);
    expect(emptyRender.getByTestId("alerts-empty")).toHaveTextContent("没有告警");
    expect(emptyRender.queryByTestId("alerts-no-source")).toBeNull();
    const emptyText = emptyRender.container.textContent;
    emptyRender.unmount();

    const noSourceRender = render(<AlertsPanel envelope={noSource.gateway} isLoading={false} failure={null} />);
    expect(noSourceRender.getByTestId("alerts-no-source")).toHaveTextContent("无告警源");
    expect(noSourceRender.getByTestId("alerts-no-source")).toHaveTextContent("Core 无告警源");
    expect(noSourceRender.queryByTestId("alerts-empty")).toBeNull();
    // 同一个「0 条」，两种呈现：文本与结构都不相同。
    expect(noSourceRender.container.textContent).not.toBe(emptyText);
  });

  it("真实 Gateway 的 not_wired 信封渲染为「无告警源」而非「没有告警」", () => {
    render(
      <AlertsPanel
        envelope={{ status: "not_wired", reason: "Core 无告警源：只有台账事件与 run document 的拒止计数，哪些算告警属产品决定。", alerts: [] }}
        isLoading={false}
        failure={null}
      />,
    );
    expect(screen.getByTestId("alerts-no-source")).toBeInTheDocument();
    expect(screen.queryByTestId("alerts-empty")).toBeNull();
  });
});
