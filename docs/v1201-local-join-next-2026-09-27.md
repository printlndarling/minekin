# 1.20.1 本地加入解阻：主控连续任务卡

状态：`PROPOSED_FOR_M_INTEGRATION`。基线为远端 `main` 的 `e3b1c6f8e38d4ced74770606290874ccfde0dc8e`；本文件所在分支经 M 审查合入后，以下队列才激活。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；本文件给 H、V、E 顺序派卡，**不设第二个主干 NEXT**。

## 0. 已作出的选择与仍未作出的选择

用户已明确要求按服务器版本自动选择受审客户端，并以 1.20.1 为现阶段主线。这足以排除“把 1.20.1 profile 强行改报 1.21.4”或“只支持 1.21.4”的路线，**不是一次新的远程服连接授权**。本卡只解受控本地 1.20.1 第二客户端的准入和可观测性，不改变 V08 的 `BLOCKED_DECISION`。

已核代码：`src/minekin_core/adapters/launcher/server_profile.py` 的 v1 `load_server_profile` 固定只接受 loopback、offline 和 `MINECRAFT_VERSION = "1.21.4"`；`domain.sh` 的 H1f 已让加入者 profile 诚实填本次 `launched_version`，所以 1.20.1 被 v1 准入拒在 JVM 之前。**不要把 v1 常量改成 1.20.1，也不要为求绿绕开准入。**同一模块已提供 v2 `ManagedTargetProfile`：`load_joinable_session_target` 仅允许 loopback 且版本 allowlist 恰一项，`require_target_allows_launch` 再与本次实际版本比对。此处最小闭环是在受控 runner 的 1.20.1 加入者路径写出符合已审 v2 形状的 loopback profile，保留 1.21.4 既有 v1 字节和行为；若实测证明现有 v2 路径仍无法承载，停下来具名报告，不临时修改产品安全策略。

`src/minekin_core/adapters/launcher/metadata.py` 也有默认 `1.21.4`，但**现在没有证据说明它是这一次准入拒止的执行点**。先用真实调用链测量，若 profile 解阻后才暴露这里的错误，再由 M 开独立产品卡；禁止把两个常量一起盲改。

仍需另外决定、不可由本队列代答：HOST §5 的所有权三格；`minekin.p0.evidence.v1` 跨 bundle 三段链载体及重封范围；OFFLINE-090 Dashboard 载体；`domain.sh` 原有 auto+joiner 组合拒止是否改变；FORWARDED_VARIABLES 的产品语义；远程服 V08 的新授权；任何认证/公网放宽、数据删除或进程接管。这些只阻断其各自的卡，**不阻断下面的本地手动加入复测**。

## 1. 现场基线和证据边界

- 远端 `main=e3b1c6f` 时，V3 `V3-1201-JOIN-LIVE-READOUT-AFTER-H1F` 只交付 `PARTIAL` 活体读数：runner 生成的加入者 profile 是 1.20.1，产品 v1 准入随后拒绝；加入者 JVM 没有启动。由此不能把客户端 stderr 无 `GLFW 0x1000E` 当作故障已排除。
- E 在第十四轮已经于**本地隔离服**封存 OFFLINE-100 的 A1/B/A2 三段。三份 bundle 各自可验证，不等于跨 bundle 父断言 PASS；`A_B_A_TRIPLE_NOT_SEALED` 保持不动。再跑同样三段不会补上链载体，不再为它占 E 写卷窗口。
- 当前 `W30`/`p0-core` 仍 `promotable: false`；已封 PASS、单测绿、文档声称、只读 ping 都不能代替本次 1.20.1 加入者真启动、JOIN 与首快照。规范卷 `minekin-runner-data` 仅 E 可写，H/V/M 只读或不挂载。

## 2. 连续队列：一张完成、审查合入并核远端 SHA 后再提升下一张

### H1g `V1201-JOINER-LOCAL-V2-PROFILE-001` — H lane 的下一张

**前置**：M 合入本计划；H1f、H1e 已在主干；E 无需交出规范卷写窗，因为本卡不写它。

**允许面**：`test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/` 记录。确有必要才改 runner 自己的 fixture/脚本，并先在记录里列明；不改产品 `src/**`、Bridge、判据、registry、门禁、封存 schema、`domain.sh` 的 auto+joiner 拒止。H 在独立 worktree/分支从当时最新远端 `main` 起卡，不能直接推 `main`。

**实现边界**：只对本地受控的 1.20.1 加入者输出已审 v2 的 profile，目标必须为 `127.0.0.1` 或 `::1`、`auth_mode=offline`、`version_policy.mode=explicit_allowlist` 且 `allowed_versions` 仅为本次 `launched_version`、`target_authorization` 为受控 runner 的可归因固定来源。不得从 server status 展示文本、聊天、环境猜测版本，不可用在线认证，不可让 v2 远程 IP 在 `session start` 路径放行。1.21.4 加入者继续走原 v1 形状，旧 profile 测试不漂移。若 v2 精确字段要求与此冲突，停止并交 M 审，不自行放宽 loader。

**验收**：先用 H1f 当前字节复现 1.20.1 profile 的 v1 准入红；新字节下 1.20.1 v2 受控目标能通过 `load_session_server_profile(..., minecraft_version="1.20.1")` 且加入者确实越过 `launcher.profile`；1.21.4 v1 控制组字段和拒止行为保持原样；空版本、版本错配、多项 allowlist、非 loopback、online、无授权字段分别在客户端 JVM 前具名拒止；至少一项非空转反证把新的版本分派退回旧形状后让目标测试转红。`bash -n`、定向契约、ruff/pyright/边界检查及可运行的全量本地测试通过；若全量因资源型 flaky 失败，原始失败与独立复跑并列，不写成全绿。本卡不封证、不宣称 JOIN。

**停止**：第一个真实前沿仍在 profile 准入之外时，只报告精确停点，不顺手改 `metadata.py` 或游戏客户端。M 按真实 merge-base、允许路径、反证和合并树测试双审后合入，立即 push `main` 并核远端 SHA。

### V4 `V1201-LOCAL-JOIN-AFTER-V2-001` — H1g 合入后提升 V lane

**允许面**：V 私有本地测试根和一份新 `docs/validation/` 记录；规范卷 `:ro` 或不挂，产品/runner/判据/registry 零改动。仅连接由受控 runner 本次启动的本地 1.20.1 服，不读、不用用户远程目标配置。

**验收**：同一 run 明列服务端实际版本、加入者 profile schema/version、客户端 JVM 是否启动、Bridge 握手、JOIN/首快照、`GLFW 0x1000E` 与 `XDG_RUNTIME_DIR`、预算/Bridge 取料停点；逐项区分 `PASS`、`FAIL`、`未达到该阶段`。配一个 1.21.4 正对照与一项版本错配反证。若完整加入并达到 `PLAYABLE`，仍仅记为 V 私有活体读数，不冒充规范卷 sealed evidence；若失败，保留 stdout/stderr/crash 原物，按单一最先失败层归因并交 M 排独立修复卡。

**派工前置（桥产物落点由 M 在 2026-09-27 按字节实测；供给停点那条注明出处）**：

- 1.20.1 的 `minekin-bridge` 是 `workspace:` 取料，相对路径写死在 `recipe.py:74`
  （`bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`）。该 jar 是**未入库的构建产物，不随分支走**：
  2026-09-27 实测 `minekin/` 与 `minekin-wt-evidence/` 各有一枚，sha256 `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`、
  1310604 字节；`minekin-wt-integration/` 与 `minekin-wt-h1g/` 里没有。V4 要把已核字节那枚**复制进自己的 worktree**
  （`find_workspace_root` 把 workspace 根解析为容器里的 `/src`），并在记录里写明 sha256 与落点；不重新构建、不伪造取料源。
- 越过 `launcher.profile` 之后的第一停点**已由 H1g 读数②c 量到**（`主控侧未复量`）：一次性空 store 下
  `3638 of 3638 artifacts are not in the store yet, starting with com.mojang:minecraft:1.20.1`。
  那是空 store 的形状产物，不是出厂路径：真实受控 run 会把 host Kin 的 store `cp -a` 给 joiner
  （`domain.sh:713-727`）。V4 必须在**已备好物料的私有 store** 上跑，且不得把这一句读成 1.20.1 的预算/Bridge 前沿。

### E6 `V1201-LOCAL-JOIN-SEAL-001` — 仅 V4 真正达到可封的 JOIN/首快照后提升 E lane

**允许面**：E 独占规范卷写窗、其 lane 的证据记录；只调用已登记的 1.20.1 case 和现行判据，不改 case/registry 求绿。新 Kin/新 attempt，旧 FAIL 与 PASS 原样保留。

**验收**：当前 build 的同 run 真客户端、Bridge、JOIN、首快照，以及需要的释放/停止，按 case 封存后 `evidence verify`、独立 `rejudge`、适用 `replay`、`report_promotion` 四读和非空转反证；明确 run/bundle/attempt id、case_version、build 与门载荷前后差。材料不足保持 `BLOCKED_EVIDENCE`，不凭 V4 文档写 `DONE`。

### M 收口与下一段

M 对 H1g/V4/E6 逐张复审、单独合入、推送、核远端 SHA，真实发生的状态再回写主计划和短 TODO。若 H1g 或 V4 暴露的下一前沿是产品 `metadata.py`/Bridge/预算等，M 只能基于**具名活体材料**另开一张窄卡，写 owner、允许面、反证和验收，再派对应 lane；不能让同一卡横跨 runner、产品和证据卷。1.20.1 本地证据收口后，V08 仍等待用户对**该次远程服连接**的明确授权；没有授权时继续推进互不依赖的 Dashboard Gateway 只读契约或 B2 case/证据设计，但不把待产品决定的链载体自动扩字段。

## 3. Qoder 单会话续跑提示词

```text
/goal 阅读 docs/qoder-execution-handoff.md 的恢复步骤、docs/development-execution-plan.md 顶部“2026-09-27 1.20.1 本地加入解阻”覆盖段，以及 docs/v1201-local-join-next-2026-09-27.md。你是 M 集成主控；先核本地/远端 main、worktree 与脏文件，并按真实 merge-base 审查和合入这份规划分支（codex/minekin-next-1201），不得覆盖活动 lane。现行主干唯一 current_next 保持 PARALLEL-INTEGRATION-GATE-001；H lane 先执行 H1g，M 双审合入并立即 push、核远端 SHA；然后 V4 本地活体复测；只有 V4 真到 JOIN/首快照才派 E6 独占规范卷封证。每卡只改允许面，先本地/Docker 测，再 commit/push lane，M 逐卡合 main；失败保留材料并按最先失败层开窄卡，继续做独立安全任务。保持 v1 的 1.21.4 冻结行为，1.20.1 本地加入使用现成 v2 loopback/offline/单版本准入，绝不把 1.20.1 假报为 1.21.4，绝不为求绿放宽远程地址、在线认证、判据或 auto+joiner 拒止。不要连接用户远程服；V08、HOST/PERSIST、跨 bundle 证据 schema、Dashboard 载体仍待各自明确决策。每个交付用“已合主干／仅在分支／真实封证／未验证”四态报告；不要因为 integration 待审分支一时为空就结束 goal，按此连续队列机械推进到真正边界。
```
