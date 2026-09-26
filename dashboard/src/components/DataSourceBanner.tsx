import type { AdapterDescriptor, ReadFailure } from "../domain/adapter";
import { MOCK_SCENARIOS, type MockScenarioId } from "../fixtures/mockFixtures";
import styles from "./DataSourceBanner.module.css";

export interface DataSourceBannerProps {
  readonly descriptor: AdapterDescriptor;
  readonly scenario: MockScenarioId;
  readonly onScenarioChange: (scenario: MockScenarioId) => void;
  readonly failure: ReadFailure | null;
  readonly isFetching: boolean;
}

/** Loud about provenance: mock readings must never be mistaken for a live Kin. */
export function DataSourceBanner({ descriptor, scenario, onScenarioChange, failure, isFetching }: DataSourceBannerProps) {
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
        <span className={isFetching ? styles.pollBusy : styles.pollIdle} data-testid="poll-state">
          {isFetching ? "读取中…" : "已轮询"}
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
