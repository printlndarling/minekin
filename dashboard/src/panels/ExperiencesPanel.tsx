import { useState } from "react";
import { Panel } from "../components/Panel";
import type { Field, SkillExperience } from "../domain/model";
import { formatDateTime } from "../lib/format";
import styles from "./identity.module.css";
import controls from "./timeline.module.css";

const RESULTS: Readonly<Record<string, string>> = {
  CONFIRMED: "已确认", FAILED: "失败", UNKNOWN: "结果未知", INTERRUPTED: "已中断", STARTED: "已开始",
};
const SOURCES: Readonly<Record<string, string>> = {
  model: "模型", local_reflection: "本地反思", OPERATOR_PLAN: "操作员计划", "": "未记录",
};

export function ExperiencesPanel({ experiences }: {
  readonly experiences: Field<readonly SkillExperience[]> | undefined;
}) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [result, setResult] = useState("all");
  const records = experiences !== undefined && "value" in experiences ? experiences.value : null;
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const shown = records?.filter((record) => {
    const text = [record.skill, record.reason, record.event_id, record.run_id, record.session_id ?? ""]
      .join(" ").toLocaleLowerCase();
    return (source === "all" || record.decision_source === source)
      && (result === "all" || record.result === result)
      && terms.every((term) => text.includes(term));
  }) ?? [];
  const hasFilter = query !== "" || source !== "all" || result !== "all";
  return <Panel title="最近行为经历" testId="panel-experiences"
    note="最多 8 条同角色台账记录，可含当前运行；不是某次模型调用的精确输入。过去结果不证明当前世界、背包或权限，不提供动作重放。历史记录不携带当时的决策模式（当时的本地执行也可能是旧实现的隐式失败回退），不能判定；来源 token 保持记录时的原样，不按今天的配置或运行解释。">
    {records === null ? <p className={styles.state}>
      {experiences !== undefined && "gap" in experiences ? experiences.gap.reason : "接口尚未提供经历读数。"}
    </p> : <>
      <div className={controls.toolbar}>
        <label className={controls.searchLabel}>搜索经历
          <input className={controls.search} type="search" value={query}
            placeholder="技能、原因、事件或运行引用…" onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className={controls.searchLabel}>经历决策来源
          <select className={controls.search} value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="all">全部记录来源</option>
            {Object.entries(SOURCES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className={controls.searchLabel}>经历结果
          <select className={controls.search} value={result} onChange={(event) => setResult(event.target.value)}>
            <option value="all">全部结果</option>
            {Object.entries(RESULTS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button type="button" className={controls.chip} disabled={!hasFilter}
          onClick={() => { setQuery(""); setSource("all"); setResult("all"); }}>清除经历筛选</button>
      </div>
      <p className={styles.state} role="status">显示 {shown.length} / {records.length} 条已加载经历；不代表完整历史。</p>
      {records.length === 0 ? <p className={styles.state}>已读取台账，尚无行为经历记录。</p>
        : shown.length === 0 ? <p className={styles.state}>当前已加载经历中无匹配记录。</p> : null}
      <ol aria-label="最近行为经历">
      {shown.map((record) => <li key={record.event_id}>
        <h3>{record.skill} · {RESULTS[record.result] ?? record.result}</h3>
        <p>{formatDateTime(record.observed_at_utc)} · 决策来源：{SOURCES[record.decision_source] ?? record.decision_source}</p>
        {record.reason ? <p>原因：{record.reason}</p> : null}
        <details><summary>事件与运行引用</summary>
          <p className={styles.mono}>event={record.event_id} · position={record.event_position}</p>
          <p className={styles.mono}>run={record.run_id} · session={record.session_id ?? "未记录"}</p>
          <p>CORE 台账历史结果；当前世界适用性未知。</p>
        </details>
      </li>)}
    </ol></>}
  </Panel>;
}
