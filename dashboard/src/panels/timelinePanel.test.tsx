import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../domain/model";
import { TimelinePanel } from "./TimelinePanel";

const items: readonly TimelineEvent[] = [
  { eventId: "event-1", kind: "input", at: "2026-10-02T01:00:00Z", monotonicMs: 1,
    generation: 3, sequence: 8, title: "use_target", detail: "GUI_CONFLICT", outcome: "rejected", sourceRef: "ledger://one" },
  { eventId: "event-2", kind: "observation", at: "2026-10-02T01:00:01Z", monotonicMs: 2,
    generation: 3, sequence: 9, title: "背包更新", detail: null, outcome: "applied", sourceRef: "ledger://two" },
];

describe("timeline investigation", () => {
  it("searches case-insensitive literal terms across title and reason, and clears all filters", async () => {
    const user = userEvent.setup();
    render(<TimelinePanel items={items} isLoading={false} failure={null} />);
    await user.type(screen.getByRole("searchbox", { name: "搜索事件" }), "USE gui_conflict");
    expect(screen.getByText("use_target")).toBeInTheDocument();
    expect(screen.queryByText("背包更新")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("显示 1 / 2");
    await user.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(screen.getByText("背包更新")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "清除筛选" })).toBeDisabled();
  });

  it("combines result and kind filters without changing the source events", async () => {
    const user = userEvent.setup();
    render(<TimelinePanel items={items} isLoading={false} failure={null} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "事件结果" }), "rejected");
    expect(screen.getByText("use_target")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "观察" }));
    expect(screen.getByText("当前无匹配事件。")).toBeInTheDocument();
    expect(items).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(screen.getByRole("status")).toHaveTextContent("显示 2 / 2");
  });

  it("never renders cached events while reporting a failed read", () => {
    render(<TimelinePanel items={items} isLoading={false}
      failure={{ kind: "disconnected", message: "offline" }} />);
    expect(screen.queryByText("use_target")).not.toBeInTheDocument();
    expect(screen.queryByText("背包更新")).not.toBeInTheDocument();
  });

  it("can search a source reference and treats regex symbols literally", async () => {
    const user = userEvent.setup();
    render(<TimelinePanel items={items} isLoading={false} failure={null} />);
    const search = screen.getByRole("searchbox", { name: "搜索事件" });
    await user.type(search, "ledger://two");
    expect(screen.getByText("背包更新")).toBeInTheDocument();
    await user.clear(search);
    await user.type(search, ".*");
    expect(screen.getByText("当前无匹配事件。")).toBeInTheDocument();
  });
});
