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

当前 **E lane** 的 `NEXT` 是 **B2 `P0-CONTROLLED-CAMPAIGN-001`**（主干 `NEXT` 是 M 的 `PARALLEL-INTEGRATION-GATE-001`，见[并行作业协议](parallel-execution-plan.md)与[执行计划 §2](development-execution-plan.md#2-上一卡交付与当前-next-边界)的 lane_next 表；B2 属 §4 B 段第二张，B1 已满足其「inventory 后」前置；在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle。**第一刀 `CORE-040`/`CORE-050` 与第二刀 `OFFLINE-030` 已交，剩余是 5 条 `only_another_build` 的 `ADMIT-001/040/060/100/110`，以及卡面后半段 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak**）。**那 5 条 ADMIT 行与 `OFFLINE-030` 一样都在 `non_mandatory` 名单里，再跑也不会动任何一门**；今天 11 个包的 block 字段里没有 `CASE_VERSION_MISMATCH`，剩下的阻因是 `REQUIRED_CASE_NOT_REGISTERED` 与 `NO_MANDATORY_CASES`，属 case 设计与门禁决定（主控）。**禁止连接用户远程服；V08 仍未提升**，A4 是新的授权门，B 段推进不等于入服许可。W60 的 `promotable: true` 只是机器候选，**晋级属 `P0-GATE-PROMOTION-001`（主控）**，它既不等于 `p0-core tested`，也不等于任何门已点亮；执行侧不翻 `status/gaps`、不改 case/registry 求绿。A1 留下的 `V1201-DEMO-CASE-FREEZE-001`、A2 留下的 `V1201-DISK-PREFLIGHT-001`/`V1201-SRV-RESOLVER-001`，与 B1 留下的六个产品事实载体问题、`ADMIT-030/050` 的 case id 拆分都是 `BLOCKED_DECISION`，留在主控手里；B1 交出的 `P0-OFFLINE-090-100-EVIDENCE-CHECK-001` 是 `QUEUED_PROPOSED`，排期是主控动作。本地真跑再受 runner 缺陷阻断时，保留原始材料并按需另登修复卡。

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
