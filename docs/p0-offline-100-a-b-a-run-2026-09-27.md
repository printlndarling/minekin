# P0-OFFLINE-100-A-B-A-RUN-001：A→B→A 三段的卷上真跑与逐条 C1-C5 人工读数

- 卡：`P0-OFFLINE-100-A-B-A-RUN-001`（`docs/development-execution-plan.md:250`，M 主控第十一轮立卡；
  判据冻结 = `2e6711f`）。判据原文在 `docs/p0-offline-090-100-case-spec-2026-09-27.md` §3.5 C（C1-C5），
  本卡不改动任何判据。
- 分支 `codex/minekin-evidence`，base = `0e497a9`（卡面钉住的提交；主干此后前进到 `d4d44b6`，本卡未
  rebase、未 merge 主干）。工作树 `C:\Users\darling\Documents\agent_work\minekin-wt-evidence`。
- Kin 根 = `kin-e-aba`；卷 = `minekin-runner-data`，除 §6 那一次标注过的**副本**试验外全部 `:ro` 挂载读数。
- 探针材料（未跟踪）：`.tmp/aba/`（`a1.log` `a1-retry.log` `warmup.log` `a1-leg.log` `b-leg.log`
  `a2-leg.log` `server-profile-b.json` `readout.sh` `readout.log` `readout-extra.log`
  `forgery-copy.log`，及本收尾会话的复量 `readout-recheck.log` / `readout-recheck-r1.log`）。
- 测试服是运行者控制的**本地隔离服**（匿名称谓；地址只在未跟踪的 `.tmp/local-test-server.txt`，
  本文档不出现其 IP:port / 主机名；本卡全程未连接任何远程服务器）。
- 一句话结论：**三段已真跑并封存为三份 `SEALED` bundle，逐条 C1-C5 的人工读数全部成立；
  但 registry 侧父行仍 `FAIL`，失败名照原样是
  `the_world_switch_returned_to_the_confirmed_world:A_B_A_TRIPLE_NOT_SEALED`**——卡面第 12 轮
  边界写明「本卡即便跑出完整三段，也不会让已登记的判据自行变绿……真跑的产出是卷上三段字节 +
  逐条 C1-C5 的人工读数记录，把『能否闭合』交给主控裁决」。本文档就是那份读数记录。

## 1. 卷上发生了什么（含失败与热身，全部保留、未删未改）

OFFLINE-100 在 `kin-e-aba` 上的 attempts 台账（`:ro` 原样行，复量补测的带表头版本在
`.tmp/aba/readout-recheck-r1.log`）：

```text
case_id|run_id|sequence|supersedes_run_id|status
OFFLINE-100|fd516eb623704d0db454fe636af7dbc0|1||SEALED
OFFLINE-100|c96aa8bd26b2477fabd869214b2ed44c|2|fd516eb623704d0db454fe636af7dbc0|SEALED
OFFLINE-100|cd215ca1caf74bd0b230abe8de72e568|3|c96aa8bd26b2477fabd869214b2ed44c|SEALED
OFFLINE-100|a26e2c35b66e498b828900877397a73f|4|cd215ca1caf74bd0b230abe8de72e568|SEALED
OFFLINE-100|7ff026e4bca646c58f8eee2c2b000867|5|a26e2c35b66e498b828900877397a73f|SEALED
```

时间顺序（server run 目录与宿主 `started_at`，均见对应日志）：

| 记号 | run_id | server run | 结果 |
| --- | --- | --- | --- |
| 首试 | `fd516eb623704d0db454fe636af7dbc0`(seq1) | run-179 | 会话 240s 内未到 playable，`outcome HANDSHAKE_TIMEOUT`，真实 FAIL 封存（`.tmp/aba/a1.log`）；当时四断言除链外全红：`PREVIOUS_IS_FIRST_RUN` ×2、`JOIN_NOT_LOGGED` |
| 重试 | `c96aa8bd26b2477fabd869214b2ed44c`(seq2) | run-180 | 同样 `HANDSHAKE_TIMEOUT`，FAIL 封存（`.tmp/aba/a1-retry.log`）|
| 热身 | `8ce303467b1f409d97f66bf1cd411183`（非 attempt，不封存） | run-181 | playable、走完会话（`.tmp/aba/warmup.log`）；它就是 A1 的 `previous_run_id` |
| **A1** | `cd215ca1caf74bd0b230abe8de72e568`(seq3) | run-182 | 真跑+封存，profile `p0-controlled-offline-loopback`（`.tmp/aba/a1-leg.log`）|
| **B** | `a26e2c35b66e498b828900877397a73f`(seq4) | run-183 | 真跑+封存，换 profile 为 `p0-controlled-offline-loopback-b`（`.tmp/aba/b-leg.log`、配方 `.tmp/aba/server-profile-b.json`）|
| **A2** | `7ff026e4bca646c58f8eee2c2b000867`(seq5) | run-184 | 真跑+封存，回到 A 的 profile（`.tmp/aba/a2-leg.log`）|

seq1/seq2 两份 FAIL bundle 与热身 run 的账本行**原样留在卷上**；本卡没有任何删除、改写或
supersede 操作的伪装——`supersedes_run_id` 链是台账的正常逐次前指，不是清理。

三段各自 manifest 的 `attempt.sequence` = 3/4/5，`previous_run_id` 链（时间链，异于台账
supersedes 链）为 `8ce30346… → cd215ca1…(A1) → a26e2c35…(B) → 7ff026e4…(A2)`，三份
`asserter-inputs.json` 逐字如此（`readout.log` §1）。

## 2. 逐条 C1-C5 人工读数（判据原文 → 原样读数 → 成立/不成立 → 反证）

以下所有字段名与值均来自 `:ro` 挂载下三份 bundle 的原样读取（`.tmp/aba/readout.log`，本收尾
会话以同一脚本复量，见 §5），具名到 run_id 与字段。

### C1 `the_kin_id_is_single_across_the_triple` — 成立

- 判据原文（§3.5 C/C1）：三条时间线的 `kin_id` 只有一个值，且等于三份
  `asserter-inputs.json:kin_id`。
- 读数：`bridge-trace.jsonl` 的 `kin_id` 字段——A1 `cd215ca1…` timeline.kins = `["kin-e-aba"]`；
  B `a26e2c35…` = `["kin-e-aba"]`；A2 `7ff026e4…` = `["kin-e-aba"]`；三份
  `previous-run-trace.jsonl` 的 kins 同为 `["kin-e-aba"]`；三份 `asserter-inputs.json:kin_id`
  均为 `kin-e-aba`。每份 `bridge-trace.jsonl` 的 `run_id` 集恰为本 run 一个值（sealer 构造性
  保证，实测无跨 run 行）。
- 结论：**成立**（三段单值一致）。
- 反证维度：registry 侧两-run 形 `the_kin_id_continues_from_the_previous_run` 在三份 bundle 的
  manifest `assertions.observed` 中均在列（A1/B/A2 三份逐字含该名字）。

### C2 `the_triple_runs_as_three_distinct_sessions` — 成立

- 判据原文：三条时间线各自恰有一个非空 `session_id` 且两两不相交。
- 读数（`readout.log` §1 各 `timeline.sessions` / `previous_timeline.sessions`）：
  A1 = `f0a287335e5f408285886aff7d65bdb3`；B = `4ba0825eee234506bcdca524d1631df9`；
  A2 = `ed3fdc067e294d5e9b356c34ca9a058b`。每个 timeline 的 sessions 集大小均为 1；
  B 的 `previous_timeline.sessions` = A1 的值、A2 的 = B 的值，相邻对两两互斥成立，
  三个值互不相同。
- 结论：**成立**。
- 反证维度：registry 形 `the_session_is_not_the_one_the_previous_run_had` 在三份 manifest
  `assertions.observed` 均在列。

### C3 `the_two_a_runs_share_one_confirmed_world_context` — 在人工读数下成立，但**链上没有载体**

- 判据原文：W(A1) 与 W(A2) 均存在且*获确认*（确认 = 服务端自记的 `joined the game` +
  usercache 对 `offline_player_uuid` 规则，见 C5），且 tuple
  `(profile_id, revision, level-name)`（并核 `Preparing level "<name>"`）相等。
- 读数：
  - A1 `cd215ca1…`：`trusted/server-profile.json:profile_id` = `p0-controlled-offline-loopback`，
    `revision` = `c742c47670997ac5f8f9e9f3bcca6304a041b253fe953dc0906923affb798d4b` =
    `manifest.world.server_config_digest`；`server/server.properties` `level-name=world`；
    `server/server.log` `Preparing level "world"`。
  - A2 `7ff026e4…`：同上四值逐字相同（`profile_id` = `p0-controlled-offline-loopback`、
    digest = `c742c47670997ac5f8f9e9f3bcca6304a041b253fe953dc0906923affb798d4b`、
    `level-name=world`、`Preparing level "world"`）。
  - B `a26e2c35…`（对照）：`profile_id` = `p0-controlled-offline-loopback-b`、digest =
    `bfd03fcd16cf9d02b044fb475a030d6274f7424fcff0b22ca9dfdaece79268d1`，与 A 两端不同。
  - joined 行（确认动作的服务端自记）：A1 `[22:28:23] … Kin joined the game`、
    A2 `[22:31:38] … Kin joined the game`（B 为 `[22:30:02]`）。
- 结论：**tuple 相等且两端各有服务端自记确认 ⇒ 人工读数成立**；但必须如实标注——
  账本列 `world_context_id` 在卷上（含本次三段的全部 `bridge-trace.jsonl` 行）为 null
  （三份 bundle 的 `timeline.world_context_ids` 逐字为 `["None"]`），因此「首尾 A 属同一
  **获确认** world context」今天只有 `server_config_digest` + `level_name` + `Preparing level`
  这组**旁证**，没有任何跨 bundle 的链上载体。拿 null 相等糊判被规范明文禁止。
- 反证（`.tmp/aba/forgery-copy.log`，标注过的**副本**试验，绝不碰规范卷）：把 A2 的
  `server/server.properties` 单字段 `level-name` 改成 `OTHERWORLD` 的 /tmp 副本上重算
  tuple——`A2(forged) tuple = ["p0-controlled-offline-loopback", "c742c476…", "OTHERWORLD", ["world"]]`
  与 A1 不再相等（level-name 匹配 False、含 Preparing 的全 tuple 匹配 False），且副本
  properties 的摘要 `4386613f096bf1bfa297e7d8ce918478378205cfadfc3c43ba845e3debad1491`
  与已封 manifest 不符（改一个字节即露馅）；规范卷未受影响（sentinel `data writable: False`，
  规范 A2 的 `level-name=world` 原样，副本目录已清理）。

### C4 `the_b_run_does_not_cross_into_a` — 成立

- 判据原文：B 的 session 集与 context tuple 在 A1、A2 的时间线或载体对中均不出现；
  A1|B 与 B|A2 的 pairwise 互斥都须成立。
- 读数：B 的 session `4ba0825eee234506bcdca524d1631df9` 不出现在 A1（timeline =
  `f0a28733…`、previous = `b80c75d9…`）也不出现在 A2（timeline = `ed3fdc06…`、previous =
  `4ba0825e…` 为前驱行、其自身 timeline 为 `ed3fdc06…`）的任一 timeline 集合中
  （`readout.log` §1 `previous_timeline.sessions` 逐段列明）；B 的 context tuple
  （`…-b` profile / `bfd03fcd…` digest）与 A 两端的 tuple（§C3 读数）不等。
- 结论：**成立**（session 与 tuple 两个方向均无交叉）。

### C5 `the_external_identity_is_server_observed_in_all_three` — 成立

- 判据原文：三 run 各自的 `server/usercache.json` + `server/server.log` 满足已注册的
  `server_observed_join_identity` 规则，不重推规则、不采信客户端自称。
- 读数：三份 bundle 的 `server/usercache.json` 中 `name = "Kin"` 条目均为
  `uuid = 8f40376b-c23f-3ef1-b553-5564eea75639`（expiresOn 分别为 22:28:23 / 22:30:02 /
  22:31:38 +30d）；三份 `manifest.identity.server_observed_name_uuid` 均为
  `Kin/8f40376b-c23f-3ef1-b553-5564eea75639`；三份 `server.log` 各含一行
  `Kin joined the game`（时间戳见 C3）。独立重算（`readout.log` §2）：
  `str(offline_player_uuid('Kin')) = 8f40376b-c23f-3ef1-b553-5564eea75639`，与三份服务端
  自记逐字一致。
- 结论：**成立**。registry 形 `the_world_and_the_identity_are_the_server_s_record` 在三份
  manifest `assertions.observed` 均在列，与上读数相互印证。

## 3. 父行为什么仍 FAIL（照原样，不粉饰）

三份 bundle 的 `manifest.assertions` 逐字相同：

```json
"expected": ["the_kin_id_continues_from_the_previous_run",
             "the_session_is_not_the_one_the_previous_run_had",
             "the_world_and_the_identity_are_the_server_s_record",
             "the_world_switch_returned_to_the_confirmed_world"],
"observed": ["the_kin_id_continues_from_the_previous_run",
             "the_session_is_not_the_one_the_previous_run_had",
             "the_world_and_the_identity_are_the_server_s_record"],
"failures": ["the_world_switch_returned_to_the_confirmed_world:A_B_A_TRIPLE_NOT_SEALED"],
"result": "FAIL"
```

原因具名在 `tools/assert_case_evidence.py:3892-3913` 的 docstring：一个 `RunMaterial` 只携
本次 run 与其 `previous-run-trace.jsonl`，三段链要成为可判对象需要新的封存载体，而命名一份
新封存工件 = 扩展证据 schema `minekin.p0.evidence.v1`（主控保留决策，且会重封全卷）；
账本 `world_context_id` 列全卷为 null，不构成捷径。因此该函数对任何 bundle 恒答
`A_B_A_TRIPLE_NOT_SEALED`。**本卡没有改动该函数、registry、任何 case 定义或 fixture。**

## 4. 本次新增封证的读数记录（四读 + 报告 + 卷底数 + 账本邻接）

- **bundle_digest 三份**（`readout.log` §3 原样）：
  A1 `670aec0bfb516755b52b1fddac446d38d9bb79ba6f43df5e83e6a0f2f4faa202`、
  B `0314121c01b56d0e9f0c3f4ae1e4fb77df5cca9a8de45a203b3047fd391692a4`、
  A2 `0cc1fb99111d4cef11c47dcb86305784130b6a9746bc77251d5289a80dfb92b7`。
- **`evidence verify` 三份原样**（均 `verified: true / sealed: true / result: FAIL /
  artifacts: 13 / violations: []`；failures 里的 FAIL 是被验的 verdict，不是读失败）：

```text
{"artifacts": 13, "bundle_digest": "670aec0bfb516755b52b1fddac446d38d9bb79ba6f43df5e83e6a0f2f4faa202", "command": "evidence verify", "evidence_directory": "/data/kin/kin-e-aba/run/evidence/cd215ca1caf74bd0b230abe8de72e568", "result": "FAIL", "run_id": "cd215ca1caf74bd0b230abe8de72e568", "schema_version": 1, "sealed": true, "status": "verified", "verified": true, "violations": []}
{"artifacts": 13, "bundle_digest": "0314121c01b56d0e9f0c3f4ae1e4fb77df5cca9a8de45a203b3047fd391692a4", "command": "evidence verify", "evidence_directory": "/data/kin/kin-e-aba/run/evidence/a26e2c35b66e498b828900877397a73f", "result": "FAIL", "run_id": "a26e2c35b66e498b828900877397a73f", "schema_version": 1, "sealed": true, "status": "verified", "verified": true, "violations": []}
{"artifacts": 13, "bundle_digest": "0cc1fb99111d4cef11c47dcb86305784130b6a9746bc77251d5289a80dfb92b7", "command": "evidence verify", "evidence_directory": "/data/kin/kin-e-aba/run/evidence/7ff026e4bca646c58f8eee2c2b000867", "result": "FAIL", "run_id": "7ff026e4bca646c58f8eee2c2b000867", "schema_version": 1, "sealed": true, "status": "verified", "verified": true, "violations": []}
```

- **`rejudge_evidence.py` 三份**：均 `Rejudge evidence: OK (OFFLINE-100 at
  a44289e8cdbc0643eebb7ff73985014a8fb87e176c622fd2a1c085f7abcc8a3b — these bytes produce the
  verdict the bundle records)`，JSON 里 `status: "agrees"`、`disagreements: []`，
  `re_judged.failures` 逐字复现 `the_world_switch_returned_to_the_confirmed_world:A_B_A_TRIPLE_NOT_SEALED`。
  case_version 三段与登记摘要一致，无摘要漂移。
- **`report_promotion.py --data-root /data`**：`report exit: 1`、`status: blocked`、
  `overall.promotable: False`；OFFLINE-100 五行为 §1 表所列（全部 `SEALED`，五份 bundle 均在
  registry 的 attempts 输出中）。**没有任何门因此变动。**
- **卷底数**：`bundles = 99`、attempts 表 `count(*) = 76`、`server-runs = 184`。
- **账本邻接**（`kin-e-aba` 的 `kin.sqlite3` event 表按 run 分组）：

```text
fd516eb623704d0db454fe636af7dbc0|1|10
c96aa8bd26b2477fabd869214b2ed44c|11|20
8ce303467b1f409d97f66bf1cd411183|21|39
cd215ca1caf74bd0b230abe8de72e568|40|58
a26e2c35b66e498b828900877397a73f|59|77
7ff026e4bca646c58f8eee2c2b000867|78|96
```

  每段的 `previous-run-trace.jsonl` 恰指向邻接前一段（A1 前驱 = 热身 run；B 前驱 = A1；
  A2 前驱 = B），`run_id` 无重叠。

## 5. 收尾会话的复量（同脚本、同 `:ro` 姿势）

- 姿势：`docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro"
  -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src
  minekin-runner:local -lc 'bash /src/.tmp/aba/readout.sh'`（输出
  `.tmp/aba/readout-recheck.log`，446 行）。
- **复量逐项一致**：重跑输出与 `readout.log` 的行多重集逐行相等（`diff <(sort a) <(sort b)`
  为空）；唯一差异是三条 `Rejudge evidence: OK` 行（stderr）与 `--- rejudge …` 头（stdout）
  合并重定向时的打印交错位置不同，无内容差异。§1-§7 的关键字段——三段 digest
  （A1/A2 同 `c742c476…`、B 为 `bfd03fcd…`）、三个互不相同的 session（`f0a28733…` /
  `4ba0825e…` / `ed3fdc06…`）、`world_context_ids` 三段均 `["None"]`、五行 attempts、
  卷底数 99/76/184、账本邻接、`offline_player_uuid('Kin')` 独立重算——全部与旧读数一致，
  无任何数值漂移。
- 旧 `readout-extra.log` R1 因引号误写为 `''OFFLINE-100''` 报 sqlite 解析错；本次以正确引号
  补测（`.tmp/aba/readout-recheck-r1.log`），拿到带表头的原样 5 行，内容与 §1/§6 一致。

## 6. 伪造试验（仅副本，规范卷全程 `:ro` 且事后核对）

见 C3 反证段：在 /tmp 的 A2 **副本**上单字段翻转 `level-name`，tuple 即不相等、副本摘要与已封
manifest 不符；规范卷 sentinel 全程 `data writable: False`，规范 `server.properties` 的
`level-name=world` 复量未变，副本目录用后即删（`.tmp/aba/forgery-copy.log`）。

## 7. 四态划分与边界（不声称闭合）

- **已在卷上（真实封证）**：seq1-seq5 五份 `SEALED` bundle（含两份早期 HANDSHAKE_TIMEOUT
  失败）+ 热身 run 的账本行；三段 bundle 字节即本卡规定的产出。
- **仅在分支**：本记录文档（`docs/p0-offline-100-a-b-a-run-2026-09-27.md`），随本提交在
  `codex/minekin-evidence` 上；主干未动。
- **人工判读成立但未登记**：C1-C5 五条作为 §2 的人工读数全部成立。
- **仍缺载体 / 未验证**：跨 bundle 的三段链判断载体（需扩展 `minekin.p0.evidence.v1`，主控
  保留）；`world_context_id` 的链上真值（全卷 null）；「首尾 A 同一获确认 context」目前只有
  旁证；OFFLINE-090 侧真跑（本卡未触及）；registry 父行变绿——以上任何一项都**没有**被本卡
  完成或声称完成。OFFLINE-100 未闭合，是否闭合由主控凭本记录裁决。
