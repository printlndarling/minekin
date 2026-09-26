# Minekin 并行开发调度计划

版本：2026-09-26 激活、2026-09-27 第四轮补「M 侧审查的写操作边界」与 H 当前施工支。目的：把一个串行 Qoder 会话拆成可独立推进的实现、前端和真实验证工作流，同时保留当前证据门禁和用户决策边界。本文是**并行作业协议**，不是宣称这些能力已经完成；主控已于 2026-09-26 把它与 `development-execution-plan.md` 的主干状态原子对齐（主干 §2 `lane_next` 激活表与唯一 integration `NEXT` = `PARALLEL-INTEGRATION-GATE-001`，此后每合一张 lane 卡即回写主干状态）。

## 1. 当前现场与启动条件

制定本计划时远端 `main`/工作分支均为 `6f0f562`，Qoder 的共享工作树正在改 B2 `P0-CONTROLLED-CAMPAIGN-001` 的四份文档与一份新证据记录，尚未提交。B2 第一刀 `CORE-040/050` 在本地受控 1.21.4 上得到当前构建的 sealed PASS，W60 只是 `promotable` 候选；`p0-core` 仍缺 fixture/真实证据。A1 的 1.20.1 本地自动装机→PLAYABLE→look/move→释放同 run PASS 已封存；V08 用户远程服仍 `BLOCKED_DECISION`。Dashboard/Gateway/Web API/媒体 worker 均未实现；P0 ADR 0001 明确 P0 不引入 Web API 或 Dashboard。

**立即生效的保护**：原 Qoder 先完成或安全停放 B2 当前脏改，不能因本计划丢弃它。其它会话只在独立 Git worktree + 独立分支施工，绝不在共享 checkout 上写。主干继续只有 B2 一个 `NEXT`；并行分支使用下文各自的 `lane_next`，只代表该分支可开发，不代表主干验收。主控审完并合并本计划后，在现行主计划加一条“每 lane 一个 NEXT、主干一个 integration NEXT”的状态规则；此后不得再用“全库只有一个 NEXT”阻止已划清路径的并行分支，也不得把未合并分支写成主干 `DONE`。

## 2. 工作区、所有权与共享资源

| Lane / 初始 `lane_next` | 独占修改面 | 禁止碰的面 | 可交付的第一张卡 |
| --- | --- | --- | --- |
| M 主控/集成 | `docs/development-execution-plan.md`、`docs/development-todo.md`、`docs/qoder-execution-handoff.md`、本计划、合并/门禁记录；主干 refs | 不在他人正在施工的分支改代码；不替执行者改判据求绿 | B2 checkpoint → 启用并行规则 → 逐分支双审和合并 |
| E 真实运行/证据 | 当前 B2 专属证据记录、其 case/判官必要改动；规范数据卷的**唯一写入者** | `dashboard/**`、自动入口产品代码、他人独立卷；不得连接用户远程服 | B2 当前构建的剩余受控证据，缺 fixture 与未实现行为逐条分开 |
| V 1.20.1 游戏内调试 | 独立卷/独立 Kin 的本地真实 run 与 `docs/validation/**` 中自己的报告；产品源码只读。**当前施工支（2026-09-27 第六轮收口）**：`codex/minekin-v1201-auto-status` @ `../minekin-wt-v1201-auto-status`（base `cb4786f`，卡 V2，lane 尖 `9ec4486`）**已合完**（合并 `b6f23a8`），该 lane 手上没有活动施工支；`lane_next` = **无安全可派卡，停等具名**（⑤ 家族在 1.20.1 侧没有加入者起跳面 ⇒ 需先有一张 H 面的 runner 卡；其余是 H-3/H-4 产品下载器归属，属主控决策） | 规范卷（本卡连 `:ro` 都不挂）、B2 文件、runner/判官/case/registry（`test-orchestrator/**` 此刻归 H 的 `H1c`）、用户远程服 | `V1201-AUTO-STATUS-ON-1201-001`：1.20.1 侧的 auto × `--enable-status` 活体读数＋⑤ 家族是否复现的形状计数＋bridge 阻断复核 |
| S 自动入服安全 | `src/minekin_core/cli/auto_session.py`、必要 `bootstrap.py`/`server_profile.py` 和对应单元/契约测试（路径若需扩大先给 M） | `test-orchestrator/**`、证据工具、case fixtures、registry、规范卷、主计划 | `V1201-AUTO-ENTRY-GATE-ORDER-001`；之后 N2 预算参数校验，另卡另提交 |
| H 测试 Harness | `test-orchestrator/runner/**`、`tools/run_controlled_server.py`、对应 runner 契约测试；`seal_run_evidence.py` 需与 E 协调独占窗口。**当前施工支（2026-09-27 第七轮更新）**：`codex/minekin-client-env-readout`（卡 `H1c`，base `9ac99c0`，lane 尖 `de579ad`）**已合完**（合并 `3706524`，远端 SHA 已核），该 lane 此刻没有活动施工支。此前各支（`codex/minekin-harness`、`codex/minekin-runner-named-failure`、`codex/minekin-auto-path-runner`、`codex/minekin-controlled-server-status`、`codex/minekin-auto-path-status-wiring`）**均已合完** | 产品 `src/**`、`bridge*/**`、case 判据、registry、规范卷、主计划 | `H1d`（V2 读数暴露的 `domain.sh` rc=0 可见性缺口；第七轮提升为 H 的 `lane_next`）。**派工暂时被阻**：受控容器引擎自第七轮起对 `/_ping` 回 500，H1d 的测量要挂 Docker，M 不擅自重启用户机上的引擎进程（进程接管属主控保留决策） |
| D Web Dashboard 前端 | 新增 `dashboard/**`，只含前端、类型/模拟数据、前端测试、局部说明 | `src/**`、`bridge*/**`、服务端 API、数据库、游戏输入、真实媒体宣称、主计划 | 只读状态/时间线 mock-first 垂直切片；不合并为 P0 运行产品 |

另设候补 **G Gateway 只读投影**：待 M 冻结浏览器读模型与 P2 进程形态后，单独拥有新 `gateway/**`；不可在 P0 Core 里偷偷塞 FastAPI/WS，不可直接暴露 SQLite、Bridge socket 或带凭据原始事件。**P2 媒体**也待真实采集和授权接口冻结后开新 lane；不能用假画面充 Live View。

同一文件仅一名 owner。任何跨 lane 修改都先在 M 的冲突表登记：需求、目标文件、当前 owner、移交时点；不能两边各写一半再指望 Git 自动合。每张卡附 base SHA、diff stat、测试原始结果、未测、阻断；分支 commit 后立即 push 本分支供审查，**只有 M 能更新 `main`**，且仅在证据/测试通过后按依赖顺序集成。失败分支保留，不能靠重写历史隐藏失败。

**M 侧审查的写操作边界（2026-09-27 第四轮补，起因是 M 自己的一次越界）**：M 对 lane 卡的复量、反向证明和任何写文件的动作，只在**自己新建的 worktree / 自己的容器卷**里做，或在该 lane 会话明确停笔之后做；**不得在被审 lane 的活动 worktree 内写文件，不得替 lane 提交或重排它的提交**。同一条约束反过来也约束 lane：lane 不得为了让审查通过而改动 M 的合并说明。`Constraint`/`Not-tested` 这类 trailer 的口径由**做过该测量的一方**负责——M 未复量应写「M 侧未复量」，不得写成「未做」，那会把 lane 真实跑过的测量抹掉（第四轮 H2 上真实发生过一次，lane 已按事实更正）。

#### 冲突表登记（2026-09-26，M 逐条开）

| 卡 | 需求 | 目标文件 | 当前 owner | 移交时点 |
| --- | --- | --- | --- | --- |
| `INT-EVIDENCE-INTEGRITY-001` | 台账 `SEALED` 行缺 bundle 不再静默（E 第五刀 R-E 量出） | `tools/report_promotion.py`、`tests/unit/test_report_promotion.py` | M（读者面不属任何 lane 的独占面） | 已闭环：`759125f` 合入 `main`，未占用 E 的规范卷写窗口 |
| `H1a` `TEST-ORCHESTRATOR-PINNED-PYTEST-001` | 受控镜像带钉住的测试工具链，消掉「镜像内跑仓库自检 ⇒ 环境性假 FAIL」（E 第五刀 §5） | `test-orchestrator/runner/Dockerfile`（+ 其契约测试 `tests/contract/test_runner_scripts.py`） | **H 独占面**；施工由 M 派工到 `../minekin-wt-harness`（`codex/minekin-harness`），仍走 H 的分支与 H 的验收 | 已闭环：`44922b8` 经 M 双审合入 `main = ee0a439`（2026-09-26）。**副作用登记**：共享 tag `minekin-runner:local` 已重建（image id `7730fc480365 → b67a4d917306`），全体 lane 的下一次镜像运行都带这一层；修前参照以 `minekin-runner-before:local` 留在本机 |
| `H1b` `RUNNER-NAMED-FAILURE-001` | `domain.sh` 的加入基线读取在全新 Kin 上确定性静默 `rc=2`（E 第四刀）；分类 ④（runner 未 `import sys`）后判**仓库代码未复现**，故本卡只有一个提交 | `test-orchestrator/runner/domain.sh` | **H 独占面**；派工到 `../minekin-wt-runner`（`codex/minekin-runner-named-failure`），与 H1a 不同分支不同文件，二者不互撞 | 已闭环：`1dc6101` 经 M 双审合入 `main = d09e9b2`（2026-09-26）。该 worktree 随即移交下一张 runner 卡（见下方 G1/G2 行），H1b 的 `.tmp/` 探针作为测量材料保留在未合并分支之外 |
| `S2` `V1201-MAX-BYTES-VALIDATION-001` | 非正预算具名拒止（当时是 `INTERNAL_INVARIANT`）、`--max-bytes` 与 `--profile` 同给具名用法错误（A2 的 N2） | `src/minekin_core/cli/auto_session.py` + 必要 `src/minekin_core/bootstrap.py` + 对应单元测试 | S 独占面（本表 §2 那行授予的「必要 `bootstrap.py`」即此）；派工到 `../minekin-wt-auto-entry`（`codex/minekin-auto-entry`） | 已闭环：`20e2e60` 经 M 双审合入 `main = ea5423e`（2026-09-26）；不改 case 判据、不碰规范卷 |
| `E-CO` 镜像内自检重封一轮 | 让「判官只需仓库字节」那四条的 `environment` 段与真正执行检查的环境一致（②落地后的新证据卡） | 写入目标只有规范卷 `minekin-runner-data`（新 attempt + 新 bundle）与本卡自己的 `docs/p0-repo-internal-image-reseal-2026-09-26.md` | **E 独占**：规范卷唯一写入者；`tools/**`、`src/**`、`test-orchestrator/**` 一律只读 | 移交时点：已闭环 —— M 派工于 2026-09-26（base 为合入三张工程卡后的 `main`），E 交付 `626a454`，M 只读复核卷上读数与门载荷摘要后以合并 `6cc9c45` 入主干并核远端 SHA。与 H 的 G1/G2 同时开工的前提成立：G1/G2 全程未挂载规范卷（M 复核其记录与改面） |
| `INT-REPO-CHECK-TOOLCHAIN-PROVENANCE-001` | 报出「哪份仓库自检 bundle 的解释器不是受控镜像那一个」：卷上 13 份里 9 份记宿主 `.venv`，读者面无字段区分（`E-CO` 收卡时 M 量到） | `tools/report_promotion.py`、`tests/unit/test_report_promotion.py` | M（读者面不属任何 lane 的独占面） | 已闭环：`318a44c` 经 M 门禁后以合并 `0ab208c` 入 `main`（2026-09-26），只命名不门禁，门载荷摘要一字未动 |
| `E-RR` 修好的 runner 真跑复跑 | 把 ③ 与 G1/G2 从代码层证据升到真跑层证据（第四刀那次被静默 `rc=2` 掐死的 `CORE-030` 加入尝试） | 规范卷 `minekin-runner-data`（新 attempt）+ 本卡自己的 `docs/p0-core030-runner-rerun-*.md` | **E 独占**：规范卷唯一写入者；`tools/**`、`src/**`、`test-orchestrator/**` 一律只读 | 移交时点：M 派工于 2026-09-26，base `main = be4e79b`。**已闭环（第五轮）**：E 交付 `0521fcb` + `918218d`，M 只读复核卷上两份新 bundle（都是具名 FAIL）与门载荷摘要后以合并 `3932ba5` 入主干，卡面按 `BLOCKED_HARNESS` 收口（③ 的真实通道一半已证；PASS 被 ⑤ 家族挡住）。与 H2 同时开工的前提：H2 不挂载规范卷、只改 `tools/run_controlled_server.py` 与其测试（已写进两张派工） |
| `V1201-AUTO-PATH-STATUS-WIRING-001`（H3） | H2 只把 `--enable-status` 做进工具，`domain.sh` 的受控启动器调用面仍不传 ⇒ auto 路径按构造被自己那条读回后早停掐住（此为该卡派工前的形状，现由 H3 改掉，见末列） | `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、新增 `docs/validation/**` 记录 | **H 独占面**；派工支 `codex/minekin-auto-path-status-wiring` @ `../minekin-wt-h3`，base `6ce9f06` | **已闭环（第五轮）**：`4b943ce` + `a70bf38`（远端尖 `a70bf38467ac5a46b6ddd5a5cdd55ebb4bd5fded`），M 双审后以合并 `cd7664b` 入主干。**边界（派工时写死，实际未越）**：旗标只在 `-n "${auto_bundle}"` 这一个谓词下传、不得无条件全开、不得删读回后早停；禁改 `tools/**`；**禁挂规范卷**（该 lane 自报全程未挂载该卷，M 复核其改面确无卷侧产物）。活体红/绿/对照/mismatch 四组读数与四组变异归 H；M 只复量了合并树门禁、一次 base 字节反向与合并后卷上「不重判任何 bundle」的只读复量 |
| `V1201-AUTO-STATUS-ON-1201-001`（V2） | **已闭环（第六轮，合并 `b6f23a8` 入 `main`，远端 SHA `b6f23a89888d9b5f46f14e1601400955f18bd7d0` 已核）**：把「1.20.1 recipe × `--enable-status`」与「端到端 auto 形状」这两格 M 侧明写未测的读数，在 1.20.1 隔离侧补成活体测量（V-a 红/绿/非 auto 对照/`AUTH_MODE_MISMATCH`；V-b 只报 ⑤ 家族是否复现的形状与计数；V-c 复核 bridge 那件阻断是否仍成立） | 新增 `docs/validation/v1201-auto-status-1201-2026-09-27.md`（唯一改面，+314 行）+ 自有 scratch 卷 `minekin-v2-*`；仓库其余文件一律只读 | **V lane**；派工支 `codex/minekin-v1201-auto-status` @ `../minekin-wt-v1201-auto-status`，base `cb4786f`，lane 尖 `9ec4486`。**硬边界（实际未越）**：`test-orchestrator/**` 此刻归 H 的 `H1c` 施工，V 未改未并卡；**完全未挂载规范卷**（连 `:ro` 都没有）⇒ 本卡不构成真实封证。**M 侧复核**：承重引用逐字对仓库字节核过（缺陷脚本 sha1 `0eb3f55d…` 同枚、`domain.sh:404-407/:576/:739/:791`、bridge fixture `:42`），并**在自己的 worktree + 自建卷 `minekin-m-v2-verify` 上独立重放了 V-a 的红/绿两组**（`3639 / 738,432,269` 逐字同值），mismatch/control 两组与 V-c 的取件前沿 M 未复量；合并树四门 `rc=0`、门载荷仍 `fb0152c8…`。V 的另一项产出是给 H 的读数：`domain.sh` 在 auto run 停在具名供应链拒止（`BUDGET_UNDECLARED`）时仍 `rc=0`，已登记为候补卡 `H1d`（§4 同名行） |
| `H1c` 受控客户端环境具名化（⑤ 的下游读数区分） | **已闭环（第七轮，合并 `3706524` 入 `main`，远端 SHA `370652462c75e4e59837ae4d5eda11b95f410f7b` 已核）**：让 runner 在起被管加入者客户端前具名报出 `DISPLAY` / `XDG_RUNTIME_DIR` / GL 后端三者的实际值并给红/绿对照，并把「客户端从未拨号」与「服务端 status 探测不到」两类下游读数区分开；同时回答卡面 (b)——同一 case 的 PASS 与 FAIL 之间，编排脚本字节是否相同在现有 bundle 里读不读得出来 | `test-orchestrator/runner/domain.sh` 的客户端起跳段、`test-orchestrator/runner/Dockerfile` 的客户端环境段、`tests/contract/test_runner_scripts.py`、新增 `docs/validation/**` 记录 | **H 独占面**；派工支 `codex/minekin-client-env-readout` @ `../minekin-wt-client-env`，base `9ac99c0`（= 当时远端 `main`）。**规范卷写入窗口的释放由 M 在本行核**：`E-RR` 已按 `BLOCKED_HARNESS` 收卡并入主干（合并 `3932ba5`），本会话此刻没有活动的 E 施工支 ⇒ 窗口空闲；H1c 一律 **`:ro` 挂载**、不得封存任何 attempt/bundle。不得改产品 `src/**`、判据/registry/门禁/seal schema，**不往 `minekin.p0.evidence.v1` 加字段**（读不出来就登记为可见性缺口）。**M 侧独立双审（第七轮）**：改面从真实 merge-base `9ac99c0` 起算是 3 文件（`domain.sh` +164、`tests/contract/test_runner_scripts.py` +154、`docs/validation/v1201-client-env-readout-2026-09-27.md` +359），全在 H 独占面内、无越界；合并树 `bash -n` rc=0、契约 `22 passed`、全量 `uv run --frozen pytest -q` 给 **`2537 passed, 3 skipped in 415.31s`**（主干基线 2535 ⇒ 恰为两张新测）、ruff check/format、pyright、`check_boundaries`、`check_case_assertions`（140 registered）、`verify_fixture_digests`（W00 OK）、`git diff --check` 全 rc=0；M 自己下的反向证明是把两个调用点各改成注释 ⇒ 恰好 `2 failed, 20 passed`，还原后 `sha256sum` 与审前一致、工作树 clean。**采信 `(b)`**：本卡从卷字节侧独立确证现有 bundle 读不出 `domain.sh` 字节，修复走 §3.3 那两行的主控保留决策，本卡未加字段。**一处过强断言登记给 `H1d`**：记录写「客户端 JVM 拿到的正是后者（launch 那组值）」，而 launch 读数取自**探针自己那次** `xvfb-run` 调用，与真起客户端那次是两个进程——屏号可能因释放后重分配而相同，`XAUTHORITY` 临时目录必然不同；该成对对照要容器实测，本轮受控引擎对 `/_ping` 回 500 ⇒ **M 侧未复量**，合并后 `:ro` 台账底数（`attempts 71 / bundles 107`）与门载荷（`fb0152c8…`）同样 **M 侧未复量**，只登记 lane 自己的读数与本会话合并前的仓库侧门禁。 |
| `B1-b` **第一阶段**（`P0-OFFLINE-090-100-EVIDENCE-CHECK-001` 的仓库侧） | 甲类两条（`OFFLINE-090`/`OFFLINE-100`）缺的是 **case 定义与断言**，不是只差运行。本阶段只把「这两条判据能否逐字落在**已封存工件**的字段名上」变成仓库里可判定的形状，并按 §3.3 同名行的验收 ③ 报门载荷的前后与逐项差异 | 新增 `tests/fixtures/cases/**` 里这两条的定义与覆盖它们的测试 + 本卡自己那份记录；**不碰** `test-orchestrator/**`（`H1c` 在工）、`tools/**`（M 的面）、`src/**`、判据/registry 的 `status/gaps` | **E lane**；派工支 `codex/minekin-offline-090-100` @ `../minekin-wt-b1b`，base `03c1d95`（= 当时远端 `main`）。**阶段边界（M 第七轮定标）**：规范卷全程 `:ro`、不建 attempt/bundle ⇒ 与 `H1c` 的读卡并行**不违反**卷写窗串行；**真实封存仍等 `H1c` 合并后 E 拿回写窗**。注册这两条必然让门载荷离开 `fb0152c8…`（验收 ③(ii)），故本阶段的门读数只作「前后两枚摘要 + 逐项差异 + 各落入哪个 block」报告，`promotable` 冻结在 `W00/W10/W20/W60`；push 后 M 审 |
| `H1d` auto run 停在具名前沿时 `domain.sh` 仍 `rc=0` | V2 的绿读数（M 在自己卷上重放确认）：跨过早停后停在 `BUDGET_UNDECLARED` 的 auto run 与「起了客户端但没到 playable」在退出码上不可区分（同驱动红形状给 `rc=2` ⇒ 非恒零） | `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、新增 `docs/validation/**` 记录 | **H 独占面，与 `H1c` 同面 ⇒ 已排在其后**；状态 **`lane_next`（第七轮提升，因 `H1c` 已并入 `3706524`）**，主计划 §4 同名行有先红后绿验收。**第七轮追加一项验收（来自 `H1c` 的 M 审查发现）**：把 `launch` 深度读数取自**真起客户端那一次** wrapper 调用（或由同一条命令行先写读数再 `exec` 客户端），并对「探针屏／客户端屏」「探针 `XAUTHORITY`／客户端 `XAUTHORITY`」给成对实测对照，使记录里那句「客户端 JVM 拿到的正是后者」可判真伪。**派工被阻**：这两项都要活体容器测量，而受控容器引擎自第七轮起对 `/_ping` 回 500；引擎进程重启属主控保留决策，M 不擅自操作。禁挂规范卷、禁改判据/registry/门禁/seal schema |
| `V1201-CONTROLLED-SERVER-STATUS-KNOB-001`（H2） | `tools/run_controlled_server.py:247` 硬编码 `enable-status=false` 且无回读 ⇒ 受控启动器按构造对 status 探测失明（G1/G2 记录点名的遗留①；此为该卡派工前的形状，现由 H2 改掉，见末列） | `tools/run_controlled_server.py` + 覆盖它的测试；新增 `docs/validation/**` 记录 | **H 独占面**（协议 §2 那行已授予该文件）；派工到新支 `codex/minekin-controlled-server-status` @ `../minekin-wt-status`，base `be4e79b` | **已闭环（第四轮，合并 `6ce9f06`）**。**边界**：默认值不改（`false`），不改 `domain.sh`、判据、registry、门；**禁止挂载规范卷**（此刻归 `E-RR`）。push 后 M 审 |
| `V1201-AUTO-PATH-RUNNER-001`（G1/G2） | 自动路径进 `domain.sh` 并按 `seal_run_evidence.py` 实际必填项传参；`enable-status` 可复核读数与 `Pos/Rotation` 控制台探针默认化 | `test-orchestrator/**` + `tests/contract/test_runner_scripts.py`；`tools/seal_run_evidence.py` **只读接口，不改** | **H 独占面**；派工到 `../minekin-wt-runner` 的新支 `codex/minekin-auto-path-runner`（H1b 合完后顺序接手同一文件面，避免两条施工撞同一批脚本） | 开工条件已满足（③、② 均在主干）。**禁令**：不得挂载规范卷（归 E 的 `E-CO`）；需要封存独占窗口即停在该前置上报。push 后 M 审。**已闭环**：H 交付 `efb8630 → f8a1d9a → f3b6001`（远端分支 `f3b6001`），M 侧独立双审（真实 `merge-base` 与主干核为 `ea5423e`、改面只有 `test-orchestrator/**` 与该契约测试、两条新契约测试对缺陷副本 `2 failed` / 在分支 `19 passed`、lane 工作树六项门全 `rc=0`）后以合并 `be4e79b` 入 `main`（2026-09-26）。其记录点名的遗留① 转为下一张 H 卡（本表 H2 行） |

登记只解决文件面归属，**不把 lane 分支上的实现升格为主干状态**：本表中标着「已闭环」的十二行（`INT-EVIDENCE-INTEGRITY-001`、`H1a`、`H1b`、`S2`、`E-CO`、`V1201-AUTO-PATH-RUNNER-001`、`INT-REPO-CHECK-TOOLCHAIN-PROVENANCE-001`、`E-RR`、`V1201-CONTROLLED-SERVER-STATUS-KNOB-001`（H2）、`V1201-AUTO-PATH-STATUS-WIRING-001`（H3）、`V1201-AUTO-STATUS-ON-1201-001`（V2）、`H1c`）都已随 M 的合入闭环，主干 SHA 逐笔在行内；其中 `E-RR` 与 V2 同样是**按 `BLOCKED_HARNESS` 收口**的闭环。**本表此刻只有一行「在工」**：E lane 的 `B1-b` **第一阶段**（第七轮派工，支 `codex/minekin-offline-090-100` @ `../minekin-wt-b1b`，base `03c1d95`，全程只 `:ro` 读规范卷、不建 attempt/bundle ⇒ 不占卷写窗）。`H1c` 已随合并 `3706524` 闭环（第六轮派工、第七轮收口：该 lane 首个施工会话在子代理轮次上限处被掐断、工作树留下**未提交**实现，M 在同一工作树派续跑会话**收尾而非重设计**——复量红/绿/对照/反向、写记录、两个提交、push）。`H1d` 于第七轮从候补行提升为 H 的 `lane_next`，与 `H1c` 同面且排其后，并带上 `H1c` 审查新增的那条验收（`launch` 读数须取自真起客户端那次 wrapper 调用）；它的活体测量与 V lane 的下一张卡一样**阻于受控容器引擎 500**，故不计入在工。V lane 收口后没有下一张安全卡（1.20.1 侧缺加入者起跳面 ⇒ 需先有 H 面 runner 卡，即 `H1d`；H-3/H-4 属主控决策）。E lane 回到 B2 的剩余范围（其 LAN 形状被 ⑤ 具名阻断，见主计划 §2 分类表；M 在第六轮判断「先做 `H1c` 的环境读数、不做第三次裸重跑」），`lane_next` = `B1-b`（**第一阶段在工**；第七轮定标：只读的仓库侧形状不必等 `H1c` 合并——`H1c` 已并入 `3706524` ⇒ **规范卷写窗自第七轮起空闲**，「真实封存等写窗」的前置已满足，等第一阶段收口即可派封存侧）。**第七轮实测的全 lane 共同阻因**：`docker version` 对 `/_ping` 回 500，凡需挂卷或活体 JVM 的测量、对照与封存在引擎恢复前无法开工；重启用户机上的引擎进程属进程接管，留主控。

### 工作区配方

各会话从最近 `origin/main` 创建不同 worktree/分支；如果目标名已存在先核对归属，不强行覆盖。示意：

```powershell
git fetch origin main
git worktree add -b codex/minekin-auto-entry C:\Users\darling\Documents\agent_work\minekin-wt-auto-entry origin/main
git worktree add -b codex/minekin-dashboard C:\Users\darling\Documents\agent_work\minekin-wt-dashboard origin/main
git worktree add -b codex/minekin-harness C:\Users\darling\Documents\agent_work\minekin-wt-harness origin/main
git worktree add -b codex/minekin-v1201-validation C:\Users\darling\Documents\agent_work\minekin-wt-v1201-validation origin/main
```

这些是**三个分别执行的例子**，不是在当前脏 checkout 里切分支。E 保留当前共享 checkout 直到 B2 checkpoint；之后也迁到独立 worktree。每会话启动都读 `git status --short`、branch/HEAD、远端 main SHA、本文 lane 卡和专项契约。不要 `git reset --hard`、删别人工作树或用 `git add -A` 混入其他 lane 的文件。

### 真实运行资源租约

默认 `minekin-runner-data` 是**规范证据卷**，仅 E 写；M 只读核验。其它会话如需复现用 `MINEKIN_RUNNER_DATA=<该 lane 专用唯一卷名>`、唯一 Kin ID/日志目录、独立容器；`/src` 优先只读挂载。不同容器内 loopback `25565` 不冲突，但 CPU/RAM/网络不足时串行安排 JVM 真跑，不以并发数为目标。只有 E/M 审核后才能把分支证据提升为规范卷引用；不能拷一份旧 PASS 到新 build 充数。真跑四读（verify/rejudge/replay/report_promotion）、独立 oracle、负向反证和失败 attempt 保留。

## 3. 第一波可立即开展的卡

### E1 `P0-CONTROLLED-CAMPAIGN-001`（现行主干 B2）

现有 Qoder 完成 `CORE-040/050` 的 dirty checkpoint，先核对当前 build、case digest、封证与 W60 机器候选，再单独 commit/push。后续按[证据盘点](p0-evidence-inventory-2026-09-26.md)分：已有 fixture 但仅旧 build、缺 fixture、产品未实现、HOST 延迟。`OFFLINE-030`、`ADMIT-001/040/060/100/110` 的当前构建运行可以作为独立证据卡，但它们现为 `mandatory:false`，**补跑不等于 p0-core 全绿**。L3/L5/L6、崩溃恢复、离线身份和 soak 按契约逐项完成；缺断言/产品行为先写小卡，不改判据求绿。E 使用规范卷，控制真实服/客户端和判官。B2 如需修改 H 独占 runner，先停在可复现失败并申请移交。

### S1 `V1201-AUTO-ENTRY-GATE-ORDER-001`

A2 实测 N1：同一 profile 的 `--profile` 路径 2 秒拒止，`--auto-bundle` 路径却先下载数百文件或遍历 3639 项才拒非 loopback；版本 allowlist 也未在自动路径先判。S 在 `prepare_auto_bundle_start` 的 probe/resolve 后、`_provision` 前复用现行可信 profile/地址规则，让非法地址、managed session 禁区、allowlist 与解析结果不一致**先具名拒绝**。测试同一输入对照 X1/X2/Y2 与 B1/B2：被拒时 downloader/JVM 未触发、空 store 仍 0；合法本地目标仍可安装启动。不得改 fixture/registry/测试期望来绿灯，不扩在线认证或远程地址政策。S2 才处理 `--max-bytes 0/-1` 变 INTERNAL_INVARIANT、与 `--profile` 同给被静默忽略的 N2；两卡分提交。

### D1 `DASHBOARD-READONLY-SHELL-001`

按[Dashboard 契约](standalone-runtime-dashboard.md)和[技术栈](technical-stack-selection.md)，在 `dashboard/**` 建 Node 24/pnpm/TypeScript strict/React+Vite 前端，先定义小而稳定的**只读界面**：Kin 状态（idle/running/unresolved/stale）、session/generation、目标/版本/心跳、时间线/告警、证据来源与 unknown 显示。使用明确标注的 mock fixtures 和可替换 read adapter；前端对同一界面测试正常/失联/陈旧/未知/无权限。只呈现已由 Core 可读状态支撑的字段，Persona/成本/Live View 尚无真源时显示“未接入”，不造假数据。Vitest/组件测试/Playwright 本地 smoke + `pnpm build` 必须过；不接真实 Gateway、不保存密钥、不调用 Bridge、无输入按钮/遥控。D2 只有在 G 冻结 Gateway 只读接口后才做真实接线。

### V1 `V1201-PARTIAL-STORE-AND-JOIN-SMOKE-001`

1.20.1 主线单独开一个受控本地验证会话：从当前已审 recipe 和固定本地 offline profile 起，在该 lane 的唯一 Docker 数据卷/新 Kin 中复现 A2 F4 未测的“下载中断后旧 blob 仍可逐件重验”，再做一次本地 status→自动选择→真实 JOIN/PLAYABLE→安全退出的 current-build smoke。对部分 store 要记录哪些 blob 已验证、哪些是 `.staging`、恢复时是否重复抓取/误用；对入服要保存 run/attempt/版本摘要与失败分类。需要服务器独立读数时用自己的受控 server/console，不借 E 的规范卷。若现有 runner 仍不能同 run 自动探测+封证（G1/G2），如实标 `BLOCKED_HARNESS` 并把复现交 H；不得手改判官、搬旧 bundle 或称其为 V08 远程入服。V 只写独立报告和自己分支的复现脚本；产出的 bundle 不自动进入 tested/规范卷，M/E 独立复核后再决定是否引用。机器资源紧张时与 E 约时间轮流跑 JVM，但 S/D 的编码不受阻。

### H1 `V1201-AUTO-PATH-RUNNER-001`（B2 释放文件租约后）

A1 的 G1/G2：`domain.sh` 未识别 `--auto-bundle`，封证入口仍强制 `--profile`；受控服务端默认 `enable-status=false`，无法在同一受控通道既自动探测又收集独立服务器 Pos/Rotation。H 改 runner 编排与本地 server launcher，使自动路径、status、探针和封证同 run 可复现；测试验证原有显式路径不回归、无服务端读数时必须红、私服地址/凭据不入证据。不得改产品代码、case 判据或历史 sealed bundle。需要改 `seal_run_evidence.py` 时先从 E 获得该文件租约；E 正在跑 JVM/封证时不热改 runner。

### M1 集成护栏

审 S/H/D/V 的契约和工程两轴，逐分支在主干最新 HEAD 重跑针对测试与全量基础门；Bridge 变更才追加 Java 21 `check --rerun-tasks`，真运行要求容器和 sealed 证据。合并顺序优先安全修复 S1→S2，证据 E 的已封存 checkpoint，H 的 runner 修复，D 的未集成前端，V 的独立观察报告按相关修复验证时点并入。每次只合一张卡，合后核 `main` 远端 SHA，给各 lane 发新 base；变更导致旧 build 证据失效则先更新证据归属而非“仍绿”。D 可以先 push 分支，但是否进入主干 P0 包须检查 ADR：保持前端独立、不可让 P0 运行依赖 Node/Gateway。

## 4. 第二、三波与完成门

第二波在第一波接口/运行读数稳定后：G 冻结只读 Gateway read model（只读快照/事件游标、来源/陈旧度、字段脱敏、localhost/auth/CSRF/origin），实现独立 Gateway adapter；D 接真 API/WS 并证明断线重连/乱序/陈旧提示；H 扩真跑矩阵与自动路径；E 重跑受影响的 1.20.1 current-build。Gateway 新进程属于 P2，不改变 P0 两进程证据，也不让浏览器持有 Bridge 凭据。媒体 lane 需真实 framebuffer 采集、独立故障与画面 provenance 后才可接 Live View；没有真帧就显示不可用。

第三波按主计划产品依赖顺序拆为 Navigation/Perception、Survival Action/Inventory、Mind/Goal/Persona、Persistence/Memory、Social/Long-soak、Release/UX 多 lane；每 lane 在分配路径和可观察验收前只做契约/原型，不宣称完整自治。HOST §5 三个所有权、PERSIST case IDs、进程接管/数据保留仍是决策门；未拍板时只推进不依赖它们的本地工作。S4 单 Kin 演示须真实客户端连续活动、重启/失败恢复、人格与社会后果的多日证据；S5 多 Kin/跨维度是后续扩展，不作为当前 P0 完成条件。

**里程碑按可演示能力而非提交数计**：M0 本地 1.20.1 同 run 可玩（已封证，但自动 runner 仍需 H）；M1 P0 所需 case/故障门禁真正可复判；M2 经本次授权的 V08 无动作入服；M3 经另次授权的 V09 限幅控制与 V10 demo；M4 HOST/PERSIST 决策和真跑；M5 Dashboard/Gateway/媒体真实接线；M6 单 Kin 生存→自治→社会长期演示。每个里程碑列 PASS/FAIL/BLOCKED、run/bundle/commit/SHA、未测，不能用完成百分比替代。

## 5. 审查、晋级与停机规则

- 每个 lane 同时一张卡；主控只负责集成，不给同一文件两位 owner。依赖通过后直接从本文任务簿/主计划派下一张，减少每小节问用户。出现新缺口先登记范围/证据，主控决定优先级；不能让 Qoder 自行扩产品契约。
- Push 节奏：worker 每卡 push 自己的远端分支并核 SHA；M 双审、针对测试/全量门、真证据后合主干，立即 push `main` 并核 SHA。worker **不得**用共享 checkout `git push origin HEAD:main`，避免并行覆盖。禁强推、禁覆盖未提交改动。
- 远程用户测试服 V08 仍暂停；只有用户明确给**本次只读探测+无动作入服**的目标/时间窗/频率，E 才能连接。V09 look/move 是另一项授权。先前给过地址/offline-mode 并不自动解除“V08 暂不提升”。
- 在线认证、扩大公网访问、HOST/PERSIST 三格所有权、数据删除/进程接管属重大决策；不能由并行策略代答。若阻断一 lane，停该 lane 并推进其它已授权 lane；无安全工作时报告具体选项一次，不新造审计格。
- 所有 mock、read-only、单测、CI、ping、真实入服、sealed evidence 在状态表分列；分支 PASS 不等于主干 DONE，W60 `promotable` 不等于 `p0-core tested`。真正完成项目需主计划的产品契约和真实证据门全部达到，而非各 agent 都回复“完成”。
