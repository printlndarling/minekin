# H1l `V1201-RUN-SH-FORWARD-CONTROLLED-SERVER-JOIN-NAME-001` — `run.sh` 转发专服加入名：读数与反证

日期：2026-09-27。基线：`ac1d7fb`（= 动手时远端 `main`，H1k 合入后；动手期间 `main` 又前进到
`4a2778f`，全是 handoff/账目文档，与本卡允许面零重叠，本分支不 rebase、不 merge——合入复审归 M）。
分支：`codex/minekin-h1l-forward-join-name`。规范卷 `minekin-runner-data` 全程只出现在门载荷一条
`-v ...:/data:ro` **只读**挂载里，未建 attempt、未建 bundle；活体一律走 lane 私有卷 `minekin-h1k-live`。

## 0. 动手前现场复量与改面

- 工作树 `C:\Users\darling\Documents\agent_work\minekin-wt-h1k`：`git status --porcelain` 空、
  `HEAD = 84648c0f718985c12de3b49697c229f999b0b7d1`（H1k 分支头），干净 ⇒ 才允许起分支。
- `git fetch origin && git checkout -b codex/minekin-h1l-forward-join-name origin/main` ⇒ HEAD `ac1d7fb`。
- 改面（`git diff --numstat`，全仓只有这两个文件 + 本记录）：
  - `test-orchestrator/runner/run.sh` **+10 / −1**：`domain` 分支 `EXTRA_ARGS` 名单末尾加
    `-e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`（裸声明，写法与 H1j 那四名逐字同形），
    加注释点名「读了不转发 ⇒ run 跑完、封了、却是另一个场景的证据」这一族缺陷。未铸任何默认值。
  - `tests/contract/test_runner_scripts.py` **+25 / −26**：按登记自己的注释处理——**删登记，不删断言**。
    `registered_gap = {JOINER_CONTROLLED_SERVER_KNOB}` 及其 `not in delivered` 反向断言删除；
    该名字改为**逐一要求已转发**（`JOINER_CONTROLLED_SERVER_KNOB in delivered`，与四名同格同法），
    `read - delivered == set()` 与 `delivered - read == set()` 双向集合差保留，断言与注释全程
    逐字引用 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`。`JOINER_CONTROLLED_SERVER_KNOB`
    常量本体与其余 H1k 测试（读数/铸法/guard/反恒真）一字未动。
  - `domain.sh` 盘上字节 = `git show origin/main:...` = `e1d8dbb98d5f760db5c2583f001941e48485e0240f61b8061120504c36714015`
    （动手前后各核一次，**0 行**）；`src/**`、`tools/**`、fixtures、registry、`mandatory`、封存 schema **0 行**。
- 字节身份（交付候选，盘上）：`run.sh` = `10681b18fac76f8bc2e9e00d9efa36e2c1dfdff3cd38f32138bbfa705e446bdf`（189 行）；
  `test_runner_scripts.py` = `e33a1da96a53cc2a1c1d66d244d6115ac8170a3072dcf3d5b3be476d0e0349ca`（盘上 CRLF 形态）。
  按主干 §12 点名的口径：`*.py` 未钉 `eol=lf` 且本检出 `core.autocrlf=true`，库内 blob 摘要以
  `git show <sha>:<path> | sha256sum` 为准，与盘上值不同是行尾形态差，不是内容差。

## 1. 核心验收：一次经真实 `run.sh` 的形状读（不是静态断言顶替）

镜像 `minekin-runner:local`，宿主机 Git Bash，`MINEKIN_RUNNER_DATA=minekin-h1k-live`（lane 私有卷），
其余只设点名的旋钮，命令直接是仓库里的 `run.sh`：

- **live-1（只设新名，无加入者 ⇒ guard 第一条具名拒止）**：

```text
MINEKIN_RUNNER_DATA=minekin-h1k-live MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1 \
  bash test-orchestrator/runner/run.sh domain session start --profile /src/tests/fixtures/launcher/1.20.1.json
rc=2
domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER names where a joining client goes and this run has none (MINEKIN_DOMAIN_JOIN is unset); refused rather than carried as a knob that does nothing
```

  这行拒止只可能在 `join_on_controlled_server_asked=1` 时打印 ⇒ 容器里的 `domain.sh` 确实经
  `run.sh` 的转发看见了这个名字（H1k 之前它读到的是空、走的是「not asked for」）。全文
  `.tmp/h1l-live-forwarded.log`。
- **live-2（新名 × 首快照拒止同给 ⇒ 第七条组合具名拒止，两名同点）**：

```text
MINEKIN_RUNNER_DATA=minekin-h1k-live MINEKIN_SERVER_JAR=C:/Users/darling/Documents/agent_work/minekin/.tmp/mc-1.20.1-server.jar \
  MINEKIN_DOMAIN_JOIN=kin-h1l-probe MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1 MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1 \
  bash test-orchestrator/runner/run.sh domain session start --profile /src/tests/fixtures/launcher/1.20.1.json \
       --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json
rc=2
domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER and MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT name two destinations for one wait; the chain answers the snapshot refusal before any joining client is sent, so the prepared joiner would never go -- refused rather than carried as a knob that does nothing
```

  两个都是 wrapper 转发的名，第七条在**任何 JVM、任何 run 目录之前**回答 ⇒ 全程未起服、未起
  client、未写 `/data`。规范卷未出现在这两条命令里；未连接任何用户远程服务器（本轮没有读
  `.tmp/local-test-server.txt`，本文档无任何 IP:port）。
- 起 run 前 `docker ps` 静默核验（空列表，rc=0），`docker version` rc=0（server 29.5.3）。

## 2. 默认关闭不变（未设 ⇒ 注入集合与该名无关）

宿主未设该名时，用 `PATH` 上的 `docker` 桩 dump `run.sh` 的真实 argv
（`.tmp/h1l/argv-unset.txt`，rc=0）：名单里落下的是一条**裸声明**——

```text
-e
MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER
```

`grep 'MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER='` 计数 **0**（rc=1）：没有 `NAME=`、没有
`NAME=0` 这类铸名，`run.sh` 里「不把未给的值铸成字符串」的既有语义守住。docker 对裸 `-e NAME`
的既定语义另用真实 docker 探针量了一遍（同名两名，宿主不设 ⇒ 容器 `ABSENT`，rc=0；宿主设
`1` ⇒ 容器收到 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`，rc=0）。因此未设场景下容器收到的
环境集合与本卡之前逐字相同，H1k 的默认关闭路径字节等值不受影响（`domain.sh` 本轮 0 行，§0）。

## 3. 反证两则（各自红在该红的案上；全程无 `git checkout --`/`restore`/`reset`/`stash`）

种桩前 `cp test-orchestrator/runner/run.sh .tmp/h1l/run.sh.h1l-pristine`（sha256
`10681b18…`，与本卡交付字节相同）；两则还原后 `sha256sum` 均打印
`RESTORED: sha256 matches pristine (10681b18…)`。全过程 `bash .tmp/h1l/counterexamples.sh`
（log `.tmp/h1l/counterexamples.log`）。

- **CE(a)：把 `run.sh` 里那一行去掉** ⇒ 契约案
  `tests/contract/test_runner_scripts.py::test_every_knob_the_harness_reads_is_one_the_wrapper_hands_it`
  **红（pytest rc=1，`1 failed in 0.17s`）**，错误消息逐字点名这件事：
  `run.sh stopped forwarding MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER: a knob that is read and not
  delivered arrives empty, takes domain.sh's 'not asked for' branch, and the run seals evidence for
  a scenario that never happened`。集合差本体另以 shipped 解析器在变异字节上直接求值：
  `read - delivered = ['MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER']` ⇒ 非空，`set-difference empty?
  False -> RED as required`（该案由逐名断言先答，集合差在同一守卫里同步变红，两格都留了字面量）。
  `bash -n` 在变异体上仍 rc=0——红的是语义，不是语法。
- **CE(b)：把未设值铸成无条件 `NAME="${NAME:-}"` 注入** ⇒ §2 的默认关闭那一格**红**：同一
  stub dump 下 `grep 'NAME='` 命中第 72 行 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=`（rc=0
  = 命中 = 该格应红；对照：还原后的干净字节同一 grep 返回 rc=1/0 命中，证明该格敏感而非恒真）。
  契约集合差测试在这具变异体上**保持绿**——它管的是名单齐不齐，铸名恰好是它看不见的轴，
  这正是 H1j 当年用 argv 层读数、本卡沿用同一读数的原因，如实记。

## 4. 全部门（现读 `ci.yml` `python` job 的 `- run:` 清单，逐道单步、每题单独打印真实 rc）

| 门 | 命令 | 真实输出（末行） | rc |
| --- | --- | --- | --- |
| ruff check | `uv run --frozen --offline ruff check .` | `All checks passed!` | **0** |
| ruff format | `uv run --frozen --offline ruff format --check .` | `366 files already formatted` | **0** |
| pyright | `uv run --frozen --offline pyright` | `0 errors, 0 warnings, 0 informations` | **0** |
| pytest 全量 | `uv run --frozen --offline pytest` | `2737 passed, 1 warning in 417.05s` | **0** |
| 边界 | `uv run --frozen --offline python tools/check_boundaries.py` | `Minekin package dependency boundaries: OK` | **0** |
| 判据 | `... tools/check_case_assertions.py` | `Case assertion implementations: OK (150 registered)` | **0** |
| fixture 摘要 | `... tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK` | **0** |
| workflow pins | `... tools/check_workflow_pins.py` | `Workflow pins: OK` | **0** |
| wheel | `uv build --wheel`（离线窗口加 `--offline`） | `Successfully built dist\minekin_core-0.0.0-py3-none-any.whl` | **0** |
| wheel 边界 | `... tools/check_wheel_boundary.py dist/*.whl` | `Wheel oracle boundary: OK` | **0** |
| CLI | `uv run --frozen --offline minekin --help` | `usage: minekin [-h] ...` | **0** |
| shell | `bash -n test-orchestrator/runner/run.sh`（反证还原后的最终字节） | 无输出 | **0** |
| 空白 | `git diff --check` | 无输出 | **0** |

每道的完整输出存 `.tmp/h1l/gate-*.log`。全量 pytest 单跑，不与任何 docker 活体重叠。

## 5. 门载荷一对（本卡字节，规范卷 `:ro`，只读）

`docker run --rm -v <本树>:/src:ro -v minekin-runner-data:/data:ro -e LD_LIBRARY_PATH=/opt/sqlite/lib
-e PYTHONPATH=/src/src minekin-runner:local -lc 'python tools/report_promotion.py --data-root /data'`
（挂载前 `docker ps` 空列表核验）：

```text
rc(report_promotion)=1            ← 按构造 blocked（REQUIRED_CASE_NOT_REGISTERED），本卡不注册 case、不翻 mandatory
文档 103921 字节；{"work_packages","overall"} 子集 json.dumps(sort_keys=True) = 6051 字节
gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
```

与主干钉住的基线**逐字相同** ⇒ 门在本卡字节上一字未移；`check_case_assertions` 仍 `150 registered`
（§4 实测）。材料 `.tmp/h1l/gate-payload-doc.json`。

## 6. 复现命令（Git Bash）

```text
# 第 1 格（真实形状读；私有卷，规范卷不出现在命令里）
MINEKIN_RUNNER_DATA=minekin-h1k-live MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1 \
  bash test-orchestrator/runner/run.sh domain session start --profile /src/tests/fixtures/launcher/1.20.1.json
# 第 2 格（默认关闭 argv 读；docker 桩在 PATH 前）
env -u MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER PATH="$PWD/.tmp/h1l/stub:$PATH" \
  bash test-orchestrator/runner/run.sh domain session start --profile /tmp/x.json
# 第 3 格（反证，自带备份/还原/sha 核对）
bash .tmp/h1l/counterexamples.sh
# 门载荷（唯一一条规范卷 :ro 读）
docker run --rm --entrypoint /bin/bash -v <tree>:/src:ro -v minekin-runner-data:/data:ro \
  -e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src -w /src minekin-runner:local \
  -lc 'python tools/report_promotion.py --data-root /data'
```

（`.tmp/` 内桩、dump、log 全部未跟踪、不进仓。live 挂载姿势按 M 已量过的坑：`-v` 源路径写正斜杠 +
`MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`，写成反斜杠得到的是 rc=127 的 daemon 报错而非镜像坏。）

## 7. 四态封顶

- **仅在分支、待 M 复审**：本卡全部验收（转发、删登记、默认关闭、真实形状读、两则反证、
  全部门、门载荷）都在 `codex/minekin-h1l-forward-join-name` 的字节上量得，各 rc 见上文。
- 真实封证：**0**。本卡未写规范卷、未建 attempt/bundle、未注册 case、未动 registry/`mandatory`/判据。
- 未闭合格：无已知未闭合——本卡的验收面全部有字面读数；H1k ③ 里那两格「未验证」（整轮永不加入名的
  专用对照、同 run 主持有者读数不变）按 §2.16 口径继续归 V5′，不在本卡允许面内，不冒领。
- 本卡没有发生的事：没连过任何本 run 之外的地址；`domain.sh`、`tools/**`、`src/**`、任何
  case/fixture/registry/封存 schema、主干文档全程 0 行；旧材料与失败材料（H1k 的
  `live-a…live-f`、`run-1…run-5`、各反证 log）原地未动，本卡新增材料一律落在 `.tmp/h1l*`。
