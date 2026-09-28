import { describe, expect, it } from "vitest";
import { deriveSessionProgress } from "./sessionProgress";
import type { TimelineEvent, TimelineKind, TimelineOutcome } from "./model";
import { REAL_TIMELINE_WIRE } from "../test/realGatewayWire";
import { decodeTimelinePayload } from "../adapters/gatewayAdapter";

/**
 * The session-progress reading is derived only from ledger rows the Gateway
 * already serves: `title` is Core's event-type name and `sourceRef` carries the
 * ledger position. These tests pin the two properties that make the panel
 * trustworthy — an old attempt must not credit the current one, and a row that
 * never happened must stay 未观测 rather than being drawn as a greyed-out step.
 */

function row(position: number, title: string, detail: string | null = null, kind: TimelineKind = "session", outcome: TimelineOutcome = "applied"): TimelineEvent {
  return {
    eventId: `evt-${position}`,
    kind,
    at: `2026-09-28T00:00:${String(position % 60).padStart(2, "0")}Z`,
    monotonicMs: null,
    generation: 1,
    sequence: position,
    title,
    detail,
    outcome,
    sourceRef: `ledger://kin-01/${position}`,
  };
}

function state(progress: ReturnType<typeof deriveSessionProgress>, key: string): string {
  const stage = progress.stages.find((s) => s.key === key);
  if (stage === undefined) throw new Error(`没有名为 ${key} 的阶段`);
  return stage.state;
}

describe("会话进度派生", () => {
  it("真实 Gateway 的两行：启动与离场都成立，终态是正常离场", () => {
    const decoded = decodeTimelinePayload(REAL_TIMELINE_WIRE);
    if (!decoded.ok) throw new Error(`真实 Gateway 字节解不开：${decoded.issues.join("; ")}`);
    const progress = deriveSessionProgress(decoded.events);
    expect(progress.pinned).toBe(true);
    expect(progress.hasRows).toBe(true);
    expect(state(progress, "launch")).toBe("observed");
    expect(state(progress, "exit")).toBe("observed");
    expect(state(progress, "join")).toBe("absent");
    expect(progress.terminal).toEqual({ label: "客户端已离场", at: "2000-01-01T00:00:05Z", detail: null, failed: false });
    expect(progress.granted).toBe(0);
    expect(progress.refused).toBe(0);
  });

  it("入服到可玩之间断掉：只承认到 join，绝不把可玩画成灰色已完成", () => {
    const progress = deriveSessionProgress([
      row(10, "SessionProcessStarted"),
      row(11, "BridgeHelloAccepted"),
      row(12, "JoinObserved", "phase=join"),
    ]);
    expect(state(progress, "join")).toBe("observed");
    expect(state(progress, "playable")).toBe("absent");
    expect(state(progress, "lease")).toBe("absent");
    expect(progress.furthest?.key).toBe("join");
    expect(progress.terminal).toBeNull();
  });

  it("行序不影响读数（Gateway 是最新在前，倒序也必须同解）", () => {
    const ascending = [row(10, "SessionProcessStarted"), row(11, "JoinObserved"), row(12, "PlayableEstablished")];
    expect(deriveSessionProgress([...ascending].reverse())).toEqual(deriveSessionProgress(ascending));
  });

  it("旧 attempt 走过的阶段不算当前 attempt 的进度（锚定新启动行之后的判别）", () => {
    const oldAttempt = [row(1, "SessionProcessStarted"), row(2, "JoinObserved"), row(3, "PlayableEstablished"), row(4, "ClientProcessExited")];
    const newAttempt = [row(5, "SessionProcessStarted"), row(6, "BridgeHelloAccepted")];
    const progress = deriveSessionProgress([...oldAttempt, ...newAttempt]);
    expect(progress.pinned).toBe(true);
    expect(progress.attemptStartedAt).toBe(row(5, "").at);
    expect(state(progress, "hello")).toBe("observed");
    expect(state(progress, "playable")).toBe("absent");
    expect(progress.terminal).toBeNull();
    // 反对照：把新 attempt 的两行拿掉，旧会话的离场与可玩就必须显形，
    // 否则上面那条「absent」可能只是因为整个窗口是空的。
    const withoutNew = deriveSessionProgress(oldAttempt);
    expect(withoutNew.attemptStartedAt).toBe(row(1, "").at);
    expect(state(withoutNew, "playable")).toBe("observed");
    expect(withoutNew.terminal?.label).toBe("客户端已离场");
  });

  it("启动失败带 Core 的 reason：终具名失败并原样带出细节", () => {
    const progress = deriveSessionProgress([row(7, "SessionProcessStarted"), row(8, "SessionProcessFailed", "reason=launcher_exit_2", "fault", "rejected")]);
    expect(progress.terminal).toEqual({ label: "客户端启动失败", at: row(8, "").at, detail: "reason=launcher_exit_2", failed: true });
    expect(state(progress, "hello")).toBe("absent");
  });

  it("中断与离场同时存在时按台账位置取更晚的那条", () => {
    const interruptedLast = deriveSessionProgress([row(1, "ClientProcessExited"), row(2, "SessionInterrupted", "reason=watchdog")]);
    expect(interruptedLast.terminal).toMatchObject({ label: "会话被中断", failed: true, detail: "reason=watchdog" });
    const exitedLast = deriveSessionProgress([row(1, "SessionInterrupted", "reason=watchdog"), row(2, "ClientProcessExited")]);
    expect(exitedLast.terminal?.label).toBe("客户端已离场");
  });

  it("租约按次计数，拒止原因去重排序后原样暴露", () => {
    const progress = deriveSessionProgress([
      row(1, "SessionProcessStarted"),
      row(2, "InputLeaseGranted", "capability=move"),
      row(3, "InputRefused", "capability=turn, reason=lease_expired", "input", "rejected"),
      row(4, "InputReleased"),
      row(5, "InputLeaseGranted", "capability=move"),
      row(6, "InputRefused", "capability=move, reason=admission_denied", "input", "rejected"),
      row(7, "InputRefused", "capability=turn, reason=lease_expired", "input", "rejected"),
    ]);
    expect(progress.granted).toBe(2);
    expect(progress.released).toBe(1);
    expect(progress.refused).toBe(3);
    expect(progress.refusalReasons).toEqual([
      "capability=move, reason=admission_denied",
      "capability=turn, reason=lease_expired",
    ]);
    expect(state(progress, "release")).toBe("observed");
  });

  it("释放分开数：真有租约交还的与手上已经没租约的不是同一件事", () => {
    const progress = deriveSessionProgress([
      row(1, "SessionProcessStarted"),
      row(2, "InputReleased", "reason=TIMEOUT, had_lease=True"),
      row(3, "InputReleased", "reason=TIMEOUT, had_lease=True"),
      row(4, "InputReleased", "reason=EXPLICIT, had_lease=False"),
    ]);
    expect(progress.released).toBe(3);
    expect(progress.releases).toEqual({ total: 3, handedBack: 2, withoutLease: 1, unrecorded: 0 });
  });

  it("没写有没有租约的释放行不靠猜：两类都不加，单列为未记录", () => {
    const progress = deriveSessionProgress([
      row(1, "SessionProcessStarted"),
      row(2, "InputReleased"),
      row(3, "InputReleased", "reason=EXPLICIT"),
      row(4, "InputReleased", "had_lease=1"),
      row(5, "InputReleased", "reason=TIMEOUT, had_lease=True"),
    ]);
    expect(progress.releases).toEqual({ total: 4, handedBack: 1, withoutLease: 0, unrecorded: 3 });
  });

  it("上一段会话的释放行不进本次的分拆", () => {
    const previous = [row(1, "SessionProcessStarted"), row(2, "InputReleased", "reason=EXPLICIT, had_lease=True")];
    const current = [row(3, "SessionProcessStarted"), row(4, "InputReleased", "reason=TIMEOUT, had_lease=False")];
    const progress = deriveSessionProgress([...previous, ...current]);
    expect(progress.pinned).toBe(true);
    expect(progress.releases).toEqual({ total: 1, handedBack: 0, withoutLease: 1, unrecorded: 0 });
  });

  it("没有启动行时不假装锚定：整窗都算进来看，并申报未锚定", () => {
    const progress = deriveSessionProgress([row(1, "BridgeHelloAccepted"), row(2, "JoinObserved")]);
    expect(progress.pinned).toBe(false);
    expect(progress.attemptStartedAt).toBeNull();
    expect(state(progress, "join")).toBe("observed");
  });

  it("空台账 ⇒ 无行、无最远阶段、无终态", () => {
    const progress = deriveSessionProgress([]);
    expect(progress.hasRows).toBe(false);
    expect(progress.furthest).toBeNull();
    expect(progress.terminal).toBeNull();
    expect(progress.stages.every((stage) => stage.state === "absent")).toBe(true);
  });
});
