import type { Signal, SignalStatus } from "./signals";

/**
 * The frozen read model of `docs/gateway-dashboard-readonly-contract-2026-09-28.md`.
 * The Gateway server and this frontend must answer/consume this exact literal;
 * any other version is a `contract_mismatch`, not a fallback (§2.3).
 */
export const SNAPSHOT_SCHEMA_VERSION = "kin-dashboard-readmodel/1.0.0";

/**
 * Only the three values Core's `ObservedState` carries. `paused` and `recovering`
 * were dropped by the contract census (§3): nothing produces them, so the union
 * must not let a UI show them.
 */
export type KinRuntimeState = "idle" | "running" | "unresolved";

export type LinkState = "connected" | "connecting" | "disconnected";

export type SessionMode = "A_companion" | "B_standalone";

/**
 * One member inside a `known` group. The group has a carrier, but each member
 * either carries a value or travels as a named gap (§3: C-tier fields have no
 * producer in Core and must render as such, never as a defaulted value).
 */
export type FieldGapStatus = "unknown" | "unavailable" | "not_wired";

export interface FieldGap {
  readonly status: FieldGapStatus;
  readonly reason: string;
}

export type Field<T> = { readonly value: T } | { readonly gap: FieldGap };

export function filled<T>(value: T): Field<T> {
  return { value };
}

export function gapField<T>(status: FieldGapStatus, reason: string): Field<T> {
  return { gap: { status, reason } };
}

/** The value of a filled member, or null when it is a gap — never a default. */
export function fieldValue<T>(field: Field<T>): T | null {
  return "value" in field ? field.value : null;
}

export function fieldGap<T>(field: Field<T>): FieldGap | null {
  return "value" in field ? null : field.gap;
}

export interface SessionInfo {
  readonly sessionId: Field<string>;
  readonly generation: Field<number>;
  readonly startedAt: Field<string>;
  readonly pid: Field<number>;
  readonly overlay: Field<string>;
  readonly mode: Field<SessionMode>;
}

export interface WorldInfo {
  readonly profileId: Field<string>;
  readonly profileName: Field<string>;
  readonly worldContext: Field<string>;
  readonly epoch: Field<number>;
  readonly joined: Field<boolean>;
  readonly resolvedVersion: Field<string>;
}

export interface VersionSet {
  readonly runtime: Field<string>;
  readonly bridge: Field<string>;
  readonly clientBundle: Field<string>;
  readonly java: Field<string>;
  readonly fabricLoader: Field<string>;
}

export interface Heartbeat {
  readonly lastSequence: Field<number>;
  readonly lastObservedAt: Field<string>;
  readonly intervalMs: Field<number>;
  readonly inputLeaseHeld: Field<boolean>;
}

/**
 * `dimension` and `guiOpen` were removed: the contract census (§3) found no
 * carrier for either, and this group is a whole-group gap in practice.
 * health/food do have a carrier (`SelfStateValue`), so they stay as plain
 * numbers inside the group value.
 */
export interface SelfState {
  readonly health: number;
  readonly food: number;
}

export interface EvidenceRef {
  readonly runId: Field<string>;
  readonly attempt: Field<number>;
  readonly bundleDigest: Field<string>;
  readonly sealedAt: Field<string>;
}

/**
 * The `skillSteps` group: the newest `SkillStepRecorded` ledger row of the newest run,
 * as `gateway/readmodel.py::_skill_steps_group` projects it. Every member is a `Field`
 * because each one is empty *by construction* for some legal run shape — a scripted
 * `--skill-plan` run has no goal, a CONFIRMED step has no failure reason, a local
 * decision never reached a model — and the Gateway renders those as named gaps rather
 * than as `""` or `0`. `result` and `decisionSource` stay plain strings: they are Core's
 * own enum tokens projected verbatim, and a new token from Core must render rather than
 * fail the whole snapshot decode. `modelCost`/`modelConfig` never carry a value: Core
 * records them only in the run document, which this read surface does not parse.
 * `behaviorParameters` is the one run-document field the projection DOES parse: it lands
 * as a value only for a sealed, verified bundle that carries a run document, and stays a
 * named `not_wired` gap otherwise. It is a backward-compatible addition, so the decoder
 * tolerates a snapshot from an older projection byte that omits the member entirely.
 */
export interface SkillStepInfo {
  readonly goal: Field<string>;
  readonly stepIndex: Field<number>;
  readonly skill: Field<string>;
  readonly result: Field<string>;
  readonly reason: Field<string>;
  readonly attribution: Field<string>;
  readonly decisionSource: Field<string>;
  readonly modelRefusal: Field<string>;
  readonly stepCount: Field<number>;
  readonly modelCost: Field<string>;
  readonly modelConfig: Field<string>;
  readonly behaviorParameters: Field<string>;
}

export interface MediaStreamRef {
  readonly available: boolean;
  readonly transport: "webrtc" | "hls" | "mjpeg";
  readonly url: string;
  readonly startedAt: string;
}

export interface KinSnapshot {
  readonly schemaVersion: string;
  readonly kinId: Signal<string>;
  readonly runtimeState: Signal<KinRuntimeState>;
  readonly bridgeLink: Signal<LinkState>;
  readonly serverLink: Signal<LinkState>;
  readonly session: Signal<SessionInfo>;
  readonly world: Signal<WorldInfo>;
  readonly skillSteps: Signal<SkillStepInfo>;
  readonly versions: Signal<VersionSet>;
  readonly bridgeHeartbeat: Signal<Heartbeat>;
  readonly selfState: Signal<SelfState>;
  readonly evidence: Signal<EvidenceRef>;
  readonly liveView: Signal<MediaStreamRef>;
}

export type TimelineKind =
  | "observation"
  | "decision"
  | "intent"
  | "input"
  | "server_feedback"
  | "reflex"
  | "fault"
  | "session";

export type TimelineOutcome = "applied" | "rejected" | "expired" | "released" | "unknown";

export interface TimelineEvent {
  readonly eventId: string;
  readonly kind: TimelineKind;
  readonly at: string;
  readonly monotonicMs: number | null;
  readonly generation: number | null;
  readonly sequence: number | null;
  readonly title: string;
  readonly detail: string | null;
  readonly outcome: TimelineOutcome;
  readonly sourceRef: string;
}

export type AlertSeverity = "info" | "warning" | "critical";

export type AlertState = "active" | "resolved" | "acknowledged";

export type AlertComponent = "runtime" | "bridge" | "launcher" | "gateway" | "media" | "database";

export interface Alert {
  readonly alertId: string;
  readonly severity: AlertSeverity;
  readonly state: AlertState;
  readonly component: AlertComponent;
  readonly title: string;
  readonly detail: string | null;
  readonly firstSeenAt: string;
  readonly lastSeenAt: string | null;
  readonly sourceRef: string;
}

/**
 * The alerts envelope frozen by §5.3 (`ALERT_SOURCE_AMBIGUITY`): a bare empty
 * array would read as "nothing is wrong" when the truth is "nothing decides
 * what wrong would be". `reason` must be non-empty whenever the status is not
 * `known`; `known` with zero alerts means 「没有告警」, any other status with
 * zero alerts means 「无告警源」— two different UI facts.
 */
export interface AlertsEnvelope {
  readonly status: SignalStatus;
  /** "" only when `status === "known"`; every gap carries Core's own reason. */
  readonly reason: string;
  readonly alerts: readonly Alert[];
}

/**
 * The identity read model of `docs/stable-player-name-2026-09-29.md`. Unlike the three
 * frozen snapshot reads, this is a flat document — `gateway/identity.py` answers it whole
 * for one stopped Kin, so there is no per-field Signal to degrade. A decode mismatch is a
 * whole-read `contract_mismatch`, never a partial fill.
 */
export const IDENTITY_SCHEMA_VERSION = "kin-dashboard-identity/1.0.0";

/**
 * Who this Kin currently is, as Core's identity service stores it. `renameAllowed`
 * mirrors the exact predicate the write enforces (a stopped session), so the panel
 * disables the form for the same reason the server would refuse rather than guessing
 * from a poll that raced a launch.
 */
export interface IdentityInfo {
  readonly kinId: string;
  readonly username: string;
  readonly uuidCanonical: string;
  readonly identityRevision: number;
  readonly state: KinRuntimeState;
  readonly renameAllowed: boolean;
  readonly notice: string;
  readonly observedAt: string;
  readonly staleAfterMs: number;
}

/** One identity snapshot as a rename report carries it: the name and its derived UUID. */
export interface IdentityViewSnapshot {
  readonly username: string;
  readonly uuidCanonical: string;
  readonly identityRevision: number;
}

/**
 * A confirmed rename submission. `confirm` is the literal `true` type so no call site can
 * submit without having consciously set the confirmation flag, and `expectedRevision` is
 * the revision the operator reviewed — the compare-and-swap that refuses a stale write.
 */
export interface RenameRequest {
  readonly username: string;
  readonly confirm: true;
  readonly expectedRevision: number;
}

/** Core's two outcomes: it either moved to a new name or the name was already current. */
export type RenameStatus = "renamed" | "unchanged";

export interface RenameResult {
  readonly status: RenameStatus;
  readonly kinId: string;
  readonly before: IdentityViewSnapshot;
  readonly after: IdentityViewSnapshot;
  readonly uuidChanged: boolean;
  readonly notice: string;
}

/**
 * The operator-config read model of `gateway/config_write.py::config_read`. It is the second
 * authorized write surface after the identity rename: the settings form reviews this document
 * and submits it back whole. Like the identity read it is a flat document, so a decode
 * mismatch is a whole-read `contract_mismatch`, never a partial fill.
 *
 * `fields` carries ONLY the populated settings — an unset field is absent, not null — because
 * that is exactly the disk shape `operator_config.as_document` projects, and a save replaces
 * the whole document, so the fields the form sends back must be the fields it wants kept.
 * No field here can hold an API key: the closest is `model_api_key_env`, a variable NAME.
 * `csrfToken` is deliberately NOT part of this model (mirroring how the identity decode keeps
 * the token beside the model) so a panel cannot render it.
 */
export const CONFIG_SCHEMA_VERSION = "kin-dashboard-config/1.0.0";

/** A config value on the wire: a string setting or a positive-integer setting. */
export type ConfigValue = string | number;

export interface ConfigInfo {
  readonly fields: Readonly<Record<string, ConfigValue>>;
  readonly knownFields: readonly string[];
  readonly intFields: readonly string[];
  readonly providers: readonly string[];
  readonly maxBodyBytes: number;
  /** Core's own reason the saved document could not be read; null when it parsed. */
  readonly loadError: string | null;
  readonly observedAt: string;
  readonly staleAfterMs: number;
}

/**
 * The whole document a save submits. A field omitted is written as unset, so the form builds
 * this from its current draft (blanks dropped) rather than sending a patch.
 */
export interface ConfigSaveRequest {
  readonly fields: Record<string, ConfigValue>;
}

/** The document as it now lives after an accepted save — the same populated-only shape as the read. */
export interface ConfigSaveResult {
  readonly status: "saved";
  readonly fields: Record<string, ConfigValue>;
}

export interface ModelTestResult {
  readonly status: "connected" | "unavailable";
  readonly reason: string;
  readonly elapsedMs: number;
  readonly timeoutMs: number;
  readonly modelCalls: number;
  readonly estimatedCostMicro: number;
}

export interface ServerFields { readonly host: string; readonly port: number; }
export interface ServerConfigInfo {
  readonly revision: number;
  readonly fields: ServerFields | null;
  readonly authMode: "offline";
  readonly loadError: string | null;
  readonly observedAt: string;
}
export interface ServerSaveRequest { readonly revision: number; readonly fields: ServerFields; }
export interface ServerSaveResult { readonly revision: number; readonly fields: ServerFields; }
export interface ServerProbeResult {
  readonly revision: number;
  readonly fields: ServerFields;
  readonly outcome: string;
  readonly protocol: number | null;
  readonly serverVersion: string | null;
  readonly supportStatus: string;
  readonly supportReasons: readonly string[];
  readonly bundleId: string | null;
  readonly minecraftVersion: string | null;
  readonly osArch: string;
}

/**
 * The session-control read model of `gateway/session_control.py::session_read`: the observed
 * session state plus exactly what this surface can do about it. Like the identity and config
 * reads it is a flat document decoded whole or not at all — a mismatch is a `contract_mismatch`,
 * never a partial fill — and `csrfToken` stays beside the model rather than inside it.
 *
 * `stopAllowed` mirrors the write's own predicate (a session that is not idle), so the panel
 * enables 停止 for the same reason the server would act, not a poll that raced a launch.
 * `availableControls` is the verbs the composed surface offers today (`stop` plus the managed
 * `start` `gateway/session_jobs.py` supervises); `unavailableControls` carries a name-and-reason
 * pair per verb the state machine cannot yet honor (pause/resume), so the boundary is rendered
 * rather than faked with a button a later POST would refuse.
 */
export const SESSION_SCHEMA_VERSION = "kin-dashboard-session/1.0.0";

export interface UnavailableControl {
  readonly verb: string;
  readonly reason: string;
}

export interface SessionControlInfo {
  readonly state: KinRuntimeState;
  readonly stopAllowed: boolean;
  readonly availableControls: readonly string[];
  readonly unavailableControls: readonly UnavailableControl[];
  readonly observedAt: string;
  readonly staleAfterMs: number;
}

/**
 * A confirmed stop submission. `confirm` is the literal `true` type so no call site can request
 * a stop without having consciously set the flag — the same explicit-confirmation shape the
 * rename uses, because stopping is a control verb, not a side effect of reading.
 */
export interface StopRequest {
  readonly confirm: true;
}

/** Core's two stop outcomes: the session either came to a complete stop or left something unresolved. */
export type StopStatus = "stopped" | "blocked";

/**
 * The input-release ledger inside a stop report (`StopReleaseReport.as_document`): which held
 * leases were asked to release, actually released, were never held, or could not be confirmed.
 * Each list holds the pids in that bucket. `unconfirmed` non-empty is a `UNKNOWN`-style caveat the
 * panel must not read as success.
 */
export interface StopReleaseReport {
  readonly asked: readonly number[];
  readonly released: readonly number[];
  readonly nothingHeld: readonly number[];
  readonly unconfirmed: readonly number[];
}

/**
 * The process-ownership outcome inside a stop report (`StopOutcome.as_document`): which pids were
 * terminated after their identity was proven, left alone on purpose, or could not be proven.
 * `unresolved` non-empty means the stop is `blocked`, not complete.
 */
export interface StopOutcomeReport {
  readonly terminated: readonly number[];
  readonly leftAlone: readonly number[];
  readonly unresolved: readonly number[];
}

/**
 * A stop report the server accepted (HTTP 200), projected from Core's `StopReport.as_dict`. The
 * wire spells its members in snake_case (`kin_id`, `nothing_held`, `left_alone`); the decoder maps
 * them onto this camelCase model, keeping the two `int[]` buckets (release / outcome) intact so
 * the panel can name what was and was not released rather than collapsing a `blocked` stop to a
 * green one.
 */
export interface StopReport {
  readonly status: StopStatus;
  readonly kinId: string;
  readonly release: StopReleaseReport;
  readonly outcome: StopOutcomeReport;
}

export interface StopResult {
  readonly state: KinRuntimeState;
  readonly report: StopReport;
  readonly jobCancelRequested?: boolean;
}

export interface SessionStartRequest {
  readonly confirm: true;
  readonly serverRevision: number;
  readonly allowRemote: boolean;
  readonly maxDownloadBytes: number;
  readonly durationSeconds: number;
  readonly autonomousSteps: number;
}
export interface SessionJob {
  readonly jobId: string;
  readonly phase: string;
  readonly reason: string;
  readonly fields: ServerFields;
  readonly serverRevision: number;
  readonly installed: number;
  readonly total: number;
  readonly outcome: string | null;
  readonly inputReleaseFailed: boolean | null;
}
export interface SessionJobInfo { readonly job: SessionJob | null; }
export interface SessionStartResult { readonly jobId: string; readonly phase: "preparing"; }

/**
 * The goal read model of `gateway/goal_read.py::goal_read`: the standing milestone the operator
 * already saved through the config write, plus the gross build plan the curated recipe catalog
 * implies for it — or the single named precondition (`CRAFT_RECIPE_UNAVAILABLE`) saying the product
 * sits OUTSIDE that catalog's declared cover. Like the config/session reads it is a flat document
 * decoded whole or not at all (a mismatch is a `contract_mismatch`, never a partial fill), and
 * `csrfToken` is dropped at the seam because this read is pure GET — setting a goal stays the
 * config write's job, so there is no fourth write to guard.
 *
 * The projection carries NO live progress: Core's ledger holds per-step `goal` strings, not a live
 * inventory snapshot, so `plan` counts are gross (what the goal implies), never how many the bag
 * already holds. `configured: false` with null milestone/plan/precondition is the honest empty
 * state (no goal saved), not a fault; a hand-edited unreadable document surfaces through `loadError`
 * with the same empty projection, mirroring `config_read`.
 */
export const GOAL_SCHEMA_VERSION = "kin-dashboard-goal/1.0.0";

/** The saved milestone as the read projects it; `direction` carries Core's derived label. */
export interface GoalMilestone {
  readonly productId: string;
  readonly quantity: number;
  readonly sourceItemId: string;
  readonly direction: string;
}

export interface GoalPlanMaterial {
  readonly itemId: string;
  readonly count: number;
}

/** One owed craft in the implied plan: what it makes, how many in total, and what it eats. */
export interface GoalPlanStep {
  readonly productId: string;
  readonly requiredTotal: number;
  readonly materials: readonly GoalPlanMaterial[];
}

export interface GoalInfo {
  readonly configured: boolean;
  readonly milestone: GoalMilestone | null;
  readonly plan: readonly GoalPlanStep[] | null;
  readonly precondition: string | null;
  readonly loadError: string | null;
  readonly observedAt: string;
  readonly staleAfterMs: number;
}

/**
 * The recipe-coverage read model of `gateway/recipe_read.py::recipe_read`: the whole covered region
 * of the curated catalog at once — the game version it claims, the watched/curated split, and one
 * row per known craft — so a panel can show the catalog's support BOUNDARY rather than only the plan
 * one product implies (`GoalInfo`). This is the criterion-6 surface: the small curated set is honest
 * precisely because it says out loud what it stands behind.
 *
 * Two honesty invariants survive the wire and are enforced at the seam, not trusted from the server:
 * `universal` is the catalog's hard-wired `false` (a `true` byte is a contract mismatch — a finite
 * fallback must never read as a general crafting source), and every row's `provenance` distinguishes
 * a craft watched on the controlled server from one only curated from the game's data. Like the goal
 * read this is a pure GET with NO write partner, so the payload carries no `csrfToken` at all — there
 * is nothing here to authorize. A product outside `covered` is simply absent from the rows; the
 * boundary is the empty room the table makes for it, named elsewhere by `CRAFT_RECIPE_UNAVAILABLE`.
 */
export const RECIPE_SCHEMA_VERSION = "kin-dashboard-recipe/1.0.0";

/** How this build came to hold a row — watched crafted, or curated and not yet watched. */
export type RecipeProvenance = "live_confirmed" | "curated_unwatched";

/** One ingredient a batch of the recipe eats. */
export interface RecipeIngredient {
  readonly itemId: string;
  readonly count: number;
}

/** One catalog craft: its name, shape, cost, yield, whether this build's grid can hold it, and
 *  the provenance saying how much the catalog actually stands behind it. */
export interface RecipeRow {
  readonly productId: string;
  readonly recipeId: string;
  readonly gridWidth: number;
  readonly gridHeight: number;
  readonly yields: number;
  readonly fitsPlayerGrid: boolean;
  readonly provenance: RecipeProvenance;
  readonly ingredients: readonly RecipeIngredient[];
}

export interface RecipeCoverageInfo {
  readonly gameVersion: string;
  /** Always `false` — the catalog never claims to know every craft. Enforced at the seam. */
  readonly universal: false;
  readonly playerGridSide: number;
  readonly covered: readonly string[];
  readonly liveConfirmed: readonly string[];
  readonly curatedUnwatched: readonly string[];
  readonly recipes: readonly RecipeRow[];
  readonly observedAt: string;
  readonly staleAfterMs: number;
}
