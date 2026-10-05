import type { SessionJob } from "../domain/model";
import styles from "./sessionJob.module.css";

const PHASES: Readonly<Record<string, { label: string; explanation: string }>> = {
  preparing: { label: "准备客户端", explanation: "正在核对或取得版本所需文件，尚未证明入服。" },
  supervising: { label: "后台监督中", explanation: "准备已返回，后台正在监督客户端。是否入服、可操作仍以世界与会话读数为准。" },
  stopping: { label: "正在收尾", explanation: "已收到停止请求，等待客户端和输入收尾确认，请勿重复启动。" },
  ended: { label: "任务已结束", explanation: "后台任务已收尾；这不代表目标达成或所有按键释放均已确认。" },
  failed: { label: "任务失败", explanation: "请先核对原因与进程状态，再显式重试；页面不会自动重连。" },
  interrupted: { label: "监督已中断", explanation: "旧任务的监督进程不在运行。客户端可能仍在，需要核对会话状态；不会自动接管或重启。" },
};

const POLICY_SOURCE_LABELS: Readonly<Record<string, string>> = {
  environment: "环境（含 env 文件，优先）",
  config: "保存配置",
  default: "默认",
};

export function SessionJobProgress({ job }: { readonly job: SessionJob }) {
  const phase = PHASES[job.phase] ?? { label: "任务状态未知", explanation: "尚不认识此阶段，不推断客户端可操作。" };
  const countsValid = Number.isSafeInteger(job.installed) && Number.isSafeInteger(job.total) &&
    job.installed >= 0 && job.total > 0 && job.installed <= job.total;
  const progressKnown = job.phase === "preparing" && countsValid;
  const cacheKnown = countsValid && (job.phase === "supervising" ||
    (["ended", "failed"].includes(job.phase) && job.outcome !== null));
  return <section className={styles.card} aria-label="后台任务进度" data-testid="session-job-status">
    <h3 className={styles.heading} aria-live="polite">{phase.label}</h3>
    <p>{phase.explanation}</p>
    <p className={styles.target}>{job.fields.host}:{job.fields.port} · 配置修订 {job.serverRevision}</p>
    {job.phase === "preparing" ? <>
      <label className={styles.progressLabel}>
        {progressKnown ? `文件核对与准备 ${job.installed} / ${job.total}` : "等待文件清单与准备读数"}
        <progress aria-label="客户端文件准备" max={progressKnown ? job.total : 1}
          value={progressKnown ? job.installed : undefined} />
      </label>
      <p className={styles.note}>此进度按文件条数计，不是下载字节或游戏进入进度；包含缓存核对。</p>
    </> : cacheKnown ? <p>新取得文件 {job.installed} · 缓存复用 {job.total - job.installed} · 总计 {job.total}。
      文件准备成功不等于入服成功。</p> : null}
    <p className={styles.note} data-testid="session-job-decision-policy">
      {job.decisionPolicy === null
        ? "本次启动的决策模式未记录（旧作业记录没有这个字段，不回填默认值）。"
        : `本次启动决策模式：${job.decisionPolicy}（来源：${
            job.decisionPolicySource === null
              ? "未记录"
              : POLICY_SOURCE_LABELS[job.decisionPolicySource] ?? job.decisionPolicySource
          }）。`}
    </p>
    <p className={styles.note} data-testid="session-job-policy-note">
      该读数在本次受管启动时捕获：保存配置只是下一次启动的输入，启动时进程环境同名变量优先；之后修改保存值不会改写本作业记录。旧作业没有该字段时显示未记录，不推断。
    </p>
    {job.reason || job.outcome ? <p>收尾/原因：{job.reason || job.outcome}</p> : null}
    {job.clientExitCode !== null && job.clientExitCode !== undefined ? <p>客户端退出码 {job.clientExitCode}</p> : null}
    {job.inputReleaseFailed === true ? <p className={styles.warning} role="alert">按键释放未确认，请核对会话和客户端收尾。</p>
      : job.outcome === "BRIDGE_LOST" ? <p className={styles.warning}>连接已丢失，Bridge 释放确认不可用。</p>
      : <p className={styles.note}>按键是否释放请查看输入与会话的独立读数，本任务不补造确认。</p>}
    <details><summary>任务诊断引用</summary>
      <p className={styles.reference}>job={job.jobId} · phase={job.phase}</p>
    </details>
  </section>;
}
