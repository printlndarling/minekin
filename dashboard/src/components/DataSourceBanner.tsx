import type { AdapterDescriptor, ReadFailure } from "../domain/adapter";
import { MOCK_SCENARIOS, type MockScenarioId } from "../fixtures/mockFixtures";
import { POLL_INTERVAL_MS, type ReadHealth } from "../hooks/useKinReads";
import { formatAge, formatSpan } from "../lib/format";
import styles from "./DataSourceBanner.module.css";

export interface DataSourceBannerProps {
  readonly descriptor: AdapterDescriptor;
  readonly scenario: MockScenarioId;
  readonly onScenarioChange: (scenario: MockScenarioId) => void;
  readonly failure: ReadFailure | null;
  readonly isFetching: boolean;
  readonly health: ReadHealth;
  readonly nowMs: number;
}

/**
 * The poll is the only channel the frozen contract gives us, so a break in it
 * shows up as a streak of failed reads. Saying「断连」without a count and a retry
 * interval would leave the operator guessing whether the panel is deaf or the
 * Kin is gone.
 */
function healthText(health: ReadHealth, isFetching: boolean, nowMs: number): string {
  if (health.failureStreak > 0) {
    const broke = health.firstFailureAtMs === null ? "断开起点未记录" : `已持续 ${formatSpan(nowMs - health.firstFailureAtMs)}`;
    const lastSuccess = health.lastSuccessAtMs === null ? "尚无成功读数" : `末次成功 ${formatAge(new Date(health.lastSuccessAtMs).toISOString(), nowMs)}`;
    return `断连 · 连续 ${health.failureStreak} 次读取失败 · ${broke} · ${lastSuccess} · 每 ${POLL_INTERVAL_MS / 1000} 秒自动重试`;
  }
  if (health.lastSuccessAtMs === null) return isFetching ? "首次读取中…" : "等待首次读取";
  return `读数正常 · 末次成功 ${formatAge(new Date(health.lastSuccessAtMs).toISOString(), nowMs)} · 每 ${POLL_INTERVAL_MS / 1000} 秒轮询`;
}

/** Loud about provenance: mock readings must never be mistaken for a live Kin. */
export function DataSourceBanner({ descriptor, scenario, onScenarioChange, failure, isFetching, health, nowMs }: DataSourceBannerProps) {
  const degraded = health.failureStreak > 0;
  return (
    <div className={`${styles.banner} ${descriptor.mock ? styles.bannerMock : styles.bannerReal}`} data-testid="data-source-banner">
      <div className={styles.left}>
        <span className={styles.badge}>{descriptor.mock ? "模拟数据 MOCK" : "真实读数"}</span>
        <span className={styles.label}>{descriptor.label}</span>
        <span className={styles.note}>{descriptor.note}</span>
      </div>
      <div className={styles.right}>
        {descriptor.mock ? (
          <label className={styles.picker}>
            <span>模拟场景</span>
            <select
              value={scenario}
              onChange={(event) => {
                const next = MOCK_SCENARIOS.find((s) => s.id === event.target.value);
                if (next) onScenarioChange(next.id);
              }}
            >
              {MOCK_SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <span
          className={degraded ? styles.pollFailed : isFetching ? styles.pollBusy : styles.pollIdle}
          data-testid="poll-state"
        >
          {healthText(health, isFetching, nowMs)}
        </span>
      </div>
      {failure ? (
        <p className={styles.failure} data-testid="read-failure">
          读取失败 · {failure.kind}：{failure.message} 面板值全部按未知显示。
        </p>
      ) : null}
    </div>
  );
}
