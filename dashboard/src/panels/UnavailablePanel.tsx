import { Panel } from "../components/Panel";
import styles from "./liveView.module.css";

export interface UnavailableSection {
  readonly label: string;
  readonly reason: string;
}

/** Placeholder page for surfaces whose authoritative source does not exist yet. */
export function UnavailablePanel({
  title,
  intro,
  sections,
  testId,
}: {
  readonly title: string;
  readonly intro: string;
  readonly sections: readonly UnavailableSection[];
  readonly testId: string;
}) {
  return (
    <Panel title={`${title} · 未接入`} note="未接入不等于正常：这里不渲染任何示例人格、成本或派生摘要。" testId={testId}>
      <p className={styles.heading}>{intro}</p>
      <ul className={styles.list}>
        {sections.map((section) => (
          <li key={section.label}>
            <strong>{section.label}：</strong>
            {section.reason}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
