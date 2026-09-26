# V1201-AUTO-PATH-STATUS-WIRING-001 — 把 `--enable-status` 接进 `domain.sh` 对受控启动器的调用面（H lane，H3）

日期：2026-09-27。执行 lane：H（test Harness）。
基线：main @ `6ce9f065d6d98e824c6b6d10d08901ce5a2b5f54`（本 worktree `git rev-parse HEAD` 实读一致）。
分支：`codex/minekin-auto-path-status-wiring`，worktree `../minekin-wt-h3`。
改动面：仅 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py` 与本记录。
未动：`tools/**`（含 `run_controlled_server.py`）、产品 `src/**`、case fixture、registry、`mandatory`、
任何判据/门禁、任何历史日期记录、`test-orchestrator/**` 里除 `domain.sh` 以外的文件。
规范卷 `minekin-runner-data` **全程未挂载**（连只读都没有；此刻归 E lane）；容器切片只用本 lane
自建卷 `minekin-h3-20260927`。本卡不产生任何封存证据。文中不出现任何外部地址；未打开、未引用
`.tmp/local-test-server.txt`。

## 缺陷（三处原文，先读再改）

1. `tools/run_controlled_server.py`（H2 已合入 `main` @ `6ce9f06`）：status 应答已是具名 opt-in —
   `DEFAULT_ENABLE_STATUS = False`、`--enable-status`、写后回读打印
   `enable-status: asked for <x>, the settings written say <y>`、落盘前具名拒止
   `status_switch_refusal(...)`。记录：`docs/validation/v1201-controlled-server-status-knob-2026-09-27.md`。
2. `test-orchestrator/runner/domain.sh`（base @ `6ce9f06` 第 565 行）：runner 起受控服务器的
   `python /src/tools/run_controlled_server.py ...` 调用**不传** `--enable-status`。
3. 同文件（base 第 632-641 行）：auto 路径（`-n "${auto_bundle}"`）读回 `server.properties` 的
   `enable-status`，非 `true` 即在起客户端之前具名早停，原文
   「the controlled-server tool has to make it answer (registered separately)」。
   被登记的那张卡（H2）已合入 ⇒ 本卡把旗标接进调用面；早停护栏**保留**。

## 改动（语义按 M 钉死，未自行扩大）

`domain.sh` 受控服务器分支新增（逐字）：

```bash
    status_args=()
    if [ -n "${auto_bundle}" ]; then
        status_args=(--enable-status)
    fi
```

并在 `run_controlled_server.py` 调用面追加一行展开 `"${status_args[@]}" \`。谓词与第 638 行早停
完全相同（`-n "${auto_bundle}"`）；非 auto 的 run（含按设计跳过早停的黑洞分支——它起的是
`run_silent_listener.py`，根本不经过受控启动器）不传，保持默认 `false`。无条件全开被拒
（见提交 trailers）。早停读回的是磁盘文件而不是请求，原样保留。

## 先量红（base 脚本，受控镜像真 JVM）

容器与镜像：`minekin-runner:local`（id `b67a4d917306`），1.21.4 默认 recipe；
逐字驱动脚本 `.tmp/h3-auto-run.sh`（同一条命令在红/绿两态复用）：

```bash
#!/usr/bin/env bash
# H3 driver: one minimal auto-shape run through domain.sh, exactly as it is on disk.
# The auto run is the one the G2 early-stop is asked about; this script only shows
# the readings the run itself produced. Nothing here mounts the canonical volume.
set -uo pipefail
export MINEKIN_HOME=/data PYTHONPATH=/src/src LD_LIBRARY_PATH=/opt/sqlite/lib
# `run.sh` forwards the account name into the container; the product config requires
# it and has no default, so the driver names it the same way (the whitelist default
# in domain.sh is `Kin` either way).
export MINEKIN_USERNAME="${MINEKIN_USERNAME:-Kin}"
export MINEKIN_DOMAIN_SECONDS="${H3_SECONDS:-40}"

# The ledger check in domain.sh names this run through exactly one Kin root, and a
# fresh lane volume has none yet; `init` is the same preparation `run.sh init` does.
python -m minekin_core init --kin-id kin-h3 >/tmp/domain-init.log 2>&1 || tail -3 /tmp/domain-init.log

bash /src/test-orchestrator/runner/domain.sh session start \
    --auto-bundle /src/tests/fixtures/registry/reviewed-tested-bundles.json \
    --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server.json
rc=$?
echo "H3: domain.sh rc=${rc}"
echo "H3: server tool log (/tmp/domain-server.log, tail 30):"
tail -n 30 /tmp/domain-server.log 2>/dev/null || echo "(absent)"
latest_run="$(ls -d /data/server-runs/run-* 2>/dev/null | sort -V | tail -1)"
echo "H3: newest run directory: ${latest_run:-none}"
if [ -n "${latest_run}" ] && [ -f "${latest_run}/server.properties" ]; then
    echo "H3: enable-status line read from the run directory itself:"
    grep -n '^enable-status=' "${latest_run}/server.properties" || echo "(no such line)"
fi
if [ -f /tmp/domain-session.err ]; then
    echo "H3: session stderr (/tmp/domain-session.err, tail 20):"
    tail -n 20 /tmp/domain-session.err
fi
exit "${rc}"
```

宿主侧调用（构造中途 `/src` 挂可写以便 `.tmp/` 驱动与日志落盘可查）：

```bash
export MSYS_NO_PATHCONV=1
REPO="$(cygpath -m /c/Users/darling/Documents/agent_work/minekin-wt-h3)"
JAR="${REPO}/.tmp/mc-1.21.4-server.jar"
docker run --rm --entrypoint /bin/bash -w /src \
  -v "${REPO}:/src" -v minekin-h3-20260927:/data -v "${JAR}:/server/server.jar:ro" \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -e H3_SECONDS=30 \
  minekin-runner:local -lc 'bash /src/.tmp/h3-auto-run.sh'
```

诚实记录两轮不算读数的测错（原始输出保留为过程材料）：

- 第一轮（`.tmp/h3-red-auto.log`）：`/server/server.jar is missing; download the pinned server
  jar first`，rc=1。镜像不烘焙 jar（实测镜像内 `/server` 不存在），jar 由宿主按 `run.sh` 的
  方式具名挂载；该轮在服务器 ready 之前就终止，根本没走到 enable-status 读数行，不构成红读数。
  随后用仓库自带通道取料：`uv run --frozen python tools/verify_supply_chain.py --version 1.21.4
  --max-bytes 120000000 --save-server .tmp/mc-1.21.4-server.jar` → `ok com.mojang:server:1.21.4
  56880250 bytes`、`Supply chain: OK`，落盘 jar 与 recipe 钉摘要一致。（该下载是制品 CDN 的
  钉摘要取料，不是连接/探测任何 Minecraft 服务器。）
- 绿态第一次重放（`.tmp/h3-green-auto.log`）：容器里没导出 `MINEKIN_USERNAME`，
  `minekin init` 与 session 都按 CONFIG 具名拒绝，run 停在
  `this run cannot name its ledger (found 1)`。该轮证明的是**已经跨过** enable-status 早停
  （同轮确实打印了 `enable-status=true`）但驱动缺账号变量，不作为最终绿读数；驱动补
  `MINEKIN_USERNAME` 后重放取下列绿读数。

红读数（base `domain.sh` @ sha1 `0eb3f55dfa10d686553ff1da8f514e5f5266f198`，原始输出
`.tmp/h3-red-auto2.log`）：

```text
domain: server run directory /data/server-runs/run-1
domain: server ready
domain: the controlled server reports enable-status=false
domain: the auto path needs this server to answer status and it reports enable-status=false; the controlled-server tool has to make it answer (registered separately), so the run stops before the client starts
H3: domain.sh rc=2
enable-status: asked for false, the settings written say false
14:enable-status=false
```

即：真 JVM 起服并报 ready（门不是恒绿，也不是虚构）；回读为 `false`；auto run 按具名早停
rc=2、客户端未起；run 目录自身的 `server.properties` 第 14 行同为 `false`。

## 改绿（同一驱动形状，wired `domain.sh`）

`.tmp/h3-green-auto2.log`：

```text
domain: server run directory /data/server-runs/run-3
domain: server ready
domain: the controlled server reports enable-status=true
domain: the session never became playable within 30s (the session exited first)
H3: domain.sh rc=0
enable-status: asked for true, the settings written say true
14:enable-status=true
H3: session stderr (/tmp/domain-session.err, tail 20):
{"category": "SUPPLY_CHAIN", "component": "cli.auto_session", ..., "message": "4120 of 4120 artifacts are missing and would cost 523788383 bytes; pass --max-bytes deliberately rather than let a session start download them by accident [BUDGET_UNDECLARED]", "operation": "session start --auto-bundle", ...}
```

要点：打印 `enable-status=true` 并**跨过**早停（护栏行未触发）；受控启动器自报
`asked for true, the settings written say true`；run 目录第 14 行实录 `true`。客户端 session
真跑到了 auto 路径自己的下一个具名前沿：`BUDGET_UNDECLARED`（4120 件制品 / 523,788,383 字节，
未带 `--max-bytes` 故拒绝顺手下载）。该前沿在 `src/minekin_core/cli/auto_session.py` 的
顺序里位于状态探针与摘要门**之后**（其 docstring 原文：该拒绝 "only appears after the probe
and the digest gate"）——即 auto 路径这次真的拿到了服务器 status 读数，H2 记录「停在何处」
点名的唯一剩余阻塞就此打开。本卡**不**代以真下载补 store（那是一个 523 MB 的具名预算决定，
不属于本卡语义），停在被具名照亮的那一步如实上报。

对照组（非 auto，`--profile` 形状，驱动 `.tmp/h3-nonauto-run.sh`，原始输出
`.tmp/h3-control-nonauto.log`）：

```text
domain: the controlled server reports enable-status=false
enable-status: asked for false, the settings written say false
14:enable-status=false
H3: domain.sh rc=0
```

旗标没有无条件扩散：非 auto run 照旧拿默认 `false`（且按设计不触发 auto 早停）。

## 需要具名记录的新停点：auto + `--online-mode true`

加了旗标后，若同一个 auto run 再强制 `MINEKIN_DOMAIN_ONLINE_MODE=true`，调用面变成
`--enable-status --online-mode`，正是 H2 工具具名拒止的形状。驱动 `.tmp/h3-mismatch-run.sh`，
原始输出 `.tmp/h3-mismatch-auto-true-onlinemode.log`：

```text
H3: run directories before this shape: 3
domain: server run directory /data/server-runs/run-4
domain: the server exited before it reported ready
--enable-status asks the controlled server to answer a status ping, and this run forces the server to require session verification; that is the one shape this tool documents as a server its client must never get into (AUTH_MODE_MISMATCH), ...
H3: domain.sh rc=1
H3: run directories on the volume: 3
```

即：具名拒绝在落盘前发生（run 目录数前后都是 3，被预留的 `run-4` 没有被创建）；
`domain.sh` 停在 `the server exited before it reported ready`，rc=1，并把拒绝原文透出。
**没有**为了让这个形状变绿而悄悄不传 `--online-mode`——AUTH_MODE_MISMATCH 场景的产生通道
（`MINEKIN_DOMAIN_ONLINE_MODE`）保持完整；该形状现在与 H2 工具层的具名拒绝一致地停得更早。
（该形状需要早停之后的 auto 分支不覆盖它：它是拒绝→无服务器→起服等待循环具名退出。）

## 契约测试与反向证明

`tests/contract/test_runner_scripts.py` 新增
`test_the_auto_path_hands_the_status_opt_in_to_the_controlled_launcher`（钉住：旗标全脚本恰好
出现一次；那一处位于 `status_args=()` + `[ -n "${auto_bundle}" ]` 守卫块内；受控启动器调用面
展开 `"${status_args[@]}"`；黑洞分支切片不含 `status_args`；读回后早停的 `if` 行与具名消息
原样在位）。改后该文件 `uv run --frozen pytest -q tests/contract/test_runner_scripts.py` →
**20 passed**（原有 19 + 新 1），rc=0。

反向证明四组，全部只在工作树里做、做完 `git checkout -- test-orchestrator/runner/domain.sh`
还原（`git status` 核实干净），不产生提交：

| 变异 | 结果 | 指名变红的断言行 |
| --- | --- | --- |
| RV-base：把缺陷在位的 base 脚本（`git show 6ce9f06:...`）放回施工位 | `1 failed, 19 passed`（`.tmp/h3-reversal-RV-base.log`） | `test_runner_scripts.py:593` `assert text.count("--enable-status") == 1` → `0 == 1` |
| RV-always：谓词翻成「永远传」（删守卫，无条件 `status_args=(--enable-status)`） | `1 failed, 19 passed`（`.tmp/h3-reversal-RV-always.log`） | `:600` 守卫块整体匹配 → 缺失（注意 `:593` 计数仍为 1，非空转靠的就是这条结构断言） |
| RV-never：谓词翻成「永远不传」（守卫保留、删赋值） | `1 failed, 19 passed`（`.tmp/h3-reversal-RV-never.log`） | `:593` `count("--enable-status") == 1` → `0 == 1`（调用面展开仍在位，抓住的正是「旗标被悄悄摘掉」这一退化） |
| RV-guard：删掉读回后早停的 `if` 块（读数行保留） | `2 failed, 18 passed`（`.tmp/h3-reversal-RV-guard.log`） | 新测试 `:625` 与既有 G2 测试 `:563` 同时指名 `if [ -n "${auto_bundle}" ] && [ "${enable_status}" != "true" ]; then` |

另：红/绿两态的**活体**反向证据就是上面的红读数本身——护栏在 base 态真的触发（rc=2 具名早停），
在 wired 态读回 `true` 才放行；若 wired 后写入在别处被回退成 `false`，命中的正是 RV-guard 钉住
的那条早停（绿 run 里它跨过的是文件实录为 `true` 的目录）。

## 门禁（本 worktree，`uv sync --locked --dev` 后全部 `uv run --frozen`）

| 门 | 命令 | rc |
| --- | --- | --- |
| 语法 | `bash -n test-orchestrator/runner/domain.sh` | 0 |
| lint | `uv run --frozen ruff check .` | 0（All checks passed!） |
| format | `uv run --frozen ruff format --check .` | 0（342 files already formatted） |
| 类型 | `uv run --frozen pyright` | 0（0 errors, 0 warnings, 0 informations） |
| 边界 | `uv run --frozen python tools/check_boundaries.py` | 0（OK） |
| 判据 | `uv run --frozen python tools/check_case_assertions.py` | 0（140 registered） |
| fixture 摘要 | `uv run --frozen python tools/verify_fixture_digests.py` | 0（OK） |
| 工作流钉 | `uv run --frozen python tools/check_workflow_pins.py` | 0（OK） |
| 空白 | `git diff --check` | 0（干净） |
| 针对测试 | `uv run --frozen pytest -q tests/contract/test_runner_scripts.py` | 0（20 passed） |
| 全量 | `uv run --frozen pytest -q` | 0（**2535 passed, 3 skipped in 352.58s**；三个 skip 为主干既有平台跳过 `test_orphans.py:686`、`test_silent_listener.py:123`、`test_tested_provenance.py:354`，未新增；2535 = H2 合入后的 2534 + 本卡新增 1 条契约测试。全量跑在四组反向证明全部 `git checkout --` 还原之后单独跑，`git status` 先核实干净） |

## 停在何处（诚实边界）

- **端到端 auto JOIN 仍未真跑**：绿 run 停在 `BUDGET_UNDECLARED`（补 store 是 523 MB 的具名
  预算决定，不归本卡）；status 盲区这一层的阻塞已实测打开。
- **未测**：`--enable-status` 与 1.20.1 recipe 的容器组合（本卡活体只跑 1.21.4 默认 recipe）；
  黑洞分支的活体 run（旗标进入不了该分支是结构事实，由契约切片断言钉住，未单独活体重放）；
  `--enable-status` + `--resource-pack` 同时开启的 domain 形状（H2 已在单元层证互不影响）；
  任何 seal（规范卷与独占窗口不在本卡允许面，全程未挂载该卷）。
- auto + `--online-mode true` 的形状现在停在落盘前的具名拒绝（rc=1 于 domain.sh 层），这是
  本卡改动引入的**新的、更早的**具名停点，已如实记录，不加宽、不绕过。
- 全程未连接、未探测任何外部或用户的 Minecraft 服务器；文中不出现任何 IP:port 形式的外部地址。

## 四态声明

`domain.sh` 调用面接线与其契约测试：**仅在分支**（`codex/minekin-auto-path-status-wiring`，
未合入 main，等待主控双审）。红/绿/对照/mismatch 四组读数：**真实测量**（受控镜像、真 1.21.4
JVM、本 lane 自建卷、逐字驱动脚本）。**真实封证：无** —— 本卡不产生任何 sealed evidence。
端到端 auto-bundle 真 JOIN 与补料后的绿灯：**尚未验证**（如「停在何处」）。
本记录不宣称 Minekin 完成，不宣称任何门禁点亮。
