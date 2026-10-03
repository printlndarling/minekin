import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createMockAdapter } from "../adapters/mockAdapter";
import { SessionStartPanel } from "./SessionStartPanel";

describe("受管启动", () => {
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
