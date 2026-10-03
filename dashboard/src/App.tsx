import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { createAdapter, readDashboardConfig, type DashboardConfig } from "./adapters/config";
import { DataSourceBanner } from "./components/DataSourceBanner";
import type { MockScenarioId } from "./fixtures/mockFixtures";
import { deriveSessionProgress } from "./domain/sessionProgress";
import { useAlerts, useSnapshot, useTimeline } from "./hooks/useKinReads";
import { useNow } from "./hooks/useNow";
import { IdentityPanel } from "./panels/IdentityPanel";
import { ConfigPanel } from "./panels/ConfigPanel";
import { ServerPanel, useServerRead } from "./panels/ServerPanel";
import { SessionControlPanel } from "./panels/SessionControlPanel";
import { SessionStartPanel } from "./panels/SessionStartPanel";
import { GoalPanel } from "./panels/GoalPanel";
import { RecipeCoveragePanel } from "./panels/RecipeCoveragePanel";
import { AlertsPanel } from "./panels/AlertsPanel";
import { CapabilityPanel } from "./panels/CapabilityPanel";
import { OverviewPanel } from "./panels/OverviewPanel";
import { SessionProgressPanel } from "./panels/SessionProgressPanel";
import { SkillStepPanel } from "./panels/SkillStepPanel";
import { TimelinePanel } from "./panels/TimelinePanel";
import { ContextBar } from "./components/ContextBar";
import { NAV_GROUPS, pageLabel, type PageId } from "./shell/navigation";
import { useHashRoute } from "./shell/useHashRoute";
import { IDENTITY_ENDPOINTS, READ_ENDPOINTS, CONFIG_ENDPOINTS, SESSION_ENDPOINTS, GOAL_ENDPOINTS, RECIPE_ENDPOINTS } from "./adapters/gatewayAdapter";
import { useIdentityRead } from "./hooks/useIdentityController";
import { useConfigRead } from "./hooks/useConfigController";
import { useSessionRead } from "./hooks/useSessionController";
import { useGoalRead } from "./hooks/useGoalController";
import { useRecipeCoverageRead } from "./hooks/useRecipeCoverageController";
import { readStatusOf, type ReadStatus } from "./shell/readStatus";
import styles from "./App.module.css";

export type { PageId } from "./shell/navigation";

export const READ_ONLY_STATEMENT =
  "运行控制台：查看角色状态与动作，管理模型、目标和身份，并停止当前会话。密钥由本机进程环境提供。";

export function App({
  config,
  initialPage,
}: {
  readonly config?: DashboardConfig;
  readonly initialPage?: PageId;
}) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return (
    <QueryClientProvider client={client}>
      <Dashboard config={config} initialPage={initialPage} />
    </QueryClientProvider>
  );
}

function Dashboard({
  config,
  initialPage,
}: {
  readonly config: DashboardConfig | undefined;
  readonly initialPage: PageId | undefined;
}) {
  const resolved = useMemo(() => config ?? readDashboardConfig(window.location.search), [config]);
  const [scenario, setScenario] = useState<MockScenarioId>(resolved.scenario);
  const [page, selectPage] = useHashRoute(initialPage);
  const mainRef = useRef<HTMLElement>(null);
  const adapter = useMemo(
    () => createAdapter(resolved, resolved.adapter === "mock" ? scenario : resolved.scenario),
    [resolved, scenario],
  );
  const descriptor = useMemo(() => adapter.describe(), [adapter]);
  const nowMs = useNow(1_000);
  const snapshotRead = useSnapshot(adapter);
  const timelineRead = useTimeline(adapter, [], 50);
  const alertsRead = useAlerts(adapter);
  const identityRead = useIdentityRead(adapter);
  const configRead = useConfigRead(adapter);
  const serverRead = useServerRead(adapter);
  const sessionRead = useSessionRead(adapter);
  const goalRead = useGoalRead(adapter);
  const recipeRead = useRecipeCoverageRead(adapter);
  const sessionProgress = useMemo(() => deriveSessionProgress(timelineRead.items), [timelineRead.items]);

  const snapshotStatus = readStatusOf(
    { isLoading: snapshotRead.isLoading, failure: snapshotRead.failure },
    { nowMs, health: snapshotRead.health },
  );
  const timelineStatus = readStatusOf(timelineRead, { nowMs });
  const alertsStatus = readStatusOf(alertsRead, { nowMs });
  const identityStatus = readStatusOf(identityRead, { nowMs });
  const configStatus = readStatusOf(configRead, { nowMs });
  const sessionStatus = readStatusOf(sessionRead, { nowMs });
  const goalStatus = readStatusOf(goalRead, { nowMs });
  const recipeStatus = readStatusOf(recipeRead, { nowMs });

  const statusFor: Record<PageId, ReadStatus> = {
    overview: snapshotStatus,
    task: goalStatus,
    timeline: timelineStatus,
    alerts: alertsStatus,
    config: configStatus,
    server: readStatusOf(serverRead, { nowMs }),
    identity: identityStatus,
    session: sessionStatus,
    recipes: recipeStatus,
    data: snapshotStatus,
  };

  const changeScenario = (next: MockScenarioId): void => {
    setScenario(next);
    if (resolved.adapter === "mock") {
      // The fragment is what selects the page, and `replaceState` with a bare query would
      // drop it: keeping both means a scenario switch cannot teleport the operator.
      window.history.replaceState(null, "", `?adapter=mock&scenario=${next}#${page}`);
    }
  };

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#dashboard-content" onClick={(event) => {
        event.preventDefault();
        mainRef.current?.focus();
      }}>跳到当前面板</a>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Minekin Kin 控制台</h1>
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
        health={snapshotRead.health}
        nowMs={nowMs}
      />

      <ContextBar
        snapshot={snapshotRead.snapshot}
        nowMs={nowMs}
        identityRead={identityRead}
        snapshotHealth={snapshotRead.health}
        progress={sessionProgress}
        timelineFailure={timelineRead.failure}
        alertsEnvelope={alertsRead.envelope}
        alertsFailure={alertsRead.failure}
      />

      <div className={styles.body}>
        <nav className={styles.nav} aria-label="面板">
          {NAV_GROUPS.map((group) => (
            <div key={group.id} className={styles.group}>
              <p className={styles.groupLabel}>{group.label}</p>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={page === item.id ? styles.navActive : styles.navItem}
                  aria-current={page === item.id ? "page" : "false"}
                  title={item.hint}
                  onClick={() => selectPage(item.id)}
                >
                  <span className={statusFor[item.id].tone === "bad" ? styles.dotBad : statusFor[item.id].tone === "warn" ? styles.dotWarn : styles.dotOk} />
                  <span className={styles.navText}>
                    <span className={styles.navLabel}>{item.label}</span>
                    <span className={styles.navStatus}>{statusFor[item.id].text}</span>
                  </span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <main ref={mainRef} id="dashboard-content" tabIndex={-1} className={styles.main} data-testid={`page-${page}`} aria-label={pageLabel(page)}>
          {page === "overview" ? (
            <>
              <OverviewPanel snapshot={snapshotRead.snapshot} nowMs={nowMs} />
              <SessionProgressPanel
                progress={sessionProgress}
                nowMs={nowMs}
                isLoading={timelineRead.isLoading}
                failure={timelineRead.failure}
              />
              <SkillStepPanel snapshot={snapshotRead.snapshot} />
            </>
          ) : null}
          {page === "task" ? <GoalPanel adapter={adapter} nowMs={nowMs} /> : null}
          {page === "recipes" ? <RecipeCoveragePanel adapter={adapter} nowMs={nowMs} /> : null}
          {page === "timeline" ? (
            <TimelinePanel items={timelineRead.items} isLoading={timelineRead.isLoading} failure={timelineRead.failure} />
          ) : null}
          {page === "alerts" ? (
            <AlertsPanel envelope={alertsRead.envelope} isLoading={alertsRead.isLoading} failure={alertsRead.failure} />
          ) : null}
          {page === "config" ? <ConfigPanel adapter={adapter} nowMs={nowMs} /> : null}
          {page === "server" ? <ServerPanel adapter={adapter} /> : null}
          {page === "identity" ? <IdentityPanel adapter={adapter} nowMs={nowMs} /> : null}
          {page === "session" ? <><SessionStartPanel adapter={adapter} /><SessionControlPanel adapter={adapter} nowMs={nowMs} /></> : null}
          {page === "data" ? (
            <CapabilityPanel
              descriptor={descriptor}
              config={resolved}
              schemaVersion={snapshotRead.snapshot.schemaVersion}
              rows={[
                { label: "快照读数", path: READ_ENDPOINTS.snapshot, status: snapshotStatus },
                { label: "事件时间线", path: READ_ENDPOINTS.timeline, status: timelineStatus },
                { label: "告警信封", path: READ_ENDPOINTS.alerts, status: alertsStatus },
                { label: "配置读数", path: CONFIG_ENDPOINTS.config, status: configStatus },
                { label: "服务器设置", path: "/api/v1/dashboard/server", status: statusFor.server },
                { label: "身份读数", path: IDENTITY_ENDPOINTS.identity, status: identityStatus },
                { label: "会话读数", path: SESSION_ENDPOINTS.session, status: sessionStatus },
                { label: "目标读数", path: GOAL_ENDPOINTS.goal, status: goalStatus },
                { label: "配方覆盖读数", path: RECIPE_ENDPOINTS.recipe, status: recipeStatus },
              ]}
            />
          ) : null}
        </main>
      </div>

      <footer className={styles.footer}>
        <p>
          在配置页保存模型与目标、测试连接，在身份页修改角色名称。状态与日志来自本地 Gateway。
        </p>
        <p>尚未接入的能力和对应原因可在「数据源与缺口」页查看。</p>
      </footer>
    </div>
  );
}
