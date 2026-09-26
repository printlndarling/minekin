# Minekin 并行开发调度计划

版本：2026-09-26。目的：把一个串行 Qoder 会话拆成可独立推进的实现、前端和真实验证工作流，同时保留当前证据门禁和用户决策边界。本文是**并行作业协议**，不是宣称这些能力已经完成；上线前须由主控把它与 `development-execution-plan.md` 的主干状态原子对齐。

## 1. 当前现场与启动条件

制定本计划时远端 `main`/工作分支均为 `6f0f562`，Qoder 的共享工作树正在改 B2 `P0-CONTROLLED-CAMPAIGN-001` 的四份文档与一份新证据记录，尚未提交。B2 第一刀 `CORE-040/050` 在本地受控 1.21.4 上得到当前构建的 sealed PASS，W60 只是 `promotable` 候选；`p0-core` 仍缺 fixture/真实证据。A1 的 1.20.1 本地自动装机→PLAYABLE→look/move→释放同 run PASS 已封存；V08 用户远程服仍 `BLOCKED_DECISION`。Dashboard/Gateway/Web API/媒体 worker 均未实现；P0 ADR 0001 明确 P0 不引入 Web API 或 Dashboard。

**立即生效的保护**：原 Qoder 先完成或安全停放 B2 当前脏改，不能因本计划丢弃它。其它会话只在独立 Git worktree + 独立分支施工，绝不在共享 checkout 上写。主干继续只有 B2 一个 `NEXT`；并行分支使用下文各自的 `lane_next`，只代表该分支可开发，不代表主干验收。主控审完并合并本计划后，在现行主计划加一条“每 lane 一个 NEXT、主干一个 integration NEXT”的状态规则；此后不得再用“全库只有一个 NEXT”阻止已划清路径的并行分支，也不得把未合并分支写成主干 `DONE`。

## 2. 工作区、所有权与共享资源

| Lane / 初始 `lane_next` | 独占修改面 | 禁止碰的面 | 可交付的第一张卡 |
| --- | --- | --- | --- |
| M 主控/集成 | `docs/development-execution-plan.md`、`docs/development-todo.md`、`docs/qoder-execution-handoff.md`、本计划、合并/门禁记录；主干 refs | 不在他人正在施工的分支改代码；不替执行者改判据求绿 | B2 checkpoint → 启用并行规则 → 逐分支双审和合并 |
| E 真实运行/证据 | 当前 B2 专属证据记录、其 case/判官必要改动；规范数据卷的**唯一写入者** | `dashboard/**`、自动入口产品代码、他人独立卷；不得连接用户远程服 | B2 当前构建的剩余受控证据，缺 fixture 与未实现行为逐条分开 |
| S 自动入服安全 | `src/minekin_core/cli/auto_session.py`、必要 `bootstrap.py`/`server_profile.py` 和对应单元/契约测试（路径若需扩大先给 M） | `test-orchestrator/**`、证据工具、case fixtures、registry、规范卷、主计划 | `V1201-AUTO-ENTRY-GATE-ORDER-001`；之后 N2 预算参数校验，另卡另提交 |
| H 测试 Harness | `test-orchestrator/runner/**`、`tools/run_controlled_server.py`、对应 runner 契约测试；`seal_run_evidence.py` 需与 E 协调独占窗口 | 产品 `src/**`、`bridge*/**`、case 判据、registry、规范卷、主计划 | `V1201-AUTO-PATH-RUNNER-001`（G1/G2）；**等 E 不再改/依赖该批 runner 文件后才开工** |
| D Web Dashboard 前端 | 新增 `dashboard/**`，只含前端、类型/模拟数据、前端测试、局部说明 | `src/**`、`bridge*/**`、服务端 API、数据库、游戏输入、真实媒体宣称、主计划 | 只读状态/时间线 mock-first 垂直切片；不合并为 P0 运行产品 |

另设候补 **G Gateway 只读投影**：待 M 冻结浏览器读模型与 P2 进程形态后，单独拥有新 `gateway/**`；不可在 P0 Core 里偷偷塞 FastAPI/WS，不可直接暴露 SQLite、Bridge socket 或带凭据原始事件。**P2 媒体**也待真实采集和授权接口冻结后开新 lane；不能用假画面充 Live View。

同一文件仅一名 owner。任何跨 lane 修改都先在 M 的冲突表登记：需求、目标文件、当前 owner、移交时点；不能两边各写一半再指望 Git 自动合。每张卡附 base SHA、diff stat、测试原始结果、未测、阻断；分支 commit 后立即 push 本分支供审查，**只有 M 能更新 `main`**，且仅在证据/测试通过后按依赖顺序集成。失败分支保留，不能靠重写历史隐藏失败。

### 工作区配方

各会话从最近 `origin/main` 创建不同 worktree/分支；如果目标名已存在先核对归属，不强行覆盖。示意：

```powershell
git fetch origin main
git worktree add -b codex/minekin-auto-entry C:\Users\darling\Documents\agent_work\minekin-wt-auto-entry origin/main
git worktree add -b codex/minekin-dashboard C:\Users\darling\Documents\agent_work\minekin-wt-dashboard origin/main
git worktree add -b codex/minekin-harness C:\Users\darling\Documents\agent_work\minekin-wt-harness origin/main
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

### H1 `V1201-AUTO-PATH-RUNNER-001`（B2 释放文件租约后）

A1 的 G1/G2：`domain.sh` 未识别 `--auto-bundle`，封证入口仍强制 `--profile`；受控服务端默认 `enable-status=false`，无法在同一受控通道既自动探测又收集独立服务器 Pos/Rotation。H 改 runner 编排与本地 server launcher，使自动路径、status、探针和封证同 run 可复现；测试验证原有显式路径不回归、无服务端读数时必须红、私服地址/凭据不入证据。不得改产品代码、case 判据或历史 sealed bundle。需要改 `seal_run_evidence.py` 时先从 E 获得该文件租约；E 正在跑 JVM/封证时不热改 runner。

### M1 集成护栏

审 S/H/D 的契约和工程两轴，逐分支在主干最新 HEAD 重跑针对测试与全量基础门；Bridge 变更才追加 Java 21 `check --rerun-tasks`，真运行要求容器和 sealed 证据。合并顺序优先安全修复 S1→S2，证据 E 的已封存 checkpoint，H 的 runner 修复，D 的未集成前端。每次只合一张卡，合后核 `main` 远端 SHA，给各 lane 发新 base；变更导致旧 build 证据失效则先更新证据归属而非“仍绿”。D 可以先 push 分支，但是否进入主干 P0 包须检查 ADR：保持前端独立、不可让 P0 运行依赖 Node/Gateway。

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
