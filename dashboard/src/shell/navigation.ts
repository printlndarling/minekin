/**
 * The shell's navigation model.
 *
 * A page exists only when a real read backs it: the pages below map onto the three
 * frozen contract GET routes plus the three authorized writes (identity rename, config
 * persist, session stop). Nothing here reserves a slot for a feature Core cannot answer — an
 * unimplemented surface is a named row on the 数据源与缺口 page, not a tab that renders a stub.
 */

export type PageId = "overview" | "task" | "timeline" | "alerts" | "config" | "server" | "identity" | "session" | "recipes" | "data";

export interface NavItem {
  readonly id: PageId;
  readonly label: string;
  readonly hint: string;
}

export interface NavGroup {
  readonly id: string;
  readonly label: string;
  readonly items: readonly NavItem[];
}

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    id: "now",
    label: "现在",
    items: [
      { id: "overview", label: "总览", hint: "是谁、在哪个世界、走到哪一步" },
      { id: "task", label: "任务 · 目标与计划", hint: "已存目标的里程碑与目录推得的合成计划（纯读，不报实时进度）" },
      { id: "recipes", label: "配方知识 · 覆盖边界", hint: "精选目录覆盖哪些合成、各自形状与来源，并声明它不是通用合成源（纯读）" },
    ],
  },
  {
    id: "history",
    label: "过程",
    items: [
      { id: "timeline", label: "时间线", hint: "Core 与 Bridge 的台账行" },
      { id: "alerts", label: "告警", hint: "有源为空与无告警源是两件事" },
    ],
  },
  {
    id: "settings",
    label: "设置",
    items: [
      { id: "config", label: "配置 · 模型与目标", hint: "保存模型和目标，显式测试连接；密钥由进程环境提供" },
      { id: "server", label: "服务器 · 连接设置", hint: "保存地址并探测版本，使用修订检查避免覆盖他人的修改" },
      { id: "identity", label: "身份 · 改名", hint: "会话停止后修改角色名称" },
      { id: "session", label: "会话 · 控制", hint: "停止会话，释放输入并关闭本产品的客户端" },
      { id: "data", label: "数据源与缺口", hint: "每条读路的状态，以及未接入的原因" },
    ],
  },
];

export const PAGES: readonly NavItem[] = NAV_GROUPS.flatMap((group) => [...group.items]);

export const DEFAULT_PAGE: PageId = "overview";

const BY_ID = new Map<string, NavItem>(PAGES.map((page) => [page.id, page]));

export function pageLabel(id: PageId): string {
  return BY_ID.get(id)?.label ?? id;
}

export function isPageId(value: string): value is PageId {
  return BY_ID.has(value);
}

/** `#timeline` → `"timeline"`; an unknown or empty fragment falls back to the default page. */
export function pageFromHash(hash: string): PageId {
  const fragment = hash.replace(/^#/, "").trim();
  return isPageId(fragment) ? fragment : DEFAULT_PAGE;
}
