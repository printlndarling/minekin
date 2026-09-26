# Qoder / 新会话连续执行交接

更新：2026-09-26。旧 875 行交接（包括 Qoder 未提交的第七类审计草稿）完整保存在[历史交接](qoder-execution-handoff-history-through-cef712b.md)；其中旧 `NEXT`、旧 run 读数、旧“队列为空”不再指挥执行。现行唯一队列是[执行计划](development-execution-plan.md)。

## 每次启动与上下文丢失后的恢复步骤

1. 在 `C:\Users\darling\Documents\agent_work\minekin` 运行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、`git log -8 --oneline`、`git ls-remote origin refs/heads/main refs/heads/codex/core-state-transition`。记录 HEAD/两 ref/dirty 文件，勿 reset/stash/覆盖他人改动；远端与本地分叉先停下协商。
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

