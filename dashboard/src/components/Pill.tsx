import styles from "./ui.module.css";

export type Tone = "ok" | "warn" | "bad" | "muted";

const TONE_CLASS: Record<Tone, string> = {
  ok: styles.pillOk ?? "",
  warn: styles.pillWarn ?? "",
  bad: styles.pillBad ?? "",
  muted: styles.pillMuted ?? "",
};

export function Pill({ text, tone, title }: { readonly text: string; readonly tone: Tone; readonly title?: string }) {
  return (
    <span className={`${styles.pill} ${TONE_CLASS[tone]}`} title={title ?? text}>
      {text}
    </span>
  );
}
