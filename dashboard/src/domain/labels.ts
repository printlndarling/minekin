import type { AlertComponent, AlertSeverity, AlertState, KinRuntimeState, LinkState, SessionMode, TimelineKind, TimelineOutcome } from "./model";
import type { Freshness, SignalStatus } from "./signals";

export const KIN_STATE_LABELS: Record<KinRuntimeState, string> = {
  idle: "空闲",
  running: "运行中",
  paused: "已暂停",
  recovering: "恢复中",
  unresolved: "未定（无法判定）",
};

export const LINK_STATE_LABELS: Record<LinkState, string> = {
  connected: "已连接",
  connecting: "连接中",
  disconnected: "已失联",
};

export const SESSION_MODE_LABELS: Record<SessionMode, string> = {
  A_companion: "A 陪玩",
  B_standalone: "B 独立",
};

export const SIGNAL_STATUS_LABELS: Record<SignalStatus, string> = {
  known: "已知",
  unknown: "未知",
  unavailable: "不可用",
  not_wired: "未接入",
  permission_denied: "无权限",
};

export const FRESHNESS_LABELS: Record<Freshness, string> = {
  fresh: "实时",
  stale: "陈旧",
  no_observation_time: "无观测时间",
  not_applicable: "—",
};

export const TIMELINE_KIND_LABELS: Record<TimelineKind, string> = {
  observation: "观察",
  decision: "决定",
  intent: "意图",
  input: "输入",
  server_feedback: "服务器反馈",
  reflex: "反射",
  fault: "故障",
  session: "会话",
};

export const TIMELINE_OUTCOME_LABELS: Record<TimelineOutcome, string> = {
  applied: "已执行",
  rejected: "被拒绝",
  expired: "已过期",
  released: "已释放",
  unknown: "结果未知",
};

export const ALERT_SEVERITY_LABELS: Record<AlertSeverity, string> = {
  info: "信息",
  warning: "告警",
  critical: "严重",
};

export const ALERT_STATE_LABELS: Record<AlertState, string> = {
  active: "活动中",
  resolved: "已恢复",
  acknowledged: "已确认",
};

export const ALERT_COMPONENT_LABELS: Record<AlertComponent, string> = {
  runtime: "Runtime",
  bridge: "Bridge",
  launcher: "Launcher",
  gateway: "Gateway",
  media: "媒体",
  database: "数据库",
};

export const TIMELINE_KIND_ORDER: readonly TimelineKind[] = [
  "observation",
  "decision",
  "intent",
  "input",
  "server_feedback",
  "reflex",
  "fault",
  "session",
];
