import { SIGNAL_STATUS_LABELS } from "../domain/labels";
import { fieldGap, type Field, type KinSnapshot } from "../domain/model";
import { isKnown } from "../domain/signals";
import { formatDateTime } from "../lib/format";
import { Panel } from "../components/Panel";
import { Pill } from "../components/Pill";
import styles from "../components/ui.module.css";

/**
 * Core's own verdict tokens, projected verbatim by `gateway/readmodel.py`. The map only
 * adds a Chinese gloss; an unknown token still renders as itself rather than being
 * folded into one of the three — the projection never re-labels Core's words, and
 * neither may this panel.
 */
const RESULT_LABELS: Record<string, string> = {
  CONFIRMED: "已确认",
  FAILED: "失败",
  UNKNOWN: "结果未知",
  INTERRUPTED: "已中断",
};

/**
 * The gloss for the source token, never a re-label. `local_reflection` is local code doing the
 * step -- an imminent-protection step or the rules strategy -- and this ledger row does not say
 * which mode was chosen at the time, so the gloss does not claim either and the panel says so.
 * Both spellings are glossed because the ledger writes Core's lowercase tokens while older
 * fixtures and gap texts use the enum spellings.
 */
const SOURCE_LABELS: Record<string, string> = {
  model: "模型决策",
  DECISION_FROM_MODEL: "模型决策",
  local_reflection: "本地执行（安全保护或规则策略）",
  DECISION_FROM_LOCAL: "本地执行（安全保护或规则策略）",
  OPERATOR_PLAN: "操作员计划",
};

const REASON_LABELS: Record<string, string> = {
  DECISION_PRECONDITION_CHANGED: "观察已变化，本步撤回并重新规划",
  COLLECT_AIM_NOT_CONFIRMED: "尚未确认行走朝向，未开始前进",
  NO_CONFIRMING_OBSERVATION: "等待期限内未观察到动作效果",
  SCREEN_STILL_OPEN: "窗口仍未关闭",
  GUI_CONFLICT: "当前窗口占用输入",
  DEADLINE_EXCEEDED: "输入授权期限已到",
  CRAFT_MATERIALS_MISSING: "最近库存不足，未发送合成点击",
  CRAFT_SCREEN_UNSUPPORTED: "当前容器没有已支持的合成槽位布局",
  SCREEN_NOT_CONFIRMED: "未确认同一个合成界面，停止后续点击",
};

// Explanations of recorded outcomes, not new action plans or current-world claims.
const READING_GUIDANCE: Readonly<Record<string, string>> = {
  CRAFT_MATERIALS_MISSING: "该步读取的最近库存不足，不代表当前仍然缺料。先核对当前背包与模型要求的材料；本面板不会代为采集或重发点击。",
  CRAFT_SCREEN_UNSUPPORTED: "该步遇到未支持的容器布局，程序没有猜槽位。核对当时打开的界面；不要把反复启动当作已具备该容器能力。",
  SCREEN_NOT_CONFIRMED: "该步没有确认原合成窗口仍有效，后续点击已停止。查看最新界面与库存；结果未知不等于产物丢失，也不授权重放。",
  NO_CONFIRMING_OBSERVATION: "在该步的等待期限内没有确认效果。先核对最新连接与世界读数；不能据此认定动作从未发生或直接重放。",
  SESSION_STOP_REQUESTED: "该步被停止请求中断。请另外核对会话收尾与松键回执；此结论本身不证明输入已释放。",
};

function memberLabel<T>(field: Field<T>): string {
  const gap = fieldGap(field);
  return gap === null ? "已知" : SIGNAL_STATUS_LABELS[gap.status];
}

/**
 * The gloss and the token side by side — or the token alone.
 *
 * An unmapped token glosses to itself, and `STARTED · STARTED` reads like a defect on the
 * screen an operator trusts. The token still appears once and un-folded, because the panel
 * may add a Chinese gloss but may not re-label Core's word.
 */
function glossed(value: string, gloss: ((v: string) => string) | undefined): string {
  const shown = gloss ? gloss(value) : value;
  return shown === value ? value : `${shown} · ${value}`;
}

function MemberRow({
  label,
  field,
  gloss,
}: {
  readonly label: string;
  readonly field: Field<string>;
  readonly gloss?: (v: string) => string;
}) {
  return (
    <div className={styles.row} data-testid={`skill-step-${label}`}>
      <span className={styles.rowLabel}>{label}</span>
      <span className={"value" in field ? styles.rowValue : `${styles.rowValue} ${styles.rowValueUnknown}`}>
        {"value" in field ? glossed(field.value, gloss) : SIGNAL_STATUS_LABELS[field.gap.status]}
      </span>
      <span className={styles.rowAside}>
        <Pill text={memberLabel(field)} tone={"value" in field ? "muted" : "warn"} />
      </span>
      {"value" in field ? null : <span className={styles.rowReason}>{field.gap.reason}</span>}
    </div>
  );
}

function CountRow({ label, field, format }: { readonly label: string; readonly field: Field<number>; readonly format: (v: number) => string }) {
  return (
    <div className={styles.row} data-testid={`skill-step-${label}`}>
      <span className={styles.rowLabel}>{label}</span>
      <span className={"value" in field ? styles.rowValue : `${styles.rowValue} ${styles.rowValueUnknown}`}>
        {"value" in field ? format(field.value) : SIGNAL_STATUS_LABELS[field.gap.status]}
      </span>
      <span className={styles.rowAside}>
        <Pill text={memberLabel(field)} tone={"value" in field ? "muted" : "warn"} />
      </span>
      {"value" in field ? null : <span className={styles.rowReason}>{field.gap.reason}</span>}
    </div>
  );
}

export interface SkillStepPanelProps {
  readonly snapshot: KinSnapshot;
}

/**
 * The snapshot's `skillSteps` group, one row per projected member. The group is a
 * ledger fact only: a row lands when a step CONCLUDES (verdict from the later world
 * readings), so this is the newest concluded step, never the in-flight one, and a Kin
 * that never drove skills keeps the whole group as a named gap rather than a zeroed-out
 * one. Cost and model config are named `not_wired` gaps — Core records them only in the
 * run document, which this read surface does not parse. `behaviorParameters` is the
 * exception: a sealed run's craft step shows its redacted `target_item`/`quantity` here;
 * persona and history summaries likewise require that verified document and describe inputs,
 * not model adoption or current-world knowledge,
 * and a snapshot byte that omits the member renders as a named gap, not a blank row.
 */
export function SkillStepPanel({ snapshot }: SkillStepPanelProps) {
  const group = snapshot.skillSteps;
  const refusal =
    isKnown(group) && "value" in group.value.modelRefusal ? group.value.modelRefusal.value : null;
  const readingGuidance = isKnown(group)
    && "value" in group.value.result && ["FAILED", "UNKNOWN", "INTERRUPTED"].includes(group.value.result.value)
    && "value" in group.value.reason ? READING_GUIDANCE[group.value.reason.value] : undefined;
  return (
    <Panel
      title="技能步读数（逐行来自台账 SkillStepRecorded）"
      note="台账只在一步结论时落行：这里读的是最近一步的结论，不是正在执行中的那一步；结果只取 Core 由后续世界读数判出的 verdict，不取 Bridge 的 SUCCEEDED。"
      testId="panel-skill-steps"
    >
      {isKnown(group) ? (
        <>
          <MemberRow label="自主目标" field={group.value.goal} />
          <CountRow label="最近步序" field={group.value.stepIndex} format={(v) => `第 ${v} 步`} />
          <MemberRow label="技能" field={group.value.skill} />
          <MemberRow label="实际结果" field={group.value.result} gloss={(v) => RESULT_LABELS[v] ?? v} />
          <MemberRow label="结果原因" field={group.value.reason} gloss={(v) => REASON_LABELS[v] ?? v} />
          <MemberRow
            label="决策来源"
            field={group.value.decisionSource}
            gloss={(v) => SOURCE_LABELS[v] ?? v}
          />
          {readingGuidance ? <p className={styles.panelNote} data-testid="skill-step-reading-guidance">
            读数解释：{readingGuidance}
          </p> : null}
          <details>
          <summary>诊断与记录详情</summary>
          <MemberRow label="失败归因" field={group.value.attribution} />
          <MemberRow label="模型拒止" field={group.value.modelRefusal} />
          <CountRow label="技能步数" field={group.value.stepCount} format={(v) => `${v} 步`} />
          <MemberRow label="调用花费" field={group.value.modelCost} />
          <MemberRow label="模型配置状态" field={group.value.modelConfig} />
          <MemberRow label="行为参数" field={group.value.behaviorParameters} />
          <MemberRow label="人格输入来源" field={group.value.personaContext} />
          <MemberRow label="历史记忆输入" field={group.value.sessionHistory} />
          <p className={styles.panelNote}>这两项描述封存运行的心智输入，不证明模型采纳或人格生效；历史阶段不代表当前背包、已松键或目标成功。</p>
          <p className={styles.panelNote} data-testid="skill-step-source-note">
            决策来源是 Core 记录的原始 token，本面板只加中文注释。local_reflection 表示这一步由本地代码执行：可能是紧迫安全保护（例如挨打时撤离一步）、规则策略（rules）的决策，或旧实现的隐式失败回退；该台账行不携带当时选择的决策模式，历史不能判定——不以今天的保存配置、本次启动读数倒推历史。
          </p>
          </details>
          {refusal === "MODEL_NOT_CONFIGURED" ? (
            <p className={styles.panelNote} data-testid="skill-step-model-guidance">
              模型未配置：请在「配置 · 模型与目标」页填写模型连接后重试；当前构建按 MODEL_NOT_CONFIGURED 具名停止，不会自动切换到规则策略；历史运行是否如此没有记录，不做推断。
            </p>
          ) : null}
          <p className={styles.panelNote} data-testid="skill-step-observed">
            最近一步落行于 {formatDateTime(group.observedAt)}；本组取自台账行，不按时间判陈旧。
          </p>
        </>
      ) : (
        <div className={styles.row} data-testid="skill-steps-gap">
          <span className={styles.rowLabel}>技能步</span>
          <span className={`${styles.rowValue} ${styles.rowValueUnknown}`}>{SIGNAL_STATUS_LABELS[group.status]}</span>
          <span className={styles.rowAside}>
            <Pill text={SIGNAL_STATUS_LABELS[group.status]} tone={group.status === "not_wired" ? "muted" : "warn"} />
          </span>
          <span className={styles.rowReason}>{group.reason}</span>
        </div>
      )}
    </Panel>
  );
}
