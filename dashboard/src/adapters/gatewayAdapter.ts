import {
  SNAPSHOT_SCHEMA_VERSION,
  type Alert,
  type AlertComponent,
  type AlertSeverity,
  type AlertState,
  type EvidenceRef,
  type Heartbeat,
  type KinRuntimeState,
  type KinSnapshot,
  type LinkState,
  type MediaStreamRef,
  type SelfState,
  type SessionInfo,
  type SessionMode,
  type TimelineEvent,
  type TimelineKind,
  type TimelineOutcome,
  type VersionSet,
  type WorldInfo,
} from "../domain/model";
import {
  fail,
  ok,
  type AdapterDescriptor,
  type KinReadAdapter,
  type ReadFailure,
  type ReadResult,
  type TimelineQuery,
} from "../domain/adapter";
import { gap, known, type Signal, type SignalContext, type SignalStatus } from "../domain/signals";
import { asBoolean, asInteger, asNullableNumber, asNullableString, asNumber, asRecord, asString, oneOf } from "./jsonGuards";

/**
 * Candidate Gateway wiring. The endpoints and payload shapes below are a
 * PROPOSAL from the D1 read model, not a frozen contract: G lane has not
 * published a read model yet. Every mismatch fails closed instead of guessing,
 * so this adapter can never show an invented value.
 */
export const PROPOSED_ENDPOINTS = {
  snapshot: "/api/v1/dashboard/snapshot",
  timeline: "/api/v1/dashboard/timeline",
  alerts: "/api/v1/dashboard/alerts",
} as const;

const KIN_STATES: readonly KinRuntimeState[] = ["idle", "running", "paused", "recovering", "unresolved"];
const LINK_STATES: readonly LinkState[] = ["connected", "connecting", "disconnected"];
const SESSION_MODES: readonly SessionMode[] = ["A_companion", "B_standalone"];
const TIMELINE_KINDS: readonly TimelineKind[] = [
  "observation",
  "decision",
  "intent",
  "input",
  "server_feedback",
  "reflex",
  "fault",
  "session",
];
const TIMELINE_OUTCOMES: readonly TimelineOutcome[] = ["applied", "rejected", "expired", "released", "unknown"];
const ALERT_SEVERITIES: readonly AlertSeverity[] = ["info", "warning", "critical"];
const ALERT_STATES: readonly AlertState[] = ["active", "resolved", "acknowledged"];
const ALERT_COMPONENTS: readonly AlertComponent[] = ["runtime", "bridge", "launcher", "gateway", "media", "database"];
const MEDIA_TRANSPORTS: readonly MediaStreamRef["transport"][] = ["webrtc", "hls", "mjpeg"];
const SIGNAL_STATUSES: readonly SignalStatus[] = ["known", "unknown", "unavailable", "not_wired", "permission_denied"];

interface WireSignal {
  readonly status: SignalStatus;
  readonly reason: string;
  readonly ctx: SignalContext;
  readonly value: unknown;
}

function decodeSignal(raw: unknown, path: string, issues: string[]): WireSignal | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 signal 对象`);
    return null;
  }
  const status = oneOf(rec.status, SIGNAL_STATUSES);
  if (status === null) {
    issues.push(`${path}.status: 未知取值`);
    return null;
  }
  const sourceRef = asString(rec.sourceRef);
  const observedAt = asNullableString(rec.observedAt);
  const staleAfterMs = asNullableNumber(rec.staleAfterMs);
  if (sourceRef === null || observedAt === undefined || staleAfterMs === undefined) {
    issues.push(`${path}: 缺少 provenance 字段（sourceRef/observedAt/staleAfterMs）`);
    return null;
  }
  const reason = status === "known" ? "" : (asString(rec.reason) ?? "");
  if (status !== "known" && reason === "") {
    issues.push(`${path}.reason: 缺口必须给出原因`);
    return null;
  }
  return { status, reason, value: rec.value, ctx: { source: "gateway", sourceRef, observedAt, staleAfterMs } };
}

function typed<T>(wire: WireSignal, path: string, issues: string[], parse: (raw: unknown) => T | null): Signal<T> | null {
  if (wire.status !== "known") {
    return gap(wire.status, wire.reason, wire.ctx);
  }
  const value = parse(wire.value);
  if (value === null) {
    issues.push(`${path}.value: 取值不符合只读契约`);
    return null;
  }
  return known(value, wire.ctx);
}

function parseString(raw: unknown): string | null {
  return asString(raw);
}

function field<T>(raw: unknown, key: string, path: string, issues: string[], parse: (v: unknown) => T | null): T | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 object`);
    return null;
  }
  const value = parse(rec[key]);
  if (value === null) {
    issues.push(`${path}.${key}: 字段缺失或类型不符`);
    return null;
  }
  return value;
}

function parseSession(raw: unknown): SessionInfo | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const sessionId = field<string>(rec, "sessionId", "session", issues, parseString);
  const generation = field<number>(rec, "generation", "session", issues, asInteger);
  const mode = field<SessionMode>(rec, "mode", "session", issues, (v) => oneOf(v, SESSION_MODES));
  const startedAt = field<string>(rec, "startedAt", "session", issues, parseString);
  if (sessionId === null || generation === null || mode === null || startedAt === null) return null;
  return { sessionId, generation, mode, startedAt };
}

function parseWorld(raw: unknown): WorldInfo | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const profileId = field<string>(rec, "profileId", "world", issues, parseString);
  const profileName = field<string>(rec, "profileName", "world", issues, parseString);
  const worldContext = field<string>(rec, "worldContext", "world", issues, parseString);
  const epoch = field<number>(rec, "epoch", "world", issues, asInteger);
  const joined = field<boolean>(rec, "joined", "world", issues, asBoolean);
  const resolvedVersion = field<string>(rec, "resolvedVersion", "world", issues, parseString);
  if (!profileId || !profileName || !worldContext || epoch === null || joined === null || !resolvedVersion) return null;
  return { profileId, profileName, worldContext, epoch, joined, resolvedVersion };
}

function parseVersions(raw: unknown): VersionSet | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const runtime = field<string>(rec, "runtime", "versions", issues, parseString);
  const bridge = field<string>(rec, "bridge", "versions", issues, parseString);
  const clientBundle = field<string>(rec, "clientBundle", "versions", issues, parseString);
  const java = field<string>(rec, "java", "versions", issues, parseString);
  const fabricLoader = field<string>(rec, "fabricLoader", "versions", issues, parseString);
  if (!runtime || !bridge || !clientBundle || !java || !fabricLoader) return null;
  return { runtime, bridge, clientBundle, java, fabricLoader };
}

function parseHeartbeat(raw: unknown): Heartbeat | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const lastSequence = field<number>(rec, "lastSequence", "bridgeHeartbeat", issues, asInteger);
  const lastObservedAt = field<string>(rec, "lastObservedAt", "bridgeHeartbeat", issues, parseString);
  const intervalMs = field<number>(rec, "intervalMs", "bridgeHeartbeat", issues, asNumber);
  const inputLeaseHeld = field<boolean>(rec, "inputLeaseHeld", "bridgeHeartbeat", issues, asBoolean);
  if (lastSequence === null || !lastObservedAt || intervalMs === null || inputLeaseHeld === null) return null;
  return { lastSequence, lastObservedAt, intervalMs, inputLeaseHeld };
}

function parseSelfState(raw: unknown): SelfState | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const health = field<number>(rec, "health", "selfState", issues, asNumber);
  const food = field<number>(rec, "food", "selfState", issues, asNumber);
  const dimension = field<string>(rec, "dimension", "selfState", issues, parseString);
  const guiOpen = field<boolean>(rec, "guiOpen", "selfState", issues, asBoolean);
  if (health === null || food === null || !dimension || guiOpen === null) return null;
  return { health, food, dimension, guiOpen };
}

function parseEvidence(raw: unknown): EvidenceRef | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const runId = field<string>(rec, "runId", "evidence", issues, parseString);
  const attempt = field<string>(rec, "attempt", "evidence", issues, parseString);
  const bundleDigest = field<string>(rec, "bundleDigest", "evidence", issues, parseString);
  const sealedAt = field<string>(rec, "sealedAt", "evidence", issues, parseString);
  if (!runId || !attempt || !bundleDigest || !sealedAt) return null;
  return { runId, attempt, bundleDigest, sealedAt };
}

function parseMedia(raw: unknown): MediaStreamRef | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const issues: string[] = [];
  const available = field<boolean>(rec, "available", "liveView", issues, asBoolean);
  const transport = field<MediaStreamRef["transport"]>(rec, "transport", "liveView", issues, (v) => oneOf(v, MEDIA_TRANSPORTS));
  const url = field<string>(rec, "url", "liveView", issues, parseString);
  const startedAt = field<string>(rec, "startedAt", "liveView", issues, parseString);
  if (available === null || !transport || !url || !startedAt) return null;
  return { available, transport, url, startedAt };
}

export function decodeSnapshotPayload(raw: unknown): { ok: true; snapshot: KinSnapshot } | { ok: false; issues: readonly string[] } {
  const issues: string[] = [];
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$ : 响应不是 object"] };
  if (asString(rec.schemaVersion) !== SNAPSHOT_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${SNAPSHOT_SCHEMA_VERSION}`);
  }

  const kinId = decodeAndType<string>(rec.kinId, "kinId", issues, parseString);
  const runtimeState = decodeAndType<KinRuntimeState>(rec.runtimeState, "runtimeState", issues, (v) => oneOf(v, KIN_STATES));
  const bridgeLink = decodeAndType<LinkState>(rec.bridgeLink, "bridgeLink", issues, (v) => oneOf(v, LINK_STATES));
  const serverLink = decodeAndType<LinkState>(rec.serverLink, "serverLink", issues, (v) => oneOf(v, LINK_STATES));
  const session = decodeAndType<SessionInfo>(rec.session, "session", issues, parseSession);
  const world = decodeAndType<WorldInfo>(rec.world, "world", issues, parseWorld);
  const versions = decodeAndType<VersionSet>(rec.versions, "versions", issues, parseVersions);
  const bridgeHeartbeat = decodeAndType<Heartbeat>(rec.bridgeHeartbeat, "bridgeHeartbeat", issues, parseHeartbeat);
  const selfState = decodeAndType<SelfState>(rec.selfState, "selfState", issues, parseSelfState);
  const evidence = decodeAndType<EvidenceRef>(rec.evidence, "evidence", issues, parseEvidence);
  const liveView = decodeAndType<MediaStreamRef>(rec.liveView, "liveView", issues, parseMedia);

  if (issues.length > 0) return { ok: false, issues };
  if (
    kinId === null ||
    runtimeState === null ||
    bridgeLink === null ||
    serverLink === null ||
    session === null ||
    world === null ||
    versions === null ||
    bridgeHeartbeat === null ||
    selfState === null ||
    evidence === null ||
    liveView === null
  ) {
    return { ok: false, issues: [...issues, "$: 字段解码失败"] };
  }
  return {
    ok: true,
    snapshot: {
      schemaVersion: SNAPSHOT_SCHEMA_VERSION,
      kinId,
      runtimeState,
      bridgeLink,
      serverLink,
      session,
      world,
      versions,
      bridgeHeartbeat,
      selfState,
      evidence,
      liveView,
    },
  };
}

function decodeAndType<T>(
  raw: unknown,
  path: string,
  issues: string[],
  parse: (v: unknown) => T | null,
): Signal<T> | null {
  const wire = decodeSignal(raw, path, issues);
  if (wire === null) return null;
  return typed(wire, path, issues, parse);
}

function decodeTimelinePayload(raw: unknown): { ok: true; events: readonly TimelineEvent[] } | { ok: false; issues: readonly string[] } {
  if (!Array.isArray(raw)) return { ok: false, issues: ["$: 期望数组"] };
  const issues: string[] = [];
  const events: TimelineEvent[] = [];
  for (const [index, item] of raw.entries()) {
    const path = `events[${index}]`;
    const rec = asRecord(item);
    if (rec === null) {
      issues.push(`${path}: 期望 object`);
      continue;
    }
    const eventId = asString(rec.eventId);
    const kind = oneOf(rec.kind, TIMELINE_KINDS);
    const at = asString(rec.at);
    const title = asString(rec.title);
    const outcome = oneOf(rec.outcome, TIMELINE_OUTCOMES);
    const sourceRef = asString(rec.sourceRef);
    const monotonicMs = asNullableNumber(rec.monotonicMs);
    const generation = asNullableNumber(rec.generation);
    const sequence = asNullableNumber(rec.sequence);
    const detail = asNullableString(rec.detail);
    if (
      eventId === null ||
      kind === null ||
      at === null ||
      title === null ||
      outcome === null ||
      sourceRef === null ||
      monotonicMs === undefined ||
      generation === undefined ||
      sequence === undefined ||
      detail === undefined
    ) {
      issues.push(`${path}: 字段缺失或枚举取值未知`);
      continue;
    }
    events.push({
      eventId,
      kind,
      at,
      title,
      outcome,
      sourceRef,
      monotonicMs,
      generation,
      sequence,
      detail,
    });
  }
  return issues.length > 0 ? { ok: false, issues } : { ok: true, events };
}

function decodeAlertsPayload(raw: unknown): { ok: true; alerts: readonly Alert[] } | { ok: false; issues: readonly string[] } {
  if (!Array.isArray(raw)) return { ok: false, issues: ["$: 期望数组"] };
  const issues: string[] = [];
  const alerts: Alert[] = [];
  for (const [index, item] of raw.entries()) {
    const path = `alerts[${index}]`;
    const rec = asRecord(item);
    if (rec === null) {
      issues.push(`${path}: 期望 object`);
      continue;
    }
    const alertId = asString(rec.alertId);
    const severity = oneOf(rec.severity, ALERT_SEVERITIES);
    const state = oneOf(rec.state, ALERT_STATES);
    const component = oneOf(rec.component, ALERT_COMPONENTS);
    const title = asString(rec.title);
    const firstSeenAt = asString(rec.firstSeenAt);
    const sourceRef = asString(rec.sourceRef);
    const detail = asNullableString(rec.detail);
    const lastSeenAt = asNullableString(rec.lastSeenAt);
    if (
      alertId === null ||
      severity === null ||
      state === null ||
      component === null ||
      title === null ||
      firstSeenAt === null ||
      sourceRef === null ||
      detail === undefined ||
      lastSeenAt === undefined
    ) {
      issues.push(`${path}: 字段缺失或枚举取值未知`);
      continue;
    }
    alerts.push({ alertId, severity, state, component, title, detail, firstSeenAt, lastSeenAt, sourceRef });
  }
  return issues.length > 0 ? { ok: false, issues } : { ok: true, alerts };
}

interface HttpJson {
  readonly ok: true;
  readonly data: unknown;
}

function classifyStatus(status: number, url: string): ReadFailure {
  if (status === 401 || status === 403) {
    return { kind: "permission_denied", message: `${url} → HTTP ${status}：需要 Gateway 管理员只读鉴权。` };
  }
  if (status === 404) {
    return { kind: "contract_mismatch", message: `${url} → HTTP 404：Gateway 只读接口尚未实现。` };
  }
  return { kind: "disconnected", message: `${url} → HTTP ${status}` };
}

async function fetchJson(
  baseUrl: string,
  path: string,
  timeoutMs: number,
  outerSignal?: AbortSignal,
): Promise<{ ok: true; data: unknown } | { ok: false; failure: ReadFailure }> {
  const url = `${baseUrl}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const onAbort = (): void => controller.abort("cancelled");
  outerSignal?.addEventListener("abort", onAbort);
  try {
    const response = await fetch(url, { method: "GET", signal: controller.signal, headers: { accept: "application/json" } });
    if (!response.ok) {
      return { ok: false, failure: classifyStatus(response.status, url) };
    }
    return { ok: true, data: await response.json() };
  } catch (error) {
    const reason = controller.signal.reason;
    if (reason === "cancelled" || outerSignal?.aborted === true) {
      return { ok: false, failure: { kind: "cancelled", message: "读取已取消。" } };
    }
    if (reason === "timeout") {
      return { ok: false, failure: { kind: "timeout", message: `${url} 在 ${timeoutMs}ms 内未响应。` } };
    }
    return {
      ok: false,
      failure: { kind: "disconnected", message: `${url} 不可达：${error instanceof Error ? error.message : String(error)}` },
    };
  } finally {
    clearTimeout(timer);
    outerSignal?.removeEventListener("abort", onAbort);
  }
}

export interface GatewayAdapterOptions {
  readonly baseUrl: string;
  readonly timeoutMs: number;
}

/**
 * Real-transport adapter for the future Gateway. With no base URL configured it
 * performs zero network calls and reports `not_configured`, which the UI shows
 * as 未接入 rather than as mock values.
 */
export function createGatewayAdapter(options: GatewayAdapterOptions | null): KinReadAdapter {
  const describe = (): AdapterDescriptor => ({
    id: options === null ? "gateway:unconfigured" : `gateway:${options.baseUrl}`,
    kind: "gateway",
    label: options === null ? "Gateway 只读接口 · 未配置" : `Gateway 只读接口 · ${options.baseUrl}`,
    mock: false,
    note:
      options === null
        ? "未设置 VITE_GATEWAY_BASE_URL；G lane 尚未冻结只读 read model。"
        : "端点与字段来自 D1 提议契约，任何不匹配都会失败关闭而不是猜测。",
  });

  if (options === null) {
    return {
      describe,
      async snapshot(): Promise<ReadResult<KinSnapshot>> {
        return fail("not_configured", "Gateway 只读接口未配置（无 G lane 契约）。");
      },
      async timeline(): Promise<ReadResult<readonly TimelineEvent[]>> {
        return fail("not_configured", "Gateway 只读接口未配置（无 G lane 契约）。");
      },
      async alerts(): Promise<ReadResult<readonly Alert[]>> {
        return fail("not_configured", "Gateway 只读接口未配置（无 G lane 契约）。");
      },
    };
  }

  const { baseUrl: rawBaseUrl, timeoutMs } = options;
  const baseUrl = rawBaseUrl.replace(/\/+$/, "");
  return {
    describe,
    async snapshot(signal?: AbortSignal): Promise<ReadResult<KinSnapshot>> {
      const response = await fetchJson(baseUrl, PROPOSED_ENDPOINTS.snapshot, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeSnapshotPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `快照契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.snapshot, "gateway", `gateway://${PROPOSED_ENDPOINTS.snapshot}`);
    },
    async timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>> {
      const url = `${PROPOSED_ENDPOINTS.timeline}?limit=${encodeURIComponent(String(query.limit))}`;
      const response = await fetchJson(baseUrl, url, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeTimelinePayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `时间线契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      const wanted = query.kinds.length === 0 ? decoded.events : decoded.events.filter((e) => query.kinds.includes(e.kind));
      return ok(wanted, "gateway", `gateway://${PROPOSED_ENDPOINTS.timeline}`);
    },
    async alerts(signal?: AbortSignal): Promise<ReadResult<readonly Alert[]>> {
      const response = await fetchJson(baseUrl, PROPOSED_ENDPOINTS.alerts, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeAlertsPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `告警契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.alerts, "gateway", `gateway://${PROPOSED_ENDPOINTS.alerts}`);
    },
  };
}

export type { HttpJson };
