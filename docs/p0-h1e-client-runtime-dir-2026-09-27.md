# H1e：把受控加入者客户端启动线上的 `XDG_RUNTIME_DIR` 从「只具名」升级为「真提供」，并把来源一起具名（H lane）

日期：2026-09-27（本轮全部读数当日实量）。
执行 lane：H（test Harness / runner）。
分支 `codex/minekin-client-env-readout`，起点 `de579ad`；`git fetch` 后 `git merge origin/main` 干净快进到
`0e497a9f951c7704c81ee807c7ef646b94e4b7fe`（= 派工时的 `origin/main`），实现提交 `0b820e0`。
工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-client-env`。

改面（`git diff --numstat 0e497a9..HEAD` 实读，加本记录恰三文件）：
`test-orchestrator/runner/domain.sh` +140/−1、`tests/contract/test_runner_scripts.py` +269/−9
（`.tmp/h1e-gates-fast.log` 里 `git diff --stat` 把两条各计为 141/278 行变更，合计 409 insertions/10 deletions）；本记录。
未碰：`tools/**`、`src/minekin_core/**`、`tests/fixtures/**` 与 `manifest.sha256`、case registry 的
`status`/`gaps`/`mandatory`、任何判据与门禁、`minekin.p0.evidence.v1` 的字段。
规范卷 `minekin-runner-data` 全程只以 `:ro` 挂载，且只挂在 M5 那一次只读探针上；
活体对照（CTL-A…F 与 red 侧）挂的是 `-v ${REPO}:/src:ro`，**没有挂任何数据卷**，读数与运行时目录都落在容器 `/tmp`。
本卡不含真跑：没有起受控 domain 运行、没有 attempt、没有 bundle、没有封证。

## 0. 一句话结论

harness 现在在**加入者客户端自己的那条启动线**上提供一个可用的 `XDG_RUNTIME_DIR`（合法值原样继承、
缺失/无效时建一个 mode 0700 的私有目录），并且 `client-environment.txt` 里每个深度多出一行
`XDG_RUNTIME_DIR_ORIGIN=`，把「这个值是容器给的」和「这个值是 harness 补的」分开具名。
**活体 JOIN 未测**：本卡没有任何真跑读数，`[0x1000E]` 是否消失归 V lane 复量。

## 1. 先量现状（改动前，base 字节 `0e497a9`）

原始记录 `.tmp/h1e-1-measure.log`（M1–M4）、`.tmp/h1e-2-volume.log`（M5，规范卷 `:ro`）、
`.tmp/h1e-5-base-red.log`（red 侧启动线重放）。
base 字节的 `domain.sh` sha256 = `fccf372e6ca5c831ac3a44773994efa4afc97d67c8b5f98078b4b17f20a82549`。

| 量 | 读数 |
| --- | --- |
| M1 容器自己 | `uid=0`、`XDG_RUNTIME_DIR is not in the container environment at all (<unset>)`、`ls: cannot access '/run/user/0': No such file or directory`；`env -u XDG_RUNTIME_DIR` 对照 ⇒ `present=[] value=[]` |
| M2 今天怎么办这件事 | 全 `domain.sh` 里提到这个名字的**只有一行**：`808:        for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do`（`client_environment_probe` 的具名循环，函数体 `:778-817`）。`grep -c 'XDG_RUNTIME_DIR="'` = 0、`grep -c 'export XDG_RUNTIME_DIR'` = 0、`grep -c 'chmod 700'` = 0 ⇒ **只有具名，没有任何提供** |
| M3 具名读数（活体） | 两深度真跑探针（`launch` 深度真过 `xvfb-run`）逐字含 `harness XDG_RUNTIME_DIR=<unset>` 与 `launch XDG_RUNTIME_DIR=<unset>`；正对照 `export XDG_RUNTIME_DIR=/tmp/h1e-measure-inherited` ⇒ 回读同值，探针确实只读不填 |
| M4 客户端环境的门 | Core 侧 `FORWARDED_VARIABLES = ('DISPLAY', 'XAUTHORITY', 'MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT')`；把 `XDG_RUNTIME_DIR` 设进环境后，被管客户端实际拿到的环境名集合是 `['DISPLAY','HOME','TEMP','TMP','TMPDIR','XAUTHORITY','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME']` ⇒ **`does XDG_RUNTIME_DIR cross that door? False`** |
| M5 那句话是谁写的 | 规范卷只读：`XDG_RUNTIME_DIR is invalid` 出现在 11 个文件里，其中 3 个是已封 bundle 的 `client/stderr.log`，其余是 `run/session/<id>/generation-1/logs/stderr.log`；样本首行逐字 `1:error: XDG_RUNTIME_DIR is invalid or not set in the environment.` ⇒ 写它的是**被管客户端进程**，不是 harness 的 shell |

M5 与 M4 合起来是本卡最重要的现状事实，必须在交付时就说清：
这条线索在客户端那一侧，而客户端的环境由 Core 从一份**封闭名单**构造、不隐式继承任何名字；
harness 能决定的只有自己那条启动线。因此本卡交付的是**这一半**，并把最后一格
（`XDG_RUNTIME_DIR` 进 `config.FORWARDED_VARIABLES`）登记为 M 面决定，不在本卡越界改。

red 侧（base 字节重放同一条启动线，末尾客户端换成打印自己环境的桩）：

```text
BASE: launch-line fragment sliced from base bytes, source lines 973-988
CLIENT-SEES XDG_RUNTIME_DIR=<unset> ORIGIN=<unset>
BASE readout:
    harness XDG_RUNTIME_DIR=<unset>
    launch XDG_RUNTIME_DIR=<unset>
```

即改动前被 exec 的那个进程**什么都没拿到**，读数两深度各 6 行、没有来源行。

## 2. 最小实现：只在加入者客户端的启动线上提供

新增 `provide_the_joiner_runtime_directory()`（`domain.sh:941` 起），调用点恰一处，
在 `name_the_joiner_client_environment` 之后、`"${joiner_launch_wrapper[@]}"` 之前（`join_the_published_world`，
现 `:1097`）：

- **继承优先**：`XDG_RUNTIME_DIR` 若已绝对、存在、是目录、可写 ⇒ 原样不动，`client_runtime_dir_origin=inherited`。
  五种不可用的情形分开报名（未设 / 设成空串 / 不是绝对路径 / 不是目录 / 不可写），
  其中「未设」与「设成空串」问的是环境本身（`${XDG_RUNTIME_DIR+set}`）而不是取过来的 local ——
  否则两者都塌成空串，正是 H1c 反对的那种塌法。
- **否则自己建**：`mktemp -d "${client_runtime_dir_base}/runtime.XXXXXX"` + 显式 `chmod 700` + 建后复核
  `-d && -w`，`client_runtime_dir_origin=provided-by-harness`。
- **放在 `/tmp/minekin-client-runtime/`，不放 `/data`**，理由（写在 `domain.sh:833-852` 的注释里）：
  `/data` 是运行的材料，Kin 的 run 目录里多出这么一个目录，将来任何 glob 运行目录的封存面都得学会躲开它 ——
  运行时目录不是证据，也不该成为可封存材料；规范卷本卡全程未写。`/tmp` 已经是这条线所有不可封存暂存物的去处
  （`/tmp/domain-join-session.err`、探针脚本本体），不新增去向。0700 是这个名字自身的要求，所以按 run 独占新建而不是复用共享目录。
- **不 export 进本脚本**：harness 自己没有窗口面需要向运行时目录注册；值只走 `joiner_runtime_dir_env`
  数组，展开在客户端那条 `env` 上（`domain.sh:1113`）。提供失败时数组留空 ⇒ 客户端拿到的和改动前一字相同，
  而不是 `<set-but-empty>`（那比 `<unset>` 更坏，看着像个值）。

## 3. 读数跟着升级：来源与值分开具名，三态不塌

探针（`client_environment_probe`）在三件套循环之后多写一行（`domain.sh:824-825`）：

```bash
        printf "%s XDG_RUNTIME_DIR_ORIGIN=%s\n" "${depth}" \
            "$(read_one CLIENT_RUNTIME_DIR_ORIGIN)" >> "${out}"
```

走的是 H1c 已有的 `read_one`，所以三态原样保留：harness 深度没被告知就写 `<unset>`（不是省掉这行，
也不是假装 `inherited`），`XDG_RUNTIME_DIR=` 空值仍写 `<set-but-empty>`。每深度 7 行。

## 4. 容器活体读数（最终发货字节，2026-09-27）

`.tmp/h1e-3-controls-final.log`。发货字节 sha256 = `9883a788f5f39008b208998d2b3833e9ea6ad511bfd35f9b63693daf1b9671a0`
（容器内 `/src/test-orchestrator/runner/domain.sh` 自读，与 `git show 0b820e0:...` 同字节）。
控制器 `.tmp/h1e-3-controls.sh` 用 `awk`/`python` 从**当次发货字节**按行范围切出准备段数据、两个函数、
以及客户端那条启动线本体，只把 `exec "$@"` 末端的真实客户端换成打印自身环境的桩 ——
所以 `CLIENT-SEES` 与读数都是真字节产出的，不是手抄副本。容器配方（无数据卷）：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" \
  -e PYTHONPATH=/src/src minekin-runner:local -lc 'bash /src/.tmp/h1e-3-controls.sh'
```

| 案 | 环境 | 量到的东西 |
| --- | --- | --- |
| CTL-A | 容器原样（名字未设） | 读数 `harness XDG_RUNTIME_DIR=<unset>` + `harness XDG_RUNTIME_DIR_ORIGIN=<unset>`；`launch XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.9cAvLi` + `launch XDG_RUNTIME_DIR_ORIGIN=provided-by-harness`；**被 exec 的进程自己报** `CLIENT-SEES XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.9cAvLi ORIGIN=provided-by-harness`；`stat -c %a` = `700 /tmp/minekin-client-runtime/runtime.9cAvLi` |
| **正对照** CTL-B | 调用方已有可用目录 `/tmp/h1e-ctl-inherited` | `..._ORIGIN=inherited`，两深度同一路径，`CLIENT-SEES` 同值，`runtime directories now under /tmp/minekin-client-runtime: 1`（没为这案新建第二个） ⇒ 合法值确实**没被换掉** |
| 反证 CTL-C | 设成一个不存在的路径 | 仍建新的、`ORIGIN=provided-by-harness`，且报名理由：`the name it would have inherited was unusable because it names no directory that is there (/tmp/h1e-ctl-does-not-exist)` |
| CTL-D | `XDG_RUNTIME_DIR=`（存在但空） | harness 深度 `XDG_RUNTIME_DIR=<set-but-empty>`（与 `<unset>` 不混，三态存活）；理由报 `it is set to nothing in the environment this script holds` |
| CTL-E | 提供不出来（base 设成 `/proc/no-such-place/...`） | 具名拒绝对账：`not provided, /proc/no-such-place/minekin-client-runtime cannot be created; the client keeps what it had, which was unusable because it is not set...`；`CLIENT-SEES XDG_RUNTIME_DIR=<unset> ORIGIN=<unset>`（**没有**塞一个空值进去），脚本继续跑完（case rc=0） |
| CTL-F | 模式实读 | `700 /tmp/minekin-client-runtime/runtime.*`（三个独立目录逐个 `stat`） |

出处对账：上表里的 `CLIENT-SEES`、两深度读数、`stat` 行与计数都在 `.tmp/h1e-3-controls-final.log`（最终字节那轮，
目录名 `runtime.9cAvLi` / `runtime.QgXTDf` / `runtime.iytzKd`）。CTL-C、CTL-D、CTL-E 引用的那三句
`domain: joiner runtime directory:` 报名原话出自**前一轮**容器对照 `.tmp/h1e-3-controls.log`
（同一函数、同一按行切分法，只是跑在最终字节定稿前，那轮的目录名是 `runtime.K4pf8H` / `runtime.9ZQ8qe` /
`runtime.c9maES`）；final 那轮日志没有重复抓这行 stdout。这句话的字节本体在
`domain.sh:952/969/986`，与所引片段逐字一致。

## 5. 契约测试与反证

新增三条（`tests/contract/test_runner_scripts.py`，沿用该文件既有命名风格）：

1. `test_the_joiner_launch_line_is_handed_a_runtime_directory` —— 启动线确实带上这个变量：
   函数存在且调用点恰一处、`joiner_runtime_dir_env` 里两行都在、`env "${joiner_runtime_dir_env[@]}"` 在客户端那条线上、
   继承的四道校验各自在、`chmod 700`、base 在 `/tmp` 且函数体内不出现 `/data`、
   全脚本 `export XDG_RUNTIME_DIR` 为 0、`if [ -n "${client_runtime_dir}" ]` 的空值护栏、
   以及顺序「具名读数 → 决定运行时目录 → wrapper 起进程 → `joiner_pid=$!`」。
2. `test_the_client_environment_readout_names_where_the_runtime_directory_came_from` —— 读数具名了来源：
   来源行只在探针里写一次（`count == 1`）、`CLIENT_RUNTIME_DIR_ORIGIN=` 全脚本只出现在客户端那条线（`count == 1`）、
   两个名字 `inherited` / `provided-by-harness` 都在字节里、来源行走 `read_one`、
   三件套 for 循环与四个缺失名原样健在（**没被压成一态**）、探针段仍是 5 处 `>> "${out}"`。
3. `test_the_runtime_directory_provision_is_not_an_always_true_claim` —— 非空洞性：同一对谓词在**发货字节上先判绿**，
   再对四个变异各自判红。

工作树里对**真文件**下手放的反证（`.tmp/h1e-4-reversal.log`，每次跑同一份契约测试）。
下手前实现字节已提交为 `0b820e0`、工作树是干净的，另存一份 `.tmp/domain-h1e-new.sh` 并核对 sha256；
还原用的是 `git checkout --`（此时它还原到已提交的实现字节，不是丢弃未提交的工作），
收尾 `git status --porcelain` 空、还原后 sha256 与 `0b820e0` 一致）：

| 变异 | 结果 |
| --- | --- |
| RV-a 删掉启动线数组里的 `XDG_RUNTIME_DIR="${client_runtime_dir}"` 一行（= 卡面要求的那枚「把 export 删掉」） | `2 failed, 25 passed`，红在 `test_the_joiner_launch_line_is_handed_a_runtime_directory` 与第 3 条 |
| RV-b 删掉探针里的 `XDG_RUNTIME_DIR_ORIGIN` 那两行 | `2 failed, 25 passed`，红在 `test_the_client_environment_readout_names_...` 与第 3 条 |
| RV-c 来源行还在，但把 `read_one` 换成 `${CLIENT_RUNTIME_DIR_ORIGIN}`（三态塌成一态） | `2 failed, 25 passed` |
| RV-d `client_runtime_dir_base=/tmp/...` 改成 `/data/kin/client-runtime`（挪进可封存材料） | `2 failed, 25 passed` |

每一案都只红 2 条、其余 25 条照绿 —— 红是新形状专属，不是把整份文件改坏。
第 3 条测试在字节层重放了同样四刀（RV-1…RV-4），所以 M 侧复量只需 `pytest`，不必手改文件。

改动的**既有条款**只有两处，且都是被这次的形状逼着改的，不是顺手放宽：

1. `test_the_runner_names_the_joiner_environment_before_its_jvm` 里锚定客户端那条线的字面量
   从 `… \\\n        env MINEKIN_KIN_ID="${joiner}"` 换成带 `"${joiner_runtime_dir_env[@]}"` 的新字节
   （同一个锚点，两处用到，抽成模块常量 `JOINER_LAUNCH_HEAD`）。
   同一条测试里 `assert text.count('"${joiner_launch_wrapper[@]}"') == 1`、
   `count("python -m minekin_core session start") == 1`、`count("--renderer-display") == 1`、
   `count("export DISPLAY") == 1` **一字未动**，仍然全绿 —— 客户端仍只有一个、封存侧的自测仍在原位。
2. 该条与 `test_the_launch_depth_reading_travels_on_the_line_that_execs_the_client` 的两处**注释/docstring**
   原话是「这里不 export / 不默认化那三项中的任何一项」，在 H1e 之后过强（启动线确实给了一个值），
   已改成准确说法：探针本体仍然一个都不动，唯一的交付在客户端那条线上，并由来源行具名。
   对应的**断言没有被删除或放宽**（`export DISPLAY` 仍 == 1，新增的是 `export XDG_RUNTIME_DIR` 必须 == 0）。

## 6. 本地门（逐字，全部当日在本工作树实跑）

| 命令 | 输出 |
| --- | --- |
| `uv run --frozen pytest -q` | 最终字节上跑过两次。首跑 `.tmp/h1e-gates-pytest-full.log`：`1 failed, 2578 passed, 3 skipped in 489.80s (0:08:09)`，唯一失败是 `tests/unit/test_session_supervision.py::test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in`（`tests\unit\test_session_supervision.py:141: TimeoutError`）。收尾重跑 `.tmp/h1e-gates-pytest-full-rerun.log`：`2579 passed, 3 skipped in 412.20s (0:06:52)`，全绿；两次的收集总数同为 2582，本卡新增恰 3 条（契约文件 def 数 22→25），除该例外无一条基线条目变红。首跑那例是满载全量下的 TimeoutError、非本卡引入——主控 M 在合并树 `3f85fc0`（`0b820e0` + `d4d44b6`）全量 `2594 passed, 3 skipped in 406.22s` 零失败，且在主干 `d4d44b6` 上单独重跑 `uv run --frozen pytest -q tests/unit/test_session_supervision.py` 三次 `22 passed`（53.37s / 35.16s / 32.05s）。两份日志在 `.tmp/` 下如实保留，失败材料未删 |
| `uv run --frozen ruff format --check .` | `350 files already formatted` |
| `uv run --frozen ruff check .` | `All checks passed!` |
| `uv run --frozen pytest tests/contract/test_runner_scripts.py -q` | `27 passed in 0.10s`（改面文件针对性；读数出自 `.tmp/h1e-4-reversal.log` 中反证还原后的那次最终字节复核） |
| `uv run --frozen python tools/check_case_assertions.py` | `Case assertion implementations: OK (146 registered)`（与主干基线一字相同，本卡没碰那三面） |
| `bash -n test-orchestrator/runner/domain.sh` | rc=0，无输出 |
| `uv run --frozen python tools/check_boundaries.py` | `Minekin package dependency boundaries: OK` |
| `uv run --frozen python tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK` |
| `git diff --check 0e497a9` | rc=0 |

## 7. 四态声明与没做到的部分

四态口径逐条给：**未合并 main / 仅在本分支 `codex/minekin-client-env-readout`（`0b820e0` + 本记录）/
无真封存证据新增（规范卷全程 `:ro`，未建 attempt、未封 bundle、未起受控真跑）/ 活体 JOIN 尚未量。**
本轮也不点亮任何门：registry `status`/`gaps`、`mandatory`、判据、`minekin.p0.evidence.v1` 字段一字未动。

- 仓库侧形状 + 契约测试 + 反证：**已实测**（受控镜像 `minekin-runner:local` `b67a4d917306`，真 `xvfb-run`、真 exec 线、真 `stat`）。
- **活体 JOIN 未测，归 V**：本卡没起任何受控真跑、没封 bundle、没建 attempt，因此**不声称 JOIN 已修好**，
  也不声称 `[0x1000E] Failed to detect any supported platform` 消失 —— 那是活体读数。
- 本卡**明确不判**也**明确不修**的一格：M4 量到被管客户端的环境由 Core 的封闭名单构造，
  `XDG_RUNTIME_DIR` 过不了那扇门（`DISPLAY`、`XAUTHORITY` 能）。所以「启动线提供了」是这一半的完整事实，
  「客户端 JVM 因此拿到了」不是 —— 后者要动 `src/minekin_core/config.py` 的 `FORWARDED_VARIABLES`，属 M 的独占面，
  在此登记而不越界。
- 提供出来的目录**不做收尾清理**：窗口关闭时客户端可能仍在用那个目录，删它比留它更错；这一点与 `/tmp` 里
  已有的那批不可封存暂存物同命，如实记下而不是当成已解决。
- 没量到的一格：`launch` 深度的 `XDG_RUNTIME_DIR_ORIGIN=inherited` 只在 CTL-B 的构造环境里出现过（容器本身永远不设），
  真跑里会不会天然继承仍要看 V 的活体读数。
- 全程未连接、未探测、未读取用户的远程 offline 服（`.tmp/local-test-server.txt` 本轮没有被打开）；
  本文档只出现本地路径、卷名、镜像名与 loopback 地址。
