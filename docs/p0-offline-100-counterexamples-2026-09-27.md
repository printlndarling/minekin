# P0-OFFLINE-100 §3.6 反例 9/10/11 — 判官层直驱（L1）+ 封存校验层反证（L2）读数记录

- 会话：E lane（真实运行 / 证据），分支 `codex/minekin-offline-100-counterexamples`
- base / HEAD（记录时）：`7aa5d14602cd5f9b5466ecececf041302c0cf463`（= 远端 `main`，merge-base 同源，`git rev-list --count origin/main..HEAD` = 0）
- 逐文件改动：仅本文件一个新跟踪文件（`docs/p0-offline-100-counterexamples-2026-09-27.md`）；
  `git diff --stat` 见文末提交补记。探针脚本与日志在 `.tmp/ecs/`（不入库）。
- 环境：Windows + Git Bash，容器镜像 `minekin-runner:local` =
  `b67a4d91730657e147adc15d65be22115ae2c1315ac7981f731d534608095d6f`（`docker image inspect` 原样），
  仓库以 `:ro` 挂 `/src`、规范卷 `minekin-runner-data` 以 `:ro` 挂 `/data`，`PYTHONPATH=/src/src`。
  本卡运行期间卷上镜像未被重建；宿主 `uv` 门禁（§6）在本 worktree（base `7aa5d14`）执行。

## 1. 复现姿势（全部读数的统一命令形态）

```bash
cd "C:/Users/darling/Documents/agent_work/minekin-wt-e-cx"
export MSYS_NO_PATHCONV=1
REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash -w /src \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  minekin-runner:local -lc 'bash /src/.tmp/ecs/<s1-remeasure|s2-forgery|s3-rejudge>.sh'
```

原始日志：`.tmp/ecs/s1-remeasure.log`（25 行）、`.tmp/ecs/s2-forgery.log`（88 行）、
`.tmp/ecs/s3-rejudge.log`（59 行）。写试探（容器内对 `/data` 写一个探针文件）回
`OSError: [Errno 30] Read-only file system`，见 s1/s2 日志头尾；全程未写规范卷。

## 2. 三枚 bundle 与 A/B/A2 对应关系（本卡自行重量，非抄录）

重量方式：只读打开 `/data/evidence-attempts.sqlite3`（sqlite URI `mode=ro`）取
OFFLINE-100 的 `sequence/run_id`；对每段 bundle 目录独立重算
`sha256(manifest.json)` 并与 `bundle.sha256` 文件比对；世界归属取
`trusted/server-profile.json` 的 `profile_id`+`revision`、`server/server.properties` 的
`level-name` 与 `server/server.log` 的 `Preparing level "…"`；会话取
`bridge-trace.jsonl` / `previous-run-trace.jsonl` 的 `session_id` 列。复现命令 = §1 姿势跑
`.tmp/ecs/s1-remeasure.sh`。

| attempt seq | run_id | bundle digest（自算=文件，逐字） | 段 | profile_id / revision | 本段 session_id |
|---|---|---|---|---|---|
| 3 | `cd215ca1caf74bd0b230abe8de72e568` | `670aec0bfb516755b52b1fddac446d38d9bb79ba6f43df5e83e6a0f2f4faa202` | **A1** | `p0-controlled-offline-loopback` / `c742c47670997ac5f8f9e9f3bcca6304a041b253fe953dc0906923affb798d4b` | `f0a287335e5f408285886aff7d65bdb3` |
| 4 | `a26e2c35b66e498b828900877397a73f` | `0314121c01b56d0e9f0c3f4ae1e4fb77df5cca9a8de45a203b3047fd391692a4` | **B** | `p0-controlled-offline-loopback-b` / `bfd03fcd16cf9d02b044fb475a030d6274f7424fcff0b22ca9dfdaece79268d1` | `4ba0825eee234506bcdca524d1631df9` |
| 5 | `7ff026e4bca646c58f8eee2c2b000867` | `0cc1fb99111d4cef11c47dcb86305784130b6a9746bc77251d5289a80dfb92b7` | **A2** | `p0-controlled-offline-loopback` / `c742c476…`（与 A1 同） | `ed3fdc067e294d5e9b356c34ca9a058b` |

A/B/A2 的归属依据（量出来的）：A1 与 A2 的 `profile_id`+`revision` 逐字相同（世界 A），
B 的 `profile_id`（`…-b`）与 `revision`（`bfd03fcd…`）与两端不同（世界 B）；三段
`level-name` 与 `Preparing level` 均为字符串 `world`（两套独立服务端各自的世界名，
世界身份由 profile revision 承载）。前驱链（各 bundle `asserter-inputs.json` 的
`previous_run_id` 与其 `previous-run-trace.jsonl` 的 session 集合互证）：
A1 前驱 = `8ce303467b1f409d97f66bf1cd411183`（热身 run，未入 attempts），B 前驱 = A1
（前驱 session `f0a28733…` = A1 本段 session），A2 前驱 = B（前驱 session `4ba0825e…` =
B 本段 session）。seq1/seq2（`fd516eb6…`、`c96aa8bd…`）为早期失败 attempt，不在本卡材料内。

## 3. 反例 9 — 伪造某一段的 `kin_id` ⇒ C1 clause 具名红

- 伪造：A2 bundle 的 `/tmp` 带标签副本 `CX9-a2-forged-kin-id`（目录名自述伪造字段）。
  字段：`bridge-trace.jsonl` 每行的 `kin_id` 列，原值 `kin-e-aba` → 新值
  `kin-e-aba-forged`（首行原值逐字：`'kin-e-aba'`，同文件 `run_id` 未动，仍
  `'7ff026e4bca646c58f8eee2c2b000867'`）。
- **L1 判官层直驱**（`read_sealed_material` → `the_kin_id_continues_from_the_previous_run`）：
  逐字返回 `'KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-e-aba-forged'`。
- **L1 父行**（同一伪造材料 → `evaluate(OFFLINE-100 case, material)`）：
  `result FAIL`，`observed` 中消失该项，`failures` 逐字含
  `'the_kin_id_continues_from_the_previous_run:KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-e-aba-forged'`
  （另有常量项 `the_world_switch_returned_to_the_confirmed_world:A_B_A_TRIPLE_NOT_SEALED`）。
  即：此红不止到 clause 层，够到判官层父行 verdict。
- **L2 封存校验层反证**（同一伪造副本）：
  `python3 -m minekin_core evidence verify 7ff026e4…`（`MINEKIN_HOME` 指向副本的
  run-id 寻址根）→ `verify rc=12`，stdout 逐字
  `"status": "invalid", "verified": false, "violations": ["ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl"]`；
  `tools/rejudge_evidence.py` → `rc=2`，stderr 逐字
  `{"schema_version": 1, "status": "unjudged", "message": "the bundle does not hold up, so there is nothing to re-judge: ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl"}`。
- **正对照**（未伪造规范字节的 A2 `/tmp` 副本，同一加载路径）：clause 返回 `None`；
  `evaluate` 与封存 manifest 一致（`observed` 含该 clause，`failures` 只剩常量项）；
  `evidence verify rc=0 status=verified violations=[]`；`rejudge rc=0 status=agrees`。
  ⇒ 红来自伪造字段，不是恒红。

## 4. 反例 10 — 伪造相邻两段复用同一 `session_id` ⇒ C2 clause 具名红；字面 A1↔A2 变体具名登记

- **CX10a（执行的主读数）**：B bundle 副本 `CX10a-b-forged-session-eq-A1`，字段
  `bridge-trace.jsonl` 每行 `session_id`，原值 `4ba0825eee234506bcdca524d1631df9` →
  新值 `f0a287335e5f408285886aff7d65bdb3`（= A1 的 session，取自 B bundle 自带的
  `previous-run-trace.jsonl`，不抄录）。
  - L1：`the_session_is_not_the_one_the_previous_run_had` 逐字返回
    `'SESSION_ID_SHARED_ACROSS_RUNS:f0a287335e5f408285886aff7d65bdb3'`；
    父行 `evaluate` failures 逐字含
    `'the_session_is_not_the_one_the_previous_run_had:SESSION_ID_SHARED_ACROSS_RUNS:f0a287335e5f408285886aff7d65bdb3'`。
  - L2：`verify rc=12`，`violations: ["ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl"]`；
    `rejudge rc=2`，message 逐字
    `the bundle does not hold up, so there is nothing to re-judge: ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl`。
  - 正对照：未伪造 B 副本同一 clause 返回 `None`，`rejudge agrees`、`verify rc=0`。
- **CX10b（§3.6 字面「A1 与 A2 复用同一 session_id」变体，量出来的具名事实）**：
  A2 副本 `CX10b-a2-forged-session-eq-A1-literal`，字段 `bridge-trace.jsonl` 每行
  `session_id`：`ed3fdc067e294d5e9b356c34ca9a058b` → `f0a287335e5f408285886aff7d65bdb3`
  （A1 的 session）。L1 clause 返回 **`None`**，父行 `evaluate` 的 failures 只剩常量项。
  L2 仍拒：`verify rc=12 ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl`、`rejudge rc=2`。
  ⇒ 具名事实（不回改冻结文档）：**字面 A1↔A2 的 session 复用不可被任何已注册 clause 判出**——
  已注册的 C2 clause 是相邻对（本 run vs `previous-run-trace`）判据，A1 不在 A2 bundle 的
  载体里；§3.6 为 10 设计的目标串 `SESSIONS_NOT_THREE_DISTINCT` 在 `tools/assert_case_evidence.py`
  中不存在、不可观察。这不是「未测」，而是本卡用真实读数证明的构造性质，与父行
  `A_B_A_TRIPLE_NOT_SEALED` 同族（缺跨 bundle 三段链载体，主控保留）。

## 5. 反例 11 — 从一段删掉 `server/usercache.json` 载体 ⇒ 该段不绿（具名）

- 伪造：A2 副本 `CX11-a2-usercache-deleted`，删除 `server/usercache.json`
  （删前该文件 sha256 逐字：
  `be61370b4571451ac28582cf1243fb9364949b1370890991b21f1307519ad30e`）。
  服务端身份载体常量：`SERVER_IDENTITIES_ARTIFACT = "server/usercache.json"`
  （`tools/assert_case_evidence.py:721`，本卡读取基线内）。
- **L1**：`the_world_and_the_identity_are_the_server_s_record` 逐字返回
  `'IDENTITY_NOT_RECORDED'`（该段不绿，具名；命中路径：join 行在 server.log 仍在，
  服务端缓存已无条目 ⇒ `server_observed_join_identity` 具名拒——与 §3.6 引用的
  `IDENTITY_NOT_RECORDED` 语义一致，当前基线行号 `:1066`）。
- **L1 父行**：`evaluate` failures 逐字含
  `'the_world_and_the_identity_are_the_server_s_record:IDENTITY_NOT_RECORDED'`。
- **L2**：`verify rc=12`，violations 逐字 `["ARTIFACT_MISSING:server/usercache.json"]`
  （删除触发的具名摘要拒止族；非删除型伪造如 CX9/10 回 `ARTIFACT_DIGEST_MISMATCH`），
  `rejudge rc=2`，message 逐字
  `the bundle does not hold up, so there is nothing to re-judge: ARTIFACT_MISSING:server/usercache.json`。
- **正对照**：未删 A2 副本同一 clause 返回 `None`（三份 bundle 的 manifest
  `assertions.observed` 亦在列），`verify rc=0`、`rejudge agrees rc=0`。

## 6. 汇总与边界

- 逐条两层完成度：**9、10（CX10a 主读数 + CX10b 字面变体）、11 全部 L1+L2+正对照齐**，
  无一条只有单层。副本目录名均带标签（段名+伪造字段），伪造只发生在 `/tmp` 副本；
  规范卷全程 `:ro`（写试探回 `Errno 30`），三枚 bundle 的 `manifest.json` 摘要在全部
  试验后复核仍与 §2 逐字一致（`digest_matches_file True ×3`，s2 日志尾段）。
- 只到 clause 层的：无——三条 L1 红都同时出现在判官层父行 `evaluate` 的 `failures` 里
  （§3/§4/§5 逐字）。够到父行的限定：**判官层**父行不等于登记面父行；登记面父行今天
  对任何材料恒答常量（见下）。
- **本卡不使 OFFLINE-100 闭合。登记面父行判据
  `the_world_switch_returned_to_the_confirmed_world` 仍对三份规范 bundle 恒答
  `FAIL / A_B_A_TRIPLE_NOT_SEALED`（§3 正对照的 `evaluate` 与 §3 尾 `rejudge agrees`
  读数逐字复现），本卡未改 `tools/**`、registry、case fixture、产品 `src/**` 任何字节。**
- §3.6 设计目标串与已注册 clause 的对应关系（具名事实，不回改冻结文档）：9 设计的
  `KIN_ID_NOT_SINGLE_ACROSS_TRIPLE`、10 设计的 `SESSIONS_NOT_THREE_DISTINCT` 不存在于
  注册代码；已注册 clause 在真判定分支上实际可观察的具名红分别是
  `KIN_ID_NOT_CONTINUOUS:<名单>` 与 `SESSION_ID_SHARED_ACROSS_RUNS:<名单>`，本卡量到的
  正是这两个。三段链级判定（跨 bundle 的「单一 kin_id」「三个互异 session」）仍需要
  `minekin.p0.evidence.v1` 的新增载体——主控保留决定，不在本卡。
- 镜像来源限定（登记）：宿主唯一 `minekin-runner:local` 为 `b67a4d917306`（2026-09-26 构建），
  H1f 在 `c866d05` 之后可能重建同名镜像；本卡读数不依赖镜像内代码（仓库以 `:ro` 挂
  `/src` 且 `PYTHONPATH=/src/src`，判据代码全部来自本 worktree `7aa5d14`），镜像仅提供
  python 运行时。
- 未测清单（本卡确实没测的）：§3.6-8 的第二半（把 A2 载体整体搬到 B 的真实世界、含
  `Preparing level`）；OFFLINE-090 侧真跑；seq1/seq2 两份早期 FAIL attempt 的读数复核；
  登记面父行变绿、门载荷、registry 状态（全部属 M 面/主控保留，未触及）。
- 一句话结论：**DONE**——9、10、11 以两层读数（L1 判官层真红 + L2 封存通道具名拒止 +
  未伪造正对照全绿）实测完成；§3.6 字面 10（A1↔A2 复用）与三条的三段链级目标串按构造
  不可判，已以 CX10b 与常量读数留证并具名登记，非含糊化。

## 7. 门禁原始输出（本 worktree，base `7aa5d14` 全树，宿主 uv）

运行时代码树 = `7aa5d14` + 本记录文档一次 docs-only 提交（`8c38f1d`），工作树 clean；
未合入 `41cff82` 的 clause map 重排，故不触发该重排下的 `168 != 150` 失败面。

```text
$ uv run --frozen pytest -q            # 一次跑满,未触发已知满载 flaky,无 failed 行
2594 passed, 3 skipped in 417.61s (0:06:57)
SKIPPED [1] tests\unit\test_orphans.py:686: this platform cannot answer the question, so it can never say gone
SKIPPED [1] tests\unit\test_silent_listener.py:123: a Windows terminate is not a signal
SKIPPED [1] tests\unit\test_tested_provenance.py:354: bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is not built on this host, ...

$ uv run ruff format --check .
353 files already formatted

$ uv run ruff check .
All checks passed!

$ uv run python tools/check_case_assertions.py
Case assertion implementations: OK (150 registered)

$ uv run python tools/verify_fixture_digests.py
Minekin case fixture digests: OK

$ uv run python tools/check_boundaries.py
Minekin package dependency boundaries: OK

$ git diff --check
(空输出,clean)
```

（`verify_fixture_digests` 原样行:`Minekin case fixture digests: OK`。）

四态划分：
- **已合入**：无——主干未动,本卡一切产物只在本分支。
- **仅在分支**：本记录文档 + `.tmp/ecs/` 探针与日志(不入库)。
- **真实封证(卷上,既有)**：§2 三枚 `SEALED` bundle(第十四轮封,本卡只 `:ro` 复量,零新增封证)。
- **未验证/未测**：§6 未测清单;另登记一条边界——本卡的 L2 `rejudge agrees`/`verify` 正对照
  成立依赖 base `7aa5d14` 的 case fixture 字节与封证时一致;远端 main 若经 41cff82+ 的 clause
  map 重排,在 41cff82 上 `rejudge_evidence` 会以 case 摘要漂移
  (`731f63d0…` vs 封证 `f55260af…`,registry fixture `tests/fixtures/cases/p0-offline-100.json`
  面)改答 `unjudged`,该漂移属 M 独占面、由 M 处置,本卡未改任何 fixture 字节。

## 8. 一句话结论

**DONE**：§3.6 反例 9、10、11 全部完成两层读数(L1 判官层真红 + L2 封存通道具名拒止 +
未伪造正对照全绿),证明 OFFLINE-100 已注册的三条 clause 判据(`kin_id` 延续、session 不跨界、
服务端身份记录)非恒真;§3.6 字面 10(A1↔A2 复用)与两段设计目标串
(`KIN_ID_NOT_SINGLE_ACROSS_TRIPLE`/`SESSIONS_NOT_THREE_DISTINCT`)按构造不可由现注册判据观察,
已以 CX10b 真实读数具名登记;登记面父行仍 `FAIL / A_B_A_TRIPLE_NOT_SEALED`,OFFLINE-100
不因本卡闭合。
