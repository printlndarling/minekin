# H1m `V1201-LAN-SECOND-NAMED-PROBE-TARGET-001` — `domain.sh` 第二名具名探测：读数、反证与门表

日期：2026-09-27。基线：`dc0067cdcbc962266750c5ccbaa5535a0972945d`（含 H1l 合入 `d95e59d` 之后的
主干）。分支：`codex/minekin-h1m-second-probe-target`。本卡不 rebase、不 merge——合入复审归 M。
规范卷 `minekin-runner-data` 全程只出现在门载荷的 `-v ...:/data:ro` **只读**挂载里，未建 attempt、
未建 bundle；活体一律走 lane 私有卷 `minekin-h1m-live`（三式跑完，容器已退出，不再起重跑）。

## 0. 现场复量与改面（交付时逐项复核，非记忆值）

- 工作树 `C:\Users\darling\Documents\agent_work\minekin-wt-h1m`：`HEAD = dc0067cd…`、
  `git status --short` 恰三个脏文件，无未跟踪外溢。
- 改面（`git diff --numstat`，全仓只有这三个文件 + 本记录）：

| 文件 | numstat | 交付字节 sha256（盘上） | 主干前值 |
| --- | --- | --- | --- |
| `test-orchestrator/runner/domain.sh` | +43 / −0 | `e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954` | `e1d8dbb98d5f760db5c2583f001941e48485e0240f61b8061120504c36714015` |
| `test-orchestrator/runner/run.sh` | +6 / −1 | `323f521a3141fa3c613d02b93500612aa1ec943a2467a4da1d4a5080f1669126` | `10681b18fac76f8bc2e9e00d9efa36e2c1dfdff3cd38f32138bbfa705e446bdf` |
| `tests/contract/test_runner_scripts.py` | +216 / −1 | `86b216853a6cf8bf0edce27d372870808e89973e71b34d96d0f899b2c028a3cb` | `e33a1da96a53cc2a1c1d66d244d6115ac8170a3072dcf3d5b3be476d0e0349ca`（盘上 CRLF 形态；库内 blob 为 `153edb14ee3abd22273ab8936bde3a935b7625df5f371338fe4fa924eab033b7`，`git show HEAD:… \| sed 's/$/\r/' \| sha256sum` 即得前值，行尾形态差不是内容差——口径同主干 H1l 记录 §0） |

- 合计 **+265 / −2**，与 M 独立量过的在飞改面逐字一致。`src/**`、`tools/**`、`tests/fixtures/cases`、
  registry、`mandatory`、判据、封存 schema **0 行**；未连接任何远程服务器；未对这三个文件做过任何
  `checkout --`/`restore`/`reset`/`stash`/`clean`。

## 1. §2.29 派工接口逐格验收（行号为交付字节现读）

| 格 | 要求（§2.29） | 交付字节上的实现与取读处 |
| --- | --- | --- |
| 新旋钮绑定 | `MINEKIN_DOMAIN_PROBE_SECOND`，默认关闭 | `domain.sh:35` `probe_second="${MINEKIN_DOMAIN_PROBE_SECOND:-}"`，空默认、不铸值 |
| guard 读的第一名 | 与 forge 同一表达式 | 第一名是 `${probe:-${player}}`；`use_target` 绑在 `domain.sh:141`（主干既有，guard 直接读） |
| 具名早退①：第二名 == 第一名 | 在落盘前，不把下游 rc 当判据 | `domain.sh:802–:826` guard 区段（`second-probe-guard begin/end` 为契约测试的提取锚），`:816` 打印具名消息、`exit 2`；真跑见 §2 refuse-1 |
| 具名早退②：`USE_TARGET × 第二名` | tools 侧那句是兜底不是替代 | 同区段 `:821` 具名消息、`exit 2`；真跑见 §2 refuse-2 |
| forge 默认等值 | 未设 ⇒ `probe_args` 那行与旧字节逐字相同 | `domain.sh:833` 与主干 `:715` 逐字同串：`probe_args=(--probe-player "${probe:-${player}}" --probe-every-seconds "${probe_seconds}")` |
| forge 追加 | 设了 ⇒ 在该行**之后**追加第二个 `--probe-player`，不替换第一个 | `:834–:836`：`if [[ -n "${probe_second}" ]]; then probe_args+=(--probe-player "${probe_second}") fi`（区段 `:832–:837` `second-probe-forge begin/end`） |
| run.sh 转发 | 名单必须带上这个名，否则容器里读到空 | `run.sh:134` 名单末尾裸 `-e MINEKIN_DOMAIN_PROBE_SECOND`（派工文本里 `MINEKIN_PROBE_SECOND` 系笔误简写，实发为全名），与 H1l 同族缺陷的防线：`test_every_knob_the_harness_reads_is_one_the_wrapper_hands_it` 双向集合差按名钉住 |
| 经 run.sh 的真实形状读 | 两名都被问过 | §4 live-A：同一 `server.log` 内 `Kin` 72 行、`Kin2` 66 行按名答题，均经 `run.sh` 转发进容器 |

契约侧新增/扩充（`tests/contract/test_runner_scripts.py`，宿主与容器各 94 案全绿，§5 门表）：
默认等值案扩充为**静态钉 + 驱动读**双格（`test_the_console_probe_is_a_default_and_the_status_switch_is_read`
新增 `tmp_path` 驱动半边，未设时实跑 forge 区段得单名 argv）；
`test_the_second_probe_name_rides_after_the_first_when_the_run_names_one`（追加序）；
`test_the_second_probe_refusals_are_shipped_verbatim_and_answer_before_any_write`（两条消息逐字 + 早退位置）；
`test_the_second_probe_guard_answers_the_pairs_it_cannot_ask_about[same-as-default-first]/[same-as-named-first]`
（具名 guard 真跑 rc=2）。

可复算命令（Git Bash，树根）：

```text
uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q
uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q \
  -k "second_probe or console_probe_is_a_default"
```

## 2. 三枚真跑的具名拒止（`.tmp/h1m/refuse-*.log`，逐字抄）

- **refuse-1（同名 ⇒ 具名消息 + `rc=2`）**：
  `domain: MINEKIN_DOMAIN_PROBE_SECOND names Kin, and that is the name this run already asks as its
  first probe target (MINEKIN_DOMAIN_PROBE, or the whitelisted account when it is unset); one run
  asking the same name twice is not a reading of two kins -- refused here, before anything is written`
- **refuse-2（`USE_TARGET × 第二名` ⇒ 具名消息 + `rc=2`）**：
  `domain: MINEKIN_DOMAIN_USE_TARGET places one block in the look of one probed kin and
  MINEKIN_DOMAIN_PROBE_SECOND adds a second probed name (Kin2); the pair does not say whose look the
  block is placed in -- refused here, before anything is written`
- **refuse-3（同容器产物缺位形状下仍先答）**：具名 USE_TARGET 消息 + `domain.sh rc=2`，随后核验
  `PROFILE-ABSENT` / `RUNDIRS-ABSENT` / `NO-JVM`（outer rc=0 为核验脚本自身）⇒ 拒止在任何 profile、
  任何 run 目录、任何 JVM 之前回答。

## 3. 三枚反证（`bash .tmp/h1m/counterexamples.sh`，log `.tmp/h1m/counterexamples.log`；全程无 restore/reset）

种桩前 `cp …/domain.sh .tmp/h1m/domain.sh.pristine`（sha256 `e04524d6…` = 交付字节）。三枚各自红在
该红的案上，每枚还原后均打印 `RESTORED: sha256 matches pristine (e04524d6…)`：

- **CE(a)** 删掉 `probe_args+=(--probe-player "${probe_second}")` 那行 ⇒ 独红
  `test_the_second_probe_name_rides_after_the_first_when_the_run_names_one`（`1 failed, 93 passed`，变异体上 `bash -n` rc=0——红的是语义）。
- **CE(b)** 破坏默认等值（追加丢掉空守卫 ⇒ 未设也多出 `--probe-player ''`）⇒ 独红
  `test_the_console_probe_is_a_default_and_the_status_switch_is_read`（驱动半边 `['--probe-pla…e-player',''] == […,'5']` 不等）。
- **CE(c)** 删同名拒止文本 ⇒ 三条具名案独红：`test_the_second_probe_refusals_are_shipped_verbatim_and_answer_before_any_write`、
  `[…guard_answers_the_pairs_it_cannot_ask_about(same-as-default-first)]`、`(same-as-named-first)`（`3 failed, 91 passed`）。
- **FINAL CHECK（交付字节驱动）**：`94 passed in 16.63s`，`pytest(pristine) rc=0`。

## 4. 三式活体读数（私有卷 `minekin-h1m-live`；**这是活体读数，不是 sealed bundle，不得被引作 LAN 第二客户端的同 run 封证**——封证是 V5′/E7 的活）

镜像 `minekin-runner:local`，`/src` 为本树只读挂载、`/data` 为私有卷；种子来自 V lane 已交付私有卷
`minekin-v4-join` 的**只读**挂载（`prep.sh`/`prep.log`，7565 blobs，kin `kin-h1m-host` init rc=0）。

- **live-A（两名真问）** `run-1/server.log` sha256 `1be9518be10cb42902ce242ca7be8d6ba853773c772030b1d8eae2b4a446fa1e`（274 行）：
  同一份日志内按名答题 `Kin` **72** 行、`Kin2` **66** 行；`Kin` 15:17:26 joined / 15:19:44 left，
  `Kin2` 15:17:27 joined / 15:19:38 left；首末读数分列（`Kin [-2.5d,-60.0d,-5.5d]`、`Kin2 [3.5d,-60.0d,0.5d]`）。
  run 文档 `"outcome": "BRIDGE_LOST"`，`rc=14`（停会话的预期姿势，与 H1k/H1l 同形）。
- **live-B（默认关闭）** `run-2/server.log`（304 行）：`Kin2` **未到场**——joined/left 只有 `Kin`，
  `Kin2` 按名答题 **0** 行；`rc=14`、`BRIDGE_LOST`。
- **live-B2（非恒真对照）** `run-3/server.log`（166 行）：`Kin2` **真到场并离场**
  （15:30:00 joined / 15:32:11 left），但按名答题行 **0** 行 ⇒ B 的「0 行」不是因为 `Kin2` 不可能在场。
  `rc=14`、`BRIDGE_LOST`。
  读数文件：`.tmp/h1m/live-{A-two-names,B-default-off,B2-default-off}.log` + 各自 `*-readout.txt`。

**不足申报（本卡记录内如实）**：三式 live 日志头部**没有打印 `domain.sh` 的 sha256** ⇒ 活体字节出处
靠摘要链而非日志直读：`.tmp/h1m/domain.sh.pristine` = `e04524d6…` = 交付字节；`prep.log`
（15:14:50Z，同一 `/src` 只读挂载、早于三式开跑）打印 `/src/test-orchestrator/runner/domain.sh` =
`e04524d6…`；三式之后 CE 各枚还原均打印 `RESTORED: sha256 matches pristine (e04524d6…)`。链条闭合，
但下一张卡的活体日志应直接打印被测脚本摘要。

## 5. 门载荷一对：PRE == POST（本卡不动 cases/registry/mandatory ⇒ 期望逐字相等）

- PRE：`.tmp/h1m/gate-payload-pre.json`，103,921 B（盘上时间戳 15:17Z；PRE 侧 rc 未单独落盘成
  `.run.log`，其 blocked-by-construction 形状与 POST 同一命令、同一挂载）。
- POST：`.tmp/h1m/gate-payload-post.json`，103,921 B；`gate-payload-post.run.log` 记 `rc=1`
  （按构造 blocked：`REQUIRED_CASE_NOT_REGISTERED` 族，与主干 §2.30 同一形状）。
- 子集摘要配对复算式（口径同 `tools/report_promotion.py` 输出的 `{work_packages, overall}` 子集，
  `json.dumps(sort_keys=True)` 后 sha256；等价手为主干树 `.tmp/trunk_digest.py`）：

```text
cd /c/Users/darling/Documents/agent_work/minekin-wt-h1m
uv run --frozen --offline python .tmp/h1m/pair_digest.py
# pre_subset_sha256 =cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
# post_subset_sha256=...同值...  ⇒ MATCH
```

  结果（本交付步补跑并落盘 `.tmp/h1m/gate-payload-pair-digest.log`，15:46:46Z，rc=0）：
  **PRE == POST == `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**，
  与 §2.19/§2.30 主干基线**逐字同值** ⇒ 门在本卡字节上一字未移。§2.29 留的「POST 没量到」欠账
  至此在本卡交付字节上闭合。`check_case_assertions` 仍 `150 registered`（§6 实测）。

## 6. 全部门表（每道单步跑、rc 单独读；末行逐字抄自 `.tmp/h1m/` 落盘日志）

| 门 | 末行读数 | rc | 日志 |
| --- | --- | --- | --- |
| ruff format 首跑 | `1 file would be reformatted, 366 files already formatted`（具名 `tests/contract/test_runner_scripts.py` 会被重排） | **1** | `gate-ruff-format.log` |
| ruff format 复跑（格式化后） | `367 files already formatted` | **0** | `gate-ruff-format-retry.log` |
| ruff check | `All checks passed!` | **0** | `gate-ruff-check-final.log` |
| pyright | `0 errors, 0 warnings, 0 informations` | **0** | `gate-pyright.log` |
| uv sync（离线校验） | `Resolved 18 packages in 2ms` / `Checked 18 packages in 78ms` | **0** | `gate-sync.log` |
| pytest 全量（宿主） | `2676 passed, 2 skipped in 327.92s (0:05:27)` | **0** | `gate-pytest-full.log` |
| 契约（宿主，ruff format 之后） | `94 passed in 17.44s` | **0** | `gate-contract-host-postformat.log` |
| 契约（容器 `minekin-runner:local`） | `94 passed in 1.72s` | **0** | `gate-contract-container.log` |
| 边界 | `Minekin package dependency boundaries: OK` | **0** | `gate-boundaries.log` |
| 判据 | `Case assertion implementations: OK (150 registered)` | **0** | `gate-case-assertions.log` |
| fixture 摘要 | `W00 schema and fixture digests: OK` | **0** | `gate-fixture-digests.log` |
| workflow pins | `Workflow pins: OK (every action is a commit, and each names its release)` | **0** | `gate-workflow-pins.log` |
| wheel 构建 | `Successfully built dist\minekin_core-0.0.0-py3-none-any.whl` | **0** | `gate-build.log` |
| wheel 边界 | `Wheel oracle boundary: OK (dist\minekin_core-0.0.0-py3-none-any.whl)` | **0** | `gate-wheel-boundary.log` |
| CLI | `usage: minekin [-h] {init,doctor,bundle,launch-plan,session,server,evidence,replay} ...` | **0** | `gate-minekin-help.log` |
| shell（最终字节） | `bash -n` `run.sh` / `domain.sh` 均无输出 | **0** | `gate-bash-n-run.log`、`gate-bash-n-domain.log` |
| 空白 | `git diff --check` 无输出（23:42:09Z 复跑亦空） | **0** | `gate-git-diff-check.log` |
| 门载荷 POST | `rc=1`（按构造 blocked）；子集摘要 MATCH（§5） | 1（预期） | `gate-payload-post.run.log`、`gate-payload-pair-digest.log` |
| 反证 FINAL CHECK | `94 passed in 16.63s`，`pytest(pristine) rc=0` | **0** | `counterexamples.log` |

全量 pytest 单跑，不与任何 docker 活体重叠；三式活体跑完容器已退出，交付时未再起。

## 7. 四态封顶

- **仅在分支、待 M 复审**：本卡全部验收（绑定、guard 双早退、forge 默认等值与追加、run.sh 裸转发、
  三枚反证、三枚具名拒止、三式活体、全部门、门载荷 PRE==POST）都在
  `codex/minekin-h1m-second-probe-target` 的字节上量得；合入与否由 M 独立复审决定，非本卡动作。
- 真实封证：**0**。未写规范卷、未建 attempt/bundle、未注册 case、未动 registry/`mandatory`/判据；
  §4 的三式是私有卷活体读数，不得被引作 LAN 第二客户端的同 run 封证（V5′ 第 4 条第一格仍在其后）。
- 未闭合格：无已知未闭合——验收面全部有字面读数；一处记录不足已在 §4 末尾具名申报
  （live 日志未打印脚本摘要，出处靠 pristine/prep 摘要链）。
- 本卡没有发生的事：没连过任何本 run 之外的地址；`src/**`、`tools/**`、`domain.sh` 之外的任何
  runner 脚本、任何 case/fixture/registry/封存 schema、主干文档全程 0 行；旧材料与失败材料
  （H1l/H1k 各 `.tmp/h1l*`、CE 日志、`domain.sh.pristine`、被退回的笔误简写记录）原地未动，
  本卡新增材料一律落在 `.tmp/h1m/`。
