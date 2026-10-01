import {
  fail,
  ok,
  type AdapterDescriptor,
  type KinReadAdapter,
  type ReadResult,
  type TimelineQuery,
} from "../domain/adapter";
import {
  IDENTITY_SCHEMA_VERSION,
  CONFIG_SCHEMA_VERSION,
  SESSION_SCHEMA_VERSION,
  type AlertsEnvelope,
  type ConfigInfo,
  type ConfigSaveRequest,
  type ConfigSaveResult,
  type ConfigValue,
  type IdentityInfo,
  type IdentityViewSnapshot,
  type KinSnapshot,
  type RenameRequest,
  type RenameResult,
  type SessionControlInfo,
  type StopRequest,
  type StopResult,
  type TimelineEvent,
} from "../domain/model";
import {
  MOCK_SCENARIOS,
  buildMockBundle,
  buildMockConfig,
  buildMockIdentity,
  buildMockSession,
  buildMockStopReport,
  mockConfigInitialFields,
  MOCK_CONFIG_PROVIDERS,
  mockIdentityState,
  mockOfflineUuid,
  type MockScenarioId,
} from "../fixtures/mockFixtures";
import { DEFAULT_IDENTITY_NAME, isValidUsername } from "../domain/identityPolicy";
import { CONFIG_FIELDS, buildSaveFields, validateConfigDraft } from "../domain/configPolicy";
import {
  decodeAlertsPayload,
  decodeConfigPayload,
  decodeConfigSavePayload,
  decodeIdentityPayload,
  decodeRenamePayload,
  decodeSessionPayload,
  decodeSnapshotPayload,
  decodeStopPayload,
  decodeTimelinePayload,
} from "./gatewayAdapter";

const MOCK_RENAME_NOTICE =
  "身份已改名。离线 UUID 由名字推导，改名会解析出新的离线 UUID；背包、位置与进度不迁移，已加入过的服务器会把它当作另一个玩家。";
const MOCK_RENAME_UNCHANGED_NOTICE = "新名字与当前名字相同，身份未变：UUID 与 revision 保持原样。";

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

  // In-memory identity store: a new Kin sits on the Core default name at revision 1, and a
  // successful rename mutates it so the NEXT identity read reflects the new name and bumped
  // revision — the same observable sequence Core's stored identity produces between a rename
  // and the following read. Nothing here can start, stop or move a session; `state` is fixed
  // by the scenario, so only a stopped (idle) scenario can ever complete a rename.
  const store: { username: string; identityRevision: number } = {
    username: DEFAULT_IDENTITY_NAME,
    identityRevision: 1,
  };
  // Stands in for the per-process CSRF token the real identity GET hands out and the rename
  // must echo back. The closure holds it, not the rendered model, so the token never reaches
  // the UI; a rename before any successful identity read has nothing to echo and is refused
  // exactly like a request that skipped the GET.
  let csrfIssued = false;

  // In-memory config store: the saved document each scenario starts on, with a successful save
  // replacing it whole so the NEXT config read reflects what was written — the same observable
  // sequence `operator_config` produces between `save_operator_config` and the following
  // `load_operator_config`. Like the identity store, nothing here can start/stop/move a session.
  const configStore: { fields: Record<string, ConfigValue> } = {
    fields: mockConfigInitialFields(scenario),
  };
  // The config GET is what hands out the (shared) token; a save before any config read is refused
  // exactly like the real surface refusing one that skipped the GET.
  let configReadIssued = false;
  const KNOWN_CONFIG_KEYS = new Set(CONFIG_FIELDS.map((meta) => meta.key));

  // The session GET is what hands out the (shared) token and reports the observed state; a stop
  // before any session read is refused exactly like one that skipped the GET. Like the identity and
  // config stores, nothing here can actually start/stop/move a session — `state` is fixed by the
  // scenario, so only a running/unresolved scenario can ever complete a stop, and an idle one is
  // refused the way Core's `stop_from_request` refuses an idle Kin.
  let sessionReadIssued = false;

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
    async identity(signal?: AbortSignal): Promise<ReadResult<IdentityInfo>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：身份读取失败。");
      }
      const decoded = decodeIdentityPayload(
        buildMockIdentity(scenario, Date.now(), store.username, store.identityRevision),
      );
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟数据与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      // The GET is what hands out the token; a rename only becomes possible after one read.
      csrfIssued = true;
      return ok(decoded.identity, "mock", `mock://scenario/${scenario}/identity`);
    },
    async renameIdentity(request: RenameRequest, signal?: AbortSignal): Promise<ReadResult<RenameResult>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "改名请求已取消。");
      }
      if (scenario === "read_failed") {
        // The Gateway is unreachable, so the write never arrives: a transport failure, not a
        // policy refusal. The mock has no cross-site threat surface, so the CSRF/origin/media-
        // type layers are represented by `csrfIssued` below rather than replayed byte-for-byte.
        return fail("disconnected", "模拟场景：Gateway 不可达，改名请求无法送达。");
      }
      if (!csrfIssued) {
        return fail("write_refused", "missing_or_bad_csrf_token：改名前必须先成功读取身份以取得 CSRF 令牌。");
      }
      // rename_from_request, in the order the Gateway checks it: the session predicate runs
      // before the body is parsed, and every check runs before the store is touched — so no
      // refused request leaves a partial identity behind.
      const state = mockIdentityState(scenario);
      if (state !== "idle") {
        return fail("write_refused", `session_not_stopped：当前会话状态是 ${state}，只有停止时才能改名。`);
      }
      const body = request as unknown as Record<string, unknown>;
      const username = body.username;
      if (typeof username !== "string" || !isValidUsername(username)) {
        return fail("write_refused", "invalid_request：username 不是有效的 Minecraft 名字（3-16 位字母、数字或下划线）。");
      }
      if (body.confirm !== true) {
        return fail("write_refused", "invalid_request：改名必须显式确认（confirm 必须为 true）。");
      }
      const expectedRevision = body.expectedRevision;
      if (typeof expectedRevision !== "number" || !Number.isInteger(expectedRevision)) {
        return fail("write_refused", "invalid_request：expectedRevision 必须是整数身份修订号。");
      }
      if (expectedRevision < 1) {
        return fail("write_refused", "invalid_request：expectedRevision 从一开始。");
      }
      if (expectedRevision !== store.identityRevision) {
        return fail(
          "write_refused",
          `stale_revision：身份修订号已前进（期望 ${expectedRevision}，当前 ${store.identityRevision}）——有人先改了这个 Kin。`,
        );
      }

      const before: IdentityViewSnapshot = {
        username: store.username,
        uuidCanonical: mockOfflineUuid(store.username),
        identityRevision: store.identityRevision,
      };
      const unchanged = username === store.username;
      if (!unchanged) {
        store.username = username;
        store.identityRevision += 1;
      }
      const after: IdentityViewSnapshot = {
        username: store.username,
        uuidCanonical: mockOfflineUuid(store.username),
        identityRevision: store.identityRevision,
      };
      // Route the accepted rename through the SAME decoder gateway bytes use, so a mock
      // rename result and a real one cannot drift in shape.
      const decoded = decodeRenamePayload({
        schemaVersion: IDENTITY_SCHEMA_VERSION,
        status: unchanged ? "unchanged" : "renamed",
        kinId: "kin_nova_01",
        before,
        after,
        uuidChanged: !unchanged,
        notice: unchanged ? MOCK_RENAME_UNCHANGED_NOTICE : MOCK_RENAME_NOTICE,
      });
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟改名结果与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "mock", `mock://scenario/${scenario}/rename`);
    },
    async config(signal?: AbortSignal): Promise<ReadResult<ConfigInfo>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：配置读取失败。");
      }
      const decoded = decodeConfigPayload(buildMockConfig(scenario, Date.now(), configStore.fields));
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟配置与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      // The config GET is what hands out the shared token; a save only becomes possible after one read.
      configReadIssued = true;
      return ok(decoded.config, "mock", `mock://scenario/${scenario}/config`);
    },
    async saveConfig(request: ConfigSaveRequest, signal?: AbortSignal): Promise<ReadResult<ConfigSaveResult>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "保存请求已取消。");
      }
      if (scenario === "read_failed") {
        // Gateway unreachable: the write never arrives, a transport failure rather than a policy
        // refusal. The mock has no cross-site surface, so the CSRF/origin/media-type layers are
        // represented by `configReadIssued` below rather than replayed byte-for-byte.
        return fail("disconnected", "模拟场景：Gateway 不可达，保存请求无法送达。");
      }
      if (!configReadIssued) {
        return fail("write_refused", "missing_or_bad_csrf_token：保存前必须先成功读取配置以取得 CSRF 令牌。");
      }
      // Mirror save_from_request's order: the top-level shape first, then each field. The form sends
      // the whole document, so a save is a replace — a field the body omits is written as unset.
      const draft: Record<string, string> = {};
      for (const [key, value] of Object.entries(request.fields)) {
        if (!KNOWN_CONFIG_KEYS.has(key)) {
          return fail("write_refused", `invalid_config: not a configurable field: ${key}`);
        }
        draft[key] = String(value);
      }
      const errors = validateConfigDraft(draft, MOCK_CONFIG_PROVIDERS);
      // Report the first offender in CONFIG_FIELDS order, the same deterministic way the panel gates.
      for (const meta of CONFIG_FIELDS) {
        const message = errors[meta.key];
        if (message !== undefined) {
          return fail("write_refused", `invalid_config: ${meta.key}: ${message}`);
        }
      }
      // The save lands whole before the response is shaped, so a refusal above never leaves a partial
      // document — matching operator_config's atomic write.
      const savedFields = buildSaveFields(draft);
      configStore.fields = savedFields;
      // Route the accepted save through the SAME decoder gateway bytes use, so a mock save result and
      // a real one cannot drift in shape.
      const decoded = decodeConfigSavePayload({
        schemaVersion: CONFIG_SCHEMA_VERSION,
        status: "saved",
        fields: savedFields,
      });
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟保存结果与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "mock", `mock://scenario/${scenario}/config/save`);
    },
    async session(signal?: AbortSignal): Promise<ReadResult<SessionControlInfo>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "读取已取消。");
      }
      if (scenario === "read_failed") {
        return fail("disconnected", "模拟场景：会话读取失败。");
      }
      const decoded = decodeSessionPayload(buildMockSession(scenario, Date.now()));
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟会话读数与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      // The session GET is what hands out the shared token and reports the observed state; a stop
      // only becomes possible after one read. The token stays in this closure, never in the model.
      sessionReadIssued = true;
      return ok(decoded.session, "mock", `mock://scenario/${scenario}/session`);
    },
    async stopSession(request: StopRequest, signal?: AbortSignal): Promise<ReadResult<StopResult>> {
      await settle();
      if (signal?.aborted === true) {
        return fail("cancelled", "停止请求已取消。");
      }
      if (scenario === "read_failed") {
        // Gateway unreachable: the write never arrives, a transport failure rather than a policy
        // refusal. The mock has no cross-site surface, so the CSRF/origin/media-type layers are
        // represented by `sessionReadIssued` below rather than replayed byte-for-byte.
        return fail("disconnected", "模拟场景：Gateway 不可达，停止请求无法送达。");
      }
      if (!sessionReadIssued) {
        return fail("write_refused", "missing_or_bad_csrf_token：停止前必须先成功读取会话以取得 CSRF 令牌。");
      }
      // Mirror stop_from_request's order: the body shape first (unknown fields, then the explicit
      // confirm), then the session predicate. Every check runs before Core's stop, so a refused
      // request never releases inputs it was not authorised to release.
      const body = request as unknown as Record<string, unknown>;
      const unknown = Object.keys(body).filter((key) => key !== "confirm");
      if (unknown.length > 0) {
        return fail("write_refused", `invalid_request：unexpected field(s): ${unknown.sort().join(", ")}`);
      }
      if (body.confirm !== true) {
        return fail("write_refused", "invalid_request：stopping requires an explicit confirmation (confirm must be true)");
      }
      const state = mockIdentityState(scenario);
      if (state === "idle") {
        return fail("write_refused", "session_not_running：这个 Kin 没有运行中的会话可以停止。");
      }
      // The stop lands, then the report is shaped — a blocked report (unconfirmed/unresolved pids)
      // stays blocked through the SAME decoder, never collapsed to a green one.
      const decoded = decodeStopPayload({
        schemaVersion: SESSION_SCHEMA_VERSION,
        state,
        report: buildMockStopReport(state),
      });
      if (!decoded.ok) {
        return fail("contract_mismatch", `模拟停止报告与自身解码器不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "mock", `mock://scenario/${scenario}/session/stop`);
    },
  };
}
