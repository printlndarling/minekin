import {
  CONFIG_SCHEMA_VERSION,
  GOAL_SCHEMA_VERSION,
  IDENTITY_SCHEMA_VERSION,
  RECIPE_SCHEMA_VERSION,
  SESSION_SCHEMA_VERSION,
  SNAPSHOT_SCHEMA_VERSION,
  filled,
  gapField,
  type AlertsEnvelope,
  type Alert,
  type AlertComponent,
  type AlertSeverity,
  type AlertState,
  type ConfigInfo,
  type ConfigSaveRequest,
  type ConfigSaveResult,
  type ModelTestResult,
  type SessionStartRequest, type SessionStartResult, type SessionJobInfo, type SessionJob,
  type ServerConfigInfo, type ServerSaveRequest, type ServerSaveResult, type ServerProbeResult,
  type ConfigValue,
  type EvidenceRef,
  type Field,
  type FieldGapStatus,
  type GoalInfo,
  type GoalMilestone,
  type GoalPlanMaterial,
  type GoalPlanStep,
  type Heartbeat,
  type IdentityInfo,
  type SavedPersona,
  type SkillExperience,
  type IdentityViewSnapshot,
  type KinRuntimeState,
  type KinSnapshot,
  type LinkState,
  type MediaStreamRef,
  type RenameRequest,
  type RenameResult,
  type RenameStatus,
  type RecipeCoverageInfo,
  type RecipeIngredient,
  type RecipeRow,
  type SelfState,
  type SessionControlInfo,
  type SessionInfo,
  type SessionMode,
  type SkillStepInfo,
  type StopReleaseReport,
  type StopReport,
  type StopRequest,
  type StopResult,
  type StopStatus,
  type TimelineEvent,
  type TimelineKind,
  type TimelineOutcome,
  type UnavailableControl,
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

function validServerFields(raw: unknown): raw is ServerSaveResult["fields"] {
  const rec = asRecord(raw);
  return rec !== null && typeof rec.host === "string" && rec.host.length > 0 &&
    typeof rec.port === "number" && Number.isSafeInteger(rec.port) && rec.port > 0 && rec.port <= 65535;
}

function validServerRecord(rec: Record<string, unknown> | null): rec is Record<string, unknown> {
  return rec !== null && rec.schemaVersion === "kin-dashboard-server/1.0.0" && rec.authMode === "offline" &&
    typeof rec.revision === "number" && Number.isSafeInteger(rec.revision) && rec.revision >= 0 &&
    (rec.fields === null || validServerFields(rec.fields));
}

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

/**
 * The config surface `gateway/config_write.py` opens: one GET that answers what settings are
 * saved (and hands out the SAME per-process CSRF token the identity read does), and the one POST
 * save the whole-project goal's Phase D authorizes. Kept apart from `READ_ENDPOINTS` because that
 * tuple is the frozen read-only contract; these two are the second documented exception.
 */
export const CONFIG_ENDPOINTS = {
  config: "/api/v1/dashboard/config",
  save: "/api/v1/dashboard/config/save",
} as const;

/**
 * The session surface `gateway/session_control.py` opens: one GET that answers whether the recorded
 * Kin can be stopped (and hands out the SAME per-process CSRF token the identity/config reads do),
 * and the one POST stop the whole-project goal's Phase D authorizes. Kept apart from
 * `READ_ENDPOINTS` because that tuple is the frozen read-only contract; these two are the third
 * documented exception — and unlike the config write it reduces activity rather than persisting it.
 */
export const SESSION_ENDPOINTS = {
  session: "/api/v1/dashboard/session",
  stop: "/api/v1/dashboard/session/stop",
} as const;

/**
 * The goal surface `gateway/goal_read.py` opens: one GET that answers the standing milestone the
 * config write already saved plus the plan the recipe catalog implies. It is a READ, not a fourth
 * write — setting a goal stays `CONFIG_ENDPOINTS.save`'s job — so only this one path exists and the
 * per-process token the payload echoes is dropped at the seam rather than captured.
 */
export const GOAL_ENDPOINTS = {
  goal: "/api/v1/dashboard/goal",
} as const;

/**
 * The recipe-coverage surface `gateway/recipe_read.py` opens: one GET that answers the whole covered
 * region of the curated catalog — the version, the watched/curated split and one row per craft — so
 * the panel can show the catalog's support BOUNDARY (criterion 6), not only the plan one product
 * implies. It is a READ with no write sibling, so only this one path exists and — unlike the goal read,
 * whose payload still echoes a token the seam drops — the recipe payload carries no `csrfToken` at all.
 */
export const RECIPE_ENDPOINTS = {
  recipe: "/api/v1/dashboard/recipe-coverage",
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
  // The projection does not carry max_health, so do not cap health at vanilla
  // 20: effects may raise it. Food is still an integer hunger level in [0, 20].
  if (health < 0 || !Number.isInteger(food) || food < 0 || food > 20) {
    issues.push("selfState.value: 生命必须非负，饥饿必须是 0..20 的整数");
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
 *
 * `behaviorParameters` is the one member decoded optionally. Current projection bytes
 * always emit it, but `readmodel.py` gained it after the run-document read landed, so a
 * snapshot from an earlier byte omits the key — that must render as a named gap, not
 * fail-close the whole group. Only its absence is tolerated; a present-but-malformed
 * member fails like every other one.
 */
const BEHAVIOR_PARAMETERS_ABSENT_GAP =
  "本快照字节未携带行为参数成员（投影早于该字段）：行为参数只在已封 bundle 的 run document 里解析。";

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
  const behaviorParameters =
    "behaviorParameters" in rec
      ? decodeField(rec.behaviorParameters, "skillSteps.behaviorParameters", issues, parseString)
      : gapField<string>("not_wired", BEHAVIOR_PARAMETERS_ABSENT_GAP);
  const personaContext = "personaContext" in rec
    ? decodeField(rec.personaContext, "skillSteps.personaContext", issues, parseString)
    : gapField<string>("not_wired", "旧快照未携带人格输入来源，不证明模型已采用人格。");
  const sessionHistory = "sessionHistory" in rec
    ? decodeField(rec.sessionHistory, "skillSteps.sessionHistory", issues, parseString)
    : gapField<string>("not_wired", "旧快照未携带历史记忆输入，不补造当前世界知识。");
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
    modelConfig === null ||
    behaviorParameters === null || personaContext === null || sessionHistory === null
  ) {
    return null;
  }
  return {
    goal,
    stepIndex,
    skill,
    result,
    reason,
    attribution,
    decisionSource,
    modelRefusal,
    stepCount,
    modelCost,
    modelConfig,
    behaviorParameters,
    personaContext,
    sessionHistory,
  };
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

function parseSavedPersona(raw: unknown, issues: string[]): SavedPersona | null {
  const rec = asRecord(raw);
  const traits = rec === null ? null : asRecord(rec.traits);
  const names = ["social_initiative", "cooperation", "orderliness", "curiosity", "risk_tolerance"];
  const values = ["autonomy", "fairness", "resource_security", "belonging", "exploration", "creation"];
  const allowed = ["manifest_sha256", "schema_version", "algorithm", "traits", "value_priority"];
  if (rec === null || Object.keys(rec).some((key) => !allowed.includes(key)) ||
      typeof rec.manifest_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(rec.manifest_sha256) ||
      rec.schema_version !== 1 || rec.algorithm !== "persona-blake2b-v1" || traits === null ||
      Object.keys(traits).length !== names.length || names.some((name) =>
        typeof traits[name] !== "number" || !Number.isInteger(traits[name]) || traits[name] < 1 || traits[name] > 9) ||
      !Array.isArray(rec.value_priority) || rec.value_priority.length !== values.length ||
      new Set(rec.value_priority).size !== values.length ||
      rec.value_priority.some((value: unknown) => typeof value !== "string" || !values.includes(value))) {
    issues.push("$.persona: 已保存人格字段不合法或携带非公开字段");
    return null;
  }
  return {
    manifest_sha256: rec.manifest_sha256, schema_version: 1, algorithm: rec.algorithm,
    traits: traits as Record<string, number>, value_priority: rec.value_priority as string[],
  };
}

/**
 * The identity read `gateway/identity.py::identity_read` answers: a flat document, so any
 * missing field or out-of-enum value is a whole-document mismatch rather than a partial
 * fill. `csrfToken` is returned beside the model but deliberately left OUT of `IdentityInfo`
 * — a panel must not be able to render the token, and the adapter keeps it for the rename.
 */
function parseExperiences(raw: unknown, issues: string[]): readonly SkillExperience[] | null {
  if (!Array.isArray(raw) || raw.length > 8) {
    issues.push("$.experiences: 期望最多 8 条经历");
    return null;
  }
  const records: SkillExperience[] = [];
  const keys = ["event_id", "event_position", "run_id", "session_id", "observed_at_utc",
    "source", "trust_class", "skill", "result", "reason", "decision_source"];
  const ref = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value);
  for (const entry of raw) {
    const rec = asRecord(entry);
    if (rec === null || Object.keys(rec).length !== keys.length || keys.some((key) => !(key in rec)) ||
        !ref(rec.event_id) || !ref(rec.run_id) || !(rec.session_id === null || ref(rec.session_id)) ||
        typeof rec.event_position !== "number" || !Number.isSafeInteger(rec.event_position) || rec.event_position < 1 ||
        typeof rec.observed_at_utc !== "string" || rec.observed_at_utc.length > 40 ||
        !Number.isFinite(Date.parse(rec.observed_at_utc)) || !/(Z|[+-]\d{2}:\d{2})$/.test(rec.observed_at_utc) ||
        rec.source !== "CORE" || rec.trust_class !== "CORE" ||
        typeof rec.skill !== "string" || !/^[a-z_]{1,64}$/.test(rec.skill) ||
        typeof rec.result !== "string" || !["STARTED", "CONFIRMED", "FAILED", "INTERRUPTED", "UNKNOWN"].includes(rec.result) ||
        typeof rec.reason !== "string" || !/^[A-Z0-9_]{0,96}$/.test(rec.reason) ||
        typeof rec.decision_source !== "string" ||
        !["model", "local_reflection", "OPERATOR_PLAN", ""].includes(rec.decision_source)) {
      issues.push("$.experiences: 历史记录字段不合法或携带非公开字段");
      return null;
    }
    records.push(rec as unknown as SkillExperience);
  }
  return records;
}

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
  const persona = "persona" in rec
    ? decodeField(rec.persona, "$.persona", issues, (value) => parseSavedPersona(value, issues))
    : gapField<SavedPersona>("not_wired", "旧身份接口未携带已保存人格，不能据此判断人格是否存在。");
  const experiences = "experiences" in rec
    ? decodeField(rec.experiences, "$.experiences", issues, (value) => parseExperiences(value, issues))
    : gapField<readonly SkillExperience[]>("not_wired", "旧身份接口未携带行为经历，不能据此判断历史是否存在。");
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
  if (issues.length > 0 || persona === null || experiences === null) return { ok: false, issues };
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
      persona,
      experiences,
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

/**
 * A populated-fields map on the wire: keys are field names, each value is a string setting or a
 * finite number. A boolean, null, or nested object is rejected — the closed field set never holds
 * one, so a response that does is a contract mismatch rather than something to coerce.
 */
function parseConfigFields(raw: unknown, path: string, issues: string[]): Record<string, ConfigValue> | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 {字段: 字符串|整数} 对象`);
    return null;
  }
  const out: Record<string, ConfigValue> = {};
  for (const [key, value] of Object.entries(rec)) {
    if (typeof value === "string") {
      out[key] = value;
      continue;
    }
    const n = asNumber(value);
    if (n === null) {
      issues.push(`${path}.${key}: 取值必须是字符串或有限数值`);
      return null;
    }
    out[key] = n;
  }
  return out;
}

function asStringArray(raw: unknown, path: string, issues: string[]): string[] | null {
  if (!Array.isArray(raw)) {
    issues.push(`${path}: 期望字符串数组`);
    return null;
  }
  const out: string[] = [];
  for (const [index, item] of raw.entries()) {
    const s = asString(item);
    if (s === null) {
      issues.push(`${path}[${index}]: 数组成员非字符串`);
      return null;
    }
    out.push(s);
  }
  return out;
}

export type ConfigDecode =
  | { readonly ok: true; readonly config: ConfigInfo; readonly csrfToken: string }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * The config read `gateway/config_write.py::config_read` answers: a flat document, so any missing
 * field or wrong shape is a whole-read mismatch rather than a partial fill — the same rule the
 * identity read follows. `csrfToken` is returned beside the model but deliberately kept OUT of
 * `ConfigInfo`, so a panel cannot render it, and the adapter echoes it back on the save.
 *
 * `loadError` is the one field allowed to be null (an unreadable hand-edited document is reported
 * that way, not raised); every other field is required.
 */
export function decodeConfigPayload(raw: unknown): ConfigDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 配置响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== CONFIG_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${CONFIG_SCHEMA_VERSION}`);
  }
  const fields = parseConfigFields(rec.fields, "$.fields", issues);
  const knownFields = asStringArray(rec.knownFields, "$.knownFields", issues);
  const intFields = asStringArray(rec.intFields, "$.intFields", issues);
  const providers = asStringArray(rec.providers, "$.providers", issues);
  const maxBodyBytes = asInteger(rec.maxBodyBytes);
  const loadError = asNullableString(rec.loadError);
  const csrfToken = asString(rec.csrfToken);
  const observedAt = asString(rec.observedAt);
  const staleAfterMs = asNumber(rec.staleAfterMs);
  if (fields === null) issues.push("$.fields: 缺失或形状不符");
  if (knownFields === null) issues.push("$.knownFields: 缺失或非数组");
  if (intFields === null) issues.push("$.intFields: 缺失或非数组");
  if (providers === null) issues.push("$.providers: 缺失或非数组");
  if (maxBodyBytes === null) issues.push("$.maxBodyBytes: 缺失或非整数");
  if (loadError === undefined) issues.push("$.loadError: 缺失或既非字符串也非 null");
  if (csrfToken === null) issues.push("$.csrfToken: 缺失（无法保存）");
  if (observedAt === null) issues.push("$.observedAt: 缺失或非字符串");
  if (staleAfterMs === null) issues.push("$.staleAfterMs: 缺失或非数值");
  if (issues.length > 0) return { ok: false, issues };
  return {
    ok: true,
    csrfToken: csrfToken as string,
    config: {
      fields: fields as Record<string, ConfigValue>,
      knownFields: knownFields as string[],
      intFields: intFields as string[],
      providers: providers as string[],
      maxBodyBytes: maxBodyBytes as number,
      loadError: (loadError as string | null) ?? null,
      observedAt: observedAt as string,
      staleAfterMs: staleAfterMs as number,
    },
  };
}

export type ConfigSaveDecode =
  | { readonly ok: true; readonly result: ConfigSaveResult }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * A save the server accepted (HTTP 2xx): the document as it now lives, in the same populated-only
 * shape as the read. A refusal never reaches this decoder — the transport routes a non-2xx answer
 * through `decodeRefusalPayload` instead, so the named field/reason survives.
 */
export function decodeConfigSavePayload(raw: unknown): ConfigSaveDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 保存响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== CONFIG_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${CONFIG_SCHEMA_VERSION}`);
  }
  const status = oneOf(rec.status, ["saved"] as const);
  if (status === null) issues.push("$.status: 未知保存结果");
  const fields = parseConfigFields(rec.fields, "$.fields", issues);
  if (fields === null) issues.push("$.fields: 缺失或形状不符");
  if (status === null || fields === null || issues.length > 0) return { ok: false, issues };
  return { ok: true, result: { status, fields: fields as Record<string, ConfigValue> } };
}

const STOP_STATUSES: readonly StopStatus[] = ["stopped", "blocked"];

/**
 * A pid bucket on the wire: a JSON array of integers. A non-integer member (a string, a float, a
 * nested object) is rejected outright — Core only ever lists proven pids, so a response that holds
 * anything else is a contract mismatch, not something to coerce to a number. The three release
 * buckets and the three outcome buckets all decode through this so an empty list and a missing key
 * stay distinguishable at the field level.
 */
function asIntArray(raw: unknown, path: string, issues: string[]): number[] | null {
  if (!Array.isArray(raw)) {
    issues.push(`${path}: 期望整数数组`);
    return null;
  }
  const out: number[] = [];
  for (const [index, item] of raw.entries()) {
    const n = asInteger(item);
    if (n === null) {
      issues.push(`${path}[${index}]: 数组成员非整数`);
      return null;
    }
    out.push(n);
  }
  return out;
}

function parseStopRelease(raw: unknown, path: string, issues: string[]): StopReleaseReport | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 {asked, released, nothing_held, unconfirmed} 对象`);
    return null;
  }
  const asked = asIntArray(rec.asked, `${path}.asked`, issues);
  const released = asIntArray(rec.released, `${path}.released`, issues);
  const nothingHeld = asIntArray(rec.nothing_held, `${path}.nothing_held`, issues);
  const unconfirmed = asIntArray(rec.unconfirmed, `${path}.unconfirmed`, issues);
  if (asked === null || released === null || nothingHeld === null || unconfirmed === null) return null;
  return { asked, released, nothingHeld, unconfirmed };
}

/**
 * Core's `StopReport.as_dict` spreads the outcome buckets flat (`terminated`, `left_alone`,
 * `unresolved`) beside the nested `release`, so this reads them from the report root and re-groups
 * them into the model's `outcome`. `schema_version`/`command` are Core's own envelope and are
 * deliberately not carried into the panel model. A `blocked` status with a non-empty `unresolved`
 * or `unconfirmed` stays exactly that — the panel names what was not released rather than collapsing
 * an uncertain stop into a green one.
 */
function parseStopReport(raw: unknown, issues: string[]): StopReport | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("$.report: 期望 stop report 对象");
    return null;
  }
  const status = oneOf(rec.status, STOP_STATUSES);
  if (status === null) issues.push("$.report.status: 未知停止结果");
  const kinId = asString(rec.kin_id);
  if (kinId === null) issues.push("$.report.kin_id: 缺失或非字符串");
  const release = parseStopRelease(rec.release, "$.report.release", issues);
  const terminated = asIntArray(rec.terminated, "$.report.terminated", issues);
  const leftAlone = asIntArray(rec.left_alone, "$.report.left_alone", issues);
  const unresolved = asIntArray(rec.unresolved, "$.report.unresolved", issues);
  if (status === null || kinId === null || release === null || terminated === null || leftAlone === null || unresolved === null) {
    return null;
  }
  return { status, kinId, release, outcome: { terminated, leftAlone, unresolved } };
}

export type SessionDecode =
  | { readonly ok: true; readonly session: SessionControlInfo; readonly csrfToken: string }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * The session read `gateway/session_control.py::session_read` answers: a flat document, so a missing
 * field or out-of-enum value is a whole-read mismatch rather than a partial fill — the same rule the
 * identity/config reads follow. `csrfToken` is returned beside the model but kept OUT of
 * `SessionControlInfo`, so a panel cannot render it, and the adapter echoes it back on the stop.
 *
 * `unavailableControls` arrives as a `{verb: reason}` object on the wire; it becomes an ordered array
 * of `{verb, reason}` so the panel renders the recorded reasons rather than faking buttons. An empty
 * object is valid — it would mean nothing is withheld — but the server pins start/pause/resume as
 * the reasons today, so a well-formed read always carries all three.
 */
export function decodeSessionPayload(raw: unknown): SessionDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 会话响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== SESSION_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${SESSION_SCHEMA_VERSION}`);
  }
  const state = oneOf(rec.state, KIN_STATES);
  if (state === null) issues.push("$.state: 未知会话状态");
  const stopAllowed = asBoolean(rec.stopAllowed);
  if (stopAllowed === null) issues.push("$.stopAllowed: 缺失或非布尔");
  const availableControls = asStringArray(rec.availableControls, "$.availableControls", issues);
  if (availableControls === null) issues.push("$.availableControls: 缺失或非数组");
  const unavailable = asRecord(rec.unavailableControls);
  let unavailableControls: UnavailableControl[] | null = [];
  if (unavailable === null) {
    issues.push("$.unavailableControls: 期望 {动词: 原因} 对象");
    unavailableControls = null;
  } else {
    const collected: UnavailableControl[] = [];
    for (const [verb, reason] of Object.entries(unavailable)) {
      const r = asString(reason);
      if (r === null) {
        issues.push(`$.unavailableControls.${verb}: 原因缺失或非字符串`);
        unavailableControls = null;
        break;
      }
      collected.push({ verb, reason: r });
    }
    if (unavailableControls !== null) unavailableControls = collected;
  }
  const observedAt = asString(rec.observedAt);
  if (observedAt === null) issues.push("$.observedAt: 缺失或非字符串");
  const staleAfterMs = asNumber(rec.staleAfterMs);
  if (staleAfterMs === null) issues.push("$.staleAfterMs: 缺失或非数值");
  const csrfToken = asString(rec.csrfToken);
  if (csrfToken === null) issues.push("$.csrfToken: 缺失（无法停止）");
  if (issues.length > 0) return { ok: false, issues };
  return {
    ok: true,
    csrfToken: csrfToken as string,
    session: {
      state: state as KinRuntimeState,
      stopAllowed: stopAllowed as boolean,
      availableControls: availableControls as string[],
      unavailableControls: unavailableControls as UnavailableControl[],
      observedAt: observedAt as string,
      staleAfterMs: staleAfterMs as number,
    },
  };
}

export type StopDecode =
  | { readonly ok: true; readonly result: StopResult }
  | { readonly ok: false; readonly issues: readonly string[] };

/**
 * A stop the server accepted (HTTP 200): the state it observed before acting plus Core's report. A
 * refusal never reaches this decoder — the transport routes a non-2xx answer through
 * `decodeRefusalPayload`, so `session_not_running` and an invalid confirmation keep their named code.
 */
export function decodeStopPayload(raw: unknown): StopDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 停止响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== SESSION_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${SESSION_SCHEMA_VERSION}`);
  }
  const state = oneOf(rec.state, KIN_STATES);
  if (state === null) issues.push("$.state: 未知会话状态");
  const report = parseStopReport(rec.report, issues);
  if (state === null || report === null || issues.length > 0) return { ok: false, issues };
  return { ok: true, result: { state: state as KinRuntimeState, report, jobCancelRequested: rec.jobCancelRequested === true } };
}

export type GoalDecode =
  | { readonly ok: true; readonly goal: GoalInfo }
  | { readonly ok: false; readonly issues: readonly string[] };

/** The milestone envelope `Milestone.as_document` writes in snake_case, mapped onto the model. */
function parseGoalMilestone(raw: unknown, issues: string[]): GoalMilestone | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push("$.milestone: 期望 milestone 对象");
    return null;
  }
  const productId = asString(rec.product_id);
  if (productId === null) issues.push("$.milestone.product_id: 缺失或非字符串");
  const quantity = asInteger(rec.quantity);
  if (quantity === null) issues.push("$.milestone.quantity: 缺失或非整数");
  const sourceItemId = asString(rec.source_item_id);
  if (sourceItemId === null) issues.push("$.milestone.source_item_id: 缺失或非字符串");
  const direction = asString(rec.direction);
  if (direction === null) issues.push("$.milestone.direction: 缺失或非字符串");
  if (productId === null || quantity === null || sourceItemId === null || direction === null) return null;
  return { productId, quantity, sourceItemId, direction };
}

function parseGoalMaterials(raw: unknown, path: string, issues: string[]): GoalPlanMaterial[] | null {
  if (!Array.isArray(raw)) {
    issues.push(`${path}: 期望材料数组`);
    return null;
  }
  const out: GoalPlanMaterial[] = [];
  for (const [index, item] of raw.entries()) {
    const rec = asRecord(item);
    if (rec === null) {
      issues.push(`${path}[${index}]: 期望 {item_id, count} 对象`);
      return null;
    }
    const itemId = asString(rec.item_id);
    if (itemId === null) issues.push(`${path}[${index}].item_id: 缺失或非字符串`);
    const count = asInteger(rec.count);
    if (count === null) issues.push(`${path}[${index}].count: 缺失或非整数`);
    if (itemId === null || count === null) return null;
    out.push({ itemId, count });
  }
  return out;
}

/** The gross build plan `gateway/goal_read.py::_step` writes, one craft per row, snake_case → camel. */
function parseGoalPlan(raw: unknown, issues: string[]): GoalPlanStep[] | null {
  if (!Array.isArray(raw)) {
    issues.push("$.plan: 期望步骤数组");
    return null;
  }
  const out: GoalPlanStep[] = [];
  for (const [index, item] of raw.entries()) {
    const rec = asRecord(item);
    if (rec === null) {
      issues.push(`$.plan[${index}]: 期望 build step 对象`);
      return null;
    }
    const productId = asString(rec.product_id);
    if (productId === null) issues.push(`$.plan[${index}].product_id: 缺失或非字符串`);
    const requiredTotal = asInteger(rec.required_total);
    if (requiredTotal === null) issues.push(`$.plan[${index}].required_total: 缺失或非整数`);
    const materials = parseGoalMaterials(rec.materials, `$.plan[${index}].materials`, issues);
    if (productId === null || requiredTotal === null || materials === null) return null;
    out.push({ productId, requiredTotal, materials });
  }
  return out;
}

/**
 * The goal read `gateway/goal_read.py::goal_read` answers: a flat document decoded whole or not at
 * all, so a missing field is a `contract_mismatch` rather than a partial fill. `csrfToken` is present
 * on the wire but deliberately NOT returned — this is a pure GET with no write to guard, and keeping
 * the token out of the seam is what stops a panel from ever rendering it.
 *
 * The document's own invariant is enforced here rather than trusted: `configured: false` answers with
 * a null milestone/plan/precondition, while `configured: true` carries a milestone AND exactly one of
 * (plan array) or (precondition string). A byte that violates that split is a mismatch, not a state
 * to render — the panel must never see a goal that is simultaneously planned and blocked.
 */
export function decodeGoalPayload(raw: unknown): GoalDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 目标响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== GOAL_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${GOAL_SCHEMA_VERSION}`);
  }
  const configured = asBoolean(rec.configured);
  if (configured === null) issues.push("$.configured: 缺失或非布尔");
  const loadError = asNullableString(rec.loadError);
  if (loadError === undefined) issues.push("$.loadError: 缺失或既非字符串也非 null");
  const observedAt = asString(rec.observedAt);
  if (observedAt === null) issues.push("$.observedAt: 缺失或非字符串");
  const staleAfterMs = asNumber(rec.staleAfterMs);
  if (staleAfterMs === null) issues.push("$.staleAfterMs: 缺失或非数值");

  const milestoneRaw = rec.milestone;
  const planRaw = rec.plan;
  const preconditionRaw = rec.precondition;
  let milestone: GoalMilestone | null = null;
  let plan: GoalPlanStep[] | null = null;
  let precondition: string | null = null;

  if (configured === false) {
    if (milestoneRaw !== null || planRaw !== null || preconditionRaw !== null) {
      issues.push("$: 未配置目标时 milestone/plan/precondition 必须全为 null");
    }
  } else if (configured === true) {
    if (milestoneRaw === null) {
      issues.push("$.milestone: 已配置目标却缺失");
    } else {
      milestone = parseGoalMilestone(milestoneRaw, issues);
    }
    const hasPlan = Array.isArray(planRaw);
    const pre = asNullableString(preconditionRaw);
    const hasPrecondition = typeof pre === "string" && pre !== "";
    if (hasPlan === hasPrecondition) {
      issues.push("$: 已配置目标必须恰有 plan 或 precondition 之一");
    } else if (hasPlan) {
      plan = parseGoalPlan(planRaw, issues);
    } else {
      precondition = pre as string;
    }
  }

  if (issues.length > 0) return { ok: false, issues };
  return {
    ok: true,
    goal: {
      configured: configured as boolean,
      milestone,
      plan,
      precondition,
      loadError: (loadError as string | null) ?? null,
      observedAt: observedAt as string,
      staleAfterMs: staleAfterMs as number,
    },
  };
}

export type RecipeDecode =
  | { readonly ok: true; readonly coverage: RecipeCoverageInfo }
  | { readonly ok: false; readonly issues: readonly string[] };

/** One batch's cost, the same `{item_id, count}` shape the goal plan materials decode. */
function parseRecipeIngredients(
  raw: unknown,
  path: string,
  issues: string[],
): RecipeIngredient[] | null {
  if (!Array.isArray(raw)) {
    issues.push(`${path}: 期望材料数组`);
    return null;
  }
  const out: RecipeIngredient[] = [];
  for (const [index, item] of raw.entries()) {
    const rec = asRecord(item);
    if (rec === null) {
      issues.push(`${path}[${index}]: 期望 {item_id, count} 对象`);
      return null;
    }
    const itemId = asString(rec.item_id);
    if (itemId === null) issues.push(`${path}[${index}].item_id: 缺失或非字符串`);
    const count = asInteger(rec.count);
    if (count === null) issues.push(`${path}[${index}].count: 缺失或非整数`);
    if (itemId === null || count === null) return null;
    out.push({ itemId, count });
  }
  return out;
}

/** One catalog row `gateway/recipe_read.py::_row` writes, snake_case → camel, with the provenance
 *  restricted to the two words the catalog actually uses and the grid fit read as a boolean. */
function parseRecipeRow(raw: unknown, path: string, issues: string[]): RecipeRow | null {
  const rec = asRecord(raw);
  if (rec === null) {
    issues.push(`${path}: 期望 recipe 行对象`);
    return null;
  }
  const productId = asString(rec.product_id);
  if (productId === null) issues.push(`${path}.product_id: 缺失或非字符串`);
  const recipeId = asString(rec.recipe_id);
  if (recipeId === null) issues.push(`${path}.recipe_id: 缺失或非字符串`);
  const gridWidth = asInteger(rec.grid_width);
  if (gridWidth === null) issues.push(`${path}.grid_width: 缺失或非整数`);
  const gridHeight = asInteger(rec.grid_height);
  if (gridHeight === null) issues.push(`${path}.grid_height: 缺失或非整数`);
  const yields = asInteger(rec.yields);
  if (yields === null) issues.push(`${path}.yields: 缺失或非整数`);
  const fitsPlayerGrid = asBoolean(rec.fits_player_grid);
  if (fitsPlayerGrid === null) issues.push(`${path}.fits_player_grid: 缺失或非布尔`);
  const provenance = oneOf(rec.provenance, ["live_confirmed", "curated_unwatched"] as const);
  if (provenance === null) {
    issues.push(`${path}.provenance: 期望 live_confirmed 或 curated_unwatched`);
  }
  const ingredients = parseRecipeIngredients(rec.ingredients, `${path}.ingredients`, issues);
  if (
    productId === null ||
    recipeId === null ||
    gridWidth === null ||
    gridHeight === null ||
    yields === null ||
    fitsPlayerGrid === null ||
    provenance === null ||
    ingredients === null
  ) {
    return null;
  }
  return { productId, recipeId, gridWidth, gridHeight, yields, fitsPlayerGrid, provenance, ingredients };
}

/**
 * The recipe-coverage read `gateway/recipe_read.py::recipe_read` answers: a flat document decoded
 * whole or not at all, so a missing field is a `contract_mismatch` rather than a partial fill. There
 * is NO `csrfToken` on this wire — the read has no write partner — so none is dropped or kept.
 *
 * The document's own honesty invariant is enforced here rather than trusted: `universal` must be the
 * catalog's hard-wired `false`. A byte that is not a boolean OR is `true` is a mismatch, because a
 * finite curated fallback reading itself as a universal crafting source is exactly the criterion-6
 * lie this surface exists to prevent — the panel must never be handed a `universal: true` to render.
 */
export function decodeRecipeCoveragePayload(raw: unknown): RecipeDecode {
  const rec = asRecord(raw);
  if (rec === null) return { ok: false, issues: ["$: 配方覆盖响应不是 object"] };
  const issues: string[] = [];
  if (asString(rec.schemaVersion) !== RECIPE_SCHEMA_VERSION) {
    issues.push(`$.schemaVersion: 期望 ${RECIPE_SCHEMA_VERSION}`);
  }
  const observedAt = asString(rec.observedAt);
  if (observedAt === null) issues.push("$.observedAt: 缺失或非字符串");
  const staleAfterMs = asNumber(rec.staleAfterMs);
  if (staleAfterMs === null) issues.push("$.staleAfterMs: 缺失或非数值");
  const gameVersion = asString(rec.game_version);
  if (gameVersion === null) issues.push("$.game_version: 缺失或非字符串");
  const universal = asBoolean(rec.universal);
  if (universal !== false) issues.push("$.universal: 必须为 false（有限回退不得自称通用合成源）");
  const playerGridSide = asInteger(rec.player_grid_side);
  if (playerGridSide === null) issues.push("$.player_grid_side: 缺失或非整数");

  const covered = asStringArray(rec.covered, "$.covered", issues);
  const liveConfirmed = asStringArray(rec.live_confirmed, "$.live_confirmed", issues);
  const curatedUnwatched = asStringArray(rec.curated_unwatched, "$.curated_unwatched", issues);

  const recipesRaw = rec.recipes;
  let recipes: RecipeRow[] | null = null;
  if (!Array.isArray(recipesRaw)) {
    issues.push("$.recipes: 期望行数组");
  } else {
    recipes = [];
    for (const [index, item] of recipesRaw.entries()) {
      const row = parseRecipeRow(item, `$.recipes[${index}]`, issues);
      if (row === null) return { ok: false, issues };
      recipes.push(row);
    }
  }

  if (
    issues.length > 0 ||
    observedAt === null ||
    staleAfterMs === null ||
    gameVersion === null ||
    playerGridSide === null ||
    covered === null ||
    liveConfirmed === null ||
    curatedUnwatched === null ||
    recipes === null
  ) {
    return { ok: false, issues };
  }
  return {
    ok: true,
    coverage: {
      gameVersion,
      universal: false,
      playerGridSide,
      covered,
      liveConfirmed,
      curatedUnwatched,
      recipes,
      observedAt,
      staleAfterMs,
    },
  };
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
 * The one shape both authorized writes share: a same-origin POST that echoes the per-process CSRF
 * token in `CSRF_HEADER` and `content-type: application/json` — the two headers that together make
 * a cross-site request impossible to forge (a cross-site form cannot set either without a
 * preflight, and this browser→same-origin call is not cross-site). A server refusal comes back as a
 * `refusal` with its named reason; a transport break comes back as a `failure`. `cancelledMessage`
 * lets each write name its own取消 so a UI reads the honest reason for the surface it used.
 */
async function postWrite(
  baseUrl: string,
  path: string,
  timeoutMs: number,
  body: unknown,
  csrfToken: string,
  cancelledMessage: string,
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
      return { kind: "failure", failure: { kind: "cancelled", message: cancelledMessage } };
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
 * The rename POST the identity card authorizes. It carries the CSRF token through the shared write
 * transport; only its取消 message is rename-specific.
 */
async function postRename(
  baseUrl: string,
  path: string,
  timeoutMs: number,
  body: RenameRequest,
  csrfToken: string,
  outerSignal?: AbortSignal,
): Promise<PostResult> {
  return postWrite(baseUrl, path, timeoutMs, body, csrfToken, "改名请求已取消。", outerSignal);
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
    label: options === null ? "本地 Gateway · 未配置" : `本地 Gateway · ${options.baseUrl}`,
    mock: false,
    note:
      options === null
        ? "请设置本地 Gateway 地址以读取角色状态。"
        : "读取本地角色的状态、动作与日志。配置、身份修改、模型连接测试及停止会话均在对应页面显式提交。",
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
      async config(): Promise<ReadResult<ConfigInfo>> {
        return unconfigured();
      },
      async saveConfig(): Promise<ReadResult<ConfigSaveResult>> {
        return unconfigured();
      },
      async testModel(): Promise<ReadResult<ModelTestResult>> {
        return unconfigured();
      },
      async serverConfig(): Promise<ReadResult<ServerConfigInfo>> { return unconfigured(); },
      async sessionJob(): Promise<ReadResult<SessionJobInfo>> { return unconfigured(); },
      async startSession(): Promise<ReadResult<SessionStartResult>> { return unconfigured(); },
      async saveServer(): Promise<ReadResult<ServerSaveResult>> { return unconfigured(); },
      async probeServer(): Promise<ReadResult<ServerProbeResult>> { return unconfigured(); },
      async session(): Promise<ReadResult<SessionControlInfo>> {
        return unconfigured();
      },
      async stopSession(): Promise<ReadResult<StopResult>> {
        return unconfigured();
      },
      async goal(): Promise<ReadResult<GoalInfo>> {
        return unconfigured();
      },
      async recipe(): Promise<ReadResult<RecipeCoverageInfo>> {
        return unconfigured();
      },
    };
  }

  const { baseUrl: rawBaseUrl, timeoutMs } = options;
  const baseUrl = rawBaseUrl.replace(/\/+$/, "");
  // Captured from the identity GET and echoed on the rename POST; the config and session GETs hand
  // out the SAME per-process token, so it is refreshed on every identity, config OR session poll too.
  // A write before the first successful read has nothing to echo and the server refuses it — which is
  // correct, honest.
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
    async config(signal?: AbortSignal): Promise<ReadResult<ConfigInfo>> {
      const response = await fetchJson(baseUrl, CONFIG_ENDPOINTS.config, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeConfigPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `配置契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      csrfToken = decoded.csrfToken;
      return ok(decoded.config, "gateway", `gateway://${CONFIG_ENDPOINTS.config}`);
    },
    async serverConfig(signal?: AbortSignal): Promise<ReadResult<ServerConfigInfo>> {
      const response = await fetchJson(baseUrl, "/api/v1/dashboard/server", timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const rec = asRecord(response.data);
      if (!validServerRecord(rec) || typeof rec.csrfToken !== "string" || typeof rec.observedAt !== "string" ||
          !(rec.loadError === null || typeof rec.loadError === "string")) return fail("contract_mismatch", "服务器配置结果契约不匹配。");
      csrfToken = rec.csrfToken;
      return ok({ revision: rec.revision as number, fields: rec.fields as ServerConfigInfo["fields"],
        authMode: "offline", loadError: rec.loadError, observedAt: rec.observedAt }, "gateway", "gateway://server");
    },
    async sessionJob(signal?: AbortSignal): Promise<ReadResult<SessionJobInfo>> {
      const response = await fetchJson(baseUrl, "/api/v1/dashboard/session/job", timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const rec = asRecord(response.data);
      if (rec === null || rec.schemaVersion !== "kin-dashboard-session-job/1.0.0" || rec.error !== undefined)
        return fail("contract_mismatch", "会话启动记录不可读。");
      if (rec.job === null) return ok({ job: null }, "gateway", "gateway://session/job");
      const job = asRecord(rec.job);
      if (job === null || typeof job.jobId !== "string" || !/^[a-f0-9]{32}$/.test(job.jobId) ||
          !["preparing", "supervising", "stopping", "ended", "failed", "interrupted"].includes(String(job.phase)) ||
          typeof job.reason !== "string" || !validServerFields(job.fields) ||
          ![job.serverRevision, job.installed, job.total].every((n) => typeof n === "number" && Number.isSafeInteger(n) && n >= 0) ||
          !(job.outcome === null || typeof job.outcome === "string") ||
          !(job.clientExitCode === undefined || job.clientExitCode === null || Number.isSafeInteger(job.clientExitCode)) ||
          !(job.inputReleaseFailed === null || typeof job.inputReleaseFailed === "boolean"))
        return fail("contract_mismatch", "会话启动记录契约不匹配。");
      const value: SessionJob = { jobId: job.jobId, phase: String(job.phase), reason: job.reason,
        clientExitCode: typeof job.clientExitCode === "number" && Number.isSafeInteger(job.clientExitCode) ? job.clientExitCode : null,
        fields: job.fields as SessionJob["fields"], serverRevision: job.serverRevision as number,
        installed: job.installed as number, total: job.total as number, outcome: job.outcome as string | null,
        inputReleaseFailed: job.inputReleaseFailed as boolean | null };
      return ok({ job: value }, "gateway", "gateway://session/job");
    },
    async startSession(request: SessionStartRequest, signal?: AbortSignal): Promise<ReadResult<SessionStartResult>> {
      const response = await postWrite(baseUrl, "/api/v1/dashboard/session/start", Math.max(timeoutMs, 10_000), request, csrfToken, "启动请求已取消。", signal);
      if (response.kind === "failure") return { ok: false, failure: response.failure };
      if (response.kind === "refusal") return fail("write_refused", `${response.code}：${response.message}`);
      const rec = asRecord(response.data);
      if (rec === null || rec.schemaVersion !== "kin-dashboard-session-job/1.0.0" ||
          typeof rec.jobId !== "string" || !/^[a-f0-9]{32}$/.test(rec.jobId) || rec.phase !== "preparing")
        return fail("contract_mismatch", "会话启动响应契约不匹配。");
      return ok({ jobId: rec.jobId, phase: "preparing" }, "gateway", "gateway://session/start");
    },
    async saveServer(request: ServerSaveRequest, signal?: AbortSignal): Promise<ReadResult<ServerSaveResult>> {
      const response = await postWrite(baseUrl, "/api/v1/dashboard/server/save", timeoutMs, request, csrfToken, "保存已取消。", signal);
      if (response.kind === "failure") return { ok: false, failure: response.failure };
      if (response.kind === "refusal") return fail("write_refused", `${response.code}：${response.message}`);
      const rec = asRecord(response.data);
      if (!validServerRecord(rec) || rec.fields === null) return fail("contract_mismatch", "服务器保存结果契约不匹配。");
      return ok({ revision: rec.revision as number, fields: rec.fields as ServerSaveResult["fields"] }, "gateway", "gateway://server/save");
    },
    async probeServer(revision: number, allowRemote: boolean, signal?: AbortSignal): Promise<ReadResult<ServerProbeResult>> {
      const response = await postWrite(baseUrl, "/api/v1/dashboard/server/probe", Math.max(timeoutMs, 10_000), { revision, confirm: true, allowRemote }, csrfToken, "探测已取消。", signal);
      if (response.kind === "failure") return { ok: false, failure: response.failure };
      if (response.kind === "refusal") return fail("write_refused", `${response.code}：${response.message}`);
      const rec = asRecord(response.data);
      const textOrNull = (v: unknown) => v === null || typeof v === "string";
      if (rec === null || rec.schemaVersion !== "kin-dashboard-server/1.0.0" || !validServerFields(rec.fields) ||
          !Number.isSafeInteger(rec.revision) || typeof rec.outcome !== "string" || typeof rec.supportStatus !== "string" ||
          typeof rec.osArch !== "string" || !textOrNull(rec.serverVersion) || !textOrNull(rec.bundleId) || !textOrNull(rec.minecraftVersion) ||
          !(rec.protocol === null || Number.isSafeInteger(rec.protocol)) || !Array.isArray(rec.supportReasons) || !rec.supportReasons.every((r) => typeof r === "string"))
        return fail("contract_mismatch", "服务器探测结果契约不匹配。");
      return ok({ revision: rec.revision as number, fields: rec.fields as ServerProbeResult["fields"],
        outcome: rec.outcome, protocol: rec.protocol as number | null, serverVersion: rec.serverVersion as string | null,
        supportStatus: rec.supportStatus, supportReasons: rec.supportReasons as string[], bundleId: rec.bundleId as string | null,
        minecraftVersion: rec.minecraftVersion as string | null, osArch: rec.osArch }, "gateway", "gateway://server/probe");
    },
    async testModel(signal?: AbortSignal): Promise<ReadResult<ModelTestResult>> {
      const path = "/api/v1/dashboard/model/test";
      const result = await postWrite(baseUrl, path, Math.max(timeoutMs, 25_000), { confirm: true }, csrfToken, "模型测试请求已取消。", signal);
      if (result.kind === "failure") return { ok: false, failure: result.failure };
      if (result.kind === "refusal") return fail("write_refused", `${result.code}：${result.message}`);
      const rec = asRecord(result.data);
      if (rec === null || rec.schemaVersion !== "kin-dashboard-model-test/1.0.0" ||
          (rec.status !== "connected" && rec.status !== "unavailable") ||
          typeof rec.reason !== "string" ||
          ![rec.elapsedMs, rec.timeoutMs, rec.modelCalls, rec.estimatedCostMicro].every((n) => typeof n === "number" && Number.isSafeInteger(n) && n >= 0)) {
        return fail("contract_mismatch", "模型测试结果契约不匹配。");
      }
      return ok({ status: rec.status, reason: rec.reason, elapsedMs: rec.elapsedMs as number,
        timeoutMs: rec.timeoutMs as number, modelCalls: rec.modelCalls as number,
        estimatedCostMicro: rec.estimatedCostMicro as number }, "gateway", `gateway://${path}`);
    },
    async saveConfig(request: ConfigSaveRequest, signal?: AbortSignal): Promise<ReadResult<ConfigSaveResult>> {
      const result = await postWrite(baseUrl, CONFIG_ENDPOINTS.save, timeoutMs, request, csrfToken, "保存请求已取消。", signal);
      if (result.kind === "failure") return { ok: false, failure: result.failure };
      if (result.kind === "refusal") {
        return fail("write_refused", `${result.code}：${result.message}`);
      }
      const decoded = decodeConfigSavePayload(result.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `保存结果契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "gateway", `gateway://${CONFIG_ENDPOINTS.save}`);
    },
    async session(signal?: AbortSignal): Promise<ReadResult<SessionControlInfo>> {
      const response = await fetchJson(baseUrl, SESSION_ENDPOINTS.session, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeSessionPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `会话契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      csrfToken = decoded.csrfToken;
      return ok(decoded.session, "gateway", `gateway://${SESSION_ENDPOINTS.session}`);
    },
    async stopSession(request: StopRequest, signal?: AbortSignal): Promise<ReadResult<StopResult>> {
      const result = await postWrite(baseUrl, SESSION_ENDPOINTS.stop, timeoutMs, request, csrfToken, "停止请求已取消。", signal);
      if (result.kind === "failure") return { ok: false, failure: result.failure };
      if (result.kind === "refusal") {
        return fail("write_refused", `${result.code}：${result.message}`);
      }
      const decoded = decodeStopPayload(result.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `停止结果契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.result, "gateway", `gateway://${SESSION_ENDPOINTS.stop}`);
    },
    async goal(signal?: AbortSignal): Promise<ReadResult<GoalInfo>> {
      const response = await fetchJson(baseUrl, GOAL_ENDPOINTS.goal, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeGoalPayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `目标契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.goal, "gateway", `gateway://${GOAL_ENDPOINTS.goal}`);
    },
    async recipe(signal?: AbortSignal): Promise<ReadResult<RecipeCoverageInfo>> {
      const response = await fetchJson(baseUrl, RECIPE_ENDPOINTS.recipe, timeoutMs, signal);
      if (!response.ok) return { ok: false, failure: response.failure };
      const decoded = decodeRecipeCoveragePayload(response.data);
      if (!decoded.ok) {
        return fail("contract_mismatch", `配方覆盖契约不匹配：${decoded.issues.slice(0, 6).join("；")}`);
      }
      return ok(decoded.coverage, "gateway", `gateway://${RECIPE_ENDPOINTS.recipe}`);
    },
  };
}
