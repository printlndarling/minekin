import { Panel } from "../components/Panel";
import type { Field, SkillExperience } from "../domain/model";
import { formatDateTime } from "../lib/format";
import styles from "./identity.module.css";

const RESULTS: Readonly<Record<string, string>> = {
  CONFIRMED: "已确认", FAILED: "失败", UNKNOWN: "结果未知", INTERRUPTED: "已中断", STARTED: "已开始",
};
const SOURCES: Readonly<Record<string, string>> = {
  model: "模型", local_reflection: "本地反思", OPERATOR_PLAN: "操作员计划", "": "未记录",
};

export function ExperiencesPanel({ experiences }: {
  readonly experiences: Field<readonly SkillExperience[]> | undefined;
}) {
  const records = experiences !== undefined && "value" in experiences ? experiences.value : null;
  return <Panel title="最近行为经历" testId="panel-experiences"
    note="最多 8 条同角色台账记录，可含当前运行；不是某次模型调用的精确输入。过去结果不证明当前世界、背包或权限，不提供动作重放。历史记录不携带当时的决策模式（当时的本地执行也可能是旧实现的隐式失败回退），不能判定；来源 token 保持记录时的原样，不按今天的配置或运行解释。">
    {records === null ? <p className={styles.state}>
      {experiences !== undefined && "gap" in experiences ? experiences.gap.reason : "接口尚未提供经历读数。"}
    </p> : records.length === 0 ? <p className={styles.state}>已读取台账，尚无行为经历记录。</p> : <ol aria-label="最近行为经历">
      {records.map((record) => <li key={record.event_id}>
        <h3>{record.skill} · {RESULTS[record.result] ?? record.result}</h3>
        <p>{formatDateTime(record.observed_at_utc)} · 决策来源：{SOURCES[record.decision_source]}</p>
        {record.reason ? <p>原因：{record.reason}</p> : null}
        <details><summary>事件与运行引用</summary>
          <p className={styles.mono}>event={record.event_id} · position={record.event_position}</p>
          <p className={styles.mono}>run={record.run_id} · session={record.session_id ?? "未记录"}</p>
          <p>CORE 台账历史结果；当前世界适用性未知。</p>
        </details>
      </li>)}
    </ol>}
  </Panel>;
}
