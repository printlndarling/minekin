import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createMockAdapter } from "../adapters/mockAdapter";
import { ok, type ReadResult } from "../domain/adapter";
import type { ServerConfigInfo, SessionStartResult } from "../domain/model";
import { SessionStartPanel } from "./SessionStartPanel";

describe("受管启动", () => {
  it.each(["session-job", "server"])("%s 轮询失联即禁用缓存启动，并要求恢复后重新确认", async (read) => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.serverConfig();
    await adapter.saveServer({ revision: 0, fields: { host: "127.0.0.1", port: 25566 } });
    const originalJob = adapter.sessionJob.bind(adapter);
    const originalServer = adapter.serverConfig.bind(adapter);
    const jobRead = vi.spyOn(adapter, "sessionJob");
    const serverRead = vi.spyOn(adapter, "serverConfig");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SessionStartPanel adapter={adapter} /></QueryClientProvider>);
    const confirm = screen.getByTestId("session-start-confirm");
    await waitFor(() => expect(confirm).toBeEnabled());
    await userEvent.click(confirm);
    expect(screen.getByTestId("session-start-submit")).toBeEnabled();
    (read === "session-job" ? jobRead : serverRead).mockRejectedValue(new Error("disconnected"));
    await client.refetchQueries({ queryKey: [read, adapter.describe().id] });
    await waitFor(() => expect(screen.getByTestId("session-start-submit")).toBeDisabled());
    expect(await screen.findByRole("alert")).toHaveTextContent(read === "session-job" ? "启动状态读取失败" : "服务器设置读取失败");
    jobRead.mockImplementation(originalJob);
    serverRead.mockImplementation(originalServer);
    await client.refetchQueries({ queryKey: [read, adapter.describe().id] });
    await waitFor(() => expect(confirm).toBeEnabled());
    expect(confirm).not.toBeChecked();
  });
  it("服务器修订变化不解锁在途请求，不展示旧修订响应", async () => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    await adapter.serverConfig();
    await adapter.saveServer({ revision: 0, fields: { host: "127.0.0.1", port: 25566 } });
    let resolve!: (value: ReadResult<SessionStartResult>) => void;
    vi.spyOn(adapter, "startSession").mockImplementation(() => new Promise((done) => { resolve = done; }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SessionStartPanel adapter={adapter} /></QueryClientProvider>);
    await waitFor(() => expect(screen.getByTestId("session-start-confirm")).toBeEnabled());
    await userEvent.click(screen.getByTestId("session-start-confirm"));
    await userEvent.click(screen.getByTestId("session-start-submit"));
    const key = ["server", adapter.describe().id];
    const old = client.getQueryData<ReadResult<ServerConfigInfo>>(key)!;
    if (!old.ok) throw new Error("missing config");
    client.setQueryData(key, { ...old, value: { ...old.value, revision: 2 } });
    await waitFor(() => expect(screen.getByText(/修订 2/)).toBeInTheDocument());
    expect(screen.getByTestId("session-start-submit")).toHaveTextContent("提交中");
    expect(screen.getByTestId("session-start-confirm")).toBeDisabled();
    // Even restoring the former revision must not revive the old response.
    client.setQueryData(key, old);
    await waitFor(() => expect(screen.getByText(/修订 1/)).toBeInTheDocument());
    expect(screen.getByTestId("session-start-confirm")).toBeDisabled();
    resolve(ok({ jobId: "a".repeat(32), phase: "preparing" }, "mock", "mock://start"));
    await waitFor(() => expect(screen.getByTestId("session-start-submit")).not.toHaveTextContent("提交中"));
    expect(screen.queryByTestId("session-start-result")).toBeNull();
    expect(screen.getByTestId("session-start-confirm")).not.toBeChecked();
  });
  it.each(["CLIENT_EXITED", "BRIDGE_LOST"])("显示失败 %s 和真实退出码，读取失败记录不重新启动", async (outcome) => {
    const adapter = createMockAdapter("healthy_run_07", 0);
    vi.spyOn(adapter, "sessionJob").mockResolvedValue(ok({ job: {
      jobId: "a".repeat(32), phase: "failed", reason: outcome, fields: { host: "127.0.0.1", port: 25566 },
      serverRevision: 1, installed: 0, total: 3639, outcome, inputReleaseFailed: false, clientExitCode: -9,
    } }, "mock", "mock://session/job"));
    const start = vi.spyOn(adapter, "startSession");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SessionStartPanel adapter={adapter} /></QueryClientProvider>);
    const status = await screen.findByTestId("session-job-status");
    expect(status).toHaveTextContent("failed");
    expect(status).toHaveTextContent("客户端退出码 -9");
    if (outcome === "BRIDGE_LOST") expect(status).toHaveTextContent("Bridge 释放确认不可用");
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
