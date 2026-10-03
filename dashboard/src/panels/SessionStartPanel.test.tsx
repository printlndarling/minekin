import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createMockAdapter } from "../adapters/mockAdapter";
import { ok } from "../domain/adapter";
import { SessionStartPanel } from "./SessionStartPanel";

describe("受管启动", () => {
  it("显示失败和真实退出码，读取失败记录不重新启动", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    vi.spyOn(adapter, "sessionJob").mockResolvedValue(ok({ job: {
      jobId: "a".repeat(32), phase: "failed", reason: "CLIENT_EXITED", fields: { host: "127.0.0.1", port: 25566 },
      serverRevision: 1, installed: 0, total: 3639, outcome: "CLIENT_EXITED", inputReleaseFailed: false, clientExitCode: -9,
    } }, "mock", "mock://session/job"));
    const start = vi.spyOn(adapter, "startSession");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SessionStartPanel adapter={adapter} /></QueryClientProvider>);
    const status = await screen.findByTestId("session-job-status");
    expect(status).toHaveTextContent("failed");
    expect(status).toHaveTextContent("客户端退出码 -9");
    expect(start).not.toHaveBeenCalled();
  });
  it("只在显式确认后发出有界请求，模拟适配器拒绝真实启动", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.serverConfig();
    await adapter.saveServer({ revision: 0, fields: { host: "127.0.0.1", port: 25566 } });
    const start = vi.spyOn(adapter, "startSession");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SessionStartPanel adapter={adapter} /></QueryClientProvider>);
    await waitFor(() => expect(screen.getByTestId("session-start-confirm")).toBeEnabled());
    expect(start).not.toHaveBeenCalled();
    expect(screen.getByTestId("session-start-submit")).toBeDisabled();
    await userEvent.click(screen.getByTestId("session-start-confirm"));
    await userEvent.click(screen.getByTestId("session-start-submit"));
    expect(await screen.findByTestId("session-start-result")).toHaveTextContent("模拟数据不能启动真实 Minecraft 客户端");
    expect(start).toHaveBeenCalledTimes(1);
    expect(start).toHaveBeenCalledWith({ confirm: true, serverRevision: 1, allowRemote: false,
      maxDownloadBytes: 0, durationSeconds: 300, autonomousSteps: 0 });
  });
});
