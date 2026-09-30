import {
  IDENTITY_SCHEMA_VERSION,
  SNAPSHOT_SCHEMA_VERSION,
  filled,
  gapField,
  type AlertsEnvelope,
  type Alert,
  type AlertComponent,
  type AlertSeverity,
  type AlertState,
  type EvidenceRef,
  type Field,
  type FieldGapStatus,
  type Heartbeat,
  type IdentityInfo,
  type IdentityViewSnapshot,
  type KinRuntimeState,
  type KinSnapshot,
  type LinkState,
  type MediaStreamRef,
  type RenameRequest,
  type RenameResult,
  type RenameStatus,
  type SelfState,
  type SessionInfo,
  type SessionMode,
  type SkillStepInfo,
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
import {
  gap,
  known,
  type DataSourceKind,
  type Signal,
  type SignalContext,
  type SignalStatus,
} from "../domain/signals";
import {
  asBoolean,
  asInteger,
  asNullableNumber,
  asNullableString,
  asNumber,
  asRecord,
  asString,
  oneOf,
} from "./jsonGuards";

/**
 * The three reads frozen by `docs/gateway-dashboard-readonly-contract-2026-09-28.md`
 * §2.1 — exactly these GETs, each with the 3000 ms timeout pinned in `config.ts`;
 * a fourth path is a change to that record, not to this file. These decoders are
 * the single wire-to-domain path for BOTH adapters (gateway and mock), so the two
 * cannot drift: every mismatch fails closed as `contract_mismatch` rather than
 * guessing or filling a default.
 */
export const READ_ENDPOINTS = {
  snapshot: "/api/v1/dashboard/snapshot",
  timeline: "/api/v1/dashboard/timeline",
  alerts: "/api/v1/dashboard/alerts",
} as const;

/**
 * The identity surface `docs/stable-player-name-2026-09-29.md` opens: one GET that answers
 * who the Kin is (and hands out the per-process CSRF token), and the one POST rename the
 * card authorizes. They are kept apart from `READ_ENDPOINTS` because that tuple is the
 * frozen read-only contract; these two are the documented exception.
 */
export const IDENTITY_ENDPOINTS = {
  identity: "/api/v1/dashboard/identity",
  rename: "/api/v1/dashboard/identity/rename",
} as const;

/** The header `gateway/identity.py` requires the rename to echo the identity-GET token back in. */
export const CSRF_HEADER = "X-Minekin-CSRF-Token";

const KIN_STATES: readonly KinRuntimeState[] = ["idle", "running", "unresolved"];
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
// A member gap inside a known group never carries `permission_denied`: that status
// belongs to the envelope level (§2.2), matching `gateway/signals.py`'s use here.
const FIELD_GAP_STATUSES: readonly FieldGapStatus[] = ["unknown", "unavailable", "not_wired"];

interface WireSignal {
  readonly status: SignalStatus;
  readonly reason: string;
  readonly ctx: SignalContext;
  readonly value: unknown;
}

function decodeSignal(
  raw: unknown,
  path: string,
  issues: string[],
  source: DataSourceKind,
): WireSignal | null {
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
  return { status, reason, value: rec.value, ctx: { source, sourceRef, observedAt, staleAfterMs } };
}

type GroupParser<T> = (raw: unknown, issues: string[]) => T | null;

function typed<T>(
  wire: WireSignal,
  path: string,
  issues: string[],
  parse: GroupParser<T>,
): Signal<T> | null {
  if (wire.status !== "known") {
    return gap(wire.status, wire.reason, wire.ctx);
  }
  const value = parse(wire.value, issues);
  if (value === null) {
    issues.push(`${path}.value: 取值不符合只读契约`);
    return null;
  }
  return known(value, wire.ctx);
}

function parseString(raw: unknown): string | null {
  return asString(raw);
}

/**
 * One member of a `known` group: the wire shape is `{"value": …}` when Core has a
 * carrier and `{"gap": {"status", "reason"}}` when it does not (§3 C-tier census).
 * A member that is neither, whose `value` is null, or whose gap has no reason is
 * rejected outright — there is deliberately no branch that fills a default.
 */
function decodeField<T>(
  raw: unknown,
  path: string,
  issues: string[],
  parse: (v: unknown) => T | null,
): Field<T> | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 组内成员期望 {value} 或 {gap} 对象`);
    return null;
  }
  const hasValue = "value" in rec;
  const hasGap = "gap" in rec;
  if (hasValue === hasGap) {
    issues.push(`${path}: 组内成员必须恰有 value 或 gap 之一`);
    return null;
  }
  if (hasValue) {
    const parsed = parse(rec.value);
    if (parsed === null) {
      issues.push(`${path}.value: 取值缺失或类型不符`);
      return null;
    }
    return filled(parsed);
  }
  const gapRec = asRecord(rec.gap);
  if (gapRec === null) {
    issues.push(`${path}.gap: 期望 {status, reason} 对象`);
    return null;
  }
  const status = oneOf(gapRec.status, FIELD_GAP_STATUSES);
  const reason = asString(gapRec.reason) ?? "";
  if (status === null || reason === "") {
    issues.push(`${path}.gap: 缺口状态未知或缺少原因`);
    return null;
  }
  return gapField(status, reason);
}

function parseSession(raw: unknown, issues: string[]): SessionInfo | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("session: 期望 object");
    return null;
  }
  const sessionId = decodeField(rec.sessionId, "session.sessionId", issues, parseString);
  const generation = decodeField(rec.generation, "session.generation", issues, asInteger);
  const startedAt = decodeField(rec.startedAt, "session.startedAt", issues, parseString);
  const pid = decodeField(rec.pid, "session.pid", issues, asInteger);
  const overlay = decodeField(rec.overlay, "session.overlay", issues, parseString);
  const mode = decodeField(rec.mode, "session.mode", issues, (v) => oneOf(v, SESSION_MODES));
  if (sessionId === null || generation === null || startedAt === null || pid === null || overlay === null || mode === null) {
    return null;
  }
  return { sessionId, generation, startedAt, pid, overlay, mode };
}

function parseWorld(raw: unknown, issues: string[]): WorldInfo | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("world: 期望 object");
    return null;
  }
  const profileId = decodeField(rec.profileId, "world.profileId", issues, parseString);
  const profileName = decodeField(rec.profileName, "world.profileName", issues, parseString);
  const worldContext = decodeField(rec.worldContext, "world.worldContext", issues, parseString);
  const epoch = decodeField(rec.epoch, "world.epoch", issues, asInteger);
  const joined = decodeField(rec.joined, "world.joined", issues, asBoolean);
  const resolvedVersion = decodeField(rec.resolvedVersion, "world.resolvedVersion", issues, parseString);
  if (profileId === null || profileName === null || worldContext === null || epoch === null || joined === null || resolvedVersion === null) {
    return null;
  }
  return { profileId, profileName, worldContext, epoch, joined, resolvedVersion };
}

function parseVersions(raw: unknown, issues: string[]): VersionSet | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("versions: 期望 object");
    return null;
  }
  const runtime = decodeField(rec.runtime, "versions.runtime", issues, parseString);
  const bridge = decodeField(rec.bridge, "versions.bridge", issues, parseString);
  const clientBundle = decodeField(rec.clientBundle, "versions.clientBundle", issues, parseString);
  const java = decodeField(rec.java, "versions.java", issues, parseString);
  const fabricLoader = decodeField(rec.fabricLoader, "versions.fabricLoader", issues, parseString);
  if (runtime === null || bridge === null || clientBundle === null || java === null || fabricLoader === null) {
    return null;
  }
  return { runtime, bridge, clientBundle, java, fabricLoader };
}

function parseHeartbeat(raw: unknown, issues: string[]): Heartbeat | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("bridgeHeartbeat: 期望 object");
    return null;
  }
  const lastSequence = decodeField(rec.lastSequence, "bridgeHeartbeat.lastSequence", issues, asInteger);
  const lastObservedAt = decodeField(rec.lastObservedAt, "bridgeHeartbeat.lastObservedAt", issues, parseString);
  const intervalMs = decodeField(rec.intervalMs, "bridgeHeartbeat.intervalMs", issues, asNumber);
  const inputLeaseHeld = decodeField(rec.inputLeaseHeld, "bridgeHeartbeat.inputLeaseHeld", issues, asBoolean);
  if (lastSequence === null || lastObservedAt === null || intervalMs === null || inputLeaseHeld === null) {
    return null;
  }
  return { lastSequence, lastObservedAt, intervalMs, inputLeaseHeld };
}

// health/food arrive as bare numbers inside the group value: this is Core's
// `SelfStateValue` reading, and the group envelope is what degrades to a gap
// when the projection cannot reach it. `dimension`/`guiOpen` have no carrier
// (§3) and no longer exist in the model, so a response carrying them is a
// contract mismatch rather than something to silently drop.
function parseSelfState(raw: unknown, issues: string[]): SelfState | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("selfState: 期望 object");
    return null;
  }
  const health = asNumber(rec.health);
  const food = asNumber(rec.food);
  if (health === null || food === null || "dimension" in rec || "guiOpen" in rec) {
    issues.push("selfState.value: 期望仅含 health/food 数值");
    return null;
  }
  return { health, food };
}

function parseEvidence(raw: unknown, issues: string[]): EvidenceRef | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("evidence: 期望 object");
    return null;
  }
  const runId = decodeField(rec.runId, "evidence.runId", issues, parseString);
  const attempt = decodeField(rec.attempt, "evidence.attempt", issues, asInteger);
  const bundleDigest = decodeField(rec.bundleDigest, "evidence.bundleDigest", issues, parseString);
  const sealedAt = decodeField(rec.sealedAt, "evidence.sealedAt", issues, parseString);
  if (runId === null || attempt === null || bundleDigest === null || sealedAt === null) {
    return null;
  }
  return { runId, attempt, bundleDigest, sealedAt };
}

/**
 * The `skillSteps` group as `gateway/readmodel.py::_skill_steps_group` answers it.
 * Every member is a `{value}`/`{gap}` field on the wire — the projection names its
 * own empties (a scripted run's goal, a confirmed step's reason) instead of sending
 * `""`, so there is no defaulted branch here either. `result` and `decisionSource`
 * decode as plain strings rather than pinned enums: they are Core's tokens passed
 * through verbatim, and a token Core adds later must render rather than fail-close
 * the whole snapshot.
 */
function parseSkillSteps(raw: unknown, issues: string[]): SkillStepInfo | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("skillSteps: 期望 object");
    return null;
  }
  // §4 rule 1 taken literally: the allowlist is the whole projected surface, and the two
  // ledger-internal identifiers a SkillStepRecorded row carries must not reach a panel.
  // Like `selfState`'s refused `dimension`/`guiOpen`, a response carrying them is a
  // contract mismatch, not something to silently drop.
  if ("action_id" in rec || "lease_id" in rec || "actionId" in rec || "leaseId" in rec) {
    issues.push("skillSteps.value: 台账内部标识 action_id/lease_id 不得进投影");
    return null;
  }
  const goal = decodeField(rec.goal, "skillSteps.goal", issues, parseString);
  const stepIndex = decodeField(rec.stepIndex, "skillSteps.stepIndex", issues, asInteger);
  const skill = decodeField(rec.skill, "skillSteps.skill", issues, parseString);
  const result = decodeField(rec.result, "skillSteps.result", issues, parseString);
  const reason = decodeField(rec.reason, "skillSteps.reason", issues, parseString);
  const attribution = decodeField(rec.attribution, "skillSteps.attribution", issues, parseString);
  const decisionSource = decodeField(rec.decisionSource, "skillSteps.decisionSource", issues, parseString);
  const modelRefusal = decodeField(rec.modelRefusal, "skillSteps.modelRefusal", issues, parseString);
  const stepCount = decodeField(rec.stepCount, "skillSteps.stepCount", issues, asInteger);
  const modelCost = decodeField(rec.modelCost, "skillSteps.modelCost", issues, parseString);
  const modelConfig = decodeField(rec.modelConfig, "skillSteps.modelConfig", issues, parseString);
  if (
    goal === null ||
    stepIndex === null ||
    skill === null ||
    result === null ||
    reason === null ||
    attribution === null ||
    decisionSource === null ||
    modelRefusal === null ||
    stepCount === null ||
    modelCost === null ||
    modelConfig === null
  ) {
    return null;
  }
  return { goal, stepIndex, skill, result, reason, attribution, decisionSource, modelRefusal, stepCount, modelCost, modelConfig };
}

function bareField<T>(
  rec: Record<string, unknown>,
  key: string,
  path: string,
  issues: string[],
  parse: (v: unknown) => T | null,
): T | null {
  const value = parse(rec[key]);
  if (value === null) {
    issues.push(`${path}.${key}: 字段缺失或类型不符`);
    return null;
  }
  return value;
}

function parseMedia(raw: unknown, issues: string[]): MediaStreamRef | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("liveView: 期望 object");
    return null;
  }
  const available = bareField(rec, "available", "liveView", issues, asBoolean);
  const transport = bareField(rec, "transport", "liveView", issues, (v) => oneOf(v, MEDIA_TRANSPORTS));
  const url = bareField(rec, "url", "liveView", issues, parseString);
  const startedAt = bareField(rec, "startedAt", "liveView", issues, parseString);
  if (available === null || transport === null || url === null || startedAt === null) return null;
  return { available, transport, url, startedAt };
}

export type SnapshotDecode =
  | { readonly ok: true; readonly snapshot: KinSnapshot }
  | { readonly ok: false; readonly issues: readonly string[] };

export function decodeSnapshotPayload(raw: unknown, source: DataSourceKind = "gateway"): SnapshotDecode {
  const issues: string[] = [];
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$ : 响应不是 object"] };
  if (asString(rec.schemaVersion) !== SNAPSHOT_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${SNAPSHOT_SCHEMA_VERSION}`);
  }

  const kinId = decodeAndType<string>(rec.kinId, "kinId", issues, parseString, source);
  const runtimeState = decodeAndType<KinRuntimeState>(rec.runtimeState, "runtimeState", issues, (v) => oneOf(v, KIN_STATES), source);
  const bridgeLink = decodeAndType<LinkState>(rec.bridgeLink, "bridgeLink", issues, (v) => oneOf(v, LINK_STATES), source);
  const serverLink = decodeAndType<LinkState>(rec.serverLink, "serverLink", issues, (v) => oneOf(v, LINK_STATES), source);
  const session = decodeAndType<SessionInfo>(rec.session, "session", issues, parseSession, source);
  const world = decodeAndType<WorldInfo>(rec.world, "world", issues, parseWorld, source);
  // `skillSteps` is the one group that may be legitimately ABSENT from the bytes: the
  // verbatim historical captures in `src/test/realGatewayWire.ts` were frozen before this
  // projection landed, and they must keep decoding. A missing key therefore synthesizes a
  // group-level `not_wired` gap naming its absence — the same two-level rule the contract
  // applies inside a known group, lifted to the group itself. A key that IS present must
  // still decode strictly.
  const skillSteps: Signal<SkillStepInfo> | null =
    rec.skillSteps === undefined
      ? gap("not_wired", "响应字节里没有 skillSteps 组：这枚快照产自加上该投影之前的 Gateway。", {
          source,
          sourceRef: "snapshot://absent/skillSteps",
          observedAt: null,
          staleAfterMs: null,
        })
      : decodeAndType<SkillStepInfo>(rec.skillSteps, "skillSteps", issues, parseSkillSteps, source);
  const versions = decodeAndType<VersionSet>(rec.versions, "versions", issues, parseVersions, source);
  const bridgeHeartbeat = decodeAndType<Heartbeat>(rec.bridgeHeartbeat, "bridgeHeartbeat", issues, parseHeartbeat, source);
  const selfState = decodeAndType<SelfState>(rec.selfState, "selfState", issues, parseSelfState, source);
  const evidence = decodeAndType<EvidenceRef>(rec.evidence, "evidence", issues, parseEvidence, source);
  const liveView = decodeAndType<MediaStreamRef>(rec.liveView, "liveView", issues, parseMedia, source);

  if (
    kinId === null ||
    runtimeState === null ||
    bridgeLink === null ||
    serverLink === null ||
    session === null ||
    world === null ||
    skillSteps === null ||
    versions === null ||
    bridgeHeartbeat === null ||
    selfState === null ||
    evidence === null ||
    liveView === null
  ) {
    return { ok: false, issues: [...issues, "$: 字段解码失败"] };
  }
  if (issues.length > 0) return { ok: false, issues };
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
      skillSteps,
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
  parse: GroupParser<T>,
  source: DataSourceKind,
): Signal<T> | null {
  const wire = decodeSignal(raw, path, issues, source);
  if (wire === null) return null;
  return typed(wire, path, issues, parse);
}

export type TimelineDecode =
  | { readonly ok: true; readonly events: readonly TimelineEvent[] }
  | { readonly ok: false; readonly issues: readonly string[] };

export function decodeTimelinePayload(raw: unknown): TimelineDecode {
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
    events.push({ eventId, kind, at, title, outcome, sourceRef, monotonicMs, generation, sequence, detail });
  }
  return issues.length > 0 ? { ok: false, issues } : { ok: true, events };
}

function decodeAlert(raw: unknown, path: string, issues: string[]): Alert | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 object`);
    return null;
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
    return null;
  }
  return { alertId, severity, state, component, title, detail, firstSeenAt, lastSeenAt, sourceRef };
}

export type AlertsDecode =
  | { readonly ok: true; readonly envelope: AlertsEnvelope }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * §5.3 (`ALERT_SOURCE_AMBIGUITY`): alerts arrive as an envelope, never a bare
 * array. A non-`known` status without a non-empty reason is rejected (§2.2), so
 * 「没有告警」 can only come from a `known` empty list and 「无告警源」 always
 * carries the reason the source gave.
 */
export function decodeAlertsPayload(raw: unknown): AlertsDecode {
  const rec = asRecord(raw);
  if (rec === null) {
    return { ok: false, issues: ["$: 告警必须是信封对象（契约 §5.3），不接受裸数组"] };
  }
  const issues: string[] = [];
  const status = oneOf(rec.status, SIGNAL_STATUSES);
  if (status === null) issues.push("$.status: 未知取值");
  if (!Array.isArray(rec.alerts)) {
    issues.push("$.alerts: 信封必须携带告警数组");
    return { ok: false, issues };
  }
  const alerts: Alert[] = [];
  for (const [index, item] of (rec.alerts as readonly unknown[]).entries()) {
    const alertItem = decodeAlert(item, `alerts[${index}]`, issues);
    if (alertItem !== null) alerts.push(alertItem);
  }
  const reason = asString(rec.reason) ?? "";
  if (status !== null && status !== "known" && reason === "") {
    issues.push("$.reason: 缺口必须给出原因（无告警源要说清为什么）");
  }
  // A gap status that still lists alerts contradicts itself: the source claims it
  // cannot answer, yet answers — fail closed rather than render half of it.
  if (status !== null && status !== "known" && alerts.length > 0) {
    issues.push("$.alerts: 非 known 状态不得携带告警条目");
  }
  if (issues.length > 0 || status === null) return { ok: false, issues };
  return { ok: true, envelope: { status, reason, alerts } };
}

const RENAME_STATUSES: readonly RenameStatus[] = ["renamed", "unchanged"];

export type IdentityDecode =
  | { readonly ok: true; readonly identity: IdentityInfo; readonly csrfToken: string }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * The identity read `gateway/identity.py::identity_read` answers: a flat document, so any
 * missing field or out-of-enum value is a whole-document mismatch rather than a partial
 * fill. `csrfToken` is returned beside the model but deliberately left OUT of `IdentityInfo`
 * — a panel must not be able to render the token, and the adapter keeps it for the rename.
 */
export function decodeIdentityPayload(raw: unknown): IdentityDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 身份响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== IDENTITY_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${IDENTITY_SCHEMA_VERSION}`);
  }
  const kinId = asString(rec.kinId);
  const username = asString(rec.username);
  const uuidCanonical = asString(rec.uuidCanonical);
  const identityRevision = asInteger(rec.identityRevision);
  const state = oneOf(rec.state, KIN_STATES);
  const renameAllowed = asBoolean(rec.renameAllowed);
  const notice = asString(rec.notice);
  const csrfToken = asString(rec.csrfToken);
  const observedAt = asString(rec.observedAt);
  const staleAfterMs = asNumber(rec.staleAfterMs);
  if (kinId === null) issues.push("$.kinId: 缺失或非字符串");
  if (username === null) issues.push("$.username: 缺失或非字符串");
  if (uuidCanonical === null) issues.push("$.uuidCanonical: 缺失或非字符串");
  if (identityRevision === null) issues.push("$.identityRevision: 缺失或非整数");
  if (state === null) issues.push("$.state: 未知取值");
  if (renameAllowed === null) issues.push("$.renameAllowed: 缺失或非布尔");
  if (notice === null) issues.push("$.notice: 缺失或非字符串");
  if (csrfToken === null) issues.push("$.csrfToken: 缺失（无法改名）");
  if (observedAt === null) issues.push("$.observedAt: 缺失或非字符串");
  if (staleAfterMs === null) issues.push("$.staleAfterMs: 缺失或非数值");
  if (issues.length > 0) return { ok: false, issues };
  return {
    ok: true,
    csrfToken: csrfToken as string,
    identity: {
      kinId: kinId as string,
      username: username as string,
      uuidCanonical: uuidCanonical as string,
      identityRevision: identityRevision as number,
      state: state as KinRuntimeState,
      renameAllowed: renameAllowed as boolean,
      notice: notice as string,
      observedAt: observedAt as string,
      staleAfterMs: staleAfterMs as number,
    },
  };
}

function parseIdentityView(raw: unknown, path: string, issues: string[]): IdentityViewSnapshot | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 object`);
    return null;
  }
  const username = asString(rec.username);
  const uuidCanonical = asString(rec.uuidCanonical);
  const identityRevision = asInteger(rec.identityRevision);
  if (username === null || uuidCanonical === null || identityRevision === null) {
    issues.push(`${path}: 字段缺失或类型不符`);
    return null;
  }
  return { username, uuidCanonical, identityRevision };
}

export type RenameDecode =
  | { readonly ok: true; readonly result: RenameResult }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * A rename that the server accepted (HTTP 2xx): the before/after views, whether the UUID
 * moved, and Core's notice. A refusal never reaches this decoder — the transport routes a
 * non-2xx answer through `decodeRefusalPayload` instead, so the named reason survives.
 */
export function decodeRenamePayload(raw: unknown): RenameDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 改名响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== IDENTITY_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${IDENTITY_SCHEMA_VERSION}`);
  }
  const status = oneOf(rec.status, RENAME_STATUSES);
  if (status === null) issues.push("$.status: 未知改名结果");
  const kinId = asString(rec.kinId);
  if (kinId === null) issues.push("$.kinId: 缺失或非字符串");
  const uuidChanged = asBoolean(rec.uuidChanged);
  if (uuidChanged === null) issues.push("$.uuidChanged: 缺失或非布尔");
  const notice = asString(rec.notice);
  if (notice === null) issues.push("$.notice: 缺失或非字符串");
  const before = parseIdentityView(rec.before, "$.before", issues);
  const after = parseIdentityView(rec.after, "$.after", issues);
  if (status === null || kinId === null || uuidChanged === null || notice === null || before === null || after === null) {
    return { ok: false, issues };
  }
  return { ok: true, result: { status, kinId, before, after, uuidChanged, notice } };
}

/**
 * The body of a refused rename (`gateway/identity.py::refusal`): `{schemaVersion, error,
 * message}`. `error` is the named reason — `session_not_stopped`, `stale_revision`,
 * `invalid_request`, `missing_or_bad_csrf_token`, `cross_origin`, `forbidden_host`,
 * `unsupported_media_type` — so the panel says which check tripped instead of folding every
 * refusal into one generic failure.
 */
export function decodeRefusalPayload(raw: unknown): { readonly code: string; readonly message: string } | null {
  const rec = asRecord(raw);
  if (rec === null) return null;
  const error = asString(rec.error);
  const message = asString(rec.message);
  if (error === null || message === null) return null;
  return { code: error, message };
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

type PostResult =
  | { readonly kind: "ok"; readonly data: unknown }
  | { readonly kind: "refusal"; readonly code: string; readonly message: string }
  | { readonly kind: "failure"; readonly failure: ReadFailure };

function parseMaybeJson(text: string): unknown {
  if (text === "") return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined; // present but not JSON — distinct from `null` (an empty body)
  }
}

/**
 * The one POST the identity card authorizes. It carries the per-process CSRF token in
 * `CSRF_HEADER` and `content-type: application/json` — the two headers that together make a
 * cross-site request impossible to forge (a cross-site form cannot set either without a
 * preflight, and this browser→same-origin call is not cross-site). A server refusal comes
 * back as a `refusal` with its named reason; a transport break comes back as a `failure`.
 */
async function postRename(
  baseUrl: string,
  path: string,
  timeoutMs: number,
  body: RenameRequest,
  csrfToken: string,
  outerSignal?: AbortSignal,
): Promise<PostResult> {
  const url = `${baseUrl}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const onAbort = (): void => controller.abort("cancelled");
  outerSignal?.addEventListener("abort", onAbort);
  try {
    const response = await fetch(url, {
      method: "POST",
      signal: controller.signal,
      headers: { accept: "application/json", "content-type": "application/json", [CSRF_HEADER]: csrfToken },
      body: JSON.stringify(body),
    });
    const parsed = parseMaybeJson(await response.text());
    if (response.ok) {
      if (parsed === undefined) {
        return { kind: "failure", failure: { kind: "contract_mismatch", message: `${url} → 响应不是合法 JSON。` } };
      }
      return { kind: "ok", data: parsed };
    }
    if (typeof parsed === "object" && parsed !== null) {
      const refusal = decodeRefusalPayload(parsed);
      if (refusal !== null) return { kind: "refusal", code: refusal.code, message: refusal.message };
    }
    return { kind: "failure", failure: classifyStatus(response.status, url) };
  } catch (error) {
    const reason = controller.signal.reason;
    if (reason === "cancelled" || outerSignal?.aborted === true) {
      return { kind: "failure", failure: { kind: "cancelled", message: "改名请求已取消。" } };
    }
    if (reason === "timeout") {
      return { kind: "failure", failure: { kind: "timeout", message: `${url} 在 ${timeoutMs}ms 内未响应。` } };
    }
    return {
      kind: "failure",
      failure: { kind: "disconnected", message: `${url} 不可达：${error instanceof Error ? error.message : String(error)}` },
    };
  } finally {
    clearTimeout(timer);
    outerSignal?.removeEventListener("abort", onAbort);
  }
}

/**
 * Real-transport adapter for the frozen Gateway. With no base URL configured it
 * performs zero network calls and reports `not_configured`, which the UI shows
 * as 未配置 rather than as mock values.
 */
export function createGatewayAdapter(options: GatewayAdapterOptions | null): KinReadAdapter {
  const describe = (): AdapterDescriptor => ({
    id: options === null ? "gateway:unconfigured" : `gateway:${options.baseUrl}`,
    kind: "gateway",
    label: options === null ? "Gateway 只读接口 · 未配置" : `Gateway 只读接口 · ${options.baseUrl}`,
    mock: false,
    note:
      options === null
        ? "未设置 VITE_GATEWAY_BASE_URL：契约已冻结，等待 Gateway 基址，期间零网络调用。"
        : "按 docs/gateway-dashboard-readonly-contract-2026-09-28.md 冻结的三条只读 GET 读取，任何不匹配都会失败关闭而不是猜测；身份页只做 docs/stable-player-name-2026-09-29.md 授权的一次改名写入。",
  });

  if (options === null) {
    const unconfigured = (): ReadResult<never> =>
      fail("not_configured", "Gateway 只读接口未配置（无基址，零网络调用）。");
    return {
      describe,
      async snapshot(): Promise<ReadResult<KinSnapshot>> {
        return unconfigured();
      },
      async timeline(): Promise<ReadResult<readonly TimelineEvent[]>> {
        return unconfigured();
      },
      async alerts(): Promise<ReadResult<AlertsEnvelope>> {
        return unconfigured();
      },
      async identity(): Promise<ReadResult<IdentityInfo>> {
        return unconfigured();
      },
      async renameIdentity(): Promise<ReadResult<RenameResult>> {
        return unconfigured();
      },
    };
  }

  const { baseUrl: rawBaseUrl, timeoutMs } = options;
  const baseUrl = rawBaseUrl.replace(/\/+$/, "");
  // Captured from the identity GET and echoed on the rename POST. The token is per-process,
  // so it is refreshed on every identity poll; a rename before the first successful read has
  // nothing to echo and the server refuses it — which is the correct, honest outcome.
  let csrfToken = "";
  return {
    describe,
    async snapshot(signal?: AbortSignal): Promise<ReadResult<KinSnapshot>> {
      const response = await fetchJson(baseUrl, READ_ENDPOINTS.snapshot, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeSnapshotPayload(response.data, "gateway");
      if (!decoded.ok) {
        return fail("contract_mismatch", `快照契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.snapshot, "gateway", `gateway://${READ_ENDPOINTS.snapshot}`);
    },
    async timeline(query: TimelineQuery, signal?: AbortSignal): Promise<ReadResult<readonly TimelineEvent[]>> {
      const url = `${READ_ENDPOINTS.timeline}?limit=${encodeURIComponent(String(query.limit))}`;
      const response = await fetchJson(baseUrl, url, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeTimelinePayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `时间线契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      const wanted = query.kinds.length === 0 ? decoded.events : decoded.events.filter((e) => query.kinds.includes(e.kind));
      return ok(wanted, "gateway", `gateway://${READ_ENDPOINTS.timeline}`);
    },
    async alerts(signal?: AbortSignal): Promise<ReadResult<AlertsEnvelope>> {
      const response = await fetchJson(baseUrl, READ_ENDPOINTS.alerts, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeAlertsPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `告警契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.envelope, "gateway", `gateway://${READ_ENDPOINTS.alerts}`);
    },
    async identity(signal?: AbortSignal): Promise<ReadResult<IdentityInfo>> {
      const response = await fetchJson(baseUrl, IDENTITY_ENDPOINTS.identity, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeIdentityPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `身份契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      csrfToken = decoded.csrfToken;
      return ok(decoded.identity, "gateway", `gateway://${IDENTITY_ENDPOINTS.identity}`);
    },
    async renameIdentity(request: RenameRequest, signal?: AbortSignal): Promise<ReadResult<RenameResult>> {
      const result = await postRename(baseUrl, IDENTITY_ENDPOINTS.rename, timeoutMs, request, csrfToken, signal);
      if (result.kind === "failure") return { ok: false, failure: result.failure };
      if (result.kind === "refusal") {
        return fail("write_refused", `${result.code}：${result.message}`);
      }
      const decoded = decodeRenamePayload(result.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `改名结果契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "gateway", `gateway://${IDENTITY_ENDPOINTS.rename}`);
    },
  };
}
