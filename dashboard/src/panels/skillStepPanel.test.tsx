import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { decodeSnapshotPayload } from "../adapters/gatewayAdapter";
import { buildMockBundle } from "../fixtures/mockFixtures";
import { REAL_JOINED_RUN_SNAPSHOT_WIRE } from "../test/realGatewayWire";
import type { KinSnapshot } from "../domain/model";
import { SkillStepPanel } from "./SkillStepPanel";

const NOW = Date.parse("2026-09-26T12:00:00.000Z");

/** The panel only ever renders decoded bytes — the same path both adapters use. */
function snapshotFrom(wire: Record<string, unknown>, source: "mock" | "gateway"): KinSnapshot {
  const decoded = decodeSnapshotPayload(wire, source);
  if (!decoded.ok) throw new Error(`解码失败：${decoded.issues.join(" | ")}`);
  return decoded.snapshot;
}

describe("技能步面板：known 组逐成员、缺组具名、绝不折叠成 0 步", () => {
  it("心智输入来源原样展示，但不声称模型采纳或历史已松键", () => {
    const wire = buildMockBundle("healthy_run_07", NOW).snapshot;
    const group = wire.skillSteps as Record<string, unknown>;
    const value = group.value as Record<string, unknown>;
    value.personaContext = { value: "manifest_sha256=abc; curiosity=7" };
    value.sessionHistory = { value: "event_id=old-event; last_recorded_phase=STOPPED; input_release=unknown" };
    render(<SkillStepPanel snapshot={snapshotFrom(wire, "gateway")} />);
    expect(screen.getByTestId("skill-step-人格输入来源")).toHaveTextContent("curiosity=7");
    expect(screen.getByTestId("skill-step-历史记忆输入")).toHaveTextContent("input_release=unknown");
    expect(screen.getByTestId("panel-skill-steps")).toHaveTextContent("不证明模型采纳或人格生效");
  });

  it("旧成员缺席可兼容，存在但畸形的来源拒绝解码", () => {
    const wire = buildMockBundle("healthy_run_07", NOW).snapshot;
    const group = wire.skillSteps as Record<string, unknown>;
    const value = group.value as Record<string, unknown>;
    delete value.personaContext;
    delete value.sessionHistory;
    render(<SkillStepPanel snapshot={snapshotFrom(wire, "gateway")} />);
    expect(screen.getByTestId("skill-step-人格输入来源")).toHaveTextContent("旧快照未携带");
    expect(screen.getByTestId("skill-step-历史记忆输入")).toHaveTextContent("旧快照未携带");
    value.personaContext = { value: null };
    expect(decodeSnapshotPayload(wire, "gateway").ok).toBe(false);
    delete value.personaContext;
    value.sessionHistory = { gap: { status: "unknown", reason: "" } };
    expect(decodeSnapshotPayload(wire, "gateway").ok).toBe(false);
  });

  it("known 组：最近一步的值原样上屏，按构造为空的成员显示带 Core 原文的缺口", () => {
    const snapshot = snapshotFrom(buildMockBundle("healthy_run_07", NOW).snapshot, "mock");
    render(<SkillStepPanel snapshot={snapshot} />);
    const panel = screen.getByTestId("panel-skill-steps");
    expect(panel).toHaveTextContent("先挖到木头，再合成木镐");
    expect(panel).toHaveTextContent("craft");
    expect(panel).toHaveTextContent("已确认 · CONFIRMED");
    expect(panel).toHaveTextContent("4 步");
    expect(panel).toHaveTextContent("DECISION_FROM_MODEL");
    // 空而不缺：CONFIRMED 步的 reason/归因/拒止各有一句具名理由。
    expect(panel).toHaveTextContent("没有失败原因可报");
    expect(panel).toHaveTextContent("没有失败可归因");
    expect(panel).toHaveTextContent("没有拒止可报");
    // 花费与配置永远只是具名缺口，不出现数字。
    expect(panel).toHaveTextContent("model_calls / model_spent_micro / model_cap_refusals");
    expect(panel).toHaveTextContent("model_enabled");
    expect(panel.textContent).not.toMatch(/花费[:：]?\s*\d/);
    // 行为参数是 run document 里唯一被解析的成员：已封 bundle 的脱敏参数原样上屏。
    const parameters = screen.getByTestId("skill-step-行为参数");
    expect(parameters).toHaveTextContent("target_item=minecraft:wooden_pickaxe");
    expect(parameters).toHaveTextContent("quantity=1");
  });

  it("组级缺口（没有技能步行的 run）：一句具名理由，而不是零值事实", () => {
    const snapshot = snapshotFrom(buildMockBundle("fields_unknown", NOW).snapshot, "mock");
    render(<SkillStepPanel snapshot={snapshot} />);
    const gap = screen.getByTestId("skill-steps-gap");
    expect(gap).toHaveTextContent("台账里没有技能步行");
    expect(gap).toHaveTextContent("不把它折成「0 步」");
    // 组级缺口时不渲染任何成员行：没有「最近一步」可报，也没有花费行可误读。
    expect(screen.queryByText("调用花费")).toBeNull();
    expect(screen.queryByText("自主目标")).toBeNull();
  });

  it("旧 Gateway 字节（整个组缺席）：面板渲染合成的 not_wired 缺口而不是崩溃", () => {
    const snapshot = snapshotFrom(REAL_JOINED_RUN_SNAPSHOT_WIRE, "gateway");
    render(<SkillStepPanel snapshot={snapshot} />);
    const gap = screen.getByTestId("skill-steps-gap");
    expect(gap).toHaveTextContent("未接入");
    expect(gap).toHaveTextContent("响应字节里没有 skillSteps 组");
  });

  it("结果未知步：UNKNOWN 原样上屏，不误标为已确认或失败", () => {
    const wire = buildMockBundle("healthy_run_07", NOW).snapshot;
    const group = wire.skillSteps as Record<string, unknown>;
    const value = { ...(group.value as Record<string, unknown>) };
    value.result = { value: "UNKNOWN" };
    value.reason = { value: "NO_CONFIRMING_OBSERVATION" };
    group.value = value;
    const snapshot = snapshotFrom(wire, "mock");
    render(<SkillStepPanel snapshot={snapshot} />);
    const panel = screen.getByTestId("panel-skill-steps");
    expect(panel).toHaveTextContent("结果未知 · UNKNOWN");
    expect(panel).toHaveTextContent("NO_CONFIRMING_OBSERVATION");
    expect(panel).not.toHaveTextContent("已确认 · CONFIRMED");
  });

  it("没有中文注释的 token（真实自主 run 的 STARTED）：只上屏一次，不折进三种 verdict 也不重复一遍", () => {
    const wire = buildMockBundle("healthy_run_07", NOW).snapshot;
    const group = wire.skillSteps as Record<string, unknown>;
    const value = { ...(group.value as Record<string, unknown>) };
    value.result = { value: "STARTED" };
    value.reason = { value: "AIM_IN_PROGRESS" };
    value.attribution = { value: "ACTION_NOT_EFFECTIVE" };
    group.value = value;
    render(<SkillStepPanel snapshot={snapshotFrom(wire, "mock")} />);
    // 正对照：这一行确实渲染了，token 原样在屏上，而且只出现一次。
    const row = screen.getByTestId("skill-step-实际结果");
    expect(row).toHaveTextContent("STARTED");
    expect((row.textContent ?? "").split("STARTED").length - 1).toBe(1);
    expect(row).not.toHaveTextContent("STARTED · STARTED");
    const panel = screen.getByTestId("panel-skill-steps");
    expect(panel).toHaveTextContent("AIM_IN_PROGRESS");
    expect(panel).toHaveTextContent("ACTION_NOT_EFFECTIVE");
    // 这一步不再是被注释过的那三种 verdict 之一：去重不能顺手给它套上一个中文标签。
    expect(panel).not.toHaveTextContent("已确认 · CONFIRMED");
    expect(panel).not.toHaveTextContent("结果未知 · UNKNOWN");
    expect(panel).not.toHaveTextContent("失败 · FAILED");
  });
});
