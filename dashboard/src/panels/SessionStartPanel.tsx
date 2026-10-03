import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { KinReadAdapter } from "../domain/adapter";
import type { SessionStartRequest } from "../domain/model";
import { Panel } from "../components/Panel";
import { useServerRead } from "./ServerPanel";
import styles from "./config.module.css";

export function SessionStartPanel({ adapter }: { readonly adapter: KinReadAdapter }) {
  const server = useServerRead(adapter).config;
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["session-job", adapter.describe().id],
    queryFn: ({ signal }) => adapter.sessionJob(signal), refetchInterval: 1000, refetchOnWindowFocus: false });
  const [confirmed, setConfirmed] = useState(false);
  const [remote, setRemote] = useState(false);
  const [mode, setMode] = useState("observe");
  const [duration, setDuration] = useState("300");
  const [steps, setSteps] = useState("24");
  const [download, setDownload] = useState("0");
  const start = useMutation({ mutationFn: (request: SessionStartRequest) => adapter.startSession(request), retry: false,
    onSuccess: () => { setConfirmed(false); void client.invalidateQueries({ queryKey: ["session-job", adapter.describe().id] }); } });
  useEffect(() => { setConfirmed(false); setRemote(false); start.reset(); }, [server?.revision, mode, duration, steps, download, start.reset]);
  const job = query.data?.ok ? query.data.value.job : null;
  const active = job !== null && ["preparing", "supervising", "stopping"].includes(job.phase);
  const requiresRemote = server?.fields !== null && server?.fields !== undefined && !["127.0.0.1", "::1"].includes(server.fields.host);
  const whole = (text: string, min: number, max: number) => /^\d+$/.test(text) && Number(text) >= min && Number(text) <= max;
  const valid = whole(duration, 1, 3600) && whole(download, 0, 2048) && (mode === "observe" || whole(steps, 1, 64));
  const ready = server?.fields !== null && server?.fields !== undefined && server.loadError === null && query.data?.ok === true;
  return <Panel title="启动受管会话" note="显式入服；后台监督版本准备、运行时限与停止。刷新页面不会自动重启。" testId="panel-session-start">
    <p>{server?.fields ? `已保存服务器 ${server.fields.host}:${server.fields.port} · 修订 ${server.revision}` : "先在服务器页保存地址。"}</p>
    <form className={styles.form} onSubmit={(event) => { event.preventDefault(); if (!ready || !confirmed || !valid || active || start.isPending || (requiresRemote && !remote)) return;
      start.mutate({ confirm: true, serverRevision: server!.revision, allowRemote: remote, maxDownloadBytes: Number(download) * 1024 * 1024,
        durationSeconds: Number(duration), autonomousSteps: mode === "observe" ? 0 : Number(steps) }); }}>
      <label className={styles.field}>运行方式<select value={mode} disabled={active || start.isPending} onChange={(e) => setMode(e.target.value)}>
        <option value="observe">仅入服观察（不调用模型）</option><option value="autonomous">按已保存模型与目标自主运行</option></select></label>
      <label className={styles.field}>运行时限（秒，1–3600）<input value={duration} disabled={active || start.isPending} onChange={(e) => setDuration(e.target.value)} /></label>
      {mode === "autonomous" ? <label className={styles.field}>最多动作数（1–64）<input value={steps} disabled={active || start.isPending} onChange={(e) => setSteps(e.target.value)} /></label> : null}
      <label className={styles.field}>下载预算（MiB，0 仅使用缓存）<input value={download} disabled={active || start.isPending} onChange={(e) => setDownload(e.target.value)} /></label>
      {requiresRemote ? <label><input type="checkbox" checked={remote} disabled={active || start.isPending} onChange={(e) => { setRemote(e.target.checked); setConfirmed(false); }} />允许连接此已保存远程服务器</label> : null}
      <label><input type="checkbox" data-testid="session-start-confirm" checked={confirmed} disabled={!ready || active || start.isPending} onChange={(e) => setConfirmed(e.target.checked)} />我确认启动此角色并加入上述服务器</label>
      <button className={styles.submit} data-testid="session-start-submit" disabled={!ready || !confirmed || !valid || active || start.isPending || (requiresRemote && !remote)}>{start.isPending ? "提交中…" : "启动会话"}</button>
    </form>
    {start.data ? <p role="status" data-testid="session-start-result">{start.data.ok ? "启动请求已接受，等待实际入服读数。" : `启动失败：${start.data.failure.message}`}</p> : null}
    {start.isError ? <p role="alert">启动请求未完成，请检查 Gateway 连接。</p> : null}
    {query.data && !query.data.ok ? <p role="alert">启动状态读取失败：{query.data.failure.message}</p> : null}
    {job ? <p role="status" data-testid="session-job-status">任务 {job.phase} · {job.fields.host}:{job.fields.port} · 准备 {job.installed}/{job.total} · {job.reason || job.outcome || "等待结果"}{job.inputReleaseFailed === true ? " · 按键释放未确认" : ""}。入服状态见上方世界与会话读数；结束任务不会自动重连。</p> : <p>尚无后台启动记录。</p>}
  </Panel>;
}
