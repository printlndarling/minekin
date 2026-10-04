import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import type { SessionJob } from "../domain/model";
import { SessionJobProgress } from "./SessionJobProgress";

const job: SessionJob = { jobId: "a".repeat(32), phase: "preparing", reason: "",
  fields: { host: "127.0.0.1", port: 25565 }, serverRevision: 1, installed: 5, total: 10,
  outcome: null, inputReleaseFailed: null };

describe("任务进度只表达已有读数", () => {
  it("准备条数包含缓存核对，不称为下载百分比或入服完成", () => {
    render(<SessionJobProgress job={job} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "5");
    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "10");
    expect(screen.getByText(/包含缓存核对/)).toBeInTheDocument();
    expect(screen.queryByText(/缓存复用 5/)).toBeNull();
  });
  it.each([0, -1, 4])("总数 %s 不够支持进度时保持未知，不补造100%%", (total) => {
    render(<SessionJobProgress job={{ ...job, total }} />);
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("value");
    expect(screen.getByText("等待文件清单与准备读数")).toBeInTheDocument();
  });
  it("监督中从新下载数量解释缓存，不再画准备百分比", () => {
    render(<SessionJobProgress job={{ ...job, phase: "supervising", installed: 0 }} />);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.getByText(/新取得文件 0 · 缓存复用 10/)).toBeInTheDocument();
    expect(screen.getByText(/是否入服、可操作仍以/)).toBeInTheDocument();
  });
  it("失败计数可能是中间进度，不冒充完整缓存清单", () => {
    render(<SessionJobProgress job={{ ...job, phase: "failed", reason: "CLIENT_EXITED", clientExitCode: -9 }} />);
    expect(screen.queryByText(/缓存复用/)).toBeNull();
    expect(screen.getByText(/客户端退出码 -9/)).toBeInTheDocument();
  });
  it("准备期间取消并结束时不把处理条数改称新下载或缓存命中", () => {
    render(<SessionJobProgress job={{ ...job, phase: "ended", reason: "START_CANCELLED" }} />);
    expect(screen.queryByText(/缓存复用/)).toBeNull();
    expect(screen.getByText(/START_CANCELLED/)).toBeInTheDocument();
  });
  it("监督中断不意味着客户端已消失，释放失败仍显示告警", () => {
    render(<SessionJobProgress job={{ ...job, phase: "interrupted", inputReleaseFailed: true }} />);
    expect(screen.getByText(/客户端可能仍在/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("按键释放未确认");
  });
});
