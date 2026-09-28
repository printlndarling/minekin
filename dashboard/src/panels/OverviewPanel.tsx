import { KIN_STATE_LABELS, LINK_STATE_LABELS, SESSION_MODE_LABELS } from "../domain/labels";
import type { KinSnapshot } from "../domain/model";
import { isKnown } from "../domain/signals";
import { fieldText, formatDateTime, formatNumber } from "../lib/format";
import { Panel } from "../components/Panel";
import { SignalValue } from "../components/SignalValue";

export function OverviewPanel({ snapshot, nowMs }: { readonly snapshot: KinSnapshot; readonly nowMs: number }) {
  const lease = snapshot.bridgeHeartbeat;
  return (
    <>
      <Panel title="Kin 运行状态" note="状态取值只来自 read adapter；失联或未观测时不给出猜测值。" testId="panel-kin">
        <SignalValue label="Kin ID" signal={snapshot.kinId} nowMs={nowMs} format={(v) => v} showSource />
        <SignalValue label="runtime_state" signal={snapshot.runtimeState} nowMs={nowMs} format={(v) => KIN_STATE_LABELS[v]} />
        <SignalValue label="Bridge 链路" signal={snapshot.bridgeLink} nowMs={nowMs} format={(v) => LINK_STATE_LABELS[v]} />
        <SignalValue label="服务器链路" signal={snapshot.serverLink} nowMs={nowMs} format={(v) => LINK_STATE_LABELS[v]} />
        <SignalValue
          label="Bridge 心跳"
          signal={snapshot.bridgeHeartbeat}
          nowMs={nowMs}
          format={(v) =>
            `序列 ${fieldText(v.lastSequence, (n) => String(n))} · 间隔 ${fieldText(v.intervalMs, (n) => `${formatNumber(n, 0)}ms`)} · lease ${fieldText(v.inputLeaseHeld, (b) => (b ? "持有" : "无"))}`
          }
        />
      </Panel>

      <Panel title="会话与版本" note="generation 变化意味着旧 lease、旧观察与新会话不可混用。" testId="panel-session">
        <SignalValue
          label="会话"
          signal={snapshot.session}
          nowMs={nowMs}
          format={(v) =>
            `${fieldText(v.sessionId, (s) => s)} · gen ${fieldText(v.generation, (g) => String(g))} · 模式 ${fieldText(v.mode, (m) => SESSION_MODE_LABELS[m])} · 起于 ${fieldText(v.startedAt, formatDateTime)} · pid ${fieldText(v.pid, (p) => String(p))} · 覆盖层 ${fieldText(v.overlay, (o) => o)}`
          }
          showSource
        />
        <SignalValue
          label="世界上下文"
          signal={snapshot.world}
          nowMs={nowMs}
          format={(v) =>
            `入服 ${fieldText(v.joined, (b) => (b ? "已入服" : "未入服"))} · profile ${fieldText(v.profileId, (p) => p)} · 名称 ${fieldText(v.profileName, (n) => n)} · 上下文 ${fieldText(v.worldContext, (c) => c)} · epoch ${fieldText(v.epoch, (e) => String(e))} · resolvedVersion ${fieldText(v.resolvedVersion, (r) => r)}`
          }
        />
        <SignalValue
          label="版本集合"
          signal={snapshot.versions}
          nowMs={nowMs}
          format={(v) =>
            `runtime ${fieldText(v.runtime, (r) => r)} · java ${fieldText(v.java, (j) => j)} · loader ${fieldText(v.fabricLoader, (f) => f)} · bridge ${fieldText(v.bridge, (b) => b)} · bundle ${fieldText(v.clientBundle, (c) => c)}`
          }
        />
        <SignalValue
          label="自身状态（玩家可知）"
          signal={snapshot.selfState}
          nowMs={nowMs}
          format={(v) => `生命 ${formatNumber(v.health)} · 饥饿 ${formatNumber(v.food, 0)}`}
        />
      </Panel>

      <Panel title="证据来源" note="面板只引用 Core 已封存的读数，不据此宣称 tested 或在线。" testId="panel-evidence">
        <SignalValue
          label="证据引用"
          signal={snapshot.evidence}
          nowMs={nowMs}
          format={(v) =>
            `run ${fieldText(v.runId, (r) => r)} · attempt ${fieldText(v.attempt, (a) => String(a))} · ${fieldText(v.bundleDigest, (d) => d)} · 封存 ${fieldText(v.sealedAt, formatDateTime)}`
          }
          showSource
        />
        <SignalValue label="Live View" signal={snapshot.liveView} nowMs={nowMs} format={(v) => v.transport} />
        {isKnown(lease) ? null : <p className="muted">心跳不可用时，任何“在线”结论都必须撤回。</p>}
      </Panel>
    </>
  );
}
