import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ok, type KinReadAdapter } from "../domain/adapter";
import type { ServerSaveRequest } from "../domain/model";
import { Panel } from "../components/Panel";
import styles from "./config.module.css";

export function useServerRead(adapter: KinReadAdapter) {
  const query = useQuery({ queryKey: ["server", adapter.describe().id],
    queryFn: ({ signal }) => adapter.serverConfig(signal), refetchInterval: 5000, refetchOnWindowFocus: false });
  return { config: query.data?.ok ? query.data.value : null,
    failure: query.data !== undefined && !query.data.ok ? query.data.failure : null,
    isLoading: query.isLoading, isFetching: query.isFetching, isError: query.isError };
}

export function ServerPanel({ adapter }: { readonly adapter: KinReadAdapter }) {
  const read = useServerRead(adapter);
  const client = useQueryClient();
  const config = read.config;
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("25565");
  const [seed, setSeed] = useState(0);
  const [edited, setEdited] = useState(false);
  const [allowRemote, setAllowRemote] = useState(false);
  const changed = config !== null && seed !== config.revision;
  const save = useMutation({ mutationFn: (request: ServerSaveRequest) => adapter.saveServer(request), retry: false,
    onSuccess: (result) => {
      if (result.ok && config !== null) {
        client.setQueryData(["server", adapter.describe().id], ok({ ...config, ...result.value }, adapter.describe().kind, "server/save"));
        setEdited(false); void client.invalidateQueries({ queryKey: ["server", adapter.describe().id] });
      }
    } });
  const probe = useMutation({ mutationFn: () => adapter.probeServer(seed, allowRemote), retry: false });
  useEffect(() => {
    if (config !== null && !edited) {
      setHost(config.fields?.host ?? "127.0.0.1"); setPort(String(config.fields?.port ?? 25565));
      setSeed(config.revision); setAllowRemote(false);
    }
  }, [config?.revision, edited]);
  useEffect(() => { probe.reset(); setAllowRemote(false); }, [config?.revision, edited, host, port, probe.reset]);
  useEffect(() => {
    if (!edited) return;
    const warn = (event: BeforeUnloadEvent): void => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [edited]);
  const valid = host.length > 0 && /^\d+$/.test(port) && Number(port) > 0 && Number(port) <= 65535;
  const remote = host !== "127.0.0.1" && host !== "::1";
  const busy = save.isPending || probe.isPending;
  const editable = config !== null && config.loadError === null && !busy;
  const visibleProbe = !edited && !changed && probe.data !== undefined &&
    (!probe.data.ok || probe.data.value.revision === config?.revision) ? probe.data : undefined;
  return <Panel title="服务器 · 连接设置" note="保存服务器地址后显式探测版本。探测不会启动客户端或加入世界。" testId="panel-server">
    {config === null ? <p className={styles.state}>{read.failure === null ? "正在读取服务器设置…" : `读取失败：${read.failure.message}`}</p> : <>
      {config.loadError !== null ? <p className={styles.refusal}>{config.loadError}</p> : null}
      <p className={styles.hint}>当前使用离线身份；客户端版本由实际探测和已登记支持决定。地址须为 IP 字面量，暂不接受 DNS 名称。</p>
      <form className={styles.form} onSubmit={(event) => { event.preventDefault(); if (valid && editable && !changed) save.mutate({ revision: seed, fields: { host, port: Number(port) } }); }}>
        <label className={styles.field}>服务器地址<input className={styles.input} data-testid="server-host" value={host} disabled={!editable}
          onChange={(event) => { setHost(event.target.value); setEdited(true); save.reset(); }} /></label>
        <label className={styles.field}>端口<input className={styles.input} inputMode="numeric" data-testid="server-port" value={port} disabled={!editable}
          aria-invalid={!valid} onChange={(event) => { setPort(event.target.value); setEdited(true); save.reset(); }} /></label>
        {!valid ? <p className={styles.refusal}>填写地址和 1–65535 的整数端口。</p> : null}
        {edited ? <p className={styles.notice} role="status">{changed ? "服务器配置已在别处变化，草稿已保留。请放弃修改并读取最新设置。" : "有未保存修改；保存后才能探测此地址。"}</p> : null}
        <button className={styles.submit} data-testid="server-save" disabled={!valid || !editable || changed}>{save.isPending ? "保存中…" : "保存服务器"}</button>
        <button type="button" className={styles.submit} disabled={!edited || busy} onClick={() => { setEdited(false); save.reset(); }}>放弃服务器草稿</button>
      </form>
      {save.data !== undefined ? <p role="status" className={save.data.ok ? styles.result : styles.refusal} data-testid="server-save-result">{save.data.ok ? `服务器已保存 · 修订 ${save.data.value.revision}` : `保存失败：${save.data.failure.message}`}</p> : null}
      {remote ? <label className={styles.field}><input type="checkbox" checked={allowRemote} disabled={edited || changed || busy} onChange={(event) => setAllowRemote(event.target.checked)} />我允许探测已保存的远程地址 {host}:{port}</label> : null}
      <button type="button" className={styles.submit} data-testid="server-probe" disabled={!editable || edited || changed || config.fields === null || (remote && !allowRemote)} onClick={() => probe.mutate()}>{probe.isPending ? "探测中…" : "探测服务器版本"}</button>
      {visibleProbe !== undefined ? <p className={visibleProbe.ok && visibleProbe.value.supportStatus === "RESOLVED" ? styles.result : styles.refusal} role="status" data-testid="server-probe-result">{visibleProbe.ok ? `探测 ${visibleProbe.value.outcome} · 版本 ${visibleProbe.value.serverVersion ?? "未知"} · 协议 ${visibleProbe.value.protocol ?? "未知"} · 客户端 ${visibleProbe.value.supportStatus}（${visibleProbe.value.osArch}）${visibleProbe.value.supportReasons.length > 0 ? `：${visibleProbe.value.supportReasons.join("，")}` : ""}` : `探测失败：${visibleProbe.failure.message}`}</p> : null}
      {save.isError || probe.isError ? <p role="alert" className={styles.refusal}>请求未完成，请检查 Gateway 连接。</p> : null}
    </>}
  </Panel>;
}
