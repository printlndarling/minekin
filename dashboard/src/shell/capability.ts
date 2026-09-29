/**
 * What the back office can actually answer, as a list rather than as a promise.
 *
 * The shell used to carry a tab per feature the roadmap named, which meant an operator
 * clicking through saw pages that rendered nothing and had to read a paragraph to learn
 * why. This registry is the honest version of the same fact: a surface is `live` only when
 * a route behind it returns real readings, `gap` when Core or the Bridge has no authoritative
 * source yet, and `reserved` when the capability exists but this phase deliberately does not
 * open it. A new page added to the shell has to appear here with the route it reads, so a
 * placeholder cannot re-enter as a tab.
 */

export type CapabilityState = "live" | "gap" | "reserved";

export interface CapabilityRow {
  readonly surface: string;
  readonly state: CapabilityState;
  /** The route or process that answers it, or the missing source that would have to. */
  readonly source: string;
  readonly detail: string;
}

export const CAPABILITY_STATE_LABELS: Record<CapabilityState, string> = {
  live: "已接入",
  gap: "未接入",
  reserved: "暂不开放",
};

export const CAPABILITY_ROWS: readonly CapabilityRow[] = [
  {
    surface: "Kin 运行状态 / 会话 / 版本 / 证据引用",
    state: "live",
    source: "GET /api/v1/dashboard/snapshot",
    detail: "冻结契约的三条只读 GET 之一；每个字段带自己的 provenance，读不到就显示缺口而不是补默认值。",
  },
  {
    surface: "事件时间线（含会话阶段与输入拒止原因）",
    state: "live",
    source: "GET /api/v1/dashboard/timeline",
    detail: "阶段、租约授予/释放与拒止 reason 全部从台账行读出，前端不推断。",
  },
  {
    surface: "告警信封",
    state: "live",
    source: "GET /api/v1/dashboard/alerts",
    detail: "「有源为空」与「无告警源」是两种呈现；当前 Core 没有告警源，所以读到的是后者。",
  },
  {
    surface: "身份读数与停机确认式改名",
    state: "live",
    source: "GET/POST /api/v1/dashboard/identity",
    detail: "唯一被授权的写面：只在会话停止时、需显式确认、按身份修订号做 compare-and-swap；改名会改变离线 UUID，不迁移服务端物品。",
  },
  {
    surface: "游戏画面（Live View）",
    state: "gap",
    source: "缺帧源进程与媒体中继",
    detail: "没有 framebuffer 采集、媒体鉴权与画面 provenance 之前不渲染任何画面，也不放示例视频。",
  },
  {
    surface: "心智 / 目标 / 关系 / 模型成本",
    state: "gap",
    source: "缺 PlayerMind 与 Tool Gateway 记账",
    detail: "Core 尚无权威的人格、目标与成本读数；没有真源就不显示人格摘要或花费数字。",
  },
  {
    surface: "事件游标与增量订阅",
    state: "gap",
    source: "契约只冻结轮询",
    detail: "2026-09-28 冻结契约没有 SSE/WebSocket，面板以 5 秒轮询为准，断连表现为连续未落的读取。",
  },
  {
    surface: "通用写控制端点（启停、移动、注入输入）",
    state: "reserved",
    source: "本产品阶段不开放",
    detail: "面板不启动、不暂停、不持有任何凭据；这一条是边界而不是缺口，需要另行授权才会改变。",
  },
];
