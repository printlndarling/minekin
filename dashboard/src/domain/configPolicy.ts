import type { ConfigInfo, ConfigValue } from "./model";

/**
 * The settings form's own view of the closed field set that `gateway/config_write.py` projects
 * and `minekin_core.domain.operator_config` persists. Nothing here decides a value's meaning —
 * that belongs to `model_access`, `goal_spec` and `recipe_catalog` — this file only says how a
 * field is LABELLED and what the panel checks as a COURTESY before submitting. The server is
 * still the authority: a value the panel lets through is one it believes the server accepts, and
 * a refusal the server gives still renders beside the unchanged document.
 *
 * The rules below mirror `_validated_field` in `operator_config.py` on purpose, so the mock
 * adapter can reuse `validateConfigDraft` as its stand-in for `save_operator_config` and the two
 * cannot drift into a panel that promises a save the real Gateway would refuse.
 */

/** The form holds every field as a string; integer fields are parsed only at save time. */
export type ConfigDraft = Record<string, string>;

export type ConfigGroupId = "model" | "goal";

export interface ConfigFieldMeta {
  readonly key: string;
  readonly label: string;
  readonly hint: string;
  readonly placeholder: string;
  /** True for a value that must not be blank in order to count as set (all fields qualify). */
  readonly int: boolean;
  /** Render a provider `<select>` from the read's `providers` vocabulary rather than free text. */
  readonly provider: boolean;
  readonly item: boolean;
  readonly envName: boolean;
}

const field = (
  key: string,
  label: string,
  hint: string,
  placeholder: string,
  flags: { int?: boolean; provider?: boolean; item?: boolean; envName?: boolean } = {},
): ConfigFieldMeta => ({
  key,
  label,
  hint,
  placeholder,
  int: flags.int === true,
  provider: flags.provider === true,
  item: flags.item === true,
  envName: flags.envName === true,
});

export const CONFIG_FIELDS: readonly ConfigFieldMeta[] = [
  field(
    "model_provider",
    "模型后端",
    "决定这一版是否调用真实模型。off 表示不调用模型；openai_compatible 表示走 OpenAI 兼容端点。",
    "off",
    { provider: true },
  ),
  field("model_base_url", "端点地址", "OpenAI 兼容服务的基址，例如 https://…/v1。不含密钥。", "https://…/v1"),
  field("model_name", "模型名称", "端点上的模型 id，例如 deepseek-chat。", "deepseek-chat"),
  field(
    "model_api_key_env",
    "密钥所在的环境变量名",
    "只保存变量名，绝不保存密钥本身。真正的 key 留在进程环境里，不入库、不进响应、不进日志。",
    "MINEKIN_MODEL_API_KEY",
    { envName: true },
  ),
  field("model_timeout_ms", "单次调用超时（毫秒）", "一次模型调用的最长等待，超时即有界失败，不无限重试。", "30000", { int: true }),
  field("model_run_cost_cap", "整轮费用上限（微单位）", "一个 run 的调用花费上限，达到即拒止继续调用。", "5000000", { int: true }),
  field("model_request_rate", "请求费率（微单位 / 百万 token）", "用户提供的估算费率，留空沿用 2500；0 是显式零费率，不证明免费。与预算使用同一单位，不是供应商账单。", "2500", { int: true }),
  field("model_response_rate", "响应费率（微单位 / 百万 token）", "用户提供的估算费率，留空沿用 10000；usage 缺失时估算仍不完整。仅影响后续运行，不修改旧账本。", "10000", { int: true }),
  field("goal_product_id", "目标产物", "玩家可见的游戏物品 id（namespace:path，小写）。", "minecraft:wooden_pickaxe", { item: true }),
  field("goal_quantity", "目标数量", "一次请求的成品数量，受单组上限约束。", "1", { int: true }),
  field("goal_source_item_id", "起点材料", "已知的起始物品 id（namespace:path，小写），可留空。", "minecraft:oak_log", { item: true }),
  field("goal_direction", "目标补充说明", "给模型的一句话目标描述，可留空。", "先挖木头，再合成木镐"),
];

export const CONFIG_GROUPS: readonly { id: ConfigGroupId; label: string; fields: readonly ConfigFieldMeta[] }[] = [
  { id: "model", label: "模型与预算", fields: CONFIG_FIELDS.filter((meta) => meta.key.startsWith("model_")) },
  { id: "goal", label: "目标", fields: CONFIG_FIELDS.filter((meta) => meta.key.startsWith("goal_")) },
];

/**
 * A bare environment-variable name, matching `minekin_core.config.LOCAL_ENV_NAME_PATTERN`. A
 * pasted key carries dashes and dots and fails here, which is the same way the server keeps a
 * credential out of the field that is meant to name a variable.
 */
const ENV_NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** `namespace:path`, both lowercase — mirrors `minekin_core.domain.skill_parameters._ITEM_ID_PATTERN`. */
const ITEM_ID_PATTERN = /^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$/;

/** A long unstructured token: the shape of a pasted credential, never of a name, URL or count. */
const SECRET_SHAPED = /[A-Za-z0-9_-]{32,}/;

const MAX_INT = 1_000_000_000;

/** `MAX_QUANTITY` in Core is one stack; a goal ask above a stack is not a single ask. */
const MAX_GOAL_QUANTITY = 64;

/** The positive-integer ceiling the panel enforces per field, mirroring `_checked_positive_int`. */
function intCeiling(key: string): number {
  return key === "goal_quantity" ? MAX_GOAL_QUANTITY : MAX_INT;
}

/**
 * The populated fields rendered into a form draft: strings for text, decimal strings for ints.
 * An absent field becomes the empty string, which the form treats as "unset" and a save drops.
 */
export function fieldsToDraft(fields: Readonly<Record<string, ConfigValue>>): ConfigDraft {
  const draft: ConfigDraft = {};
  for (const meta of CONFIG_FIELDS) {
    const value = fields[meta.key];
    draft[meta.key] = value === undefined || value === null ? "" : String(value);
  }
  return draft;
}

/**
 * The save body built from a draft: blanks dropped (an omitted field is written as unset),
 * integer fields parsed. Only fields the draft names as known are emitted.
 */
export function buildSaveFields(draft: ConfigDraft): Record<string, ConfigValue> {
  const out: Record<string, ConfigValue> = {};
  for (const meta of CONFIG_FIELDS) {
    const trimmed = (draft[meta.key] ?? "").trim();
    if (trimmed === "") continue;
    if (meta.int) {
      const parsed = Number(trimmed);
      if (Number.isInteger(parsed)) out[meta.key] = parsed;
    } else {
      out[meta.key] = trimmed;
    }
  }
  return out;
}

/**
 * Validate a draft field by field, returning a message per offending field. A blank field is
 * always allowed (it means "unset"); the moment a value is present it must pass the same check
 * the server will run. This is the single source reused by both the panel's submit gate and the
 * mock adapter's refusal, so a name the panel lets through is a name the Gateway also accepts.
 */
export function validateConfigDraft(draft: ConfigDraft, providers: readonly string[]): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const meta of CONFIG_FIELDS) {
    const raw = draft[meta.key];
    if (raw === undefined) continue;
    const value = raw.trim();
    if (value === "") continue;

    if (meta.int) {
      const parsed = Number(value);
      const minimum = meta.key === "model_request_rate" || meta.key === "model_response_rate" ? 0 : 1;
      if (!Number.isInteger(parsed) || parsed < minimum) {
        errors[meta.key] = `必须是 ≥ ${minimum} 的整数。`;
      } else if (parsed > intCeiling(meta.key)) {
        errors[meta.key] = `不能超过 ${intCeiling(meta.key)}。`;
      }
      continue;
    }

    if (value.length > 512) {
      errors[meta.key] = "过长，不像一条设置。";
      continue;
    }
    if (meta.provider) {
      if (!providers.includes(value)) {
        errors[meta.key] = `未知后端，请从 ${providers.join(" / ")} 中选择。`;
      }
      continue;
    }
    if (meta.envName) {
      if (!ENV_NAME_PATTERN.test(value)) {
        errors[meta.key] = "只能填环境变量名（字母、数字或下划线，字母或下划线开头），不是密钥本身。";
      }
      continue;
    }
    if (meta.item) {
      if (!ITEM_ID_PATTERN.test(value)) {
        errors[meta.key] = "必须是游戏里写法的物品 id（namespace:path，小写）。";
      }
      continue;
    }
    if (SECRET_SHAPED.test(value)) {
      errors[meta.key] = "这看起来像一段凭据；密钥请放在环境变量里，不填在这里。";
    }
  }
  return errors;
}

/** Freshness of a config reading against a caller-supplied clock. */
export function configIsStale(config: ConfigInfo, nowMs: number): boolean {
  const at = Date.parse(config.observedAt);
  if (!Number.isFinite(at)) return false;
  return nowMs - at > config.staleAfterMs;
}

/**
 * A stable signature of the saved document, keyed on the field vocabulary order rather than
 * object key order, so the form can tell "the document changed" from "the same document,
 * re-parsed". Used to decide when to re-seed the draft from the read without clobbering edits.
 */
export function configFieldsSignature(config: ConfigInfo): string {
  return CONFIG_FIELDS.map((meta) => `${meta.key}=${config.fields[meta.key] ?? ""}`).join("&");
}
