import { Panel } from "../components/Panel";
import { SignalValue } from "../components/SignalValue";
import type { SelfState } from "../domain/model";
import { freshnessOf, isKnown, type Signal } from "../domain/signals";
import { formatDateTime, formatNumber } from "../lib/format";
import styles from "./vitals.module.css";

/** Instruments use only fresh admitted HUD observations, never default scores. */
export function PlayerVitalsPanel({ signal, nowMs }: {
  readonly signal: Signal<SelfState>;
  readonly nowMs: number;
}) {
  const fresh = isKnown(signal) && freshnessOf(signal, nowMs) === "fresh";
  return <Panel title="角色身体" testId="panel-vitals"
    note="只展示玩家 HUD 读数，不据此保证安全或判断死亡。最大生命尚未提供，不显示生命百分比。">
    <SignalValue label="自身状态（玩家可知）" signal={signal} nowMs={nowMs}
      format={(v) => `${fresh ? "" : "历史读数 · "}生命 ${formatNumber(v.health)} · 饥饿 ${formatNumber(v.food, 0)}`}
      showSource />
    {fresh && isKnown(signal) ? <div className={styles.grid}>
      <div className={styles.reading}>
        <span>生命值</span>
        <strong>{formatNumber(signal.value.health)}</strong>
        <small>最大生命未知</small>
      </div>
      <div className={styles.reading}>
        <label htmlFor="player-food-meter">饱食度</label>
        <strong>{signal.value.food} / 20</strong>
        <meter id="player-food-meter" min={0} max={20} value={signal.value.food}
          aria-label="饱食度" />
        <small>数值越高，越饱</small>
      </div>
    </div> : <p className={styles.notice}>当前身体仪表不可用；等待新鲜观察，不沿用旧数值。</p>}
    {isKnown(signal) ? <p className={styles.notice}>
      {signal.source === "mock" || signal.sourceRef.startsWith("mock://") ? "模拟读数" : "网关读数"} · 采样于 {formatDateTime(signal.observedAt)}
    </p> : null}
  </Panel>;
}
