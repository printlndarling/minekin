import { describe, expect, it } from "vitest";
import { createMockAdapter } from "./mockAdapter";
import { createAdapter, parseDashboardConfig } from "./config";
import { createGatewayAdapter, decodeSnapshotPayload, PROPOSED_ENDPOINTS } from "./gatewayAdapter";
import { buildMockBundle } from "../fixtures/mockFixtures";
import { wireSnapshot } from "../test/wireFixture";
import { isKnown } from "../domain/signals";

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

describe("gateway read adapter（契约未冻结，失败关闭）", () => {
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
      const result = await adapter.snapshot();
      expect(!result.ok && result.failure.kind).toBe("not_configured");
      expect(calls).toBe(0);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("符合提议契约的响应可解码为只读快照", async () => {
    const wire = wireSnapshot(buildMockBundle("healthy_run_07", Date.now()).snapshot);
    const original = globalThis.fetch;
    const urls: string[] = [];
    globalThis.fetch = ((input: RequestInfo | URL) => {
      urls.push(String(input));
      return Promise.resolve(jsonResponse(wire));
    }) as typeof fetch;
    try {
      const adapter = createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000/", timeoutMs: 1_000 });
      const result = await adapter.snapshot();
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.source).toBe("gateway");
        expect(isKnown(result.value.session)).toBe(true);
        if (isKnown(result.value.session)) expect(result.value.session.value.generation).toBe(3);
        expect(result.value.kinId.status).toBe("known");
      }
      // 传入带尾斜杠的 base URL，也必须只打一个斜杠。
      expect(urls).toEqual([`http://127.0.0.1:8000${PROPOSED_ENDPOINTS.snapshot}`]);
    } finally {
      globalThis.fetch = original;
    }
  });

  it("契约不匹配时列出问题且不猜测字段", async () => {
    const wire = wireSnapshot(buildMockBundle("healthy_run_07", Date.now()).snapshot) as Record<string, unknown>;
    const broken = { ...wire, session: { status: "known", sourceRef: "x", observedAt: null, staleAfterMs: null, value: { sessionId: "s" } } };
    const original = globalThis.fetch;
    globalThis.fetch = (async () => jsonResponse(broken)) as typeof fetch;
    try {
      const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).snapshot();
      expect(!result.ok && result.failure.kind).toBe("contract_mismatch");
      if (!result.ok) expect(result.failure.message).toContain("session");
    } finally {
      globalThis.fetch = original;
    }
  });

  it("HTTP 404 记为接口未实现，403 记为无权限，网络异常记为失联", async () => {
    const original = globalThis.fetch;
    const snapshot = buildMockBundle("healthy_run_07", Date.now()).snapshot;
    const cases: readonly (() => Promise<Response> | Response)[] = [
      () => jsonResponse({ detail: "not found" }, 404),
      () => jsonResponse({ detail: "forbidden" }, 403),
      () => {
        throw new TypeError("fetch failed");
      },
    ];
    const expected = ["contract_mismatch", "permission_denied", "disconnected"] as const;
    try {
      for (const [index, behavior] of cases.entries()) {
        globalThis.fetch = (async () => await behavior()) as typeof fetch;
        const result = await createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1_000 }).snapshot();
        expect(!result.ok && result.failure.kind, String(index)).toBe(expected[index]);
      }
      const decoded = decodeSnapshotPayload({ ...wireSnapshot(snapshot), schemaVersion: "kin-dashboard-readmodel/0.0.9" });
      expect(decoded.ok).toBe(false);
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("adapter 选择", () => {
  it("默认使用 mock，URL 参数可切场景与网关", () => {
    expect(parseDashboardConfig("")).toEqual({
      adapter: "mock",
      scenario: "healthy_run_07",
      gatewayBaseUrl: null,
      latencyMs: 120,
    });
    expect(parseDashboardConfig("?scenario=bridge_disconnected").scenario).toBe("bridge_disconnected");
    expect(parseDashboardConfig("?scenario=nope").scenario).toBe("healthy_run_07");
    expect(parseDashboardConfig("?adapter=gateway&gateway=http://127.0.0.1:8000//").gatewayBaseUrl).toBe("http://127.0.0.1:8000");
    expect(createAdapter(parseDashboardConfig("")).describe().kind).toBe("mock");
    expect(createAdapter(parseDashboardConfig("?adapter=gateway")).describe().id).toBe("gateway:unconfigured");
  });
});
