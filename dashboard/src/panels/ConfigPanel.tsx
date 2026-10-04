import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import type { KinReadAdapter } from "../domain/adapter";
import type { ConfigFieldMeta } from "../domain/configPolicy";
import {
  CONFIG_GROUPS,
  buildSaveFields,
  configFieldsSignature,
  configIsStale,
  fieldsToDraft,
  validateConfigDraft,
} from "../domain/configPolicy";
import type { ConfigDraft } from "../domain/configPolicy";
import { useConfigController } from "../hooks/useConfigController";
import { Panel } from "../components/Panel";
import styles from "./config.module.css";

const SECRET_BOUNDARY_NOTE =
  "这里只保存变量名，绝不保存密钥本身。真正的 API key 留在进程环境里，不入库、不进响应、不进日志、不显示在这个页面上。";
const WHOLE_DOCUMENT_NOTE =
  "保存会整份替换当前文档：留空的字段会被写成未设置。字段合法性先在本机核对一次，服务器仍是最终裁判——它拒绝时会说明原因，已存的文档不变。";

/**
 * The settings surface the whole-project goal authorizes as the second Dashboard write: the
 * operator's model and goal configuration, persisted through `gateway/config_write.py`. The
 * read is reported above the form; the form below is the write, and it deliberately mirrors the
 * server's own gates — it validates on the same rules `configPolicy` reuses from `operator_config`
 * before enabling 保存, so a value the panel lets through is one it believes the Gateway accepts.
 * A refusal the server gives still renders here (named, not folded into a generic error) beside
 * the document that did NOT change. The CSRF token never reaches this component's state or markup.
 */
export function ConfigPanel({ adapter, nowMs }: { readonly adapter: KinReadAdapter; readonly nowMs: number }) {
  const controller = useConfigController(adapter);
  const modelTest = useMutation({
    mutationFn: (_context: { signature: string | null; draftRevision: number }) => adapter.testModel(),
    retry: false,
  });
  const { config } = controller;
  const signature = config === null ? null : configFieldsSignature(config);

  const [draft, setDraft] = useState<ConfigDraft>({});
  const [edited, setEdited] = useState(false);
  const [draftRevision, setDraftRevision] = useState(0);
  // A -> B -> A during a request must not make its old answer current again.
  useEffect(() => setDraftRevision((current) => current + 1), [signature]);
  // Re-seed only when the SAVED document's signature actually changes (initial load, or the refetch
  // after an accepted save). A poll that returns the same document leaves the operator's in-progress
  // edits untouched, because the signature is unchanged and this effect does not fire.
  const [seededSignature, setSeededSignature] = useState<string | null>(null);
  useEffect(() => {
    if (signature === null) return;
    if (signature === seededSignature) {
      if (edited && controller.outcome?.ok) setEdited(false);
      return;
    }
    // A different polled document is not permission to erase unsaved operator input.
    if (edited && !controller.outcome?.ok) return;
    setDraft(fieldsToDraft(config!.fields));
    setSeededSignature(signature);
    setEdited(false);
  }, [signature, seededSignature, config, edited, controller.outcome?.ok]);

  const externalChange = edited && signature !== null && signature !== seededSignature;
  useEffect(() => {
    if (!edited) return;
    const warn = (event: BeforeUnloadEvent): void => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [edited]);

  const errors = useMemo(
    () => (config === null ? {} : validateConfigDraft(draft, config.providers)),
    [draft, config],
  );
  const valid = Object.keys(errors).length === 0;
  const editable = config !== null && !controller.pending;

  const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (config === null || controller.pending || !valid || externalChange) return;
    // The form sends the whole document (blanks dropped), matching save_from_request's replace
    // semantics — a field the body omits is written as unset.
    controller.submit({ fields: buildSaveFields(draft) });
  };

  const setField = (key: string, value: string): void => {
    setDraftRevision((current) => current + 1);
    setEdited(true);
    setDraft((current) => ({ ...current, [key]: value }));
    if (controller.outcome !== null) controller.clearOutcome();
  };

  const outcome = controller.outcome;
  // Resetting a pending mutation does not cancel its network request. Keep it busy,
  // and bind its eventual answer to the saved configuration and draft generation.
  const modelTestCurrent = !edited && modelTest.variables?.signature === signature &&
    modelTest.variables?.draftRevision === draftRevision;

  return (
    <Panel
      title="配置 · 模型与目标"
      note="设置模型连接与角色目标，点击保存后生效。API 密钥通过进程环境提供，此处仅保存变量名。"
      testId="panel-config"
    >
      {controller.isLoading && config === null ? (
        <p className={styles.state} data-testid="config-loading">
          正在读取配置…
        </p>
      ) : null}

      {controller.failure !== null && config === null ? (
        <p className={styles.readFailure} data-testid="config-read-failure">
          配置读数失败（{controller.failure.kind}）：{controller.failure.message}
        </p>
      ) : null}

      {config === null ? null : (
        <>
          {config.loadError !== null ? (
            <p className={styles.loadError} data-testid="config-load-error">
              已存配置无法解析：{config.loadError}。表单仍可编辑，保存会写入一份干净的文档。
            </p>
          ) : null}

          <p className={styles.freshness} data-testid="config-freshness">
            {configIsStale(config, nowMs)
              ? "读数已陈旧：保存以最新一次成功读取为准。"
              : `读数新鲜（观测于 ${config.observedAt}）。`}
          </p>

          <p className={styles.notice} data-testid="config-secret-boundary">
            {SECRET_BOUNDARY_NOTE}
          </p>
          <p className={styles.stability}>{WHOLE_DOCUMENT_NOTE}</p>
          {edited ? <p className={styles.notice} role="status" data-testid="config-unsaved">
            {externalChange ? "已存配置在别处发生变化。你的编辑已保留；请先放弃修改并读取最新配置，再重新编辑，避免覆盖。" :
              "有未保存修改。关闭或刷新会提示；切换面板会丢失此草稿，请先保存或放弃修改。"}
          </p> : null}

          <form className={styles.form} onSubmit={onSubmit}>
            {CONFIG_GROUPS.map((group) => (
              <fieldset key={group.id} className={styles.group} data-testid={`config-group-${group.id}`}>
                <legend className={styles.groupLabel}>{group.label}</legend>
                {group.fields.map((meta) => (
                  <ConfigField
                    key={meta.key}
                    meta={meta}
                    value={draft[meta.key] ?? ""}
                    error={errors[meta.key]}
                    providers={config.providers}
                    editable={editable}
                    onChange={setField}
                  />
                ))}
              </fieldset>
            ))}

            <button
              type="submit"
              className={styles.submit}
              data-testid="config-submit"
              disabled={!valid || controller.pending || externalChange}
            >
              {controller.pending ? "保存中…" : "保存配置"}
            </button>
            <button type="button" className={styles.submit} disabled={!edited || controller.pending}
              onClick={() => {
                setDraftRevision((current) => current + 1);
                setDraft(fieldsToDraft(config.fields));
                setSeededSignature(signature);
                setEdited(false);
                controller.clearOutcome();
              }}>放弃修改，读取已存配置</button>
          </form>

          <p className={styles.notice}>
            连接测试使用已保存配置与 Gateway 进程环境（环境优先），最多等待 20 秒。
            点击会尝试一次模型调用，可能产生费用；返回的决策不会执行游戏动作。
          </p>
          <button type="button" className={styles.submit} data-testid="model-test-submit"
            disabled={edited || controller.pending || modelTest.isPending || config.loadError !== null}
            onClick={() => modelTest.mutate({ signature, draftRevision })}>
            {modelTest.isPending ? "测试连接中…" : "测试已保存的模型连接"}
          </button>
          {modelTest.data !== undefined && modelTestCurrent ? (
            <p className={modelTest.data.ok && modelTest.data.value.status === "connected" ? styles.result : styles.refusal} role="status" data-testid="model-test-result">
              {modelTest.data.ok
                ? `${modelTest.data.value.status === "connected" ? "模型连接与决策格式通过" : `模型不可用：${modelTest.data.value.reason}`} · ${modelTest.data.value.elapsedMs} ms · 调用记录 ${modelTest.data.value.modelCalls} · 估算成本 ${modelTest.data.value.estimatedCostMicro} micro（非账单）`
                : `连接测试失败：${modelTest.data.failure.message}`}
            </p>
          ) : null}
          {!modelTest.isPending && (modelTest.data !== undefined || modelTest.isError) && !modelTestCurrent ? (
            <p className={styles.notice} role="status">连接测试期间配置或草稿已变化，旧结果不适用于当前设置；请按需重新测试。</p>
          ) : null}
          {modelTest.isError && modelTestCurrent ? <p className={styles.refusal} role="alert">
            连接测试未完成，请检查 Gateway 连接后重试。
          </p> : null}

          {outcome?.ok && outcome.result !== null ? (
            <p className={styles.result} data-testid="config-result">
              已保存：写入 {Object.keys(outcome.result.fields).length} 个字段
              {Object.keys(outcome.result.fields).length === 0 ? "（全部清空）" : ""}。
            </p>
          ) : null}

          {outcome !== null && !outcome.ok && outcome.failure !== null ? (
            <p className={styles.refusal} data-testid="config-refusal">
              保存被拒绝（{outcome.failure.kind}）：{outcome.failure.message}
            </p>
          ) : null}
        </>
      )}
    </Panel>
  );
}

function ConfigField({
  meta,
  value,
  error,
  providers,
  editable,
  onChange,
}: {
  readonly meta: ConfigFieldMeta;
  readonly value: string;
  readonly error: string | undefined;
  readonly providers: readonly string[];
  readonly editable: boolean;
  readonly onChange: (key: string, value: string) => void;
}) {
  const id = `config-field-${meta.key}`;
  return (
    <div className={styles.field}>
      <label className={styles.inputLabel} htmlFor={id}>
        {meta.label}
      </label>
      {meta.provider ? (
        <select
          id={id}
          className={styles.input}
          value={value}
          disabled={!editable}
          data-testid={`config-input-${meta.key}`}
          aria-invalid={error !== undefined}
          aria-describedby={`${id}-hint`}
          onChange={(event) => onChange(meta.key, event.target.value)}
        >
          {providers.map((provider) => (
            <option key={provider} value={provider}>
              {provider}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          className={styles.input}
          type={meta.int ? "number" : "text"}
          value={value}
          placeholder={meta.placeholder}
          disabled={!editable}
          data-testid={`config-input-${meta.key}`}
          aria-invalid={error !== undefined}
          aria-describedby={`${id}-hint`}
          onChange={(event) => onChange(meta.key, event.target.value)}
        />
      )}
      <p className={styles.hint} id={`${id}-hint`}>
        {error !== undefined ? (
          <span className={styles.fieldError} data-testid={`config-error-${meta.key}`}>
            {error}
          </span>
        ) : (
          meta.hint
        )}
      </p>
    </div>
  );
}
