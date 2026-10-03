import { describe, expect, it } from "vitest";
import { createMockAdapter } from "./mockAdapter";
import {
  CSRF_HEADER,
  SESSION_ENDPOINTS,
  createGatewayAdapter,
  decodeSessionPayload,
  decodeStopPayload,
} from "./gatewayAdapter";
import { SESSION_SCHEMA_VERSION } from "../domain/model";
import { buildMockSession, buildMockStopReport } from "../fixtures/mockFixtures";

/**
 * The session read + the third authorized write (a confirmed stop), tested at the adapter seam.
 * Like the identity/config tests these cases prove PARITY, not specific values: both adapters route
 * the read and the stop through the SAME decoders the Gateway uses, so a mock stop and a real stop
 * cannot drift into a panel that promises to end a session the server would refuse. The mock's
 * refusal ordering (CSRF-before-read → unknown field → confirm → idle) is lifted verbatim from
 * `gateway/session_control.py::stop_from_request`, so the named refusals below are exactly the shapes
 * the real server emits.
 */

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

async function withFetch<T>(impl: typeof fetch, run: () => Promise<T>): Promise<T> {
  const original = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await run();
  } finally {
    globalThis.fetch = original;
  }
}

describe("mock 会话读取与停止", () => {
  it("运行场景读到 running + stopAllowed，逐字段与共享解码器一致，且模型里没有 CSRF", async () => {
    const result = await createMockAdapter("healthy_run_07", 0).session();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.source).toBe("mock");
    expect(result.value.state).toBe("running");
    expect(result.value.stopAllowed).toBe(true);
    expect(result.value.availableControls).toEqual(["stop", "start"]);
    expect(result.value.unavailableControls.map((c) => c.verb)).toEqual(["pause", "resume"]);
    // The token lives in the wire document and the decoder output, never in SessionControlInfo.
    expect(JSON.stringify(result.value)).not.toContain("csrf");
  });

  it("失联场景读到 unresolved：仍可停，但会话状态如实为未定", async () => {
    const result = await createMockAdapter("bridge_disconnected", 0).session();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.state).toBe("unresolved");
    expect(result.value.stopAllowed).toBe(true);
  });

  it("空闲场景读到 idle：stopAllowed 为假", async () => {
    const result = await createMockAdapter("fields_unknown", 0).session();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.state).toBe("idle");
    expect(result.value.stopAllowed).toBe(false);
  });

  it("read_failed 场景会话读取以失联结束", async () => {
    const result = await createMockAdapter("read_failed", 0).session();
    expect(!result.ok && result.failure.kind).toBe("disconnected");
  });

  it("停止前先成功读取会话取得 CSRF，运行会话被干净停止并回报 stopped", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.session();
    const stopped = await adapter.stopSession({ confirm: true });
    expect(stopped.ok).toBe(true);
    if (!stopped.ok) return;
    expect(stopped.value.report.status).toBe("stopped");
    expect(stopped.value.report.outcome.terminated).toEqual([4242]);
    expect(stopped.value.report.release.released).toEqual([4242]);
  });

  it("未先读会话就停止：缺 CSRF，具名拒止", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    const result = await adapter.stopSession({ confirm: true });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("missing_or_bad_csrf_token");
  });

  it("未确认就停止：invalid_request，confirm 必须为真", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.session();
    const result = await adapter.stopSession({ confirm: false } as unknown as { confirm: true });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("invalid_request");
    expect(result.failure.message).toContain("confirmation");
  });

  it("混进未知字段：具名拒止并点名该字段，先于确认判定", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.session();
    const result = await adapter.stopSession({ confirm: true, force: true } as unknown as { confirm: true });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("invalid_request");
    expect(result.failure.message).toContain("force");
  });

  it("空闲会话请求停止：session_not_running，不动任何进程", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.session();
    const result = await adapter.stopSession({ confirm: true });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("session_not_running");
  });

  it("未定会话的停止回报 blocked：未确认释放不折成干净停止", async () => {
    const adapter = createMockAdapter("bridge_disconnected", 0);
    await adapter.session();
    const stopped = await adapter.stopSession({ confirm: true });
    expect(stopped.ok).toBe(true);
    if (!stopped.ok) return;
    expect(stopped.value.report.status).toBe("blocked");
    expect(stopped.value.report.release.unconfirmed).toEqual([4242]);
    expect(stopped.value.report.outcome.unresolved).toEqual([4242]);
  });

  it("read_failed 场景的停止以失联结束（请求无法送达）", async () => {
    const adapter = createMockAdapter("read_failed", 0);
    await adapter.session();
    const result = await adapter.stopSession({ confirm: true });
    expect(!result.ok && result.failure.kind).toBe("disconnected");
  });
});

describe("gateway 会话读取与停止（真实传输 + CSRF 回显）", () => {
  const BASE = "http://127.0.0.1:8000";

  it("未配置 base URL：会话读取与停止都零网络调用并报 not_configured", async () => {
    const adapter = createGatewayAdapter(null);
    const read = await adapter.session();
    const write = await adapter.stopSession({ confirm: true });
    expect(!read.ok && read.failure.kind).toBe("not_configured");
    expect(!write.ok && write.failure.kind).toBe("not_configured");
  });

  it("会话 GET 少一个字段即整读判红，不部分填充", async () => {
    const wire = buildMockSession("healthy_run_07", Date.now());
    delete wire.stopAllowed;
    await withFetch((async () => jsonResponse(wire)) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).session();
      expect(!result.ok && result.failure.kind).toBe("contract_mismatch");
    });
  });

  it("会话 GET 解码后 CSRF 令牌留在适配器闭包里，绝不进渲染模型", async () => {
    await withFetch((async () => jsonResponse(buildMockSession("healthy_run_07", Date.now()))) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).session();
      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.value.state).toBe("running");
      expect(JSON.stringify(result.value)).not.toContain("csrf");
    });
  });

  it("停止 POST 带上 CSRF 头与 JSON {confirm:true}，且成功结果经共享解码器还原", async () => {
    const captured: {
      readonly url: string;
      readonly headers: Record<string, string>;
      readonly body: Record<string, unknown>;
    }[] = [];
    const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        captured.push({
          url,
          headers: init.headers as Record<string, string>,
          body: JSON.parse(String(init.body)) as Record<string, unknown>,
        });
        return jsonResponse({
          schemaVersion: SESSION_SCHEMA_VERSION,
          state: "running",
          report: buildMockStopReport("running"),
        });
      }
      return jsonResponse(buildMockSession("healthy_run_07", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      const read = await adapter.session();
      if (!read.ok) throw new Error("应先读会话以取得令牌");
      const result = await adapter.stopSession({ confirm: true });
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.value.report.status).toBe("stopped");
    });

    expect(captured).toHaveLength(1);
    const request = captured[0];
    if (request === undefined) throw new Error("应发出一次 POST");
    expect(request.url).toBe(`${BASE}${SESSION_ENDPOINTS.stop}`);
    expect(request.headers[CSRF_HEADER]).toBe("mock-csrf-token");
    expect(request.headers["content-type"]).toBe("application/json");
    expect(request.body).toEqual({ confirm: true });
  });

  it("服务器具名拒止原样送到面板，不塌成通用失败", async () => {
    const impl = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse(
          { schemaVersion: SESSION_SCHEMA_VERSION, error: "session_not_running", message: "这个 Kin 没有运行中的会话可以停止。" },
          409,
        );
      }
      return jsonResponse(buildMockSession("healthy_run_07", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      await adapter.session();
      const result = await adapter.stopSession({ confirm: true });
      expect(!result.ok && result.failure.kind).toBe("write_refused");
      if (result.ok) return;
      expect(result.failure.message).toContain("session_not_running");
    });
  });

  it("mock 与 gateway 对同一份 wire 文档解出同一形状（共享解码器的意义）", () => {
    const sessionWire = buildMockSession("healthy_run_07", 1_700_000_000_000);
    const sessionDecoded = decodeSessionPayload(sessionWire);
    expect(sessionDecoded.ok).toBe(true);
    if (!sessionDecoded.ok) return;
    expect(sessionDecoded.session.state).toBe("running");
    expect(sessionDecoded.csrfToken).toBe("mock-csrf-token");
    // A SessionControlInfo (what a panel gets) has no token field.
    expect(Object.keys(sessionDecoded.session)).not.toContain("csrfToken");

    const stopWire = {
      schemaVersion: SESSION_SCHEMA_VERSION,
      state: "unresolved",
      report: buildMockStopReport("unresolved"),
    };
    const stopDecoded = decodeStopPayload(stopWire);
    expect(stopDecoded.ok).toBe(true);
    if (!stopDecoded.ok) return;
    expect(stopDecoded.result.state).toBe("unresolved");
    expect(stopDecoded.result.report.status).toBe("blocked");
  });
});
