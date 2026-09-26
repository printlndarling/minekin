import type { ReactNode } from "react";
import styles from "./ui.module.css";

export function Panel({
  title,
  note,
  children,
  testId,
}: {
  readonly title: string;
  readonly note?: string;
  readonly children: ReactNode;
  readonly testId?: string;
}) {
  return (
    <section className={styles.panel} aria-label={title} data-testid={testId}>
      <h2 className={styles.panelTitle}>{title}</h2>
      {children}
      {note ? <p className={styles.panelNote}>{note}</p> : null}
    </section>
  );
}
