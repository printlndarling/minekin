import { describe, expect, it } from "vitest";
import { createMockAdapter } from "./mockAdapter";
import {
  CSRF_HEADER,
  IDENTITY_ENDPOINTS,
  createGatewayAdapter,
} from "./gatewayAdapter";
import { IDENTITY_SCHEMA_VERSION } from "../domain/model";
import { buildMockIdentity, mockOfflineUuid } from "../fixtures/mockFixtures";
import type { RenameRequest } from "../domain/model";

/**
 * The identity read + the one authorized rename, tested at the adapter seam. Both adapters
 * route through the SAME decoders as the gateway, so a mock rename and a real rename cannot
 * drift in shape — that parity is the point of most of these cases, not the specific values.
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

describe("mock 身份读取与改名", () => {
  it("停止场景读到默认 minekin、revision 1、可改名", async () => {
    const result = await createMockAdapter("fields_unknown", 0).identity();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.source).toBe("mock");
    expect(result.value.username).toBe("minekin");
    expect(result.value.identityRevision).toBe(1);
    expect(result.value.state).toBe("idle");
    expect(result.value.renameAllowed).toBe(true);
    expect(result.value.uuidCanonical).toBe(mockOfflineUuid("minekin"));
  });

  it("read_failed 场景身份读取以失联结束", async () => {
    const result = await createMockAdapter("read_failed", 0).identity();
    expect(!result.ok && result.failure.kind).toBe("disconnected");
  });

  it("改名前先读身份取得 CSRF，然后重命名成功并推进 revision 与 UUID", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.identity();
    const result = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 1 });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.status).toBe("renamed");
    expect(result.value.before.username).toBe("minekin");
    expect(result.value.after.username).toBe("nova_kin");
    expect(result.value.after.identityRevision).toBe(2);
    expect(result.value.uuidChanged).toBe(true);
    // The next read reflects the mutation — this is the sequence Core's stored identity shows.
    const reread = await adapter.identity();
    expect(reread.ok).toBe(true);
    if (!reread.ok) return;
    expect(reread.value.username).toBe("nova_kin");
    expect(reread.value.identityRevision).toBe(2);
    expect(reread.value.uuidCanonical).toBe(mockOfflineUuid("nova_kin"));
  });

  it("未先读身份就改名：缺 CSRF，拒且不动身份", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    const result = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 1 });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("missing_or_bad_csrf_token");
    const identity = await adapter.identity();
    if (!identity.ok) throw new Error("应读到身份");
    expect(identity.value.username).toBe("minekin");
    expect(identity.value.identityRevision).toBe(1);
  });

  it("会话运行中改名：具名拒止 session_not_stopped", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.identity();
    const result = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 1 });
    expect(!result.ok && result.failure.kind).toBe("write_refused");
    if (result.ok) return;
    expect(result.failure.message).toContain("session_not_stopped");
  });

  it("非法名字或未确认或 revision 不符：各自具名拒止，身份不变", async () => {
    const bad = createMockAdapter("fields_unknown", 0);
    await bad.identity();
    const invalid = await bad.renameIdentity({ username: "not a name!", confirm: true, expectedRevision: 1 });
    expect(invalid.ok).toBe(false);
    if (!invalid.ok) expect(invalid.failure.message).toContain("invalid_request");

    const noConfirm = createMockAdapter("fields_unknown", 0);
    await noConfirm.identity();
    const unconfirmed = await noConfirm.renameIdentity({
      username: "nova_kin",
      confirm: false,
      expectedRevision: 1,
    } as unknown as RenameRequest);
    expect(unconfirmed.ok).toBe(false);
    if (!unconfirmed.ok) expect(unconfirmed.failure.message).toContain("confirm");

    const stale = createMockAdapter("fields_unknown", 0);
    await stale.identity();
    const outdated = await stale.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 9 });
    expect(outdated.ok).toBe(false);
    if (!outdated.ok) expect(outdated.failure.message).toContain("stale_revision");
    // None of the three touched the store.
    const identity = await stale.identity();
    if (!identity.ok) throw new Error("应读到身份");
    expect(identity.value.identityRevision).toBe(1);
  });

  it("提交与当前相同的名字：unchanged，UUID 与 revision 不变", async () => {
    const adapter = createMockAdapter("fields_unknown", 0);
    await adapter.identity();
    const result = await adapter.renameIdentity({ username: "minekin", confirm: true, expectedRevision: 1 });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.status).toBe("unchanged");
    expect(result.value.uuidChanged).toBe(false);
    expect(result.value.after.identityRevision).toBe(1);
  });
});

describe("gateway 身份读取与改名（真实传输 + CSRF 回显）", () => {
  const BASE = "http://127.0.0.1:8000";

  it("未配置 base URL：身份读取与改名都零网络调用并报 not_configured", async () => {
    const adapter = createGatewayAdapter(null);
    const read = await adapter.identity();
    const write = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 1 });
    expect(!read.ok && read.failure.kind).toBe("not_configured");
    expect(!write.ok && write.failure.kind).toBe("not_configured");
  });

  it("身份 GET 解码后 CSRF 令牌留在适配器闭包里，绝不进渲染模型", async () => {
    await withFetch((async () => jsonResponse(buildMockIdentity("fields_unknown", Date.now()))) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).identity();
      expect(result.ok).toBe(true);
      if (!result.ok) return;
      expect(result.value.username).toBe("minekin");
      // The IdentityInfo the panel receives has no csrfToken field at all.
      expect(JSON.stringify(result.value)).not.toContain("csrf");
    });
  });

  it("改名 POST 带上 CSRF 头与 JSON，且回显当前 revision", async () => {
    const captured: {
      readonly url: string;
      readonly headers: Record<string, string>;
      readonly body: Record<string, unknown>;
    }[] = [];
    const renameWire = {
      schemaVersion: IDENTITY_SCHEMA_VERSION,
      status: "renamed",
      kinId: "kin_nova_01",
      before: { username: "minekin", uuidCanonical: mockOfflineUuid("minekin"), identityRevision: 1 },
      after: { username: "nova_kin", uuidCanonical: mockOfflineUuid("nova_kin"), identityRevision: 2 },
      uuidChanged: true,
      notice: "已改名。",
    };
    const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") {
        captured.push({
          url,
          headers: init.headers as Record<string, string>,
          body: JSON.parse(String(init.body)) as Record<string, unknown>,
        });
        return jsonResponse(renameWire);
      }
      return jsonResponse(buildMockIdentity("fields_unknown", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      const read = await adapter.identity();
      if (!read.ok) throw new Error("应先读到身份以取得令牌");
      const result = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: read.value.identityRevision });
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.value.after.identityRevision).toBe(2);
    });

    expect(captured).toHaveLength(1);
    const request = captured[0];
    if (request === undefined) throw new Error("应发出一次 POST");
    expect(request.url).toBe(`${BASE}${IDENTITY_ENDPOINTS.rename}`);
    expect(request.headers[CSRF_HEADER]).toBe("mock-csrf-token");
    expect(request.headers["content-type"]).toBe("application/json");
    expect(request.body).toEqual({ username: "nova_kin", confirm: true, expectedRevision: 1 });
  });

  it("服务器具名拒止原样送到面板，不塌成通用失败", async () => {
    const impl = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse(
          { schemaVersion: IDENTITY_SCHEMA_VERSION, error: "stale_revision", message: "身份修订号已前进" },
          409,
        );
      }
      return jsonResponse(buildMockIdentity("fields_unknown", Date.now()));
    }) as typeof fetch;

    await withFetch(impl, async () => {
      const adapter = createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 });
      await adapter.identity();
      const result = await adapter.renameIdentity({ username: "nova_kin", confirm: true, expectedRevision: 1 });
      expect(!result.ok && result.failure.kind).toBe("write_refused");
      if (result.ok) return;
      expect(result.failure.message).toContain("stale_revision");
    });
  });

  it("身份 GET 少一个字段即整读判红，不部分填充", async () => {
    const wire = buildMockIdentity("fields_unknown", Date.now());
    delete wire.uuidCanonical;
    await withFetch((async () => jsonResponse(wire)) as typeof fetch, async () => {
      const result = await createGatewayAdapter({ baseUrl: BASE, timeoutMs: 1_000 }).identity();
      expect(!result.ok && result.failure.kind).toBe("contract_mismatch");
    });
  });
});
