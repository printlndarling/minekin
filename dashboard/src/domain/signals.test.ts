import { describe, expect, it } from "vitest";
import { ageMs, freshnessOf, gap, isKnown, known } from "./signals";

const T0 = Date.parse("2026-09-26T09:00:00.000Z");

function at(observedMs: number | null, staleAfterMs: number | null) {
  return { source: "mock" as const, sourceRef: "mock://test", observedAt: observedMs === null ? null : new Date(observedMs).toISOString(), staleAfterMs };
}

describe("signal provenance", () => {
  it("只把 known 信号当作值", () => {
    const value = known(7, at(T0, 5_000));
    expect(isKnown(value)).toBe(true);
    if (isKnown(value)) expect(value.value).toBe(7);
    const hole = gap("unknown", "无读数", at(null, null));
    expect(isKnown(hole)).toBe(false);
    if (!isKnown(hole)) expect(hole.reason).toBe("无读数");
  });

  it("新鲜度按观测时间与预算判定", () => {
    expect(freshnessOf(known(1, at(T0 - 1_000, 5_000)), T0)).toBe("fresh");
    expect(freshnessOf(known(1, at(T0 - 6_000, 5_000)), T0)).toBe("stale");
    expect(freshnessOf(gap("unavailable", "无读数", at(T0 - 9_000, 1_000)), T0)).toBe("not_applicable");
  });

  it("无时间戳的读数不会被误判为陈旧", () => {
    const sig = known("x", at(null, 1_000));
    expect(freshnessOf(sig, T0)).toBe("no_observation_time");
    expect(ageMs(null, T0)).toBeNull();
  });

  it("age 永不为负", () => {
    expect(ageMs(new Date(T0).toISOString(), T0 - 5_000)).toBe(0);
  });
});
