import { KIN_STATE_LABELS, LINK_STATE_LABELS, SESSION_MODE_LABELS } from "../domain/labels";
import type { KinSnapshot } from "../domain/model";
import { isKnown } from "../domain/signals";
import { formatDateTime, formatNumber } from "../lib/format";
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
          format={(v) => `seq ${v.lastSequence} · 间隔 ${formatNumber(v.intervalMs, 0)}ms · lease ${v.inputLeaseHeld ? "持有" : "无"}`}
        />
      </Panel>

      <Panel title="会话与版本" note="generation 变化意味着旧 lease、旧观察与新会话不可混用。" testId="panel-session">
        <SignalValue
          label="会话"
          signal={snapshot.session}
          nowMs={nowMs}
          format={(v) => `${v.sessionId} · gen ${v.generation} · ${SESSION_MODE_LABELS[v.mode]} · 起于 ${formatDateTime(v.startedAt)}`}
        />
        <SignalValue
          label="世界上下文"
          signal={snapshot.world}
          nowMs={nowMs}
          format={(v) =>
            `${v.profileName} · ${v.worldContext} · epoch ${v.epoch} · ${v.joined ? "已入服" : "未入服"} · 版本 ${v.resolvedVersion}`
          }
        />
        <SignalValue
          label="版本集合"
          signal={snapshot.versions}
          nowMs={nowMs}
          format={(v) => `runtime ${v.runtime} · bridge ${v.bridge} · bundle ${v.clientBundle} · java ${v.java} · loader ${v.fabricLoader}`}
        />
        <SignalValue
          label="自身状态（玩家可知）"
          signal={snapshot.selfState}
          nowMs={nowMs}
          format={(v) => `生命 ${formatNumber(v.health)} · 饥饿 ${formatNumber(v.food, 0)} · ${v.dimension} · GUI ${v.guiOpen ? "打开" : "关闭"}`}
        />
      </Panel>

      <Panel title="证据来源" note="面板只引用 Core 已封存的读数，不据此宣称 tested 或在线。" testId="panel-evidence">
        <SignalValue
          label="证据引用"
          signal={snapshot.evidence}
          nowMs={nowMs}
          format={(v) => `run ${v.runId} · attempt ${v.attempt} · ${v.bundleDigest} · 封存于 ${formatDateTime(v.sealedAt)}`}
          showSource
        />
        <SignalValue label="Live View" signal={snapshot.liveView} nowMs={nowMs} format={(v) => v.transport} />
        {isKnown(lease) ? null : <p className="muted">心跳不可用时，任何“在线”结论都必须撤回。</p>}
      </Panel>
    </>
  );
}
