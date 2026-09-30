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
 * run document, which this read surface does not parse.
 */
export function SkillStepPanel({ snapshot }: SkillStepPanelProps) {
  const group = snapshot.skillSteps;
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
          <MemberRow label="失败原因" field={group.value.reason} />
          <MemberRow label="失败归因" field={group.value.attribution} />
          <MemberRow label="决策来源" field={group.value.decisionSource} />
          <MemberRow label="模型拒止" field={group.value.modelRefusal} />
          <CountRow label="技能步数" field={group.value.stepCount} format={(v) => `${v} 步`} />
          <MemberRow label="调用花费" field={group.value.modelCost} />
          <MemberRow label="模型配置状态" field={group.value.modelConfig} />
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
