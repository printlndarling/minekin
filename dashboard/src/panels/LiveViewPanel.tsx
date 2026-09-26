import { SIGNAL_STATUS_LABELS } from "../domain/labels";
import type { MediaStreamRef } from "../domain/model";
import { isKnown, type Signal } from "../domain/signals";
import { Panel } from "../components/Panel";
import { SignalValue } from "../components/SignalValue";
import styles from "./liveView.module.css";

const PREREQUISITES: readonly string[] = [
  "真实帧源：受控客户端窗口/帧缓冲采集进程（Xvfb + FFmpeg 或 Windows 等价物）。",
  "媒体中继与鉴权：MediaMTX/WebRTC 或等价通道，带观看权限与观看审计。",
  "断流语义：与 Runtime/Bridge 故障状态区分，断流不得影响本地反射与输入释放。",
  "画面 provenance：可证明画面来自该 run/attempt 的同一客户端，而不是示例视频。",
];

/**
 * Live View stays empty on purpose. Rendering a placeholder frame, a stock
 * clip or a "connecting…" spinner would be fabricated evidence of a game view.
 */
export function LiveViewPanel({ signal, nowMs }: { readonly signal: Signal<MediaStreamRef>; readonly nowMs: number }) {
  return (
    <Panel title="Live View（游戏画面）" note="本卡不做媒体接入：没有真帧源时只显示不可用原因。" testId="panel-liveview">
      <SignalValue label="媒体通道" signal={signal} nowMs={nowMs} format={(v) => `${v.transport} · ${v.url}`} />
      <p className={styles.statement} data-testid="liveview-statement">
        {isKnown(signal) && signal.value.available
          ? "媒体通道报告可用，但本版本仍不渲染画面：真帧验证未完成。"
          : `当前状态：${isKnown(signal) ? "已读数" : SIGNAL_STATUS_LABELS[signal.status]}。没有真实帧源，不显示任何画面内容。`}
      </p>
      <div className={styles.block}>
        <p className={styles.heading}>接入真实 Live View 仍缺：</p>
        <ul className={styles.list}>
          {PREREQUISITES.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
