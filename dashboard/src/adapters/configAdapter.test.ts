import { describe, expect, it } from "vitest";
import { createMockAdapter } from "./mockAdapter";
import {
  CONFIG_ENDPOINTS,
  CSRF_HEADER,
  createGatewayAdapter,
  decodeConfigPayload,
} from "./gatewayAdapter";
import { CONFIG_SCHEMA_VERSION } from "../domain/model";
import { buildMockConfig, mockConfigInitialFields } from "../fixtures/mockFixtures";

/**
 * The config read + the second authorized write (persist), tested at the adapter seam. Like the
 * identity tests, most of these cases prove PARITY, not specific values: both adapters route the
 * read and the save through the SAME decoders the Gateway uses, so a mock edit and a real edit
 * cannot drift into a panel that promises a save the server would refuse. The single-source
 * validation (`configPolicy.validateConfigDraft`) is what the mock reuses as its stand-in for
 * `save_operator_config`, so the refusals below are exactly the shapes `save_from_request` emits.
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

describe("Gateway 模型测试传输", () => {
  it.each([false, true])("带 CSRF 的显式 POST，拒绝不完整的结果：%s", async (malformed) => {
    const calls: RequestInit[] = [];
    const impl = (async (_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        calls.push(init);
        return jsonResponse(malformed ? { status: "connected" } : {
          schemaVersion: "kin-dashboard-model-test/1.0.0", status: "unavailable",
          reason: "TIMEOUT", elapsedMs: 1000, timeoutMs: 1000, modelCalls: 1, estimatedCostMicro: 0,
        });
      }
      return jsonResponse(buildMockConfig("healthy_run_07", Date.now()));
    }) as typeof fetch;
    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: "http://127.0.0.1:8000", timeoutMs: 1000 });
      await adapter.config();
      const result = await adapter.testModel();
      expect(result.ok).toBe(!malformed);
      if (!result.ok) expect(result.failure.kind).toBe("contract_mismatch");
      else expect(result.value.reason).toBe("TIMEOUT");
    });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.body).toBe('{"confirm":true}');
    expect((calls[0]?.headers as Record<string, string>)[CSRF_HEADER]).toBe("mock-csrf-token");
  });
});

describe("mock 配置读取与保存", () => {
  it("预填场景读到 openai_compatible 预设，逐字段与共享解码器一致，且模型里没有 CSRF", async () => {
    const result = await createMockAdapter("healthy_run_07", 0).config();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.source).toBe("mock");
    expect(result.value.fields.model_name).toBe("deepseek-chat");
    expect(result.value.providers).toEqual(["off", "openai_compatible"]);
    expect(result.value.loadError).toBeNull();
    // The token lives in the wire document and the decoder output, never in ConfigInfo.
    expect(JSON.stringify(result.value)).not.toContain("csrf");
  });

  it("空文档场景读到空白文档（新建根）：fields 里没有任何预填字段", async () => {
    const result = await createMockAdapter("fields_unknown", 0).config();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.fields).toEqual({});
  });

  it("read_failed 场景配置读取以失联结束", async () => {
    const result = await createMockAdapter("read_failed", 0).config();
    expect(!result.ok && result.failure.kind).toBe("disconnected");
  });

  it("保存前先成功读取配置取得 CSRF，保存整份替换后重读反映最后一次接受的保存", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();
    const saved = await adapter.saveConfig({ fields: { model_provider: "off", goal_product_id: "minecraft:iron_pickaxe", goal_quantity: 3 } });
    expect(saved.ok).toBe(true);
    if (!saved.ok) return;
    expect(saved.value.status).toBe("saved");
    expect(saved.value.fields.goal_quantity).toBe(3);
    const reread = await adapter.config();
    expect(reread.ok).toBe(true);
    if (!reread.ok) return;
    expect(reread.value.fields.goal_product_id).toBe("minecraft:iron_pickaxe");
    expect(reread.value.fields.goal_quantity).toBe(3);
  });

  it("整份替换语义：第二次保存未写的字段被写成未设置", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();
    await adapter.saveConfig({ fields: { model_provider: "off" } });
    const second = await adapter.saveConfig({ fields: { goal_direction: "只留这句" } });
    expect(second.ok).toBe(true);
    if (!second.ok) return;
    // The document now holds only goal_direction; the earlier model_provider is gone.
    expect(second.value.fields).toEqual({ goal_direction: "只留这句" });
    const reread = await adapter.config();
    if (!reread.ok) throw new Error("应读到配置");
    expect(reread.value.fields.model_provider).toBeUndefined();
  });

  it("未先读配置就保存：缺 CSRF，拒且不动文档", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    const result = await adapter.saveConfig({ fields: { model_provider: "off" } });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("missing_or_bad_csrf_token");
    const reread = await adapter.config();
    if (!reread.ok) throw new Error("应读到配置");
    expect(reread.value.fields).toEqual({});
  });

  it("非配置字段混进 body：具名拒止 not a configurable field，文档不变", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();
    const result = await adapter.saveConfig({ fields: { shell_command: "rm -rf /" } });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("not a configurable field: shell_command");
    const reread = await adapter.config();
    if (!reread.ok) throw new Error("应读到配置");
    expect(reread.value.fields).toEqual({});
  });

  it("逐字段校验：非法物品 id 具名拒止并点名该字段", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();
    const result = await adapter.saveConfig({ fields: { goal_product_id: "Not A Valid Id" } });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("invalid_config: goal_product_id:");
    const reread = await adapter.config();
    if (!reread.ok) throw new Error("应读到配置");
    expect(reread.value.fields).toEqual({});
  });

  it("直接把密钥形状填进 env 名：校验拒止，绝不接受成凭据", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();
    const leaked = "sk-" + "a".repeat(40);
    const result = await adapter.saveConfig({ fields: { model_api_key_env: leaked } });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("model_api_key_env:");
    // The refused value never lands in the store.
    const reread = await adapter.config();
    if (!reread.ok) throw new Error("应读到配置");
    expect(JSON.stringify(reread.value.fields)).not.toContain("sk-");
  });

  it("read_failed 场景的保存以失联结束（请求无法送达）", async () => {
    const adapter = createMockAdapter("read_failed", 0);
    const result = await adapter.saveConfig({ fields: { model_provider: "off" } });
    expect(!result.ok && result.failure.kind).toBe("disconnected");
  });
});

describe("gateway 配置读取与保存（真实传输 + CSRF 回显）", () => {
  const BASE = "http://127.0.0.1:8000";

  it("未配置 base URL：配置读取与保存都零网络调用并报 not_configured", async () => {
    const adapter = createGatewayAdapter(null);
    const read = await adapter.config();
    const write = await adapter.saveConfig({ fields: { model_provider: "off" } });
    expect(!read.ok && read.failure.kind).toBe("not_configured");
    expect(!write.ok && write.failure.kind).toBe("not_configured");
  });

  it("配置 GET 少一个字段即整读判红，不部分填充", async () => {
    const wire = buildMockConfig("healthy_run_07", Date.now());
    delete wire.providers;
    await withFetch((async () => jsonResponse(wire)) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).config();
      expect(!result.ok && result.failure.kind).toBe("contract_mismatch");
    });
  });

  it("配置 GET 解码后 CSRF 令牌留在适配器闭包里，绝不进渲染模型", async () => {
    await withFetch((async () => jsonResponse(buildMockConfig("healthy_run_07", Date.now()))) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).config();
      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.value.fields.model_name).toBe("deepseek-chat");
      expect(JSON.stringify(result.value)).not.toContain("csrf");
    });
  });

  it("保存 POST 带上 CSRF 头与 JSON {fields}，且成功结果经共享解码器还原", async () => {
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
          schemaVersion: CONFIG_SCHEMA_VERSION,
          status: "saved",
          fields: { model_provider: "off", goal_quantity: 2 },
        });
      }
      return jsonResponse(buildMockConfig("healthy_run_07", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      const read = await adapter.config();
      if (!read.ok) throw new Error("应先读配置以取得令牌");
      const result = await adapter.saveConfig({ fields: { model_provider: "off", goal_quantity: 2 } });
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.value.status).toBe("saved");
    });

    expect(captured).toHaveLength(1);
    const request = captured[0];
    if (request === undefined) throw new Error("应发出一次 POST");
    expect(request.url).toBe(`${BASE}${CONFIG_ENDPOINTS.save}`);
    expect(request.headers[CSRF_HEADER]).toBe("mock-csrf-token");
    expect(request.headers["content-type"]).toBe("application/json");
    expect(request.body).toEqual({ fields: { model_provider: "off", goal_quantity: 2 } });
  });

  it("服务器具名拒止原样送到面板，不塌成通用失败", async () => {
    const impl = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse(
          { schemaVersion: CONFIG_SCHEMA_VERSION, error: "invalid_config", message: "goal_product_id: 不是合法物品 id" },
          400,
        );
      }
      return jsonResponse(buildMockConfig("fields_unknown", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      await adapter.config();
      const result = await adapter.saveConfig({ fields: { goal_product_id: "bad id" } });
      expect(!result.ok && result.failure.kind).toBe("write_refused");
      if (result.ok) return;
      expect(result.failure.message).toContain("invalid_config");
      expect(result.failure.message).toContain("goal_product_id");
    });
  });

  it("mock 与 gateway 对同一份 wire 文档解出同一形状（共享解码器的意义）", () => {
    const wire = buildMockConfig("healthy_run_07", 1_700_000_000_000);
    const decoded = decodeConfigPayload(wire);
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) return;
    expect(decoded.config.fields).toEqual(mockConfigInitialFields("healthy_run_07"));
    // The token the save echoes back is here, but a ConfigInfo (what a panel gets) has no such field.
    expect(decoded.csrfToken).toBe("mock-csrf-token");
    expect(Object.keys(decoded.config)).not.toContain("csrfToken");
  });
});

describe("决策策略词表与读写", () => {
  it("配置读取投影策略词表；字节缺失即整读契约不符", async () => {
    const result = await createMockAdapter("healthy_run_07", 0).config();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.policies).toEqual(["model", "rules"]);

    const wire = buildMockConfig("healthy_run_07", Date.now()) as Record<string, unknown>;
    delete wire.policies;
    const decoded = decodeConfigPayload(wire);
    expect(decoded.ok).toBe(false);
    if (!decoded.ok) expect(decoded.issues.join(" | ")).toContain("policies");
  });

  it("保存 rules 后读回仍是 rules；未知策略被具名拒止且文档不变", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.config();

    const saved = await adapter.saveConfig({ fields: { decision_policy: "rules" } });
    expect(saved.ok).toBe(true);
    const again = await adapter.config();
    expect(again.ok).toBe(true);
    if (again.ok) expect(again.value.fields.decision_policy).toBe("rules");

    const bad = await adapter.saveConfig({ fields: { decision_policy: "sometimes" } });
    expect(bad.ok).toBe(false);
    if (!bad.ok) {
      expect(bad.failure.message).toContain("decision_policy");
      expect(bad.failure.message).toContain("未知策略");
    }
    const unchanged = await adapter.config();
    expect(unchanged.ok).toBe(true);
    if (unchanged.ok) expect(unchanged.value.fields.decision_policy).toBe("rules");
  });
});
