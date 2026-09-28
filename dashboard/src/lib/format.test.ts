import { describe, expect, it } from "vitest";
import { formatSpan } from "./format";

describe("formatSpan", () => {
  it("秒级窗口按秒说，不给时间戳", () => {
    expect(formatSpan(0)).toBe("0 秒");
    expect(formatSpan(-5_000)).toBe("0 秒");
    expect(formatSpan(15_400)).toBe("15 秒");
    expect(formatSpan(59_999)).toBe("59 秒");
  });

  it("过一分钟换成「分 + 秒」，过一小时换成「小时 + 分」", () => {
    expect(formatSpan(60_000)).toBe("1 分 0 秒");
    expect(formatSpan(95_000)).toBe("1 分 35 秒");
    expect(formatSpan(3_600_000)).toBe("1 小时 0 分");
    expect(formatSpan(7_320_000)).toBe("2 小时 2 分");
  });
});
