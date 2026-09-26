import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SignalValue } from "./SignalValue";
import { gap, known } from "../domain/signals";
import { KIN_STATE_LABELS } from "../domain/labels";
import type { KinRuntimeState } from "../domain/model";

const T0 = Date.parse("2026-09-26T09:00:00.000Z");
const ctx = (observedMs: number | null, staleAfterMs: number | null) => ({
  source: "mock" as const,
  sourceRef: "mock://component-test",
  observedAt: observedMs === null ? null : new Date(observedMs).toISOString(),
  staleAfterMs,
});

describe("SignalValue", () => {
  it("已知读数显示格式化值与新鲜度", () => {
    render(
      <SignalValue
        label="runtime_state"
        signal={known<KinRuntimeState>("running", ctx(T0 - 1_000, 15_000))}
        nowMs={T0}
        format={(v) => KIN_STATE_LABELS[v]}
      />,
    );
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("实时")).toBeInTheDocument();
  });

  it("陈旧读数保留值并标注陈旧", () => {
    render(<SignalValue label="会话" signal={known(42, ctx(T0 - 60_000, 15_000))} nowMs={T0} format={(v) => String(v)} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getAllByText("陈旧").length).toBeGreaterThan(0);
    expect(screen.getByText("1 分前")).toBeInTheDocument();
  });

  it("缺口显示状态与原因，绝不显示值", () => {
    const { container } = render(
      <SignalValue label="世界上下文" signal={gap("unknown", "失联后不重放旧 world context。", ctx(null, null))} nowMs={T0} format={() => "不该出现"} />,
    );
    expect(screen.getAllByText("未知").length).toBeGreaterThan(0);
    expect(screen.getByText("失联后不重放旧 world context。")).toBeInTheDocument();
    expect(container.textContent).not.toContain("不该出现");
  });

  it("未接入与无权限有各自文案", () => {
    const { rerender } = render(
      <SignalValue label="Live View" signal={gap("not_wired", "没有帧源。", ctx(null, null))} nowMs={T0} format={() => ""} />,
    );
    expect(screen.getAllByText("未接入").length).toBeGreaterThan(0);
    rerender(
      <SignalValue label="Live View" signal={gap("permission_denied", "需要观战授权。", ctx(null, null))} nowMs={T0} format={() => ""} />,
    );
    expect(screen.getAllByText("无权限").length).toBeGreaterThan(0);
  });
});
