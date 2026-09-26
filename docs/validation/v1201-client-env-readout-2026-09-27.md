# V1201-CLIENT-ENV-READOUT-001 — 被管加入者客户端的环境具名读数、orchestrator 字节的可见性缺口、下游两类读数的区分（H lane）

日期：2026-09-27（本轮全部读数于当日实量；文中任何"某天等于某值"的历史读数都标了日期，不当作永久事实）。
执行 lane：H（test Harness）。
基线：`9ac99c06f2a9a71aac1064370f635eb54544fbe9`（= 派出本卡时的 `origin/main`，即 base）。
分支：`codex/minekin-client-env-readout`，worktree `../minekin-wt-client-env`。
改动面（`git diff --stat 9ac99c0..HEAD` 实读）：`test-orchestrator/runner/domain.sh` +164、
`tests/contract/test_runner_scripts.py` +154、本记录一份。**docker/Dockerfile 的客户端环境段未改**
（`git diff --stat test-orchestrator/runner/Dockerfile` 输出为空）。
未动：`tools/**`、产品 `src/**`、判据、case registry、`status`/`gaps`、任何门禁、seal schema、
`mandatory`（diff 内 `grep -ci mandatory` = 0）、任何历史日期记录。
规范卷 `minekin-runner-data` **全程只以 `:ro` 挂载**，且只在 (b) 的只读探针那两次挂上；
(a) 的活体运行连规范卷都没有挂载，只用本 lane 自建 scratch 卷
（`minekin-h1c-lanrun`、`minekin-h1c-ctl2`）与 `/src` 只读挂载。
**本卡不含真实封证**：没有任何 attempt/bundle 被写入、被封存、被重判。

## 这张卡要答的三件事

| 问 | 本卡的回答 | 依据 |
| --- | --- | --- |
| (a) runner 在起被管加入者客户端之前，能否具名报出 `DISPLAY` / `XDG_RUNTIME_DIR` / GL 后端三者的实际值，并能反证？ | 能：两个深度各报五项，三态具名，且"不设 ⇒ 报 `<unset>`""设了 ⇒ 报那个值"两边都量到了 | 下文「(a) 绿」「对照」 |
| (b) 同一 case 的 PASS 与 FAIL 之间，`domain.sh` 的字节是否相同，在**现有** bundle 里读不读得出来？ | **读不出来** —— 登记为可见性缺口（不是本卡能修的东西：往 `minekin.p0.evidence.v1` 的 seal schema 加字段属主控决定） | 下文「(b) 的原始读数」 |
| (c) 能否把「客户端从未拨号」与「服务端 status 探测不到」两类下游读数区分开？ | 能：`classify_the_joiner_downstream_readings()` 只读两件事（loopback 上发布端口有没有人应答、客户端侧 GL 后端可不可测），并给组合各自的名字 | 下文「(c)」与 CTL-6/CTL-7 |

**这是读数，不是修复**：新代码不 export / 不 unset / 不默认化那三项中的任何一项，也不把 FAIL
变成看起来像 PASS。`domain.sh` 里 `export DISPLAY` 的 occurrences 改前改后都是 1（那句仍是
harness 指向自己那块屏），契约测试把这条钉住；真正的端到端 JOIN 在本轮**仍然没有跑通**
（见「四态声明」与「没做到的部分」）。

## (a) 红：改动前不存在这个读数

契约层红（把 base 字节原样放回施工位，跑同一份契约测试）：

```bash
cp .tmp/domain-base.sh test-orchestrator/runner/domain.sh   # base 字节 sha256 2ee030824df0d057…47564a
uv run pytest tests/contract/test_runner_scripts.py -q
```

```text
tests\contract\test_runner_scripts.py:676: AssertionError   ← assert 'joiner_launch_wrapper=(xvfb-run -a --server-args="-screen 0 1280x720x24")' in text
tests\contract\test_runner_scripts.py:742: AssertionError   ← assert "classify_the_joiner_downstream_readings() {" in text
2 failed, 20 passed in 0.27s
FAILED ...::test_the_runner_names_the_joiner_environment_before_its_jvm
FAILED ...::test_a_joiner_that_never_arrived_is_told_apart_from_an_unprobeable_world
```

其余 20 条在 base 字节上照旧绿，说明这两条红是新读数专属，不是把整份文件改坏。
原始记录：`.tmp/h1c-r2-contract-red-recheck.log`（本轮）、`.tmp/h1c-r2-contract-red.log`（上一会话，同一形状）。

活体层红（base 字节走一遍真实容器运行，看有没有读数文件）：

```bash
bash .tmp/h1c-a-driver.sh .tmp/domain-base.sh kin-e-h1c-red    # 容器配方见「(a) 绿：容器活体读数」段
```

`.tmp/h1c-run-red/30-client-environment.txt` 为 0 字节、`.tmp/h1c-run-red/10-domain.log` 里
`grep -c "joiner client environment"` = 0（该 log 第 3 行仍是 `domain: Kin2 never arrived within 90s`）。
即改动前那次客户端死亡之后**没有任何一处记录它被 handed 了什么**。

诚实注明这一跑的来历：该活体红不是本轮重跑的，而是上一会话在被停止前几分钟（本地 2026-09-27 03:07）
留下的材料。本轮核过它的来源头 `.tmp/h1c-run-red/00-bytes.txt`：驱动脚本 = `.tmp/domain-base.sh`、
其 sha256 = `2ee030824df0d057a0f2cfe1b4b14460f780fe52c6ce5ae2f9c09e227947564a`（与 `git show 9ac99c0:test-orchestrator/runner/domain.sh`
同字节）、joiner = `kin-e-h1c-red`、卷清单里没有规范卷。契约层红（上一小节）是本轮亲手重量的。

## (a) 绿：实现的形状

`domain.sh` 的 prepare 段新增一个数组与一个探针串，launcher 在 `join_the_published_world`
里、基线读之后、把任何东西交给客户端之前调用一次：

- `joiner_launch_wrapper=(xvfb-run -a --server-args="-screen 0 1280x720x24")` —— 数组同时喂
  探针和真正的客户端；契约测试钉 `"${joiner_launch_wrapper[@]}"` 恰好出现 2 次，防止"读一块屏、
  起另一块屏"。
- `client_environment_readout="/data/kin/${joiner}/run/client-environment.txt"` —— 落在加入者
  自己的运行目录里，不是 `/tmp`（RV-A9 钉住）。
- 两个深度各写 6 行：`harness`（本脚本手里的那份环境，`WRAPPER=direct`）与
  `launch`（wrapper 递给子进程的那份，`WRAPPER=inside-wrapper`）：
  `DISPLAY` / `XDG_RUNTIME_DIR` / `XAUTHORITY` / `GL_BACKEND` / `GL_PROBE_RC` / `WRAPPER`。
- 三态具名：`<unset>`（名字不存在）、`<set-but-empty>`（存在但为空）、值本身。GL 后端另有
  `not-measured: this process was handed no DISPLAY at all`（压根没屏可问）与
  `unmeasurable: the DISPLAY named here is not being served (glxinfo rc=…)`（有名字没人服务）。
  空串不允许冒充"没设"——那正是读不出来那种缺口的形状。
- 一次性的可 grep 行打到运行自己的 stderr：
  `domain: joiner client environment before its JVM: launch DISPLAY=… GL_BACKEND=…`。
- 函数只 return 不 exit：读不出来时它把"读不出来"具名（CTL-4/CTL-5），不去毁掉一次本来要产出证据的运行。

## (a) 绿：容器活体读数（本轮，2026-09-27）

复现配方（本工作树、lane scratch 卷，规范卷不挂载；镜像 `minekin-runner:local`，image id `b67a4d917306`，内含钉住的 pytest 9.1.1）：

```bash
export MSYS_NO_PATHCONV=1
REPO="$(cygpath -m C:/Users/darling/Documents/agent_work/minekin-wt-client-env)"
bash .tmp/h1c-a-driver.sh test-orchestrator/runner/domain.sh kin-h1c-v26
```

本轮跑通的是**新字节**（`test-orchestrator/runner/domain.sh`，sha256
`2e2b3c3d45f24dc080b8dc3564ccdb8047ddad947060d893f94d7567154c8b5a`；驱动头 `.tmp/h1c-run/00-bytes.txt`
同时记下 HEAD `9ac99c06f2a9a71aac1064370f635eb54544fbe9` 与 lane 自建卷清单
`minekin-h1c-bread minekin-h1c-ctl minekin-h1c-ctl2 minekin-h1c-envprobe minekin-h1c-lanrun`，
**其中没有规范卷**）。加入者 Kin 名为 `kin-h1c-v26`，读数文件 `/data/kin/kin-h1c-v26/run/client-environment.txt`：

```text
harness DISPLAY=:77
harness XDG_RUNTIME_DIR=<unset>
harness XAUTHORITY=<unset>
harness GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)
harness GL_PROBE_RC=0
harness WRAPPER=direct
launch DISPLAY=:99
launch XDG_RUNTIME_DIR=<unset>
launch XAUTHORITY=/tmp/xvfb-run.rwb9BA/Xauthority
launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)
launch GL_PROBE_RC=0
launch WRAPPER=inside-wrapper
downstream THE_RUN_DIED_ON_THE_CLIENT_SIDE with a live world and a measurable screen (llvmpipe (LLVM 20.1.2, 256 bits)), so the client environment rather than the world is where to look next
```

同一跑的运行侧 stderr 里那条一次性可 grep 行（`.tmp/h1c-run/10-domain.log` 第 4 行，逐字）：

```text
domain: joiner client environment before its JVM: launch DISPLAY=:99 launch XDG_RUNTIME_DIR=<unset> launch XAUTHORITY=/tmp/xvfb-run.rwb9BA/Xauthority launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits) launch GL_PROBE_RC=0 launch WRAPPER=inside-wrapper
```

两深度的差是本轮实测出来的，不是推的：`harness DISPLAY=:77` 是 harness 自己那块屏，
`launch DISPLAY=:99` 与 `launch XAUTHORITY=/tmp/xvfb-run.rwb9BA/Xauthority` 是 wrapper 现场 alloc
的——客户端 JVM 拿到的正是后者。`XDG_RUNTIME_DIR` 在两深度都是 `<unset>`：这个容器根本没设它，
读数把"没人设"说成了"没人设"，没有把它默认化成一个像样的路径。

该次运行**没有因为新读数而改变结局**：`domain.sh rc=0`，客户端仍然起来了、仍然被判时窗超过，
`/tmp/domain-client-environment.err` 为空（探针自身没报错）。

**必须如实记下的一处措辞越界（本轮新量到）**：这次 `kin-h1c-v26` 在 90 秒窗之后其实**加入了那个世界**
——同一条 log 后面还有 `domain: Kin2 admitted its first snapshot of that world`，
客户端最终 `{'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 26}`。
而分类器是在 `Kin2 never arrived within 90s` 这条**超时分支**上调用的，于是它对一次"迟到但确实连上"的运行
写下了 `THE_RUN_DIED_ON_THE_CLIENT_SIDE`。它说的两件事都是真的（世界在 `127.0.0.1:25570` 有人应答、
客户端屏可测），但那半句"死在客户端侧"对本跑而言是**过强**的：准确说法是"该往客户端侧看"。
作为对照，本地 2026-09-27 03:12 由上一会话留下的那一跑（`.tmp/h1c-run-green/10-domain.log`，
joiner `kin-e-h1c-green`）结局是
`{'outcome': 'HANDSHAKE_TIMEOUT', 'connection_state': None, 'snapshots_admitted': 0, 'entities_admitted': 0}`，
那一跑才真的是客户端没到。**本卡不擅自改这段措辞**（改名会撞反向证明表 RV-B3/B4 与判据措辞的边界，
且该函数不产任何 bundle 字段），把它登记为待主控定夺的一处命名问题。

时钟注记：容器读 UTC，比本地早 8 小时。本轮这跑的 run document 里 `started_at` 是
`2026-09-26T19:23:19Z`，本地即 2026-09-27 03:23；下文 (b) 里那三份 trace 的 `sealed_at_utc`
同理是 UTC 读数，别当成本地日期。

## 对照：设了值就报那个值，不设就报名字（本轮，2026-09-27）

`.tmp/h1c-a-controls.sh` 用 `awk` 从**当次发货字节**里按行范围切出数组与两个函数再驱动，
所以对照测的是真字节而不是手抄副本。容器配方同上，数据卷换成本 lane 的 `minekin-h1c-ctl2`：

```bash
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" -v minekin-h1c-ctl2:/data \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  minekin-runner:local -lc 'bash /src/.tmp/h1c-a-controls.sh'      # 原始记录 .tmp/h1c-a-controls-recheck.log
```

| 案 | 环境 | 量到的读数（摘） |
| --- | --- | --- |
| CTL-0 | `DISPLAY`/`XDG_RUNTIME_DIR`/`XAUTHORITY` 全不设 | `harness …=<unset>` ×3、`harness GL_BACKEND=not-measured: this process was handed no DISPLAY at all`（`GL_PROBE_RC=255`）；同一次 `launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)`、`launch DISPLAY=:99`、`launch XAUTHORITY=/tmp/xvfb-run.U7Xv43/Xauthority` |
| **正对照** CTL-1 | 调用方自己 `export XDG_RUNTIME_DIR=/tmp/h1c-ctl-runtime` | 两个深度都回读 `XDG_RUNTIME_DIR=/tmp/h1c-ctl-runtime`（逐字等于设进去的那个值） |
| CTL-2 | `XDG_RUNTIME_DIR=`（存在但空） | `XDG_RUNTIME_DIR=<set-but-empty>`，与 CTL-0 的 `<unset>` 不混 |
| **反证** CTL-3 | `export DISPLAY=:199`（没人服务的号） | `harness GL_BACKEND=unmeasurable: the DISPLAY named here is not being served (glxinfo rc=255)` —— "有名字"与"能测"被分开 |
| CTL-4 | wrapper 换成不存在的可执行文件 | 只剩 `harness` 六行；stderr `the launch-depth reading failed rc=127 (the wrapper never reached its child…)`；分类给出 `THE_CLIENT_ENVIRONMENT_WAS_NEVER_READ … this run cannot say which half died` |
| CTL-5 | 读数路径指向不存在的目录 | 具名拒写 `the joining client environment could not be written because … is not writable`，函数 rc=0（不毁运行） |
| CTL-6 | 在 `127.0.0.1:25599` 真起一个监听者 | `THE_RUN_DIED_ON_THE_CLIENT_SIDE with a live world and a measurable screen (llvmpipe (LLVM 20.1.2, 256 bits))…` |
| CTL-7 | 同一份读数、监听者撤掉 | 立刻翻成 `THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers 127.0.0.1:25599 while the client screen measured (…)` |

GL 后端三态本轮**全部量到**：有值（CTL-0/1/2/3/6/7 的 `launch`）、`not-measured`（CTL-0/1/2/4 的 `harness`）、
`unmeasurable`（CTL-3 的 `harness`）。要挑没量到的那一格：`unmeasurable` 只在 `harness` 深度出现过，
`launch` 深度那一格本轮没有构造出可复现形状（wrapper 自己 alloc 屏，除非它挂掉——那走 CTL-4 的"无 launch 读数"分支）。

## 反向证明表：每种"读数退化成复述"各红在哪条断言（本轮，2026-09-27）

```bash
uv run python .tmp/h1c-reversals.py        # 原始记录 .tmp/h1c-reversals-recheck.log，收尾 restored: True
```

15 个变异案**全部转红**，没有恒真断言；每案都是 1 failed / 21 passed（RV-B5 是 2 failed，因为
把分类喂进封存面同时撞到两条）。逐案的锚点：

| 案 | 变异含义 | 红在哪条断言 |
| --- | --- | --- |
| RV-A1 | 客户端回到手抄字面量、数组只喂探针 | `test_runner_scripts.py:676`（数组字面量） |
| RV-A2 | 探针之前顺手 `export DISPLAY=":99"` | `:712` `assert 2 == 1`（`export DISPLAY` 允许多） |
| RV-A3 | 少读一项（去掉 `XAUTHORITY`） | `:690`（三件套 for 循环） |
| RV-A4 | 缺失状态不再具名（写回空串） | `:692` `the readout lost the name for an absent item: "<set-but-empty>"` |
| RV-A5 | 读得太晚（读数移到客户端起来之后） | `:704` `assert 47308 < 47018` |
| RV-A6 | 读得太早（基线读之前） | `:703` `assert 47029 < 46456` |
| RV-A7 | 拿客户端侧读数冒充封存侧测量 | `:717`（sealer 自己的 `glxinfo -B` 那行被删） |
| RV-A8 | 具名行说了两遍 | `:698` `assert 2 == 1` |
| RV-A9 | 读数改写到 `/tmp` | `:697`（读数路径） |
| RV-A10 | 起两个加入者客户端 | `:680` `assert 3 == 2`（wrapper 用点数量） |
| RV-B1 | 世界那侧改成拨非回环地址 | `:764` `assert ['${lan_host}'] == ['127.0.0.1']` |
| RV-B2 | 分类读 harness 自己那块屏 | `:768`（`sed -n 's/^launch GL_BACKEND=//p'`） |
| RV-B3 | 两种结局共用一个名字 | `:759` `a downstream reading is missing or doubled: THE_RUN_DIED_ON_THE_CLIENT_SIDE` |
| RV-B4 | 到没到都下一样判词 | `:775` `assert 2 == 1`（调用点数量） |
| RV-B5 | 把分类喂进封存面 | `:716` `assert 2 == 1` + `:773` `assert '--renderer-display' not in body` |

## (b) 的结论与原始读数：现有 bundle 读不出 orchestrator 的字节

结论：**读不出来**。卷上那些 bundle 里唯一提到 `domain.sh` 的工件是
`run/evidence/<run_id>/orchestrator-trace.json`，其中承担这件事的字段只有 `orchestrator`，
值是一个路径字符串 `test-orchestrator/runner/domain.sh`；**没有该项的 digest / size / revision**。
三份 trace（seq2 PASS、seq3 FAIL、seq4 FAIL）该字段逐字相同，文件自身摘要只随
`run_id` / `sealed_at_utc` / `verdict` 变。⇒ 同一 case 的 PASS 与 FAIL 之间脚本字节是否相同，
从证据里**不可判**，这是可见性缺口。本卡不擅自往 `minekin.p0.evidence.v1` 的 seal schema 加字段。

复现（规范卷 `:ro`，只写容器 `/tmp`）：

```bash
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" \
  -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  -e LD_LIBRARY_PATH=/opt/sqlite/lib minekin-runner:local -lc 'bash /src/.tmp/h1c-b4-readout.sh'
docker run … -lc 'bash /src/.tmp/h1c-b5-tracecmp.sh'      # 逐字段比三份 trace
```

本轮（2026-09-27）原始读数，`.tmp/h1c-b4.log` / `.tmp/h1c-b5.log`：

```text
# 只读是真只读：真实写尝试，不是 os.access（容器 root 下 os.access 恒真，不能当哨兵）
H1c-B4: refused: OSError 30 [Errno 30] Read-only file system: /data/.h1c-b4-must-fail
H1c-B4: refused: OSError: [Errno 30] Read-only file system: '/data/kin/.h1c-b4-must-fail'

# 提到 domain.sh 的工件：三跑各自只有一个
seq2-PASS: files under 19ff9064…/ mentioning 'domain.sh' = ['orchestrator-trace.json']
seq3-FAIL: files under 78716806…/ mentioning 'domain.sh' = ['orchestrator-trace.json']
seq4-FAIL: files under 6286f1e5…/ mentioning 'domain.sh' = ['orchestrator-trace.json']
# 该字符串作为值出现过的字段名（全三跑扫过）：
field 'orchestrator': distinct values = ['test-orchestrator/runner/domain.sh']; occurrences = 3

# manifest 完全不提脚本路径；它只给每个工件的 sha256+size
seq2-PASS: manifest mentions the script path = False
seq3-FAIL: manifest mentions the script path = False
seq4-FAIL: manifest mentions the script path = False
```

三份 trace 的逐字段对比（`orchestrator-trace.json` 共 8 个键）：

| 键 | 三跑之间不同取值的个数 | 读数 |
| --- | --- | --- |
| `case_id` | 1 | `"CORE-030"` |
| `orchestrator` | 1 | `"test-orchestrator/runner/domain.sh"` ← PASS 与两次 FAIL 逐字相同 |
| `schema_version` | 1 | `1` |
| `server_directory` | 1 | `null` |
| `session_argv` | 1 | `["session","start","--profile","tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json","--world-save","tests/fixtures/saves/kinworld","--world-name","kinworld"]` |
| `run_id` | 3 | `19ff9064…` / `78716806…` / `6286f1e5…` |
| `sealed_at_utc` | 3 | `2026-09-26T12:46:23Z` / `…17:26:18Z` / `…17:38:12Z`（UTC；本轮 2026-09-27 实读到的封存字段值） |
| `verdict` | 2 | PASS 的 `failures: []`；两次 FAIL 各带 `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT` |

文件自身摘要（唯一能"区分"三跑的东西，但它区分的是运行身份不是脚本字节）：

```text
cd3f45476de0a173b6e1bd99ea9d6296905edc78e66661d06df070f0cd627b80  seq2-PASS orchestrator-trace.json (915 bytes)
eb51d6ec6486813fc16ec3e81f35fe66cc816df2a3fea7a4916387cc7a166c19  seq3-FAIL orchestrator-trace.json (973 bytes)
ad5406a262ba3f4968e4df0b274897f1ef2563ab8bcc82952692b2ed9fac48be  seq4-FAIL orchestrator-trace.json (973 bytes)
```

这三个摘要同时作为 `sha256` 出现在各自 `manifest.json` 的 artifacts 列表里 —— 也就是说封存面
**给的是"这份 trace 文档的摘要"，不是"脚本的摘要"**。同一份脚本可以产出不同摘要（seq3/seq4 同为
973 字节但摘要不同），不同脚本也可能产出完全相同的这份文档（本轮 base 字节与新字节都会写出
`orchestrator` = 同一路径字符串）。所以这条通道对"字节是否相同"是结构性盲的。

补一条同源缺口：bundle 的 `environment.renderer_display` 由 sealer 事后自己
`xvfb-run -a … glxinfo -B` 测（`domain.sh` 的 seal 分支），本轮实读它三跑都是
`llvmpipe (LLVM 20.1.2, 256 bits)`，包括客户端根本没开到窗口的那两跑 —— 封存侧的读数描述不了客户端侧的死亡。
这正是 (a) 那个读数必须由 launcher 自己做的理由。

## (c) 两类下游读数的区分

判据 `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT` 都只是客户端那半的事实，
从下游看和"服务器 status 探不到"同形（都没东西来）。`classify_the_joiner_downstream_readings()`
在"加入者没到"那一条分支上把两件事分开读：

1. 有没有人在**回环**上的发布端口应答：`timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/${lan_port}"`。
   全脚本里 `/dev/tcp` 只有一处，且目标是 `127.0.0.1`（RV-B1 钉住：换成 `${lan_host}` 即红）。
   本卡从不、也不能拨远程地址。
2. 客户端被 handed 的屏可不可测：只读 `launch` 深度那行（RV-B2 钉住：改读 `harness` 即红）。

组合各有名字：`THE_CLIENT_ENVIRONMENT_WAS_NEVER_READ` / `THE_RUN_DIED_IN_THE_CLIENT_ENVIRONMENT` /
`THE_RUN_DIED_ON_THE_CLIENT_SIDE` / `THE_WORLD_STATUS_IS_NOT_PROBEABLE` / `BOTH_HALVES_NAMED_AND_BOTH_BAD`
（RV-B3 钉住"两结局不同名"）。它不新增判据、不改门禁、不往 bundle 写任何字段（RV-B5 钉住），
被它描述的那次运行仍是原来那个 FAIL，只是多说了件事。同一运行的读数翻面由 CTL-6/CTL-7 实测。

## 门禁表（本轮，2026-09-27）

| 命令 | rc | 关键输出 |
| --- | --- | --- |
| `bash -n test-orchestrator/runner/domain.sh` | 0 | （无输出） |
| `uv run pytest tests/contract/test_runner_scripts.py -q` | 0 | `22 passed in 0.21s` |
| 同测试打在 base 字节上 | 1 | `2 failed, 20 passed`（红点见上） |
| `uv run python .tmp/h1c-reversals.py` | 0 | 15 案全红、`restored: True` |
| `uv run ruff check .` | 0 | `All checks passed!` |
| `uv run ruff format --check .` | 0 | `344 files already formatted` |
| `uv run pyright` | 0 | `0 errors, 0 warnings, 0 informations` |
| `uv run python tools/check_boundaries.py` | 0 | `Minekin package dependency boundaries: OK` |
| `uv run python tools/check_case_assertions.py` | 0 | `Case assertion implementations: OK (140 registered)` |
| `uv run python tools/verify_fixture_digests.py` | 0 | `W00 schema and fixture digests: OK` |
| `git diff --check` | 0 | （无输出） |
| `python /src/tools/report_promotion.py --data-root /data`（容器内，规范卷 `:ro`） | 1 | 载荷摘要与台账底数见下 |

门载荷与台账底数（`report_promotion` 的 `--data-root` 实读，`.tmp/h1c-b4.log`）：

```text
gate payload sha256 = fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da   # 一字未动
promotable = ["W00", "W10", "W20", "W60"]                                                  # 名单未变
evidence.attempts = 71 / evidence.bundles = 107                                            # 底数保持
evidence.from_another_build = 61, repo_checks_not_from_the_controlled_interpreter = 9
sealed_without_bundle = 0 / unreadable = 0 / unsealed = 0 / unverified = 0
```

台账底数用两条独立路径交叉核过（上一会话在这里数错过一次，教训见下节）：

```text
sqlite registry /data/evidence-attempts.sqlite3 → attempts rows = 71（全部 status=SEALED）
bundle 目录 = /data/kin/*/<run>/evidence/<run_id> 94 个 + /data/repo-evidence/<run_id> 13 个 = 107
```

第二条与 `minekin_core.cli.evidence.candidate_roots()` 的读法一致（Kin 根 + `repo-evidence` 根）。
上一会话那两条 glob（`/data/attempts/*/attempt.json`、`kin/*/run/evidence/*/manifest.json`）得到
`attempts 0 / bundles 94`，是路径写错：attempt 台账是一张 sqlite 表，仓库自身检查的 bundle 落在
`repo-evidence/` 而不是 `kin/` 下。

## 诚实记录：本轮的一次危险操作与一次修正

- 任务给的还原步骤 `git checkout -- test-orchestrator/runner/domain.sh` 在本卡是**破坏性**的：
  HEAD 就是 base，而实现未提交，`git checkout` 会把实现冲掉（量红后确实发生了，文件 sha256
  变回 `2ee03082…`）。还原是靠 `.tmp/domain-new.sh`（新字节副本 `2e2b3c3d…`）完成的，
  还原后复验：`sha256sum` = `2e2b3c3d45f24dc0…154c8b5a`、`git diff --stat` 回到 `+164/+154`、
  契约测试重新 `22 passed`。留给后续 H 卡的教训：**base == HEAD 时，红/绿切换不能用 `git checkout` 还原，
  要用字节副本**（`.tmp/domain-base.sh` / `.tmp/domain-new.sh` 两份都在）。
- 反向证明脚本 `.tmp/h1c-reversals.py` 每次变异后从 `.tmp/domain-new.sh` 写回原字节，收尾自证
  `restored: True`（本轮实读到该行为真）。

## 四态声明

- `domain.sh` 的加入者环境具名读数与下游两态分类、以及其契约测试：**仅在分支**
  （`codex/minekin-client-env-readout`，未合入 main，等待主控双审）。
- 红/绿/正对照/反向证明/活体读数：**真实测量**（受控容器 `minekin-runner:local` `b67a4d917306`、
  真 JVM、lane 自建卷；日期均为 2026-09-27）。
- (b) 的 orchestrator 字节可见性：**缺口已确证**（现有 bundle 读不出来），**修复未验证** ——
  本卡不动 seal schema，加字段属主控决定。
- 真实端到端 JOIN 与该读数的封证：**尚未验证 / 本卡不产出**（本卡全程无封存，规范卷只读）。
  本记录不宣称 Minekin 完成，不宣称任何门禁点亮。

## 本轮没做到的部分

- 没有跑全量 `uv run pytest -q`（约 400 秒那一轮）：本轮只跑了
  `tests/contract/test_runner_scripts.py` 与全套静态/门禁用工具；主干侧基线由 M 另行把。
- 活体那一跑的**结局没有被读数改变**，但也**没被救活成干净的一跑**：本轮 `kin-h1c-v26` 是
  "90 秒窗后迟到加入、最终 `BRIDGE_LOST`"（上面已逐字记），上一会话本地 03:12 那跑是
  `HANDSHAKE_TIMEOUT` 且 `snapshots_admitted: 0`。也就是说真实端到端 JOIN **仍未跑通过一次**
  "窗内到达 + 正常收尾"的运行；本卡按卡面只做读数，不修任何东西。
- `launch` 深度的 GL_BACKEND `unmeasurable` 态未构造出可复现形状（只有 `harness` 深度量到）。
- 没有任何 attempt/bundle 级别的封证，因此该读数在 bundle 里**目前也不可见**——它落在
  `/data/kin/<joiner>/run/client-environment.txt`，而现有 manifest 的工件清单不收这一文件。
  把它纳入封存面同样要碰 seal schema，属主控决定。
- 未读、未连、未探用户的远程测试服务器（`.tmp/local-test-server.txt` 本轮没有被打开）。
