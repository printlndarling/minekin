import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { gap, known } from "../domain/signals";
import { PlayerVitalsPanel } from "./PlayerVitalsPanel";

const NOW = Date.parse("2026-10-04T00:00:00Z");
const context = {
  source: "gateway" as const, sourceRef: "core://status/kin/selfState",
  observedAt: new Date(NOW - 1000).toISOString(), staleAfterMs: 15_000,
};

describe("角色身体只显示新鲜的当前仪表", () => {
  it("新鲜 HUD 显示真实饱食度、来源和时间，不假定生命上限", () => {
    render(<PlayerVitalsPanel signal={known({ health: 40.5, food: 7 }, context)} nowMs={NOW} />);
    expect(screen.getByRole("meter", { name: "饱食度" })).toHaveAttribute("value", "7");
    expect(screen.getByText("40.5")).toBeInTheDocument();
    expect(screen.getByText("最大生命未知")).toBeInTheDocument();
    expect(screen.getByText(context.sourceRef)).toBeInTheDocument();
    expect(screen.getByText(/网关读数 · 采样于/)).toBeInTheDocument();
  });

  it("过期后撤下仪表，旧值明确标为历史", () => {
    const signal = known({ health: 17.5, food: 10 }, context);
    const { rerender } = render(<PlayerVitalsPanel signal={signal} nowMs={NOW} />);
    expect(screen.getByRole("meter")).toBeInTheDocument();
    rerender(<PlayerVitalsPanel signal={signal} nowMs={NOW + 30_000} />);
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("历史读数 · 生命 17.5 · 饥饿 10")).toBeInTheDocument();
    expect(screen.getByText(/等待新鲜观察/)).toBeInTheDocument();
  });

  it("缺口保留原因，不补满血满饱默认值", () => {
    render(<PlayerVitalsPanel signal={gap("unavailable", "客户端已停止", context)} nowMs={NOW} />);
    expect(screen.getByText("客户端已停止")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.queryByText("20 / 20")).not.toBeInTheDocument();
  });

  it("无采样时间不充当当前仪表，模拟来源保留标记", () => {
    render(<PlayerVitalsPanel signal={known({ health: 20, food: 20 }, {
      ...context, source: "mock", observedAt: null,
    })} nowMs={NOW} />);
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText(/模拟读数 · 采样于/)).toBeInTheDocument();
  });

  it("模拟来源即使经网关传输也不标成真实读数", () => {
    render(<PlayerVitalsPanel signal={known({ health: 20, food: 20 }, {
      ...context, sourceRef: "mock://scenario/healthy/selfState",
    })} nowMs={NOW} />);
    expect(screen.getByText(/模拟读数 · 采样于/)).toBeInTheDocument();
    expect(screen.queryByText(/网关读数 · 采样于/)).not.toBeInTheDocument();
  });
});
