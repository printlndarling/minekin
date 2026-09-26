import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { createAdapter, readDashboardConfig, type DashboardConfig } from "./adapters/config";
import { DataSourceBanner } from "./components/DataSourceBanner";
import type { MockScenarioId } from "./fixtures/mockFixtures";
import { useAlerts, useSnapshot, useTimeline } from "./hooks/useKinReads";
import { useNow } from "./hooks/useNow";
import { AlertsPanel } from "./panels/AlertsPanel";
import { LiveViewPanel } from "./panels/LiveViewPanel";
import { OverviewPanel } from "./panels/OverviewPanel";
import { TimelinePanel } from "./panels/TimelinePanel";
import { UnavailablePanel } from "./panels/UnavailablePanel";
import styles from "./App.module.css";

const TABS = [
  { id: "overview", label: "总览" },
  { id: "timeline", label: "时间线" },
  { id: "alerts", label: "告警" },
  { id: "live", label: "Live View" },
  { id: "mind", label: "Mind / 成本" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export const READ_ONLY_STATEMENT = "只读面板：不启动、不暂停、不注入游戏输入，也不持有任何凭据。";

const MIND_SECTIONS: readonly { label: string; reason: string }[] = [
  { label: "Persona Manifest 与变化时间线", reason: "PlayerMind/Persona 属 P1，Core 尚无权威数据可读。" },
  { label: "needs / drives 与心境", reason: "没有 reducer 投影出的当前张力读数。" },
  { label: "目标、承诺与切换原因", reason: "目标账本未暴露按 kin 查询接口。" },
  { label: "关系多维视图与证据链接", reason: "关系存储与证据引用尚未产品化。" },
  { label: "自我叙事与取回记忆", reason: "叙事是派生物，需与客观事件分栏后才能显示。" },
  { label: "模型 / 搜索 / 视觉与资源预算", reason: "Tool Gateway 记账未实现，成本无真源。" },
];

export function App({
  config,
  initialTab = "overview",
}: {
  readonly config?: DashboardConfig;
  readonly initialTab?: TabId;
}) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return (
    <QueryClientProvider client={client}>
      <Dashboard config={config} initialTab={initialTab} />
    </QueryClientProvider>
  );
}

function Dashboard({
  config,
  initialTab,
}: {
  readonly config: DashboardConfig | undefined;
  readonly initialTab: TabId;
}) {
  const resolved = useMemo(() => config ?? readDashboardConfig(window.location.search), [config]);
  const [scenario, setScenario] = useState<MockScenarioId>(resolved.scenario);
  const [tab, setTab] = useState<TabId>(initialTab);
  const adapter = useMemo(() => createAdapter(resolved, resolved.adapter === "mock" ? scenario : resolved.scenario), [resolved, scenario]);
  const descriptor = useMemo(() => adapter.describe(), [adapter]);
  const nowMs = useNow(1_000);
  const snapshotRead = useSnapshot(adapter);
  const timelineRead = useTimeline(adapter, [], 50);
  const alertsRead = useAlerts(adapter);

  const changeScenario = (next: MockScenarioId): void => {
    setScenario(next);
    if (resolved.adapter === "mock") {
      window.history.replaceState(null, "", `?adapter=mock&scenario=${next}`);
    }
  };

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Minekin Kin 控制台（只读）</h1>
          <p className={styles.subtitle}>{READ_ONLY_STATEMENT}</p>
        </div>
        <p className={styles.schema} data-testid="schema-version">
          read model <code>{snapshotRead.snapshot.schemaVersion || "未定"}</code>
        </p>
      </header>

      <DataSourceBanner
        descriptor={descriptor}
        scenario={scenario}
        onScenarioChange={changeScenario}
        failure={snapshotRead.failure}
        isFetching={snapshotRead.isFetching}
      />

      <nav className={styles.tabs} aria-label="面板">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? styles.tabActive : styles.tab}
            aria-current={tab === item.id ? "page" : "false"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <main className={styles.main}>
        {tab === "overview" ? <OverviewPanel snapshot={snapshotRead.snapshot} nowMs={nowMs} /> : null}
        {tab === "timeline" ? (
          <TimelinePanel items={timelineRead.items} isLoading={timelineRead.isLoading} failure={timelineRead.failure} />
        ) : null}
        {tab === "alerts" ? (
          <AlertsPanel items={alertsRead.items} isLoading={alertsRead.isLoading} failure={alertsRead.failure} />
        ) : null}
        {tab === "live" ? <LiveViewPanel signal={snapshotRead.snapshot.liveView} nowMs={nowMs} /> : null}
        {tab === "mind" ? (
          <UnavailablePanel
            title="Mind / Soul / 成本"
            intro="P0 只有 Core 与 Bridge 两个进程；以下页面的权威数据源都还不存在。"
            sections={MIND_SECTIONS}
            testId="panel-mind"
          />
        ) : null}
      </main>

      <footer className={styles.footer}>
        <p>
          本面板是 P2 前置的只读外壳：Gateway 只读 API、事件游标与媒体通道尚未实现，缺失字段一律显示未知/未接入。
        </p>
        <p>P0 Core 不依赖 Node；构建产物是静态文件，可由未来的 Gateway 或反向代理直接托管。</p>
      </footer>
    </div>
  );
}
