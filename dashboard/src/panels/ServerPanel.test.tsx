import { act, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createMockAdapter } from "../adapters/mockAdapter";
import { ok } from "../domain/adapter";
import { ServerPanel } from "./ServerPanel";

function setup() {
  const adapter = createMockAdapter("healthy_run_07", 0);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ServerPanel adapter={adapter} /></QueryClientProvider>);
  return { adapter, client };
}

describe("服务器设置", () => {
  it("未保存及草稿不能探测，保存后模拟数据明确拒绝真实探测", async () => {
    const { adapter } = setup();
    const probe = vi.spyOn(adapter, "probeServer");
    await waitFor(() => expect(screen.getByTestId("server-save")).toBeEnabled());
    expect(screen.getByTestId("server-probe")).toBeDisabled();
    await userEvent.click(screen.getByTestId("server-save"));
    await waitFor(() => expect(screen.getByTestId("server-probe")).toBeEnabled());
    expect(probe).not.toHaveBeenCalled();
    await userEvent.click(screen.getByTestId("server-probe"));
    expect(await screen.findByTestId("server-probe-result")).toHaveTextContent("模拟数据不能探测真实 Minecraft 服务器");
    expect(probe).toHaveBeenCalledTimes(1);
    await userEvent.type(screen.getByTestId("server-port"), "7");
    expect(screen.getByTestId("server-probe")).toBeDisabled();
    expect(screen.queryByTestId("server-probe-result")).toBeNull();
  });

  it("轮询外部修订保留草稿并拒绝覆盖，放弃草稿恢复最新配置", async () => {
    const { adapter, client } = setup();
    await waitFor(() => expect(screen.getByTestId("server-save")).toBeEnabled());
    await userEvent.clear(screen.getByTestId("server-port"));
    await userEvent.type(screen.getByTestId("server-port"), "25567");
    const current = await adapter.serverConfig();
    if (!current.ok) throw new Error("mock read failed");
    act(() => client.setQueryData(["server", adapter.describe().id], ok({ ...current.value,
      revision: 2, fields: { host: "127.0.0.1", port: 25568 } }, "mock", "test")));
    expect(screen.getByTestId("server-port")).toHaveValue("25567");
    await waitFor(() => expect(screen.getByTestId("server-save")).toBeDisabled());
    expect(screen.getByTestId("server-probe")).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "放弃服务器草稿" }));
    await waitFor(() => expect(screen.getByTestId("server-port")).toHaveValue("25568"));
  });

  it("远程地址保存后仍需显式许可，编辑清除许可", async () => {
    setup();
    await waitFor(() => expect(screen.getByTestId("server-save")).toBeEnabled());
    await userEvent.clear(screen.getByTestId("server-host"));
    await userEvent.type(screen.getByTestId("server-host"), "192.0.2.1");
    await userEvent.click(screen.getByTestId("server-save"));
    await waitFor(() => expect(screen.getByRole("checkbox")).toBeEnabled());
    expect(screen.getByTestId("server-probe")).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByTestId("server-probe")).toBeEnabled();
    await userEvent.type(screen.getByTestId("server-port"), "7");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByTestId("server-probe")).toBeDisabled();
  });
});
