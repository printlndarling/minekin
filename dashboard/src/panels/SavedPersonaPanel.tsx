import type { Field, SavedPersona } from "../domain/model";
import { Panel } from "../components/Panel";
import styles from "./identity.module.css";

const TRAITS: Readonly<Record<string, string>> = {
  social_initiative: "社交主动性", cooperation: "合作倾向", orderliness: "秩序倾向",
  curiosity: "好奇心", risk_tolerance: "风险容忍度",
};
const VALUES: Readonly<Record<string, string>> = {
  autonomy: "自主", fairness: "公平", resource_security: "资源保障",
  belonging: "归属", exploration: "探索", creation: "创造",
};

export function SavedPersonaPanel({ persona }: { readonly persona: Field<SavedPersona> | undefined }) {
  const value = persona !== undefined && "value" in persona ? persona.value : null;
  return <Panel title="角色人格 · 已保存的倾向" testId="panel-saved-persona"
    note="这份人格随角色保存，不会在每次启动或改名时重抽。倾向不是固定动作脚本，也不证明模型已表现出相应行为。">
    {value === null ? <p className={styles.state} data-testid="persona-gap">
      {persona !== undefined && "gap" in persona ? persona.gap.reason : "当前身份接口未携带人格读数，不自动生成默认人格。"}
    </p> : <>
      <dl className={styles.fields}>
        {Object.entries(TRAITS).map(([name, label]) => <div className={styles.field} key={name}>
          <dt className={styles.label}>{label}</dt>
          <dd className={styles.value}>{value.traits[name]} / 9</dd>
        </div>)}
      </dl>
      <p className={styles.stability}>倾向评分为 1–9，不是技能熟练度或成功概率。</p>
      <h3 className={styles.inputLabel}>价值优先顺序</h3>
      <ol aria-label="价值优先顺序">
        {value.value_priority.map((name) => <li key={name}>{VALUES[name]}</li>)}
      </ol>
      <details><summary>版本与来源摘要</summary>
        <p className={styles.mono}>{value.algorithm} · v{value.schema_version}</p>
        <p className={styles.mono}>manifest_sha256={value.manifest_sha256}</p>
      </details>
    </>}
  </Panel>;
}
