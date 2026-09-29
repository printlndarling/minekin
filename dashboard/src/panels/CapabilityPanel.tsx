import type { AdapterDescriptor } from "../domain/adapter";
import type { DashboardConfig } from "../adapters/config";
import { IDENTITY_ENDPOINTS, READ_ENDPOINTS } from "../adapters/gatewayAdapter";
import { POLL_INTERVAL_MS } from "../hooks/useKinReads";
import { CAPABILITY_ROWS, CAPABILITY_STATE_LABELS, type CapabilityState } from "../shell/capability";
import type { ReadStatus } from "../shell/readStatus";
import { Pill, type Tone } from "../components/Pill";
import { Panel } from "../components/Panel";
import styles from "./capability.module.css";

export interface ReadRouteRow {
  readonly label: string;
  readonly path: string;
  readonly status: ReadStatus;
}

export interface CapabilityPanelProps {
  readonly descriptor: AdapterDescriptor;
  readonly config: DashboardConfig;
  readonly schemaVersion: string;
  readonly rows: readonly ReadRouteRow[];
}

const STATE_TONE: Record<CapabilityState, Tone> = { live: "ok", gap: "warn", reserved: "muted" };

/**
 * The page that answers「这条读路现在怎么样」和「哪些能力根本没有」，用同一份真实数据。
 *
 * The route table is per-read status, so a panel that went deaf is visible here even while
 * the Kin itself looks fine. The capability list below it is the registry the tabs used to
 * stand in for: an unimplemented surface is named with the source it is missing, and a
 * deliberately closed one is labelled as a boundary rather than a defect.
 */
export function CapabilityPanel({ descriptor, config, schemaVersion, rows }: CapabilityPanelProps) {
  const unconfigured = descriptor.kind === "gateway" && config.gatewayBaseUrl === null;
  return (
    <>
      <Panel title="读路状态" note="状态来自每次轮询的落定结果；失败关闭，不缓存旧值冒充在场。" testId="panel-read-routes">
        <table className={styles.table} data-testid="read-route-table">
          <thead>
            <tr>
              <th>读路</th>
              <th>路由</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>
                  <code>{row.path}</code>
                </td>
                <td>
                  <Pill text={row.status.text} tone={row.status.tone} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className={styles.meta} data-testid="read-meta">
          适配器 <code>{descriptor.id}</code> · 来源 <code>{descriptor.kind}</code> · 读模型 <code>{schemaVersion || "未定"}</code> · 轮询每 {POLL_INTERVAL_MS / 1000} 秒 · 冻结路由{" "}
          <code>{READ_ENDPOINTS.snapshot}</code> / <code>{READ_ENDPOINTS.timeline}</code> / <code>{READ_ENDPOINTS.alerts}</code> · 身份面{" "}
          <code>{IDENTITY_ENDPOINTS.identity}</code>
        </p>
        {unconfigured ? (
          <p className={styles.hint} data-testid="gateway-howto">
            当前没有 Gateway 地址，所以本页面不会发起任何网络读取。指向本地受控演示发布的只读面：
            <code>MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8787 pnpm --dir dashboard dev</code>，或直接把地址写进网址{" "}
            <code>?adapter=gateway&amp;gateway=http://127.0.0.1:8787</code>。
          </p>
        ) : null}
      </Panel>

      <Panel title="能力清单" note="未接入＝没有权威数据源；暂不开放＝本产品阶段有意保留的边界。两者都不是故障，也不会渲染成可用功能。" testId="panel-capability">
        <ul className={styles.list}>
          {CAPABILITY_ROWS.map((row) => (
            <li key={row.surface} className={styles.item} data-testid={`capability-${row.state}`}>
              <p className={styles.head}>
                <Pill text={CAPABILITY_STATE_LABELS[row.state]} tone={STATE_TONE[row.state]} />
                <strong>{row.surface}</strong>
              </p>
              <p className={styles.source}>{row.source}</p>
              <p className={styles.detail}>{row.detail}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
