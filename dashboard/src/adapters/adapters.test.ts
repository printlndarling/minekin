import { describe, expect, it } from "vitest";
import { createMockAdapter } from "./mockAdapter";
import { createAdapter, DEFAULT_TIMEOUT_MS, parseDashboardConfig } from "./config";
import { createGatewayAdapter, decodeSnapshotPayload, READ_ENDPOINTS } from "./gatewayAdapter";
import { cloneWire } from "../test/wireFixture";
import { REAL_ALERTS_ENVELOPE_WIRE, REAL_JOINED_RUN_SNAPSHOT_WIRE, REAL_TIMELINE_WIRE } from "../test/realGatewayWire";
import { isKnown } from "../domain/signals";
import { fieldValue, type KinSnapshot } from "../domain/model";

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

describe("mock read adapter", () => {
  it("声明自己是模拟源，且从不返回真值语义", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const descriptor = adapter.describe();
    expect(descriptor.mock).toBe(true);
    expect(descriptor.kind).toBe("mock");
    const result = await adapter.snapshot();
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.source).toBe("mock");
  });

  it("read_failed 场景以失联结束，不给出半真半假的快照", async () => {
    const result = await createMockAdapter("read_failed", 0).snapshot();
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.failure.kind).toBe("disconnected");
  });

  it("按类型与上限过滤时间线", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const all = await adapter.timeline({ limit: 50, kinds: [] });
    expect(all.ok && all.value.length).toBeGreaterThan(3);
    const onlyInput = await adapter.timeline({ limit: 50, kinds: ["input"] });
    if (!onlyInput.ok) throw new Error("应成功");
    expect(onlyInput.value.length).toBeGreaterThan(0);
    expect(onlyInput.value.every((event) => event.kind === "input")).toBe(true);
    const capped = await adapter.timeline({ limit: 1, kinds: [] });
    if (!capped.ok) throw new Error("应成功");
    expect(capped.value).toHaveLength(1);
  });

  it("取消中的读取回报 cancelled", async () => {
    const controller = new AbortController();
    controller.abort();
    const result = await createMockAdapter("healthy_run_07", 0).snapshot(controller.signal);
    expect(!result.ok && result.failure.kind).toBe("cancelled");
  });
});

describe("gateway read adapter（冻结契约，失败关闭）", () => {
  it("未配置 base URL 时零网络调用并报告 not_configured", async () => {
    let calls = 0;
    const original = globalThis.fetch;
    globalThis.fetch = (() => {
      calls += 1;
      return Promise.resolve(jsonResponse({}));
    }) as typeof fetch;
    try {
      const adapter = createGatewayAdapter(null);
      expect(adapter.describe().mock).toBe(false);
      const snapshot = await adapter.snapshot();
      const alerts = await adapter.alerts();
      expect(!snapshot.ok && snapshot.failure.kind).toBe("not_configured");
      expect(!alerts.ok && alerts.failure.kind).toBe("not_configured");
      expect(calls).toBe(0);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("真实 Gateway 字节可解码为只读快照", async () => {
    const original = globalThis.fetch;
    const urls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      urls.push(String(input));
      return Promise.resolve(jsonResponse(REAL_JOINED_RUN_SNAPSHOT_WIRE));
    }) as typeof fetch;
    try {
      const adapter = createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000/", timeoutMs: 1_000 });
      const result = await adapter.snapshot();
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.source).toBe("gateway");
        const snapshot = result.value as KinSnapshot;
        expect(isKnown(snapshot.session)).toBe(true);
        if (isKnown(snapshot.session)) expect(fieldValue(snapshot.session.value.generation)).toBe(1);
        expect(snapshot.kinId.status).toBe("known");
      }
      // 传入带尾斜杠的 base URL，也必须只打一个斜杠。
      expect(urls).toEqual([`http://127.0.0.1:8000${READ_ENDPOINTS.snapshot}`]);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("真实 alerts 信封读取为信封而非裸数组", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () => jsonResponse(REAL_ALERTS_ENVELOPE_WIRE)) as typeof fetch;
    try {
      const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).alerts();
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.value.status).toBe("not_wired");
        expect(result.value.reason).toContain("无告警源");
        expect(result.value.alerts).toEqual([]);
      }
    } finally {
      globalThis.fetch = original;
    }
  });

  it("真实 timeline 数组读取", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () => jsonResponse(REAL_TIMELINE_WIRE)) as typeof fetch;
    try {
      const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).timeline({ limit: 50, kinds: [] });
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.value[0]?.sourceRef).toBe("ledger://kin-01/42");
    } finally {
      globalThis.fetch = original;
    }
  });

  it("抽掉一个 provenance 字段即整读判红（§6.2 判别式）", async () => {
    const wire = cloneWire(REAL_JOINED_RUN_SNAPSHOT_WIRE);
    delete (wire.session as Record<string, unknown>).sourceRef;
    const original = globalThis.fetch;
    globalThis.fetch = (async () => jsonResponse(wire)) as typeof fetch;
    try {
      const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).snapshot();
      expect(!result.ok && result.failure.kind).toBe("contract_mismatch");
      if (!result.ok) {
        expect(result.failure.message).toContain("session");
        expect(result.failure.message).toContain("provenance");
      }
    } finally {
      globalThis.fetch = original;
    }
  });

  it("HTTP 404 记为接口未实现，403 记为无权限，网络异常记为失联", async () => {
    const original = globalThis.fetch;
    try {
      const cases: readonly (() => Promise<Response> | Response)[] = [
        () => jsonResponse({ detail: "not found" }, 404),
        () => jsonResponse({ detail: "forbidden" }, 403),
        () => {
          throw new TypeError("fetch failed");
        },
      ];
      const expected = ["contract_mismatch", "permission_denied", "disconnected"] as const;
      for (const [index, behavior] of cases.entries()) {
        globalThis.fetch = (async () => await behavior()) as typeof fetch;
        const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).snapshot();
        expect(!result.ok && result.failure.kind, String(index)).toBe(expected[index]);
      }
      const decoded = decodeSnapshotPayload({ ...REAL_JOINED_RUN_SNAPSHOT_WIRE, schemaVersion: "kin-dashboard-readmodel/0.1.0-proposal" }, "gateway");
      expect(decoded.ok).toBe(false);
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("adapter 选择", () => {
  it("默认走真实 Gateway，fixture 要显式点名才用", () => {
    expect(parseDashboardConfig("")).toEqual({
      adapter: "gateway",
      scenario: "healthy_run_07",
      gatewayBaseUrl: null,
      latencyMs: 120,
    });
    expect(parseDashboardConfig("?scenario=bridge_disconnected").scenario).toBe("bridge_disconnected");
    expect(parseDashboardConfig("?scenario=nope").scenario).toBe("healthy_run_07");
    expect(parseDashboardConfig("?adapter=mock").adapter).toBe("mock");
    expect(parseDashboardConfig("?adapter=gateway&gateway=http://127.0.0.1:8000//").gatewayBaseUrl).toBe("http://127.0.0.1:8000");
    // 认不出的值留在真实档上：后台不能因为一次拼错就悄悄改用编造的 Kin。
    expect(parseDashboardConfig("?adapter=Gateway").adapter).toBe("gateway");
    expect(createAdapter(parseDashboardConfig("")).describe().id).toBe("gateway:unconfigured");
    expect(createAdapter(parseDashboardConfig("?adapter=gateway")).describe().id).toBe("gateway:unconfigured");
    expect(createAdapter(parseDashboardConfig("?adapter=mock")).describe().kind).toBe("mock");
  });

  it("超时按契约 §2.1 钉在 3000ms", () => {
    expect(DEFAULT_TIMEOUT_MS).toBe(3_000);
  });
});
