import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { buildMockIdentity } from "../fixtures/mockFixtures";
import { decodeIdentityPayload } from "../adapters/gatewayAdapter";
import { SavedPersonaPanel } from "./SavedPersonaPanel";

function wire() {
  return { ...buildMockIdentity("fields_unknown", 0), persona: { value: {
    manifest_sha256: "a".repeat(64), schema_version: 1, algorithm: "persona-blake2b-v1",
    traits: { social_initiative: 3, cooperation: 5, orderliness: 1, curiosity: 9, risk_tolerance: 2 },
    value_priority: ["exploration", "autonomy", "fairness", "creation", "belonging", "resource_security"],
  } } };
}

describe("已保存人格的只读查看", () => {
  it("从身份解码器展示真实字段及限制，不提供重抽操作", () => {
    const read = decodeIdentityPayload(wire());
    if (!read.ok) throw new Error(read.issues.join(";"));
    render(<SavedPersonaPanel persona={read.identity.persona} />);
    const panel = screen.getByTestId("panel-saved-persona");
    expect(panel).toHaveTextContent("好奇心");
    expect(panel).toHaveTextContent("9 / 9");
    expect(screen.getByRole("list", { name: "价值优先顺序" }).firstChild).toHaveTextContent("探索");
    expect(panel).toHaveTextContent("不是技能熟练度或成功概率");
    expect(panel).toHaveTextContent("不证明模型已表现出相应行为");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("旧接口和缺失人格显示具名原因，不捏造中间分数", () => {
    const old = decodeIdentityPayload(buildMockIdentity("fields_unknown", 0));
    if (!old.ok) throw new Error(old.issues.join(";"));
    const view = render(<SavedPersonaPanel persona={old.identity.persona} />);
    expect(screen.getByTestId("persona-gap")).toHaveTextContent("旧身份接口");
    expect(screen.queryByText("5 / 9")).toBeNull();
    view.rerender(<SavedPersonaPanel persona={{ gap: { status: "unavailable", reason: "PERSONA_NOT_INITIALISED" } }} />);
    expect(screen.getByTestId("persona-gap")).toHaveTextContent("PERSONA_NOT_INITIALISED");
  });

  it("拒绝越界倾向、重复优先级和原始种子字段", () => {
    const trait = wire();
    trait.persona.value.traits.curiosity = 10;
    expect(decodeIdentityPayload(trait).ok).toBe(false);
    const priority = wire();
    priority.persona.value.value_priority[0] = "autonomy";
    expect(decodeIdentityPayload(priority).ok).toBe(false);
    const seed = wire();
    Object.assign(seed.persona.value, { persona_seed: "secret-canary" });
    expect(decodeIdentityPayload(seed).ok).toBe(false);
  });
});
