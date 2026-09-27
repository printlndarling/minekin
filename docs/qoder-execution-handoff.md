# Qoder / 新会话连续执行交接

> 2026-09-27 第三十六轮后交棒点（规划分支 `codex/minekin-local-control-next`，基线 `main=d26a2dd`；**第三十七轮：M 审查后已合入，merge `24ac6e0`，非 docs 改动面 0，CI run `36301474388` success**）：E6 真封证有效，但它是**专服单客户端** `V1201-020`，不是 V4 的**第二客户端 LAN 世界**复现；`reviewed-tested-bundles.json` 已有该案同构建 seq2 PASS 引用，当前不替换、不翻 mandatory 求绿。下一条可执行本地路线见[H1h→V5→M-C1→E7→M-G1 连续任务卡与单会话提示词](v1201-lan-control-next-2026-09-27.md)。主干唯一 integration `NEXT` 不变；**第三十七轮在工的是三张卡：H lane 的 H1h（仅在分支 `codex/minekin-lan-joiner-bounded-control`，base `24ac6e0`，工作树 `minekin-wt-h1h`）、M 的载体卡 M-C0（仅在分支 `codex/minekin-probe-target-carrier`，base `5d0cd2a`，工作树 `minekin-wt-mc0`）、以及本轮新派的 V5a 前置活体量测（分支 `codex/minekin-v5-probe-target-preflight`，base `8dfeac6`，工作树 `minekin-wt-v5`）——三树到本节写定时都仍是零提交、远端无 ref；H1i 依 §2.2 排在 H1h 与 M-C0 之后，V5/M-C1/E7/M-G1 未开始，LAN 第二客户端控制封证仍为 0**。V08、HOST/PERSIST、跨 bundle schema 等未因本规划获得授权。下方旧“只剩三道门/无安全下一张”仅是当时读数，以本交棒点为准。

> 2026-09-27 新交棒点（规划分支 `codex/minekin-next-1201`，基线远端 `main=e3b1c6f`；须经 M 审查合入才激活）：第二十四轮“lane 待审队列为空”仅说明没有待合分支，**不说明 Minekin 已完成**。用户此前已经选定 1.20.1 主线及按服务器版本自动选受审客户端；下一条可执行的本地解阻路径见[H1g → V4 → E6 连续任务卡与单会话提示词](v1201-local-join-next-2026-09-27.md)。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；H1g 是 H lane 的下一张（**第二十六~二十七轮回写：H1g 已双审合入主干，准入层解阻已量到；当前在工的是 V lane 的 V4，E6 未提升**）。先保留 v1 的 1.21.4 冻结行为，用现成 v2 的 loopback/offline/单版本受管目标验证 1.20.1 加入者；不要把 V3 未起 JVM 的记录说成已排除 GLFW 故障。远程服 V08 和证据 schema 决策没有因本次排卡获得授权。下文旧“无安全下一张”段落是其当时读数，以本交棒点和现行主计划顶部覆盖段为准。

更新：2026-09-27（本文的轮次按「第 N 轮」顺排，**文末最后一节即最新一轮**；旧轮次正文里「最新一轮是第十二轮」那句只是当时的读数）。旧 875 行交接（包括 Qoder 未提交的第七类审计草稿）完整保存在[历史交接](qoder-execution-handoff-history-through-cef712b.md)；其中旧 `NEXT`、旧 run 读数、旧“队列为空”不再指挥执行。现行唯一队列是[执行计划](development-execution-plan.md)。

## 每次启动与上下文丢失后的恢复步骤

1. 在 `C:\Users\darling\Documents\agent_work\minekin` 运行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、`git log -8 --oneline`、`git ls-remote origin refs/heads/main refs/heads/codex/core-state-transition`。记录 HEAD/两 ref/dirty 文件，勿 reset/stash/覆盖他人改动；远端与本地分叉先停下协商。**2026-09-26 lane 化后的补充口径**：主干 `main` 只由 M 移动，lane 会话一律在自己的 worktree + 分支上工作（清单见[并行作业协议](parallel-execution-plan.md) §2：E `codex/minekin-evidence` @ `../minekin-wt-evidence`、H `codex/minekin-harness` / `codex/minekin-auto-path-runner` / `codex/minekin-controlled-server-status` / `codex/minekin-auto-path-status-wiring`、S `codex/minekin-auto-entry`、D/V 各自分支），启动时把上面那条 `ls-remote` 的 ref 列表换成「`refs/heads/main` 加本 lane 分支」；`codex/core-state-transition` 只是 B2 checkpoint 的历史落点，不再作为执行侧的推送目标。
2. 读[执行计划](development-execution-plan.md) 的 `current_next` 和该卡、[短 TODO](development-todo.md)、[1.20.1 路线](version-auto-to-server-control-plan.md)、该卡专项契约。以当前树/当前规范数据根的机器读数确认卡的前置，不以历史 `DONE` 文本或 `.tmp` 产物代替。
3. 逐卡只改 `allowed_paths`，先本地/Docker 验证和真实 sealed evidence，再规格/工程双审查、commit、立即 push 工作分支与 `main`、核远端 SHA；下一卡只能在上一卡五项齐全后提升。CI 额度不足时不等 CI 代替本地；CI 红时如实记录，不声称绿。**2026-09-26 主控改口径**：本条的「push `main`」在 B2 证据 checkpoint 之后失效——执行侧停止直接写 `main`，B2 后续作为 E 证据 lane 只推独立分支（见「目前交棒点」末段）。
4. 遇用户产品选择、远程服新授权、HOST/PERSIST、在线认证、数据删除/进程接管或判据冲突，停在 `BLOCKED_DECISION`；允许推进文档已经明确排好的独立安全卡，但不可新造“再审计一次”卡填空。

## 目前交棒点

`cef712b` 时 Qoder 已停止且留下三份未提交旧文档草稿。本次整理已把草稿连同所有历史内容保存为同级 `*-history-through-cef712b.md`，新现行文件从零建队列。

A1 `V1201-LOCAL-DEMO-REHEARSAL-001` 已于 2026-09-26 收卡：在全新 data root 与全新 Kin 上，一次自动路径 `session start` 同 run 完成装机（`installed 3639 / reused 0`）、JOIN、`PlayableEstablished`、限幅 look+move、租约到期释放与 `session stop` 退出，按现行 case `V1201-040` 封存为 PASS，四读一致（`verified PASS` / `re_judged AGREES` / replay 23 事件 / 当前 build），七类单项删除各自把对应断言判红；两次失败 attempt（服务端无读数的 sealed FAIL、供应链中断的 partial store）都原样保留。原始读数、复现命令和三格缺口在[执行计划 §2、§3.1](development-execution-plan.md#2-上一卡交付与当前-next-边界)。

A2 `V1201-LOCAL-NEGATIVE-MATRIX-001` 已于 2026-09-26 收卡：六族负向全部量出当前 build 的真实读数——18 行真 socket 状态探测（正对照 `control_1201` `OBSERVED`，其余按名归类，`FAIL=0`）、自动入口对伪造显示文本与多版本代理各 `NEEDS_PIN` 且 store 0 文件、profile 装载期禁区地址四拒（连接计数证明拒在发出字节之前）、显式路径五条准入拒 + Bridge 钉错两拒（同一 store 下未变 recipe `launchable: true`）、`V1201-060/070/080` 本 build 重读 `PASS / agrees`。新量到的产品缺口是自动入口的门序：`--auto-bundle` 下装机先于 join 授权与版本 allowlist（X1 秒拒 vs X2 下 388 文件、Y2 等 3639 全过才拒、`java=0`）。逐行读数、配对反证与四格缺口登记见[负向矩阵复判记录](version-negative-matrix-2026-09-26.md) 与[执行计划 §2、§3.2](development-execution-plan.md#2-上一卡交付与当前-next-边界)。

A3 `V1201-TESTED-GATE-READOUT-001` 已于 2026-09-26 收卡：规范卷只读复判量出 provenance `verified / rc=0`（`tested` 摘要已被真算真比，不再是文本）、六条 1.20.1 引用四读一致且 `from_repository_build: true`、条目 19 能力与六 case 断言双向差集为空、`report_promotion` 三门仍 `false`（W60 `CASE_VERSION_MISMATCH`、W70 `NO_MANDATORY_CASES`、`p0-core` 两者皆有），并列出卷内 15 次 attempt 的引用/旧 build/sealed FAIL 分布；四条反转证明读者能判红。逐条读数与边界见[tested 门禁复判记录](tested-gate-readout-2026-09-26.md)。

B1 `P0-EVIDENCE-INVENTORY-001` 已于 2026-09-26 收卡：规范卷只读四桶盘点把契约要求的 74 条 case 逐条标注为 `missing_fixture 31 / no_current_build_evidence 28 / real_failure_on_current_build 0 / current_build_pass 15`（每条恰落一桶），28 条按成因（`no_bundle_on_this_root 18`、`only_another_build 10`）与判据形状（要运行材料且本根零 bundle 1 条、只有别的构建的 bundle 10 条、只需仓库字节但零 bundle 17 条）各切一刀；11 门的 block 分成三种语义（缺定义 / 缺当前构建真跑 / 缺主控的门禁决定），收卡时 W60 与 `p0-core` 只阻在 `CORE-040`、`CORE-050` 的 `CASE_VERSION_MISMATCH`（该读数已由 B2 第一刀改变，见下一段；原读数在记录里按 `37f8deb` baseline 保留）。「产品未实现」在已注册 case 上为空，在缺 fixture 侧点名 6 条整条 + 2 个半句，HOST 18 条不判。四条反证各移一个机制（删 fixture、空数据根、把通过行改成 `FAIL`、改一位 case 摘要），后两条会同时触发视图与晋级规则的对账护栏。盘点一张门都不点亮。逐条读数见[P0 证据盘点](p0-evidence-inventory-2026-09-26.md)，两张建议卡与两类产品事实决定登记在[执行计划 §3.3](development-execution-plan.md#33-b1-交出的缺-case-排卡按-12-单独登记不由-b1-顺手写断言也不自占队列)。

B2 的第一刀 `P0-CORE-040-050-RUN-001` 已于 2026-09-26 完成（**B2 本身仍是 E lane 的 `NEXT`，不收卡**）：在规范卷 `kin-01` 上补了三轮受控本地 dedicated offline 真跑（jar 实测与 `SERVER_RECIPES["1.21.4"]` 的 pin 相同），`CORE-040`、`CORE-050` 各留一份当前构建的 PASS bundle，`case_version` 逐字节等于今天的摘要、`from_repository_build: true`，四读齐全（封证 verdict、`evidence verify`、`report_promotion` row、独立复判 `observed=6/6` 与 `4/4`、`disagreements=[]`）；W60 因此从 `CASE_VERSION_MISMATCH` 转为 `promotable: true / blocks []`，`p0-core` 只剩 `REQUIRED_CASE_NOT_REGISTERED`。反证四组：撤掉任一判绿 run 该门立刻回红，只改一位封进去的字节则 `EVIDENCE_NOT_VERIFIED` + `rc=12` + 复判 `unjudged`、而规范卷同一 run 仍 `verified`。`CORE-050` 第 1 次 attempt 真实 **FAIL**（本次命令漏 `MINEKIN_DOMAIN_STILL=1`，`--hold-at join` 下 harness 不代跑静默等待 ⇒ `NO_SERVER_READINGS`），判据未改、材料保留。逐条读数、复现命令与「本卡不声称」见[CORE-040 / CORE-050 当前构建真跑封证](p0-core-040-050-run-2026-09-26.md)。

当前 **E lane** 的 `NEXT` 是 **B2 `P0-CONTROLLED-CAMPAIGN-001`**（主干 `NEXT` 是 M 的 `PARALLEL-INTEGRATION-GATE-001`，见[并行作业协议](parallel-execution-plan.md)与[执行计划 §2](development-execution-plan.md#2-上一卡交付与当前-next-边界)的 lane_next 表；B2 属 §4 B 段第二张，B1 已满足其「inventory 后」前置；在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle。**第一刀 `CORE-040`/`CORE-050`、第二刀 `OFFLINE-030`、第三刀 5 条 `ADMIT-001/040/060/100/110`、第四刀 `CORE-030`（LAN）与第五刀 4 条仓库自检行（`OFFLINE-001/040/050` + `ADMIT-080`）已交；B1 §6 三格里的非 deferred 形状至此清空，剩余是卡面后半段 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak（要新场景与新判据），以及整族 deferred 的 `HOST*`（13 条「只需仓库字节」+ `HOST-030/040`，前置是 ownership 决策）**）。**本轮交的这些行都在 `non_mandatory` 名单里，再跑也不会动任何一门**；今天 11 个包的 block 字段里没有 `CASE_VERSION_MISMATCH`，剩下的阻因是 `REQUIRED_CASE_NOT_REGISTERED` 与 `NO_MANDATORY_CASES`，属 case 设计与门禁决定（主控）。**禁止连接用户远程服；V08 仍未提升**，A4 是新的授权门，B 段推进不等于入服许可。W60 的 `promotable: true` 只是机器候选，**晋级属 `P0-GATE-PROMOTION-001`（主控）**，它既不等于 `p0-core tested`，也不等于任何门已点亮；执行侧不翻 `status/gaps`、不改 case/registry 求绿。A1 留下的 `V1201-DEMO-CASE-FREEZE-001`、A2 留下的 `V1201-DISK-PREFLIGHT-001`/`V1201-SRV-RESOLVER-001`，与 B1 留下的六个产品事实载体问题、`ADMIT-030/050` 的 case id 拆分都是 `BLOCKED_DECISION`，留在主控手里；B1 交出的 `P0-OFFLINE-090-100-EVIDENCE-CHECK-001` 是 `QUEUED_PROPOSED`，排期是主控动作。本地真跑再受 runner 缺陷阻断时，保留原始材料并按需另登修复卡。

**2026-09-26 主控对 B2 后续工作的边界（覆盖本文更早的推送口径）**：证据 checkpoint 之后执行侧**停止直接写 `main`**；B2 的后续一刀作为 **E 证据 lane 在独立分支**推进，由主控决定分支名与合入时机。执行侧使用的受控通道是仓库内 `test-orchestrator/runner/run.sh` 与 `test-orchestrator/runner/domain.sh`（服务端 `tools/run_controlled_server.py`，判据 `tools/assert_case_evidence.py`，封证 `tools/seal_run_evidence.py`，读数 `tools/report_promotion.py` / `tools/rejudge_evidence.py`），镜像 `minekin-runner:local`，**规范数据卷 `minekin-runner-data`（容器内 `/data`，证据在 `kin/kin-01/run/evidence/<run>`、attempt 登记在 `evidence-attempts.sqlite3`）**；只读读数一律以 `-v …:/src:ro -v minekin-runner-data:/data:ro` 挂载并在 `/tmp` 副本上做破坏性动作。

**B2 证据 checkpoint 已落地（2026-09-26，交主控）**：两刀的证据文档与 lane 化后的状态口径落在提交 `57cb274`（第二刀记录 + 计划/TODO/交接更新）与其上的合并提交 `e6f3e7a`（手工并入 `origin/main` 的 `23d04d5` lane_next 激活，逐字保留 `current_next: PARALLEL-INTEGRATION-GATE-001`、lane_next 表和 integration gate 行；对该计划文件的改动相对主干只是追加第二刀事实）。**推送只到 `codex/core-state-transition`**：本地 HEAD、`git ls-remote` 的该分支 SHA 同为 `e6f3e7aa0bf51b88b5ec6d02ae2b2fa80c7a4072`，而 `refs/heads/main` 仍是 `23d04d5…`（M 的 activation 提交，未被执行侧移动）。合并后在同一挂载上重跑第一刀的只读复现脚本，读数与合并前那份**逐字节相同**（`diff` 为空）：`attempts 54 / bundles 90 / from_another_build 61 / unverified 0`，`CORE-040 85a97e3b PASS+AGREES 6/6`、`CORE-050 c20a20f1 PASS+AGREES 4/4`、`eb7f9086 FAIL+AGREES 3/4` 原样在卷，W60 `promotable: true / blocks [] / requirement.satisfied: true`，`p0-core` 与 overall 仍 `false / REQUIRED_CASE_NOT_REGISTERED`。门禁：合并解决后 ruff check、`ruff format --check`（332 files）、pyright 0 errors、boundaries、140 条 case assertions、fixture digests、workflow pins 全绿；全量 `pytest` 是合并前在同一工作树上跑的（`2501 passed, 2 skipped in 441.58s`），合并本身只动 docs。**待主控给**：E lane 的独立分支/worktree 名（当前 E 仍占共享 checkout 的 `codex/core-state-transition`），以及 `PARALLEL-INTEGRATION-GATE-001` 对本 checkpoint 的审查时机。

## 主控答复与本轮交棒（2026-09-26，M，覆盖上一条「待主控给」）

- **E 两问已答**：lane 分支/worktree 早已给——`codex/minekin-evidence` @ `minekin-wt-evidence`（main `300ed07` 迁移，规范卷唯一写入者不变）；checkpoint 审查已完成——`e6f3e7a` 与 handoff `6a02ac6` 经双审合入主干。**E 的下一步**：按[执行计划 §3.2 N1 行](development-execution-plan.md)在下一轮受控真跑里补 S1「先拒后装」的规范卷重跑读数（重跑 X1/X2/Y2 与 B1/B2 三组行；S1 实现已在主干 `b88e36f`），其余 B2 剩余动作按卡面与 §3.3 排期，`BLOCKED_DECISION` 群不动。
- **主干现状**：`main` 已推进到本轮各合入（S1 `b88e36f`、V1 `eb6f63d`+lint 修 `536a3d0`、D1 `8aab153`，及计划/协议回写提交；确切 SHA 以 `git ls-remote origin refs/heads/main` 当场读）。lane 会话冷启动一律 fetch 后以最新远端 `main` 为 base 重建分支再开新卡。
- **各 lane 下一张**：S→S2 `V1201-MAX-BYTES-VALIDATION-001`（N2）；H→H1 `V1201-AUTO-PATH-RUNNER-001`，开工前先看 V1 报告的 H-1..H-5 交办项（其中 H-3/H-4 触产品 `src/**`，等 M 另卡，H 不越界）；D→停等 G lane 冻结只读契约；V→停等 H-1/H-2 落地后 M 重新派卡；合并节奏按协议 §5「每合一张即推 main、核远端 SHA」。

## E lane 回复：N1 收口读数已交 + 两条基础设施更正（2026-09-26，E @ `codex/minekin-evidence`）

- **主控本轮派给 E 的那张已交**：按 §3.2 N1 行在规范卷基线上重跑复判记录 §3 的三组行（X1/X2、Y1/Y2、B1/B2），
  读数、复现命令、反向对照与边界见[S1 门序重跑读数](s1-gate-order-rerun-2026-09-26.md)。被测构建是主干 `ed37260`
  （含 S1 实现 `b88e36f`），三个 `.tmp/` 脚本与期望**一字未改**。关键读数：X2 由 `exit=124 / store 388 文件 / 3 条 fetching`
  变为 `exit=17 / store 0 / 0 条 fetching`；Y2 由「`fetching 3639/3639` 之后才拒」变为「整份输出 1 行、装机之前即拒」，而同一份
  满 store 的 Y1 仍穿过 join 授权（停在下一段 Bridge 未构建上）⇒ 决定因素是 host 而不是走到哪算哪；B1/B2 由 `exit=124`
  变为 3–4 秒具名 `ADMISSION`（分别是 allowlist 与解析版本不符、allowlist 列两个版本），十三行拒止之后的 store 由 **290 文件**
  变为 **0 文件**，未改动的正对照 C1 仍进入装机。反向对照：把 `b88e36f` 的父提交 `300ed07` 导出成只读 `/src` 重放 X 组，
  旧读数 `exit=124 / store 354` 在同机同镜像上复现。**本收口只关门序，不封 bundle、不动任何门**：W60 / `p0-core` / overall
  与 checkpoint 那份逐字节相同。两个需要主控知道的读数缺口：B12/B13 两侧都因未跟踪脚本读取假端点端口表的 python 片段
  缺 `import sys`（A2 基线日志 `minekin-v1201neg2/a2-matrix.log` 里有同样的 `NameError` 与空端口表）而没有真正测到目标场景，
  修它不在 N1 判据里所以 E 没顺手改，若要把 13 行矩阵的 A 族与 B12/B13 补回来请另卡；N2（`--max-bytes 0/-1` 得 `exit=70`）仍开着。
- **镜像曾被清空并已按仓库钉住的 Dockerfile 重建**：`docker system df` 一度 Images 0（24 个数据卷完好），
  `minekin-runner:local` 由 `test-orchestrator/runner/Dockerfile` 重建（image id `7730fc480365`，容器内 python 3.12.3）。
  重建后只读跑 B2 第一刀读数脚本，输出与 checkpoint `postmerge-core-readout.log` **逐字节相同**（`attempts 54 / bundles 90 /
  from_another_build 61 / unverified 0`，W60 `promotable true / blocks []`，`CORE-040 6/6`、`CORE-050 4/4`、`disagreements=[]`）。
- **撤回 E 早前一则"规范卷疑似丢数据"的警报——那是我自己的读数错误**：我只数了 `/data/kin/*/run/evidence`（85 个目录），
  而 `candidate_roots` 有四个证据根（`kin-01 82 + kin-02 2 + kin-auto-inst-20260925T141055Z 1 + repo-evidence 5 = 90`），
  与门禁读数一致；A1 的 sealed PASS 材料一直在独立卷 `minekin-v1201demo3`（`kin-demo-rhs3-20260926T052929Z`，store 3639 文件、
  manifest 重读 `V1201-040 / PASS`），A2 的 X/Y/B 原始材料在 `minekin-v1201neg10/11/2`，都还在。**没有发生删除，E 也没删任何材料。**
  顺带一处路径写法需要更正：attempt 登记库在**卷根** `/data/evidence-attempts.sqlite3`（16,384 字节），不在 `kin/kin-01/…` 之下；
  本文上一条主控边界段那句表述请按此读，E 不代改主控文本。
- **E 现在停等的东西**：B2 卡面要求的 `mandatory` 当前构建 bundle，今天所有门的阻因都是
  `REQUIRED_CASE_NOT_REGISTERED` / `NO_MANDATORY_CASES`（case 设计与门禁晋级 = 主控动作），E 再跑也不会点亮任何一门；
  §3.3 的排卡与 `BLOCKED_DECISION` 群（含 B12/B13 那类 runner 缺陷的处置）等主控决定。禁止连接用户远程服这条不变。

## E lane 交件：B2 第三刀（5 条 ADMIT 行的当前构建真跑封证）2026-09-26

- **交了什么**：上一条「E 现在停等的东西」里那 5 条 `only_another_build` 的
  `ADMIT-001/040/060/100/110`，已在 E 工作树 `48fe79e`（源码与主干 `ed37260` 逐字相同，纯文档提交）上
  各补一轮受控本地真跑并封证。记录：[五条 ADMIT 行的当前构建真跑封证](p0-admit-five-run-2026-09-26.md)。
- **读数**：五条各得一份 `PASS + verified + sealed + re_judged=AGREES + crit_match=True + violations=0` 的
  当前构建行（run `b8da082d / f3ce6fec / e7e6687d / b5d411db / 40790771`，attempt 序号 2/2/3/1/1），
  独立复判观测 `2/2、6/6、6/6、3/3、3/3` 且 `disagreements=[]`。规范卷底色
  `attempts 54→59 / bundles 90→95`，而 `from_another_build` **仍是 61** —— B1 分出的
  「本根只有别的构建的证据」那一格从 5 条变 0 条。
- **旋钮生效是量出来的，不是叙述的**：`ADMIT-040` 的 bundle 里 `server.properties` 写 `online-mode=true`
  而 profile 是 `auth_mode=offline`；`ADMIT-060` 写 `require-resource-pack=true` + loopback pack URL +
  `resource-pack-sha1`；`ADMIT-100` 的 run document 是 `snapshots_admitted=0 / connection_state=FAILED`；
  `ADMIT-110` 的 bundle 里没有 `server/` 目录（黑洞 run）。复现命令在记录 §1，含一条只 docker 的复核行。
- **和前两刀一样弱，请照弱读数使用**：这五条都是 `mandatory: false`，且它们同时列在 W40 与 `p0-core` 的
  `requirement.non_mandatory` 里。反证 R1 从镜像副本里撤掉这五份之后，`W40 / p0-core / W60 / overall` 四行
  与正对照 P **逐字相同**（两门仍 `REQUIRED_CASE_NOT_REGISTERED`、`satisfied: []`；W60 仍 `promotable true / blocks []`）。
  也就是说：**卡面上点名「只差运行」的三格至此清空，而门禁缺口一寸未移**——那仍是 case 设计与
  `P0-GATE-PROMOTION-001`（主控）。`tools/rejudge_evidence.py` 一位字节即 `rc=12 + ARTIFACT_DIGEST_MISMATCH`
  （R2），同一条在规范卷上仍 `rc=0`（R3）：这批 bundle 的可用性不是自证的。
- **E 接下来的停等边界（更新上一条）**：B2 剩余动作需要的是新场景与判据（卡面后半段 L3/L5/L6、崩溃恢复、
  重启协调、offline identity、soak；B1-b `P0-OFFLINE-090-100-EVIDENCE-CHECK-001` 仍 `QUEUED_PROPOSED`；
  §9.3 三类的 31 条 `absent` 行前置是产品决定），不是再跑同一批现成判据。**E 不自造断言、不改 `mandatory`、
  不动 registry。** 需要主控点的三件仍然开着：mandatory 登记/晋级、§3.3 排期、runner 脚本 `import sys` 缺陷
  （B12/B13 与 A 族 18 条探针）另卡处置。禁止连接用户远程服这条不变；规范卷 `minekin-runner-data` 仍只有 E 写，
  本轮对它的写入只有五次真跑的追加。

## E lane 交件：B2 第四刀（`CORE-030` 的 LAN 真跑封证）+ 两条 runner 缺陷报告 2026-09-26

- **交了什么**：B1 §6 那 10 条 `only_another_build` 里剩下的最后一条非 deferred 行 —— `CORE-030`，
  也是本 campaign **第一条 LAN 形状**的当前构建真跑。E 工作树 `c3998a3`（源码与主干 `ed37260` 逐字相同，
  纯文档提交）。记录：[CORE-030 的当前构建 LAN 真跑封证](p0-core030-lan-run-2026-09-26.md)。
  **至此 B1 §7 定义的 9 条最小内容全部有当前构建 sealed bundle**（`CORE-040/050` + `OFFLINE-030` +
  5 条 `ADMIT` + `CORE-030`）；那一格只剩 deferred 的 `HOST-030/040`，前置仍是 HOST ownership 决策。
- **读数**：加入者 bundle `19ff9064c72a411c925ae9043e155d49`（attempt seq 2，顶掉本轮 FAIL `8164024d`）
  `PASS + verified + sealed + re_judged=AGREES`，判据 `2/2`；宿主 `kin-01` run `dc105562…` 的
  `lan_publication {LAN_OPENED, 25570}` 与 `world_snapshot.settings_digest 3bdd4aff…`（逐字节等于
  `core-030.json` 钉住的 `level.dat`）。字节级到达证明在两端日志里都在（`Started serving on 25570` →
  `Kin2 joined the game`；`bridge asked vanilla to connect to 127.0.0.1:25570` → `CONNECTION_PHASE_JOIN_SEEN`），
  加入者终态 `PLAYABLE / snapshots_admitted 1 / entities_admitted 71 / PLAYER_EQUIVALENT`。
  底色 `attempts 59→61 / bundles 95→97`，`from_another_build` **仍是 61**。
- **和前几刀一样弱**：`CORE-030` 是 `mandatory: false`，列在 `overall` 与 `p0-core` 的
  `requirement.non_mandatory` 里。反证 P / R1（撤 PASS）/ R2（撤本轮两份 = 退回第三刀）三种卷状态给出
  **同一份门读数**（两门仍 `REQUIRED_CASE_NOT_REGISTERED`、`satisfied: []`，W60 仍 `promotable true`）。
  R3/R4 另量到一个机制值得主控知道：**移走 `level.dat` 的 pin 之后，复判读者对 PASS 与 FAIL 都只给
  `unjudged rc=2`**，也就是「判据摘要对不上」优先于判决，具名否只能从未移的判据读（本轮 FAIL 的两条
  `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT` 就是这样从 §3 第 4 读出来的）。
- **缺陷报告 1（确定性，建议另卡）—— `test-orchestrator/runner/domain.sh:657`**：
  joiner 分支在 `set -euo pipefail` 下做 `before=$(ls "/data/kin/${joiner}/run/session/" 2>/dev/null | sort)`。
  一个刚 `session init` 出来、从未起过会话的 joiner Kin **没有** `run/session/` 目录 ⇒ `ls` 退出码 2 终止整个 run，
  且 stderr 被 `2>/dev/null` 吞掉。第一次真跑只留下三行日志和 `rc=2`，没有任何一行说明是目录不存在。
  E 的处置：操作员先 `mkdir -p /data/kin/kin-04/run/session` 作为准备，**没有 patch 已提交代码**
  （runner 不在 B2 的 `allowed_paths`，与上一条已披露的 `import sys` 缺陷同一处置）。
  修法是加 `|| true`/先建目录，属一行改动，但需要主控定点：这条会影响任何「全新 Kin 做加入者」的 LAN 卡。
- **缺陷报告 2（不可重现，请决定是否开诊断卡）—— 加入者客户端 GLFW 崩溃**：第二次真跑的加入者崩在
  `RenderSystem.initBackendSystem` → `GLX._initGlfw`，`GLFW error during init: [0x1000E]Failed to detect any supported platform`，
  crash report 已随 FAIL bundle 封进卷（`client/crash-reports/crash-2026-09-26_12.24.07-client.txt`，7196 字节）。
  E 量到的边界（记录 §5，四条都在）：崩溃那次与成功那次的 bundle `environment` 块**逐字相同**
  （`llvmpipe (LLVM 20.1.2, 256 bits)` / 同一 Temurin 21.0.12.1 / 同一内核）；`/proc/<pid>/environ` 探针证明
  正在拨号的被管客户端确实拿到 `DISPLAY=:99` + `XAUTHORITY=/tmp/xvfb-run.<rand>/Xauthority`（同窗口对照行里
  Core 自己是 `:100` 加它那一轮的 cookie，即二者都经 `config.FORWARDED_VARIABLES` 转发）；A–G 矩阵把四条能拒止的 X 路径各自命名
  （抽 cookie ⇒ `Authorization required, but no authorization protocol specified`；
  `-nolisten tcp` ⇒ `Error: unable to open display 127.0.0.1:99`；`TMPDIR`/`HOME` 进会话叠加不影响；
  `unix:99` 可通），而崩溃那次属于「全部允许」那一格；**第三次一字未改重跑即 PASS**。
  ⇒ E 不写根因，也不声称它不会再现。
- **E 接下来的停等边界（更新上一条）**：B2 卡面点名「只差运行」的部分至此清空，剩余都需要新的东西而不是
  重跑：卡面后半段 L3/L5/L6、崩溃恢复、重启协调、offline identity、soak 需要新场景与判据，
  B1-b 仍 `QUEUED_PROPOSED`，`HOST-030/040` 与 §9.3 那 31 条 `absent` 行前置是主控决定。
  **E 不自造断言、不改 `mandatory`、不动 registry、不 patch 已提交的 runner/产品代码。**
  待主控点的仍是那三件 + 新加两件：mandatory 登记/晋级、§3.3 排期、`import sys` 缺陷、`domain.sh:657`、
  GLFW `[0x1000E]` 是否值得诊断卡。禁止连接用户远程服这条不变；规范卷 `minekin-runner-data` 仍只有 E 写，
  本轮对它的写入只有两次真跑的追加（其余全程 `:ro`）。

## E lane 交件：B2 第五刀（4 条「判官只需仓库字节」行的当前构建封证）+ 两格交主控的事实 2026-09-26

- **交了什么**：B1 §6 三格按判据形状切出的第三种形状 —— 「判官只需仓库字节但本根零 bundle 17 条」里
  **非 HOST 的 4 条**（`OFFLINE-001`、`OFFLINE-040`、`OFFLINE-050`、`ADMIT-080`），各封一份当前构建的
  PASS bundle。**该格由此从 17 条变成 13 条，而剩下的 13 条全部属 `HOST*` 家族**
  （`HOST-010/020/050/060/070/080`、`HOSTCOMMIT-090/110`、`HOSTCTL-001/010/050/060/070`）。E 工作树
  `2a83109`（第四刀的记录提交）之上的同一份主干源码，纯文档提交。
  记录：[四条仓库自检行的当前构建封证](p0-repo-four-case-run-2026-09-26.md)。
- **这一刀的形状与前四刀不同，值得主控知道**：它**不是** Minecraft 真跑，而是既有的**仓库自检通道**
  （`tools/run_repo_case.py` 跑 case 声明的 pytest 判据 ⇒ `tools/seal_repo_case.py --data-root /data` 封到
  `repo-evidence/<run-id>/`）。这条通道 09-25 已在卷上留下三份（`f2335016 / e2393e92 / 157eccd2`），本轮是
  按同一条通道重复它，未新增判据、未新增 case id。四份 attempt 各 seq 1、检查 `5/3/3/6` 条全 held、
  工件 9/7/7/10 件、`launch_plan_digest bcc0c10d…`（与前四刀同一份当前仓库构建）。
- **读数（四读，含该通道自己的口径）**：封存自报 `sealed / PASS / failures []`；只读挂载上
  `python -m minekin_core evidence verify` 四条 `rc=0`；`report_promotion.py --data-root /data` 每行
  `from_repository_build: true / verified: true / sealed: true / violations: []`；**`rejudge_evidence.py`
  报 `UNJUDGED` + `rc=2`**，理由是 bundle 不记 asserter 输入（`asserter-inputs.json`）——这是仓库自检类
  bundle 的既有口径，所以这条通道的**第二次读法是重跑检查**，本轮四条各有全新 run id 的独立重跑并同意
  （`c844cffa / 5826ff69 / 25696021 / e115a539`）。**E 不声称 `re_judged = AGREES`**，请按此强度使用。
  底色 `attempts 61→65 / bundles 97→101`，`from_another_build` **仍是 61**。
- **门一寸未动，而且是量出来的**：把 `report_promotion.py` 的 `work_packages`+`overall` 整段按 sort_keys
  序列化取 sha256，封前（97 份 bundle）与封后（101 份）**同一个值** `fb0152c85d029ee0…`；四条都是
  `mandatory: false` 且都在所属门的 `requirement.non_mandatory` 名单里。反证七件 P/R-A/R-B/R-C/R-D/R-E/R-F：
  一位字节的两种工件（检查输出、判决工件）都给 `rc=12` + `ARTIFACT_DIGEST_MISMATCH` 且**还原即回 `rc=0`**；
  R-D 在产品代码副本上改一字节（token 入参、`STALE_GENERATION` 处置、`uuid` 规范化）使四案各自的判据转红
  （`3/5`、`2/3`、`4/6`，`OFFLINE-040` 需自己那一刀才 `2/3`），并如实封成**卷外** FAIL；R-E 删 bundle 目录
  ⇒ `bundles 9→5` 而 `attempts` 仍 65。规范卷全程 `:ro`，唯一写入是那四次封存追加。
- **交主控的事实 1（基础设施，E 不自作处置）——受控镜像里执行不了仓库自检类检查**：
  `minekin-runner:local` 内 `find_spec("pytest")` → `None`，`/opt/minekin/lib/python3.12/site-packages` 只有
  `google / pip / pip-24.0.dist-info / protobuf-6.33.6.dist-info`（`test-orchestrator/runner/Dockerfile` 里只
  `pip install "protobuf==6.33.6"`）。在镜像里跑 `run_repo_case.py` ⇒ `rc=1`、`result FAIL`、五条 detail 全是
  `No module named pytest`，即**一份由环境造成的假 FAIL**。E 没有临时 `pip install`（会把未钉住的代码放进封证
  链路）、没有改镜像（`test-orchestrator/` 不在本卡允许路径，且这是基础设施不是证据）、也没有把那份假 FAIL 封进卷，
  走的是 09-25 已在卷上留下三份的同一条通道（检查在宿主、封存受控容器）。**请定口径**：给受控镜像加一份钉住的
  测试工具链（另卡），还是明确「仓库自检类 bundle 的 `environment` 段按封存进程记」为本项目正式口径。
- **交主控的事实 2（判读侧，是否开卡由主控判）——「台账有行、卷上无 bundle」被静默忽略**：在副本里删掉本轮四个
  run 目录后，`report_promotion.py` 仍报 `attempts 65`、`unsealed 0`、`unreadable 0`，只有 `bundles 9→5`；
  而反方向的半套卷（有 bundle 无台账）09-25 量过是 `unusable / exit 2`。也就是说**半套卷的拒绝只朝一个方向生效**，
  一条 `SEALED` 台账行指向不存在的目录时没有任何读者会抱怨。E 不动工具代码。
- **E 接下来的停等边界（更新上一条）**：B1 §6 三格里的**全部非 deferred 形状**至此清空（1 条 → 第二刀、
  10 条 → 第三、四刀、17 条 → 第五刀后剩 13 条全 HOST）。剩余动作没有一件是 E 单方能做的：卡面后半段
  L3/L5/L6 / 崩溃恢复 / 重启协调 / offline identity / soak 要新场景与新判据；B1-b 仍 `QUEUED_PROPOSED`；
  HOST 那 13 + 2 条的前置是 ownership 决策。**E 不自造断言、不改 `mandatory`、不动 registry、不 patch
  已提交的 runner/产品代码、不封 HOST 族。** 待主控点的仍是那五件 + 新加两件：mandatory 登记/晋级、§3.3 排期、
  `import sys` 缺陷、`domain.sh:657`、GLFW `[0x1000E]` 是否开诊断卡、受控镜像是否携带钉住的测试工具链、
  「`SEALED` 行无 bundle」的静默是否开卡。禁止连接用户远程服这条不变；`minekin-runner-data` 仍只有 E 写。
- **给 M 的整合形状（量出来的，2026-09-26 `13:50` UTC 前后，lane `470b032`）**：`git merge-base --is-ancestor
  ed37260 HEAD` 成立 ⇒ 主干就是 E 分支的祖先，合并是 **fast-forward**、`git merge-tree --write-tree origin/main HEAD`
  的 rc=0 且不报任何冲突；`git log origin/main..HEAD` 是 5 条提交（`48fe79e` N1 收口读数、`c3998a3` 第三刀、
  `2a83109` 第四刀、`a5f3ec8` 第五刀、`470b032` 第五刀的判据归属更正），`git diff --stat origin/main...HEAD`
  是 **8 个 `docs/` 文件、974 行增、7 行删**，`src/ tools/ tests/ test-orchestrator/ schemas/ bridge/` 零改动。
  基础门在同一棵树上重跑：`ruff check` / `ruff format --check`（339 files）/ `pyright` 0 errors /
  `pytest` 2509 passed 2 skipped / boundaries / 140 registered assertions / fixture digests / workflow pins 全绿。
  这条只描述 M 合并时预期看到什么，不构成任何合并时机的请求；E 之后若再提交，仍然只动 `docs/`。

## M 主控轮次（2026-09-26）：E 分支合入、七项阻断分类、第一张完整性卡

四态口径逐条给：**已合入 main / 仅在分支 / 真实封证 / 尚未验证**。本轮不产生新的真跑封证（规范卷全程 `:ro`），也不点亮任何门。

- **已合入 main**：E 的 `codex/minekin-evidence` 整条（`48fe79e → c3998a3 → 2a83109 → a5f3ec8 → 470b032 → f632665`）以 fast-forward 合入并推送；`git ls-remote` 实测 `refs/heads/main = f632665029469fd7de51b949578dacaa5cad7925`。M 独立复核过 E 的声称，不是照抄记录：卷上 `attempts 65 / bundles 101 / from_another_build 61 / unverified 0`；门载荷 sha256 重算 = `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`（与第五刀 §3 逐字相同）；11 门 `promotable` 分布 `W00/W10/W20/W60 true`、其余 `false`、overall `false / REQUIRED_CASE_NOT_REGISTERED / blocking_cases 31` ⇒ **四条 `PASS` 没有变成任何晋级**；五条 repo/真跑 bundle 的 `launch_plan_digest` 与本轮重建的 tree 计划摘要 `bcc0c10d46ab5c0b46d0c86f7e0de9d0d57b635bc17f9dcffdf7631eba8125e2` 相同；一～四刀的 run 复判仍 `AGREES`，失败 attempt（`CORE-050 eb7f9086`、`CORE-030 8164024d`、`ADMIT-060 3c17aa78`、`ADMIT-110 c383d4f1`）原样在卷。**四条 repo bundle 的 `re_judged` 是 `UNJUDGED`**（该通道没有 asserter-inputs 工件），其第二读法是重跑检查，这条区分照记录使用。
- **已合入 main（第二笔）**：`INT-EVIDENCE-INTEGRITY-001` 从 `codex/minekin-evidence-integrity` @ `../minekin-wt-integrity`（base `f632665`）以 fast-forward 单独合入并推送；提交 `759125f0a97a0f201c18f08363832f9e89c1c2e8`，`git ls-remote` 实测 `refs/heads/main` 与 `refs/heads/codex/minekin-evidence-integrity` 同为该 SHA。改动面逐字核对过：`tools/report_promotion.py`（+35，台账→bundle 方向的具名与 docstring）、`tests/unit/test_report_promotion.py`（三条新案）、三份 M 拥有的主干文档 ⇒ **无产品代码、无 case 判据、无 registry 字节、无重封**。合入前门禁：`46 passed`（该文件）、文档里那条 `-k` 复现命令复跑 = `4 passed, 42 deselected`、全量 `2511 passed, 3 skipped`、pyright `0 errors`、ruff/format/boundaries/case-assertions/fixture-digests/workflow-pins 全绿；合入后规范卷只读读数与 E 分支合入前逐字相同（`attempts 65 / bundles 101 / unverified 0 / sealed_without_bundle []`，`rc=1`，overall `false / REQUIRED_CASE_NOT_REGISTERED`）。
- **仅在分支**（本轮派出、尚未 push 到可审形状）：`H1a` @ `../minekin-wt-harness`（`codex/minekin-harness`）、`H1b` @ `../minekin-wt-runner`（`codex/minekin-runner-named-failure`）、`S2` @ `../minekin-wt-auto-entry`（`codex/minekin-auto-entry`），base 均为当时的 `main = f632665`；各自动工后主干已推进，M 合下一张前先 `git fetch` 以远端 `main` 为新 base，分支未合并一律不写成主干 `DONE`。
- **七项阻断分类**（① 完整性静默＝工程，本轮做；② 镜像缺钉住 pytest＝基础设施，排 `H1a`；③ `domain.sh:657` 静默 `rc=2`、④ runner 未 `import sys`＝工程，合并成 `H1b` 两提交；⑤ GLFW `[0x1000E]` 不可重现＝观察项，不再量到才开诊断卡；⑥ `REQUIRED_CASE_NOT_REGISTERED`/`NO_MANDATORY_CASES` 与 `mandatory` 晋级＝主控保留的门禁决定，本轮不动 registry；⑦ HOST 13+2 条＝§5 所有权未冻结，维持 `DEFERRED`）。同时把第五刀 §5 请 M 定的那一格定成**两条都要**：镜像补工具链（②），已封 repo bundle 的 `environment` 段按封存进程解释（②-b），不重封。
- **下一步（不需要用户拍板的安全工作）**：`H1a` 与 `H1b` 在 `test-orchestrator/**`（H 独占面，冲突表已登记，H 未同时施工由 M 代打）、S2 `V1201-MAX-BYTES-VALIDATION-001` 留在 S lane、`E-CO` 镜像内自检重封一轮排 `QUEUED` 等 `H1a`。
- **仍然阻着的**（不自答）：HOST §5 三格所有权、PERSIST case 冻结、V08 远程服连接、V09 动作授权、在线认证、数据删除/进程接管。**本轮没有连接、也没有探测用户的远程服务器**；规范卷只有 E 写，M 只读。
- **不声称** Minekin 已完成、不声称任何 gate 已点亮、不声称 ②③④ 已修（只登记了卡与验收）。

## M 主控第二轮（2026-09-26）：三张 lane 工程卡逐张合入、④ 的更正、两张新派工

四态口径逐条给：**已合入 main / 仅在分支 / 真实封证 / 尚未验证**。本轮**没有产生任何新的真跑封证**（规范卷全程 `:ro`），也**不点亮任何门**；`mandatory`、registry `status/gaps`、case 判据一字未动。

- **已合入 main（按依赖顺序单张）**：主干 `caee32c → d09e9b2 → ee0a439 → ea5423e`，每笔合入后立刻 `git push origin HEAD:main` 并以 `git ls-remote origin refs/heads/main` 核远端 SHA；当前远端 `refs/heads/main = ea5423e9711f944d27b4bdd9257d28c7da35d67e`。
  - `d09e9b2e0d5ad7953be749fa7a2e8f75a7874ddb` = **H1b `RUNNER-NAMED-FAILURE-001`**（七项分类的 ③），lane 提交 `1dc6101`，parents `caee32c` + `1dc6101`。改面只有 `test-orchestrator/runner/domain.sh`：加入者会话基线的读取从 `before=$(ls … 2>/dev/null | sort)` 这种会被 `pipefail` 静默掐死的形式，换成双向具名形状（目录存在却列不出 ⇒ 打印具名理由并 `exit 2`；目录不存在 ⇒ 明说「还没有 session 目录，加入基线为空」并继续）。M 侧验收读数：在全新加入者 Kin 上，原形状给 `rc=2` 且无一行解释，新形状两种情形各给一行具名读数。
  - `ee0a439d594710d170314845b261afe3024c75c6` = **H1a `TEST-ORCHESTRATOR-PINNED-PYTEST-001`**（②），lane 提交 `44922b8`，parents `d09e9b2` + `44922b8`。改面 `test-orchestrator/runner/Dockerfile`（`/opt/minekin/bin/pip install` 一层，钉 `pytest==9.1.1` 与其非 Windows 依赖闭包 `iniconfig==2.3.0 / packaging==26.3 / pluggy==1.6.0 / pygments==2.21.0`）+ `tests/contract/test_runner_scripts.py`（+65：一条漂移守卫，要求镜像 pip 的每个包都写成 `name==version` 且逐条等于 `uv.lock`）。**M 亲测的红绿**：旧镜像里 `import pytest` ⇒ `ModuleNotFoundError`，`tools/run_repo_case.py --case tests/fixtures/cases/offline-001.json` ⇒ `rc=1` 且五条详情全为 `No module named pytest`（正是第五刀 §5 记的那条假 FAIL）；重建后的镜像 `pytest 9.1.1` on Python 3.12.3，同一条命令 `rc=0` 且 `5/5` held。**漂移守卫的两处反证（合并说明里承诺记在这里）**：把 pip 参数改成浮动 `pytest` ⇒ 在 `test_runner_scripts.py:450` 具名失败；把 `9.1.1` 改成 `9.0.0`（与锁文件不同）⇒ 在 `:458` 具名失败；两次反证跑完都还原，合入树里是原始钉住。**副作用登记**：`minekin-runner:local` 已按新 Dockerfile 重建，旧镜像保留为 `minekin-runner-before:local` 标签作为修复前参照；已封的四条 repo bundle **不重封**（②-b 口径：其 `environment` 段按封存进程解释）。
  - `ea5423e9711f944d27b4bdd9257d28c7da35d67e` = **S2 `V1201-MAX-BYTES-VALIDATION-001`**（§3.2 N2），lane 提交 `20e2e60`，parents `ee0a439` + `20e2e60`。改面 `src/minekin_core/cli/auto_session.py`（新 `require_spendable_budget`，作为 `prepare_auto_bundle_start` 的第一条语句）、`src/minekin_core/bootstrap.py`（`bundle install` 入口同规则；`session start` 分支在 `--max-bytes` 与 `--profile` 同给时具名 usage 退出）+ 相应测试。**M 在受控镜像的合并树上亲量四格**（`/src:ro` + 卷外 `/tmp` store，registry/profile 路径一律不存在）：`bundle install --max-bytes 0` ⇒ `rc=10` + `[BUDGET_NOT_POSITIVE]` 且 `operation: "bundle install"`；同命令 `--max-bytes 5` ⇒ 走到 `SUPPLY_CHAIN` 读档失败（`rc=11`），证明正预算被接受；`session start --profile … --max-bytes 5` ⇒ `rc=2` + `MAX_BYTES_WITHOUT_AUTO_BUNDLE`；`--profile` 独用 ⇒ 越过预算检查落到既有的 `no Kin exists`（`rc=10`），即新拒答不是无条件开火。
- **合入树门禁（逐笔跑，不接受 lane 自报）**：`d09e9b2` / `ee0a439` / `ea5423e` 三棵树的全量 `uv run --frozen pytest -q` 依次 `2511 passed, 3 skipped`、`2512 passed, 3 skipped`、`2518 passed, 3 skipped`；每笔另跑 ruff check、`ruff format --check`（339 文件）、pyright `0 errors`、`check_boundaries.py`、`check_case_assertions.py`（140 条已注册）、`verify_fixture_digests.py`、`check_workflow_pins.py`、`git diff --check`，全绿。**逐卡双审都核过允许路径**：H1b/H1a 只在 `test-orchestrator/**` 与其契约测试，S2 在 CLI 校验面与协议 §2 已授予的「必要 `bootstrap.py`」内；三笔都不含产品判据、registry 字节或重封。
- **④ 更正：仓库代码未复现**。上一轮把「runner 使用 `sys` 而未 `import sys`」当作已定位缺陷并入 `H1b`，该说法的来源是一个未跟踪的 `.tmp/` 探针，不是仓库字节。M 侧全仓扫描：246 个被跟踪的 `.py` 里 `sys.` 的字面命中只有两处，都在 `tests/contract/test_runner_scripts.py:329,333` 的**字符串字面量**内（它们正是那条断言的证据文本）；`test-orchestrator/` 下没有任何 `.py`；`domain.sh` 用到 `sys` 的五处（`265,269,317,321,390`）都是 `import json,sys` 齐全的 Python 片段。因此 ④ 按「未复现」关闭，`H1b` 实际只交付 ③ 一个提交（lane 报告里的「两提交」口径同样作废并在此更正）。**教训留在流程里**：lane 报告的缺陷事实必须由 M 复扫仓库字节后才写进卡。
- **仅在分支、尚未验证（本轮派工，进行中）**：① `E-CO` 镜像内自检重封一轮 —— E lane，`codex/minekin-evidence` @ `../minekin-wt-evidence`，base 为三张工程卡合入后的远端 `main`；在同一个重建镜像里跑「判官只需仓库字节」那一族，使 `environment` 段与检查执行环境一致；**写规范卷（E 独占）、只推自己分支、不重封已封四条、不翻 registry、不声称晋级**。② `V1201-AUTO-PATH-RUNNER-001`（H lane 的 `lane_next`）—— `codex/minekin-auto-path-runner` @ `../minekin-wt-runner`；G1（`domain.sh` 捕获 `--auto-bundle` 并按 `seal_run_evidence.py` 的必填项传参）+ G2（受控 launcher 给出可复核的 `enable-status` 与服务端 `Pos/Rotation` 探针）；只动 `test-orchestrator/**` 与其契约测试，且**禁止指名挂载规范卷 `minekin-runner-data`**（此刻归 `E-CO`，`seal_run_evidence.py` 独占窗口按协议先协调）。两者 push 后由 M 逐卡双审、单张合入并再核远端 SHA；**branch 上有实现不等于主干 `DONE`**。
- **待读的既成事实（不抢占）**：③ 修好后，第四刀那条被静默 `rc=2` 掐死的 `CORE-030` 尝试可以重跑，但它要占规范卷与封存窗口，按协议先与 E 协调，不与 `E-CO` 同时开工。
- **真实封证（卷上可见，E 的记录尚未 push ⇒ 文档侧仍是「仅在分支」）**：M 在 15:45–15:52 UTC 只读快照到 `E-CO` 已经封出四条新的仓库自检 bundle（`OFFLINE-001/040/050` + `ADMIT-080`，`46f88ff6 / e9ee19ab / 8af1ad70 / 8ffed6f1`，各 `sequence 2` 顶掉第五刀那四条，旧 attempt 原样保留）。**卡面要的口径改进是真的，而且落在字节而不是 `environment` 字段上**：seq 1 的 `check-verdict.json` 记录 argv0 = 宿主 `…\.venv\Scripts\python.exe`，seq 2 记录 argv0 = `/opt/minekin/bin/python3`，检查日志里的 pytest 来自 `/opt/minekin/lib/python3.12/site-packages/_pytest/`；同一份日志留着 `PytestCacheWarning: … Read-only file system: '/src/.pytest_cache'` ⇒ 挂载确实只读（非恒真对照）。M 独立复量：四条 `evidence verify` 各 `verify_rc=0`、`sealed true / verified true / violations []`、工件 9/7/7/10；抽两条 `rejudge` 仍报既有的 `unreadable`（该通道无 `asserter-inputs.json`，第二读法是重跑检查）。卷底色 `attempts 65→69 / bundles 101→105 / from_another_build 61→61 / unsealed 0 / unverified 0 / sealed_without_bundle []`；**门载荷 sha256 仍是 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`，11 门 `promotable` 分布一字未变**（`W00/W10/W20/W60 true`，其余 `false`；overall `false / REQUIRED_CASE_NOT_REGISTERED`）。同时量到三张工程卡的合入**没有移动构建身份**：`repository_build` 仍是 1.20.1 `83299ad5…` / 1.21.4 `bcc0c10d…`，所以 S2 的产品改动没有把已引用 run 变成「别的构建」（`from_another_build` 61 条一字未动）。两条 `environment` 段的键值（`renderer_display: unmeasured` 等）新旧逐字相同 ⇒ 若 E 的记录声称改的是 `environment` 段本身，与卷上字节不符；M 会在双审时按这条判。
- **lane_next 现状**：主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`；E → `E-CO`（在分支）+ B2；H → `V1201-AUTO-PATH-RUNNER-001`（在分支）；S → **暂无安全的 S 卡**（§3.2 剩下的 N3/N4 都是 `BLOCKED_DECISION`，要冻结的是产品语义而不是代码，不由 lane 自造，也不占 `lane_next`）；D/V 仍停等其前置。冲突表见[并行作业协议](parallel-execution-plan.md)。
- **仍然阻着的**（不自答）：HOST §5 三格所有权、PERSIST case 冻结、V08 远程服连接、V09 动作授权、在线认证、数据删除/进程接管，以及 `P0-GATE-PROMOTION-001` 的门禁晋级、B1-b 的排期、`ADMIT-030/050` 的 case id 拆分、N3/N4。**本轮没有连接、也没有探测用户的远程服务器**；规范卷只有 E 写，M 只读。
- **不声称** Minekin 已完成、不声称任何 gate 点亮、不声称 ②③ 的修复制造了新的运行时证据（它们只把判官与镜像补到能给出**具名**读数的程度），也不声称 `E-CO`/G1-G2 已验证。

## M 主控第三轮（2026-09-26）：`E-CO` 记录收卡、M 的 provenance 读者卡、H 的 G1/G2 双审合入、两张新派工

四态口径逐条给：**已合入 main / 仅在分支 / 真实封证 / 尚未验证**。本轮 M **没有写规范卷**（全程 `:ro`），因此**没有 M 侧新的真跑封证**，也**不点亮任何门**；`mandatory`、registry `status/gaps`、case 判据一字未动。

- **已合入 main（按依赖顺序单张，每笔合完立刻 push 并用 `git ls-remote` 核远端）**：主干 `b40376d → 6cc9c45 → 0ab208c → be4e79b`；当前远端 `refs/heads/main = be4e79b98baafea85f1230de587fc5b7b8b15a89`。三条 lane 分支 SHA 同步核过：`codex/minekin-evidence = 626a454`、`codex/minekin-repo-check-provenance = 318a44c`、`codex/minekin-auto-path-runner = f3b6001`。
  - `6cc9c457c507090993762d0e2a522b645b53e818` = **`E-CO` 镜像内自检重封一轮的收卡记录**（lane 提交 `626a454`，parents `b40376d` + `626a454`）。改面只有 `docs/p0-repo-internal-image-reseal-2026-09-26.md`（+137，**docs-only**）——真跑材料在上一轮就已写在卷上，本轮合的是描述那份材料的主干文档 ⇒ 那四条 seq 2 当前构建封证自此是**主干可引用**的证据。M 的双审按上一轮 217 行预埋的那条判据走：记录没有声称改了 `environment` 段本身，其 §6 逐字节量出**新旧四个 bundle 的 `environment` 段相同**（`environment_equal: True` ×4）并给出原因（`environment.host_facts()` 记的是封存进程，而封存进程本来已在同一容器里），把「两边自洽」落在 `check-verdict.json` 的 argv0 与检查日志的 pytest 路径上。这与卷上字节一致 ⇒ 该格按如实记录收卡，不按夸大处理。四条 `re_judged` 仍是既有的 `UNJUDGED`（该通道无 `asserter-inputs.json`，第二读法是重跑检查，记录 §5 已按此写）。
  - `0ab208c9549bd9653d4456d868a9dfd219e4759d` = **`INT-REPO-CHECK-TOOLCHAIN-PROVENANCE-001`**（M 自己的读者面卡，②/`E-CO` 的可见性续卡；lane 提交 `318a44c`，base `b40376d`，parents `6cc9c45` + `318a44c`）。改面逐字核对过，只有允许路径两处：`tools/report_promotion.py`（+117）与 `tests/unit/test_report_promotion.py`（+177，八条新案）⇒ **无产品代码、无 case 判据、无 registry 字节、无重封、无卷写**。最小反例先量红：卷上 13 份仓库自检 bundle 里 9 份的判据记着宿主 `…\.venv\Scripts\python.exe`（`157eccd2 / 4f324c20 / 5d12b151 / 66c51fc7 / 7aa541e5 / 935c034a / e2393e92 / f2335016 / f4203033`），而修前报告**没有任何字段**能把它与 `E-CO` 那四条分开。实现时量到一个设计坑并当场改掉：第一版按「读报告的进程用自己的解释器」比较，容器内点名 **13/13** 恒红——镜像里 `sys.executable` 是 venv 别名 `/opt/minekin/bin/python`，封存记录写的是 `/opt/minekin/bin/python3`（同一 venv 的两种拼写，realpath 都是 `/usr/bin/python3.12`）；改成与 runner 镜像契约钉住的常量，并加两条测试钉住这件事（一条从 `test-orchestrator/runner/Dockerfile` 读 `python3 -m venv /opt/minekin` 防漂移，一条显式要求别名拼写**也被点名**）。M 侧读数：`uv run --frozen pytest tests/unit/test_report_promotion.py -q` ⇒ `54 passed`，全量 ⇒ `2526 passed, 3 skipped`，ruff check / `ruff format --check`（339 文件）/ pyright `0 errors`（实现过程中 pyright 先在 `tools/report_promotion.py:302,308` 报两个 unknown-type，用 `cast("list[object]", …)` 收掉才绿）/ 四项 tools 边界脚本 / `git diff --check` 全绿；合入后规范卷只读复跑名单恰是那 9 份、四条 seq 2 各记 `['/opt/minekin/bin/python3']` 且不入围，`attempts 69 / bundles 105 / from_another_build 61 / sealed_without_bundle []`、`status blocked`、`rc=1`、门载荷 sha256 仍是 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da` ⇒ **与合入前逐字相同，新字段只命名不门禁**（与 ① 同一口径）。会话型 bundle 没有 `check-verdict.json` ⇒ 记录为空、永不入围（「没说」不等于「说在别处」）。
  - `be4e79b98baafea85f1230de587fc5b7b8b15a89` = **`V1201-AUTO-PATH-RUNNER-001`（H 的 G1/G2）**（lane 提交链 `efb8630 → f8a1d9a → f3b6001`，真实 `merge-base` 与主干核为 `ea5423e`，与 lane 自报 base 一致；parents `0ab208c` + `f3b6001`）。改面四文件、`+430 / -20`：`test-orchestrator/runner/domain.sh`（+173）、`tests/contract/test_runner_scripts.py`（+90）、`test-orchestrator/runner/README.md`（+43）、`docs/validation/v1201-auto-path-runner-2026-09-27.md`（+144，H 自己的记录）⇒ **全在 H 的独占面内，不触产品 `src/**`、不改判据/registry、不重封历史 bundle**；`tools/seal_run_evidence.py` 按协议只当只读接口，未改。**M 独立双审（不照抄 lane 自报）**：`git merge-tree` 预测与真实合并都无冲突；两条新契约测试在缺陷副本上 `2 failed`、在分支上 `19 passed`；lane 工作树的 ruff/format/pyright/boundaries/case-assertions/`git diff --check` 逐条 `rc=0`；合入树全量 `2528 passed, 3 skipped`，ruff/format（341 文件）、pyright `0 errors`、四项 tools、`bash -n domain.sh` 全绿。**M 未复量、照实登记的 lane 自报部分**：其容器/真 JVM 红绿读数、那轮 `2520 passed` 的全量、以及端到端 `--auto-bundle` 真跑封证——M 在合入树上量到的是 `2528 passed, 3 skipped`，而 G1/G2 至今**只有代码 + 契约测试层面的证据**，真跑层证据正是本轮派 `E-RR` 的原因。两条审查侧观察登记给 H2：(a) 不带 `--server-profile` 的 auto run 仍会以空 `launched_version` 落到产品自己的拒答（`src/minekin_core/bootstrap.py`），runner 侧未具名；(b) 黑洞 run 按设计跳过 `enable-status` 早停。H-3/H-4 属产品下载器（`src/**`），超出 H 独占面，仍由 M 另立卡。**③ 的非回归复量（合入后，主干 `f6e6f45`）**：H 那 +173 行重写把加入基线区段搬到 `domain.sh:756-767`，M 在受控镜像里抽出这十二行在新 `bash` 进程（`set -euo pipefail`、`/data/kin` 换成容器 `/tmp` 私有根）量四格——全新 Kin `rc=0` + `before=[]` + 132 字节具名「还没有 session 目录」；不可列的既有目录（以 `nobody` 读 `chmod 000`）`rc=2` + 212 字节且 `ls` 的 `Permission denied` 与具名理由并存；正对照 `rc=0` + `before=[1111…]`；旧形状 `ls … 2>/dev/null | sort` 同根重放仍是 `rc=2` + stderr **0 字节** ⇒ 双向具名形状没被 lane 的重写带回。复现脚本 `.tmp/m-baseline-trunk.sh`（未跟踪，随容器销毁；容器内 `bash /src/.tmp/m-baseline-trunk.sh`，`/src` 只读、不挂载任何卷）。
- **真实封证（本轮无新增）**：M 全程只读挂载读规范卷；卷上可读的最新封证仍是 `E-CO` 的四条 seq 2（上一轮 217 行已量），本轮因记录合入而获得主干引用位置。合入前后与 `E-CO` 时点逐字相同的四项底数：`attempts 69 / bundles 105 / from_another_build 61 / sealed_without_bundle []`，构建身份仍是 1.20.1 `83299ad5…` / 1.21.4 `bcc0c10d…` ⇒ **runner 侧 +173 行的改动没有把任何已引用 run 重新归类成「别的构建」**。
- **仅在分支、尚未验证（本轮派工，进行中）**：① `E-RR` —— E lane，`codex/minekin-evidence` @ `../minekin-wt-evidence`，base 为 `main = be4e79b`：先复现第四刀那次静默 `rc=2` 的形状（全新加入者 Kin、`run/session/` 不存在）确认现行 runner 给具名读数，再按第四刀形状做一次当前构建 LAN 真跑并封进规范卷（`sequence +1` 的新 attempt，**不覆盖既成 seq 1/2、不改判据、不翻 registry**），交四读 + 一条正对照 + 一条反证；拿不到 PASS 就停在具名前沿、按 `BLOCKED_HARNESS` 上报并保留全部失败材料。② `V1201-CONTROLLED-SERVER-STATUS-KNOB-001`（H2）—— 新支 `codex/minekin-controlled-server-status` @ `../minekin-wt-status`，base `be4e79b`：G1/G2 记录点名的遗留①，`tools/run_controlled_server.py:247` 仍无条件写 `enable-status=false` 且无回读；本卡把取舍做成显式可命名旋钮，**默认仍是 `false`**（谁翻默认谁红——这就是非空转保证），opt-in 后要打印并回读真正写进 `server.properties` 的值，且在写入前按既有地址规则具名拒绝不安全请求；只动 `tools/run_controlled_server.py` 与其测试，**禁止挂载规范卷**（此刻归 `E-RR`），不改 `domain.sh`/判据/registry/门。两张 push 后由 M 逐卡双审、单张合入并再核远端 SHA；**branch 上有实现不等于主干 `DONE`**。
- **lane_next 现状**：主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（本轮它本身没有被"完成"：只要还有 lane 在工，它就常驻）；E → B2 未完 + `E-RR`（在分支）；H → H2（在分支）；S → **暂无安全的 S 卡**（N3/N4 属 `BLOCKED_DECISION`）；D/V 仍停等其前置。冲突表与 lane 面归属见[并行作业协议](parallel-execution-plan.md) §2。
- **仍然阻着的**（不自答）：HOST §5 三格所有权、PERSIST case 冻结、V08 远程服连接、V09 动作授权、在线认证、数据删除/进程接管，以及 `P0-GATE-PROMOTION-001` 的门禁晋级、B1-b（`P0-OFFLINE-090-100-EVIDENCE-CHECK-001`）的排期、`ADMIT-030/050` 的 case id 拆分、N3/N4、H-3/H-4 的产品下载器归属。**本轮没有连接、也没有探测用户的远程服务器**；规范卷只有 E 写，M 只读。
- **不声称** Minekin 已完成；不声称任何 gate 点亮（`W00/W10/W20/W60` 的 `promotable` 分布与上轮逐字相同，仍是机器候选）；不声称那 9 份宿主解释器的旧 repo bundle 判决是假的（本轮只让它**可见**）；不声称 G1/G2 已有真跑层证据（要到 `E-RR` 读数才算）；不声称 `E-RR`/H2 已验证。

## M 主控第四轮（2026-09-27）：H2 双审合入、⑤ 的触发条件被卷上字节满足、H3 派工与一条流程更正

四态口径逐条给：**已合入 main / 仅在分支 / 真实封证 / 尚未验证**。本轮 M **没有写规范卷**（全程 `:ro`，且 H2 的复量在自己的卷里），**没有 M 侧新的真跑封证**，也**不点亮任何门**；`mandatory`、registry `status/gaps`、case 判据一字未动。

- **已合入 main（一笔，快进式推进，无 force）**：`58e0fb4 → 6ce9f06`，合并提交 `6ce9f065d6d98e824c6b6d10d08901ce5a2b5f54`（parents `58e0fb4` + `24d9142`），`git push origin main` 后 `git ls-remote origin refs/heads/main` 核得同一枚；lane 分支 `refs/heads/codex/minekin-controlled-server-status = 24d91425ad028b9d0c7a832bb1ece8ddccb9e1bc` 同步核过。合入前先 `git merge-base --is-ancestor origin/main main` 证 `origin/main` 是本地 `main` 祖先，再 `git status` 确认工作树干净。
  - `6ce9f06` = **H2 `V1201-CONTROLLED-SERVER-STATUS-KNOB-001`**（lane 提交 `802f6fc` 实现两文件 `+382/-6`、`24d9142` 记录 `+154`；base `be4e79b`，真实 `merge-base` 与主干核过）。改面逐字只有 `tools/run_controlled_server.py`、`tests/contract/test_controlled_server_runner.py` 与该 lane 自己那份 `docs/validation/v1201-controlled-server-status-knob-2026-09-27.md` ⇒ **无 `test-orchestrator/**`、无产品 `src/**`、无 case 判据、无 registry 字节、无门禁改动**。**交付**：`DEFAULT_ENABLE_STATUS = False`（默认一字未动）＋ `--enable-status`（`store_true`，与 `--accept-eula` 同风格）＋ 写后回读打印 `enable-status: asked for <x>, the settings written say <y>`（值来自 `read_back_enable_status(directory)` 从磁盘 `server.properties` 取的**最后一行**，与 `domain.sh` 的 `sed … | tail -1` 同一读法，缺行/缺文件报 `unreadable`）＋ 落盘前的 `status_switch_refusal(profile, online_mode=…, enable_status=…)`（不发明政策：只用本文件自己声明的 `profile.is_loopback` 与写文件时同一处 `_online_mode_text(...)` 推导）。
  - **M 侧独立双审（不照抄 lane 自报）**：① 三组反向证明由 M 自己重跑（脚本 `.tmp/m-reversal.sh`，每做完一组 `git checkout --` 还原、还原后 `git status --porcelain -- tools/ tests/` 为空）——把 `git show HEAD~1:tools/run_controlled_server.py` 原样放回 ⇒ 新案 `6 failed, 18 passed`；只把 `DEFAULT_ENABLE_STATUS` 翻成 `True`（其余一字不动）⇒ `2 failed, 22 passed`，指名 `assert True is False` 与 `assert set() == {'enable-status'}`；把 `status_switch_refusal` 改成先 `return None` ⇒ 地址/认证两案转红。**默认值不是空转、`false`↔`true` 只差那一个具名开关**这两件事就此钉在测试而不是叙述上。② 承重读数由 M 在容器里独立复量（脚本 `.tmp/m-status-verify.sh`，镜像 `b67a4d917306`、钉住 1.21.4 jar、M 自建卷 `minekin-m-status-verify`，**规范卷一次都没挂，连 `:ro` 都没有**；原始记录 `.tmp/m-status-verify2.log`）：不带旗标 ⇒ 第 14 行 `enable-status=false`、`connect: accepted`、产品探针 `NO_RESPONSE` / `the endpoint closed before any frame` / `received_bytes: 0` / rc=17；带 `--enable-status` ⇒ 第 14 行 `true`、探针 `OBSERVED` / `protocol: 769` / `version_text: "1.21.4"` / `received_bytes: 163` / **rc=0**；`--enable-status --online-mode` ⇒ rc=2 具名 `AUTH_MODE_MISMATCH` 且 `run directory exists? no`。三格与 lane 记录**逐字相同**。③ 门禁在合入树上：全量 `uv run --frozen pytest -q` ⇒ `2534 passed, 3 skipped in 423.08s`（rc=0），ruff check/format `342 files`、pyright `0 errors`、四项 tools 脚本、`git diff --check` 全绿；lane 侧那轮 `24 passed`（针对该文件）与 `2534 passed` 同数。
- **真实封证（本轮新增的是 E 的，不是 M 的；M 只读看到）**：`E-RR` 的第一次重跑已在规范卷上封成**具名 FAIL** —— `CORE-030` attempt `sequence 3`、`supersedes_run_id = 19ff9064…`（第四刀那条 PASS 原样保留）、bundle 目录 `/data/kin/kin-e-rr-seal/run/evidence/787168062c4047b48e32620984d6d814`（10 件工件）、`result: FAIL` 且 `verified/sealed = true`、`from_repository_build = true`、复判 `AGREES`。两条判据各给具名否：`the_first_snapshot_of_the_world_it_dialled_was_admitted:NO_CONNECTION_WAS_DIALLED`、`the_world_this_run_joined_is_the_one_the_case_names:THE_CLIENT_NEVER_DIALLED_A_PORT`；run document `outcome: HANDSHAKE_TIMEOUT`、`snapshots_admitted 0`、`session_state STOPPED`；工件里 `client/crash-reports/crash-2026-09-26_17.19.18-client.txt` 的 `Description: Initializing game` + `java.lang.IllegalStateException: Failed to initialize GLFW, errors: GLFW error during init: [0x1000E]Failed to detect any supported platform`，`client/stderr.log` 末行 `error: XDG_RUNTIME_DIR is invalid or not set in the environment`。**这两条判据的否是那次客户端崩溃的下游，不是新的入服逻辑缺陷**；同时 ③（`domain.sh:657` 的静默 `rc=2`）**已不再是这条 run 的失败形状**——它现在给的是完整判据读数加崩溃材料，即 H1b 的具名化在这条真跑上生效了。**⑤ 的「再次量到才触发」条件就此满足** ⇒ M 登记 `H1c`（`QUEUED`，排在 H3 之后，见 §4 行）；`不可重现` 一句按新读数更正为「两次量到、仍非确定性」，不编根因。M 同时只读看到 `/data/kin/kin-e-rr-seal2/run/session/fa96bd1a…` 比那份 bundle 更新 ⇒ **E 的第二次尝试此刻仍在跑**，M 不介入、不代 E 写记录（该 lane 文档尚未 push ⇒ 文档侧仍是「仅在分支」）。卷底数 `attempts 69→70 / bundles 105→106`，而 `from_another_build` 仍 61、`sealed_without_bundle 0`、`unverified 0`、`unreadable 0`、门载荷 sha256 仍 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`、`promotable` 仍 `W00/W10/W20/W60`、构建身份仍 1.20.1 `83299ad5…` / 1.21.4 `bcc0c10d…` ⇒ **一次 FAIL 的封存没有搬动任何门**（复现，在合入树 `6ce9f06` 上、规范卷只读：`docker run --rm --entrypoint /bin/bash -w /src -v <合入树>:/src:ro -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src minekin-runner:local -lc 'python /src/tools/report_promotion.py --data-root /data > /tmp/promo.json; python /src/.tmp/m-h2-readout.py'`，其中 `.tmp/m-h2-readout.py` 是 M 的未跟踪读数脚本，原始输出 `.tmp/m-h2-volume-read.log`；该读者在 `status: blocked` 时按既有契约 `rc=1`，那是期望形状不是失败）。
- **真实封证（第四轮续读，同日稍晚，M 仍全程 `:ro`）**：`E-RR` 的第二次重跑也封成**具名 FAIL** —— `CORE-030` attempt `sequence 4`、bundle `6286f1e5a4a6403b9cfb3b564f2b3118`、`attempt.supersedes_run_id = 787168062c…`、kin 根 `kin-e-rr-seal2`。卷底数变 `attempts 71 / bundles 107`，而 `from_another_build 61`、`sealed_without_bundle 0`、`unverified 0`、九行 `repo_checks_not_from_the_controlled_interpreter`、门载荷 sha256 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`、`promotable = W00/W10/W20/W60`、两枚构建身份（1.20.1 `83299ad5…` / 1.21.4 `bcc0c10d…`）**一字未动** ⇒ 两次 FAIL 没有点亮也没有挪动任何门。**M 新量到的是三次尝试之间的对照**（脚本 `.tmp/m-core030-env-diff.sh`，原始输出 `.tmp/m-core030-env-diff.log`，同一只读容器命令把 `bash /src/.tmp/m-e-rr-peek.sh` 换成它即可复现）：seq 3（`kin-e-rr-seal`）与 seq 4（`kin-e-rr-seal2`）两个**不同全新根**上的 FAIL，其 `client/stderr.log` 逐字节同为那 65 字节 `error: XDG_RUNTIME_DIR is invalid or not set in the environment.`、崩溃报告同为 `Description: Initializing game` + 同一条 `GLX._initGlfw → RenderSystem.initBackendSystem → class_310.<init>` 栈，两条判据仍是 `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT` 那对下游读数；**同案正对照**是 seq 2 的 PASS `19ff9064c…`（kin 根 `kin-04`）：`client/` 下没有 `crash-reports/`、`stderr.log` 为 **0 字节**、run document 给 `connection_state: PLAYABLE` 与 `entities_admitted 71`，而它与 seq 4 的 `launch_plan_digest` 同为 1.21.4 `bcc0c10d…` ⇒ 差异不在 case、不在构建，在那一次交给客户端 JVM 的环境。**M 没有证明的部分照实登记**：主干 `test-orchestrator/runner/domain.sh:878-900` 自己起 `Xvfb :77-99` 并 `export DISPLAY`、`src/minekin_core/config.py:51-55` 的 `FORWARDED_VARIABLES` 点名转发 `DISPLAY`/`XAUTHORITY`，可 seq 3/4 的加入者 JVM 仍报「检测不到任何受支持平台」；要么那两次跑的不是主干这份 runner，要么 `DISPLAY` 在第二个客户端那一跳没真的传过去，而 `manifest.json` 不记录编排它的 `domain.sh` 字节摘要，读者无法只从卷上分辨——这条按 `H1c` 卡面 (b) 处理，不擅自改 seal schema。
- **仅在分支、尚未验证（本轮派工）**：**H3 `V1201-AUTO-PATH-STATUS-WIRING-001`** —— H lane 新支 `codex/minekin-auto-path-status-wiring` @ `../minekin-wt-h3`，base `6ce9f06`。H2 只把旋钮做进工具，`domain.sh:565` 的调用面仍不传它，而同一脚本 `:632-641` 在 auto 路径上按 `-n "${auto_bundle}"` + 回读值 `!= true` 具名早停（那一行的原文就是「the controlled-server tool has to make it answer (registered separately)」——被登记的卡已合入）⇒ **端到端 `--auto-bundle` 真跑今天仍走不通**，这是 H2 记录「停在何处」点名的唯一剩余阻塞。M 钉死的语义：只在**与那条早停同一个谓词**（`auto_bundle` 非空）下传旗标，非 auto 与黑洞 run 不传、保持默认 `false`，`domain.sh:638` 的读回后早停保留为护栏（它读磁盘文件而不是请求）。允许路径只有 `test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py` + 一份新 `docs/validation/` 记录；禁改 `tools/**`；**禁止挂载规范卷**（此刻 E 的 `E-RR` 在写）。并要求它如实具名记录一个诚实的下游事实：auto run 若同时强制 `--online-mode true`，工具会在落盘前 `rc=2` 拒绝（`AUTH_MODE_MISMATCH`）——**不许为了让 run 变绿而悄悄不传 `--online-mode`**。push 后由 M 双审、单张合入并再核远端 SHA。
- **一条流程自我更正（M 的缺陷，记在这里）**：H2 施工中途，M 曾在**该 lane 的活动 worktree** 里跑写文件的反向证明、并顺手提交了一次（`95c9a2d`），而 lane 会话据此先 `git diff 95c9a2d HEAD` 证内容零丢失、再 `git reset --soft HEAD~1` 退回、以准确的 trailers 重提了自己的两笔——它并指出 M 写的 `Not-tested` 声称「未做真 JVM + 活体 status ping」与其真实测量相反（**这条批评是对的**：M 当时不知道 lane 已真跑了 JVM，trailer 应写「M 侧未复量」而不是「未做」）。M 不再犯：本轮之后，**M 的复量与写文件反证只在自己新建的 worktree/卷里做，或被审 lane 明确停笔之后做；绝不替 lane 提交、绝不在活动 lane 树内写文件**。H2 的两笔因此是 lane 自己的 SHA（`802f6fc`、`24d9142`），M 只在其上盖合并提交。
- **lane_next 现状**：主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻，本轮没有被"完成"）；E → B2 未完 + `E-RR`（两次尝试各封一份具名 FAIL，记录仍在分支）；H → **H3**（在分支，M 侧只读看到 `domain.sh` 与 `tests/contract/test_runner_scripts.py` 两个文件被改、尚未提交）+ `H1c`（`QUEUED`，排在 H3 后，卡面见 §2 分类表 ⑤ 行）；S → 暂无安全的 S 卡（N3/N4 属 `BLOCKED_DECISION`）；D/V 仍停等其前置。冲突表与面归属见[并行作业协议](parallel-execution-plan.md) §2。
- **仍然阻着的**（不自答）：HOST §5 三格所有权、PERSIST case 冻结、V08 远程服连接、V09 动作授权、在线认证、数据删除/进程接管，以及 `P0-GATE-PROMOTION-001` 的门禁晋级、B1-b（`P0-OFFLINE-090-100-EVIDENCE-CHECK-001`）的排期、`ADMIT-030/050` 的 case id 拆分、N3/N4、H-3/H-4 的产品下载器归属。**本轮没有连接、也没有探测用户的远程服务器**；未读取任何外部地址；规范卷只有 E 写，M 只读。
- **不声称** Minekin 已完成；不声称任何 gate 点亮（`promotable` 分布与第三轮逐字相同，仍是机器候选）；不声称 H2 的旋钮让 auto run 跑通了（正相反，它让 auto 路径的阻塞点从"猜"变成"具名早停"，接旗标是 H3）；不声称 `E-RR` 拿到了 PASS（它两次尝试封的都是 FAIL，卡的目标未达成，M 判先做 `H1c` 的环境读数而不是第三次裸重跑）；不声称 `DISPLAY` 未转发就是那两次崩溃的根因（M 只量到两次同形状的 stderr 与一份 0 字节的 PASS 对照，机制未证）；不声称 `E-RR`/H3/`H1c` 已验证。

## M 主控第五轮（2026-09-27）：`E-RR` 与 H3 两张 lane 卡合入、⑤ 从观察项改为具名阻断者、并改掉 M 自己上一轮的一处错引

### 起点核对（先量再写）

- 本地：`../minekin-wt-integration`，`main` HEAD 起手 `3932ba5`（E-RR 合并）之前为 `6463e16`；`git fetch origin` 后 `origin/main` 与本地一致，各 lane 分支 SHA 以 `git ls-remote origin` 实读为准。
- E lane：`codex/minekin-evidence` 尖 `918218d`（其上一笔 `0521fcb`），真实 `merge-base` 与主干核为 `be4e79b` ⇒ 与 lane 自报 base 一致。
- H lane：`codex/minekin-auto-path-status-wiring` 尖 **`a70bf38467ac5a46b6ddd5a5cdd55ebb4bd5fded`**（`4b943ce` 实现 + `a70bf38` 记录），base `6ce9f06`（H2 合并），`git merge-base --is-ancestor 6ce9f065 HEAD` 量到「是主干祖先」⇒ 两笔都是干净非 ff 合并，无需处理冲突。

### 已合入 main（两张卡，按依赖顺序逐张）

- **`3932ba5` = `E-RR P0-CORE030-RUNNER-RERUN-2026-09-27`（记 `BLOCKED_HARNESS`，不记 `DONE`）**。改面恰一份新记录 [`docs/p0-core030-runner-rerun-2026-09-27.md`](p0-core030-runner-rerun-2026-09-27.md)（`git diff --stat be4e79b..918218d` = 1 文件 / +137 行）。**M 在本轮改了自己写下的两处**：① 该 diff 的范围一度写成 `626a454..918218d`，量到的是 `11 文件 / +900 -39`——那是从 E **上一轮**的 base 起算，把主干自己推进的内容算进了 lane 改面；范围只能从真实 merge-base 起算。② 上一轮 M 用 `domain.sh:878-900`（会话监督进程自己起 `Xvfb :77-99` + `export DISPLAY`）论证「runner 已经给了显示」，但**加入者客户端不走那一段**：它在 `join_the_published_world()`（主干 `:739`）里由 `xvfb-run -a --server-args="-screen 0 1280x720x24"`（`:776`）起跳。M 逐字节比过整个函数：`ed37260 → be4e79b` 的唯一差异是 ③ 的 +19 行具名基线读，那条 `xvfb-run` 启动行在 `ed37260 / be4e79b / 6463e16` 三处逐字相同 ⇒ **「那两次跑的不是主干这份 runner」这个备选被量掉**，runner 字节不是变量。
- **`cd7664b` = `V1201-AUTO-PATH-STATUS-WIRING-001`（H3）**：把 `--enable-status` 只在 `auto_bundle` 非空这一个谓词下接进 `domain.sh` 对受控启动器的调用面，读回后早停原样保留为护栏；黑洞分支不经受控启动器、拿不到旗标。改面恰三文件 `+320/-0`（`domain.sh` +15、其契约测试 +62、本卡记录 +243），无 registry / 无 case fixture / 无 `tools/**` / 无产品 `src/**`。

### M 侧独立复量（不照抄 lane 自报）

1. **合并树门禁**：`bash -n test-orchestrator/runner/domain.sh`、`uv run --frozen ruff check .`、`python tools/check_case_assertions.py`（`140 registered`）、`python tools/verify_fixture_digests.py`、`git diff --check` 全 `rc=0`；`uv run --frozen pytest -q tests/contract/test_runner_scripts.py` ⇒ **20 passed**。
2. **M 自放的反向证明（一条，主干树上做、`git checkout --` 还原）**：
   ```bash
   git show 6ce9f065:test-orchestrator/runner/domain.sh > test-orchestrator/runner/domain.sh
   uv run --frozen pytest -q tests/contract/test_runner_scripts.py   # → 1 failed, 19 passed
   git checkout -- test-orchestrator/runner/domain.sh                 # → git status 干净
   ```
   红点恰在 `tests/contract/test_runner_scripts.py:593`（`assert text.count("--enable-status") == 1` ⇒ `0 == 1`），即新测试不是空转。H 记录里其余三组变异（always / never / guard）是它的测量，**M 未复量**。
3. **两处承重引用核到代码**：`src/minekin_core/cli/auto_session.py:98` 原文写着该预算拒止 "only appears after the probe and the digest gate" ⇒ 绿 run 停的 `BUDGET_UNDECLARED`（4120 件制品 / 523,788,383 字节）确实是下一个具名前沿，不是旧阻塞换名；`tools/report_promotion.py:244` 的 `_build_agrees` 只比对 recipe 派生的 plan 摘要与 bundle 自记摘要 ⇒ **这次 runner 字节变更不重判卷上任何 bundle**。
4. **合并后规范卷只读复量**（`.tmp/m-h3-readout.sh`、`.tmp/m-h3-rows.sh`、`.tmp/m-h3-evidence.sh`，日志同名 `.log`）：
   ```bash
   export MSYS_NO_PATHCONV=1
   REPO="$(cygpath -m /c/Users/darling/Documents/agent_work/minekin-wt-integration)"
   docker run --rm --entrypoint /bin/bash -w /src \
     -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
     -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src minekin-runner:local -lc 'bash /src/.tmp/m-h3-rows.sh'
   ```
   读数：`attempts 71 / bundles 107 / from_another_build 61 / sealed_without_bundle 0 / unverified 0 / unsealed 0 / unreadable 0 / repo_checks_not_from_the_controlled_interpreter 9`；门载荷 `sha256 = fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`、`promotable` 仍 `W00/W10/W20/W60`、`overall` 仍 `REQUIRED_CASE_NOT_REGISTERED`、`report_rc=1`（不晋级 shape）；两枚构建身份一字未动（1.20.1 `83299ad5…` / 1.21.4 `bcc0c10d…`）。`CORE-030` 四行 seq 1 FAIL / seq 2 PASS / seq 3 FAIL / seq 4 FAIL 全部仍 `from_repository_build true`、`re_judged AGREES`、`verified/sealed true` ⇒ **第 3 点的代码判断有活体读数支撑**。只读性用真写入试探证明：`open("/data/.m-h3-write-probe","w")` ⇒ `OSError: [Errno 30] Read-only file system`（`os.access` 在容器 root 下恒真，不能当哨兵——M 第一轮探针就错在这里）。
5. **⑤ 的崩溃计数重放**（`.tmp/m-joiner-crash-tally.sh`，同一 `:ro` 挂载，按「会话副本 vs bundle 副本」去重）：`Time: 2026-09-26` 的 `[0x1000E]` 加入者崩溃共 **6 个具名时刻**——`kin-04 12:24:07`（第四刀 seq 1）、`kin-e-rr-branch 16:58:38` 与 `17:10:06`、`kin-e-rr-seal 17:19:18`（seq 3）、`kin-e-rr-seal2 17:31:04`（seq 4）、`kin-e-rr-imgprobe 17:41:35`（E 的换修前镜像探针）；`kin-01`（宿主根）只有 2 份崩溃文件且都是 `2026-09-19` 的旧字节 ⇒ 今日宿主侧 **0 次**。E 报的是它窗口内的 4/4，M 的 6/6 是更宽的同向读数；今天唯一没崩的那次正是 12:46 的 seq 2 PASS。

### 真实封证

本轮 **M 没有产生任何 sealed evidence，也没有写规范卷**（全程 `:ro`）。卷上的两份当前构建 `CORE-030` 新封是 **E 的**，且都是 FAIL：seq 3 `787168062c4047b48e32620984d6d814`、seq 4 `6286f1e5a4a6403b9cfb3b564f2b3118`（`supersedes` 指向前者），两条判据各给具名否 `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT`。当前构建的 LAN PASS 仍是第四刀的 seq 2 `19ff9064c…`，台账链尾在 seq 4 FAIL——这是「保留每个失败 attempt」的直接后果，M 不动它、也不粉饰。

### lane_next 现状

- 主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻，本轮没被"完成"）。
- **H → `H1c`**：由 `QUEUED` 转为该 lane 的 `lane_next`（H3 已合入，`domain.sh` / Dockerfile 面前序已清）。卡面三条 (a)(b)(c) 在[执行计划](development-execution-plan.md) §2 分类表 ⑤ 行；派工仍需 E 释放规范卷写入窗口。**不点亮、不放宽任何门；`environment.renderer_display`（六份 manifest 一律写 `llvmpipe (LLVM 20.1.2, 256 bits)`，含客户端从未建过窗口的那几份）不得顶替客户端侧读数；不擅自往 `minekin.p0.evidence.v1` 加字段**（那会重封全卷，属门禁归属人的决定）。
- **E → B2 剩余范围**：`E-RR` 不再挂着；它的 LAN 形状当下被 ⑤ 具名阻断，M 的判断是先做 `H1c` 的环境读数而不是第三次裸重跑；B2 其余不依赖 joiner 客户端的形状仍可独立推进（task 台账上「B2 剩余范围等主控排期」一条仍开着）。
- S → 暂无安全的 S 卡（N3/N4 属 `BLOCKED_DECISION`）；D/V 仍停等其前置。冲突表与面归属见[并行作业协议](parallel-execution-plan.md) §2。

### 不声称

不声称 Minekin 已完成；不声称任何 gate 点亮（`promotable` 与第三、四轮逐字相同，仍是机器候选）；不声称 H3 让端到端 auto JOIN 跑通了（它停在一个**更靠后**的具名前沿 `BUDGET_UNDECLARED`，补 store 是 523 MB 的具名预算决定，未做）；不声称 ⑤ 的根因、归类或「这是 trunk 回归」——被量掉的只有「不是 runner 那 85→104 行的改动、不是 H1a 镜像、不是 case 也不是构建」，没被量掉的是 `xvfb-run` 那一次究竟有没有给子进程可用显示、以及那 65 字节 `XDG_RUNTIME_DIR` 与它是否同一条因果链；不声称 M 复量了 E 的容器探针或 H 的四组活体读数（都没复量，两侧全量 `pytest` 也未重跑）；不声称 `H1c` 已验证。全程未连接、未探测、未读取用户的远程服务器（`.tmp/local-test-server.txt` 未被打开），文中只出现 loopback/受控本地地址、卷名与镜像名。

## M 主控第六轮（2026-09-27）：V2 双审合入、M 改掉自己为 E 写的 B1-b 三处、新登记候补卡 `H1d`

### 起点核对（先量再写）

- 主干推进顺序（`git log --oneline main`）：第五轮收尾 `9ac99c0` → `cb4786f`（H1c 派工 + M 自己 `:878-900` 错引的更正）→ `332e47e`（V lane 独立活体验证面的登记）→ `93b1f0a` + `a04d66f`（B1-b 排卡、V2 派工）→ V lane 尖 `9ec4486` → 本轮合并 `b6f23a8`。`git ls-remote origin` 实读：`refs/heads/main = b6f23a89888d9b5f46f14e1601400955f18bd7d0`、`refs/heads/codex/minekin-v1201-auto-status = 9ec448648261e808fe8ce69f7512fae6f59bebfd`、`refs/heads/codex/minekin-evidence = 918218d6…`（E 自第五刀后未再前进）。
- V lane 自报 base `cb4786f`；**施工期间主干又前进过**，M 用真实 merge-base 核：差面恰 `1 文件 / +314`（`docs/validation/v1201-auto-status-1201-2026-09-27.md`），产品/runner/工具/registry/判据一字未动。合并干净无冲突。

### 已合入 main（一笔）

- **`b6f23a8` = `V1201-AUTO-STATUS-ON-1201-001`（V2）**：把 M 前几轮明写「未测」的「1.20.1 recipe × `--enable-status`」在 1.20.1 隔离侧量成四组真实读数（V-a 红/绿/非 auto 对照/`AUTH_MODE_MISMATCH`），V-b 给 ⑤ 家族在 1.20.1 的**诚实零读数**，V-c 复核 bridge 那件阻断仍成立。V 的原话按字节留下：**「V-a 结论：1.20.1 recipe × `--enable-status` 从「未测」变为四组真实读数（红/绿/对照/mismatch）」**、**「端到端完整 JOIN：未达 PASS，按 `BLOCKED_HARNESS` 具名收口」**。

### M 侧独立双审（不照抄 lane 自报）

1. **承重引用逐字对仓库字节核过**：`.tmp/v2-domain-preh3.sh` 与 `git show 6ce9f06:test-orchestrator/runner/domain.sh` 同枚（sha1 实读 `0eb3f55dfa10d686553ff1da8f514e5f5266f198`）；`domain.sh:404-407`（auto 不能带加入者）、`:575-578`（谓词 `-n "${auto_bundle}"`）、`:739`（joiner profile 钉死 `"minecraft_version": "1.21.4"`）、`:791`（加入者 `xvfb-run -a`）、`bundle-candidate-1.20.1.json` 的 `"source": "workspace:bridge-1201"`，全部属实 ⇒ V 的 V-b 构造依据与 V-c 的阻断判断不是推断。
2. **M 重放了 V-a 的承重两组**（`.tmp/m-v2-run.sh` + `.tmp/m-v2-domain-preh3.sh`，日志 `.tmp/m-v2-red.log` / `.tmp/m-v2-green.log`；1.20.1 服务端 jar 走 `tools/verify_supply_chain.py --version 1.20.1` 具名取料、7 枚钉摘要仍匹配）：红 ⇒ `M: domain.sh rc=2` + run 目录第 12 行 `enable-status=false` + 具名早停开火；绿 ⇒ 工具自报 `asked for true, the settings written say true` + 第 12 行 `true` + 跨过早停 + 停在 `3639 of 3639 artifacts are missing and would cost 738432269 bytes … [BUDGET_UNDECLARED]`。**与 V 记录逐字同值**，且与 1.21.4 那形的 4120 件 / 523,788,383 字节明确不同形 ⇒ 早停护栏不恒绿、旗标不恒开。全程在 M 自己新建的 worktree 与自建卷 `minekin-m-v2-verify` 上，**规范卷 `minekin-runner-data` 连 `:ro` 都没挂**。
3. **合并树门禁**：`ruff check`、`ruff format --check`（344 文件）、`pyright`（0 errors）、`check_boundaries`、`check_case_assertions`（140 registered）、`verify_fixture_digests`、`check_workflow_pins`、`git diff --check` 全 `rc=0`；**规范卷只读复量到 `report_promotion` 门载荷 sha256 在合并前后都仍是 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`**、`promotable` 仍 `W00/W10/W20/W60`、`attempts 71 / bundles 107` 一字未动 ⇒ 一个纯文档 lane 卡没有搬动任何门。
4. **M 未复量**（照实在主干记）：V 的 mismatch 与 control 两组（M 只核了谓词字节）、V-c 的 738 MB 取件与装后前沿、V-b 的零计数（M 侧同样没有 1.20.1 加入者起跳面，无从反证）。

### 本轮的第二件事：M 改掉自己为 E 写的 `B1-b` 三处

第六轮在只读预检 `B1-b` 卡面时，M 量到三个自己上一轮写下的缺陷，逐条当场改主散文档（`259d597` / `009fcee` / `345d9af`），**没有让 E 去重做 M 的测量**：

1. **「台账载体不存在」是 M 的命名方法缺陷**：M 拿字面串 `ledger` 去搜工件路径，而常量拼的是 `bridge-trace.jsonl`。载体链现按字节钉死：SQLite 台账 → `ledger_rows(database, run_id)`（`tools/assert_case_evidence.py:282`，按 `position` 排序、按 `run_id` 取）→ `timeline_bytes(...)`（`:304`，一行一个 JSON 对象）→ 封存为工件 `bridge-trace.jsonl`（`LEDGER_TIMELINE_ARTIFACT`，`src/minekin_core/adapters/evidence/trace.py:73`；落盘点 `tools/seal_run_evidence.py:788`），上一 run 的行另存 `previous-run-trace.jsonl`。卷上活体读数：**94/107 份 bundle 有该工件**、manifest 以 `{path, sha256, size}` 声明、`present_not_declared = 0`、每个 3–24 行且无空文件、19 个字段键；缺的 13 份全在 `repo-evidence/` 之下（正对照：仓库自检通道本就没有 bridge 会话）。据此「甲」类从被 M 错降的 4/5 **复原为 5/5**。派工前置换成：引用那些字段名，不要把 `orchestrator-trace.json` 当台账。
2. **死指针 `docs/contracts/**`**：该目录不存在。判据锚点改为契约真实行号 `docs/p0-offline-session-compatibility-contract.md:155-156`，并带上 `:158` 那句「所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。」OFFLINE-090 的可读文本 = `CLIENT_STREAM_ARTIFACTS`（`assert_case_evidence.py:709`）+ crash 目录（seal `:252-254`）+ `server.log`（`:256`）；OFFLINE-100 = 两份 trace 工件里的 `kin_id`/`world_context_id`/`session_id`/`generation` + `server/usercache.json`（`:257`）。
3. **M 写的验收 ③ 与本卡目标互相矛盾**：case registry **就是** fixture 目录（`load_case_registry()` 直接 glob `*.json`，`src/minekin_core/adapters/evidence/promotion.py:111-114`），而 `REQUIRED_CASES` 已含 OFFLINE-090/100（`src/minekin_core/domain/cases.py:354-355`）⇒ 注册它们必然让 `requirement()` 的 `absent` 变空（`:799-806`）、`PromotionBlock.REQUIRED_CASE_NOT_REGISTERED` 消失（`:884-891`），「门载荷一字不动」与「注册缺的 case」不可能同时成立。验收 ③ 拆成两种可量形状：(i) 只做封存侧 ⇒ 摘要必须仍 `fb0152c8…`；(ii) 注册 OFFLINE-090/100 ⇒ 摘要必然移，须给前后两枚摘要 + 逐项差异、点名出现/消失哪个 block、`promotable` 冻结不晋级。门晋级仍归主控。

### 本轮的第三件事：新登记候补卡 `H1d`（runner 读数可见性缺口）

V2 的绿读数暴露、M 在自己卷上重放确认：auto run 跨过早停后停在具名供应链/预算前沿时，domain 层已打印 `the session never became playable within 30s (the session exited first)`、`this run is ` 与 `the run document said ` 皆空（无 run document ⇒ seal 通道未触发），**而 `domain.sh` 仍返回 `rc=0`**（`.tmp/m-v2-green.log:6,11,12,20`）；同一驱动的红形状在服务器段具名早停时返回 `rc=2`（`.tmp/m-v2-red.log:6`）⇒ 通道不是恒零，只是粒度不够：「客户端 JVM 从未起跳」与「起了跳但没到 playable」在退出码上不可区分，只读 rc 的调用方会把「停在预算门」当成成功。卡面、先红后绿验收与允许面已写进执行计划同名行（`QUEUED_PROPOSED`，等 `H1c` 收口后提升为 H lane 下一张；禁挂规范卷、禁往 `minekin.p0.evidence.v1` 加字段）。

### 真实封证

本轮 **M 没有产生任何 sealed evidence，也没有写规范卷**（V2 重放在自建卷、卷上复量全程 `:ro`）。V2 自己也明写「**本卡不产生封证**」，其四组读数属 lane 侧活体测量，不是主干可引用的 sealed evidence。

### lane_next 现状

- 主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻，本轮没被"完成"）。
- **H → `H1c` 在工**：该 lane 的 worktree 现有未提交改动（`test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`），分支尚未 push ⇒ M 未进该树、未在其中写文件，只在派工 base 的字节上做只读引用核对。`H1d` 排在其后。
- **E → `B1-b`（`OFFLINE-090/100` 的证据检验）已按上面三处更正定稿，`QUEUED`，等 `H1c` 合并后派工**；B2 剩余范围（非 mandatory 的 HOST 家族）仍阻在 §5 的 ownership 决定。
- **V → 无安全可派卡，停等具名**：1.20.1 端到端 JOIN 的阻断者是 bridge 非 https 不可联网获取（H-2 未落地）与 joiner 无 1.20.1 起跳面，两者都不是 V lane 能自行解除的。
- S → 暂无安全的 S 卡（N3/N4 属 `BLOCKED_DECISION`）；D → D1 已合入，D2 等 Gateway 只读契约冻结。冲突表与面归属见[并行作业协议](parallel-execution-plan.md) §2。

### 不声称

不声称 Minekin 已完成；不声称任何 gate 点亮（门载荷摘要与第三、四、五轮逐字相同）；不声称 1.20.1 的 auto JOIN 可用（V2 绿读数只证明 status 那格打开，端到端仍 `BLOCKED_HARNESS`）；不声称 ⑤ 在 1.20.1 被复现或被排除（V-b 是零读数，形状到不了）；不声称 M 复量了 V 的 mismatch/control/V-c 四处（都没复量，点名在案）；不声称 `B1-b` 已跑或已派工（它仍是 `QUEUED`，等 `H1c`）；不声称 `H1c`、`H1d` 已验证。全程未连接、未探测、未读取用户的远程服务器，`.tmp/local-test-server.txt` 未被打开；文中只出现 loopback/受控本地地址、卷名与镜像名。


## M 主控第七轮（2026-09-27）：`H1c` 双审合入 `3706524`、`B1-b` 第一阶段定标、orchestrator 版本可见性缺口登记

### 起点核对（先量再写）
- 恢复时远端 `refs/heads/main = dd3f4b1c79b132c85b9b8ff50922c45b3b1ae673`（= 第七轮派工的两笔回写 `3b00ca3` → `dd3f4b1`）；共享 checkout 停在 `codex/core-state-transition @ 6a02ac6`，M 未在其中写文件。
- M 合并前在 `dd3f4b1` 上实读的底数（`.tmp/m-r7-baseline.sh`、`.tmp/m-h3-evidence.sh`，规范卷 `:ro`）：写试探 → `OSError: [Errno 30] Read-only file system`；门载荷 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`；`promotable = ["W00","W10","W20","W60"]`；`overall.blocks = ["REQUIRED_CASE_NOT_REGISTERED"]`；`attempts 71 / bundles 107 / from_another_build 61 / sealed_without_bundle 0`。

### 已合入 main（一笔）
- `370652462c75e4e59837ae4d5eda11b95f410f7b` = H lane 的 `H1c`（支 `codex/minekin-client-env-readout`；lane 提交 `e846c27` 实现、`de579ad` 记录；base 为真实 merge-base `9ac99c0`）。推送后 `git ls-remote` 读到 `refs/heads/main` 与本地一致。

### M 侧独立双审（不照抄 lane 自报）
- 改面从真实 merge-base 起算：3 文件、`+676 -1`，全在 H 独占面（`test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`）加该 lane 自己那份 `docs/validation/v1201-client-env-readout-2026-09-27.md`，无越界、无地址泄漏、未碰 Dockerfile。
- 门禁：`bash -n` rc=0；契约 `22 passed`；全量 `uv run --frozen pytest -q` → **`2537 passed, 3 skipped in 415.31s`**（主干基线 2535 ⇒ 恰为两张新测）；ruff check / ruff format --check / pyright / `check_boundaries` / `check_case_assertions`（140 registered）/ `verify_fixture_digests`（W00 OK）/ `git diff --check` 全 rc=0。
- M 自己的反向证明：把 `name_the_joiner_client_environment` 与 `classify_the_joiner_downstream_readings` 两个调用点各改成注释 → `2 failed, 20 passed`（新测确实承重，非恒真）；还原后 `sha256sum` 与审前逐字节一致、`git status` clean。
- 采信卡面 `(b)`：现有 bundle 读不出 `domain.sh` 字节，修复需碰 seal schema ⇒ 留主控（主计划 §3.3 的 `BLOCKED_DECISION` + `QUEUED_PROPOSED` 两行）。本卡未加字段、未重判任何 attempt。

### 审查发现（两处，均未由 M 代改）
1. `H1c` 记录写「客户端 JVM 拿到的正是 `launch` 那组值」——**过强**：`launch` 读数取自探针自己那次 `xvfb-run` 调用，与真起客户端那次是两个进程，`XAUTHORITY` 临时目录必然不同、屏号只是可能重分配相同。要坐实需容器成对实测 ⇒ 追加为 `H1d` 的验收（并行计划 §4 同名行）。**M 侧未复量**（引擎故障）。
2. `H1c` 那跑（`kin-h1c-v26`）在 90 秒窗后**确实加入了世界**（`snapshots_admitted 1`、终态 `BRIDGE_LOST`），而分类器挂在超时分支上，写下 `THE_RUN_DIED_ON_THE_CLIENT_SIDE`。lane 自己已在记录里把这条措辞越界登记为待定夺，M 认可其判断、不改字节。

### 仅在分支
- E lane 的 `B1-b` **第一阶段**（支 `codex/minekin-offline-090-100` @ `../minekin-wt-b1b`，base `03c1d95`）：本轮已产出四组仓库外测量（preflight、卷普查、门底数、工件内容分布，`.tmp/e-b1b-*.log`），施工面 clean ⇒ 尚无提交，**仅在分支、尚未验证**。

### 真实封证
- 本轮零封证：M 全程 `:ro` 读规范卷，未新建 attempt/bundle，未重判既有行；合并前底数 `71 / 107` 为实读。

### 新增阻断（需要用户/主控动作）
- **受控容器引擎不可用（第七轮收尾时已诊断到根因）**：`docker version` 自 2026-09-27 19:34Z 起回 `500 Internal Server Error`，19:48Z 复测时 `tasklist //FI "IMAGENAME eq Docker Desktop.exe"` 给 **`No tasks are running which match the specified criteria`**，且 `docker info` 改报 `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` ⇒ **不是引擎报错，是 Docker Desktop 整个没有在运行**（`docker context ls` 里 `desktop-linux` 仍是指向该 npipe 的当前 context，配置未变）。受影响面：`H1d` 的活体测量、`B1-b` 的封存侧、任何 `:ro` 门载荷/台账复量、⑤ 家族的再次观察，以及一切受控真跑与封存。**M 不启动也不重启用户机上的该进程**（进程接管属保留决策）。**恢复后第一件事**：在 `d455309`（或其后）重放 `.tmp/m-r7-baseline.sh` + `.tmp/m-h3-evidence.sh`，核对门载荷仍 `fb0152c8…`、底数仍 `71 / 107`、镜像仍 `minekin-runner:local` 且 id `b67a4d917306`，再派 `H1d`。
- **一条数据风险提示（属用户动作，M 不代做）**：规范卷 `minekin-runner-data` 与各 lane 卷都活在 Docker Desktop 的 VM 磁盘里。仅仅**启动** Docker Desktop 不会动它们；但 VM 的磁盘压缩/重置或菜单里的 **Clean / Purge data** 会**删卷**，那等于删掉 `attempts 71 / bundles 107` 的全部规范证据。数据删除属保留决策，故 M 只登记不处置。

### lane_next 现状
- 主干唯一 `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`。H = `H1d`（已提升，阻于引擎）；E = `B1-b` 第一阶段在工、封存侧写窗前置已满足；V/S/D 无安全可派卡（V 的下一张需要 `H1d` 起的加入者起跳面）。

### 不声称
- 不宣称 Minekin 完成；不宣称端到端 1.20.1 auto JOIN 跑通过过一次「窗内到达 + 正常收尾」的运行；不宣称任何门禁点亮（`promotable` 仍 `W00/W10/W20/W60`，`overall.blocks` 仍 `["REQUIRED_CASE_NOT_REGISTERED"]`）。


## M 主控第八轮（2026-09-27）：受控容器引擎恢复、合并树 `:ro` 复量补完、两张卡派工

### 起点核对（先量再写）
- 恢复时远端 `refs/heads/main = 796316ad68724584178add0e34f8370dd22a5098`（= 第七轮回写的三笔 `3706524` → `d455309` → `14830cc` → `796316a`）；M 的集成 worktree `../minekin-wt-integration` 与主干同步、工作树 clean；共享 checkout `codex/core-state-transition @ 6a02ac6` 未由 M 写入。
- 用户启动 Docker Desktop 后 M 实读：`docker version` → `Server Version 29.5.3`；`docker image inspect minekin-runner:local` → id `b67a4d917306`；卷 `minekin-runner-data` 在位。第七轮诊断的根因（**整个应用没有在运行**，而非引擎报错）据此确认并解除；M 全程未自行重启/接管任何进程。

### 已合入 main
- 本轮无新的 lane 卡合入（本节的回写即是本轮唯一主干改动）。

### 补完：第七轮欠下的合并后 `:ro` 复量（本轮已做，替代主干里所有「M 侧未复量」）
- 在合并树 `796316a` 上以 `minekin-runner:local`（id `b67a4d917306`）挂仓库 `:ro` + 规范卷 `:ro` 重放 `.tmp/m-r7-baseline.sh`、`.tmp/m-h3-evidence.sh`（脚本在 `../minekin-wt-integration/.tmp`，日志 `.tmp/m-r8-baseline.log`、`.tmp/m-r8-evidence.log`）：
  - 只读性证据是真实写试探 → `OSError: [Errno 30] Read-only file system`，不是 `os.access` 断言。
  - 门载荷 `report_rc=1`、`gate_payload_sha256 = fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`、`promotable = ["W00","W10","W20","W60"]`、`overall.blocks = ["REQUIRED_CASE_NOT_REGISTERED"]` ⇒ 与第三～七轮逐字相同，`H1c` 的合入没有移动任何门禁读数。
  - 台账底数 `attempts 71 / bundles 107 / from_another_build 61 / repo_checks_not_from_the_controlled_interpreter 9`，`sealed_without_bundle 0 / unreadable 0 / unsealed 0 / unverified 0`；两个 build 计划 SHA（1.20.1 `83299ad5…`、1.21.4 `bcc0c10d…`）照旧可读；`CORE-030 rows: 0`、`supersedes: []`。

### 仅在分支（两张在工，均未提交 ⇒ 尚未验证）
- H lane `H1d`：支 `codex/minekin-h1d-run-rc` @ `../minekin-wt-h1d`，base `796316a`，工作树 clean、`git log` 尖仍是 base ⇒ 施工中、零提交。三项验收：① auto run 停在具名前沿时 `domain.sh` 的 `rc=0` 可见性缺口，② `launch` 深度读数取自真起客户端那次 wrapper（成对实测对照，坐实或改正 `H1c` 记录里那句过强措辞），③ 相应措辞修正。禁挂规范卷、禁改判据/registry/门禁/seal schema。
- M 自己 naming 卡 `INT-ORCHESTRATOR-REVISION-VISIBILITY-001`：支 `codex/minekin-orchestrator-revision-visibility` @ `../minekin-wt-revvis`，base `796316a`，当前未提交改动 = `tests/unit/test_report_promotion.py` `+43`（只动 `tools/report_promotion.py` 与其单测）。它只把「bundle 不钉编排脚本版本」这件事变成报告里可读的具名事实，不改判据、不写卷。
- E lane `B1-b` 第一阶段：支 `codex/minekin-offline-090-100` @ `../minekin-wt-b1b`，base `03c1d95`，工作树 clean、零提交；会话仍在产出仓库外测量（`.tmp/e-b1b-stage2.sh`、`stage3.sh`、`offline-090.proposed.json`、`offline-100.proposed.json`）。M 未在该 worktree 写任何文件。

### 真实封证
- 本轮零封证：M 全程 `:ro` 读规范卷，未新建 attempt/bundle、未重判任何既有行、未翻 `status/gaps`、未晋级任何门。`attempts 71 / bundles 107` 与第七轮逐字相同。

### lane_next 现状
- 主干唯一 `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`。H = `H1d`（在工）；M = `INT-ORCHESTRATOR-REVISION-VISIBILITY-001`（在工）；E = `B1-b` 第一阶段在工、其**封存侧**前置已满足（写窗空闲）；V/S/D 无安全可派卡（V 的下一张要等 `H1d` 给出加入者起跳面）。

### 不声称
- 不声称 Minekin 完成；不声称端到端 1.20.1 auto JOIN 有一次「窗内到达 + 正常收尾」的运行；不声称任何门禁点亮（`promotable` 仍 `W00/W10/W20/W60`，`overall.blocks` 仍 `["REQUIRED_CASE_NOT_REGISTERED"]`）；不声称 `H1d`/`B1-b`/`INT-ORCHESTRATOR-REVISION-VISIBILITY-001` 已验证（三张都还没有提交）。全程未连接、未探测、未读取用户的远程服务器，`.tmp/local-test-server.txt` 未被打开；文中只出现 loopback/受控本地地址、卷名与镜像名。


## M 主控第九轮（2026-09-27）：`B1-b` 第一阶段交付审查 —— 内容采信、落点越界、派落位修正

### 起点核对（先量再写）
- 恢复时远端 `refs/heads/main = 4a7d132f67d329e842e220323e8daaa83a24a278`；`git ls-remote` 首查三条在工分支全无远端 ref，随后收到 `B1-b` 会话完成件：支 `codex/minekin-offline-090-100` 远端尖 `b2e9be339af8edb60966af13c4cc9dbc426c923e`。`H1d` 与 `INT-ORCHESTRATOR-REVISION-VISIBILITY-001` 两支仍无远端 ref（本地 `minekin-wt-h1d` 尖 `796316a` 干净、`minekin-wt-revvis` 有未提交改动）。

### M 侧独立双审（不照抄 lane 自报）
- 改面从**真实 merge-base** 起算：`git merge-base origin/main origin/codex/minekin-offline-090-100` = `03c1d95bd7c8c440756e91598afd3b1bc91938a4`（与卡面自报 base 一致），parent 亦为该 SHA，`git diff --stat` = **1 文件 / +323**，无第二笔、无夹带。
- 仓库字节核过的两处引用：① 该文 `:97` 引的哨兵字面量确实存在，真实路径是 `src/minekin_core/adapters/launcher/offline_session.py:71` 与 `:82` 的 `access_token_argv="0"`（lane 正文写成 `offline_session.py:71-84` 的简写路径）⇒ **「090 判据按字面读会永红/不可判」这条阻塞属实**，需主控钉「字面量集合口径」。② `git ls-files | grep -i registry` 只给 `tests/fixtures/registry/reviewed-tested-bundles.json` 等既有件，任何 ref 里没有 `harness/` 树 ⇒ 它自报的「registry 冻结面尚未成形」与主干字节一致。
- 门读数三方一致：`B1-b-0` 两次独立复现的门载荷 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`、`promotable W00/W10/W20/W60`、`W30 blocks=[NO_MANDATORY_CASES, REQUIRED_CASE_NOT_REGISTERED]` 与 M 第八轮在 `796316a` 上的自读同值；卷底数 `attempts 71 / bundles 107 / from_another_build 61 / sealed_without_bundle 0` 亦同。它新增的分布读数是本轮第一次有的：**OFFLINE 系 bundle 的 crash-reports 为 0 份，卷上仅 3 份且都属 CORE-030；OFFLINE-070/090/100 零 bundle；53 个声明路径里无任何 Dashboard 载体**。
- 采信与不采信：普查、门基线、两行 contract 逐字引用、哨兵字面量的判定 ⇒ **采信**（可由仓库字节复算）；§2.7/§3.6 的探针与反例、注册后门 sha 增量 ⇒ lane 自己具名「未测」，M 也未复量，**不算已验证**。

### 审查发现（一处，硬阻断合并）
- **落点越界**：交付件落在新建顶层目录 `harness/case-specs/P0-OFFLINE-090-100-CASE-SPEC-001.md`，而本卡允许路径只有「`tests/fixtures/cases/**` 里这两条的定义与其覆盖测试」+「本卡自己那份记录」。`harness/` 不是本仓库任何 ref 里的既有载体，主干计划文档也从不提它 ⇒ **M 不追认越界路径**（既定规矩：越界不能事后追认，只能改落位）。内容与结论不改，只把文件按 E 自己记录的既有惯例（`docs/p0-core030-runner-rerun-2026-09-27.md` 同形）移到 `docs/p0-offline-090-100-case-spec-2026-09-27.md`；已派落位修正会话到 `../minekin-wt-b1b`，明写「只收尾、不重设计」。

### 状态四栏
- 已合入 main：仅本节回写一笔；`B1-b` 未合入。
- 仅在分支、尚未验证：`B1-b` 第一阶段（`b2e9be3`，等落位修正的第二笔）、`H1d`、`INT-ORCHESTRATOR-REVISION-VISIBILITY-001`。
- 真实封证：本轮零封证（M 未挂卷写、未建 attempt/bundle；lane 全程 `:ro`，其自报与本卷实读一致）。
- 尚未验证：`B1-b` 文中未测的探针/反例与注册后门 sha 增量；`H1d` 的活体读数。

### 新增待主控拍板（不代答）
1. `OFFLINE-090` 判据的**凭据字面量口径**：公版哨兵 `access_token_argv="0"` 算不算「暴露」，需钉一个字面量集合与判法，否则该 case 按字面永红。
2. `OFFLINE-090/100` 两条**入册的落点**：注册要动 `tools/assert_case_evidence.py` 的断言函数 + `tools/check_case_assertions.py` 的 `IMPLEMENTATIONS`（`:170`）两行，属 **M 的面**；且两 id 入册**必然移动门载荷**，须与落块读数同次给出。
3. `OFFLINE-070` 是否与 090/100 并单。
4. `OFFLINE-100` 的 A→B→A 闭合要写卷真跑（卷写窗现空闲）。

### 不声称
- 不声称 Minekin 完成；不声称 `B1-b` 已闭环（它连落位都还没改完）；不声称 `OFFLINE-090/100` 已被注册或被封证（零 bundle）；不声称任何门禁点亮（`promotable` 仍 `W00/W10/W20/W60`、`overall.blocks` 仍 `REQUIRED_CASE_NOT_REGISTERED`）。全程未连接、未探测、未读取用户的远程服务器，`.tmp/local-test-server.txt` 未被打开；文中只出现 loopback/受控本地地址、卷名与镜像名。


## M 主控第十轮（2026-09-27）：`INT-ORCHESTRATOR-REVISION-VISIBILITY-001` 合入 `6495356`、`B1-b` 判据设计退回两处

### 起点核对（先量再写）
- 恢复时远端 `refs/heads/main = ca3f9417df44c33944ed34af0d2239c37f391bd2`（第九轮回写）。`git ls-remote` 时点：`codex/minekin-orchestrator-revision-visibility` 已推 `b2e57853c5969d4b8ffa01c592f970c6c06fb5f4`；`codex/minekin-offline-090-100` 已推 `a2a93ea2bd91e2712d25abcc155f3b0c6e1fa5c3`；`codex/minekin-h1d-run-rc` 仍无远端 ref（本地工作树有未提交的 `domain.sh` + `tests/contract/test_runner_scripts.py`）。

### 已合入 main（一笔）
- `64953566e40ab7c2a39b8415c424377874c06a39` = `INT-ORCHESTRATOR-REVISION-VISIBILITY-001`（M 自己的 naming 卡，lane 提交 `b2e5785`，真实 merge-base `796316a`）。推送后 `git ls-remote` 已核。

### M 侧独立双审（不照抄 lane 自报）
- 改面恰 3 文件 `+168`：`tools/report_promotion.py` +33（新常量 `ORCHESTRATOR_REVISION_GAP` / `VISIBILITY_GAPS`，报告里平级新键 `visibility_gaps`）、`tests/unit/test_report_promotion.py` +43、`docs/validation/m-orchestrator-revision-visibility-2026-09-27.md` +92。全在 M 卡自己的面内，未碰判据/registry/schema/seal。
- 合并树门禁：单测 `55 passed`；`ruff check` / `ruff format --check` / `check_boundaries` / `check_case_assertions`（140 registered）/ `verify_fixture_digests` / `git diff --check` 全 rc=0；全量 `uv run --frozen pytest -q` 在合并树实跑 ⇒ **`2538 passed, 3 skipped in 332.26s`**（基线 `2537` ⇒ 恰为这张卡新增的 1 测）。
- M 自放反向证明：注释掉新键那一行 ⇒ `1 failed, 54 passed`（新测承重、非恒真）；`git checkout --` 还原后 sha256 与审前一致。

### 卷侧复量（补 lane 具名未做的那一半：M 在合并树 `6495356` 上以 `:ro` 容器实读）
- 配方同第八轮（镜像 `minekin-runner:local` id `b67a4d917306`，仓库 `:ro` + 规范卷 `:ro`），脚本 `.tmp/m-r10-visibility.sh`、日志 `.tmp/m-r10-visibility.log`：写试探 `OSError: [Errno 30] Read-only file system`；`report_rc=1`；**门载荷子集 `{work_packages, overall}` 仍 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`**、`promotable ['W00','W10','W20','W60']`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']` ⇒ 合入没移动门禁读数。
- 新增可见性的形状已被量出：报告顶层键多出 `visibility_gaps`（值 `ORCHESTRATOR_REVISION_NOT_PINNED`，`artifact orchestrator-trace.json`、`field orchestrator`、`gates_promotion False`），且 `visibility_gaps_in_subset False` ⇒ 平级键按构造不进载荷；整份文档的摘要另为 `e958e624db32240abc8f9d86d764d8357c19fa9a6b538671e7999a8d11724fe2`（与子集不同，具名记录，不作门载荷用）。
- **一处诚实更正**：本脚本里 M 猜的普查 glob `runs/*/bundle.json` 与 `attempts/*.json` 各回 0，那是**路径假设错误**，不是卷为空；现行底数仍是第八轮的 `attempts 71 / bundles 107 / from_another_build 61 / sealed_without_bundle 0`。

### `B1-b` 复审：落位合格、判据设计退回两处（不合入）
- 落位修正 `a2a93ea`（`git mv` → `docs/p0-offline-090-100-case-spec-2026-09-27.md`，rename 97%，累计恰 1 文件 `+324`）合格，M 认可；未重做卷普查。
- **退回两处，且已给具体改法**（主控口径）：
  1. `OFFLINE-090`：草稿 §2.5 第 1 步把「本 run 的凭据字面量」的来源指向 `asserter-inputs.json` ⇒ **M 用仓库字节证否**：`asserter_inputs_bytes` 在 `tools/assert_case_evidence.py:747-763`，写出的键恰为 `schema_version/kin_id/run_id/username/previous_run_id`，**不含 token/xuid/clientId**。判法改为主控钉下的形状：哨兵是公开非秘密值（`access_token_argv="0"`、`client_id_argv/xuid_argv=EMPTY_ARGV`，`src/minekin_core/adapters/launcher/offline_session.py:71/:82`），裸 `0` 与空值一律不算泄漏；只判**带字段/参数上下文的认证正文暴露**（可用名字：`_RECORDED_OPTIONS = ("--username","--uuid","--clientId","--xuid")` `:247`、`auth_access_token` `:166`、`auth_xuid` `:177`、`EMPTY_CAPABLE_PLACEHOLDERS` `:115`），认证字段仍统一脱敏；反例除注入红，还要加**反向对照**（裸 `0`/空值出现仍不得红）。登记形状：卷上无 Dashboard 载体 ⇒ 日志/崩溃只是部分证据，**父案 `OFFLINE-090` 不得标 PASS、不得借非 mandatory 登记暗示闭合**，拆非门禁子案承载那半句、父案保留缺口。
  2. `OFFLINE-100`：草稿 §3.5 B 用「两条时间线 `session_id` 集合互不相交」承担整条 ⇒ 主控判定**不足以证明 A→B→A**。改为逐条断言集合：同一 `kin_id` 贯穿三段、三次不同会话、**首尾两个 A 属同一个「获确认的」world context**（要写出 bundle 字段上的判法）、B 不串入 A、外部身份取服务端证据（`server/usercache.json` 对 `asserter-inputs.json:username` == `str(offline_player_uuid(username))`，`src/minekin_core/domain/offline_identity.py:39`，沿用已注册的 `server_observed_join_identity` 不重推规则）；原两 run 形状降级为「重启那半」的必要条件之一。逐条给反例（A2 带 B 的 world context ⇒ 红；kin_id 变化 ⇒ 红；A1/A2 复用同一 session ⇒ 红；缺 usercache ⇒ 具名不可探，不是绿）。
- 另三处顺手关闭并写进主干：`OFFLINE-070` **单独排卡**（`P0-OFFLINE-070-CASE-SPEC-001`，`identity_revision`/人格根半句缺载体，不与 090/100 混单）；asserter + `IMPLEMENTATIONS` + manifest 登记为 **M 独占**（新卡 `P0-OFFLINE-090-100-REGISTRATION-001`，逐案提交、量门载荷前后差、证明 `W30`/`p0-core` 仍未晋级）；`OFFLINE-100` 的受控本地 A→B→A 真跑**排在规范卷独占写窗**，前置是判据冻结且 H 当前写卷任务让窗，只用本地隔离服、绝不连用户远程服，没有完整三段证据就一直保持未完成。
- 一条 lane 侧引用错误，M 在复审时一并纠正：草稿把 `asserter_inputs_bytes` 写成 `tools/assert_case_evidence.py:70-88`，真实位置 `:747-763`（`:70-88` 是 import 区）。

### 状态四栏
- 已合入 main：`6495356`（revvis 卡）+ 本节回写。
- 仅在分支、尚未验证：`B1-b`（`b2e9be3`+`a2a93ea`，两处判据修正已在派工中）、`H1d`（未 push、零提交）。
- 真实封证：**本轮零封证**。M 只 `:ro` 读卷，未建 attempt/bundle、未重判任何行；`promotable` 未扩大、`overall.blocks` 未变。
- 尚未验证：`B1-b` 两处判据修正（含其 §2.7/§3.6 反例的运行时那一半）、`H1d` 的活体读数、`P0-OFFLINE-090-100-REGISTRATION-001` 与 `P0-OFFLINE-070-CASE-SPEC-001` 两张新卡（只登记，未开工）。

### 不声称
- 不声称 Minekin 完成；不声称 `OFFLINE-090`/`OFFLINE-100` 已注册或已闭合（卷上仍零 bundle）；不声称 090 的 Dashboard 半句有任何载体；不声称任何门禁点亮（`promotable` 仍 `W00/W10/W20/W60`、`overall.blocks` 仍 `REQUIRED_CASE_NOT_REGISTERED`）。全程未连接、未探测、未读取用户的远程服务器，`.tmp/local-test-server.txt` 未被打开；文中只出现 loopback/受控本地地址、卷名与镜像名。

## M 主控第十一轮（2026-09-27，合并三张卡并坐实卷侧底数）

### 起点核对（先量再写）
- 恢复时远端 `refs/heads/main = f5a7fdae65750cb76a3ddaa44709d4e0e1fdb541`（第十轮补记全量读数那一笔）。
- 三支 lane 分支同时到位：`codex/minekin-h1d-run-rc` 由「无远端 ref、工作树未提交」推进为 `21e0b6c` 并已推；`codex/minekin-offline-090-100` 由 `a2a93ea` 推进为 `b9c40a7`（两处退回件的修正）；新支 `codex/minekin-offline-070` = `9d43de6`，base `f5a7fda`。

### 已合入 main（三笔，逐笔核远端 SHA）
- `e3ca1b7405fbcbfc1c5d5b4ba19faf4abcb556ec` = `H1d`（真实 merge-base `796316a`，恰 3 文件 `+409/-46`：`domain.sh` +105/−32、契约测试 +141/−14、新记录 `docs/validation/v1201-h1d-run-rc-2026-09-27.md` +209）。
- `3a993e0` = `B1-b` 第一阶段的定义草稿（累计对 merge-base `03c1d95` 恰 1 文件 `+521`，全在 `docs/p0-offline-090-100-case-spec-2026-09-27.md`）。
- `24f446f6de9a94784385dda49341a5027513d1a1` = `P0-OFFLINE-070-CASE-SPEC-001` 的定义草稿（恰 1 新文件 `+121`）。远端 `main` 现为该 SHA。

### H1d 的 M 侧独立双审（不照抄 lane 自报）
- 门禁在分支树全 `rc=0`：`bash -n domain.sh`、契约 `24 passed`、`ruff check` / `ruff format --check`（347 files）、`check_boundaries`、`check_case_assertions`（140 registered）、`verify_fixture_digests`、`git diff --check`。
- M 自放两枚反向（在 M 自己的审阅 worktree `../minekin-wt-h1drev`，不碰 lane 树）：
  - 把 supervisor 退回 `'"$@"; :'` ⇒ `test_a_run_that_stops_at_a_named_supply_chain_refusal_exits_non_zero` 红（`2 failed, 22 passed`）；
  - 把 launch 行的 `exec ` 去掉 ⇒ `test_the_launch_depth_reading_travels_on_the_line_that_execs_the_client` 红（同 `2 failed, 22 passed`）；
  - 两条里第二条红都是 M 用 python 写回时 LF→CRLF 触发的 `test_scripts_are_lf_and_keep_an_executable_shebang[domain.sh]`，属**复量工具的形状**、不是本卡缺陷，如实记在这里；两次还原后 `domain.sh` 的 sha256 前缀 `fccf372e6ca5c831` 与审前一致。
- 全量：分支树 `2539 passed, 3 skipped in 371.46s`；合并后 `e3ca1b7` 树 `2540 passed, 3 skipped in 343.73s`（第十轮基线 `2538` + 本卡 2 新测）。
- **M 侧未复量**：lane 的活体容器读数（base 字节 `rc=0` + `BUDGET_UNDECLARED`、新字节 `rc=11`、早停 `rc=2` / 客户端未达 playable `rc=14` 的可分形状），以及它逐字证伪 H1c「JVM 拿到的正是探针那次」的 `XAUTHORITY` 对照（`/tmp/xvfb-run.RZkqh1/Xauthority` vs `/tmp/xvfb-run.tV9Nuz/Xauthority`）。

### B1-b 修正稿复审：两处退回都已落地（因此合入）
- 090：判法钉为**认证字段名/参数名与其值同处出现**，裸 `0` 与空 argv 一律不计泄漏（`offline_session.py:36` `EMPTY_ARGV`、`:71-73`、`:82-84` 实读到 `access_token_argv="0"`）；明写**不从 `asserter-inputs.json` 取凭据字面量**，并把错位引用 `:70-88` 改成 `:747-758`。M 逐条对仓库字节核过：`offline_session.py:10/36/71-73/82-84/166/176-177/247/278-290`、`assert_case_evidence.py:251/282-344/451-454/747-758/1028-1044/2041-2064/3447`、`errors.py:39`（`STORAGE = 12`）、`bundle.py:1-9`（拒封而非脱敏）与 `:255`（`ARTIFACT_DIGEST_MISMATCH:<path>`）、`world_activation.py:11-12/207`，全部属实。父案 `OFFLINE-090` 明写**状态不得为 PASS**，Dashboard 半句只作具名缺口，非门禁子案 `OFFLINE-090-BUNDLE-CARRIERS-001` 只承载日志/崩溃两半；§2.7 给了注入反例（红）与「裸 `0`/空值不得红」的反向对照。
- 100：§3.5 B 被显式降级为「重启那一半，不足以证明整条 A→B→A」，新增 §3.5 C 的 **C1-C5** 恰对应主控钉下的五个条件（同一 `kin_id` 三段唯一 / 三个互异 session / 首尾 A 同一「获确认」world context / B 不串入 A / 外部身份取服务端已注册读数不重推）；「获确认」落到 `(profile_id, revision, level-name)` + `joined the game` + `usercache.json` 的服务端证据，并具名禁止用 `world_context_id` 的 null 相等糊判；§3.6 第 8-11 条给了 triple 级反例（含缺 usercache ⇒ `IDENTITY_NOT_RECORDED`，非绿）。

### 卷侧底数：M 用**正确布局**自测（坐实第十轮那条 glob 更正）
- 真实布局是 `/data/kin/<kin_id>/run/evidence/<run_id>/`，里面有 `manifest.json` + `bundle.sha256` + `bridge-trace.jsonl` + `orchestrator-trace.json` + `run-document.json` + `client/` + `server/`。第十轮 M 猜的 `runs/*/bundle.json`、`attempts/*.json` 都因此回 0。脚本 `.tmp/m-r11-b1b-volume.sh`、日志 `.tmp/m-r11-b1b-volume.log`（`:ro` 容器，`rc=0`）：
  - kin 侧 manifest **94**；OFFLINE 分布 `010:2 / 020:2 / 030:1 / 030-ENUM-ALIGNED-001:2 / 030-PRISM-PARITY-001:2`；**`OFFLINE-070/090/100 = 0 份`**；
  - 声明 crash-report 的 manifest **3** 份，且无一属 OFFLINE 系 ⇒ 「090 的崩溃半句在 OFFLINE 材料上是载体缺席，不是扫过为零」成立；
  - OFFLINE 两份 trace 里带 `world_context_id` 的行 **345**，非 null **0** ⇒ 草稿「禁止拿 null 相等当判据」有实测依据；
  - 每份 OFFLINE bridge-trace 恰**一个**非 null `session_id`（`3d5606ce…`→`6e92b314…`、`f2ecb728…`→`d852ccf0…`，与草稿逐字同值）。
- 与 070 草稿 §6 的互证：全量 `glob(/data/**/manifest.json)` 为 **107**（94 kin + 13 份非 kin 根），attempts 表 **71** 行——第八轮底数一字未动。

### 门读数（第十一轮的「登记前」底数，`:ro` 容器在 `24f446f` 树上）
- `.tmp/m-r11-payload.sh` / `.log`：`report_rc=1`；门载荷子集 `{work_packages, overall}` 仍 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`（三笔合并一字未动）；`overall.blocks = ['REQUIRED_CASE_NOT_REGISTERED']`；**`W30.promotable False`、`W30.blocks = ['NO_MANDATORY_CASES', 'REQUIRED_CASE_NOT_REGISTERED']`**；报告顶层键含 `visibility_gaps`（id `ORCHESTRATOR_REVISION_NOT_PINNED`）。登记卡落地后必须与这两枚读数逐字对比，并具名证明 `W30` 与 `p0-core` 仍未晋级。

### 排期与让窗
- 主干 `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（本轮收三笔）。
- M 自己的 `P0-OFFLINE-090-100-REGISTRATION-001` 由 `QUEUED` 提升为 **`NEXT`**（判据已冻结；`tools/assert_case_evidence.py` + `tools/check_case_assertions.py` 的 `IMPLEMENTATIONS` + `tests/fixtures/cases/**` + `manifest.sha256` 由 M 逐案两笔实施，不翻 `mandatory`、不动 registry `status/gaps`）。
- 新立 `P0-OFFLINE-100-A-B-A-RUN-001`（`QUEUED`，E 的规范卷独占写窗）：受控**本地隔离服**真跑，前置=登记卡落地 + H 让窗（`H1d` 已闭环 ⇒ 让窗成立）；三段证据不齐保持未完成。
- H lane 现无 `lane_next`，等 M 另立；V lane 仍停等具名；`OFFLINE-070` 的登记留作 M 的又一张卡。

### 四态
- 已合入 main：`e3ca1b7`（H1d）、`3a993e0`（B1-b 定义）、`24f446f`（070 定义）；远端 `main = 24f446f6de9a94784385dda49341a5027513d1a1` 已核。
- 仅在分支：无（三支都已并入）。
- 真实封证：本轮**零新增**——H1d 全程未挂规范卷，两张定义卡只 `:ro` 读取，未建 attempt、未封 bundle。
- 尚未验证：H1d 的活体容器读数（M 侧未复量）、090/100/070 全部反例与阳性对照的运行时那一半、登记后门载荷的位移、端到端 1.20.1 auto JOIN。

### 不声称
- 不声称 `OFFLINE-090`/`OFFLINE-100`/`OFFLINE-070` 已注册或已闭合；不声称 090 的 Dashboard 半句有任何载体；不声称 A→B→A 有任何三段证据；不声称任何门禁点亮；不声称 Minekin 完成。
（以上属第十一轮的陈述；本轮 090/100 **已注册**，其「未闭合」结论不变，见下一节。）

## M 主控第十二轮（2026-09-27，M 独占实施 090/100 的登记，逐案两笔）

### 落干与远端核对
- `OFFLINE-090` = M 的直接提交 `11f5ea0`（5 文件 `+648`：`tools/assert_case_evidence.py` `+320`、`tools/check_case_assertions.py` `+10`、`tests/fixtures/cases/offline-090.json` 新建、`tests/fixtures/manifest.sha256` 一行、`tests/unit/test_case_evidence_assertions.py` `+302`）。
- `OFFLINE-100` = M 的直接提交 `2e6711f`（5 文件 `+562 -1`，同五个面）。
- 推送后 `git -c credential.helper= -c credential.helper=wincred ls-remote origin refs/heads/main` = **`2e6711f01a41dab5e2eb8ecbcdb68e4b92331599`**（推送前为父提交 `11f5ea07f0b47d988e890d837c9627daa55224c7`，即远端未被他人推进）。

### 090 的登记形状（按第十一轮冻结的 §2.5）
- 判据是**带字段/参数上下文的认证正文暴露**：`_FIELD_ALTERNATION` 名字与值同处出现才算。裸 `0`（离线哨兵，公开非秘密）与空 argv 一律不计泄漏；认证字段仍统一脱敏。
- JSON 载体捕获取 `[^"\\]*`。M 在提交前量到 8 条红，根因正是贪婪版 `[^"]*` 会把转义 payload 的闭合 `\"` 吞进捕获、连带行内余下花括号，把一条干净的分类标签报成凭据；Dashboard 一侧的反例夹具也改成真实参数形状 `--xuid "<正文>"` 而非散文。
- `asserter-inputs.json` **不携带** token/xuid/clientId（键恰为 `schema_version/kin_id/run_id/username/previous_run_id`），判法不从中取值。
- **整条不得 PASS 由代码保证**：父案 fixture 持两句，`auth_field_bodies_are_not_exposed_on_the_dashboard` 在无 `dashboard/` 载体时恒答具名 `DASHBOARD_CARRIER_NOT_SEALED` ⇒ 该行判 `FAIL` 且只 obs 两句之一。E 草稿里那个非门禁子案 id `OFFLINE-090-BUNDLE-CARRIERS-001` **未创建**：新 case id 要动 `src/minekin_core/domain/cases.py`（出本卡面，且属主控保留的 id 拆分口径，如 ADMIT-030/050 的先例），而主控的原条件是「必要时拆」——父案以 FAIL 形态保留缺口已满足该条件，故本轮不拆。若日后要拆，由主控先批准 id 面。

### 100 的登记形状（按 §3.5 C1-C5，可判的落在 pair 级）
- 四条注册名：`the_kin_id_continues_from_the_previous_run`、`the_session_is_not_the_one_the_previous_run_had`、`the_world_and_the_identity_are_the_server_s_record`、`the_world_switch_returned_to_the_confirmed_world`。
- 前三条在「本 bundle + 已封的 `previous-run-trace.jsonl`」上可判；服务端那半句读 `trusted/server-profile.json` + `server/server.properties` 的 `level-name` + `server.log` 的 `Preparing level "<name>"` 三者一致，UUID 与加入句**委托已注册的 `server_observed_join_identity`**，不重推规则。
- 第四条恒答 `A_B_A_TRIPLE_NOT_SEALED`：一个 `RunMaterial` 只属一次 run，三段链无封存载体，补载体 = 扩展 `minekin.p0.evidence.v1`（主控保留、且会重封全卷）；`world_context_id` 在卷上 345 行全 null，禁止拿 null 相等糊判。
- 测试面（22 条新测）：三条 pair 级判据绿；**「绿 pair 不是闭合行」**（`result == FAIL`、failures 恰为那条具名 gap）；14 条单字段反例逐条点名该红的判据；非空洞性对照（本 run 独有的外来 `session_id` 仍绿、`generation` 复用而 session 不同仍绿）；首 run ⇒ `PREVIOUS_IS_FIRST_RUN` 而非重启判决；声称有前一条却无行 ⇒ 两条判据同报 `PREVIOUS_TRACE_NOT_SEALED`（M 实施中被测试抓到的一处真实缺陷：原本空 session 集会让互斥判据**空洞地**变绿，已补 `PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION` 形状的拒答）。
- `the_world_switch_returned_to_the_confirmed_world` 的断言名与 fixture 顺序按契约句排列，fixture `tests/fixtures/cases/offline-100.json` LF 摘要 `96d4b186e09e97f4965f4dbf41999e5f59cbecac2ef5b0ccf8fc28910f096b27` 已入 `tests/fixtures/manifest.sha256`（紧接 offline-090 行，`git diff --stat` = 1 insertion）。
- **E 草稿与落地之间的一处具名分叉**：`docs/p0-offline-090-100-case-spec-2026-09-27.md` §3.1 的拟议 manifest 只有两个断言名（`the_kin_id_continues_from_the_previous_run` + `the_external_identity_and_world_context_do_not_cross_runs`）。主干落地的形状是把 E 自己在 §3.5 B/C 里拆开的条件按可判性分成**三条 pair 级判据 + 一条恒拒的三段缺口**：E 的第二名同时含「服务端自记身份」与「session/world 不串线」两件事，而 world 那半件在 pair 级没有可读的三段载体，保留为一个名字就会让它在 bundle 上要么空洞地绿、要么把可判的那半也拖成缺口。E 那份定义文档属 E 的卡面，M 不代其改写；此处具名记录分叉，后续 070/100 的读法以主干 fixture 与 `check_case_assertions.py` 为准。

### 门载荷的三段读数（`:ro` 容器，`report_promotion.py --data-root /data`，`report_rc=1` 属正常拒晋级）
- 登记前（第十一轮底数）：`fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`。
- 090 注册后：`eb4e76eb…`，`W30.requirement.absent` 5→4。
- 100 注册后：**`76fb9bdb314b59ca87aaf8077e8b579e6593bae9de39fc7273ef14634dc3ca47`**，`W30.absent` 4→3 = `OFFLINE-060/070/080`、`W30.non_mandatory` 9→10（含 `OFFLINE-090`、`OFFLINE-100`）、`p0-core.absent` 11→10；**`W30.promotable False`**（blocks 仍 `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、**`p0-core.promotable False`**、`overall.blocks` 仍只有 `REQUIRED_CASE_NOT_REGISTERED`。日志 `.tmp/m-r12-payload-after-100.log`。差异集合恰等于「这两个 id 从 absent 名单离场」所能造成的改动，无第三项。
- 摘要无漂移的正对照：`uv run --frozen python tools/check_case_assertions.py` ⇒ `Case assertion implementations: OK (146 registered)`、`rc=0`；`--record` 只移动 `offline-100.json` 一个文件 ⇒ 没有任何已注册判据的摘要被这两笔改动，也就没有已封 bundle 被判为失效（090/100 卷上本就 0 份 bundle）。
- 全量：`uv run --frozen pytest -q` ⇒ **`2576 passed, 3 skipped in 292.86s`**。收集数逐笔核过：090 那笔 `+14`（8 个函数 + 6 行 `EXPOSURE_COUNTEREXAMPLES` 参数化），100 那笔 `+22`（8 个函数 + 14 行 `PAIR_COUNTEREXAMPLES`），两笔之差恰等于第十一轮记录在案的 `2540` 与本数之差 ⇒ 除这两笔外没有其它测试面移动；`tests/unit/test_case_evidence_assertions.py` 单文件现 `472 passed`。`ruff format --diff` 32 files already formatted、`ruff check` All checks passed。

### lane_next 现状
- 主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻，本轮没有被"完成"）。
- M = `P0-OFFLINE-090-100-REGISTRATION-001` **已闭环**；M 的下一张是新立的 **`P0-OFFLINE-070-REGISTRATION-001`**（`QUEUED`，§4 同名行；不与 090/100 混单，且其 `identity_revision`/人格根半句缺载体，属主控保留的那条决定 ⇒ 该卡只登记可判半句 + 具名缺口）。同一轮里 M 按仓库字节改正了主干对 070 载体枚举名的错引（`..._DUPLICATE_LOGGED` 不存在 ⇒ `ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN`，`bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:435`）。
- E = `P0-OFFLINE-100-A-B-A-RUN-001`（`QUEUED`）：判据冻结前置已由 `2e6711f` 满足、`H1d` 已闭环 ⇒ 写窗条件成立；受控**本地隔离服**真跑，绝不连用户远程服；跑出三段也只是给主控裁决提供字节，不会让那条 gap 判据自行变绿。
- H lane 仍无 `lane_next`（等 M 另立）；V/S/D 停等其前置。

### 四态
- 已合入 main：`11f5ea0`（OFFLINE-090 登记）、`2e6711f`（OFFLINE-100 登记）；远端 `main = 2e6711f01a41dab5e2eb8ecbcdb68e4b92331599` 已核。
- 仅在分支：无新增（本轮两笔都是 M 直接在主干面上施工，未开分支）。
- 真实封证：**零新增** —— 全程规范卷 `:ro`，未建 attempt、未封 bundle；090/100 的卷上 bundle 数仍为 **0**。
- 尚未验证：两案全部反例在**真实 run 字节**上的那一半（仓库夹具已覆盖，运行时未测）；`P0-OFFLINE-100-A-B-A-RUN-001` 的三段真跑；端到端 1.20.1 auto JOIN；`OFFLINE-070` 的登记。

### 不声称
- 不声称 `OFFLINE-090` 或 `OFFLINE-100` 已闭合：090 的父案按构造只能是 FAIL（Dashboard 半句无载体），100 的 A→B→A 半句恒答具名缺口；非 mandatory 登记不表示任何一行已被真跑证明。
- 不声称卷上存在 090/100 的 bundle、三段链证据或 `world_context_id` 读数。
- 不声称任何门禁点亮（`W30` 与 `p0-core` 实测仍 `promotable False`）。
- 不声称 Minekin 完成。

## M 主控第十三轮（2026-09-27，M 独占登记 OFFLINE-070，一笔入干）

### 落干与远端核对
- 起点：`main` = 远端 `main` = `0e497a9f951c7704c81ee807c7ef646b94e4b7fe`（推送前 `git ls-remote` 同值 ⇒ 远端未被他人推进）。
- 本卡一笔：`OFFLINE-070` 登记 = M 直接提交 **`31cf9c3`**（5 文件 `+407 -2`：`tools/assert_case_evidence.py` `+126`、`tools/check_case_assertions.py` `+15`、`tests/fixtures/cases/offline-070.json` 新建 19 行、`tests/fixtures/manifest.sha256` 一行、`tests/unit/test_case_evidence_assertions.py` `+246 -2`）。
- 推送后 `git -c credential.helper= -c credential.helper=wincred ls-remote origin refs/heads/main` = **`31cf9c3a8aa91cf6b26cc518a4e099694d46fe84`**（已核）。
- 提交信息最初少了主题与正文之间的空行（整条被 `git log %s` 读成主题）。推送前只改信息、不改内容：`git commit --amend -F`，树摘要前后都是 **`ffcf1bda89320a99d75b522ebc440a9ae07edd28`** ⇒ 改动只落在提交信息上。

### 070 的登记形状（按 E 的冻结草稿 `docs/p0-offline-070-case-spec-2026-09-27.md`）
- 四条注册名，按可判性分两类。**有载体的只有一条**：`the_conflict_was_classified_as_duplicate_login` 要 `SessionInterrupted{phase: FAILED, reason: ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN}` **成对**出现——phase 单独会把掉线算成拒绝登录，reason 单独会把 Core 记在他处的拒绝算进来；服务端原句按契约不进产品事件，所以能过界的只有分类名。缺 `reason` 的行具名答 `ADMISSION_EVENT_UNCLASSIFIED`，而不是被循环跳过（那是另一种、更弱的陈述）。
- 三条恒拒的名缺口的仓库证据逐条量过（不是回忆）：`a_renamed_or_recased_login_is_not_called_a_duplicate` ⇒ `CONFLICT_CATEGORY_HAS_NO_RENAME_ENTRY`（`AdmissionFailureReason` 的臂名解析后无 RENAME/RECASE/CASE/ALIAS，且 Java 一个 arm 把两句 vanilla 文案折成同一分类；离线 UUID 是 `"OfflinePlayer:" + name` 的 MD5 ⇒ 改大小写对 vanilla 是另一个身份，不是同一身份的第二次登录）；`the_conflict_opened_a_new_identity_revision` ⇒ `IDENTITY_REVISION_HAS_NO_CHANGE_CARRIER`（`cli/init.py:77` 写常量、`identity_store.py` 只有 INSERT/SELECT、`schema.sql:93` 只 `CHECK >= 1`、`src/**` 里同时含 `update` 与 `identity_revision` 的语句 grep **rc=1**，且 sealed 输入键集恰为 `schema_version/kin_id/run_id/username/previous_run_id`）；`the_identity_root_was_not_merged` ⇒ `IDENTITY_ROOT_MERGE_HAS_NO_SEALED_CARRIER`（`create_identity_root` 的「已有一行即拒」是**码级护栏**、不是 run 记录；bundle 的 identity 段只有两个分类字符串）。
- **整条不得 PASS 由代码保证**：那三条无载体判据恒返字符串 ⇒ 一次「分类完美」的冲突 run 仍判 `FAIL`，`observed` 恰含那一条可判项、`failures` 恰为三条具名缺口（`test_a_perfectly_classified_conflict_still_cannot_close_the_row`）。非 mandatory 登记因此不会被读成闭合，形状与 090 的 `DASHBOARD_CARRIER_NOT_SEALED` 同类。
- **与 E 草稿的两处具名分叉**（E 那份定义文档属 E 的卡面，M 不代其改写；此处双向记名，后续读法以主干 fixture 与 `check_case_assertions.py` 为准）：① E 草稿只点了两个断言名，主干按契约句「同名双登录、改名、大小写变化 / 冲突·新revision分类正确 / 不合并人格根」落成**四个**名字（`a_renamed_or_recased_login_is_not_called_a_duplicate`、`the_identity_root_was_not_merged` 是主干补的名）；② E 的 revision 名 `the_conflict_opened_a_new_revision`（预想反例「`identity_revision` 仍等旧值 ⇒ `REVISION_NOT_ADVANCED`）在主干改成 `the_conflict_opened_a_new_identity_revision` 且**恒拒**——E 的反例预设有一列可读的 revision 数字，实测该产品从不写第二值，按那条写法会把「无载体」误判成「测过且没升」，所以注册成缺口而不是实现一个永远读不到数的判据。

### 反证与还原（本轮把"红线不是装饰"量了两遍）
- 自我释放反证 #1：把可判条的缺失分支改为空洞放行 ⇒ 该文件 **2 条测红**；自我释放反证 #2：把分类等值判断削弱为只看 phase ⇒ **3 条测红**。两次都按具名行核对后还原。
- 还原方式记一次教训：#1 用 `git checkout -- tools/assert_case_evidence.py` 撤「故意改坏」，连带把**未提交**的整段 070 新代码一起丢弃，靠本轮早些时候存下的 `git diff`（`.tmp/m-r13-070-neutered.diff`）`git apply` 复原并 Edit 回两处被削分支。复原是否等于原物不靠肉眼：`check_case_assertions.py` ⇒ `OK (150 registered)`、该测试文件 487 全绿、文件 sha256 前缀 **`e0f196a3c5b88814`** 与记录一致。#2 因此改为先 `cp` 到 `.tmp/m-r13-asserter-backup.py` 再动工作树，前后 sha256 同值。
- 非空洞性正对照：一份只有外来 `FAILED` 行（别的分类）的账本不把重复登录答成已分类；`NO_ADMISSION_EVENT_RECORDED` 与 `ADMISSION_EVENT_UNCLASSIFIED` 是两种具名读法，不共用一条沉默。

### 门载荷第四段读数（`:ro` 容器，`report_promotion.py --data-root /data`，`report_rc=1` 属正常拒晋级）
- 登记前（第十二轮尾底数）：`76fb9bdb314b59ca87aaf8077e8b579e6593bae9de39fc7273ef14634dc3ca47`。
- 070 注册后：**`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**（日志 `.tmp/m-r13-payload-after-070.log`）。
- 逐项：`W30.requirement.absent` 3→**2** = `OFFLINE-060 / OFFLINE-080`；`W30.non_mandatory` 10→**11**（含 `OFFLINE-070`）；`W30.misattributed` **0**；**`W30.promotable False`**、blocks 仍 `['NO_MANDATORY_CASES', 'REQUIRED_CASE_NOT_REGISTERED']`；`p0-core.absent` 10→**9**、`non_mandatory` 23→**24**、`misattributed 0`、**`p0-core.promotable False`**、blocks 仍只有 `REQUIRED_CASE_NOT_REGISTERED`。⇒ 070 的登记把「缺席」挪成「已登记未闭合」，没有点亮任何东西；差异集合恰等于 070 离场所能造成的改动，无第三项。
- 摘要无漂移的正对照：`uv run --frozen python tools/check_case_assertions.py` ⇒ **`OK (150 registered)`**（登记前 146）；`--record` 只移动 `offline-070.json` 一个文件 ⇒ 没有已注册判据的摘要被改动，也就没有已封 bundle 被判失效（070 卷上本就 0 份）。
- 全量：`uv run --frozen pytest -q` ⇒ **`2591 passed, 3 skipped in 422.06s`**（第十二轮为 `2576`，差 **15** 恰等于本卡新增测数：8 条单字段反例参数化 + 6 个函数 + 1 条 registration 形状测 ⇒ 除本卡外没有其它测试面移动）；`tests/unit/test_case_evidence_assertions.py` 单文件 **487 passed**（前为 472）。`ruff format --check` 3 files already formatted、`ruff check` All checks passed、`tools/verify_fixture_digests.py` ⇒ `W00 schema and fixture digests: OK`、`tools/check_boundaries.py` rc=0、`bash -n test-orchestrator/runner/domain.sh` rc=0、`git diff --check` rc=0。
- `tests/fixtures/cases/offline-070.json` 的 LF 摘要 **`7325aa39f2c7edc0c771a8e3709f7ddf021e4b90c4973ee77e171a7b8a8550be`** 已入 `tests/fixtures/manifest.sha256`（紧接在 090 行之前，diff = 1 insertion）。

### lane_next 现状
- 主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻，本轮没有被"完成"）。
- M = **`P0-OFFLINE-070-REGISTRATION-001` 已闭环**（§4 同名行已改写）。M 名下已无可安全自排的卡：090/100/070 三案的剩余半句全部卡在主控保留的载体/词汇决定上（Dashboard 载体、三段链载体、`identity_revision` 变更事件、身份根工件、改名分类），下一步是**收 E 与 H 的分支**而非再开 M 卡。
- E = `P0-OFFLINE-100-A-B-A-RUN-001`（施工中）：`minekin-wt-evidence` 工作树 `0e497a9`、无未提交改动 ⇒ 其本轮动作在卷上（封存窗内），尚未回报。
- H = `H1e`（`XDG_RUNTIME_DIR` 提供，施工中）：`minekin-wt-client-env` 工作树 `0e497a9` 带未提交的 `test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py` ⇒ 尚未 commit/push，也未回报。按在案的次序规则，**H1e 不在 E 的三段报告落地前合入 main**。
- V/S/D 仍停等其前置；两张 lane 卡派出的子代理截至本节撰写均未回报（其一日志在本轮 06:34 仍在写入）。

### 四态
- 已合入 main：`31cf9c3`（OFFLINE-070 登记）；远端 `main = 31cf9c3a8aa91cf6b26cc518a4e099694d46fe84` 已核。
- 仅在分支：无新增。E 与 H 的两张卡仍在各自工作树里（H 有未提交改动、E 无），M 未代其 commit。
- 真实封证：**零新增** —— 全程规范卷 `:ro`，未建 attempt、未封 bundle；070/090/100 的卷上 bundle 数仍为 **0**。
- 尚未验证：070 那条可判据在**真实冲突 run 字节**上的那一半（夹具覆盖 8 条反例，运行时未测；070 卷上 0 份 bundle）；`P0-OFFLINE-100-A-B-A-RUN-001` 的三段真跑；`H1e` 的客户端运行时目录读数；端到端 1.20.1 auto JOIN。

### 不声称
- 不声称 `OFFLINE-070` 已闭合：它按构造只能是 FAIL（三条恒拒缺口），非 mandatory 登记只把「缺席」挪成「已登记未闭合」。
- 不声称卷上存在 070 的 bundle、`identity_revision` 读数或身份根工件；也不声称改名/大小写能被今天的分类词表区分。
- 不声称任何门禁点亮（`W30` 与 `p0-core` 实测仍 `promotable False`）。
- 不声称 Minekin 完成。

## M 主控第十四轮（2026-09-27，修 100 的设计口径 + 收 E 的三段真跑 + 收 H1e）

### 落干与远端核对（次序即结论）
- 起点：`main` = 远端 `main` = `d4d44b63c2d9465392bf0fd521edb8af9cb1fcc7`（第十三轮尾）。本轮开工前 `git ls-remote` 同值 ⇒ 远端未被他人推进。
- 本轮主干三笔，按此顺序：
  1. **`91ebd6c`**（M 直接一笔，`docs/p0-offline-090-100-case-spec-2026-09-27.md` 1 文件 `+58 -13`）= 主控目标第 2 条的「先修设计和反例」。推送后远端 `main = 91ebd6cad6fdfccf57886bef42b039ebb87961ed`（已核）。
  2. **`318d1b9`** = 合并 `origin/codex/minekin-evidence`（E 的 `a42450c` + `7f75dab`）。
  3. **`639cedb`** = 合并 `origin/codex/minekin-client-env-readout`（H 的 `0b820e0` + `743765e`）。
- **H1e 在 E 之后**不是偏好而是在案的次序规则：两张卡会同时改主干 §4 行与卷底数，先合谁决定那份读数挂在谁名下。E 的报告落成 `318d1b9` 之后该条件才成立。

### 100 的设计修正：C4 的字面 scope 是一枚永红的判据（不是执行缺陷）
- 缺陷：冻结草稿 §3.5 C/C4 要求「B 的 session 不出现在 A1、A2 的**时间线或载体对**里」。bundle 的载体对里封的 `previous-run-trace.jsonl` 按装修录**必然**是前驱那次 run 的时间线，而 A2 的前驱就是 B ⇒ 该字面要求对任何诚实执行都自相矛盾。卷上原样读数（`readout.log` 第 239-242 行）：A2 `7ff026e4…` 的 `previous_timeline.sessions = ["4ba0825eee234506bcdca524d1631df9"]`，即 B `a26e2c35…` 自己的 session。
- 修法是**收窄口径而不是删判据**：C4 现在写作「B 的 session 集与获确认 context tuple 不出现在 A1、A2 **各自自身** timeline 中，且 A 的 tuple ≠ B 的，A1|B 与 B|A2 的 pairwise 互斥都须成立」；具名 `B_CROSSES_INTO_A` 不变。可判形状与 E 那半句「正确的可判形状」一致，两处的度量都指向同一批已封字节。
- 同时改掉的三处现状陈述（按仓库口径：dated 读数保留、只改现在时）：§3.5 末段与 §3.6 的「三段尚未存在 / C1-C5 反证全部 design-only 未测」，改为「首次受控三段已存在」+ 具名 run_id/digest/读数；反例头注明 9/10/11 仍未测、**8 只算了前半**（E 实量的是单字段 `level-name → OTHERWORLD`，不是「搬到 B 的真实世界」那个变体）。
- **不移动任何摘要**：`case_version` 取的是注册函数字节 + fixture，不含这份文档 ⇒ 登记数仍 `OK (150 registered)`、`verify_fixture_digests OK`、卷上 5 份 OFFLINE-100 bundle 无需重封。该笔推送后门载荷实测 `cfa0f118…` 一字未变（见下）。

### §3.5 的 C1-C5 ↔ 主干注册名映射（此前无人写死，读法会糊）

| 设计条款（文档名，不注册） | 主干注册判据（进 `case_version`） | 今天能判什么 |
| --- | --- | --- |
| C1 `the_kin_id_is_single_across_the_triple` | `the_kin_id_continues_from_the_previous_run` | 逐对（A1|热身、B|A1、A2|B）续接；三段传递单值靠三段 bundle 的人工并读，链上无单一判据 |
| C2 `the_triple_runs_as_three_distinct_sessions` | `the_session_is_not_the_one_the_previous_run_had` | 相邻对互斥；三值两两互异 = 人工并读（本轮已由 M 复量：`f0a28733…`／`4ba0825e…`／`ed3fdc06…`） |
| C3 `the_two_a_runs_share_one_confirmed_world_context` | `the_world_and_the_identity_are_the_server_s_record` + `the_world_switch_returned_to_the_confirmed_world` | 前半：每份 bundle 内 profile digest / `level-name` / `Preparing level` / 服务端自记身份一致；后半恒答 `A_B_A_TRIPLE_NOT_SEALED`——跨 bundle 的「同一获确认 context」无载体（`world_context_id` 全卷 null） |
| C4 `the_b_run_does_not_cross_into_a` | `the_session_is_not_the_one_the_previous_run_had`（两对）+ 同上缺口 | 自身 timeline 互斥与 tuple 不等可判；「载体对不含 B」按构造不可判，本轮已把口径收到前者 |
| C5 `the_external_identity_is_server_observed_in_all_three` | `the_world_and_the_identity_are_the_server_s_record` | 三份 bundle 各判各的服务端自记（`usercache.json` + `joined the game`），`offline_player_uuid` 规则**委托**已注册的 `server_observed_join_identity`，不重推 |

⇒ 结论形状：**C1/C2/C5 与 C4（收窄后）在卷上可判且已复量；C3 只有 bundle 内那一半，三段那一半仍缺载体。** 这不是「判据太弱」，而是父行 `the_world_switch_returned_to_the_confirmed_world` 恒拒的原因，仍归主控对 `minekin.p0.evidence.v1` 的保留决定。

### E 的 `P0-OFFLINE-100-A-B-A-RUN-001` 双审（真实封证在卷上，M 未写卷）
- 增量按真实 merge-base 量：`0e497a9..origin/codex/minekin-evidence` = 2 笔（`a42450c`、`7f75dab`）、改面恰 1 文件 `docs/p0-offline-100-a-b-a-run-2026-09-27.md` `+259`。`tools/**`、`tests/fixtures/**`、registry、判据、门禁、`minekin.p0.evidence.v1` 字段一字未动（E 未 rebase，其分支读 `OK (146 registered)` 属 base 差异，非缺陷）。
- 卡面四条边界逐条核：① 本地隔离服、全程未连用户远程服（文档只出现卷名/镜像名/loopback，无 IP:port）；② 三段齐备且**失败材料保留**——seq1/seq2 两份 `HANDSHAKE_TIMEOUT` FAIL bundle 与热身 run 的台账行原样在卷，5 行 attempts 全 `SEALED`，无删除、无伪装 supersede；③ 逐条 C1-C5 具名到 run_id 与字段；④ 未声称闭合，父行失败名 `A_B_A_TRIPLE_NOT_SEALED` 原样引。
- **一轮退回**：首版 §C4 写「成立」，与它自己引的载体行矛盾。M 按字节退回（不是按文风），E 以新提交 `7f75dab` 改判「部分成立」并把口径缺陷登记给主控（未 amend 已推的 `a42450c`）。
- M 侧独立复量（`minekin-wt-integration` 树、规范卷 `:ro`、日志 `.tmp/m-r14-rejudge-triple.log`）：三份 `evidence verify` 均 `verified: true / sealed: true / artifacts: 13 / violations: []`（`result: FAIL` 是被验的 verdict）；三份 `rejudge_evidence.py` 均 `status=agrees disagreements=[]`，`case_version = a44289e8cdbc0643eebb7ff73985014a8fb87e176c622fd2a1c085f7abcc8a3b`。⇒ 这一条同时把「登记会不会让已封 bundle 失效」从推断升成实测：OFFLINE-070 那四个新函数已在这条主干字节上，三段仍产出 bundle 自记的同一 verdict。
- 卷底数（E 记录 + M 复量一致）：`bundles 99 / attempts 76 / server-runs 184`；`kin-e-aba` 的账本邻接 6 段无 `run_id` 重叠。

### H1e 双审：给了运行时目录，但没越过 Core 的封闭名单
- 增量：`0e497a9..origin/codex/minekin-client-env-readout` = 2 笔、3 文件 `+548 -10`（`test-orchestrator/runner/domain.sh` `+140 -1`、`tests/contract/test_runner_scripts.py` `+269 -9`、H 自己的记录 `+194`）。`de579ad` 是 `743765e` 的祖先 ⇒ 该分支为正常前进推送，无强推。
- H 的契约测试只读文本，函数分支无人独立跑过 ⇒ M 的行为探针（`.tmp/m-r14-h1e-probe.sh`，容器内驱动真函数七态）：unset / 空 / 相对路径 / 不存在 / 不可写（用 `:ro` 绑挂造，root 也读到 `-w` 为假）五种都不合格 ⇒ 建 `/tmp/.../runtime.XXXXXX` 且 `stat` 实测 **700**、origin = `provided-by-harness`；可用目录那态 `inherited` 且值不被换；base 建不出来时两字段皆空并具名原因；`set -u` 下空数组展开 rc=0（旧坑不复活）。
- **核心自限按产品字节证实**：`src/minekin_core/config.py:51` 的 `FORWARDED_VARIABLES` 只有 `DISPLAY` / `XAUTHORITY` / 桥的三个诊断名，**无 `XDG_RUNTIME_DIR`**，而 `forwarded_environment()` 只白名单转发 ⇒ 目录停在 Core 门口，**活体 JOIN 不会因 H1e 变绿**；最后一跳属 `src/**` 产品面（另卡，且改名单是产品决定）。
- **一轮退回（文档口径，非代码）**：H 首版 §6 把全量写成 `2579 passed` 无红，而它自己引的首跑日志是 `1 failed, 2578 passed, 3 skipped in 489.80s`（红在 `tests/unit/test_session_supervision.py:141 TimeoutError`）。按「修复 = 改动真落地」退回后：H 重跑全量得 `2579 passed, 3 skipped in 412.20s`，两份日志都留在 `.tmp/` 并在 §6 逐字并列；另顺手修掉两处它自己核出的偏差（契约格 `0.08s` → 实读 `27 passed in 0.10s`；改面总量按 numstat 更正）。M 侧对该 TimeoutError 另有两枚独立证据：合并树 `3f85fc0` 全量绿、主干 `d4d44b6` 单跑三次 `22 passed` ⇒ 归类为满载负载敏感，非回归。
- 合并树（`639cedb`）复量：`bash -n domain.sh` rc=0、`ruff format --check`（352 files already formatted）、`ruff check`、`check_case_assertions OK (150 registered)`、`verify_fixture_digests OK`、`check_boundaries OK`、`git diff --check` rc=0，全量 **`2594 passed, 3 skipped in 331.11s`**（第十三轮为 `2591`，差 **3** 恰等于 H1e 新增的三条契约测试 ⇒ 除本笔外无其它测试面移动）。

### 门载荷第五段读数：真跑封证与两次合并都没动门
- E 封存后与本轮两次合并后各读一次（`:ro` 容器、同一 `report_promotion.py --data-root /data`，日志 `.tmp/m-r14-payload-after-abar.log`、`.tmp/m-r14-payload-after-merges.log`）：子集摘要两次都 **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**（与第十三轮尾一字相同）；`report_rc=1`；**`W30.promotable False`**（blocks `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、**`p0-core.promotable False`**（blocks 仍只有 `REQUIRED_CASE_NOT_REGISTERED`）；`W30.absent` 仍 2 = `OFFLINE-060 / OFFLINE-080`、`non_mandatory` 仍 11（含 070/090/100）、`misattributed 0`。
- 为什么这是量出来的而不是类推：OFFLINE-100 现在卷上有 5 份 `SEALED` bundle（含 3 份真三段），若那条恒拒判据能被 bundle 满足，`overall.blocks` 或 `non_mandatory` 行的形状必然变动。读数一字未变 ⇒ 「真实封证 ≠ 门变动」在 100 上第二次成立（第一次是 070 注册轮零封证）。

### 本轮登记给主控的两条保留决定（只命名，不实施）
1. **`src/minekin_core/config.py:51` 的 `FORWARDED_VARIABLES`**：要不要把 `XDG_RUNTIME_DIR` 放进被管客户端的转发名单，是产品面决定（H1e 只到启动线为止）。放开 = 客户端 JVM 环境可观察形状改变，需另卡并配活体读数。
2. **`A_B_A_TRIPLE_NOT_SEALED` 这枚名字**：三段链载体要么扩 `minekin.p0.evidence.v1`（重封全卷）、要么把三段材料并成一份新封存工件（同一后果）。**改名本身也会动 `case_version`** ⇒ 会立刻让卷上 5 份 OFFLINE-100 bundle 被判失效。本轮既不改名也不补载体，父行按构造继续 FAIL。

### lane_next 现状
- 主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`（常驻；本轮收掉两张 lane 分支，但该门不因收卡而「完成」）。
- E = `P0-OFFLINE-100-A-B-A-RUN-001` **已收卡并入主干**（`318d1b9`）。E 的 `lane_next` 回到 B2 剩余范围；090 侧的受控真跑是 E 可提的下一张（需先立卡，不在本轮自派）。
- H = `H1e` **已收卡并入主干**（`639cedb`）。H 名下无可安全自派的下一张：1.20.1 加入者起跳面（V 停等的第 4 格阻断）需要 H 面新卡，而它的前置——活体 JOIN 的判定面——仍卡在上面那条 `FORWARDED_VARIABLES` 决定上。
- M 名下仍无安全自排卡：090/100/070 的剩余半句全在主控保留的载体/词汇决定上。V/S/D 停等其前置。

### 四态
- 已合入 main：`91ebd6c`（100 的设计与反例口径修正）、`318d1b9`（E 的三段记录）、`639cedb`（H1e 的编排脚本 + 契约测试 + 记录），本节的回写再随下一笔入干；每笔推送后 `git ls-remote origin refs/heads/main` 与本地值对账，`91ebd6c` 推送后远端已核到 `91ebd6cad6fdfccf57886bef42b039ebb87961ed`。
- 仅在分支：无新增。E 支 `7f75dab`、H 支 `743765e` 的内容都随本轮两次合并进干，两支不再有未合提交。
- 真实封证：**卷上三份新 `SEALED` 三段 bundle 是 E 在写窗内跑出来的**（A1 `670aec0b…` / B `0314121c…` / A2 `0cc1fb99…`，加两份早期 `HANDSHAKE_TIMEOUT` FAIL），M 全程 `:ro` 只读复量、**未新封任何 bundle**、未建 attempt。OFFLINE-070/090 卷上 bundle 仍 **0**。
- 尚未验证：三段链的跨 bundle 判据（无载体）；`world_context_id` 的链上真值（全卷 null）；设计反例 9/10/11 与「搬到 B 的真实世界」变体；OFFLINE-090 的受控真跑与 Dashboard 半句；H1e 之后活体 JOIN 与 `[0x1000E]` 是否消失（归 V，且 M 未复量 V 侧任何活体读数）；端到端 1.20.1 auto JOIN。

### 不声称
- 不声称 `OFFLINE-100` 已闭合：三段字节 + 人工读数 ≠ 注册判据变绿，父行实测仍 `FAIL / A_B_A_TRIPLE_NOT_SEALED`。
- 不声称 C3 的「首尾 A 同一获确认 context」已被链上证据满足——今天有的只是 `server_config_digest` + `level-name` + `Preparing level` 这组旁证，拿 null 的 `world_context_id` 相等糊判被规范明文禁止。
- 不声称 H1e 修好了 JOIN，也不声称 `[0x1000E]` 消失；`FORWARDED_VARIABLES` 那扇门 M 未打开、H 未打开。
- 不声称任何门禁点亮（`W30` 与 `p0-core` 实测仍 `promotable False`，载荷 `cfa0f118…`）。
- 不声称 Minekin 完成。

## 第十五轮（2026-09-27，M 主控）：收干全部 lane 分支 + 一处依赖重分类 + 派 `H1f`

### 现场核对（本轮亲量，非引用上轮）
- `git ls-remote origin refs/heads/main` = `ea97c5c44ec5f3ac9a6a16274648cc52a4dccbfe`；M 的集成 worktree `../minekin-wt-integration` HEAD 同值、`git status --porcelain` 在本轮写入前为空。
- **全部 lane 分支已收干**：逐条 `git merge-base --is-ancestor <远端尖> ea97c5c` 核验，20 条 `codex/*` 分支全部 `IN_MAIN`（含 E 的 `codex/minekin-evidence @ 7f75dab`、H 的 `codex/minekin-client-env-readout @ 743765e`、B1-b 的 `codex/minekin-offline-090-100 @ b9c40a7`）。唯一 `AHEAD` 的是 `codex/parallel-execution-plan @ e472897`，它相对主干只多两笔，内容 diff 就是 `docs/parallel-execution-plan.md` 一份文件，而按 `git diff ea97c5c FETCH_HEAD` 读的是**主干更新、分支更旧**（分支那份还是 2026-09-26 的原始草稿，没有第四到第十四轮的那些补注）⇒ 判为已被取代的开工支，**无待合内容**，不再挂待办。
- 清理：M 自己第十四轮的暂存 worktree `../minekin-wt-m-r14` 与分支 `review/m-r14-h1e` 已删（删前核过：工作树干净，且其树与 `ea97c5c` 的差异恰是 5 份 `docs/` 文件、零源码/测试差异 ⇒ 那笔本地合并树的内容全在主干里）。

### 一处依赖重分类（本轮的实质判断，按字节改的是措辞里的因果，不是判据）
第十四轮把「1.20.1 加入者起跳面」写成了需要主控决策、且前置在 `src/minekin_core/config.py:51` 的 `FORWARDED_VARIABLES`。本轮重读字节后确认那是**把两个独立面混成一件事**：

- 加入者自己的 LAN profile 在 `test-orchestrator/runner/domain.sh:728-744` 那段内嵌 python 字典里，`"minecraft_version"` 是字面量 `1.21.4`（同一字典 `"profile_id": "p0-lan-host-fixture"`）；而它要加入的世界的版本并非常量——`:413` 起的 `launched_version` 从 bundle profile 的 recipe 读出，`:565-585` 附近拼成 `version_args` 交给 `tools/run_controlled_server.py`。⇒ 加入者声称的版本与世界版本按构造可以不一致，这就是 V1/V2 记录里那句「1.20.1 没有加入者起跳面」的字面来源，**修它在 H 独占面内**。
- `FORWARDED_VARIABLES` 管的是 **Core 起跳的客户端**能不能拿到 `XDG_RUNTIME_DIR`（H1e 已按字节证实那三格白名单里没有它），与「加入者 profile 声称哪个版本」无关；`[0x1000E]` 那一族的最后一跳仍在产品面，本卡不打开、也不得顺手打开。
- `domain.sh:404-407` 的 auto+joiner 拒止是**第三件事**：它自己的注释写明「no auto resolution has been reviewed for it」⇒ 属主控保留的语义冻结，`H1f` 的卡面硬边界就是**不开这扇门**，只覆盖命名 profile / 具名 bundle 路径。

### 派工 `H1f` `V1201-JOINER-VERSION-FROM-RUN-001`（仅在分支，未审未合）
- 支 `codex/minekin-joiner-version-from-run` @ `../minekin-wt-h1f`，base `ea97c5c`（M 新建 worktree，施工由 H lane 会话负责，M 不进它的工作树）。允许路径恰三份：`test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py` + 新记录 `docs/p0-h1f-joiner-version-from-run-2026-09-27.md`。
- 验收五条（写进派工）：改前后逐字打出实际写出的 profile；新契约测试在 base 字节上转红、改后转绿（非恒真）；拿不到版本时具名拒止并非零退出且**不留下**声称 `1.21.4` 的 profile（禁止静默回落）；1.20.1 与 1.21.4 两版本来源各一次正对照；**不要求** 1.20.1 完整 JOIN 变绿，真跑只报停在哪个具名读数。
- 规范卷至多 `:ro`、不封 attempt/bundle；不新建 case id、不翻 `mandatory`、不动 registry/判据/seal schema、不碰 M 的三份主干计划文档；只推自己分支。

### 四态报告（本轮）
- **已合入 main**：本轮无新合入（远端仍是第十四轮的 `ea97c5c`）；本轮的主干写入是这一份回写加 §4/`lane_next` 的登记。
- **仅在分支**：`H1f`（在工，未交付、未审、未合）。
- **真实封证**：本轮零封证。卷上仍是 E 第十四轮那三段 `SEALED` bundle（A1 `670aec0b…` / B `0314121c…` / A2 `0cc1fb99…`），M 全程至多 `:ro` 读。
- **未验证**：OFFLINE-100 的链上载体与 `world_context_id`（三段皆 `None`，父行实测 `FAIL / A_B_A_TRIPLE_NOT_SEALED`）；OFFLINE-090 的 Dashboard 载体与真跑；反例 9/10/11；1.20.1 侧活体 JOIN 与 `[0x1000E]`；`H1f` 的全部读数（尚未交付）；门禁一律未点亮（`W30`/`p0-core` 仍 `promotable False`，载荷仍 `cfa0f118…`）。

### 不声称
- 不声称 `H1f` 会让 1.20.1 的 JOIN 变绿——它的目标只是让加入者 profile 声称的版本来自本次真正起起来的世界。
- 不声称 V lane 已解锁：V 的下一张活体卡仍排在 `H1f` 收口并入主干之后。
- 不声称任何 case 闭合、任何门禁点亮，不声称 Minekin 完成。

## 第十六轮（2026-09-27，M 主控）

### 现场核对（每轮必做）

- 远端 `main`：本轮起点 `41cff82` → M 文档笔 `12d6fbb` → H1f 合并 `2ef64a8` → E-CX 合并 `5dbcc8a`；每次推送后 `git ls-remote origin refs/heads/main` 逐字复核，三次一致。
- 两条 lane 分支按**真实 merge-base** 审：H1f base `ea97c5c`（lane 三笔 `02a8b4b`/`258009a`/`403ec6b`），E-CX base `7aa5d14`（三笔 `8c38f1d`/`9fdc4dd`/`446c8df`，逐文件 diff 只一个新文档）。两卡的允许路径都守住：H1f 只写 `test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py` + 自己的 dated 文档；E-CX 只写一个 dated 文档，`tools/**`、fixture、registry、`src/**` 一字未动。
- 派工：`V3-1201-JOIN-LIVE-READOUT-AFTER-H1F` 在 `H1f` 并入后即刻派到支 `codex/minekin-v3-1201-join-live-readout` @ `../minekin-wt-v3`（base `5dbcc8a`）。只用本地隔离服、不连用户远程服；规范卷对该支 `:ro`，活体材料只写 V 私有 data root；`domain.sh:404-407` 的 auto+joiner 拒止保持闭合。

### 本轮量出来的三件事（全部 M 侧独立复量，不是抄 lane 报告）

1. **H1f 的版本来源**：M 自建复审 worktree `minekin-wt-m-r16`（branch `m-r16-h1f-review` @ `258009a`），把**基线块**（`git show ea97c5c:…domain.sh` 的 728-745）与**新字节块**（738-759）逐字抽出来在容器里驱动（`.tmp/m-r16-h1f-probe.sh`，日志 `.tmp/m-r16-h1f-probe.log`，规范卷全程不挂载）：
   - 基线：`launched_version=1.20.1` 进 → profile 仍写 `"minecraft_version": "1.21.4"`（rc 0、无拒止）；版本置空 → 仍写 `1.21.4`。缺陷读数成立。
   - 新字节：`1.20.1`→`1.20.1`、`1.21.4`→`1.21.4`；置空 → `rc=2` + 一句具名拒止 + `/tmp/domain-join-profile.json` **不存在**（`new_empty_profile_exists=no`）⇒ 没有常量兜底。
   - 正对照：除 `minecraft_version` 外七个字段与键集与基线逐字一致（`non_version_fields_identical True`、`keys_equal True`）。
   - 门：`bash -n` OK、`tests/contract/test_runner_scripts.py` 29 passed、`ruff format --check` 353 files OK、`ruff check` OK；合并后主干全量 `2596 passed, 3 skipped in 386.43s`（`.tmp/m-r16-full-suite-merged.log`；= 基线 2594 + 新契约 2）。
2. **E-CX 的三条 clause 非恒真**：M 自写复量脚本 `.tmp/m-r16-cx-recheck.sh`（卷 `:ro`，伪造只发生在 `/tmp` 带标签副本，日志 `.tmp/m-r16-cx-recheck.log`），对 A2 bundle `7ff026e4…` 三份副本各跑「clause + `evidence verify`」两层：
   - `control`（未伪造）→ `kin_clause=None session_clause=None verify_rc=0`；
   - `cx9`（`kin_id` 改成 `kin-e-aba-forged`）→ `KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-e-aba-forged`、`verify_rc=12`；
   - `cx10b`（把 A2 自身 session 换成 A1 的 `f0a28733…`，即 §3.6-10 的**字面**三段形状）→ 两条 clause **仍 `None`**、`verify_rc=12`。
   - 仓库字节侧复核该构造性质：`SESSIONS_NOT_THREE_DISTINCT` / `KIN_ID_NOT_SINGLE_ACROSS_TRIPLE` 在 `tools/assert_case_evidence.py` 出现 **0 次**；C2 clause（`:3867-3895`）只比 `previous_run_events` 一个相邻对 ⇒ **「首尾两次 run 的 session 不同」在今天的注册判据里根本不可判**，正是卡面对「相邻两 run session 不同不足以证明整条」的最硬证据。
3. **门载荷未漂移**：两次合并之后再读一次（`:ro` 容器、同一 `report_promotion.py --data-root /data`，日志 `.tmp/m-r16-payload-after-merges.log`；文档笔那一笔的读数在 `.tmp/m-r15-payload-after-doc.log`）：`gate_payload_sha256` 仍 **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**；`report_rc=1`；`W30.promotable False`（blocks `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、`p0-core.promotable False`；`W30.absent` 仍 `OFFLINE-060/080`、`non_mandatory` 仍 11（含 070/090/100）、`misattributed 0`。`verify_fixture_digests OK`、`check_case_assertions OK (150 registered)`、`check_boundaries OK`、`git diff --check` 净。

### 等主控（用户）表态的两项，本轮不实施

- **跨 bundle 三段链载体**：OFFLINE-100 的字面 10 与「首尾 A 同一获确认 world context」要新载体 ⇒ 扩展封存 schema `minekin.p0.evidence.v1`（会重封全卷）。E-CX 与 M 的读数都证明这是**构造边界**而非「再测一下就绿」。真跑侧本轮不再等待：受控本地 A→B→A 的三段（seq 3/4/5、bundle `670aec0b…`/`0314121c…`/`0cc1fb99…`，摘要为 E-CX §2 自量、**M 侧未复量**）早已封存并在 E-CX 里逐条对过，H 的写卷任务（`H1f`）也已让窗——缺的只有跨 bundle 载体这一项，因此该 case 保持未完成而不补排 E 窗。
- **OFFLINE-090 的 Dashboard 载体**：父行今天恒答 `DASHBOARD_CARRIER_NOT_SEALED`；日志/崩溃那一半已按第十五轮读数确认为**部分证据**，整条不得标 PASS。

### 四态报告

- **已合入 main**：`12d6fbb`（090 §2.7 的真实读数）、`2ef64a8`（H1f：`domain.sh` +17/−3、契约测试 +184、dated 记录 +292）、`5dbcc8a`（E-CX：dated 反例记录 +210）；远端 SHA 三次逐一核过。
- **仅在分支**：`codex/minekin-v3-1201-join-live-readout`（`V3` 在工，base `5dbcc8a`，本轮派工时尚无提交）。其余 lane 支（`codex/minekin-offline-070` @ `9d43de6`、`codex/minekin-offline-090-100` @ `b9c40a7`）经 `git merge-base --is-ancestor` 逐一确认已在主干内，不再是待审分支。
- **真实封证**：本轮**零新增封存**（卷全程 `:ro`；E-CX 明确写试探回 `Errno 30`）。
- **未验证**：H1f 新字节下的整程 live server+joiner（1.20.1 / 1.21.4 各一次）——本轮已据此派 `V3`；E 的 `evaluate` 判官层父行 failures 逐字与三枚 bundle 摘要自算（M 侧未复量，采信其记录）；090 的文件级副本注入与单字节摘要哨兵；OFFLINE-090 Dashboard 半句；§3.6-8 后半（A2 载体整体搬到 B 的真实世界）；1.20.1 侧 `GLFW 0x1000E`/`XDG_RUNTIME_DIR` 的复现或排除；门禁一律未点亮。

不声称 Minekin 已完成：本轮只把两张在工卡收口，并让 OFFLINE-090/100 的「已测」与「按构造不可测」第一次有了分层留证。

## 第十七轮（2026-09-27，M 主控）：把 OFFLINE-090 剩下两句「未测」量成文件级事实

### 现场核对（本轮亲量）

- 远端 `main`：本轮起点 `8fe96aa` → M 侧 090 读证文档笔 `776bc44`，推后 `git ls-remote origin refs/heads/main` = `776bc44523c4af37d324aefbb5735235936a95a7`（逐字一致）。这份回写落在其后，不移动任何登记字节。
- M 集成 worktree `../minekin-wt-integration` 在写入前 `git status --porcelain` 为空；规范卷 `minekin-runner-data` 全程 `:ro`，伪造只发生在带标签的 `/tmp` 副本，**零封存**。
- `V3` 仍在工、未交付：`../minekin-wt-v3` 处于 base `5dbcc8a` 且工作树干净（无提交），远端 `git ls-remote origin | grep v3` 为空 ⇒ 上一轮「仅在分支」那句仍成立，判据不因此改变。

### 本轮量出来的五件事（`.tmp/m-r17-090-filelevel.sh`，日志 `.tmp/m-r17-090-filelevel.log`，rc=0）

1. **判官读的是 manifest 声明的文件，不是它自己挑的子集**：全卷普查 `bundles=99`、`readable_bundles=65`、其中 **49** 个 bundle 的文件级载体里出现认证字段名。这里刻意留了正对照——若把「零命中」当成结论，先要证明同一读法在别处能命中。
2. **具名样本**：`kin-01 / 03bd3a22f6ac43aea07d470222cd2c92`，`bundle_digest 368d206ccf535efeb4c23ba948962d3ffea45924fd18ee93249908d3a65b9bab`，文件级载体 **14** 个（含 `client/latest.log`、`bridge-trace.jsonl`、`server/server.log`、`asserter-inputs.json`）。控制组：`bundle_clause=None` + `dashboard_clause='DASHBOARD_CARRIER_NOT_SEALED'` + `verify_rc=0`。
3. **注入反例在两种载体形状上都成立，且哨兵不背锅**：`client/latest.log` 塞真 token → `AUTH_BODY_EXPOSED:client/latest.log:accessToken`；同一份塞公版哨兵 `0` → 仍 `None`。`bridge-trace.jsonl` 塞合法 JSON 行（账本形状）→ `AUTH_BODY_EXPOSED:bridge-trace.jsonl:accessToken`，哨兵形状 → `None`。也就是说卡面第 1 条要求的「不把任意数字 0 算作泄漏、按字段/参数上下文判」现在是**驱动出来的**，不是注释里的声称。同时 `bridge-trace.jsonl` 追加非 JSON 散文行会让 `read_sealed_material` 具名抛 `Unreadable`——不可读的账本被指名，不会被算成干净。
4. **Dashboard 半句的拒止是载体驱动、不是常量**（这正是等主控那一行的实质内容）：往 `/tmp` 副本塞一个不声明的 `dashboard/view.txt` → 载体侧仍 `DASHBOARD_CARRIER_NOT_SEALED`，而封存通道报 `UNDECLARED_FILE:dashboard/view.txt`；把它**写进 manifest** → `carriers=15`，此时干净文件两半句皆 `None`、含真 token 的文件答 `AUTH_BODY_EXPOSED:dashboard/view.txt:accessToken`。但手写 manifest 条目缺 `size` 时封存通道直接 `MinekinError: evidence manifest artifact size must be an integer`（`rejudge_rc=1`）。⇒ 父行今天要真答，需要的不是改判据而是**一个被真实封存的 dashboard 载体**，即扩展 `minekin.p0.evidence.v1`——仍属主控保留决策，本轮不实施。另外把 manifest 里全部文本载体剥掉 → 答案变成 `NO_EXPOSURE_CARRIERS_READABLE`，与「扫过且干净」是两种具名读数。
5. **门载荷未漂移**（`.tmp/m-r17-payload-after-090-doc.log`，同一 `report_promotion.py --data-root /data`、`:ro`）：`gate_payload_sha256` 仍 **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**，`report_rc=1`，`W30.promotable False`（`NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、`p0-core.promotable False`；`non_mandatory` 仍 11（070/090/100 俱在），`misattributed 0`。OFFLINE-090 因此**没有**借非门禁登记被暗示为闭合。

### 四态报告

- **已合入 main**：`776bc44`（只改 `docs/p0-offline-090-100-case-spec-2026-09-27.md`：§2.7 的两句现在时「未测」改指 §2.8、新增 §2.8 记录上述十次驱动、§3.6 的 9/10/11 改引 E-CX `5dbcc8a` + M 侧复量脚本）与这一份 handoff 回写。远端 SHA 逐字核过。
- **仅在分支**：`codex/minekin-v3-1201-join-live-readout`（`V3` 在工，base `5dbcc8a`，本轮核对时零提交、远端无该支）。
- **真实封证**：本轮零新增封存；卷上仍是 E 第十四轮那三段 `SEALED` bundle，M 全程至多 `:ro`。
- **未验证**：`V3` 的全部活体读数（尚未交付）；1.20.1 侧 `GLFW 0x1000E`/`XDG_RUNTIME_DIR` 的复现或排除；OFFLINE-090 **被真实封存的** dashboard 载体端到端（本轮只证明该拒止随载体变化，未封任何载体）；其余 8 对文本形状仍在单测层而非文件级（本轮量的是 log/JSONL 两对）；OFFLINE-100 的跨 bundle 三段链载体与 `world_context_id`；门禁一律未点亮。

### 不声称

- 不声称 OFFLINE-090 整条闭合：日志/崩溃那一半是部分证据，Dashboard 半句仍具名缺口，父行仍 `DASHBOARD_CARRIER_NOT_SEALED`。
- 不声称 OFFLINE-100 或 `OFFLINE-070` 有任何推进；070 仍是独立卡，其 `identity_revision`/人格根缺口不由本轮读数顺带修掉。
- 不声称 Minekin 已完成。

## 第十八轮（2026-09-27，M 主控）：OFFLINE-090 的崩溃半句在真实封存的崩溃工件上驱动过

V3 交付前 M 继续做不依赖它的判官侧复量。全部在 `.tmp/m-r18-090-crash.sh`（日志
`.tmp/m-r18-090-crash.log`，rc=0）+ 两份普查（`.tmp/m-r18-case-attribution.sh`、
`.tmp/m-r18-bundle-census.sh`/`-census2.sh`）里，规范卷全程 `:ro`，副本在 `/tmp`，**零封存、零代码/fixture/registry 改动**。

- **普查（正对照）**：全卷 bundle 目录 **99** 枚（全部在 `/data/kin` 下、全部 32-hex 命名、全部有 `manifest.json`、无异名兄弟 `odd_names=[]`），其中 **3** 枚在 `client/crash-reports/` 下有封存工件：`kin-04 / 8164024d…`、`kin-e-rr-seal / 787168062c…`、`kin-e-rr-seal2 / 6286f1e5…`；OFFLINE-100 三段所在的 `kin-e-aba` 有 5 枚 bundle、**0** 枚崩溃工件。
- **驱动**（在第一枚真崩溃工件上追加一行，10 个文本载体、崩溃工件在册）：JSON 字段形状与 `--accessToken <值>` 参数形状各转红一次（`AUTH_BODY_EXPOSED:client/crash-reports/crash-2026-09-26_12.24.07-client.txt:accessToken`）；同一位置放公版哨兵 `0` 时 `accessToken`/`clientId`/`xuid` 三行全部保持 `None`；未改动副本 `verify_rc=0`（`bundle_digest 70380d06…`），五份被改副本一律 `rc=12` ⇒ 摘要哨兵覆盖崩溃载体，且崩溃判法与哨兵保护在文件路径上同时成立。
- **两条新读界（都往「不能声称」的方向）**：① `run-document.json` 无 case 标识字段（全卷 `case_id`/`case`/`case_ids` 读出空集），**「这份崩溃属于哪条 case」不能从 bundle 字节读出**——上表那三枚归给 `CORE-030` 家族靠的是 E 的记录，不是载体，§2.3 那一行已按此更正；② 目录侧全量 **99** 与早期清单引用的台账侧 **105/107** 不等值（差异本轮未追查），普查分母一律具名。⇒ 对已登记的 OFFLINE-090，崩溃半句仍是**无该家族载体**，不等于「测过且计数为 0」，整条不得标 PASS 的判定不变。
- 门：`verify_fixture_digests OK`、`check_case_assertions OK (150 registered)`、`check_boundaries OK`、`git diff --check` 净；门载荷本轮未重读（改面只有文档，`case_version` 不摘要文档字节，上一读数是第十七轮的 `cfa0f118…`）。
- **四态**：已合入 main = 本轮两份文档笔（紧随 `7cf4284`）；仅在分支 = `codex/minekin-v3-1201-join-live-readout`（仍零提交、远端无该支）；真实封证 = 零；未验证 = V3 活体读数、被真实封存的 dashboard 载体端到端、OFFLINE-100 跨 bundle 三段链载体、门禁一律未点亮。

## 第十九轮（2026-09-27，M 主控）：OFFLINE-100 的服务端证据条款逐合取项驱动过

V3 仍零提交（worktree 干净停在 base `5dbcc8a`、远端无该支），M 继续做不依赖它的判官侧复量。全部在
`.tmp/m-r19-100-server-clause.sh`（日志 `.tmp/m-r19-100-server-clause.log`，rc=0）+
`.tmp/m-r19-payload-after-r18.log` 里，规范卷全程 `:ro`，副本在 `/tmp`，**零封存、零代码/fixture/registry 改动**。

- **现场核对**：远端 `main` = 本地 `main` = `e22c106`；`origin` 上 lane 支 21+ 枚，V3 那支不存在 ⇒ V 的活体读数本轮仍只能标未验证。
- **`kin-e-aba` 全根普查**：5 枚封存 bundle，其中 `7ff026e4…`/`a26e2c35…`/`cd215ca1…` 三条对该条款答 `None`，
  `c96aa8bd…`/`fd516eb6…` 两条答具名 `JOIN_NOT_LOGGED`（按 §2.9 的读界只点名、不归因）。被驱动的正对照是干净三条里的
  第一枚（E 的 A2，`bundle_digest 0cc1fb99…`，13 件工件，控制副本 `verify rc=0`），其自身封存字节为
  `Preparing level "world"` / `level-name=world` / `profile_id=p0-controlled-offline-loopback` /
  `revision=c742c476…`。
- **逐合取项的九行驱动（`docs/p0-offline-090-100-case-spec-2026-09-27.md` §3.7）**：日志不再点名世界 ⇒
  `SERVER_LOG_NEVER_NAMED_THE_WORLD_IT_OPENED`；日志与 properties 不一致 ⇒
  `SERVER_OPENED_A_WORLD_OTHER_THAN_ITS_PROPERTIES:m19-other-world`；删 `level-name` ⇒
  `SERVER_PROPERTIES_SAY_NOTHING_ABOUT_THE_WORLD`；`revision` 非摘要 ⇒ `SERVER_PROFILE_HAS_NO_REVISION_DIGEST:'not-a-digest'`；
  `profile_id` 置空 ⇒ `SERVER_PROFILE_NAMES_NO_WORLD`；删 `trusted/server-profile.json` ⇒ `NO_SEALED_SERVER_PROFILE`；
  `server/usercache.json` 换成非列表 ⇒ `read_sealed_material` 抛 `Unreadable`；**删 `usercache.json` ⇒
  `IDENTITY_NOT_RECORDED`，此时 profile/properties/log 三者仍全部一致** ⇒ 卡面第 2 条要的「外部身份取服务端证据」
  在文件路径上确有牙齿，run 不能只靠客户端自称过这一款。每份被改副本一律被封存通道拒收（`verify rc=12`），
  与 §2.8 相同：判据与完整性是两台独立仪器。
- **读界不变**：该条款可变红不等于整条可判——父行仍 `FAIL / A_B_A_TRIPLE_NOT_SEALED`，「首尾 A 同一获确认 world
  context」「三次不同会话」仍按构造不可判（跨 bundle 载体属主控保留）。§3.6 的现在时陈旧表述按本轮实测改写：
  1-3、5-6 仍为设计，4 只驱动了同族的删/坏缓存而非 uuid 改写。
- **门**：`verify_fixture_digests`、`check_case_assertions`、`check_boundaries`、`ruff format --check`/`ruff check`、
  `git diff --check` 见下方收口笔；门载荷本轮**重读**（`.tmp/m-r19-payload-after-r18.log`）仍
  `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，`report_rc=1`，`W30`/`p0-core` 仍
  `promotable False`（`NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`，`W30.absent` = OFFLINE-060/080）。
- **四态**：已合入 main = 本轮 §3.6/§3.7 文档笔；仅在分支 = `codex/minekin-v3-1201-join-live-readout`（零提交、远端无该支）；
  真实封证 = 零（本轮不建 attempt、不封 bundle）；未验证 = V3 的 1.20.1 活体读数、端到端真 Dashboard 载体、OFFLINE-100
  跨 bundle 三段链载体、门禁一律未点亮。
- **不声称**：不声称 OFFLINE-100 任何一条闭合，不声称 `non_mandatory` 登记是晋级，不声称 Minekin 完成。

## 第二十轮（2026-09-27，M 主控）：OFFLINE-100 的重启成对条款逐字段驱动（§3.8）；V3 交付到分支

判官侧复量在 `.tmp/m-r20-100-ab-clauses.sh`（`.log`）+ 两个追加探测 `.tmp/m-r20b-previous-run-id.sh`、
`.tmp/m-r20c-asserter-inputs.sh`（各自 `.log`，rc=0）里，规范卷全程 `:ro`，副本在 `/tmp`，
**零封存、零代码/fixture/registry 改动**。

- **同一枚 A2 bundle 的双载体普查**：`kin-e-aba / 7ff026e4…`，`previous_run_id = a26e2c35…`，
  本 run 载体 `bridge-trace.jsonl` 与本 run 之外那份 `previous-run-trace.jsonl` 各 **19** 行，
  `here_sessions ['ed3fdc06…']` / `prev_sessions ['4ba0825e…']`，未改副本两条款 `None / None` 且 `verify rc=0`。
- **§3.6 条目 1/2/3/5/6 自此是实测**：改上一份的 `kin_id` ⇒ `KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-m20-foreign`；
  改本 run 一份行的 `kin_id` ⇒ 同一具名从另一侧到达；previous 单行 `run_id` 外来的 ⇒
  `PREVIOUS_ROWS_NOT_ONE_RUN:…`；本 run 单行 `run_id` 外来的 ⇒ `THIS_TIMELINE_ROWS_ARE_NOT_ONE_RUN:…`；
  `kin_id` 清空 ⇒ `LEDGER_ROW_NAMES_NO_KIN`；把本 run 的 session 塞进 previous 载体 ⇒
  `SESSION_ID_SHARED_ACROSS_RUNS:ed3fdc06…`；**只在本次行里加一枚外来 session ⇒ 两条款仍 `None`**
  ⇒ 这条规则判的是「跨 run 共享」而不是「唯一」，即 5 的反恒真正对照。
- **缺证据一律具名拒绝、不当计数为绿**：清空 previous 载体 ⇒ 两条款 `PREVIOUS_TRACE_NOT_SEALED`；
  previous 行不具 session ⇒ `PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION`；本次行不具 session ⇒
  `NO_SESSION_ATTRIBUTION_IN_LEDGER`。除控制与两次空操作外，每份被改副本一律 `verify rc=12`。
- **本轮量到的字段落点更正（一次失败驱动换来的读数）**：清 `run-document.json` 里的 `previous_run_id` 是**空操作**
  （实读其顶层键 = `argv_digest/generation/kin_id/overlay/pid/recovery/run/run_id/schema_version/session_id/started_at/status`，
  条款仍 `None/None`、`rc=0`）；该字段实际在 **`asserter-inputs.json`**，其完整键集实测恰为
  `['kin_id','previous_run_id','run_id','schema_version','username']` ⇒ 清它即两条款 `PREVIOUS_IS_FIRST_RUN`，
  且同时清空 previous 载体仍是 `PREVIOUS_IS_FIRST_RUN`（字段先于载体判空）。同一份键集也再次量出卡面第 1 条的前提：
  `asserter-inputs.json` 里没有 token/xuid/clientId 可读。
- **门**：本轮 `ruff check` + `ruff format --check`（354 files 已格式化）、`verify_fixture_digests`、
  `check_case_assertions (150 registered)`、`check_boundaries`、`git diff --check` 全 `rc=0`（收口笔前复跑）；
  门载荷重读仍 `cfa0f118…`、`report_rc=1`、`W30`/`p0-core` `promotable False`、
  `W30.absent = OFFLINE-060/080`、`non_mandatory 11/24`、`misattributed 0`。
- **V3 交付**：停摆的 V lane 会话按「完成并交付」恢复规则重派，产出支 `codex/minekin-v3-1201-join-live-readout`
  提交 `bbf0daf`（base `5dbcc8a`，含 `H1f`），改面恰一份新记录 `docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md`。
  自报四读数里 **② 是具名阻断不是排除**（1.20.1 加入者停在 `launcher.profile` 的 pinned-bundle 准入，未起 JVM），
  并声明 `ruff` 在其环境不可用（`rc=127`，按未跑记录）⇒ 按惯例进入 M 的 merge-base 复审与独立复量，本轮尚未合入。
- **四态**：已合入 main = 本轮 §3.8 文档笔；仅在分支 = `codex/minekin-v3-1201-join-live-readout @ bbf0daf`（待 M 复审）；
  真实封证 = 零（本轮不建 attempt、不封 bundle）；未验证 = 1.20.1 加入者的 JVM 侧与端到端 JOIN、§3.6 条目 4 的字面 uuid 改写、
  跨 bundle 三段链载体、门禁一律未点亮。
- **不声称**：成对条款可变红不等于三段可判；不声称 OFFLINE-100 任一条闭合，不声称 V3 已并入，不声称 Minekin 完成。

## 第二十一轮（2026-09-27，M 主控）：V3 双审合入主干（`PARTIAL`），并复量其四条承重读数

V lane 的停摆会话按「完成并交付」规则恢复：支 `codex/minekin-v3-1201-join-live-readout` 提交 `bbf0daf`
（base `5dbcc8a`，含 `H1f` `2ef64a8`），改面恰一份新记录 `docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md`
（`git diff --stat 5dbcc8a..bbf0daf` = 1 文件 / +139；真实 merge-base 与 lane 自报同为 `5dbcc8a`）。
M 以合并 `3ffc79c` 入 `main` 并核远端 SHA。V 全程未挂规范卷、零封存。

- **M 的独立复量（只读 V 已落盘的字节，不重写任何读数）**：
  `sha256(git show 5dbcc8a:test-orchestrator/runner/domain.sh)` 实读 `f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5`，
  与 d1/d3/d4/d5/d6 挂载的那份 `.tmp/v3/src` 副本、以及主干 worktree 的文件逐字相同；反转型 d2 用的那份 base 前副本是 `9883a788…`。
  ① 加入者 profile：d1 `1.20.1` / d4（真仓库树）`1.20.1` / d2 `1.21.4` / d3 **未写 profile**；
  ② 的 stderr：d1 与 d2 的 `domain-client-environment.err` 都是 **0 字节**，全输出树无 `XDG_RUNTIME_DIR is invalid`；
  准入两段逐字对上：d1 `"server profile minecraft_version is outside the pinned bundle"`、
  d2 `"the session launches Minecraft 1.20.1, the profile pins 1.21.4"`；
  ③ d5 的 `/tmp/domain-session.err` 含 `3639 of 3639 artifacts … 738432269 bytes … [BUDGET_UNDECLARED]`，
  d4 给 `launcher.recipe` 的「Bridge jar has not been built」；④ 反转（d1↔d2）与正对照（d3 无版本即拒写）都在盘上。
- **一条措辞更正（M 侧新量，写在这里而不是改 V 的文档）**：`grep -rl "0x1000E"` 在 V 的输出目录**会**命中——命中的是
  `90-readouts.txt` 里那行检查标签自身（`V3: files under /data or /tmp mentioning 0x1000E:`），不是客户端字节。
  ⇒ ② 的正确表述是「客户端字节不含 ⑤ 家族」，且那份 stderr 只在走到客户端环境段的两次 run（d1/d2）存在，
  d3-d6 更早停住（正是 B1 的形状）。这不是 V 的读数错，是把「grep 无命中」这种可被标签行反驳的写法换成字节口径。
- **新落阻断 B1 登记给主控**：H1f 之后 profile 诚实报 `1.20.1`，`launcher.profile` 的 pinned-bundle 准入随即拒绝它，
  加入者 JVM 从未起 ⇒ 1.20.1 端到端 JOIN 仍不可观测，⑤ 家族的排除保持**有界**。解阻需要 registry/准入语义的产品决定
  （钉住的 bundle 是否为准入放行 `1.20.1`），属主控保留 ⇒ V 的 `lane_next` 置空，不重排活体卡。
- **门**：合并前后 `ruff check` / `ruff format --check`（354 files）、`check_case_assertions (150 registered)`、
  `verify_fixture_digests`、`check_boundaries` 全 `rc=0`（V 侧那两门 `rc=127`＝宿主与镜像都无 ruff，按其自报记为未跑，由 M 补齐）；
  全量 pytest 本轮未复跑（改面只有文档）。合并后重读门载荷：`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`
  一字未动、`report_rc=1`、`W30`/`p0-core` 仍 `promotable False`、`W30.absent = OFFLINE-060/080`、
  `non_mandatory 11/24`、`misattributed 0`（`.tmp/m-r21-payload-after-v3.log`）。
- **四态**：已合入 main = `bbf0daf` 的记录（合并 `3ffc79c`）+ 本轮计划表回写；仅在分支 = 无新增（V 支停在已合提交）；
  真实封证 = 零（V3 不封证，封证需求具名交给 E/主控）；未验证 = 1.20.1 加入者的 JVM 侧与端到端 JOIN（B1）、
  ⑤ 家族在**已启动**客户端上的一般性排除、§3.6 条目 4 的字面 uuid 改写、OFFLINE-090 的 Dashboard 载体、
  OFFLINE-100 跨 bundle 三段链载体、门禁一律未点亮。
- **不声称**：不声称 V3 让 1.20.1 的 JOIN 变绿，不声称 ⑤ 家族已被一般性排除，不声称任何 case 闭合或门禁点亮，不声称 Minekin 完成。

## 第二十二轮（2026-09-27，M 主控）：V3 的续投 `1dad5f5` 按字节退回一处；B1 的真常量落到产品面

V lane 的第一段 `bbf0daf` 已在第二十一轮并入主干（合并 `3ffc79c`）。随后该卡的原始后台会话又推了一枚**纯增量**续投
`1dad5f5`（`bbf0daf..1dad5f5` 快进，改面恰同一份 `docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md`，
`+259 -0`，只增不改旧行），本轮按契约复审：

- **通过的部分**：真实 merge-base 与自报同为 `5dbcc8a`，允许面守住（仍只有那一份 `docs/validation/` 记录）；
  **一处 ruff 记录被 lane 自己更正**——上一段写的 `rc=127 未跑` 是 bare `ruff` 缺失，续投用 `uv run ruff format --check`
  （355 files）与 `uv run ruff check` 补到 `rc=0`，并全量 `2596 passed, 3 skipped / 380.55s`＝主干基线一字不变，
  契约 29 passed、`bash -n` rc=0、case assertions OK(150)、fixture digests OK。
- **退回的具体一处（不并入，直到修正）**：`git show --check 1dad5f5` 命中 1 条行尾空格
  （`docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md:203`，被逐字引用的 harness stderr 行尾带一个空格）
  ⇒ 主干门 `git diff --check` 必须 `rc=0`，该提交现在合进来就是把这道门弄脏。口径：保留字节事实，把「原文含行尾空格」
  以脚注/转写表示，删掉那个空格即可；由 V 自己新提交修正，**M 不进 V 的工作树、不 amend 已推提交**（流程自我更正仍然有效）。
- **B1 的真常量落在产品面（新登记的保留决定，未动）**：lane 指认的准入钉住点在
  `src/minekin_core/adapters/launcher/server_profile.py:32`（`MINECRAFT_VERSION = "1.21.4"`，`:200` 用它做比较），
  M 在主干字节复核为真，并看到同族常量第二处 `…/launcher/metadata.py:16`（同样 `1.21.4`，且 `:392/:544` 以它为默认版本参数）。
  ⇒ 「让 1.20.1 的加入者进 JVM」需要的是产品钉住版本/准入语义的决定（`src/**`，H 与 V 都没有独占面，M 未打开），
  属主控保留；本轮只登记，不改、不派卡去绕它。⑤ 家族的排除继续按**有界**记录。
- **门载荷**：本轮零代码/fixture/registry 改动，最后一次实读仍是第二十一轮合并后的
  `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、`W30`/`p0-core` `promotable False`
  （`.tmp/m-r21-payload-after-v3.log`）；本轮只动文档故未重读。
- **四态**：已合入 main = `bbf0daf` 的记录（第二十一轮）+ 本轮 handoff；仅在分支 = `1dad5f5`（退回一处待修）；
  真实封证 = 零；未验证 = 1.20.1 加入者 JVM 侧与端到端 JOIN（B1）、⑤ 家族在已启动客户端上的一般性排除、
  §3.6 条目 4 的字面 uuid 改写、OFFLINE-090 的 Dashboard 载体、OFFLINE-100 跨 bundle 三段链载体、门禁一律未点亮。
- **不声称**：不声称 `1dad5f5` 已并入，不声称 1.20.1 JOIN 变绿，不声称 B1 已解，不声称 Minekin 完成。

## 第二十三轮（2026-09-27，M 主控）：V3 增量退回后修正并合入；B1 常量落到产品面

- **退回→修正→合入**：`1dad5f5`（+259 -0，纯增量、同一份记录）因 `git show --check` 命中一条行尾空格被按字节退回；
  V 自己以**新提交** `bd23f45`（+3 -1：删该空格并在其下注明原文该行带一个空格、所读事实不变）修正，
  M 未进 V 工作树、未 amend 已推提交。修正后 M 以合并 **`bd7bd56`** 入 `main`，远端 `refs/heads/main`
  已核为 `bd7bd56b6dda360635fa62baf9b1b3c3a30547b2`；合并后 `git diff --check` `rc=0`、`ruff check` 绿。
- **M 对增量的字节级抽查**：记录指认的准入钉住点在主干为真——
  `src/minekin_core/adapters/launcher/server_profile.py:32` `MINECRAFT_VERSION = "1.21.4"`（`:200` 用它比较），
  同族第二处 `src/minekin_core/adapters/launcher/metadata.py:16`（`:392`/`:544` 以其为默认版本参数）；
  自报全量 `2596 passed / 3 skipped` 与第十六轮起的主干基线一字相同 ⇒ 无测试计数漂移。
  增量的边界披露（bridge jar 字节被 `cp` 进 V 私有树、正本卷全程 `:ro`、未新建 attempt/bundle、零封存）随记录接受。
- **流程一条**：本轮出现同一张卡的**两个 V 会话先后交付**（`bbf0daf` 与 `1dad5f5`）。结论是分支仍单调快进
  （`bbf0daf` 是 `bd23f45` 的祖先、改面只有那一份文档），M 的 merge-base 审查因此能逐段守住；
  但下次派续命会话前应先确认原会话是否仍在写同一支，避免同树并发。
- **四态**：已合入 main = V3 的全部记录（`3ffc79c` + `bd7bd56`）与本轮回写；仅在分支 = 无；
  真实封证 = 零（V3 不封证）；未验证 = 1.20.1 加入者 JVM 侧与端到端 JOIN（B1，产品钉住版本/准入语义＝主控保留）、
  ⑤ 家族在已启动客户端上的一般性排除、§3.6 条目 4 的字面 uuid 改写、OFFLINE-090 的 Dashboard 载体、
  OFFLINE-100 跨 bundle 三段链载体、门禁一律未点亮（载荷最后实读 `cfa0f118…`，`W30`/`p0-core` `promotable False`）。
- **不声称**：不声称 V3 让 1.20.1 JOIN 变绿，不声称 B1 已解，不声称任何 case 闭合或门禁点亮，不声称 Minekin 完成。

## 第二十四轮（2026-09-27，M 主控）：V3 合入后的门载荷实读 + 全远端分支待审普查

- **现场核对**：本地 `main` = 远端 `refs/heads/main` = `42a60142e559139648c23db64233c17dc2eb4d80`（`git rev-parse HEAD`/
  `origin/main` 同枚）；工作树 `git status --porcelain` 空。V 支 `codex/minekin-v3-1201-join-live-readout = bd23f45`、
  B1-b 支 `codex/minekin-offline-090-100 = b9c40a7`，两者都已是 `main` 的祖先。
- **待审普查（25 枚远端 head 逐枚 `git rev-list --count origin/main..origin/<b>`）**：唯一 `ahead≠0` 的是
  `codex/parallel-execution-plan ahead=2`。这两笔（`21ffbac`、`e472897`）各自只改 `docs/parallel-execution-plan.md`
  （+78 / +7-1），而主干已有同主题提交 `13b84a8`、`432cc37`；`git diff --stat origin/main origin/codex/parallel-execution-plan`
  = `100 files changed, 119 insertions(+), 16956 deletions(-)` ⇒ 该支严格落后于主干、无待审内容，**不是**「仅在分支的未合并工作」。
  ⇒ 结论：今天没有 lane 分支等 M 审；`PARALLEL-INTEGRATION-GATE-001` 的队列是空的。
- **门载荷实读（补齐第二十三轮那句「只动文档故未重读」）**：在当前主干树（含 `3ffc79c` + `bd7bd56` 两笔 V3 合并）上
  只读跑 `tools/report_promotion.py --data-root /data`（`.tmp/m-r12-payload.sh`，容器内 `/src:ro` + 规范卷 `:ro`，
  读数存 `.tmp/m-r24-payload-after-v3-increment.log`）：`report_rc=1`、`gate_payload_sha256` 仍是
  `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']`、
  `W30 promotable False`（`NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、`p0-core promotable False`，
  `W30` `absent` 仍是 `OFFLINE-060/080`、`non_mandatory 11` / `p0-core 24`、`misattributed 0`。
  ⇒ V3 的记录合并既没搬门也没造「别的构建」；这一句现在是量出来的而不是预期。
- **四态**：已合入 main = 本轮只加本段回写（无代码/fixture/registry 改动）；仅在分支 = 无待审 lane 内容（过期支
  `codex/parallel-execution-plan` 按上面量化后排除）；真实封证 = 零（本轮未写卷、未新建 attempt/bundle）；
  未验证 = 1.20.1 加入者 JVM 侧与端到端 JOIN（B1，产品钉住版本/准入语义＝主控保留）、⑤ 家族在已启动客户端上的一般性排除、
  §3.6 条目 4 的字面 uuid 改写、OFFLINE-090 的 Dashboard 载体、OFFLINE-100 跨 bundle 三段链载体、门禁一律未点亮。
- **主控保留（本轮只命名，不实施、不派卡去绕）**：① B1 的钉住版本/准入语义（`src/minekin_core/adapters/launcher/server_profile.py:32`）；
  ② OFFLINE-100 的三段链载体＝`minekin.p0.evidence.v1` 扩字段。**这条 not-派 的理由不是「还没跑」**：A→B→A 的三段真跑
  早在第十四轮就封进规范卷（A1 `cd215ca1…`／B `a26e2c35…`／A2 `7ff026e4…`，各自 `evidence verify` 与复判 `agrees`），
  缺的只是将三段连成一条链的载体——父行 `tools/assert_case_evidence.py:3919` 至今恒答 `A_B_A_TRIPLE_NOT_SEALED` ⇒
  重跑一次不推进任何东西，也不需再排 E 的写窗；要动的是扩字段那一记决定。③ B2 剩余范围（非 mandatory ADMIT 行 + 卡面后半段）
  与 OFFLINE-090 拆非门禁子案的 case-id 分配。
- **不声称**：不声称队列里有可安全自派的下一张工程卡，不声称 1.20.1 JOIN 变绿，不声称 B1 已解，不声称任何 case 闭合或门禁点亮，不声称 Minekin 完成。

## 第二十五轮（2026-09-27，M 主控）：合入 1.20.1 本地加入排期分支；M 独立量到 v2 准入今天就容得下 1.20.1

- **现场核对**：起点远端 `refs/heads/main = e3b1c6f`；规划分支 `codex/minekin-next-1201` 尖 `0da7032`，
  `git log -1 --format=%P` 显示其 parent **恰为 `e3b1c6f`**，`rev-list --left-right --count` = `0 1` ⇒ 干净的单笔后继。
  `git worktree list` 共 35 个；规划 worktree（`~/.codex/worktrees/minekin-next-1201/minekin`）与 M 的集成分支 worktree
  `git status --porcelain` 都为空。
- **真实增量审查**：`git diff --stat $(merge-base) 0da7032` = 4 份 `docs/**`、`+61 -0`（新增
  `v1201-local-join-next-2026-09-27.md` 55 行 + 三处入口覆盖段），**零代码/fixture/registry/判据改动**；
  `git show --check` rc=0。覆盖段逐条守门：主干仍只有一个 `current_next`、v1 的 1.21.4 冻结行为不改、不连用户远程服、
  V08/HOST/PERSIST/跨 bundle schema 不代答。
- **卡面承重代码声明按字节复核**（主干 `e3b1c6f`，全部为真）：`server_profile.py:31/32/34` 三枚常量、
  `:164` v1 loader（`:200` 拒任何非 `1.21.4`）、`:403 load_joinable_session_target`（`:424` 只容 loopback、
  `:429` 只容恰一项版本）、`:439 require_target_allows_launch`、`:464 load_session_server_profile`；
  v2 字段面为 `_V2_REQUIRED_KEYS` 八项 + 可选 `pinned_bundle_id`，`_VERSION_POLICY_MODES = {"explicit_allowlist"}`，
  `auth_mode` 只容 `offline`，`resource_pack_policy ∈ {deny, prompt}`，`target_authorization` 恰 `{granted_by, basis}`；
  仓库里已有 v2 样例 `tests/fixtures/managed-remote-target-example.json`（其 `host` 是 TEST-NET-1 文档地址，非 loopback）。
- **M 的独立前瞻探针（不是复述卡面）**：`.tmp/m-r25-v2-loopback-probe.sh`，同一受控镜像、`/src:ro`、**规范卷全程未挂载**，
  直接在容器里驱动产品 loader ——
  `docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" -e PYTHONPATH=/src/src minekin-runner:local -lc 'bash /src/.tmp/m-r25-v2-loopback-probe.sh'`
  （日志 `.tmp/m-r25-v2-loopback-probe.log`）。读数：**P1 `127.0.0.1` + `offline` + 单版本 `1.20.1` 且本次启动 1.20.1 ⇒ 已接受**
  （`ManagedTargetProfile`，`revision 168854d9f2cc64c1…`）；五种情形各自具名拒止且都落在 `ADMISSION`：
  P2 版本错配「launches 1.21.4, the target allows 1.20.1」、P3 非 loopback「remote joining needs its own authorization card」、
  P4 多项 allowlist、P5 `auth_mode: online`「v2 profiles have no online-mode admission path」、P6 授权字段不合规。
  ⇒ **H1g 的前沿确实在 runner 写出的文档形状上，不在产品准入里**：如果 H1g 回报「现成 v2 路径承载不了」，
  那是与这条读数冲突的新事实，M 会按字节重查而不是采信措辞。
- **合入与远端核验**：`git merge --ff-only origin/codex/minekin-next-1201`（`e3b1c6f..0da7032`）→ `git push origin main`
  → `git ls-remote origin refs/heads/main = 0da7032ab34403830fbd0a3dea71f5fe65032615`；合入树 `git diff --check` rc=0。
  本轮另改一处主干现时态错述：交接首页「最新一轮是文末的第十二轮」→ 改为「文末最后一节即最新一轮」（第十二轮那句是当时读数）。
- **H1g 已派工（在工）**：卡面取自新入干的 `v1201-local-join-next-2026-09-27.md` §2。新 worktree
  `../minekin-wt-h1g`、新支 `codex/minekin-joiner-local-v2-profile`、base `0da7032`；允许面恰
  `test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py` + 一份新
  `docs/validation/v1201-joiner-local-v2-profile-2026-09-27.md`；硬边界＝不改 `src/**`（含 `metadata.py:16`）、
  不改判据/registry/门禁/封存 schema、不动 `domain.sh:404-407` 的 auto+joiner 拒止、不封证、规范卷至多 `:ro`、
  1.21.4 控制组字节不漂移、六个具名拒止都要在客户端 JVM 之前、必须带一项非空转反向。**卡的目标上限是「加入者越过
  `launcher.profile`」，不是 JOIN。**
- **四态**：已合入 main = 规划分支 `0da7032` 的全部内容（H1g→V4→E6 队列与三处入口覆盖段）+ 首页现时态更正；
  仅在分支 = H1g（施工中，尚无提交）；真实封证 = 零（本轮 M 与 H 都不写卷，规范卷未挂载）；
  未验证 = 1.20.1 加入者 JVM 真启动、Bridge 握手、JOIN/首快照（V4 的前题）、`metadata.py` 默认值是否是下一前沿（本轮无证据）、
  E6 的同 run 封存、门禁一律未点亮（载荷最后实读 `cfa0f118…`，`W30`/`p0-core` `promotable False`）。
- **不声称**：不声称 H1g 已通过或已合入，不声称 1.20.1 能加入，不声称 v2 路径解除了任何产品安全策略，不声称任何 case 闭合或门禁点亮，不声称 Minekin 完成。

## 第二十六轮（2026-09-27，M 主控）：H1g 双审通过并合入；M 自己造成的 43 处 pyright 红按协议补全；V4 派工

- **现场核对**：起点远端 `refs/heads/main = 0da7032`（上轮落点）。`git worktree list` 36 个（新增
  `../minekin-wt-h1g`、`../minekin-wt-v4`）。H1g 分支 `codex/minekin-joiner-local-v2-profile` 真实 merge-base
  `git merge-base main origin/...` = `0da7032`，`git diff --stat` 恰三个允许路径：`domain.sh +37`、
  `tests/contract/test_runner_scripts.py +356`、新记录 `docs/validation/v1201-joiner-local-v2-profile-2026-09-27.md`。
  **无 `src/**` 改动**——与「这一格的前言在 H 独占面」的判读一致。
- **双审 A（实现字节）**：+37 全在 joiner-profile 的内嵌 python heredoc 内，按本次 launched version 分派：
  1.21.4 仍走原 v1 文档，非 1.21.4 写 `schema_version 2` + `explicit_allowlist [version]` + 具名 loopback
  `target_authorization`，且**复用** v1 分支已有的 `host/port/auth_mode/resource_pack_policy` 值而非重述。
  交付字节 sha256 `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`（blob `19947e64…`），基线字节
  `f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5`；`domain.sh:404-407` 的 auto+joiner 拒止与
  `FORWARDED_VARIABLES` 未进 diff。
- **双审 B（测试质量）**：测试把 **shipped heredoc 抽出来跑**（`joiner_profile_writer_source` 截到 `\nPY\n`）并经
  真实 loader 判定，不是重述形状；分派字面 `if version != "1.21.4":` 与 `MINECRAFT_VERSION` 常量钉住；三份文档字面
  冻结（v1 `634abc28…`、v1@1.20.1 `24eddf0a…`、v2 `038dcf1e…`）；六个放宽形状各自具名拒止；四项反向
  （RV-0 `if False:`、RV-1 分支倒置、RV-2 放宽 allowlist、RV-3 host 移向 `198.51.100.20`）证明该判据非恒真。
- **M 的两个预登记判官在合入树上复量**（`.tmp/m-r27-review-gates.sh`，容器 `python`、`/src:ro`、规范卷 `:ro`）：
  judge A `rc=0` ⇒ `1.20.1 ⇒ ACCEPTED ManagedTargetProfile a51407f412850459`、
  `1.21.4 ⇒ ACCEPTED ServerProfile c74d94a4e4f99a81`（**与基线同值 ⇒ v1 的 1.21.4 冻结行为未漂移**，
  这一条是 M 独立量的，不依赖 lane 的断言）；judge B `rc=0`，12 项放宽形状逐项具名拒止。
- **合入树门**：容器五项 `rc=0`（`bash -n`、contract `37 passed`、case-assertions、fixture-digests、boundaries）；
  宿主 `ruff format --check` = `357 files already formatted`、`ruff check` = `All checks passed!`、
  `git diff --check` `rc=0`。**门载荷未动**：`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，
  `report_promotion` 仍 `status: blocked` / `rc=1`。规范卷只读由**真写探针**证明：
  `OSError: [Errno 30] Read-only file system: '/data/.m-r25-probe'`。**本轮零封证。**
- **M 自己造成的红，按补全而非屏蔽修掉**：合入前主干全仓 `uv run pyright` 有 **43 处错**，全在 M 上一轮写的
  `tests/unit/test_case_evidence_assertions.py`——`_Asserter` 协议没列出 OFFLINE 行读的常量成员与
  `asserter_inputs_bytes`，`ledger_row` 缺 `kin` 关键字。`518d199` 把这些成员**具名补进协议**（弃用的替代方案是
  `# type: ignore`，那会把真实的接口漂移重新藏起来）⇒ 全仓 pyright **0 错**。
- **M 的两处自纠（都不是结论级动摇，但都是错误措述）**：① 我曾把 3 个 pytest collection error 归因为「缺数据根」，
  复量后是 `ModuleNotFoundError: No module named 'jsonschema'`（镜像不装 dev group），已改正
  `.tmp/m-r27-review-gates.sh` 头注；② 该脚本把判官路径写死 `/src/.tmp`，复审 lane 树时读到 `rc=2`（文件不存在），
  改为 `M_SCRIPTS` 可覆盖——同字节的独立判官读数一直是 `rc=0`，所以判据本身从未可疑。
- **双进程竞争的坦白与核验**：H1g worktree 里同时有原 lane 会话与 M 的续投会话。M **只合并已推送的 ref**：
  `ab93668`（12:39，并 `dd76a1d`+`1edf1a4`）、`8b357b6`（12:42，并 `bbd8432`）。对未推的那份重复提交，M 在
  `ab93668` 正文里具名披露；随后量到 `bbd8432` 的 post-image blob `400cfa49` 与那份重复的 post-image **相同**，
  于是把这条更正写进后续 merge 正文而不是静默调和。lane 原会话最终以「达到轮次上限」结束（其最后一句
  「Full suite green (2604 passed)」与 M 自己的宿主复量同值）。
- **V4 派工前置两条按字节量清（`965dcc4`、`8715f25`，只动排期文档）**：① 1.20.1 桥**已构建**——
  `minekin-bridge-1201-0.0.0.jar` sha256 `e50d61c2…`、1310604 字节，在 `minekin/` 与 `minekin-wt-evidence/` 都在，
  在 `-integration`/`-h1g` 皆无 ⇒ 缺口是**放置**（`find_workspace_root` 把根定在被挂载的那份工作树），不是造不出；
  ② 规范卷三个大 Kin 存料**各 7565 blobs 且已含 1.20.1 工件**（按 blob 文件名尾串 grep 才量到——内容寻址布局下
  `-path "*1.20.1*"` 对 1.21.4 也返 0，那枚 0 就是自己的负对照）⇒ 播种代替 ~25 分钟 × 3639 文件的抓取。
  边界写进文档：**blob 在 ≠ launch 集合全**，判据只能是产品自己那行 `N of M artifacts are not in the store yet`。
  H1g 记录里的 ②c 供应拒止据此归因为「一次性空 store」，M 侧未复量。
- **V4 已派工（在工）**：worktree `../minekin-wt-v4`、分支 `codex/minekin-v4-local-join-after-v2`、base `8b357b6`。
  要求逐阶段 `PASS/FAIL/未达到该阶段`、一份新日期化 `docs/validation/` 记录、一枚 1.21.4 正对照、一枚版本错配反例，
  只连本次受控 runner 自起的 loopback 服。
- **四态**：已合主干 = H1g 的 `domain.sh +37`、契约测试 `+356`、其验证记录，以及 M 的 `518d199`（pyright 补全）与
  排期文档两处前置；仅在分支 = 无（H1g 分支已全部落干）；真实封证 = 零（本轮无 attempt、无 bundle、卷只读）；
  未验证 = **1.20.1 加入者 JVM 真起、Bridge 握手、JOIN/首快照**（V4 在量）、H1g 的 ②c 供应拒止成因（主控侧未复量）、
  E6 的同 run 封存、门禁一律未点亮（载荷 `cfa0f118…`）。
- **不声称**：不声称 1.20.1 已能加入（只声称 loader/契约层面越过了 `launcher.profile`），不声称任何 case 闭合或门禁点亮，
  不声称 V4 会通过，不声称 Minekin 完成。

## 第二十七轮（2026-09-27，M 主控）：合入后全量套转绿并落数；H1g 分支尾提交按 parent 核为快进后合入

- **合入树全量套（宿主 uv）**：`2604 passed, 3 skipped in 296.39s`（日志 `.tmp/m-r25-fullsuite-after-h1g.log`），
  对比基线 `2596 passed, 3 skipped in 295.78s`（`f82c368`）⇒ **+8**，恰为 H1g 的两项行为测试加六个具名拒止；
  无既测用例转红。
- **H1g 分支的尾提交 `b0c7a34`（12:43）审查**：真实 merge-base 已是主干内的 `bbd8432`，`git diff --name-only`
  只有一份验证记录（+20 -7）。它把「已合主干：无／仅在分支」改成按**合入时刻**记，并披露拓扑。M 逐句复核：
  `git show origin/main:test-orchestrator/runner/domain.sh | sha256sum` = `ff69c879…`（＝全部新字节读数所依据的那份）；
  `test_runner_scripts.py` 在 main 与分支同为 blob `471536f4…`、`domain.sh` 同为 `19947e64…` ⇒ 合并没改写被测量；
  `git log -1 --format=%P b0c7a34` 只有 parent `bbd8432` ⇒ **快进，未重写已发布历史**；它点名的压缩提交
  `0a42b2c`（tree `ce8db956`、parent `0da7032`）确为**未被引用的本地对象**、不在远端 ref 祖先里 ⇒ 「非快进被拒后停手、
  没有 force-push」这条披露为真。
- **合入与远端核验**：`cbe00ac = Merge branch 'codex/minekin-joiner-local-v2-profile' (H1g four-state dating)`，
  `git push origin HEAD:main` → `git ls-remote origin refs/heads/main = cbe00ac3e3553d345de9a57f108666ffa06844f7`。
  合入树上重跑审查门（`.tmp/m-r27-gates-cbe00ac.log`）：容器五项 `rc=0` + `37 passed`；judge A `rc=0`
  （`1.20.1 ⇒ ACCEPTED ManagedTargetProfile a51407f412850459`、`1.21.4 ⇒ ACCEPTED ServerProfile c74d94a4e4f99a81`）；
  judge B `rc=0`。纯文档增量，故未重跑宿主全量套（记 主控侧未复量）。
- **V4 仍在工**：`minekin-wt-v4` 工作树干净、分支尚无远端 ref（`git ls-remote origin | grep v4` 为空）⇒
  本轮没有可审的 V4 材料，M 不预判其结论。
- **全远端分支普查（第二十七轮重量，方法写在结论前）**：对 27 枚远端分支（不含 `origin/HEAD` 别名）逐枚
  `git merge-base --is-ancestor <branch> main` ⇒ 26 枚（含 `main` 自己）已在主干，唯一「非祖先」的工程/规划分支是
  `codex/parallel-execution-plan`（`ahead=2`、真实 merge-base `6f0f562`、1 文件 `+84`）。**但它没有待合内容**：
  主干上同名文件是**另一笔提交加进去的**（`git log --diff-filter=A -1 main -- docs/parallel-execution-plan.md`
  ⇒ `13b84a8`，subject 与分支那笔相同），且
  `git diff origin/codex/parallel-execution-plan:docs/parallel-execution-plan.md main:docs/parallel-execution-plan.md`
  给 `+27 / -4`，那 4 行减号是**主干后来扩写的四段**（版本行、V 行、H 行、冲突表）⇒ 主干那份是分支那份的超集。
  **教训：「不是 main 的祖先」不等于「有待审增量」**——分支内容若被重新落过干（此处 `23d04d5` 之后的回写就是这种情况），
  判据要落到 blob/内容比对，而不是只看 ancestry；否则每轮都会把这枚僵尸分支重新审一遍。
  ⇒ 本轮审卡队列实读为**空**（与第二十四轮那次同结论，理由不同：那次是「无未合分支」，这次是「唯一未合分支已被超集覆盖」）。
- **四态**：已合主干 = 上述全部（H1g 三枚分支提交 + M 的门/协议侧修复，远端尖 `cbe00ac`）；仅在分支 = V4（在工，尚无提交）；
  真实封证 = 零；未验证 = 1.20.1 真 JOIN/首快照（V4）、E6 封存、门禁（载荷 `cfa0f118…` 未动）、
  `metadata.py:16` 默认值是否下一前沿。
- **不声称**：不声称 V4 已达标，不声称 1.20.1 加入路径端到端可用，不声称任何 case 闭合、门禁点亮或 Minekin 完成。


## 第二十八轮（2026-09-27，M 主控）：V4 复审仪器预登记完毕，先抓出判官自己三处缺陷，再对在飞材料量到第一枚目标卫生读数

- **为什么要预登记**：V4 卡面有两句是否定式（「只连本次受控 runner 启起的本地 1.20.1 服」「操作员地址从未进入任何文件」）。
  否定式靠眼睛读是这里已经错过的同类断言，所以判官必须先于材料存在、必须先自证能抓到反面。
- **判官自检先转出三处真缺陷**（`.tmp/m-r27-v4-target-hygiene.py`，五例自测 `.tmp/m-r27-v4-hygiene-selftest.sh`，
  日志 `.tmp/m-r27-hygiene-selftest.log` 第一轮 → `.tmp/m-r27-hygiene-selftest-2.log` 修复后）：
  ① TEST-NET 文档段被判成 `rfc1918-private`（Python `ipaddress` 把三段文档地址都算 private）， planted 远程目标会读成普通内网跳，
  修法是把 `TEST_NET_PREFIXES` 判在 `is_private` 之前；② `::1` 完全不计（点分四段式看不见 IPv6），而 v2 准入确实容 `::1`，
  修法是单列 `IPV6` 捕获并要求 `::` 或 ≥3 枚冒号（否则 `12:50:03` 这类时钟读数会变成假端点）；
  ③ `keyed_target_values` 把 `profile[`、`*.sh` 路径当目标值（在 H1g 真实记录上实测到），修法是 `looks_like_host()` 先过滤。
  修复后五例逐条正确：clean 例 `loopback count=3` 且含 `::1`；反例例把 `198.51.100.20:25565`/`203.0.113.9` 具名为
  `test-net-documentation`、`10.1.2.3` 具名 `rfc1918-private`、`mc.attacker-target.dev` 具名 `domain-name`，
  `.sh` 路径不再出现在 keyed 行；操作员例 `operator_reference tokens=1` 且 `operator_token token=d861b7e9 hits=1`；
  空材料例打印 `endpoints_found=0 (VACUOUS …)` 而不是静默通过。
- **对 V4 在飞 scratch 的 hygiene 读数（中间读数，不是审查结论）**：`.tmp/m-r27-v4-hygiene-on-v4.sh`，
  三枚只读挂载（V4 工作树 `:/src:ro`、M 集成树 `:/m:ro`、主仓 `:/main:ro` 仅为按路径交出操作员参照，
  判官只输出 `sha8` 掩码，全脚本不打印地址），规范卷全程未挂载：
  `docker run --rm --entrypoint /bin/bash -w /src -v "${V4}:/src:ro" -v "${M}:/m:ro" -v "${MAIN}:/main:ro" minekin-runner:local -lc 'bash /m/.tmp/m-r27-v4-hygiene-on-v4.sh'`
  （日志 `.tmp/m-r27-v4-hygiene-on-v4.log`）。读数：`scanned_files=32`、`class loopback count=13`（全部 `127.0.0.1`／`127.0.0.1:25570`）、
  `keyed_target_values=7` 且逐条都是 `127.0.0.1`、**零** `rfc1918-private`／`test-net-documentation`／`link-local`／`multicast`／
  `other-external`／`domain-name`、`operator_token token=78168a76 hits=0`。这枚读数的非恒真性由上一节的反例自检提供。
- **V4 现场（本轮实读）**：分支 `codex/minekin-v4-local-join-after-v2` 仍尖 `8b357b6`（即派发时的 base），
  `git status --porcelain` 空、`origin` 上无该分支 ⇒ 尚未提交、尚未推送。工作树 `.tmp/v4/` 内已存在三条驱动：
  `drive.sh`／`launch.sh`／`drive_mismatch.sh`（版本错配反例），案例 `a` = 1.20.1 真跑，案例 `b` = `shape=v4b-live-1214`
  的 1.21.4 正对照（其 `00-header.txt` 自证 `/src/test-orchestrator/runner/domain.sh` 用字节 `ff69c879…`、桥 jar
  `minekin-bridge-1201-0.0.0.jar` sha256 `e50d61c2…`）。案例 `a` 的 `domain-join-session.json` 呈现
  `connection_state=PLAYABLE`、`snapshots_admitted=1`、`entities_admitted=11`、`perceived_information_class=PLAYER_EQUIVALENT`，
  台账事件序列含 `JoinObserved`→`PlayableEstablished`，宿主世界日志出现第二加入者行。
  ⇒ 形状与 E6 的放行条件一致，但**本轮不据此放行**：V4 的结论要由它自己的记录承担，M 的审查从「已推送的提交 + 允许面」起步。
- **四态**：已合主干 = 本轮无新增（远端尖仍 `98d1f47`）；仅在分支 = V4（在飞 scratch 材料，无提交）；真实封证 = 零；
  未验证 = 1.20.1 真 JOIN/首快照（scratch 读数待 V4 记录与 M 复审确认）、E6 封存、门禁（载荷 `cfa0f118…` 未动）、
  `metadata.py:16` 默认值是否下一前沿。
- **不声称**：不声称 V4 已达标或已通过（本轮只声称 hygiene 判官在 scratch 上零外部端点、操作员地址零命中），
  不声称 scratch JSON 等于已审记录，不声称任何 case 闭合、门禁点亮或 Minekin 完成。


## 第二十九轮（2026-09-27，M 主控）：V4 在飞材料被 M 三组独立读数覆盖，第二件复审仪器（逐阶段具名覆盖判官）预登记并自测通过

- **现场**：起点远端 `refs/heads/main = fbc3576`（第二十八轮 M 自己的提交）。V4 分支
  `codex/minekin-v4-local-join-after-v2` 仍尖派发基线 `8b357b6`，`git status --porcelain` 空、`origin` 上无该分支，
  `docs/**` 无新文件，`docker ps` 无在跑容器 ⇒ V4 在写记录前的空档；本轮 M **不**据 scratch 放行 E6。
- **卷边界读数（`.tmp/m-r28-v4-volume-boundary.log`）**：规范卷 `minekin-runner-data` 以 `:ro` 挂载后逐字段实读
  `14` 个 Kin 根、`99` 枚 bundle、匹配 `*v4*` 的 Kin 根 **0** 个，写探针 `[Errno 30] Read-only file system:
  '/data/.m-r7-write-probe'` ⇒ V4 没有碰 E 独占面。V4 私有卷 `minekin-v4-join` 内 `kin-v4-host / kin-v4-host1214 /
  kin-v4-join / kin-v4-join1214` 四根、`0` 枚 bundle、4 个 generation 目录（V4 卡面本就不封存）。
  本轮另留一次方法教训：`find /data/kin -maxdepth 3 -name manifest.json` 读到 `0`，是 glob 深度不足而非「没有 bundle」，
  正确深度实读为 `99`（与既有记忆里的错 glob 陷阱同类，改用不限深度后才有读数）。
- **门载荷未动**：`bash /src/.tmp/m-r7-baseline.sh` 在容器内（`/src:ro` + `/data:ro` + `MINEKIN_HOME=/data`）跑，
  日志 `.tmp/m-r28-baseline-fbc3576.log`：`gate_payload_sha256 cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、
  `promotable ['W00','W10','W20','W60']`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']`、`report_rc=1`（blocked 即预期形状）。
  ⇒ 第二十八轮那枚文档提交没移动门禁载荷。同一次读数先在宿主跑出了 `ModuleNotFoundError: No module named 'minekin_core'`
  与 `cd: /src: No such file or directory`——那是脚本该在容器里跑的工具形状，不是主干回归，按既有规矩先诊断再引用。
- **V4 scratch 的逐案形状（`.tmp/m-r28-v4-case-shapes.log`，中间读数）**：
  case A 交给加入者的文档是 `schema_version 2` + `host 127.0.0.1` + `auth_mode offline` +
  `allowed_versions ["1.20.1"]` + `target_authorization{granted_by: controlled-runner}`，客户端日志
  `Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`，joiner session 读到
  `connection_state=PLAYABLE / snapshots_admitted=1 / perceived_information_class=PLAYER_EQUIVALENT`；
  case B（`shape=v4b-live-1214` 正对照）文档仍是 `schema_version 1` + `minecraft_version "1.21.4"`，客户端
  `Loading Minecraft 1.21.4 with Fabric Loader 0.16.9`，同样 `PLAYABLE / snapshots_admitted=1`。
  两案都记录 `outcome=BRIDGE_LOST / session_state=STOPPED`（收尾形状），case A 宿主世界日志另有第二加入者行。
  ⇒ 版本没有互串（1.20.1 的 run 就加载 1.20.1），v1 的 1.21.4 形状未被改写；但**这仍不是 V4 的结论**，
  真 JOIN/首快照要由 V4 自己的记录承担、M 按允许面复审。
- **第二件预登记仪器**：`.tmp/m-r29-v4-record-coverage.py`（逐阶段具名 + 判定词 + 反例/正对照/桥 jar sha256/
  `127.0.0.1`/`schema_version 2`/runner 字节六项控制的形状门，缺项 exit 1）。
  四例自测（`.tmp/m-r29-coverage-selftest.sh` → `.tmp/m-r29-coverage-selftest.log`）：
  完整合成记录 `SHAPE_COMPLETE rc=0`；空心记录 **12 项**缺失（`first-snapshot NOT-NAMED`、五阶段 `verdict=NONE`、
  六项控制 `MISSING`）`rc=1`；真实 H1g 主干记录被判 `NEEDS_REVISION missing_or_unverdict=4 rc=1`
  ⇒ 判官并非恒绿，能区分「H 卡的记录」与「V 卡要求的形状」；不存在的路径打印 `record MISSING rc=1` 且不抛栈。
  已知宽松处如实登记：判定词是在「提到该阶段的任一分块」里找第一个，因此阶段名与 PASS 的**配对语义**不由它保证，
  它只保证六阶段各自具名且带判定词、六项控制在场；语义仍要 M 逐条读。
- **四态**：已合主干 = 本轮无新增（远端尖仍 `fbc3576`）；仅在分支 = V4（scratch 材料 + 三组 M 读数，无提交）；
  真实封证 = 零；未验证 = 1.20.1 真 JOIN/首快照作为**已审记录**、E6 封存、门禁（载荷 `cfa0f118…` 未动）、
  `metadata.py:16` 是否下一前沿。
- **不声称**：不声称 V4 已达标、已提交或已推送，不声称 scratch JSON 等于记录，不声称 E6 可放行，
  不声称任何 case 闭合、门禁点亮或 Minekin 完成。


### 第二十九轮补（同日，M 主控）：绕过 lane 抄出的副本，直接从私有卷的 `kin.sqlite3` 台账读加入者的阶段链

- **为什么单独记**：E6 的放行条件是「真达到 JOIN/首快照」。lane 抄到 scratch 的 `domain-join-session.json`
  是 runner 写的副本，产品自己写的载体是每个 Kin 的 SQLite 台账。M 读后者。
- **探针形状（先修工具再引用读数）**：WAL 模式的 `kin.sqlite3` **不能**只读打开——`sqlite3.connect("file:…?mode=ro", uri=True)`
  抛 `OperationalError: unable to open database file`，即使卷本身以 `:ro` 挂载。修法是把 `.db` 复制进容器 `/tmp` 再读，
  卷内零写入。脚本 `.tmp/m-r29-v4-ledger-read.sh`，日志 `.tmp/m-r29-v4-ledger-read.log`，
  复现：`docker run --rm --entrypoint /bin/bash -v minekin-v4-join:/d:ro -v "${REPO}:/src:ro" minekin-runner:local -lc 'bash /src/.tmp/m-r29-v4-ledger-read.sh'`。
- **读数（19 行事件，两案逐字节同构）**：`join-1.20.1` 与 `join-1.21.4` 的链都是
  `SessionStateTransitioned×2 → AuthPolicyFrozen → SessionProcessStarted → …WAITING_BRIDGE→HANDSHAKING → BridgeHelloAccepted →
  ResourcePackPolicyApplied → CONNECTING → JOINED_UNVERIFIED → JoinObserved{phase:JOIN_SEEN} → SessionIdentityCompared{matched:1} →
  PLAYABLE → PlayableEstablished → FAILED → STOPPING → STOPPED → SessionInterrupted{outcome:BRIDGE_LOST}`；
  状态序列 `PREPARING→STARTING_CLIENT→WAITING_BRIDGE→HANDSHAKING→READY_MENU→CONNECTING→JOINED_UNVERIFIED→PLAYABLE→FAILED→STOPPING→STOPPED`。
- **两条对后续证据设计有约束的发现**：① 台账里**没有任何快照事件**（`ledger snapshot events: NONE`），
  「首快照已准入」只存在于 session JSON 的计数器 `run.snapshots_admitted=1` 加客户端日志的
  `bridge collected 14 entity candidate(s) …, 14 confirmed visible`（1.21.4 案为 76/76）——因此断言「首快照」时
  必须点名这两处，不能暗示台账里有对应事件；② `PLAYABLE→FAILED→STOPPED / BRIDGE_LOST` 这个尾巴是**收尾形状**，
  1.21.4 正对照的台账以同样的方式结束，不能读成 1.20.1 独有的断裂。
- **lane 仍在跑**：私有卷出现第五个根 `kin-v4-c`（第三种情形），`git status --porcelain` 仍空、分支仍尖 `8b357b6`
  ⇒ 记录尚未写出、尚未提交。E6 依旧不放行。
- **四态**：已合主干 = 无新增（远端尖 `0e8522a`）；仅在分支 = V4（三案 scratch + 第五根 `kin-v4-c` 在跑，无提交）；
  真实封证 = 零；未验证 = V4 记录的形状与语义、版本错配反例、E6 封存、门禁（载荷 `cfa0f118…` 未动）。
- **不声称**：不声称台账读数等于 V4 的结论（阶段链是真的，但记录归 V4 写、复审归 M 做），不声称 E6 可放行，
  不声称任何 case 闭合、门禁点亮或 Minekin 完成。


## 第三十轮（2026-09-27，M 主控）：版本错配反例已量到非空转，V4 合入前的主干基线取妥

- **反例读数（`.tmp/m-r30-v4-counterexample.log`，中间读数）**：V4 的 case C 落在
  `.tmp/v4/out/c/{match,mismatch}.{err,session.json}` 四件上，M 逐字节读后成对成立——
  `mismatch.err` 是具名拒止 `{"category": "ADMISSION", "component": "launcher.profile",
  "message": "the session launches Minecraft 1.20.1, the target allows 1.21.4", "operation": "load",
  "retryability": "OPERATOR_ACTION"}`，且 `mismatch.session.json` **0 字节** ⇒ 那一侧连 session 文档都没写出，
  客户端 JVM 没起（这正是卡面要求的「拒止落在 JVM 之前」）；同形状的 `match` 侧 `match.err` 0 字节、
  `match.session.json` 1724 字节、`kin_id=kin-v4-c`、`connection_state=REQUEST_ACCEPTED`。
  ⇒ 差别只在目标允许的版本，一侧准入一侧拒 ⇒ 反向非空转。**注意形状**：match 侧只跑到 `REQUEST_ACCEPTED`
  就被收尾（`session_state=STOPPED`、`snapshots_admitted=0`），它是准入对照不是完整加入，别把它当第二枚 JOIN。
- **合入前基线（`.tmp/m-r30-premerge-baseline-0512f17.log`）**：在远端尖 `0512f17` 的树上跑
  `bash /src/.tmp/m-r27-review-gates.sh`（容器内、`/src:ro`、不挂规范卷）：五枚门
  `bash-syntax / contract-tests / case-assertions / fixture-digests / boundaries` **全部 rc=0**；
  M 判官 A 两枚都接受且**修订号与第二十六/七轮一致**——1.20.1 侧 `ACCEPTED ManagedTargetProfile a51407f412850459`、
  1.21.4 侧 `ACCEPTED ServerProfile c74d94a4e4f99a81`（⇒ v1 冻结行为无漂移）；判官 B 的 12 枚松形状逐条具名拒止
  （含「列两个版本」「授权字段缺失」「host 离开 loopback」「auth_mode 非 offline」「未审字段」等），`matrix rc=0`。
  ⇒ V4 合入后的同套读数若偏离这组数字，就是 V4 带进来的，而不是主干本来就红。
- **V4 现场**：分支仍尖 `8b357b6`、工作树干净、`origin` 无该分支；case C 四件写于 13:18，
  私有卷已有第五根 `kin-v4-c` ⇒ lane 在跑第三案之后、写记录之前。E6 依旧不放行。
- **四态**：已合主干 = 无新增（远端尖 `0512f17`）；仅在分支 = V4（A/B/C 三案 scratch，无提交）；真实封证 = 零；
  未验证 = V4 记录的形状与语义、1.20.1 真 JOIN 作为**已审结论**、E6 封存、门禁（载荷 `cfa0f118…` 未动）。
- **不声称**：不声称 V4 已达标/已提交，不声称 match 案完成了加入，不声称 E6 可放行，不声称任何 case 闭合、
  门禁点亮或 Minekin 完成。
---

## 第三十二轮（M）：复审 V4 的 1.20.1 活体加入复测，合入并按载体重读裁决三处超出

### 1. 现场核对

- 远端：`refs/heads/main = cfab3ff`（本轮合入前）；`refs/heads/codex/minekin-v4-local-join-after-v2 = 8d9189ed5a3d64a53f1f7c0d3113c753e1bde4b8`。
- 真实 merge-base：`git merge-base origin/main 8d9189e` = **`8b357b6`**（含 H1g 的那次基线，V4 未 rebase 未 merge）。
- V4 增量面：`git diff --stat 8b357b6 8d9189e` ⇒ **一份文件、193 行插入**：
  `docs/validation/v1201-local-join-after-v2-2026-09-27.md`。卡片允许面（V 私有根 + 一份新 `docs/validation/` 记录）兑现。
- 主控工作树 `main = cfab3ff`，`git status --porcelain -uno` 空。
- 合入前候选树：`git merge-tree --write-tree origin/main 8d9189e` = **`23e9655`**；
  `git diff --name-only origin/main^{tree} 23e9655` ⇒ 只多那一份记录；
  `git diff --name-only 0512f17 23e9655 | grep -v '^docs/' | wc -l` = **0**
  ⇒ 第二十九~三十轮在 `0512f17` 上量过的五门容器读数（`rc=0`）与全套基线**按字节继承**，无需重跑。

### 2. 把 V4 的关键判定从「记录转写」升级为「产品载体重读」

复现命令（三份日志都在 `minekin-wt-integration/.tmp/`）：

```bash
# m-r32-v4-review.sh：两个预登记判官 + 逐条摘要复核 + 规范卷边界
docker run --rm --entrypoint /bin/bash -w /src \
  -v <wt-v4>:/src:ro -v <wt-integration>:/m:ro -v <main-repo>:/main:ro \
  -v minekin-runner-data:/ro:ro -e PYTHONPATH=/src/src minekin-runner:local \
  -lc 'bash /m/.tmp/m-r32-v4-review.sh'
# m-r32b-v4-review.sh：判官 v2 自测 + 运行文档嵌套字段 + per-Kin 台账 + c 组在盘件
docker run --rm --entrypoint /bin/bash -w /src \
  -v <wt-v4>:/src:ro -v <wt-integration>:/m:ro -v minekin-v4-join:/v4data:ro \
  -e PYTHONPATH=/src/src minekin-runner:local -lc 'bash /m/.tmp/m-r32b-v4-review.sh'
```

逐字读数（`m-r32-v4-review.log` / `m-r32b-v4-review.log`）：

- **字节身份全部相等**：`domain.sh = ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`；
  v2 加入者文档 `038dcf1e7331884a91a7c795d3b1ef8960d80405b049d1c5fc270df9fbb1f771`（`schema_version=2`、
  `minecraft_version` **ABSENT**、`version_policy={"mode":"explicit_allowlist","allowed_versions":["1.20.1"]}`、
  `target_authorization.granted_by=controlled-runner`）；1.21.4 冻结 v1 `634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137`
  （`schema_version=1`、`minecraft_version` PRESENT）；两枚桥 jar `e50d61c2…`、`0ee2070b…`；
  c 组 crash `1917cd55…`、stderr `f88c93af…`。`out/a/00-header.txt` 里那两行身份逐字在盘。
- **阶段判定（记录只给了转写，M 读的是运行文档，字段嵌套在 `run` 下）**：
  run a 加入者 `kin-v4-join` / session `3629bff1c1894a8292b024ebfe878bf3`：
  `connection_state=PLAYABLE`、`snapshots_admitted=1`、`snapshot_rejections=[]`、`entities_admitted=11`、
  `entities_rejected=3`、`perceived_information_class=PLAYER_EQUIVALENT`、`world_snapshot=null`、`outcome=BRIDGE_LOST`；
  host 半边 `lan_publication={phase: LAN_OPENED, port: 25570}`、`world_snapshot.digest=5c14c563…`；
  run b（1.21.4 正对照）加入者 `PLAYABLE`、`snapshots_admitted=1`、`entities_admitted=73`。
- **per-Kin 台账（`kin-v4-join/kin.sqlite3`，19 行，先 `cp` 出卷再读——WAL 只读打不开）**：
  `SessionProcessStarted → BridgeHelloAccepted → JoinObserved → SessionIdentityCompared → PlayableEstablished → SessionInterrupted`；
  `WorldSnapshotAdmitted: False` ⇒ 「首快照」在台账里**没有事件载体**，只有计数器 + 客户端日志行。
- **⑤ 家族**：run a 的 `/tmp/domain-session.err`、`domain-join-session.err`、`domain-client-environment.err` 全 0 字节、
  `0x1000E=0`、`XDG-invalid=0`；c 组裸驱动在盘原件里两串各 1 命中，crash 第 7 行逐字
  `java.lang.IllegalStateException: Failed to initialize GLFW, errors: GLFW error during init: [0x1000E]135947197726096`。
- **握手与加入行**在 run a 自己的 `90-readouts.txt` 里逐字在盘：`CONNECTION_PHASE_LOGIN_NEGOTIATING`（194 行）→
  `PLAY_INIT`（195）→ `JOIN_SEEN`（196）、`222:[04:55:52] [Server thread/INFO]: Kin2 joined the game`。
- **反证半边**：`out/c/mismatch.err`（230 B）逐字 `{"category": "ADMISSION", "component": "launcher.profile", … "message": "the session launches Minecraft 1.20.1, the target allows 1.21.4", …}`；
  `out/c/match.err` 0 B、`mismatch.session.json` 0 B（JVM 前被拒 ⇒ 无会话文档，形状自洽）。
- **规范卷边界**：卷上 `*v4*` 命名条目 **0**；`kin_roots=14`、`manifest=112`（E 的 B2 证据提交并入后计数从 99 涨到 112）、
  `manifests_newer_than_H1g_domain_bytes=0`；V4 私有卷 `minekin-v4-join` 里 5 个 Kin 根、`manifest=0` ⇒ V 没封存、E 的独占窗完好。

### 3. 卫生判官：两份 negation 现在是量出来的

`m-r27-v4-target-hygiene.py --scan <V4 记录> --operator-file /main/.tmp/local-test-server.txt`（操作者地址按路径交给判官，输出只报掩码）：

```text
operator_reference tokens=1 (reported masked only)
scanned_files=1
class loopback                   count=5   （127.0.0.1 / 127.0.0.1:25570 / ::1）
operator_token token=78168a76 hits=0
hygiene_rc=0
```

零外部/零 rfc1918/零 TEST-NET/零域名/零 keyed 远程目标；「没连远程服」与「没写入操作者地址」两条否证各有计数与行号。

### 4. 形状判官的两处自身缺陷（**看到 V4 材料之后才修**，如实申报）

`m-r29-v4-record-coverage.py` 第一次跑 V4 记录给出 `NEEDS_REVISION missing=1`，其中两项是判官自己的错：

1. `bridge-handshake NOT-NAMED`：模式 `桥\s*握手` 认不出记录写法「Bridge 握手」，而该行表格里有 `**PASS**`。
2. `session-start verdict=FAIL (block@125)`：判定词按**裸子串**匹配，把被引的崩溃原文 `Failed to initialize GLFW` 读成了 FAIL——
   一段“否证性引用”冒充了判定。全记录里 `grep -n "FAIL"` 命中数为 0。

修正（脚本内已写进注释，未改判据要求本身）：握手识别加 `桥?\s*握手`/`BridgeHelloAccepted`；判定词改词边界匹配并计数（`PASS×N`）；
markdown 表格行自成一个 block（七项读数型记录就是把判定挂在行上）。修后自测仍**说不**：
合成空壳记录 12 项 `rc=1`、主干 H1g 记录 6 项 `rc=1`、合成完整记录 `SHAPE_COMPLETE rc=0`、路径不存在 `record MISSING rc=1`。

对 V4 记录修后读数：`launcher-profile/client-jvm/bridge-handshake/join/first-snapshot` 全部 `named≥3 verdict=PASS×1`，
六项 control 全部 present；**剩余唯一一项** `session-start verdict=NONE`——`session start` 只出现在 §2 命令形状与 §5 反证块里，
那些块不带判定词。M 裁决：这是**记录形状**问题而非阶段缺失，因为该阶段的事实由运行文档独立证实
（`argv_digest=39ae79fb…`、`started_at=2026-09-27T04:55:08Z`、台账 `SessionProcessStarted`）。不为此退回 V4 重写。

### 5. 三处超出/缺陷的裁决（写进 merge 提交信息）

1. **§1.1b 复制 1.21.4 桥 jar**（卡片只开了 `bridge-1201` 那枚的口子）：**接受**。gitignored、M 复核
   `0ee2070b97ba6583ca004cc3f0e4a0e547697d0693dc635c3143c655cc2475f4` 与 fixture pin 逐字相等、
   且它是卡片自己要求的正对照的前置；不构建成、不编造取料源。
2. **§6 披露 1：a/b 的 harness stderr 行属 `docker logs` 转写**（容器已删）：**接受为 V 侧读数**，但据此立一条约束——
   **E6 的封存面不得依赖转写行**，须以运行文档 + per-Kin 台账 + 在盘原件为准（M 已在派工简报里写死）。
3. **M 新发现：§5 现场种下的 `match.json`/`mismatch.json` 母文档未随材料保留**（`out/c` 只剩输出侧，
   `allowed_versions` 只在 `run-console.log` 里出现过）⇒ 「只改一个字段」无法从盘上重放，反证可重放性降级；
   **E6 必须自种反证件并保留 sha256**，不得引用 V4 的文档。

### 6. 合入与推送

- `git merge --no-ff -F .tmp/m-r32-merge-msg.txt 8d9189e` ⇒ **`7b994853fe52ef6b87facb3c81922b1fcc01f5c6`**；
  `push origin HEAD:main` ⇒ `cfab3ff..7b99485`；`git ls-remote origin refs/heads/main` 回读 **`7b994853fe52ef6b87facb3c81922b1fcc01f5c6`** = 本地 HEAD。
- 派工 **E6 `V1201-LOCAL-JOIN-SEAL-001`**（后台子代理，工作树 `minekin-wt-e6`，分支 `codex/minekin-v1201-join-seal`，起点 `7b99485`）：
  派工前 `docker ps` 为空 ⇒ 规范卷独占写窗成立；简报里绑死允许面（新 Kin/attempt/bundle + 一份新记录）、
  四读（verify/rejudge/replay/report_promotion）、非恒转反证、以及第 5 节三条约束与「首快照无 joiner 摘要载体」的措辞限制。

### 7. 四态

- **已合主干**：H1g（`ff69c879…`）、V4 的 1.20.1 活体加入复测记录（merge `7b99485`，远端已核）。
- **仅在分支**：E6 `codex/minekin-v1201-join-seal`（刚派出，尚无提交）；B1-b 之后的 E 侧余料与既有停放分支不变。
- **真实封证**：**仍为零**——V4 是 V 私有活体读数，E6 尚未在规范卷产出 bundle。1.20.1 本地加入的「JOIN/首快照/PLAYABLE」
  现在有主控独立重读的活体证据（运行文档 + 台账 + 在盘原件 + 字节摘要），但它不等于 sealed evidence。
- **未验证**：`::1` IPv6 loopback 形状、`--auto-bundle`×joiner、多 joiner/并发、在线认证、任何远程目标（不连）、
  PLAYABLE 之后的输入/动作半边、1.20.1 的**规范卷封存**（正是 E6 要问的）。主控侧未复量项一律沿用记录原口径。

不声称：本轮没有推进任何判据/registry/封存 schema，没有提升门禁，没有触碰 V08 或用户远程服；
V4 的记录通过复审只意味着「1.20.1 真到达可封的 JOIN/首快照」这一前置成立，不意味着 1.20.1 已有封存证据。
---

## 第三十三轮（M）：E6 在工期间的独立安全任务——把「封存复审判官」在材料存在之前预登记并标定

E6 `V1201-LOCAL-JOIN-SEAL-001` 已派工（分支 `codex/minekin-v1201-join-seal`，起点 `7b99485`），此刻尚未推送提交
（`git ls-remote` 无该 ref；`docker ps` 为空）。审卡队列另一轴复量仍为空（唯一未合分支是已定性的僵尸 `origin/codex/parallel-execution-plan`
`e472897`：base `6f0f562`、ahead 2、1 份 docs 文件、非 docs 差异 0）。所以本轮做的是**下一张卡的判据工具**，
按惯例在 E6 的 bundle 存在之前写好并标定。

### 1. 新预登记工具：`minekin-wt-integration/.tmp/m-r33-e6-seal-review.py`（+ 自测 `m-r33-e6-seal-selftest.sh`）

它复审的是**封存件本身**，不是记录对封存的转述：manifest 声明的每一件工件逐个重算 `sha256`+`size`；
缺失/摘要不符/在场未申报三类分开计数；账本时间线载体名与封存侧车名**都从产品源码常量解析**
（`LEDGER_TIMELINE_ARTIFACT`、`DIGEST_NAME`，见 `src/minekin_core/adapters/evidence/trace.py:73`、
`src/minekin_core/adapters/evidence/bundle.py:36,147,231-232`），不按业务词猜字符串 —— 这是上一轮
「拿 `ledger` 去搜工件名结果错判缺载体」的直接教训落地；侧车内容还要等于 `sha256(manifest bytes)`；
载体逐行 JSON 解析并 demanded 事件名（`--require-event JoinObserved …`）；`--require-snapshot-counter`
要求某件申报的 JSON 真的带 `snapshots_admitted`；`--expect-case` 要求该 case 在 `tests/fixtures/cases` 已登记。
任何一项不满足 `rc=1`。

### 2. 标定读数（卷全程 `:ro`，破坏性动作只做在容器 `/tmp` 的拷贝上）

```bash
docker run --rm --entrypoint /bin/bash -w /tmp \
  -v <wt-integration>:/m:ro -v minekin-runner-data:/data:ro -e PYTHONPATH=/m/src \
  minekin-runner:local -lc 'bash /m/.tmp/m-r33-e6-seal-selftest.sh'
```

- **正对照（真件未动）**：`kin-e-aba/run/evidence/7ff026e4…`（`case_id=OFFLINE-100`、
  `case_version=a44289e8cdbc0643`、`schema="minekin.p0.evidence.v1"`）⇒
  `declared=13 verified_ok=13 mismatch=0 absent=0 present_not_declared=0`、
  `carrier=bridge-trace.jsonl rows=19`、`seal_sidecar … MATCH`、`bundle_check=PASS rc=0`。
- **反证八格全部被点名**（各 `rc=1`）：删掉最大工件 ⇒ `absent=1`；追加一字节 ⇒
  `digest/size mismatch … declared f01ce04a59e4/34005 measured 1c0c4970d8f7/34012`；加未申报文件 ⇒
  `present_not_declared=1: planted-undeclared.txt`；清空载体 + 索要 JOIN 事件 ⇒
  `rows=0 kinds=[]` + `carrier 'bridge-trace.jsonl' is empty` + `carrier names no 'JoinObserved' row`；
  空卷 ⇒ `NO bundles found … this is a MISS, not a pass`；不存在的 case ⇒ `NOT registered`；
  伪造侧车 ⇒ `declared=f000000000000000 measured=0cc1fb99111d4cef MISMATCH`；
  从 manifest 里抽掉 `run-document.json` ⇒ `no declared JSON carries snapshots_admitted`（同时被抓到侧车不符）。
- 一处自测预期落空也要如实记下：自测 case 6 本想让「向一枚非 JOIN 件索要 `JoinObserved`」显红，
  结果那枚 **OFFLINE-100** 件的载体里本来就有 `JoinObserved`/`PlayableEstablished` 两行 ⇒ `rc=0`。
  所以事件轴的「能说不」由 case 5（清空载体后 `names no 'JoinObserved' row`）承担；
  这同时说明该判官的事件要求**不能**被当成区分 JOIN 与否的判据，只是载体完整性判据。
- 过程中判官自身也被纠了一格：真 bundle 里 `bundle.sha256` 是**产品自己的封存侧车**，
  第一版把它报成 `present_not_declared` ⇒ 白名单改为从 `DIGEST_NAME` 常量解析并**反向校验其值**。
  该修正在看到正对照材料之后做出，如实申报；修正后正对照 `rc=0`、七格反证仍全部 `rc=1`。

### 3. 顺带量到的一条实质事实（收窄 E6 的措辞风险）

已封的 OFFLINE-100 件里 `run-document.json` 就是**首快照计数的封存载体**：逐字
`snapshots_admitted=1 rejections=[] world_snapshot=null`。⇒ 「首快照」**不需要**扩封存 schema 就能封
（此前担心的「无载体」是错的：载体是工件，不是台账事件名）；同时 `world_snapshot=null` 也再次证实
**加入者侧没有快照摘要**，摘要只在 host 半边。E6 的允许面因此不变，其记录措辞按第二十九条约束执行。

### 4. 规范卷只读普查（本轮）

`/data/kin` 下 `manifest.json` = **99** 份，卷上全量 = **112** 份，差值 13 份全部在 `repo-evidence/`
之下（仓库自检通道本就没有 bridge 会话）—— 与 `project-ledger-timeline-carrier` 记录的正对照口径一致；
`kin_roots=14`；`*v4*` 命名条目 **0**（V4 未写过规范卷）。

### 5. 四态

- **已合主干**：不变（H1g `ff69c879…`、V4 记录 merge `7b99485`、本轮之前的主干文档 `9a13dbd`）。
- **仅在分支**：E6（已派工、无提交）；僵尸分支 `e472897` 维持不追认。
- **真实封证**：**仍为零新增**——本轮只读了卷上**既有** sealed bundle 来做判官标定，没有产出一份新证据；
  1.20.1 本地加入的规范卷封证依然是 E6 要交付的东西。
- **未验证**：E6 的 run/bundle/attempt、四读（verify/rejudge/replay/report_promotion）与它的反证；
  `::1`、`--auto-bundle`×joiner、多 joiner、在线认证、远程服、PLAYABLE 之后的输入半边。

不声称：本轮没有触碰规范卷写权限、没有改判据/registry/封存 schema、没有替 E6 预先判定它的结论；
判官 `rc=0` 只说明封存件自洽，不等于该 case 的门禁断言为真（那仍是 `rejudge` 的读数）。

## 第三十四轮：E6 在工期间的边界预审与 CI 收口（主控只读）

主控本轮不合并任何东西（E6 尚未 push），做的是两件可留档的只读量：把我自己三次 push 的
CI 读数补成闭环，以及在 E6 落 bundle 之前把它选案与判据载体的对应关系量清楚，好让复审能按
「最先失败层」归因而不是照抄 lane 的措辞。

**CI 收口（REST 实读，非推断）**：`GET /repos/printlndarling/minekin/actions/runs?head_sha=…`
对 `9a13dbd`、`7b99485`、`9d45b60` 三个主干 SHA 均 `status=completed / conclusion=success`；
`9d45b60` 的 run `36298060824`（run_number 825）在 05:46:29Z 收敛。`main` 远端 ref 仍为
`9d45b608df4b8172950fa0830bdb039870d4340a`。

**E6 的现场读数（只读，零写入）**：worktree `../minekin-wt-e6`、分支
`codex/minekin-v1201-join-seal`、HEAD 仍是 base `7b99485`、工作树干净、远端无 ref；卷上新建
`kin-e6-j020`、`kin-e6-ctr`，`.tmp/e6/` 依次出现 `e6-prep.sh`（13:43）、`e6-live.sh`/`e6-drive.sh`
（13:46/13:47）、`e6-reads.sh`（13:47）、`e6-counter.sh`（13:48）；规范卷 manifest 仍 112，
即**封证尚未落地**。PRE 读数：`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`
（与主干基线逐字节相同），`report_rc=1`，`overall_blocks=['REQUIRED_CASE_NOT_REGISTERED']`。

**驱动脚本的边界预审（读 `e6-drive.sh` 全文得到，非其自述）**：它驱动主干原样
`test-orchestrator/runner/domain.sh`（脚本内先 `sha256sum` 具名）、用**已登记**的 case
`V1201-020`、对新 Kin `kin-e6-j020` 跑一轮、由 `domain.sh` 自己封存并自检，再把 `/tmp/domain-*`
与本轮 `server-runs/run-*` 的材料拷到 out；脚本显式打印 `/src` 与 `/data` 的可写性。
⇒ 没有新造 case id、没有改判据、没有仓库码改动，写面只在 E 自己的新 Kin；**不越主控保留决策门**。

**选案语义的对应关系（`tools/assert_case_evidence.py` 源码实读）**：V1201-020 的三条断言恰好是
1.20.1 加入链本身——`first_snapshot_admitted`（:1444）要 `join_line` + `run.snapshots_admitted ≥ 1`
+ `connection_state == "PLAYABLE"`；`leave_after_join_observed`（:1514）要服务端「joined the game」
行早于「left the game」行；`server_observed_join_identity`（:1054）要服务端按名字派生的 offline
UUID 与日志记录相等。V4 已量到的材料对上前两条（`snapshots_admitted=1`、`PLAYABLE`；
`:222 04:55:52 Kin2 joined the game` 与 `:225 04:56:10 Kin2 left the game`），第三条只能由 E6
bundle 里 asserter 自己的读数定，故列为复审必核项。该案 `mandatory: false` ⇒ 封成不会自行推门，
门推进仍归主控决策。

- **已合主干**：H1g、V4 的 1.20.1 活体加入记录、M 的 r32/r32b/r33 仪器与判官（`main = 9d45b60`）。
- **仅在分支**：E6 的 live 封证在工、零提交、未 push。
- **真实封证**：1.20.1 本地加入的规范卷 bundle 仍为 0。
- **未验证**：E6 的 seal/verify/rejudge/report_promotion 四读、三条断言的实际结论、版本错配反例
  原物是否保留、POST 门载荷增量。

**续接点（下一轮照此执行，无需重新设计）**：`.tmp/m-r34-e6-review.sh` 后台等 ref，出现即自动跑
`git merge-base`＋非 docs 改动面＋卷内 E6 bundle 普查＋`python /m/.tmp/m-r33-e6-seal-review.py
--volume /data --repo /src --bundle <新 bundle> --require-snapshot-counter`（`:ro`）。日志落
`.tmp/m-r34-e6-review.log`。

不声称：本轮没有任何 1.20.1 封证；预审只证明 E6 的**边界与选案语义**在门内，不证明它的 run 为真。

## 第三十五轮：E6 的 bundle 先于其 push 出现，主控做只读早读

E6 在写卡面之前先把 live 封证落到了规范卷：`/data/kin/kin-e6-j020/run/evidence/73a52bfb8f24462794ff571c46267e2e`，
卷上 manifest 从 112 增到 113。lane 仍零提交、远端无 ref ⇒ 主控**不能合**（只合已 push 的 ref），
但把复审证据先取下来存盘，日志 `.tmp/m-r34b-e6-bundle-early-read.log`（脚本 `.tmp/m-r34b-e6-bundle-read.sh`，
全部 `:ro` 挂载、host 侧重定向，容器内实读 `/src writable False`）。

**封存件自身的读数（产品记录，非 lane 转述）**：`case_id=V1201-020`、`case_version=e7c3b72235d90766`、
`schema=minekin.p0.evidence.v1`、`result="PASS"`、`assertions.failures=[]`，三条 expected 全部 observed
（`server_observed_join_identity` / `first_snapshot_admitted` / `leave_after_join_observed`）；
`world.server_config_digest=77a19c94c4467231…`；环境行具名 `openjdk 21.0.12.1 Temurin-21.0.12.1+1`、
`llvmpipe (LLVM 20.1.2, 256 bits)`。

**主控独立重算（不采信产品自检）**：声明 12 个 artifact 逐一重哈希与重量 ⇒
`verified_ok=12 digest_or_size_mismatch=0 absent=0 present_not_declared=0`；
`bundle.sha256` 边车 `b2b4133b3e3ce030` 等于主控对 manifest 字节重算的 sha256；
时间线载体 `bridge-trace.jsonl` 19 行，含 `SessionProcessStarted / BridgeHelloAccepted / JoinObserved /
PlayableEstablished / SessionInterrupted`；`run-document.json` 里 `snapshots_admitted=1 rejections=[]`。
run 用的字节仍是主干字节：`domain.sh ff69c87994f15be3…`、1.20.1 桥 jar `e50d61c209be9813…`。
判官的 rc=0 有非恒真保证：r33 的八项植入缺陷各自 `rc=1`（`.tmp/m-r33-e6-seal-selftest-2.log`）。

- **已合主干**：H1g、V4 记录、M 的 r32/r32b/r33 仪器、第三十四轮 handoff（`main = 43a0ed3`，远端已核）。
- **仅在分支**：E6 的卡面文档与提交（bundle 已成形，仓库侧尚无 commit、未 push）。
- **真实封证**：1.20.1 本地加入的规范卷 sealed bundle **首次非零 = 1**（`73a52bfb…`），
  M 独立重哈希与载体读数均为 PASS。
- **未验证**：`evidence verify` / `rejudge` / `report_promotion` 三项的主控亲跑、POST 门载荷增量、
  版本错配反例原物是否随卡保留、E6 的 `docs/validation/` 记录本身。

不声称：bundle 的 `result="PASS"` 只说明该案 asserter 在这份封存件上判为通过，不推进任何门禁
（V1201-020 是 `mandatory:false`，门载荷预期仍含 `REQUIRED_CASE_NOT_REGISTERED`）；也不说明
1.20.1 加入链的其余未测面（多 joiner、在线认证、远程服、PLAYABLE 之后的输入半边）已被覆盖。

**续接点**：E6 push 后 → 核 ref → `merge-base`＋非 docs 改动面应为 0 → 主控亲跑
`evidence verify`/`rejudge`/`report_promotion` 并量 POST `gate_payload_sha256` → 卫生判官带
`--operator-file` 过它的记录 → 单卡合入、`push origin HEAD:main`、核远端 SHA → 第三十六轮四态回写。

## 第三十六轮：E6 收口——1.20.1 本地加入的规范卷封证合入主干

lane 提交并 push `954b47a6f9fb0255ae4107c5dd908a76d86bec7a`（真实 merge-base `7b99485`，
改动面只有 `docs/validation/v1201-local-join-seal-2026-09-27.md` 一份，`nondocs=0`），
主控单卡合入并推远端：`main = eba5821eb58b85d0df3c65415a3b7010121fc15a`（`git ls-remote` 回读同值）。

**主控亲跑四读（规范卷 `:ro`、`/src writable False`，日志 `.tmp/m-r36-e6-reads.log`）**：
`python -m minekin_core evidence verify 73a52bfb…` ⇒ `result=PASS verified=true artifacts=12 violations=[] rc=0`，
bundle 摘要 `b2b4133b3e3ce030542ddb99aa18c6dd48bff60a36a62a75da2d7330865da8d9`；
`tools/rejudge_evidence.py` ⇒ `status=agrees rc=0`，三条断言 `failures=[]` 且 observed 齐（`server_observed_join_identity /
first_snapshot_admitted / leave_after_join_observed`）；`tools/replay_evidence.py` 与 `python -m minekin_core replay`
两侧 `rc=0 status=projected`，19 事件投影到 `STOPPED`，`trace_sha256=b803bce5cbbaf474…`；
`tools/report_promotion.py` ⇒ `rc=1`，`POST gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`
**与 PRE 逐字符相同**，`W40 promotable=False blocks=['REQUIRED_CASE_NOT_REGISTERED']`，`promotable=['W00','W10','W20','W60']`，
`attempts 76→77`、`bundles 112→113`，V1201-020 四 seq 全 `PASS/AGREES`，seq4 `from_repository_build=True`。

**反例与卫生**：版本错配反例留了原物（`.tmp/e6/out/counter/mismatch.stderr` 逐字为
`{"category":"ADMISSION","component":"launcher.profile","message":"the session launches Minecraft 1.20.1,
the target allows 1.21.4"}`，配对文档 `mismatch.json` 是 `schema_version 2`、`allowed_versions:["1.21.4"]`、
`host 127.0.0.1`），并配了真起 JVM 的成对控制——V4 那一格「反例文档未留」的缺已补。
记录文本 179 行、`sha256=a61b58391ded6c8eaadf52477e64923fdb8d3de71e553aa738abd299caa65807`；
按路径比对操作者目标地址：`hits=0`，且同一扫描对地址文件本身 `self_hits=1`（正对照非恒真）；
记录内 IP 形状只有 `127.0.0.1`（4 处）与 `::1`（1 处）。

**主控裁决 D1（E6 申报的超出）**：专服形状需要 `/server/server.jar`，卡面只点名桥 jar；E6 用
`run_controlled_server.py` 自 pin 的字节（sha1 `84194a2f…`／47791053 B 双测）复制进自己的 `.tmp`，
**没有重构建、没有改仓库码**。裁决：接受——它是受控 runner 物料的取用，不改判据也不入仓库；
约束是记录必须具名其摘要（已具名），且不得据此声称 pin 集变化。

- **已合主干**：H1g、V4 活体复测记录、E6 封证记录（`main = eba5821`，远端已核）；M 的 r32–r36 仪器与日志。
- **仅在分支**：无待审 lane 交付（E6 已收口）。
- **真实封证**：1.20.1 本地加入在规范卷上有 **1 个 M 逐字节复验过的 sealed bundle**
  （V1201-020 / seq4 / `73a52bfb…` / `b2b4133b…`），当前 build 真跑、rejudge `agrees`。
- **未验证**：门禁推进（`W40` 仍不可提升，要动 `mandatory` 或登记属主控保留决策）、
  跨 bundle 证据链载体、快照摘要扩字段、`::1` 半边、`--auto-bundle`×joiner、多 joiner、在线认证、
  V08 远程服、PLAYABLE 之后的输入半边。

**下一格待定（不在本 goal 自行推进）**：是否让 seq4 替换 registry 引用、是否把 V1201-020 升级为
`mandatory`——两者都会动门载荷，均归用户主控决定。

不声称：合上这份记录不等于 1.20.1 加入链已经门禁化或产品完工；它只把「真跑到 JOIN/首快照」
从 lane 的转述升级成规范卷里可重哈希、可重判的封存件。

## 第三十七轮：规划分支 `codex/minekin-local-control-next` 合入，H1h 开工（LAN 加入者限幅控制驱动）

### 恢复现场读数（本轮亲量）
- 远端 `main` = 本地 `main` = `24ac6e0ee69cb1926fb4ce5c8439834caaa37fb3`；integration 工作树 `git status --porcelain` 空。
- 38 个 worktree；`minekin-runner-data` 卷存在且**没有任何运行中容器挂载它** ⇒ 规范卷写窗空闲（本轮 H1h 不封证，派工命令里明确禁止挂载）。
- 卷内既有计数沿用上一轮读数：`kin_roots=16`、`manifests=113`、attempts 77。

### 规划分支审查与合入（`0552e10` → merge `24ac6e0`）
- 真实增量：`git diff --name-only d26a2dd 24ac6e0 | grep -v '^docs/' | wc -l` = **0**，纯文档规划。
- 两条承重 claim 由 M 复量后才合：
  1. **E6 的 `V1201-020` seq4 是「本地专服 + 单客户端」形状**，不是 V4 的 LAN 第二客户端——合入前 M 已按 `MINEKIN_DOMAIN_CASE=V1201-020` + `--server-profile …controlled-offline-server-1.20.1.json` 的命令行形状与卷内 run document 复核；结论：范围缺口，不是 bundle 失效。
  2. **registry 现有引用仍为真**：`tools/verify_tested_provenance.py --data-root /data` 从 integration 树跑会 `BRIDGE_JAR_MISSING`（构建产物不在此树），改从持有两份桥 jar 的 `../minekin-wt-v4` 跑 ⇒ `rc=0`、两个条目 `verified True`、`findings []`。本轮不替换引用、不翻 `mandatory`。
- CI：run `36301474388` = `completed / success`。

### H1h 派工前 M 亲量的事实（决定这张卡零产品改动）
- `test-orchestrator/runner/domain.sh`@`ff69c879…`：加入者的产品调用（`:1179-1184`）只有 `session start --profile "${profile}" --server-profile /tmp/domain-join-profile.json`，**没有任何控制旗标** ⇒ 今天的 LAN 加入者是纯 observe-only。
- `src/minekin_core/cli/parser.py`：`session start` 已接受 `--hold-forward-seconds`(`:115`)、`--hold-strafe`(`:130`)、`--hold-jump/--hold-sneak`、`--hold-use-seconds`、`--hold-at`(`:165`, `playable|join`)、`--look-yaw-degrees`(`:172`)、`--look-pitch-degrees`(`:179`)；hold 只「needs `--server-profile`」，而加入者本就传它。
- `src/minekin_core/cli/session.py`：`:1072-1078` 拒「有轴无时长」、`:1100-1103` 拒非正时长、`:788-792` 产品自己已限幅单次 look、`:538` `select_kin(root, kin_selector)`；加入者进程启动时已注入 `MINEKIN_KIN_ID="${joiner}"`(`~:1166`) ⇒ **lease 天然定向第二客户端，不需要新产物 API**。
- 由此派工面收窄为：runner 侧默认关闭 + 硬限幅（一次 look、forward ≤ 2 s、随 run 结束释放）+ 契约级 A/B/C/D 读数，禁止 `src/**`、禁碰 `:400-406` 的 auto+joiner 拒止、禁碰 `FORWARDED_VARIABLES`。
- 工作树 `../minekin-wt-h1h`，分支 `codex/minekin-lan-joiner-bounded-control`，base `24ac6e0`。

### H1h 的预登记复审判据（M 在 lane 交付前写下，不事后发明）
1. **默认关闭等值**：未设 opt-in 时加入者 argv 与 `24ac6e0` 的形状逐字节等值（这是 v1/1.21.4 冻结行为的回归护栏，必须是有提交的契约测试而非口头断言）。
2. **限幅是拒止不是钳制**：越界（如 `yaw=90`、`forward=10`）具名拒止且该 argv 不出现；无 joiner 而 arm 具名拒止。
3. **不变量未被顺手改动**：`domain.sh` 的 auto+joiner 拒止段、`--hold-at join` 的拒止语义、`config.FORWARDED_VARIABLES` 全部保持原字节；`git diff --name-only 24ac6e0 HEAD` 只允许 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/` 记录。
4. **门载荷不动**：H1h 不注册 case、不动 registry ⇒ `gate_payload_sha256` 必须仍是 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`；lane 若报出别的值即为越界。
5. **不得越级报告**：H1h 记录里若出现「加入者已能走/看」这类活体结论，即为不成立——真测属 V5。

### 四态口径（本轮）
- **已合主干**：规划分支 `0552e10`（4 份 docs、零代码）→ `24ac6e0`；E6 的专服单客户端封证记录仍在其位。
- **仅在分支**：H1h 在工，远端尚无该 ref；本轮没有任何待合分支被 M 见到。
- **真实封证**：**1 个**——`73a52bfb…` / bundle `b2b4133b…`（`V1201-020`，本地专服 + 单客户端）。**LAN 第二客户端的控制封证 = 0。**
- **未验证**：H1h（控制驱动形状）、V5（活体 look/move/release）、M-C1（可判 case）、E7（同 run 封证）、M-G1（门禁与 registry 只读审计）；以及所有仍守主控决策门的项（V08 远程服、HOST/PERSIST、跨 bundle 证据 schema、registry 引用替换、`mandatory` 翻转）。

### 第三十七轮补充：M-C1/E7 的「可判载体」已提前量清（只读，规范卷未写）

派工等待期做的独立工作：把 M-C1 的前置问题——**加入者控制判据有没有单 bundle 载体**——从卷内既有 bundle 量成事实，而不是等 M-C1 开工才发现。

- 扫描口径：容器 `minekin-runner:local`，`-v minekin-runner-data:/data:ro`（**只读**），glob `kin/*/*/evidence/*/manifest.json` ⇒ `bundles=100`。
- **控制类判据词在卷内是活的**：`move_input_was_leased` 出现在 27 份 bundle、`the_server_saw_the_kin_move` 8 份、`the_lease_expired_and_was_released` 8 份、`the_bridge_released_input_when_play_ended` 3 份。
- **LAN 侧的 6 份 `CORE-030` bundle 里，没有任何一份含 `server/server.log`**；其中 5 份含 `host-run-document.json`（kin-02 / kin-04 ×2 / kin-e-rr-seal / kin-e-rr-seal2）。全卷同时含 `server/server.log` 与 `host-run-document.json` 的 bundle = **0 份**（含前者者 78 份，均在主机侧/专服侧）。
- 机制定位（仓库字节，无需真跑）：`tools/seal_run_evidence.py:256` 从 `server_directory / "server.log"` 封 `SERVER_LOG_ARTIFACT`，`:807` 另封 `HOST_RUN_DOCUMENT_ARTIFACT`；判据侧 `tools/assert_case_evidence.py:720` 用同一名字读服务端日志，`join_line()` 在 `:465-468` 按 `<username> joined the game` 定位，位置探针走 `probe_readings(material.server_log, 3)`（`:1607/:1674/:2446`）。
- **结论（决定 M-C1 的形状）**：加入者的 lease/look/释放证据在它自己的 bundle 里，而「服务端看到这个 Kin 移动」要读的是**主持有者那台 LAN 服务器的日志**。当前 sealer 只从本 run 自己的 `server_directory` 取日志，加入者 run 没有这个目录 ⇒ 单 bundle 载体缺的是「把宿主侧 LAN 日志带进加入者 bundle」这一格。**这是 `tools/**` 的封存入口问题，属 M 独占面，不是 `minekin.p0.evidence.v1` schema 扩展，也不是主控保留的跨 bundle 链上载体**。M-C1 若按此实施，E7 仍是单 bundle 同 run 封证。
- 若后续实测发现必须跨 bundle 串联，那才触主控保留门：届时的正确动作是停在 M-C1 并报告，不是实施。

### 第三十七轮补充二：§2.2 拆分生效、M-C0 派工，M 侧「改前基线」亲量并存档

派工等待期的第二批只读工作（规范卷仍全程 `:ro`，本轮零写入、零封证）。

**派工现场读数（`77329dc`，远端逐字一致）**
- H1h：`../minekin-wt-h1h` @ `codex/minekin-lan-joiner-bounded-control`，`git log` 尖仍是 base `24ac6e0` ⇒ **零提交、在工**；未提交改动恰好落在允许面内（`M test-orchestrator/runner/domain.sh`、`M tests/contract/test_runner_scripts.py`），无越界文件。
- M-C0：`../minekin-wt-mc0` @ `codex/minekin-probe-target-carrier`，base `5d0cd2a`，工作树干净、零提交 ⇒ 尚未交付。
- 远端 ref 复核按**全称**做（上一轮用 `refs/heads/codeminekin*` 这类畸形 pattern 得到空输出，那是读法坏了，不是「分支不存在」的证据）：`git ls-remote origin refs/heads/codex/minekin-lan-joiner-bounded-control refs/heads/codex/minekin-probe-target-carrier` → 无输出，与两树本地零提交相互印证。
- H1i（`V1201-PROBE-TARGET-HANDOVER-001`，只动 `domain.sh`）依 §2.2 阻塞在 H1h 与 M-C0 之后，本轮不派，避免两条 lane 同改一个 runner 文件。

**M 侧改前基线（复现命令 + 实测输出，供 M-C0 的 parity 主张与 M-G1 的基线核对）**
脚本 `.tmp/m-r38-base-readings.sh`，容器 `minekin-runner:local`、`/src:ro` + `/data:ro`，输出全量存 `.tmp/m-r38-mc0-base-readings.log`：
- `tools/rejudge_evidence.py --cases-dir /src/tests/fixtures/cases <bundle>` 三份：
  - `kin-01/61b4f0253cc84e2183d8913f3ad77867`（`OFFLINE-010`，case_version `78053e9e…`）⇒ `rc=0`、`status agrees`、`result PASS`；
  - `kin-01/87229052d24f4772a512dee497bab29c`（`V1201-020`，case_version `e7c3b722…`）⇒ `rc=0`、`status agrees`、`result PASS`；
  - `kin-01/01ca65e397354f1489a3a299e8c44973`（`CORE-060`）⇒ **`rc=2` `status unjudged`**：封于 case_version `30ac59a0…` 而现为 `d1ea32d8…`，判据已移动。**⇒ 这一份不是合法的改前改后 parity 对照**（它本来就不与当前 case 一致）；M-C0 的 parity 只拿前两份（外加 E6 的 `73a52bfb…`）逐字比。
- `tools/report_promotion.py --data-root /data --cases-dir /src/tests/fixtures/cases` ⇒ `report_rc=1`、`status blocked`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']`、`gated null`；`promotable ['W00','W10','W20','W60']`；`W30 False ['NO_MANDATORY_CASES','REQUIRED_CASE_NOT_REGISTERED']`、`W40 False ['REQUIRED_CASE_NOT_REGISTERED']`、`p0-core False ['REQUIRED_CASE_NOT_REGISTERED']`；底数 `attempts 77 / bundles 113 / from_another_build 61 / repo_checks_not_from_the_controlled_interpreter 9`，`sealed_without_bundle / unreadable / unsealed / unverified` 全 `0`；唯一 `visibility_gaps` 仍是 `ORCHESTRATOR_REVISION_NOT_PINNED`（`gates_promotion false`）。
- **门载荷**：`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ 与主干既有基线逐字符相同，这一枚现在是**在 `77329dc` 上重新量出来的**，不是引用旧记录。
- **口径澄清（本轮查清，之前只当常量用）**：`gate_payload_sha256` 不是仓库工具打印的字段——`grep -rn gate_payload_sha256 tools/ src/` 命中 **0**。它是 M 侧读法：对 `report_promotion.py` 的 `{work_packages, overall}` 子集做 `json.dumps(..., sort_keys=True)` 再 sha256（定义见 `.tmp/m-r12-payload.sh:8-12`、`.tmp/m-r7-baseline.sh:26`）。同理，报告**顶层没有 `promotable` 键**（`tools/report_promotion.py:752-753` 只写 `gated` 与 `status`），基线里那行 `promotable ['W00',…]` 是由各 work package 的 `promotable` 真值算出的（`m-r7-baseline.sh:32`）。⇒ **lane 若自报门载荷，必须用同一子集口径，否则数值不可比**；H1h/M-C0 的「门不动」一条由 M 用上述脚本亲量为准。

**四态口径（本轮，替代上一节的同口径段）**
- **已合主干**：`24ac6e0`（规划分支）+ `2acb13d / 48e3eb3 / 5d0cd2a / 77329dc`（载体预量、§2.1 裁决、行号自纠、§2.2 拆分）；E6 的专服单客户端封证记录仍在位。
- **仅在分支**：H1h、M-C0（两树均**零提交**，故连「分支上的交付」都还没有；远端无 ref）。
- **真实封证**：**1 个**——`73a52bfb…` / bundle `b2b4133b…`（`V1201-020`，本地专服 + 单客户端）；**LAN 第二客户端的控制封证 = 0**。
- **未验证**：H1h 的限幅形状、M-C0 的探针目标归属、V5 活体读数、M-C1 登记、E7 同 run 封证、M-G1 审计；以及仍守主控决策门的 V08 远程服、HOST/PERSIST、跨 bundle 证据 schema、registry 引用替换、`mandatory` 翻转。

### 第三十七轮补充三：受控镜像的 SQLite 假 FAIL（新工具形状陷阱）+ 复审闸门锁件 + H1h 断点续派

**① 受控镜像少一个 `LD_LIBRARY_PATH` 就会假 FAIL 13 个判据测试**（本轮量出，此前未记录）：
- 现象：`tests/unit/test_case_evidence_assertions.py` 在镜像里 `13 failed, 474 passed`，报错具名为 `SQLiteCompatibilityError: SQLite 3.45.1 is outside the validated multi-connection WAL safety set: this build accepts 3.51.3 or newer, or the backports 3.44.6 or 3.50.7`（`src/minekin_core/adapters/sqlite/connection.py:74`）。
- 分层实测：镜像里**确实带着钉住的库** `/opt/sqlite/lib/libsqlite3.so.3.53.4`，但 `_sqlite3.so` 按 `ldd` 链到 `/lib/x86_64-linux-gnu/libsqlite3.so.0`（Debian 3.45.1），因为 `/opt/sqlite/lib` 不在 loader 路径上（`ldconfig -p | grep -c libsqlite3` = 1）。加上 `-e LD_LIBRARY_PATH=/opt/sqlite/lib` 后同一份代码 `487 passed`；宿主 `uv run pytest`（pysqlite 3.53.1）也是 `487 passed`。⇒ **不是主干回归，不是 lane 的错**，是调用形状。此前 M 的封存读数脚本（`.tmp/m-r36-e6-reads.sh:22`、`.tmp/m-v2-run.sh:4`）本就带这个变量，只是复审闸门脚本没带。
- 处置：不为此开镜像卡（无产品/环境改动必要），把口径写进复审脚本头部。同时记入既有第三类陷阱清单（`jsonschema` 缺失导致全量套件 3 个收集错误、`verify_tested_provenance.py` 的 `BRIDGE_JAR_MISSING`）。

**② 复审闸门已钉成一件可复算工具**：`.tmp/m-r38-review-gates.sh`，在主干 `52a6457` 上标定（输出 `.tmp/m-r38-review-gates-calibration.log`）——六项全 `rc=0`（`bash -n`、contract `37 passed`、asserter `487 passed`、case-assertions `150 registered`、fixture-digests、boundaries）、两份 parity 对照逐字 `agrees/PASS`、`gate_payload_sha256 cfa0f118…63afd6`、`domain.sh ff69c879…`、auto+joiner 拒止与 `world_args=()` 两处不变量按名可读。⇒ H1h/M-C0 到货后跑同一脚本对 `BASE_SHA..TIP_SHA`，改前改后只差在 lane 声明的那几格。修脚本时踩到一个小坑：`rejudge_evidence.py` 的 JSON 在 stdout、结论句在 stderr，`2>&1` 合并会让 `json.load` 假报 unreadable——已按流分开。

**③ H1h 的 lane 断点与续派**：先前那枚 H1h 子代理停在 150 turn 上限，留下一件**未提交但已成形的实现**（`domain.sh +244`、`tests/contract/test_runner_scripts.py +734`，均在允许面内）：默认关闭的三个加入者控制名 + 边界常量（`max_yaw=45`/`max_pitch=30`/`max_forward_seconds=2`）+ 数值形状检查（拒非数、拒零、取绝对值比界，越界具名拒止不钳制）+ 一个 `MINEKIN_DOMAIN_JOIN_CONTROL_PRINT` 的读回口子；其注释已明确「不宣称真客户端转过/走过，活体读数属后续卡」，与预登记第 5 条一致。M 按既有规矩**续派完成而非重新设计**：只补 A–D 原始读数与反例、一份 `docs/validation/` 记录、提交并 push 分支（禁合主干、禁挂规范卷）。

### 第三十七轮补充四：H1i 等值判官入册、门禁复量「卷未被写」、以及 V5 的前提改派一张前置卡

**① H1i 的「opt-in 关闭等值」现在是可复算判据**（队列 §2.6，commit `8dfeac6`）：`.tmp/m-r39-h1i-seal-argv-judge.py`（`report`/`compare --base --tip`/`mutate`）在主干 `95b1b00` 标定——加入者封存区段 sha `4270b51c…`、封存调用区段 sha `7d83721f…`、`world_args=()` 在位、三个外部旗标在加入者区段出现 0 次；「无条件把 `--server-directory` 交给加入者」与「opt-in 顺手带 `--server-profile`」两种植入都被具名抓出。**M 申报自己的一处口径缺陷并已在同一次提交里修掉**：首版 `compare` 把区段绝对行号计入相等判断，导致主干对 H1h 在飞树误判「不等」（2481→2719，而两段内容 sha 逐字相同）；行号不是字节，改为只报告不判等后全部读数重跑（正对照仍在：植入树 `rc=1` 并给出同一条 fault）。同一件工具顺带量到一条对复审有用的事实：**H1h 的 +238 行没有移动封存配方**。

**② 「本轮规范卷未被写」是量出来的，不是声明的**：以 `/src:ro + /data:ro` 复跑 `.tmp/m-r38-base-readings.sh` → `.tmp/m-r40-recheck.log`，与第三十七轮存档 `.tmp/m-r38-mc0-base-readings.log` 在关键字段上逐位相同：两份 parity `agrees/PASS`、CORE-060 仍 `rc=2 unjudged`、`gate_payload_sha256 cfa0f118…63afd6`、`attempts 77 / bundles 113 / from_another_build 61`。⇒ 三次主干文档提交（`3d46686`/`6af5a77`/`52a6457`/`95b1b00`/`8dfeac6`）没有移动门禁，也没有新 bundle 被密封。CI：`52a6457`、`6af5a77`、`8dfeac6` 三笔 `protocol`/`bridge-static`/`python` 全 success。

**③ V5 的前提不是量出来的，于是先派一张前置卡 V5a**：§2.5 第 1 条「显式设 `MINEKIN_DOMAIN_PROBE` 为加入者用户名即可读到加入者位移」只是 M 对 `domain.sh:27/165/482` 的代码阅读，从未活体验证，而 V5→M-C1→E7 三张卡都挂在它上面。按「先复量前提再排工」的规矩，新派 **V5a 探针目标前置活体量测**（工作树 `minekin-wt-v5`，分支 `codex/minekin-v5-probe-target-preflight`，HEAD `8dfeac6`，`domain.sh` 主干字节 `ff69c879…`；两份桥产物按字节自 `minekin-wt-v4` 拷入：`0ee2070b…` 与 `e50d61c2…`，未跟踪）。V5a 沿用 V4 自己的 `.tmp/v4/drive.sh` 驱动形状，只交四条读数：探针回答行存在性、目标切到加入者 vs 主持有者的正对照、加入者账本 `PlayableEstablished`（不得用「服务端听到 arrival」冒充）、以及**主干无控制驱动时加入者首末读数是否真相同**（V5 第二条非恒真对照的关闭侧）。边界：私有数据根、禁挂规范卷、禁封存、禁注册 case、禁改 `test-orchestrator/**`、`tools/**`；量不下去就地停并报第一真实失败层。

**④ 一条读 lane 现场时会被误读的形状**：`minekin-wt-mc0` 一度 `git status` 干净且无新提交，看着像「零交付」；实为该 lane 为取改前基线把 WIP 存进 `stash@{0}: mc0-wip-baseline`（tracked +127/-16；未跟踪的 313 行测试只在 `stash@{0}^3` 里，`git stash show --stat` 看不到它）。⇒ 审 lane 前先 `git stash list`，M 不代 lane 恢复工作树。

## 第三十八至四十一轮：H1h/H1j/M-C0/V5a 依次入干，H1k 在飞，V5 改挂新形状

**远端 SHA 链（每笔都按 `git ls-remote origin refs/heads/main` 逐字核过）**：`dcd914a`（H1h 读数与 H1j 立卡）→ `d19714f`/`4ad3db2`（主干修 H1h 的 ruff 债与一个不存在的注解名）→ `975b786`+`145f26b` → `bcdaf17`（**H1j 合并**）→ `97dc0ef`（**M-C0 合并**）→ `29c5187`（plan §2.11–§2.14 回写 + 时序纠正）→ `4640983`（**V5a 合并**）→ `0a4a10e`（§2.15 落地记录）→ `60f11eb`（**§2.16 判据预登记**）。CI 三门（`protocol`/`python`/`bridge-static`）对 `29c5187`、`4640983` 全绿；`0a4a10e`/`60f11eb` 是纯文档笔，写作时 `python` 仍 `in_progress`。

**① 恢复现场抓到的第一个不是读数的东西：一份「文档先于提交」**。第四十轮开工时 `docs/v1201-lan-control-next-2026-09-27.md` §2.14 已写「M-C0 已合主干」，而 `main`/`origin/main` 仍是 `bcdaf17`。三样字节证据把它钉死：`git ls-tree -r HEAD --name-only | grep probe_target_carrier` 空、`.git/worktrees/minekin-wt-integration/MERGE_HEAD` 还在（指 `1e42ea6`）、那两个文件只在工作树与索引里。**修法**：先重跑主干侧闸门（`uv run --frozen ruff check .` / `ruff format --check .` / `pyright` / `tools/check_boundaries.py` / `check_case_assertions.py` / `verify_fixture_digests.py` / `check_workflow_pins.py`），再把合并落成 `97dc0ef`，并在 §2.14 末尾加一条具名时序申报而不静默改写。⇒ 以后声称入干前先量这三样。

**② 容器侧的 M-C0 决定性材料是真的，且现在仍取得到**：`.tmp/m-r44-mc0-gates.log`（契约 64、断言器 487、carrier 10、`150 registered`、digests/boundaries OK、门载荷 `cfa0f118…63afd6` 未动、`report_rc=1`、`promotable` 仍 W00/W10/W20/W60、`overall_blocks` 仍只有 `REQUIRED_CASE_NOT_REGISTERED`、两份 parity bundle `agrees/PASS`、`domain.sh` 仍 `baad190aaa5ee…`）与 `.tmp/m-r44-census-{main,mc0}.log`（`cited=18 absent_bundles=0 digest_mismatch=0`，两份 `diff` 为空 ⇒ M-C0 是加法，不动任何既有判据读数）。**容器读数的挂载形状**：`docker run --rm --entrypoint /bin/bash -e LD_LIBRARY_PATH=/opt/sqlite/lib -v <tree>:/src:ro -v minekin-runner-data:/data:ro minekin-runner:local`；漏掉 `LD_LIBRARY_PATH` 会让镜像链上 Debian SQLite 3.45.1，`test_case_evidence_assertions.py` 里 13 条用例假红（§2.13 之外的老坑，重申一次）。

**③ V5a 量出来的结论把 V5 的前提判掉了，第一真实失败层在 runner**：主干里「有探针答题人的形状」（`--server-profile` 起 `run_controlled_server.py`，回答行落 `${server_directory}/server.log`）与「有第二客户端的形状」（等宿主客户端 `latest.log` 的 `Started serving on ${lan_port}`，加入者进的是宿主 LAN 世界）**互斥**。LAN 形状卷内根本没有 `server-runs`；专服 + `--open-lan` + 加入者那一格门 120s 永不打开。于是 §2.5 的「设 `MINEKIN_DOMAIN_PROBE` 就能读到加入者位移」只在管线半句为真，推论半句不成立。⇒ 新立 **H1k**（见 §2.13），V5/M-C1/E7 全部顺移；V5a 的记录本身以 `4640983` 入干，M 只修了它两处现在时陈述（`domain.sh ff69c879…` 等于**它的 base** `8dfeac6` 而非等于主干；§4「主干没有加入者控制驱动」收窄为「本卡 base 没有」），历史读数与逐字材料未追改。

**④ 在飞现场（新会话接手时先读这段）**：H1k 在 `codex/minekin-v1201-joiner-on-controlled-server` @ `../minekin-wt-h1k`（起点 `29c5187`），允许面只有 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md`；**不挂规范卷**（活体 run 只能用私有数据根）、需扩 `run.sh` 即停手交回、门载荷必须仍是 `cfa0f118…`、四条验收 + 两则反证要字面输出。H1i（§2.4）与 H1k 同改 `domain.sh` ⇒ 按「同一文件仅一名 owner」排 **H1k → H1i**，不并飞（§2.16 第一条）。**M-G1 的「改后」census/门载荷复量故意压到 H1k 活体窗口关闭之后**——桥握手 30s 预算 + 并发争用已实测烧掉 V5a 三次尝试，M 不再往同一窗口塞容器读数。

**⑤ §2.16 是判据的冻结点**：V5′ 七条、M-C1 的双条归属口径（行内名 + 申报集合恰为 `{加入者名}`）、E7 的同 run 条件、M-G1 的压后说明，全部写在任何活体/登记读数存在之前。之后任何一条要改口径必须另起一节具名申报改哪条、为什么、旧口径下哪些读数作废。分支普查：`origin/codex/minekin-local-control-next` 相对主干 ahead=0（规划分支的增量已全数入干）；`origin/codex/parallel-execution-plan` ahead=2 但那份 `docs/parallel-execution-plan.md` 是主干版本的早期草稿（主干文本严格更新）⇒ 无真实增量，不合并、不删除。本轮零封证：LAN 第二客户端控制封证仍为 **0**。

## 第四十二至四十五轮：H1k 候选字节的 M 侧复审、`live-b` 失败层取证、判别子跑完、主控裁决四项范围

**远端 SHA 链（每笔按 `git ls-remote origin refs/heads/main` 逐字核过）**：`4a8fec3`（§2.18 M 侧静态+动态复审）→ `c17663e`（§2.19 主干字节上门载荷重测）→ `8e53cc3`（§2.20 `live-b` 第一真实失败层取证）→ `9fb4c0e`（§2.21 判别子：专服形状下第二客户端真到达真释放）→ `d933fbe`（§2.22 主控裁决 H1k 下一轮四项范围 + 规划队列回写）→ `c982a32`（`development-todo.md` 第十二轮之后的账目收束）。CI：run 864/865/866 依次 `completed/success`；run 867（`c982a32`）在本次记录时点为 `in_progress`（12:29:12Z 实读）⇒ **不构成该笔的绿读数**，接手会话须重读。

**① H1k 的候选字节在 M 树里复审过，退回项是量出来的**：lane 停在 `29c5187` 且工作树未提交，候选 sha256 `domain.sh d9a0acfc…`、`test_runner_scripts.py 7fe48b9d…`（第四十五轮复量仍同值 ⇒ 期间 lane 未动过字节）。§2.17 登记的缺陷是**形状**结论：guard 区间 `domain.sh:461–:488` 只有六条具名拒止，`MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1` × `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1` 缺第七条——`refusal_asked` 的分支排在新增 elif 之前，加入者被备好却从未被发送。M 在 `../minekin-wt-m-r45`（支 `m-r45-h1k-review`）里把它做成非恒真的动态对照并带正对照（§2.18），四门 `rc=0`。

**② 门载荷是在主干字节上重测的，不是引用常量**：`report_promotion` 的 `{work_packages, overall}` 子集（`sort_keys=True`）sha256 = `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，`rc=1`，`check_case_assertions.py` = **150 registered**；规范卷全程 `:ro`，`docker ps` 空窗时取读。操作陷阱两条，别再花时间：Git Bash 下 `docker run -v C:/…` 必须 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'` + 反斜杠源路径；`uv run --frozen` 在代理拒外网时要 `--offline`。

**③ `live-b` 的第一真实失败层已具名，且被判别子关掉**：M 从 `Exited (255)` 容器 `docker cp /tmp` 取证（会话文档全 0 字节、`server.log` 80 行停在 `Done`、加入者 `client-environment.txt` 502 字节在位），先并列两条解释；随后 M 在自己私有卷 `minekin-m-r45-live` 重放同形状，量到**第二客户端到达、按具名被问、在 H1h 限幅输入下转向行走（`-2.5,-3.5 → 2.85,6.46`）、并释放**，`domain.sh rc=14`、`outcome BRIDGE_LOST`（未判读，不是 PASS 也不是封证）。lane 自己的交付记录 §5 独立把同一格归因为 Docker Desktop 引擎挂死 ⇒ **两侧同因、同判不合入**，阻塞的只是时点条件。

**④ 在飞现场（新会话接手时先读这段）**：M 已按 §2.22 把 H1k 续跑派回 H lane，允许面不变（`domain.sh`、`tests/contract/test_runner_scripts.py`、那份 `docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md`），四项按序：① 第七条组合拒止 + 契约测试（两名字同真 ⇒ `rc=2` 且 `/tmp/domain-join-profile.json` 不存在；默认关闭字节相等扩展到该组合）；② 新字节上整体重跑 §2/§3/§4 读数与两组反证；③ `minekin-h1k-live` 上的活体 ③（**M 的 §2.21 私有卷重跑不替代这一格**）；④ 门载荷前后值。lane 未提交候选必须保住：动手前备份 + 记 sha256，禁止 `git checkout --`/`restore`/`reset --hard`。**M 侧此刻不挂任何容器活体窗**，避免与 lane 抢引擎。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；V5′ 停等 H1k 收口，E lane 不派新卡。**LAN 第二客户端在受控专服形状下的同 run 封证仍为 0**；`E6` 的 `V1201-020` seq4 是本地专服单客户端封证，不得顶替。全程未连接用户远程服、未放宽认证/地址/lease/判据、未删除旧材料。

## 第四十六至四十八轮：H1k 字节两度移动、M 的普查错判当场撤回、#56 契约侧预检通过

**远端 SHA 链（逐笔 `git ls-remote origin refs/heads/main` 核过）**：`bd5ee23`（§2.23 第①项只读预读）→ `01d3a65`（§2.24 申报 §2.23 的测试摘要已过期）→ `52e78b5`（§2.25 冲突对普查）→ `e33d109`（§2.26 **撤回** §2.25 的「第八对缺口」判定）→ `21a0784`（§2.27 #56 契约侧预检）。CI 实读：`52e78b5` `completed/success`，`e33d109` 于 13:04:49Z 单读 `in_progress`（每轮一次读，绿读数未作）。

**① lane 的字节在复审期内移动了两次，M 每次都当场申报而不是沿用**：`domain.sh` 由 §2.18 的 `d9a0acfc…`/156,083 → `e1d8dbb9…`/156,467（此后 mtime 20:50:45 起未再动）；`tests/contract/test_runner_scripts.py` 由 `7fe48b9d…`/159,426 → `02ec23c2…`/161,021 → `33f7d7f0…`/171,525。下一位复审者仍须自己重取 sha256，§2.23/§2.24 的数字只活到各自时点。

**② M 自己判错过一次，并已在新证据上撤回（保留原文不改写）**：§2.25 只看 `domain.sh` 四行，把 `MINEKIN_DOMAIN_ONLINE_MODE=true` × `JOIN_ON_CONTROLLED_SERVER=1` 判成「缺第八条具名拒止」。补读 `tools/run_controlled_server.py:226–:235/:303–:312/:264–:271` 与 `domain.sh:1788`、`tests/unit/test_case_evidence_assertions.py:3715`、契约 `:299` 后确认：该形状早有具名承担者 `AUTH_MODE_MISMATCH`（ADMIT-040），且这族里强制 online-mode 时工具**拒绝** `--enable-status`。⇒ 「guard 未列该对」≠「无人拒止该对」；#58 由退回项降级为一条待判问题（非 ADMIT-040 时是具名失配还是静默超时），处置改为「判前先 grep `tools/**` 与 `tests/unit/**` 的既有承担者」。

**③ #56（第七条拒止）的契约侧已由 M 在自己的树里量过，不是读 lane 的记录**：`../minekin-wt-m-r45`（支 `m-r45-h1k-review`）按当前候选字节覆盖后 ⇒ `tests/contract/test_runner_scripts.py` **`85 passed in 32.62s`**；M 自删 guard `:487–:490` ⇒ **`4 failed, 81 passed in 12.85s`**，红的正是 `[first-snapshot-combination]`、`test_the_two_destination_combination_is_refused_before_any_plan_is_written`、`test_the_combination_stays_a_trunk_shape_while_the_new_name_is_off`、`test_the_seventh_refusal_is_not_an_always_true_claim`；破桩前备份 `../minekin-wt-m-r45/.tmp/m-r46-domain-before-break`，还原后 sha256 与候选一致。lane 记录里的 `81 passed / 578 passed` 早于它自己追加的这 4 个案 ⇒ 过期而非矛盾，第②项仍须按最终字节整体重跑。

**④ 在飞现场（本轮更新）**：lane 在 20:52 后停止推进（`docker ps` 空、树仍脏在 `29c5187`）⇒ M 于 21:11 派**只做重测与交付、不重设计**的续做会话，并明确第①项不许改设计（有疑只写进记录）。允许面同前，交付要求＝②③④ 三项 + 按最终字节重跑门禁 + 提交并 push 自己的分支（不得 push `main`）。M 在派工后仍不挂容器活体窗，避免与 lane 的 ③ 抢引擎与时间预算（加入者等待是 420s 量级）。队列一寸未动：`current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`，H1i 严格排在 H1k 后（同文件），V5′ 的第 1 条判据（三处载体行号）只能在 H1k 入干后现场重读，M-C1/E7 依序在其后。**真实封证计数不变：LAN 第二客户端在受控专服形状下的同 run 封证 0**；本轮 M 侧读数全部来自私有卷/仓库，无一冒充 sealed bundle。未连接用户远程服、未动判据/registry/门禁、未删除失败材料。

## 第四十九轮：M-T1 落地、门载荷在新字节上重测为同值、H1m 的派工文本按已定接口写死

**远端 SHA 链**：`17a6537` → `070390d`（M-T1 的 `--no-ff` 合入，首父即真实 merge-base `17a6537`）→ `7546ec9`（§2.29）→ `f29b77d`（§2.30 门载荷重测）。每笔按 `git ls-remote origin refs/heads/main` 逐字核过；施工支 `codex/minekin-m-t1-multi-probe` @ `5ec0500` 同轮已 push。

**① M-T1 收的是 §2.28 的 B 格，且只在 M 独占面上收**。`tools/run_controlled_server.py`：`--probe-player` 转 `action="append"`/`default=[]`、新 `probe_console_commands()` 逐名排 `Pos`+`Rotation` 成对相邻、at-join 补测由单 flag 改逐名 `bursted` 集合、重名 ⇒ rc=2（落盘前）、`--use-target × 多名` ⇒ 具名拒。单名形状逐字不变，这一句是测试里的一格而不是修辞。改面恰 2 文件（工具 + `tests/contract/test_controlled_server_runner.py`，后者新增 `_ListeningServerProcess`/`run_the_console()` 读手与 4 个案：零名 ⇒ 无行、单名 ⇒ 那两行、双名 ⇒ 四行按 kin 主序、重名/use-target 两拒）。

**② 读数与反证（退出码单步读）**：契约 `28 passed` rc=0；全量 `2645 passed, 3 skipped in 301.14s` rc=0；`ruff`/`check_boundaries`/`check_case_assertions`（`150 registered`，未新增 case）/`verify_fixture_digests`/`git diff --check` 全 rc=0。CE-a `probe[:2]` ⇒ 恰双名案 1 failed（零名与单名仍绿）；CE-b 重名拒止改 `if False and` ⇒ 恰重名案 1 failed。种桩前备份 `.tmp/m-t1-pre-ce/run_controlled_server.py.orig`，还原后 sha256 复量 `263ce1046e19e0b3337af4174a84b5cce778c42390a6e8ef068a600e6dfc9466` 与种桩前同值；未对任何脏文件用 `git checkout --`/`restore`/`reset`。

**③ 门载荷这对读数现在在 M 手里**：`7546ec9` 字节 + 规范卷 `:ro` ⇒ `report_promotion` rc=1、`{work_packages, overall}` 子集 sha256 `cfa0f118…` == §2.19 的 PRE、`W30.promotable False`（`NO_MANDATORY_CASES`+`REQUIRED_CASE_NOT_REGISTERED`）、`p0-core` 仍 `REQUIRED_CASE_NOT_REGISTERED`。上一笔那次 rc=127 的成因已定位：**`-v` 源路径不能写反斜杠**，`C:/Users/…` 正斜杠配 `MSYS_NO_PATHCONV=1` 即可，镜像入口与 `python` 都正常（最小探针回 3、rc=0）。

**④ 在飞现场（接手先读这段）**：lane 仍停在 `29c5187` + 同样三处脏改动（`domain.sh`、`tests/contract/test_runner_scripts.py`、未跟踪的 `docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md`），`.tmp/h1k-recheck` 最后写 21:35、21:36 起有其活体容器在飞 ⇒ **lane 会话在跑 ③，M 不进其树、不代提交、不挂自己的容器活体窗**。lane 交付并 push 后 M 的动作次序不变：按真实 merge-base `29c5187` 复审合并 diff（`--allow-player` 范围、`join_the_published_world` 复用到服务端日志、默认关闭字节等值、新字节上的门载荷一对、#56 与 #58 处置）→ 合入 main → push → 核远端 SHA → 读 CI。此刻仍欠的 CI 读数：`070390d`/`7546ec9`/`f29b77d`（上一读 `876`＝`17a6537` 为 `in_progress`；`873/874/875` 已 `completed/success`）。H1l 仍 blockedBy H1k（它要改的 `tests/contract/test_runner_scripts.py` 正是 lane 的脏文件）；**H1m 的派工文本已写死**（§2.29：现读行号 `domain.sh:27/:133/:171/:715/:716–:717/:821`、`MINEKIN_DOMAIN_PROBE_SECOND` 默认关闭、两条早退、新名须进 `run.sh` 的 `-e` 名单并要一次经 run.sh 的真实形状读、三枚反证、门载荷前后一对），排在 H1k 收口之后；V5′ 排在 H1l 与 H1m 之后。**LAN 第二客户端在受控专服形状下的同 run 封证仍为 0**；私有卷读数与本轮 M-T1 的仓库读数都不算 sealed bundle，`E6` 的 `V1201-020` seq4 不得顶替。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`。未连接用户远程服、未放宽认证/地址/lease/判据、未删除旧材料与失败材料（`.tmp/m-t1-ce-a.log`、`.tmp/m-t1-ce-b.log`、`.tmp/m-r49-report-post.json/.err` 在案）。

## 第五十轮：主干因 M 漏跑两道门红了五次——定位、修复入干、CI 复绿，并把门禁清单这条写成硬前置

**远端 SHA 链**：`8b66ccf`（第四十九轮末）→ `d1ba27e`（M-T1 修复的 `--no-ff` 合入，真实 merge-base 为 `5ec0500`）；push 后 `git ls-remote origin refs/heads/main` = `d1ba27e61e9ad7bf5ba9c91e8c19327aba433485`。施工支 `codex/minekin-m-t1-multi-probe` 的修复笔 `8b66356` 同轮已 push。

**① 红因归 M 自己，不是 lane、不是引擎**。`/actions/runs?per_page=9` 单读：`876`（`17a6537`）`completed/success` ⇒ `877`（`5ec0500`，分支）/`878`（`070390d`）/`879`（`7546ec9`）/`880`（`f29b77d`）/`881`（`8b66ccf`）五笔连续 `completed/failure`。lane 从未 push（远端无 `codex/minekin-v1201-joiner-on-controlled-server` 的 ref），故第一真实失败层是 M-T1 的字节。jobs 端点未认证仍 404 ⇒ 定位改走「`sed` 现读 `.github/workflows/ci.yml:44-55` 的 `- run:` 清单 + 本地逐道复跑」：漏的是 `ruff format --check .`（rc=1，`2 files would be reformatted, 363 files already formatted`）与 `pyright`（rc=1，3 errors 全在 `tests/contract/test_controlled_server_runner.py:616` 的内联 `lambda path, recipe: None` ⇒ 参数类型未知）。§2.29 那句「静态门全 rc=0」在 M 自己跑过的范围内如实，但**不等于 CI 的门禁清单**，已在 §2.31 具名纠正（历史读数不 rewrite）。

**② 修复是新提交、不是 amend**：`8b66356` 只含那两道门要求的形状——`ruff format .` 重排 2 文件（+6/-7，唯一实质是一处三元式收回一行）+ 契约里的 `verify_jar` 桩改成带注解的内嵌 `def skips_the_jar_pin(path: Path, recipe: _Recipe) -> None`。**无行为改动**，merge diff 恰那 2 文件。M-T1 工具字节格式后为 `311ecf6a34875ed29faad215c8de87ccd817cc6d90e2ff6507e2555f3e4be820`（§2.29 的 `263ce104…` 是格式前那一份，保留）。CI 复绿：`882`（`8b66356`）、`883`（`d1ba27e`）均 `completed/**success**` ⇒ 第四十九轮欠的 `070390d/7546ec9/f29b77d` 三笔 CI 读数一并闭合（它们当时的红就是这一处）。

**③ 全套按 `ci.yml` 现读后逐项复量（各自单独一步读 rc）**：`ruff format --check` 0、`ruff check` 0、`pyright` 0（`0 errors`）、契约文件 0（`28 passed`）、`check_boundaries` 0、`check_case_assertions` 0（`150 registered`）、`tools/verify_fixture_digests` 0、`check_workflow_pins` 0、全量 `pytest -q` 0（`2645 passed, 3 skipped in 284.61s`）、`git diff --check` 0。中途一次 `digest_rc=2` 是 M 把路径记成 `scripts/verify_fixture_digests.py`（实在 `tools/`）——读路径错，不是门失败。门载荷在 `d1ba27e` 字节 + 规范卷 `:ro` 上再算一次：rc=1、103,921 字节、`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` == §2.19/§2.30 ⇒ M-T1 两笔均未移动门载荷。

**④ 在飞现场（接手先读这段）**：21:54 只读复量 lane = `29c5187` + 三处脏（`domain.sh` +169、`test_runner_scripts.py` +953、未跟踪验证记录），最后写点 21:35 的 `.tmp/h1k-recheck/`、`docker ps` 已空 ⇒ 判上一段 lane 会话已在轮次上限处停手，满足「先确认在飞会话已停再派接手」这条硬前置后，M 派了**H1k 续跑会话收口 §2.22**：跑 `ci.yml` 全套门（本轮把 `ruff format --check` 与 `pyright` 明列进验收，避免同样漏跑）+ §11 追加节重述四件读数 + 自己提交 push 自己的分支。M 不代提交、不进其树、不 merge 主干进其分支。**lane push 之后** M 的动作次序不变：按真实 merge-base `29c5187` 复审合并 diff（第七条具名拒止、`--allow-player` 范围、`join_the_published_world` 复用、默认关闭字节等值、新字节上门载荷一对、#56/#58 处置）→ 合入 main → push → 核远端 SHA → 读 CI。排序：H1l blockedBy H1k（同一脏契约文件）；H1m 严格在 H1k 收口之后（派工文本已写死于 §2.29）；V5′ 排在 H1l 与 H1m 之后，§2.16 第 4 条第一格到那时才可取。**LAN 第二客户端在受控专服形状下的同 run 封证仍为 0**；私有卷读数与 M 本轮的仓库/门读数都不是 sealed bundle，`E6` 的 `V1201-020` seq4 不得顶替。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`。未连接用户远程服；未放宽认证/地址/lease/判据；未改 cases/registry/`mandatory`；失败材料未删（红 run 清单 `.tmp/m-r50-ci.json`、各 `.tmp/g-*.log`、`.tmp/m-r50-promotion.json/.err` 在案）。

## 第五十一轮：H1k 收口并入主干、M 补正自己两处门禁口径、队列解开 H1l/H1m 两格

**远端 SHA 链**：`d1ba27e` → `4df1b2f`（§2.31 + 第五十轮账目）→ **`a452e84`**（H1k 的 `--no-ff` 合入，真实 merge-base `29c5187`）。`git ls-remote origin refs/heads/main` 逐笔核过；lane 分支 `codex/minekin-v1201-joiner-on-controlled-server` 首推 = `84648c0f718985c12de3b49697c229f999b0b7d1`（lane 自己提交自己 push，M 未代做）。

**① 补正 M 自己的两处口径（§2.32，以新提交落，不改 §2.31 原文）**：CI 侧的**逐步**结论其实免浏览器可得——用 runs 列表里的真实 `id` 请求 `/actions/runs/<id>/jobs` 得 http=200（先前那次 404 是 M 用了错的 id），只有日志正文仍不可得。`881`（红）的 `python` job：step 5 `ruff check` success、step 6 `ruff format --check` **failure**、step 7 `pyright` 及以后 **skipped** ⇒ CI 只证到 format 一道，pyright 的红靠本地 rc=1、绿靠 `883` step 7 success，两侧合起来才完整。且 `883` 的 15 步全 success 暴露出 M 本地清单仍漏 step 13 `uv build --wheel`/14 `check_wheel_boundary.py`/15 `minekin --help` ⇒ 已在主干字节补跑（0/0/0），并把「门禁清单 = 现读 `ci.yml` 的 python job 全部 `- run:` 步骤」钉成口径，同一条口径也写进了对 lane 的派工。

**② H1k 的 M 侧独立复审（读 lane 字节，不读它的结论）**：新名 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER` 默认关闭且坏值 `exit 2`；guard 区七条具名拒止在落盘之前（第七条即 §2.17 退回项 #56）；`--allow-player` 只追加本 run 自己的 `${join_username}`，白名单/enforcement 未动、无字面玩家名；加入者地址端口从**本 run 的** `server.properties` 读且 `server-ip != 127.0.0.1` ⇒ `exit 2`（收紧而非放宽）；新等待支读 `${server_directory}/server.log`，与 `data get entity` 应答同源；契约 11 个新案含两条非恒真与默认关闭字节等价；`run.sh` 的转发缺口是具名 `registered_gap` 登记 ⇒ 归 H1l。merge diff 恰 3 文件 `+1820/-4`。

**③ 合并树读数（各自单步读 rc）**：`ruff check` 0、`ruff format --check` 0（366 files）、`pyright` 0、boundaries 0、`check_case_assertions` 0（`150 registered`）、`verify_fixture_digests` 0、`check_workflow_pins` 0、全量 `pytest -q` **0（`2666 passed, 3 skipped in 292.44s`**，比 `d1ba27e` 的 2645 多 21 格 = lane 新案 + 参数化）、`uv build --wheel` 0、`check_wheel_boundary` 0、`minekin --help` 0、`git diff --check` 0。门载荷在合并树 + 规范卷 `:ro`：rc=1、103,921 字节、`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ H1k 未移门，这次是 M 自量非引用。lane 报的「容器内全量 2 failed + 3 errors」M 未复现未复量（镜像 jsonschema 缺集 + 既有红，CI 在 `uv sync --locked` 下不受影响），按未验证列报。

**④ lane 交回的读数与它自己的诚实更正**：`ruff format --check`/`pyright` 各 0；容器内契约 `85 passed`；宿全量 0；私有卷 `minekin-h1k-live` 上 live-e（武装）/live-f（控制关闭）两条真 run，并自报 live-f 的位移里含 `run-5/server.log:106 Kin2 was slain by Slime` ⇒ 纯净对为 live-e↔live-d、混淆对为 live-c↔live-f；门载荷 PRE==POST；`tr -d '\r'` 后盘上/库内逐字节相等的 `.py` 未钉 `eol=lf` 摘要差已点名入其 §12。**四态封顶仍是「已合主干、非封证」**：真实封证 **0**（LAN 第二客户端在受控专服形状下的同 run 封证未动；`E6` 的 `V1201-020` seq4 不得顶替）。lane 自报 5 格未验证并全部保留：专用 `No entity was found` 对照 run、同 run 内主持有者读数不变、`rc=14/BRIDGE_LOST` 是否落在 PASS 判据内（属 V5′/M-C1）、#58 那格（`ONLINE_MODE=true × 新名 × 非 ADMIT-040`）、容器 2 红成因。

**⑤ 在飞现场与下一步（接手先读这段）**：H1k 入干 ⇒ **H1l（#59）与 H1m（#61）同时解除 blocked**，两者都要改 `test-orchestrator/runner/run.sh` 与 `tests/contract/test_runner_scripts.py` ⇒ **同一写窗，按序跑，不并行**：先 H1l（转发 `JOIN_ON_CONTROLLED_SERVER` + 删 `registered_gap` + 双向集合差为空 + 一次经 `run.sh` 的真实形状读），后 H1m（`MINEKIN_DOMAIN_PROBE_SECOND` 默认关闭，§2.29 已写死派工文本，含两条早退与三枚反证）。**V5′ 排在 H1l 与 H1m 之后**（§2.16 第 4 条第一格在那之前仍按构造不可取）。本轮 `a452e84` 的 CI 结论仍待读（`884`＝`4df1b2f` 上一读 `in_progress`，`in_progress` 既不作绿也不作红）。lane 树现干净、停在 `84648c0`；M 施工树 `../minekin-wt-m-t1` 已完成使命可留档。规范卷对 M 仍只 `:ro`；未连接用户远程服；未放宽认证/地址/lease/判据；未改 cases/registry/`mandatory`；失败与中间材料未删（`.tmp/m-r50-jobs881.json`、`.tmp/m-r50-jobs883.json`、`.tmp/m-r50m-*.log`、`.tmp/g-*.log`、`.tmp/m-r50-ci.json` 在案）。
