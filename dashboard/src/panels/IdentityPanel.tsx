import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { KinReadAdapter } from "../domain/adapter";
import { KIN_STATE_LABELS } from "../domain/labels";
import { DEFAULT_IDENTITY_NAME, identityIsStale, isValidUsername } from "../domain/identityPolicy";
import { useIdentityController } from "../hooks/useIdentityController";
import { Panel } from "../components/Panel";
import styles from "./identity.module.css";

const STABILITY_NOTE =
  `新身份默认 ${DEFAULT_IDENTITY_NAME}；启动、重试、死亡或换服都不会随机改名——名字是持久化身份的一部分，只有这里的一次显式确认才能改动它。`;

/**
 * The identity-settings surface the card authorizes. Everything above the form is read-only
 * reporting of the stored identity; the form below is the single write the shell is allowed
 * to make, and it deliberately mirrors the server's own gates: the submit is reachable only
 * when the Kin is stopped, the name is valid, and the operator has confirmed the
 * UUID-changes consequence. A refusal the server gives still renders here (named, not folded
 * into a generic error) beside the identity that did NOT change.
 */
export function IdentityPanel({ adapter, nowMs }: { readonly adapter: KinReadAdapter; readonly nowMs: number }) {
  const controller = useIdentityController(adapter);
  const [draft, setDraft] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const { identity } = controller;

  useEffect(() => setConfirmed(false), [identity?.identityRevision, identity?.renameAllowed]);

  const trimmed = draft.trim();
  const nameValid = isValidUsername(trimmed);
  const sameAsCurrent = identity !== null && trimmed === identity.username;

  const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (identity === null || !identity.renameAllowed || !nameValid || !confirmed || controller.pending) return;
    // expectedRevision is the compare-and-swap token: whatever identity Core held at the
    // last poll. A concurrent rename advances it, and the server refuses on mismatch rather
    // than overwriting the newer name.
    controller.submit({ username: trimmed, confirm: true, expectedRevision: identity.identityRevision });
    setConfirmed(false);
  };

  const outcome = controller.outcome;

  return (
    <Panel
      title="身份 · 游戏 ID"
      note="修改角色名会改变离线身份。请先停止会话，再确认保存。"
      testId="panel-identity"
    >
      {controller.isLoading && identity === null ? (
        <p className={styles.state} data-testid="identity-loading">
          正在读取身份…
        </p>
      ) : null}

      {controller.failure !== null && identity === null ? (
        <p className={styles.readFailure} data-testid="identity-read-failure">
          身份读数失败（{controller.failure.kind}）：{controller.failure.message}
        </p>
      ) : null}

      {identity === null ? null : (
        <>
          <dl className={styles.fields}>
            <div className={styles.field}>
              <dt className={styles.label}>Kin</dt>
              <dd className={styles.value}>{identity.kinId}</dd>
            </div>
            <div className={styles.field}>
              <dt className={styles.label}>用户名</dt>
              <dd className={styles.value} data-testid="identity-username">
                {identity.username}
              </dd>
            </div>
            <div className={styles.field}>
              <dt className={styles.label}>离线 UUID</dt>
              <dd className={styles.mono} data-testid="identity-uuid">
                {identity.uuidCanonical}
              </dd>
            </div>
            <div className={styles.field}>
              <dt className={styles.label}>身份 revision</dt>
              <dd className={styles.value} data-testid="identity-revision">
                {identity.identityRevision}
              </dd>
            </div>
            <div className={styles.field}>
              <dt className={styles.label}>会话状态</dt>
              <dd className={styles.value} data-testid="identity-state">
                {KIN_STATE_LABELS[identity.state]}
              </dd>
            </div>
          </dl>

          <p className={styles.freshness} data-testid="identity-freshness">
            {identityIsStale(identity, nowMs)
              ? "读数已陈旧：改名以最新一次成功读取为准。"
              : `读数新鲜（观测于 ${identity.observedAt}）。`}
          </p>

          <p className={styles.notice} data-testid="identity-notice">
            {identity.notice}
          </p>
          <p className={styles.stability}>{STABILITY_NOTE}</p>

          <form className={styles.form} onSubmit={onSubmit}>
            <label className={styles.inputLabel} htmlFor="identity-new-name">
              新名字（3-16 位字母、数字或下划线）
            </label>
            <input
              id="identity-new-name"
              className={styles.input}
              type="text"
              value={draft}
              maxLength={16}
              disabled={!identity.renameAllowed || controller.pending}
              onChange={(event) => {
                setDraft(event.target.value);
                setConfirmed(false);
                if (outcome !== null) controller.clearOutcome();
              }}
            />
            {!nameValid && trimmed !== "" ? (
              <p className={styles.hint} data-testid="identity-name-hint">
                名字需为 3-16 位字母、数字或下划线。
              </p>
            ) : null}
            {sameAsCurrent ? (
              <p className={styles.hint} data-testid="identity-same-name">
                与当前名字相同，提交不会改动身份。
              </p>
            ) : null}

            <label className={styles.confirm}>
              <input
                type="checkbox"
                checked={confirmed}
                disabled={!identity.renameAllowed || controller.pending}
                onChange={(event) => {
                  setConfirmed(event.target.checked);
                  if (outcome !== null) controller.clearOutcome();
                }}
              />
              <span>我已确认：改名会解析出新的离线 UUID，已有角色数据不会自动迁移。</span>
            </label>

            <button
              type="submit"
              className={styles.submit}
              data-testid="identity-submit"
              disabled={!identity.renameAllowed || !nameValid || !confirmed || controller.pending}
            >
              {controller.pending ? "提交中…" : "确认改名"}
            </button>

            {!identity.renameAllowed ? (
              <p className={styles.caption} data-testid="identity-locked">
                只有会话停止时才能改名（当前状态：{KIN_STATE_LABELS[identity.state]}）。
              </p>
            ) : null}
          </form>

          {outcome?.ok && outcome.result !== null ? (
            <p className={styles.result} data-testid="identity-result">
              {outcome.result.status === "renamed"
                ? `已改名为 ${outcome.result.after.username} · revision ${outcome.result.after.identityRevision}${
                    outcome.result.uuidChanged ? " · 离线 UUID 已改变" : ""
                  }`
                : "名称未变：身份与 revision 保持原样。"}
            </p>
          ) : null}

          {outcome !== null && !outcome.ok && outcome.failure !== null ? (
            <p className={styles.refusal} data-testid="identity-refusal">
              改名被拒绝（{outcome.failure.kind}）：{outcome.failure.message}
            </p>
          ) : null}
        </>
      )}
    </Panel>
  );
}
