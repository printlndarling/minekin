import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Alert, AlertsEnvelope } from "../domain/model";
import { AlertsPanel } from "./AlertsPanel";

const first: Alert = { alertId: "one", severity: "critical", state: "active", component: "bridge",
  title: "连接中断", detail: "CONTROL_CHANNEL_LOST", firstSeenAt: "2026-10-02T01:00:00Z",
  lastSeenAt: null, sourceRef: "ledger://one" };
const envelope: AlertsEnvelope = { status: "known", reason: "", alerts: [first,
  { ...first, alertId: "two", title: "历史提示", severity: "info", state: "resolved" }] };

describe("alert investigation", () => {
  it("combines severity and state filters and does not turn no matches into an all-clear", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel envelope={envelope} isLoading={false} failure={null} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "严重程度" }), "critical");
    expect(screen.getByText("连接中断")).toBeInTheDocument();
    expect(screen.queryByText("历史提示")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "告警状态" }), "resolved");
    expect(screen.getByText("当前筛选无匹配告警，不代表没有告警。")).toBeInTheDocument();
    expect(screen.queryByTestId("alerts-empty")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(screen.getByRole("status")).toHaveTextContent("显示 2 / 2");
  });

  it("hides stale alerts on a failed read", () => {
    render(<AlertsPanel envelope={envelope} isLoading={false} failure={{ kind: "timeout", message: "timeout" }} />);
    expect(screen.queryByText("连接中断")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("keeps empty source distinct from absent source", () => {
    const { rerender } = render(<AlertsPanel envelope={{ ...envelope, alerts: [] }} isLoading={false} failure={null} />);
    expect(screen.getByTestId("alerts-empty")).toBeInTheDocument();
    rerender(<AlertsPanel envelope={null} isLoading={false} failure={null} />);
    expect(screen.queryByTestId("alerts-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("alerts-no-source")).toBeInTheDocument();
  });

  it("does not present untrusted items when the source reports a gap", () => {
    render(<AlertsPanel envelope={{ ...envelope, status: "unknown", reason: "no source" }} isLoading={false} failure={null} />);
    expect(screen.getByTestId("alerts-no-source")).toBeInTheDocument();
    expect(screen.queryByText("连接中断")).not.toBeInTheDocument();
  });
});
