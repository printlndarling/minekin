# Minekin 开发执行计划（现行唯一队列）

更新：2026-09-26。产品主线是 **1.20.1**；1.21.4 仅作必要回归基线。本文是唯一任务状态入口；[完整产品范围](roadmap.md)、[跨版本契约](version-auto-to-server-control-plan.md) 和各专项契约决定“做对什么”，本文决定“现在做什么”。截至 `cef712b` 的六千余行旧计划及 Qoder 尚未提交的第七类审计草稿完整保存在[历史计划](development-execution-history-through-cef712b.md)，不是当前队列。

## 0. 状态与证据口径

`current_next: PARALLEL-INTEGRATION-GATE-001`（M 的 integration gate 卡，见 §2 的 lane_next 表）。自 2026-09-26 起按[并行作业协议](parallel-execution-plan.md)激活 lane_next：主干只保留这一个 integration `NEXT`；E lane 的 `NEXT` 仍是 B2 `P0-CONTROLLED-CAMPAIGN-001`（由 E 在其独立分支施工，M 只合并），S/D/V 各有一个 `lane_next`（§2），H 的 `lane_next` 等 E 释放 runner 文件租约后激活。此前 B1 `P0-EVIDENCE-INVENTORY-001` 已于 2026-09-26 以规范卷只读四桶盘点收卡（见 §2、§3.3 与[盘点记录](p0-evidence-inventory-2026-09-26.md)）。B2 的第一刀 `P0-CORE-040-050-RUN-001` 同日完成：`CORE-040`、`CORE-050` 各在当前构建上封了一份四读齐全的 PASS bundle，W60 读数转为 `promotable: true`（仅机器候选，不晋级）。**第二刀（`OFFLINE-030`）同日完成**：一次裸 join 真跑封出该 case 在本根上的第一份当前构建 PASS bundle（四读齐全 + 八行材料层判否对照），但它 `mandatory: false`，撤掉它门一字不变；同日复核第一刀的四读逐行复现（[第二刀记录](p0-offline-030-run-2026-09-26.md)）。**第三刀（5 条 `ADMIT-001/040/060/100/110`）同日完成**：五轮受控本地真跑各封一份当前构建 PASS bundle，`from_another_build` 名单长度不变（61）而该格从 5 条变 0 条，四行门读数与正对照逐字相同（[第三刀记录](p0-admit-five-run-2026-09-26.md)）。**第四刀（`CORE-030`，第一条 LAN 形状）同日完成**：宿主客户端把 `kinworld` publish 到 `25570`、加入者拨号并承认第一个快照，封出该 case 在本根上第一份当前构建 PASS bundle（判据 `2/2`、复判 `AGREES`、宿主 `settings_digest` 逐字节等于 case 的 `level.dat` pin），卷上底色 `attempts 61 / bundles 97 / from_another_build 61`，三种卷状态下门读数一字未动；这一刀是三次尝试换来的（一次 runner 确定性 `rc=2`、一次不可重现的 GLFW 崩溃封成 FAIL，材料全留），至此 B1 §7 的 9 条最小内容全部交付（[第四刀记录](p0-core030-lan-run-2026-09-26.md)）。**第五刀（`OFFLINE-001/040/050` + `ADMIT-080` 四条）同日完成**：B1 §6 三格里的第三种形状「判官只需仓库字节但本根零 bundle」由 17 条变 **13 条**，四条各封一份当前构建 PASS bundle（检查 5/3/3/6 条全 held），**门载荷 sha256 在封证前后逐字节相同**（`fb0152c8…`）；剩下的 13 条全部属 deferred 的 HOST 家族，E 在门前停住（[第五刀记录](p0-repo-four-case-run-2026-09-26.md)）。B2 本身仍是 E lane 的 `NEXT`（见 §2 与[第一刀记录](p0-core-040-050-run-2026-09-26.md)）。A3 `V1201-TESTED-GATE-READOUT-001` 同日以规范卷只读机器读数收卡（见 §2 与[复判记录](tested-gate-readout-2026-09-26.md)）；A1/A2 同日收卡。A1 `V1201-LOCAL-DEMO-REHEARSAL-001`（真跑 sealed PASS）、A2 `V1201-LOCAL-NEGATIVE-MATRIX-001`（机器读数与配对反证）（[负向矩阵复判记录](version-negative-matrix-2026-09-26.md)）按 §3 的机械流转已依次完成。B 段首张是只读证据盘点，不是 V08 晋级，也不是连接用户服务器的许可。`cef712b` 时旧队列 `NEXT=0/QUEUED=0`；本计划是用户 2026-09-26 要求“一次性编写后续任务”的新排期，不把旧卡改称未完成。**M 主控轮次（同日）已把 E 的证据分支整条 fast-forward 合入 `main`（远端 `refs/heads/main = f632665`，`git ls-remote` 复核），把 E 提出的七项阻断逐项分类（§2 那张表），并落了第一张工程卡 `INT-EVIDENCE-INTEGRITY-001`（§2 同名小节：读者不再对「台账 `SEALED` 行 ⇒ 卷上无 bundle」保持沉默），**该卡当日以 fast-forward 单独合入并把远端 `refs/heads/main` 推到 `759125f`**（`git ls-remote` 复核）；四条 `non_mandatory` 的 `PASS` 只写成当前构建读数，11 个门的 `promotable` 分布与门载荷摘要在合入前后逐字相同。**M 的第二轮（同日）把三张 lane 工程卡按依赖顺序单张合入 `main`，逐笔核过远端 SHA：`d09e9b2`（H1b：`domain.sh` 的加入基线读取具名化，③）、`ee0a439`（H1a：受控镜像带锁定的 pytest 工具链，②）、`ea5423e`（S2：`--max-bytes` 的两处具名拒答，§3.2 N2）。三个合入都不带新的真跑封证**（每笔的合并说明里 `Not-tested` 段都点名了这点）；合入树各跑一遍全量基础门，读数依次是 `2511 passed / 3 skipped`、`2512 passed / 3 skipped`、`2518 passed / 3 skipped`，ruff check/format（339 文件）、四项 tools 边界脚本、pyright `0 errors` 全绿。④（runner 使用 `sys` 而未 `import sys`）在同一轮里更正为**仓库代码未复现**，见 §2 分类表该行。

已核实的基线：V01–V07 及空 store 自动安装真跑已完成；A1 已在受控本地把自动装机与同 run 的 PLAYABLE→look/move→释放→退出接成一次 sealed PASS（§2）；1.20.1 `V1201-080` 的正常停止显式松键有 sealed PASS，registry 对应缺口已划出；`HOST-ADMISSION-DESIGN-001` 只交付了[设计和三个未决所有权问题](host-admission-session-coordinate-design.md#5-分歧矩阵所有权问题为什么不由本卡回答)。这些都**不等于** V08、V09、V10 或完整 Minekin 完成。1.20.1 registry 其余缺口按现行文件和 `verify_tested_provenance.py` 重新读取，不以本文计数代替机器结果（A3 已按此重读：provenance `verified: true / rc=0`，边界见 §2 与[复判记录](tested-gate-readout-2026-09-26.md)）。旧 W00/W10/W20 的 `promotable` 读数不等于总体 `p0-core tested`；`p0-core`/七场景 campaign 仍有真实证据缺口。CI、ping、旧 bundle、单测、文档自述均不能证明真实入服。

状态语义：`NEXT` 可立即领取；`QUEUED` 必须依赖满足后才顺序提升；`BLOCKED_DECISION` 要用户明确拍板；`BLOCKED_EVIDENCE` 要真实材料；`DEFERRED` 不可开工。以下顺序是**长程任务账本**，不是对未冻结功能/案例的授权。主干只出现一个 integration `NEXT`，完成一张后才原子更新队列；已划清独占路径的并行分支各按 §2 持有一个 `lane_next`，`lane_next` 只代表该分支可开发，不构成主干 `NEXT`、也不写成主干 `DONE`。不会因为没有可执行卡而创建“再盘点一次”的 docs-only 任务。

## 1. 连续执行协议

1. 每次冷启动按[交接](qoder-execution-handoff.md)检查工作树、HEAD、工作分支、远端 `main` SHA；未提交改动归原作者，不 reset、stash、覆盖。读本文主干 `NEXT`（lane 会话另读自己分支的 `lane_next`）、对应专项契约和现行机器清单，写下 baseline SHA、允许路径、停止条件。
2. 只做 `NEXT`。需要产品选择、真实外部授权、修改卡外判据/registry、删除数据、接管进程时停止该分支，登记证据和 `BLOCKED_*`；继续已有的独立安全卡，不自行猜结论。测试失败先诊断是否本卡范围内的缺陷；范围外登记单独修复卡，由主控排期。
3. 一卡一可逆提交。先验路径范围和两轴审查（契约/工程），再跑与改动相称的本地门禁；运行时结论必须来自当前 build 的 Docker/受控真跑和 sealed bundle。`verify`、`rejudge`、适用 `replay`、`report_promotion` 四读、负向反证和 provenance 分开记录。失败工件不覆盖，敏感目标不入库。
4. 卡通过后更新本文及[当前 TODO](development-todo.md)，commit，立即 push 本 lane 工作分支并核远端 SHA。lane 会话**不得**push `main`；`main` 只由主控 M 在双审与门禁通过后按依赖顺序合并更新，合后核 `origin/main` SHA 并向各 lane 发新 base，该卡此时才算主干 `DONE`/回写。push 失败不领取下一张。Qoder 可以在这些条件全部满足时机械流转已明确排队的卡；`BLOCKED_DECISION`、HOST/W80+、PERSIST、在线认证、扩大公网访问不在委托内。
5. 基础门禁：`uv run --frozen pytest -q`，Ruff check/format，Pyright，`check_boundaries.py`、`check_case_assertions.py`、`verify_fixture_digests.py`、`check_workflow_pins.py`、`git diff --check`。Bridge/proto 加四项 Bridge 检查和 Java 21 `./gradlew check --rerun-tasks`（不可用 UP-TO-DATE 或 FROM-CACHE 替代）。Docker/真实客户端卡须跑其专项真实门禁。提交正文记 `Constraint`、`Rejected`、`Confidence`、`Scope-risk`、`Not-tested`。

## 2. 上一卡交付与当前 NEXT 边界

当前主干 `NEXT` 是 **M 的 integration gate 卡 `PARALLEL-INTEGRATION-GATE-001`**：逐卡审 lane 分支的允许路径、契约、测试与真实证据，按依赖顺序合并并推 `main`、核远端 SHA。E lane 的 `NEXT` 仍是 **B2 `P0-CONTROLLED-CAMPAIGN-001`**（其「inventory 后」前置已由 B1 满足），在独立分支/独立 worktree 施工，规范证据卷仍仅 E 写。B1 收卡后按 §3 的机械排期提升：V08 仍未获新授权，A4 不设 `NEXT`；HOST/PERSIST 仍 `DEFERRED`。以下是刚收掉的 B1、A3、A2 与 A1。

### lane_next 激活表（2026-09-26，随[并行作业协议](parallel-execution-plan.md)合入生效）

| lane | 分支 / worktree | `lane_next` | 状态 |
| --- | --- | --- | --- |
| E 真实运行/证据 | `codex/minekin-evidence` @ `../minekin-wt-evidence`（B2 checkpoint `6a02ac6` 已交，已迁出共享 checkout） | B2 `P0-CONTROLLED-CAMPAIGN-001`；本轮另派 `E-CO` 镜像内自检重封一轮（§4 同名行） | 进行中，B2 归 E，不因 lane 化改判；规范卷唯一写入者不变。**B2 五刀的证据文档与 `f632665` 已由 M 双审合入 `main`（远端 SHA 已核），四条 repo-check 行是 `non_mandatory` 的当前构建读数，不构成晋级**；②/① 落地后 E 的下一件受控验证已派出：`E-CO` 在 `../minekin-wt-evidence` 施工，base 为合入三张工程卡后的远端 `main`，写规范卷、只推自己分支。**待读的既成事实**：③ 修好后第四刀那条被 `rc=2` 掐死的 CORE-030 尝试可以重跑，但那要占规范卷与 `seal_run_evidence.py` 窗口，仍按协议先与 E 协调，不与 `E-CO` 同时开工。**`E-CO` 的卷上读数 M 已只读快照（15:45–15:52 UTC）并记在 §4 同名行**：四条 seq 2 attempt 已在卷、`verify_rc=0` ×4、门载荷摘要一字未动；E 的文档记录尚未 push ⇒ 仍是「仅在分支」，M 不收卡 |
| S 自动入服安全 | `codex/minekin-auto-entry` @ `../minekin-wt-auto-entry`，base 见本表激活时远端 `main` | S1 `V1201-AUTO-ENTRY-GATE-ORDER-001`（N1，§3.2）**已合入主干且已收口**（合并 `b88e36f`；E 的规范卷重跑读数 2026-09-26 已交并合入，见 §3.2 N1 行）；S2 `V1201-MAX-BYTES-VALIDATION-001`（N2）**已合入主干**（合并 `ea5423e`，2026-09-26，S 提交 `20e2e60`）；`lane_next`：**暂无安全的 S 卡** —— §3.2 剩下的 N3/N4 都是 `BLOCKED_DECISION`（要冻结的是产品语义与断言，不是代码），不由 lane 自造，也不占 `lane_next` | S1、S2 实现经双审+全量基础门合入；新 base 以远端 `main` 为准。**S2 的两处口径由 M 在合并说明里定了**：(a) 卡面那句「`--auto-bundle` 与 `--profile` 同给被静默忽略」在本 base 上不成立（`5e53429` 起 argparse 互斥组 `exit 2`），实测形状是 `--max-bytes` + `--profile`，实现与断言按 A2 §3.2 N2 的读数走；(b) `bundle install --max-bytes 0/-1` 的同族崩溃计入 N2 —— 同一个非正预算撞上同一个 `ValueError`，且 `bootstrap.py` 在 S 的既有独占面内（协议 §2 那行已授予「必要 `bootstrap.py`」）。合入后 `session start --profile --max-bytes N` 从「接受并忽略」变 `exit 2`，属可观察的 CLI 行为变化，已记在该笔 `Scope-risk` |
| D Web Dashboard 前端 | `codex/minekin-dashboard` @ `../minekin-wt-dashboard` | D1 `DASHBOARD-READONLY-SHELL-001` **已合入主干**（合并 `8aab153`，2026-09-26）；`lane_next`：D2 真实接线等 G lane 冻结 Gateway 只读契约后由 M 派卡 | D1 只读外壳合入（`dashboard/**` 50 文件；默认 mock、gateway 需显式 opt-in 且端点是 fail-closed 提案非契约；无 Bridge/DB/凭据，只读不变量由 Vitest/Playwright 固定；P0 Core 零 Node 依赖，ADR 0001 保持）。M 在合入树复跑 tsc/Vitest/build 绿后推送；Playwright e2e 复用 D 会话双 Node 版本绿的材料。真实读数声称仍被 G 未冻结契约阻断 |
| V 1.20.1 游戏内调试 | `codex/minekin-v1201-validation` @ `../minekin-wt-v1201-validation` | V1 `V1201-PARTIAL-STORE-AND-JOIN-SMOKE-001` **已合入主干**（合并 `eb6f63d`，2026-09-26）；`lane_next`：暂无，待 H-1/H-2 落地后由 M 重新派卡 | V1 按卡面收口为 `PARTIAL / BLOCKED_HARNESS`（[报告](v1201-partial-store-and-join-smoke-2026-09-26.md)：A 段逐件复验 PASS＋两缺陷复现；B 段 status/自动选择/摘要门真跑 PASS，完整 JOIN 阻于 bridge 不可联网取＋G1 封证＋G2 探测失明；四读如实 `N/A`，未进规范卷、未搬旧 PASS）；其交办的 H-1..H-5 登记给 H，其中 H-3/H-4 属产品下载器行为，另卡由 M 排期，不并入了结 V1 的这次合并 |
| H 测试 Harness | `codex/minekin-harness` @ `../minekin-wt-harness`（H1b 那支 `codex/minekin-runner-named-failure` @ `../minekin-wt-runner` 已合完，其 worktree 空出来） | `H1a TEST-ORCHESTRATOR-PINNED-PYTEST-001`（②）**已合入主干**（合并 `ee0a439`，2026-09-26，H 提交 `44922b8`）；`H1b RUNNER-NAMED-FAILURE-001`（③）**已合入主干**（合并 `d09e9b2`，H 提交 `1dc6101`，只闭合缺陷 A；④ 更正为仓库代码未复现）；`lane_next` = **`V1201-AUTO-PATH-RUNNER-001`（G1/G2，§3.1）** | 已激活（2026-09-26，E 的 B2 checkpoint `6a02ac6` 落地且本批 runner 文件零改动，文件租约释放）；E 重开真跑封证时按协议先协调 `seal_run_evidence.py` 独占窗口；V1 报告交办的 H-1..H-5（同 run 封证、bridge 产物化、损坏 blob 重取、孤儿 `.staging` 回收、`enable-status` 取舍）随 G1/G2 一并权衡，其中 H-3/H-4 触产品 `src/**`，超出 H 独占面，须由 M 另立卡。**G1/G2 本轮派到 `../minekin-wt-runner`（新支 `codex/minekin-auto-path-runner`，base 远端 `main`）**：H1b 刚改过同一批 runner 文件，两张卡不并行开工，故用空出来的 runner worktree 顺序接手。**边界由 M 写死在派工里**：只动 `test-orchestrator/**` 与其契约测试；验证一律挂**lane 自己的卷**，规范卷 `minekin-runner-data` 此刻归 E（`E-CO` 在跑）不得指名挂载；真跑到需要规范卷或 `seal_run_evidence.py` 窗口时停在该前置上报，不抢窗口 |

每个 `lane_next` 只代表该分支可开发；分支 PASS/交付不等于主干 `DONE`，只有 M 合并并通过相应门禁后才回写主干状态。跨 lane 修改先在协议 §2 冲突表登记；同一文件仅一名 owner。上表 `base` 只记激活时点：lane 会话开新卡前一律 `git fetch origin`，以当时远端 `main` 最新 SHA 为重建/rebase 基底；M 每合一张卡即推 `main`，新 base 随远端自然发布。

### E 提出的七项阻断：M 的逐项分类（2026-09-26，主控轮次）

来源是[第五刀记录](p0-repo-four-case-run-2026-09-26.md) §5–§7 与[交接](qoder-execution-handoff.md)里 E 点名的「待主控点的五件 + 新加两件」。分类按现行契约，不按报告好不好看：

| 记号 | 事项 | 分类 | 处置 |
| --- | --- | --- | --- |
| ① | 台账有 `SEALED` 行、卷上无对应 bundle，读者一字不提 | **普通工程缺陷（读者侧的完整性）** | 本轮开卡并交付：`INT-EVIDENCE-INTEGRITY-001`（下一节），已以 fast-forward 合入 `main`（远端 `759125f`） |
| ② | 受控镜像不带钉住的 pytest ⇒ 在镜像里跑仓库自检会封出**环境造成的假 FAIL** | **基础设施缺陷** | **已合入 `main`（合并 `ee0a439`，2026-09-26）**：`H1a` 把锁文件钉住的测试工具链装进 `test-orchestrator/runner/Dockerfile`，验收在镜像内真跑一条 pytest 类判据。M 在同一棵树上独立复量了两头：`import pytest` 在 `minekin-runner-before:local` 是 `ModuleNotFoundError`、在新镜像是 `9.1.1`（Python 3.12.3）；`run_repo_case.py --case tests/fixtures/cases/offline-001.json` 修前 `rc=1` 且五条 detail 全是 `No module named pytest`，修后 `rc=0`、`observed` 五条齐全、`failures []`。新契约测试把 Dockerfile 的每个 pip 参数钉成 `name==version` 且必须等于 `uv.lock`——M 用「浮动 pin」与「版本漂移到 9.0.0」两次反证量过它确实会红（都在工作树里做、都 `git checkout` 回滚，无提交）。已封四条 repo bundle 的 `environment` 段**不重封**（口径 ②-b 不变），镜像内重封一轮另卡：`E-CO` |
| ③ | `domain.sh:657` 在全新加入者 Kin 上确定性 `rc=2` 且不给具名理由 | 普通工程缺陷（runner 编排） | **已合入 `main`（合并 `d09e9b2`，2026-09-26）**：`H1b` 让基线读取双向具名——目录缺失按设计走空基线并打出具名一行，目录存在却列不出来才 `exit 2` 且不再吞掉 `ls` 自己的诊断；加入者准备同时建 `run/session`。M 在受控镜像里用同一份从真实脚本抽出的区段（`set -euo pipefail` 的新 `bash` 进程）复量四格：修前全新 Kin `rc=2` + stderr **0 字节**、修前走过真实 prep 仍 `rc=2` + 0 字节；修后同一反例 `rc=0` + 那一行 134 字节具名读数、修后走真实 prep `rc=0` + 无 stderr；正对照（`run/session/` 里有一个 session）`before=[1111…] rc=0`，说明修复不是把分支消音。第四刀那次失败 attempt 与材料原样保留，重跑属 E 的规范卷轮次 |
| ④ | runner 某处使用 `sys` 而未 `import sys` | **更正：仓库代码未复现**（不是缺陷，是读数来源错认） | 主干 `ea5423e` 上量过的两条扫描：`git ls-files test-orchestrator` 只有 `2 .sh / 2 .md / 1 Dockerfile`，即 **H 面上没有 Python 文件**；全仓 246 个受跟踪 `.py` 里 `sys.` 的两处命中都在字符串字面量与 docstring 内（`tests/contract/test_runner_scripts.py:329,333`、`tests/unit/test_verify_fixture_digests.py:26`），而 `domain.sh` 里所有内联 `python -c` 用的是 `import json,sys`（`:265,269,317,321,390`）。当初观察到的 `NameError` 出自 `.tmp/` 下未受跟踪的探针。`H1b` 因此只闭合缺陷 A，这一条以「未复现」结案而不是记一次修复；旧日志（A2 基线里同形的 `NameError` 与空端口表）不追改，作为已过期读数保留 |
| ⑤ | GLFW `[0x1000E]` 崩溃**不可重现** | 观察项，不是缺陷 | 开 `H1c` 只在再次量到时触发（材料已在第四刀记录里）；当前不排实现卡，不补断言 |
| ⑥ | `REQUIRED_CASE_NOT_REGISTERED` / `NO_MANDATORY_CASES` 与四条 `mandatory: false` 的 PASS 是否晋级 | **主控保留（门禁决定）** | 不属工程缺陷：动的是 case 集合与 `mandatory` 语义，属 `P0-GATE-PROMOTION-001`。本轮不改 registry、不翻 `status/gaps`，四条 `PASS` 只写成 `non_mandatory` 行的当前构建读数 |
| ⑦ | HOST 家族剩下 13 条（+ 2 条）不封 | **重大决策保留** | HOST §5 所有权未冻结 ⇒ 维持 `DEFERRED`，E 与 M 都不自造断言 |

② 的口径同时回答第五刀 §5 请 M 定的那一格：**两条都要**——镜像该带可用的工具链（②），已经封进去的 `environment` 段仍按封存进程解释（②-b），因为重封会让一批判据只依赖工具链存在与否的字节搬家。

### `INT-EVIDENCE-INTEGRITY-001` — `DONE`（M 主控，2026-09-26；分支 `codex/minekin-evidence-integrity` @ `../minekin-wt-integrity`，提交 `759125f`，已 fast-forward 合入 `main` 并复核远端 SHA 同一枚）

**这一格的状态标签**：代码与单测**已合入 main**；卷上读数**真实只读复跑**（§读数列）；本卡**没有**产生新的 sealed evidence，也**没有**验证「丢失已被阻止」这类说法——它只把丢失变成可见。

目的：把 ① 从「静默」变成「具名」。允许路径只有两处：`tools/report_promotion.py`（读者）与 `tests/unit/test_report_promotion.py`（判读它的测试）。不碰产品代码、case 判据、registry 字节、`status/gaps`，不重封任何历史 bundle，规范卷全程 `:ro`。

**最小反例（先量红）**：`tests/unit/test_report_promotion.py` 三条新案，同一套具序列的 bundle，只差「早期那次的字节还在不在」。

```bash
uv run --frozen pytest tests/unit/test_report_promotion.py -q \
  -k "lost or retained_earlier or missing_latest"
# 修后实测（当前测试名）：4 passed, 42 deselected in 3.05s
# 修复前实测：3 failed, 1 passed, 42 deselected in 9.95s
#   test_a_lost_earlier_attempt_is_refused_rather_than_reported → Failed: DID NOT RAISE
#     （删掉 seq 1 的 FAIL bundle，报告照样出、`promotable` 不变、没有任何字段点名）
#   test_a_lost_latest_attempt_is_named… / test_retained_earlier_attempt_keeps_the_report_readable
#     → KeyError: 'sealed_without_bundle'
#   test_missing_latest_bundle_blocks_older_pass → passed（旧行为已在，本卡不回退它）
```

那第一行红量用的是它当时的名字（那时方案还是「非最新也拒读」）；量到可逆切片与丢失同形之后改成具名，那条测试随之改名为 `test_a_lost_earlier_attempt_is_named_rather_than_absorbed`，两半判据不变（缺字节 ⇒ 出现在名单里、字节在 ⇒ `[]`）。红读数因此是**当时的**，按上表复现只会读到绿色的那一半。

同一件事在真卷上的形状由 E 的 R-E 量出：副本里删掉四个 run 目录 ⇒ `bundles 9→5`、`attempts` 仍是 65、`unsealed 0 / unreadable 0`。反方向（有 bundle 无台账）09-25 已量过是 `unusable / exit 2`——**半套卷的拒绝一直只朝一个方向生效**。

**验收**：(1) 报告里新增 `evidence.sealed_without_bundle`，逐条 `{case_id, run_id, sequence}`，覆盖最新与非最新两种位置；(2) 序列最新那次缺字节仍按现行规则把该 case 判阻（不回退）；(3) **不拒读**：故意只拷一部分的可逆切片必须仍能出报告，并在新字段里看见自己缺了哪些行——因为「丢失」与「有意切片」在盘上是同一个形状，拒读会拆掉唯一能在卷外复读 19 GB 卷的通道；(4) 完整规范卷的读数在本卡前后一字不动。

**实现**：`discover()` 补上台账→bundle 的方向（`has_bundle = verifications ∪ unreadable_run_ids`，`status == "SEALED"` 且不在其中者入列），`EvidenceOnDisk` 多一个 `sealed_without_bundle` 字段，报告多列那一段，模块 docstring 写明「为什么到此为止、不拒读」。

**读数（修后，`uv run --frozen`）**：`tests/unit/test_report_promotion.py` → `46 passed`；`test_report_promotion.py + test_case_registry.py + test_attempt_registry.py` → `140 passed`（改语义前那一轮，语义改为具名后由全量门重跑覆盖）。容器内对规范卷只读复跑（`/src:ro` + `/data:ro` + `MINEKIN_HOME=/data`）：`attempts 65 / bundles 101 / unverified 0 / unsealed 0 / unreadable 0 / sealed_without_bundle []`，`rc=1`，`overall False ['REQUIRED_CASE_NOT_REGISTERED']` —— 与修前逐字相同 ⇒ 本卡不改变任何门的读数。复现脚本 `.tmp/m-probe-sealed-without-bundle.py`、`.tmp/m-probe-slice-reads.py`（未跟踪，随容器销毁）。

**非 vacuity 与正对照**：切片副本（只拷 `repo-evidence/` 532 KB + 整份台账，`MINEKIN_HOME=/tmp/m-integrity-slice`）修后 `rc=1` 仍可读，`bundles 9`、`sealed_without_bundle 58`（前几行是 `ADMIT-001 seq 1/2`、`ADMIT-040 seq 1`），门分布 `promotable True 2 / False 9`，`overall False ['CASE_VERSION_MISMATCH', 'REQUIRED_CASE_NOT_REGISTERED']`。**同一份读者在完整卷上给 `[]`、在切片上给 58 条**，字段既不是恒空也不是恒红；E 的可逆切片通道保持可用。

**本卡不声称**：不点亮任何门晋级，不改 `mandatory`/registry；不说「丢失 bundle 现在会被阻止」——它现在会被**说出**，是否升级成门禁条件是 ⑥（`P0-GATE-PROMOTION-001`，主控）；不声称已修 ②③④；不声称已连接或探测用户远程服。


### B2 的第一刀（`P0-CORE-040-050-RUN-001`）— 已完成（2026-09-26），B2 本身仍是 E lane 的 `NEXT`

目的：交付 B2 卡面点名的最小一刀——74 条 mandatory 里唯二「只差一轮当前构建真跑」的 `CORE-040`、`CORE-050`。边界照卡面：只跑不改（产品代码、case 判据、registry 字节、`status/gaps` 一律不碰），失败材料全留，不晋级任何门。

交付（baseline `6f0f562`，三轮真跑 + 三份只读日志，全部在规范卷 `minekin-runner-data` 与 `kin-01` 上；读数 run 的 `os.access('/src'|'/data', os.W_OK)=False`）：

- 两条判绿行各过**四读**：harness 封证 verdict、`minekin_core evidence verify`、`report_promotion` row、独立复判 `tools/rejudge_evidence.py`（`observed=6/6` 与 `4/4`，`disagreements=[]`），且 `case_version` 与今天的摘要逐字节相同、`from_repository_build: true`（jar 实测 sha1/size 与 `SERVER_RECIPES["1.21.4"]` 的 pin 相同）。
- W60 读数由 `promotable: false / CASE_VERSION_MISMATCH` 变 **`promotable: true / blocks []`**；`p0-core` 阻因换成 12 条缺 fixture。**这只是机器候选，晋级属 `P0-GATE-PROMOTION-001`（主控）**。
- `CORE-050` 第 1 次 attempt 真实 **FAIL** 并保留：本次命令漏 `MINEKIN_DOMAIN_STILL=1`，`domain.sh:1218` 对 `--hold-at join` 跳过走位等待，判据要 ≥2 份服务端位置读数 ⇒ `NO_SERVER_READINGS`。判据未改、材料未删、attempt 序列未覆盖。
- 反证四组（P 正对照 / R1 撤 `CORE-040` run / R2 撤 `CORE-050` PASS run ⇒ 门立刻 `CASE_VERSION_MISMATCH` / R3 只改一位封进去的字节 ⇒ `EVIDENCE_NOT_VERIFIED` + `rc=12` + 复判 `unjudged`，且规范卷同一 run 仍 `verified`）。
- 记录：[CORE-040 / CORE-050 当前构建真跑封证](p0-core-040-050-run-2026-09-26.md)（含 §7 列出的 B2 剩余范围）。

B2 的剩余范围没有因为这一刀而消失：`OFFLINE-030`、5 条 `only_another_build` 的 `ADMIT` 行、以及卡面后半段的 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak 都还没做。（`OFFLINE-030` 同日由下面的第二刀交出；其余照旧。）

### B2 的第二刀（`OFFLINE-030`）— 已完成（2026-09-26），B2 本身仍是 E lane 的 `NEXT`

目的：交 B2 卡面在「只差运行」名单里剩下的那一格——B1 §9 按判据形状切出的「判官要运行材料且本根零 bundle」**只有 1 条**，就是 `OFFLINE-030`。边界同第一刀：只跑不改（产品代码、case 判据、registry 字节、`status/gaps` 一律不碰），全程受控本地 dedicated offline（`controlled-offline-server.json`，loopback-only），不接触用户远程服。

交付（baseline `e9288e7`，一轮真跑 + 两份只读日志，规范卷 `minekin-runner-data` 与 `kin-01`；两份只读日志开头均印 `src writable False | data writable False`）：

- 裸 join 一次判绿（`run-174`，run `3ea7c6b9…`，bundle `63e7580586e7…`，`case_version f3d834e93e93…` == 今天的 registry 摘要）：**四读齐全**——封证 verdict `PASS / failures [] / attempt 1`、`evidence verify` `verified true / rc=0`、`report_promotion` row `build=True verified=True re_judged=AGREES crit_match=True violations=0`、独立复判 `agrees / observed=1/1 disagreements=[]`。jar 实测 sha1/size 与 `SERVER_RECIPES["1.21.4"]` 的 pin 逐字节相同。
- **这一刀不点亮任何东西**：该 case `mandatory: false`（日志实测），今天列在 `overall.requirement.non_mandatory`；把这份 bundle 从镜像副本里撤掉，W30 / W60 / `p0-core` / overall 四行读数与正对照**逐字相同**。它改的是 B1 的盘点桶（`no_bundle_on_this_root` 那格 1→0），不是门。
- **判官能答「不」**：同一份封进去的材料一次只改一个事实，八行各得一个具名否（`LEDGER_UNREADABLE` / `JOINS_RECORDED:0` / `JOINS_RECORDED:2` / `JOIN_ROW_NOT_ATTRIBUTABLE` / `NO_SNAPSHOT_ADMITTED` / `CONNECTION_NOT_PLAYABLE` / `JOIN_NOT_LOGGED` / `IDENTITY_UUID_MISMATCH`），正对照 `PASS 1/1`；改字节的篡改仍是 `unjudged + ARTIFACT_DIGEST_MISMATCH`（护栏与第一刀同一形状）。边界写在记录 §6 末段：这是**进程内**材料对照，不是活读取路径的对照。
- 顺带量到的全局事实（同一份只读日志覆盖 11 个包的全部 block 字段）：**今天没有任何门阻在 `CASE_VERSION_MISMATCH` 上**，剩下的阻因只有 `REQUIRED_CASE_NOT_REGISTERED` 与 `NO_MANDATORY_CASES`。
- 同日复核第一刀：重跑 `report_promotion` + 四读，`CORE-040`、`CORE-050` 两行逐行复现（`85a97e3b` `PASS/AGREES 6/6`、`c20a20f1` `PASS/AGREES 4/4`、`eb7f9086` `FAIL/AGREES 3/4` 材料仍在），W60 仍 `promotable: true / blocks []`，`p0-core`、overall 仍 `false`；卷计数 `53/89 → 54/90`，唯一变化就是本刀新增那一份。
- 记录：[OFFLINE-030 当前构建真跑封证](p0-offline-030-run-2026-09-26.md)。

**这一刀把 B2 的「能靠跑闭合」部分见底了**：还剩 5 条 `only_another_build` 的 `ADMIT` 行（`ADMIT-001/040/060/100/110`），而第二刀记录 §1 的 `non_mandatory` 名单显示它们与 `OFFLINE-030` 一样**都不是 mandatory**——再跑也不会动任何一门。卡面后半段的 L3/L5/L6、崩溃恢复、重启协调、offline identity 其余格与 soak 要的是新断言/新场景（属 case 设计与 `P0-GATE-PROMOTION-001`，主控），不是同一批判据的重跑；`HOST-030/040` 仍 deferred，不计入本卡。（**同日回填**：那句「还剩 5 条」由第三刀交出 5 条 `ADMIT` 行、第四刀交出 `CORE-030` 而清空；B1 §6 三格剩下的第三种形状「判官只需仓库字节但本根零 bundle」17 条，也在第五刀按既有仓库自检通道交出非 HOST 的 4 条（17 → 13，见 §4 B2 行与[第五刀记录](p0-repo-four-case-run-2026-09-26.md)）。本段剩下的两点今天仍成立：卡面后半段要的是新断言，而剩下的 13 条**全部**属 deferred 的 HOST 家族。）

### `P0-EVIDENCE-INVENTORY-001` — `DONE`（2026-09-26）

目的：把契约要求的 74 条 case 在**规范数据卷**与**当前仓库构建**上逐条标注到四个桶（缺 fixture / 缺当前 build 真证据 / 真实失败 / 产品未实现），先复用旧清单，只把有明确必要性的 missing case 排成独立实现卡，不把盘点本身冒充门绿。只读卡：不改产品代码、case 判据、registry 字节、`status/gaps`，不重跑真实运行、不重封证据、失败材料全留。

交付（baseline `37f8deb`，两个 `.tmp/` 未跟踪脚本 + 两份日志，容器内 `os.access('/data', os.W_OK)=False` 与 `os.access('/src', os.W_OK)=False` 为只读凭据）：

- 交付形式（卡面「以机器读数收卡」）：新增只读记录 [docs/p0-evidence-inventory-2026-09-26.md](p0-evidence-inventory-2026-09-26.md)，含 §0 复现入口（两条 docker 读数/反证 + §5 六个代码锚点的 grep 入口）、§1 桶数读数、§2 逐桶名单、§3 十一门读数与三种 block 的语义差别、§4 真实失败桶为何为空、§5 31 条缺 fixture 的甲/乙两分、§6 28 条按成因逐条、§7 四格登记、§8 反证、§9 排卡建议。
- 四桶：`missing_fixture 31 / no_current_build_evidence 28 / real_failure_on_current_build 0 / current_build_pass 15`（74 条恰落一桶）。28 条的成因切分：`no_bundle_on_this_root 18`、`only_another_build 10`，第三种成因今天为空但被 R4 真实触发过。按判据形状再看一层（日志 §9）：判官要运行材料且本根零 bundle **1 条**（`OFFLINE-030`）、要运行材料但只有别的构建的 bundle **10 条**（mandatory 只含 `CORE-040`、`CORE-050`）、只需仓库字节但本根零 bundle **17 条**。
- 逐门：W00/W10/W20 `promotable: true`；W30/W50/host-integrated/p0-nav-exp 阻在 `NO_MANDATORY_CASES`（+ 缺定义）；W40 只阻在缺定义；W60 与 `p0-core` 阻在 `CASE_VERSION_MISMATCH`（`CORE-040`、`CORE-050`）；W70 只阻在 `NO_MANDATORY_CASES`。三种 block 分别对应「先要判据设计」「要一轮当前构建真跑」「是主控的门禁决策」——盘点一张门都不点亮。
- 产品未实现这一桶的正确读法：已注册 case 上为空（`by_judge.unimplemented == 0`、`mixed == 0`、`unregistered_assertions 0`）；缺 fixture 的 31 条里今天点名 **6 条整条**（`ADMIT-010/020/090/120`、`CORE-080`、`OFFLINE-060`）与 **2 个半句**（`OFFLINE-070` 的 revision／人格根、`OFFLINE-080` 的封禁），其余属甲类（写断言即可）或 deferred。HOST 18 条**不判**（等主控对 HOST §5 三格表态）。
- 顺带量到的两处口径滞后（原文照引不改，记录在册）：契约 crash/outbox 那行说 `CORE-060` 的 runtime 强杀窗「打不中」，磁盘上该 case id 已有 9 个 bundle、attempt 链 seq4 `ed2bbad7…` 是当前构建 PASS，其来源是历史 `:5936-5941` 的 1.21.4 换代重封；旧清单把 31 条统一写成「需先把判据写成断言」，其中 OFFLINE 三条不能只靠写断言闭合。
- 非空转：正对照即 15/31/28；四条反转各移一个机制——R1 删 `core-001.json` ⇒ `required_missing 31→32`、`current_build_pass 15→14`；R2 空数据根 ⇒ 通过桶整桶消失、28→43；R3 把 `CORE-070` 当前构建行改成 `FAIL` ⇒ 真实失败桶点名 `['CORE-070']` 且视图与规则的对账护栏同时报红；R4 改一位 case 摘要 ⇒ 第三种成因首次被触发、护栏报 `['CORE-010']`。真件上八条自检 `FAIL count = 0`、反证段 `reversal FAIL count = 0`。
- 本卡不声称：没跑过一次真实 Minecraft；没点亮任何门；`V1201-*` 族不在 74 条 required 内，所以「真实失败 0 条」不等于「这卷上没有失败」（卷上 14 份 sealed FAIL、2 份在当前构建上，原样保留）。
- 复现：记录 §0 的两条 docker 命令；日志 `.tmp/b1-evidence-inventory.log`、`.tmp/b1-inventory-reversals.log`。交出的排卡建议登记在 §3.3，不由 B1 顺手补。

### `V1201-TESTED-GATE-READOUT-001` — `DONE`（2026-09-26）

目的：在**规范数据根**（卷 `minekin-runner-data`）与**当前构建**上重读 registry/provenance、case 清单、四读与负向矩阵，给出“1.20.1 本地可玩”与“不代表远程/全版本”的精确能力边界。只读复判卡：不改产品代码、case 判据、registry 字节、`status/gaps`，不重封证据。

交付（baseline `818e2bd`，两个 `.tmp/` 脚本 + 两份日志，容器内 `os.access('/data', os.W_OK)=False` 为只读凭据）：

- 交付形式：新增只读记录 [docs/tested-gate-readout-2026-09-26.md](tested-gate-readout-2026-09-26.md)，含 §0 复现入口、§1 五问五答、§2 15 次 attempt 清单、§3/§4 正反边界、§5 与 09-25 审计对照、§6 反转、§7 不声称。
- T1 provenance 已是机器事实：`verify_tested_provenance.py --data-root /data --workspace-root /src` → `verified: true / rc=0`，两条条目 `findings: []`，registry revision `35bdd1c0…`。09-25 审计的"摘要只是文本"一格由该工具闭合（本卡 §5）。
- T2 六条被引用的 1.20.1 封证四读一致：`evidence verify` 全 `verified/PASS`（9/13/13/13/14/13 工件），`rejudge` 全 `agrees/PASS`，`replay` 全 `projected`，`report_promotion` 侧 `from_repository_build: true`、`violations: []`；六条引用行的 plan 全为 `83299ad5…` ⇒ 无一条被引用 run 落在旧 build 上。
- T3 能力边界正面：条目 19 个 capability 与六 case 断言并集**双向差集为空**；“可玩”只指那 19 件事（探测/握手、入服/首快照、限幅 move+turn、断连松键、拒快照、停止松键）加上 A1 的同 run 连续性。
- T4 边界反面：`report_promotion` 在规范卷上 W60 `false / CASE_VERSION_MISMATCH`（`CORE-040`、`CORE-050`）、W70 `false / NO_MANDATORY_CASES`、`p0-core` `false / CASE_VERSION_MISMATCH + REQUIRED_CASE_NOT_REGISTERED`、overall `false`；六条 V1201 case 全 `mandatory: false` ⇒ 本卡证据不让任何门晋级，也不改变 V08 阻断。
- T5 卷内实况（记录，不动引用）：1.20.1 家族 15 次 attempt = 6 引用 PASS + 2 本 build 等强未引用（`V1201-020` seq3 `7236c53e…`、`V1201-040` seq3 `6a86da03…`；A1 的等强 PASS `fc12d7d1…` 在独立卷 `minekin-v1201demo3`，不计入这 15 行）+ 5 旧 build（plan `ac403160…`，`from_repository_build: false`，含 seq1 的 `FAIL`/`UNJUDGED`）+ `V1201-080` seq1/2 本 build sealed **FAIL** 保留。更换 registry 引用摘要属主控动作，本卡不提议、不执行。
- 非空转：四条反转各自把读者判红——R1 空证据根 → `CITATION_BUNDLE_MISSING rc=1`；R2 引用摘要改一位 → `CITATION_DIGEST_MISMATCH rc=1`（原样消息 `"digests to dc30bdaa…, not the cited 0c30bdaa…"`）；R3 空根与规范根的 promotion 输出不同（`count 0` vs `86`）；R4 删一个工件并给另一个追加一字节 → `status: invalid rc=12` + `rejudge: unjudged / ARTIFACT_DIGEST_MISMATCH + ARTIFACT_MISSING rc=2`。正对照是 §2 表里那六条真件全绿。
- 未测并保留：F4 后半句“部分装机后旧 blob 整店复验”仍无 store 级读数；A2 的 N1–N4 与 A1 的 G1–G3 不并入本卡；1.21.4/Windows/JDK17/HOST/PERSIST/在线认证一律不声称。
- 复现：记录 §0 的两条 docker 命令（`-v minekin-runner-data:/data:ro`，反证另挂 `/src:ro`）；日志 `.tmp/a3-gate-readout.log`、`.tmp/a3-readout-reversal.log`。

### `V1201-LOCAL-NEGATIVE-MATRIX-001` — `DONE`（2026-09-26）

目的：把版本契约的九行负向矩阵按 A2 的六族逐族量出**当前 build 可重跑的拒绝类别 + 原因码**，需要真跑的两族用规范数据根的 sealed bundle 在本 build 重读，只补真实缺失的组合，不造重复 fixture、不改判据/registry/产品代码。逐行读数、复现命令、卷与配对反证都在[负向矩阵复判记录](version-negative-matrix-2026-09-26.md)，本节只留结论与卡面判据的对应。

- 交付形式（卡面"以索引/机器读数收卡"）：新增只读记录 `docs/version-negative-matrix-2026-09-26.md`；八个 `.tmp/` 未跟踪脚本 + 十个本卡新建数据卷 `minekin-v1201neg2…neg11` 保留原始材料，其中 `neg3` 是被同卡第二次运行取代的首次状态探测、`neg9` 是本卡自己构造错的失败尝试，两次都判为不确定后未采用、未覆盖。
- F1 歧义协议 / 文本-协议冲突：**成立**。真实 socket 18 行具名帧形状（`SocketStatusTransport` 真读，非 monkeypatch）全部落在预期 `outcome` 令牌上，`table rows: 20 FAIL=0`，正对照 `control_1201 → OBSERVED/exit 0`；自动入口对 `DISPLAY_TEXT_CONTRADICTS`、`MULTI_VERSION_PROXY` 各 1–2 秒 `exit=17 / ADMISSION / NEEDS_PIN` 且 store 保持 0。
- F2 错误版本 / 身份 / Bridge：**显式路径成立**。allowlist 与启动版本冲突、两版本 allowlist、`deny_all`、online-mode、非 loopback 五格在 `session start --profile` 上均 1–2 秒具名拒止；Bridge 钉错在 `bundle verify` 与 `launch-plan --dry-run` 各得 `SUPPLY_CHAIN`；未改动 recipe 正对照 `launchable: true / plan_sha256 83299ad5…`。
- F3 恶意 status / SRV / 禁区：**部分成立**。`0.0.0.0`、`169.254.169.254`、`224.0.0.1`、主机名四格在 profile 装载期具名拒止，且假端点接受计数 `0→0` 证明**拒在发出任何字节之前**（同端口的 loopback 对照把该计数从 0 变 1，证明计数非空转）；无 DNS/SRV 解析器（`SavedAddressResolver` 是唯一实现）⇒ 契约"SRV 目标改变"无法作为真实行为产生，是实际能力边界而非通过项。
- F4 hash / 中断 / 磁盘：**部分成立**。recipe 摘要不符 2 秒 `SUPPLY_CHAIN` 且 store 0；1 字节预算给出精确超额读数；半包 store 无法启动；契约"磁盘不足"一行**无实现**（N3）。
- F5 断连 / F6 旧 generation：**成立，且来自真跑封证**。`V1201-060`（`90d490ce…`，13 工件）、`V1201-070`（`eb054c0a…`，14 工件）、`V1201-080`（`22fb57f3…`，13 工件）在 baseline `11538c4` 的同一 build 上重读为 `evidence verify → verified / result PASS` 且 `rejudge_evidence.py → status: agrees`；只重读，未重封、未翻 registry。
- 非空转：四条新拒止各自配一行同入口同 store 的对照（一致的假应答进入装机、同端口 loopback 被接受、未改动 profile 被 accept、干净空 store 的未改动作正对照 `0→8→31 文件`），故矩阵不能靠"什么都拒"变绿。
- 本卡量出的真实缺口（全部按 §1.2 另登，见 §3.2）：**N1** 自动入口的门序——同一份 profile 在 `--profile` 下 2 秒拒，`--auto-bundle` 下先下到 388 文件（空 store）或先过完 3639 项（满 store）才说"只能 join loopback"，且 profile 的版本 allowlist 在自动路径上根本不参与准入（`--profile` 路径会拒同两形状）；授权本身没被绕过（`java=0`）。**N2** `--max-bytes 0/-1` 得到 `exit=70 / INTERNAL_INVARIANT`，而 `--max-bytes` 与 `--profile` 同给时被接受且被忽略。**N3** 磁盘预检缺失。**N4** 无 DNS/SRV 解析路径，契约那行 SRV 风险面 today 只能以"只接受字面 IP"收。另记一处真 socket 上不可达的 `length < 0` 死分支。
- 未测：不连任何远程目标（V08 仍未提升）；1.21.4 侧矩阵；部分装机后的整店复验（"旧 blob 仍可验"半句）；HOST/PERSIST/在线认证族。
- 复现：记录 §0 的镜像模板 + 八个脚本，每行自带时间戳目录与退出码；sealed 重读为 `-v minekin-runner-data:/data:ro` 后 `python -m minekin_core evidence verify <run_id>` 与 `python /src/tools/rejudge_evidence.py /data/kin/kin-01/run/evidence/<run_id>`。

### `V1201-LOCAL-DEMO-REHEARSAL-001` — `DONE`（2026-09-26）

目的：在**全新 Kin、全新 data root、受控本地 offline 1.20.1 服务器**上，验证“保存目标→只读探测→自动解析 tested bundle→空 per-Kin store 安装→真实启动/JOIN/首快照→PLAYABLE→一次限幅 look/move→松键/退出”的**同一 run/generation**闭环。现有 `V1201-040`（移动与转向）和 `V1201-080`（正常停止松键）是分开的证据；本卡要量集成连续性，不能把两份旧 bundle 拼成同 run。可先用当前 CLI/runner 直接跑；若工具不支持该流，记录确切缺口并单独排实现卡，不临时扩产品范围。

- 依赖：已完成 V07 真自动安装和 `V1201-080`；受控本地 runner、Java 21、当前 1.20.1 tested registry/provenance 可读取。先确认基线，不用旧构建结果代替。
- 允许：`.tmp/` 未跟踪运行脚本、私有 profile、受控 runner 数据卷、必要的本卡证据与本计划/TODO/交接；若只需编排，可跟踪最小 runner/test 调用文件。禁止：用户远程服、HOST/PERSIST、online auth、产品行为/安全契约改变、registry `status/gaps` 无证据翻转、历史 bundle 改写。运行结束只清理**本卡新建且精确验证路径**的临时会话/marker；材料先封存，不批量删。
- 验收：自动选择确切 1.20.1 bundle 且空 store `installed > 0`；同 run 的 `PlayableEstablished`、同 generation 的 lease/实际 look+move、释放及退出；客户端与独立本地服务端的位移/朝向读数分别标源；当前 build 的 sealed bundle 四读一致，至少包含一条“缺真实 JOIN/动作/释放即红”的非空转反证；失败时保留失败 attempt。先把已有 `V1201-040/080` 与新结果作清晰对照，**不把本地预演宣称为 V08 远程入服**。
- 停止：客户端不能完成自动路径、需要修改判官来让结果绿、runner 无法同 run 控制、证据材料不齐、需要碰用户服或扩大权限时停在具体阻断。不能用多次碰运气跑隐藏失败。

交付（baseline `ff1db30`，工作分支与 `main` 同步后开工；三次尝试各占一个本卡新建的全新 data root，失败材料保留）：

- **通过的 run**：Kin `kin-demo-rhs3-20260926T052929Z` / data root 卷 `minekin-v1201demo3` / run `5466221ae59843139be4c3748530e953` / attempt 1 / bundle `fc12d7d1cad0631534130df9714c13e8f69b071584311e45986de60f121cd852`，按现行 case `V1201-040`（case_version `2ef224d88492a60d4c728182f376715f9548eb176e3c952d934ee128bb041b21`）封存，结果 `PASS`，五条断言全观测。启动的 recipe `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json`，`launch_plan_digest 83299ad5e224959de8e30c72c5937a2434c4d7bba92c62f4d22cf8d89f5f6181`，bridge `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`。
- 自动安装：bundle `1.20.1-linux-x86_64-offline-java21`，`fetch_set 3639 / installed 3639 / reused 0`，运行前该 Kin 自己的 `run/artifact-store` 实测 0 文件；目标解析先由只读 status 探测得到 `OBSERVED`（protocol 763）。
- 同 run 同 generation：该 run 之后 ledger 的去重 `generation` 只有 `1`；顺序是 `JoinObserved` → `PlayableEstablished` → `InputLeaseGranted(control.move.v1)` + `InputLeaseGranted(control.look.v1)`（同一 `action_id`）→ `InputReleased reason=TIMEOUT had_lease=true` → `InputReleased reason=EXPLICIT` → `PLAYABLE→FAILED→STOPPING→STOPPED`；run 文档 `connection_state PLAYABLE`、`snapshots_admitted 1`、`actions_applied 2`、`actions_refused 0`、`outcome BRIDGE_LOST`（`session stop` 的正常收尾）。
- 两源分开：客户端侧只有 Core ledger 与 run 文档；位移/朝向断言取**独立本地服务端自己的控制台读数**——按 `run_controlled_server.py` 的同一问法（`data get entity Kin Pos` / `Rotation`）向服务器控制台写入，共 82 条读数，位置 `(-0.5,-60,0.5)→(-7.14,-60,5.99)`（水平位移约 9.3 格），朝向 `0.0→45.0`（与请求的 45° 一致），`Kin joined the game 05:45:52` / `left the game 05:47:23`。
- 四读：`minekin evidence verify` → `verified PASS`（12 artifacts）；`rejudge_evidence.py` → `AGREES`，`disagreements: []`；`replay`（CLI 与 `replay_evidence.py`）→ rc 0，投影 23 条事件；`report_promotion --work-package W60` → 该 bundle `from_repository_build: true`、`re_judged: AGREES`、`result: PASS`，W60 整体仍 `promotable: false / CASE_WITHOUT_EVIDENCE`（**晋级是主控动作，本卡不动**）。
- 非空转反证（`.tmp/v1201-rhs-counterexamples.py`，只改内存里的一次真实封存材料判读，磁盘 bundle 不改）：正对照 `V1201-020`/`V1201-040` 判 `PASS`，`V1201-080` 按自身原因 `HELD_NOTHING_WHEN_THE_SESSION_WAS_STOPPED` 判 `FAIL`（2 秒 hold 早在停止前到期，见 G3）；M1 去 JOIN → `first_snapshot_admitted`/`leave_after_join_observed`/`server_observed_join_identity` 全 `JOIN_NOT_LOGGED`；M2 去服务端位置读数 → `the_server_saw_the_kin_move:NO_SERVER_READINGS`；M3 去朝向读数 → `the_server_saw_the_kin_turn:NO_SERVER_READINGS`；M4 去到期释放 → `RELEASED_FOR_ANOTHER_REASON:EXPLICIT`；M5 去一切释放 → `NO_RELEASE_RECORDED`；M5b 去离场 → `LEAVE_NOT_LOGGED`；M6 去租约 → `NO_LEASE_GRANTED`；M7 去 Bridge 落地计数 → `NOTHING_WAS_APPLIED`；每次只多红它自己点名那条，`bad cases: 0`。
- 失败 attempt 保留：attempt 1 run `4ee21d781e0d457eb39f39b5ad8fab87`（卷 `minekin-v1201demo1`）已封存为 `FAIL`，两条服务端断言 `NO_SERVER_READINGS`——直连 pinned jar 启动服务器时没人向控制台问位置；attempt 2（卷 `minekin-v1201demo2`）在装机阶段被供应链拒绝：`asset:minecraft/sounds/music/game/infinite_amethyst.ogg failed with SUPPLY_CHAIN；partial store 不启动`，未产生 run document 也没有 bundle。两次都没有改判官、case 或 registry。
- 缺口（新登记，见 §3.1）：**G1** `domain.sh` 的参数扫描不捕获 `--auto-bundle`（`test-orchestrator/runner/domain.sh:360-382`），而封存恒定传 `--profile "${profile}"`（`:2008-2024`）且 `tools/seal_run_evidence.py:836-846` 把 `--profile` 设为必填 ⇒ 自动路径 run 今天无法用 `domain.sh` 一键封存，本卡改为手写封存。**G2** `tools/run_controlled_server.py:247` 写 `enable-status=false`，而自动解析必须观测目标 status ⇒ 同一个受控 launcher 里“能自动解析”和“有服务端读数”两半从未同时成立。**G3** 没有一条现行 case 同时断言 JOIN+PLAYABLE+look/move+释放，且 `V1201-040`（租约到期才叫释放）与 `V1201-080`（停止时仍持有）在同一次 run 里互斥。
- 未测：远程入服（V08 未获授权，本卡完全不碰）、1.21.4 必要回归、杀进程/断连引起的释放、资源包与恶意 status/SRV、多 Kin 并发、`--hold-use-seconds` 等其余输入轴。registry 的 `status/gaps` 未做任何翻转，provenance 读数留给 A3 的只读复核。
- 复现：`MSYS_NO_PATHCONV=1 docker run --rm -v <repo>:/src:ro -v minekin-v1201demo3:/data -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib --entrypoint /bin/bash -w /src minekin-runner:local -lc 'bash /src/.tmp/v1201-demo-rehearsal3.sh'`；反证：同镜像同卷 `python /src/.tmp/v1201-rhs-counterexamples.py <bundle-dir>`。三次运行都用 `tests/fixtures/registry/reviewed-tested-bundles.json` 的自动解析和 `--look-yaw-degrees 45 --hold-forward-seconds 2`。

## 3. P0 到可操作的 1.20.1 demo（按序，不跳门）

| 顺位 / ID | 状态 | 交付、验收和停止边界 |
| --- | --- | --- |
| A1 `V1201-LOCAL-DEMO-REHEARSAL-001` | `DONE`（2026-09-26，见 §2） | 全新 data root 同 run 预演：自动装机 3639/3639、同 generation 的 lease+look+move+到期释放、sealed PASS、七类反证各自变红。 |
| A2 `V1201-LOCAL-NEGATIVE-MATRIX-001` | `DONE`（2026-09-26，见 §2 与[复判记录](version-negative-matrix-2026-09-26.md)） | 六族逐族读数：18 行真 socket 状态探测 `FAIL=0`、自动入口两条 `NEEDS_PIN` 具名拒止、装载期禁区地址四拒（含“拒在发字节之前”的连接计数证明）、显式路径五拒 + Bridge 钉错两拒、`V1201-060/070/080` 本 build sealed 重读 `PASS / agrees`。量出 N1–N4 四格缺口，另登 §3.2。 |
| A3 `V1201-TESTED-GATE-READOUT-001` | `DONE`（2026-09-26，见 §2 与[复判记录](tested-gate-readout-2026-09-26.md)） | 已量出：provenance `verified/rc=0`、六条引用四读一致且全归当前 build、19 能力与六 case 断言双向差集为空、promotion 三门仍 `false`（CASE_VERSION_MISMATCH / NO_MANDATORY_CASES）、卷内 15 次 attempt 的引用与失败分布。 | 在规范数据根重读 registry/provenance、case inventory、四读和负向矩阵，给出“1.20.1 本地可玩”与“不代表远程/全版本”的精确能力边界。只做只读报告和必要的真实证据补封；需要改变 tested 声称时另开卡审查。A2 的 §3.2 缺口不并入本卡，本卡也不修产品行为。 |
| A4 `VERSION-REMOTE-SMOKE-001`（V08） | `BLOCKED_DECISION` | 用户先明确**本次**是否允许对其指定 1.20.1 测试服做一次只读 ping 和非破坏性普通玩家入服，以及运行窗口/频率。旧地址和“关闭正版验证”不是持续授权。获授权后依[原卡](version-auto-to-server-control-plan.md#v08-version-remote-smoke-001用户测试服只读探测与非破坏性入服)先 ping 后 JOIN/PLAYABLE，地址只在私有 profile，不扫描、不改服务器、不使用 op/RCON；拒绝/限流/资源包异常立即停。 |
| A5 `VERSION-SIMPLE-CONTROL-001`（V09） | `BLOCKED_DEPENDENCY` | A4 真通过后，在用户指定安全位置、另一次明确动作授权下，≤2 秒前进+小幅转向+release/退出；先 client-observed，只有独立只读 server oracle 才能声称 server-confirmed。保护插件拒绝或残留按键即停。 |
| A6 `VERSION-DEMO-ACCEPTANCE-001`（V10） | `BLOCKED_DEPENDENCY` | A1–A5 真完成后写可复现 CLI demo、风险/未测清单、1.21.4 必要回归、负向与封证索引。缺证据只能交 `PARTIAL/BLOCKED`，不写“全部完成”。 |

A2/A3 是本次新增的**本地安全顺序卡**，允许 A1 完成后机械提升；A4 不能因前三卡通过自动提升。A5 的新动作授权也不能从 A4 的只读/无动作入服授权推导。**机械排期**：A3 收卡后若 V08 尚未获得新授权，不把 A4 设成 `NEXT`；转取 B 段首张安全卡（A3 已于 2026-09-26 收卡，该分支已照此执行；B1 同日收卡后 `current_next` 现为 `P0-CONTROLLED-CAMPAIGN-001`）。B 段某卡受真实证据阻断时可转取其后不依赖它的已冻结安全卡（如平台验证），记录跳过原因；若剩余只涉及决策/未冻结契约，则保持 `current_next: none / BLOCKED_DECISION` 并一次性列出所需选择，不发明 docs-only 卡。V08 获新授权后主控重新排在安全卡边界，不能中断正在封证的 run。

### 3.1 A1 交出的三格缺口（按 §1.2 单独登记，不由 A1 顺手补）

| ID | 状态 / 依赖 | 交付与边界 |
| --- | --- | --- |
| `V1201-AUTO-PATH-RUNNER-001` | **`NEXT`（H lane 的 `lane_next`，2026-09-26 已派工到 `../minekin-wt-runner` 的新支 `codex/minekin-auto-path-runner`：仅在分支、尚未验证）**；前置已清：③ 的静默 `rc=2` 与 ② 的缺工具链都已合入主干 | 让**自动路径**与**服务端读数**在同一条受控通道里同时成立（G1+G2）：`domain.sh` 捕获 `--auto-bundle` 并在封存时按 `seal_run_evidence.py` 的实际必填项传参；受控 launcher 在“需要被 status 观测”的场景给出可复核的 `enable-status` 读数，并把 `data get entity <Kin> Pos/Rotation` 的控制台探针做成默认能力。判据不动产品行为；改 `domain.sh` 的判据/断言集合要另卡。**本轮派工的两条硬边界**：只动 `test-orchestrator/**` 与其契约测试，且**不得指名挂载规范卷 `minekin-runner-data`**（此刻归 E 的 `E-CO`，`seal_run_evidence.py` 独占窗口按协议先协调）；需要真跑到规范卷时停在该前置上报，把已完成的离线部分交回来。 |
| `V1201-DEMO-CASE-FREEZE-001` | `BLOCKED_DECISION`（等主控冻结 G3） | “一次演示 run 到底断言哪些事实”是定义 PASS 的动作，不属于执行侧自造：需要冻结是否新增融合 case、以及如何在同一次 run 里安放 `V1201-040`（租约到期释放）与 `V1201-080`（停止时仍持有）这对互斥释放原因（两次 run、放宽阈值，还是拆成两条断言）。冻结前不落 fixture、不改 registry、不封存 host 之外的新断言。 |
| 供应链单次中断（G1/G2 之外的观察） | 记录，不建卡 | attempt 2 的 `infinite_amethyst.ogg SUPPLY_CHAIN` 拒绝启动是现行防护的正确形状，但整店 25 分钟下载中一次中断就要整卡重来。是否要断点续传/单资产重试属产品选择，随 `V1201-AUTO-PATH-RUNNER-001` 一起问主控，不自行加实现。 |

### 3.2 A2 交出的四格缺口（同样按 §1.2 单独登记，不由 A2 顺手修）

| ID | 状态 / 依赖 | 交付与边界 |
| --- | --- | --- |
| **N1** `V1201-AUTO-ENTRY-GATE-ORDER-001` | **实现已合入主干 `b88e36f`（2026-09-26，S lane S1 `5355568` 经双审与全量基础门：2508 测试通过、5 条新单元/契约测试以探针计数证明“先拒后问”）**，**收口读数已交（2026-09-26，E lane）— 见[规范卷重跑读数](s1-gate-order-rerun-2026-09-26.md)** | 让 `--auto-bundle` 的准入与 `--profile` 等强：地址禁区、"managed session 只能 join loopback"、profile allowlist 与解析结果一致三件事必须在**任何下载/整店复核之前**判完。判据取复判记录 §3 的 X1 vs X2/Y2 与 B1/B2；实现不得改本记录的期望，收卡要能重跑那三组行并给出"先拒后装"的新读数。**不改 case 判据、不翻 registry。** 合入实现：`load_joinable_session_target` 在 probe/resolve 之前具名拒非法地址与禁区，`require_target_allows_launch` 在 `_resolved_entry` 后、`require_reviewed_plan` 前判 allowlist 一致性；那三组行的规范卷重跑读数由 E 在后续真跑轮补，补到前本卡不收口。**E 已补到（2026-09-26，被测构建为主干 `ed37260`，三个 `.tmp/` 脚本未改、期望未改）：X2 由 `exit=124 / store 388` 转为 `exit=17 / store 0 / 0 条 fetching`；Y2 由「整店 `fetching 3639/3639` 之后才拒」转为「整份输出 1 行、装机之前即拒」，同 store 的 Y1 仍穿过 join 授权（非空转对成立）；B1/B2 由 `exit=124` 转为 3–4 秒具名 `ADMISSION`，十三行拒止后的 store 由 290 文件变为 0，正对照 C1 仍进入装机。反向对照用 `b88e36f` 的父提交 `300ed07` 重放 X 组，得到修复前旧读数。**该收口只覆盖门序，不封 bundle、不动任何门；B12/B13 两侧都因脚本端口表为空而未测到目标场景，18 行 socket 读数的权威来源仍是 §3 复判记录。** |
| **N2** `V1201-MAX-BYTES-VALIDATION-001` | **`DONE`（M 主控合入 `main` = `ea5423e`，2026-09-26；S 提交 `20e2e60`，base `f632665`）**，不依赖 A3 | 原始缺口读数保留：`--max-bytes 0`/`-1` 当时得到 `exit=70 / INTERNAL_INVARIANT`（`ValueError` 冒到 CLI），`--max-bytes 1` 却是正确的 `SUPPLY_CHAIN` 具名拒止；`--max-bytes` 与 `--profile` 同给时被接受且被忽略。**已修的形状**：`require_spendable_budget` 在自动入口第一行具名 `BUDGET_NOT_POSITIVE`，`bundle install` 入口同规则，`session start --profile --max-bytes N` 变具名 usage 错误 `MAX_BYTES_WITHOUT_AUTO_BUNDLE`（`exit 2`）。M 在受控镜像的合并树上亲量四格（`/src:ro` + 卷外 `/tmp` store，registry/profile 路径一律不存在）：`bundle install --max-bytes 0` ⇒ `rc=10` + `[BUDGET_NOT_POSITIVE]` 且 `operation: "bundle install"`；同命令 `--max-bytes 5` ⇒ 走到 `SUPPLY_CHAIN` 读档失败（`rc=11`）证明预算被接受；`session start --profile … --max-bytes 5` ⇒ `rc=2` 具名 usage；`--profile` 独用 ⇒ 越过预算检查落到既有的 `no Kin exists`（`rc=10`），即新拒答不是无条件开火。**两处口径由 M 定**：卡面那句「`--auto-bundle` 与 `--profile` 同给被静默忽略」在本 base 不成立（`5e53429` 起 argparse 互斥组 `exit 2`），实测形状是 `--max-bytes` + `--profile`；`bundle install` 的同族崩溃计入本卡。仍**不改 case 判据、不翻 registry、不声称任何门点亮**，N2 的 CLI 读数不产 sealed bundle。 |
| **N3** `V1201-DISK-PREFLIGHT-001` | `BLOCKED_DECISION`（等主控冻结断言） | 契约"1.20.1 工件…磁盘满 → 无可启动半包"一行在 `src/minekin_core` 无任何实现（无空间预检、无对应失败类别），因此执行侧无法用真实读数回答它。需要先决定：是否装机前预检、失败令牌叫什么、与 `--max-bytes` 预算如何分工。冻结前不自造断言。 |
| **N4** `V1201-SRV-RESOLVER-001` | `BLOCKED_DECISION` | 唯一解析实现是 `SavedAddressResolver`，profile host 必须是字面 IP（复判记录 §1 F3 的 A4 行）。契约那行"SRV/DNS 目标改变"要成为可测行为，先得决定产品是否引入 SRV/DNS；若决定不引入，则该行的正确收法是"无解析路径 + 装载期禁区拒"，需要主控确认这一口径。 |
| 真 socket 上不可达的 `length < 0` 分支 | 记录，不建卡 | `adapters/launcher/server_probe.py` 的负长度守卫在真实帧上永不命中（`_read_varint` 不产负数，`negative_length` 实测 `OVERSIZE`）。属死代码清理，随任一 probe 实现卡顺手看，不作为契约缺口。 |

### 3.3 B1 交出的缺 case 排卡（按 §1.2 单独登记，不由 B1 顺手写断言也不自占队列）

B1 的卡面判据是「只把有明确必要性的 missing case 排成独立实现卡」。74 条里今天够得上「排一张卡」的只有两组，
其余三类的前置是主控选择或 deferred 族，给它们编卡号就是替主控做产品决定。完整形状与判据原文在
[盘点记录 §7、§9](p0-evidence-inventory-2026-09-26.md)。

| ID | 状态 / 依赖 | 交付与边界 |
| --- | --- | --- |
| **B1-a** `P0-CORE-040-050-RUN-001` | **`DONE`（2026-09-26，作为 B2 的第一刀执行；B2 仍是 E lane 的 `NEXT`）** | 7 条 mandatory 里唯二只差运行的行：`CORE-040`（move/look/use 的账本顺序）、`CORE-050`（首快照前拒输入）各在**当前仓库构建**上补一轮受控本地真跑。完成判据逐字取自磁盘：两条各有一份 `verified`、`case_version == 今天的摘要`（`22906123eeb7…` / `4b88854a5d46…`）、`result == PASS`、`from_repository_build: true` 的 bundle，且 W60 不再报 `CASE_VERSION_MISMATCH`。非空转反证沿用 R4 形状（改一位摘要 ⇒ 该行不再算数）。旧 attempt 全留；跑绿后 `promotable` 仍只是候选，晋级属 `P0-GATE-PROMOTION-001`。**结果见 [CORE-040/050 当前构建真跑封证](p0-core-040-050-run-2026-09-26.md)**：两条判绿行各过四读（封证 verdict、`evidence verify`、`report_promotion` row、独立复判 `6/6` 与 `4/4`），W60 今日读数 `promotable: true / blocks []`，反证 P/R1/R2/R3 齐（`CORE-050` 第 1 次 attempt 因本次命令漏 `STILL=1` 而真实 FAIL，材料保留）。 |
| **B1-b** `P0-OFFLINE-090-100-EVIDENCE-CHECK-001` | `QUEUED_PROPOSED`（等主控排期） | §5 判为**甲**的两条：待计数的字节已在 bundle 里（三份 client 日志流、`client/crash-reports/*`、`server/server.log`、账本全时间线、`previous-run-trace.jsonl`），缺的是 case 定义与断言。`OFFLINE-100` 的 A→B→A 跨 run 链按 `EVIDENCE-SEQUENCE` 形状做。两条硬边界写进卡面：`OFFLINE-090` 的 Dashboard 那半句**不在任何封存工件内**，只能登记为材料外边界，不许用 bundle 内「正文暴露次数 0」冒充整条闭合；`bundle.py:5-9` 对凭据字面量是**拒封而非脱敏**，所以「一次真实暴露」今天封不出 bundle，反证只能在副本上做并如实标注。 |
| 产品事实无载体：6 条整条 + 2 个半句 | `BLOCKED_DECISION`（缺的是选择，不是代码） | 需要主控逐条回答：账本那一行是否承载 `server_profile_id`/endpoint（`ADMIT-010/020`）；身份是否承载「人格没有被重建」（`ADMIT-090`）；oracle/canary containment 的运行期来源（`ADMIT-120`、`CORE-080`）；OFF-D/OFF-N 是否进入 reviewed 候选集（`OFFLINE-060`，今天这两候选**根本启不来**）；`identity_revision` 是否有变更事件（`OFFLINE-070` 半句，今天全仓库只在 init 写常量 1、无自增路径）；封禁是否成为独立准入分类（`OFFLINE-080` 半句，今天 `classifyDisconnect` 无 banned 分支，一句封禁响应按设计落 `UNEXPECTED_DISCONNECT`）。冻结前不自造断言、不改候选集。 |
| `ADMIT-030`、`ADMIT-050` 的 case id 拆分 | `BLOCKED_DECISION`（契约层） | 两条各自把三个互斥场景塞进一个 case id，而 promotion 对一个 case id 取任一满足 bundle ⇒ 正向证据会顺带关掉互斥的负向判据。先决定拆成几条、每条判什么，再谈 fixture。 |
| HOST 18 条 + `NAV-EXP-010` | `DEFERRED` / 依赖门，不建卡 | 前者等主控对[HOST §5](host-admission-session-coordinate-design.md#5-分歧矩阵所有权问题为什么不由本卡回答)三个 ownership 单元格表态（`HOST-OWNERSHIP-FREEZE-001`）；后者契约原文写明「只在 core tested 后运行」，而 `p0-core` 今天不可晋级。把它记成「产品未实现」是替主控做决策。 |
| 契约 crash/outbox 那行的滞后 | 记录，不建卡（不发明 docs-only 卡） | 那行说 `CORE-060` 的 runtime 强杀窗「按当前 run 形状打不中」，磁盘上是 9 个 bundle、seq4 `ed2bbad7…` 当前构建 PASS（来源：历史 `:5936-5941` 的 1.21.4 换代重封）。随下一次触碰该契约表的卡顺手改，本卡原文照引不改。 |
| `INT-EVIDENCE-INTEGRITY-001` | **`DONE`（M 主控，2026-09-26，合入 `main` = `759125f`）**，见 §2 同名小节 | 七项分类里的 ①：读者对「台账 `SEALED` 行 ⇒ 卷上无 bundle」必须具名。允许路径只有 `tools/report_promotion.py` 与其单测；不改 registry/`status/gaps`/判据，不重封历史 bundle，规范卷 `:ro`。红→绿读数、真卷对照与切片非 vacuity 都在 §2 那一节。**不声称**丢失已被阻止——它已被说出；是否升级为门禁条件是 `P0-GATE-PROMOTION-001`（主控）。 |
| `H1a` `TEST-ORCHESTRATOR-PINNED-PYTEST-001` | **`DONE`（M 主控合入 `main` = `ee0a439`，2026-09-26；H 提交 `44922b8`，base `f632665`）** | 七项分类里的 ②。交付面只有两处：`test-orchestrator/runner/Dockerfile`（+24，装锁文件钉住的 `pytest 9.1.1` 与非-Windows 依赖闭包）与 `tests/contract/test_runner_scripts.py`（+65，把每个 pip 参数钉成 `name==version` 且必须等于 `uv.lock`）。M 在合并树上独立复量：`import pytest` 在 `minekin-runner-before:local` ⇒ `ModuleNotFoundError`，新镜像 ⇒ `9.1.1`/Python 3.12.3，`pip freeze` 恰是六个钉住包；镜像内 `run_repo_case.py --case tests/fixtures/cases/offline-001.json` 由 `rc=1` + 五条 `No module named pytest` 变 `rc=0` + 五条 `held`。**防漂移测试非空转**：工作树里把 pin 改成浮动 ⇒ 具名「not an exact `name==version` pin」，改成 `9.0.0` ⇒ 具名「image pins … but uv.lock resolves …」，两次都在 `git checkout` 回滚后复跑绿（未提交）。已封四条 repo bundle 的 `environment` 段仍按封存进程解释（②-b），重封走 `E-CO`。**镜像重建对全体 lane 可见**（tag `minekin-runner:local`，image id `b67a4d917306`，修前参照 tag 保留），旧/新镜像跑同一条只读读数脚本的日志差为空是 H 的材料、M 未重复量。 |
| `H1b` `RUNNER-NAMED-FAILURE-001` | **`DONE`（M 主控合入 `main` = `d09e9b2`，2026-09-26；H 提交 `1dc6101`，base `f632665`；只闭合缺陷 A）** | 七项分类里的 ③。`test-orchestrator/runner/domain.sh` +25/−2：加入者准备同时建 `run/session`，基线读取双向具名（缺目录 ⇒ 打出 Kin 与路径的一行并按空基线继续；目录在而列不出 ⇒ 具名 + `exit 2`，且不再吞掉 `ls` 的诊断）。M 在受控镜像里用 `awk` 从真实脚本抽出该区段、在 `set -euo pipefail` 的新 `bash` 进程中重放（写只落 lane 卷 `minekin-h1b-20260926` 与容器 `/tmp`）：修前两处 `rc=2` 且 **stderr 0 字节**，修后同一反例 `rc=0` + 134 字节具名读数、走真实 prep `rc=0` + 无 stderr，正对照 `before=[1111…] rc=0`。第四刀被 `rc=2` 掐死的那次 CORE-030 尝试与材料原样保留；**它现在具备重跑条件，但重跑属 E 的规范卷轮次**（不与 `E-CO` 抢卷）。缺陷 ④（runner 未 `import sys`）在同一轮里更正为**仓库代码未复现**，读数见 §2 分类表 ④ 行；H1b 不含第二个提交，卡片不再挂“待补的第二缺陷”。 |
| `E-CO` 镜像内自检重封一轮 | **`NEXT`（E lane 的 `lane_next` 附加卡，2026-09-26 已派工到 `../minekin-wt-evidence`：仅在分支、尚未验证）**，前置 `H1a` 已满足。**M 的只读快照（同日 15:45–15:52 UTC，E 尚未 push、记录未合入）**：卷上已出现这四条的新 attempt，卡面口径**已量到改进，而且改进不在 `environment` 段**——seq 1 的 `check-verdict.json` 里 argv0 是宿主解释器 `…\minekin-wt-evidence\.venv\Scripts\python.exe`，seq 2（`46f88ff6/e9ee19ab/8af1ad70/8ffed6f1`，各 `sequence 2` 顶掉 `935c034a/f4203033/4f324c20/66c51fc7`）的 argv0 是 `/opt/minekin/bin/python3`，日志里的 pytest 来自 `/opt/minekin/lib/python3.12/site-packages/_pytest/`，且 `/src` 全程只读（pytest 写缓存被拒的 `PytestCacheWarning: Read-only file system` 留在日志里 ⇒ 非恒真对照）。M 独立复核：四条 `evidence verify` 各自 `verify_rc=0`、`sealed true / verified true / violations []`、工件 9/7/7/10；`rejudge` 两条抽样都报既有的 `unreadable`（该通道无 `asserter-inputs.json`，第二读法仍是重跑检查）。卷底色 `attempts 65→69 / bundles 101→105 / from_another_build 61→61 / unsealed 0 / unverified 0 / sealed_without_bundle []`；**门载荷 sha256 仍是 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`，11 门 `promotable` 分布一字未变**（`W00/W10/W20/W60 true`，其余 `false`，overall `false`）。两条 `environment` 段的键与取值（`renderer_display: unmeasured`）新旧逐字相同 ⇒ 该字段本身没有变好，工具链的可证性落在被封存的 argv 与日志路径上；E 的记录若声称 `environment` 段本身改了口径，与卷上字节不符。**四读齐全与反证/正对照仍以 E push 后的记录为准，本快照不构成收卡**。 | ②落地后由 E 在规范卷上做一次的受控验证：在同一镜像里跑「判官只需仓库字节」那一族（`OFFLINE-001/040/050` + `ADMIT-080`），使 `environment` 段与真正执行检查的环境一致。台账走 `sequence +1` 的新 attempt，**不覆盖既成四条、不改判据、不翻 registry**；四读 + `environment` 段新旧对比 + 一条反证 + 一条正对照都要交。若新旧 `environment` 段实际相同，如实报「本卡没有产生口径改进」。**这是新证据卡，不是把已封四条改口径**；是否点亮哪一门的 `mandatory` 仍属 `P0-GATE-PROMOTION-001`。 |


## 4. 完整 Minekin 长程任务簿（设计先行、证据后置）

以下是持续执行所需的完整方向、顺序与交付门。细到尚未冻结的 case ID/阈值/接口不预编；到其前置门时从专项契约冻结，**一张大项可按真实依赖拆成多张小卡，但主干不能同时有两个 NEXT**；§2 lane_next 激活表内的并行 lane 卡不占用主干 `NEXT` 名额，其规则以[并行作业协议](parallel-execution-plan.md)为准。不依赖重大决策且已冻结的受控本地修复/证据卡可插入 A2/A3 之后、A4 之前；记录原因，不开无限审计格。

### B. P0 证据与运行基础（A 阶段可并行规划，不越过主干 integration `NEXT`；lane 卡见 §2 激活表）

| ID | 状态 / 依赖 | 完成定义 |
| --- | --- | --- |
| `P0-EVIDENCE-INVENTORY-001` | **`DONE`（2026-09-26，见 §2 与[盘点记录](p0-evidence-inventory-2026-09-26.md)）**，依赖 A3（已满足） | 已量出：四桶 `31/28/0/15`、28 条按成因与判据形状两刀切分、11 门 block 与三种 block 的语义、产品未实现只在缺 fixture 侧点名 6 条整条 + 2 个半句、四条反证各自移一个机制、一处契约行与一处旧清单口径的滞后登记。交出 §3.3 的排卡。 |
| `P0-CONTROLLED-CAMPAIGN-001` | **E lane 的 `NEXT`（2026-09-26 自 B1 机械提升；lane 化后归 E 在独立分支施工，M 只合并）**，其「inventory 后」前置已满足；**第一刀 B1-a、第二刀（`OFFLINE-030`）、第三刀（5 条 ADMIT 行）、第四刀（`CORE-030`，LAN）与第五刀（4 条仓库自检行）同日完成，卡片仍在进行中** | 按 W00→W70/`p0-core` 契约，在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle，包括 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak；每个 case 的独立 oracle、非空转反证、版本摘要齐全，再谈 promotion。既有 `REAL-P0-CAMPAIGN-001` 历史阻断保留，不当成 DONE。B1 给它的最小内容：先补 §3.3 的 B1-a（`CORE-040`、`CORE-050` 两条 mandatory，只差运行）——**已交，见 [第一刀记录](p0-core-040-050-run-2026-09-26.md)**：两条各一份当前 build 的 `PASS + verified + case_version 对得上 + 独立复判 AGREES` bundle，W60 读数转为 `promotable: true / blocks []`（仍只是候选，不晋级），反证 P/R1/R2/R3 证明这个视图既能判红也能拒篡改。再按判据形状排 `OFFLINE-030` 与那 5 条只有别的构建 bundle 的 ADMIT 行（`ADMIT-001/040/060/100/110`）——`OFFLINE-030` **同日已交，见 [第二刀记录](p0-offline-030-run-2026-09-26.md)**（一份当前 build 的 `PASS + verified + crit_match + 复判 AGREES 1/1`，八行材料层判否对照；但该行 `mandatory: false`，撤掉它门一字不变）；那 5 条 ADMIT 行也全在 `non_mandatory` 名单里，**跑完它们不会动任何一门**，所以本卡剩下的门阻因（`REQUIRED_CASE_NOT_REGISTERED` / `NO_MANDATORY_CASES`）属 case 设计与 `P0-GATE-PROMOTION-001`（主控）。deferred 的 `HOST-030/040` 不计入本卡。**——那 5 条 ADMIT 行同日也已交，见[第三刀记录](p0-admit-five-run-2026-09-26.md)**：五轮受控本地真跑各封一份当前构建 PASS bundle（复判 `2/2、6/6、6/6、3/3、3/3`、`disagreements=[]`，旋钮生效由 bundle 内 `server.properties` / run document 的字节证明），规范卷底色 `attempts 54→59 / bundles 90→95` 而 `from_another_build` 仍是 61（B1 那格「本根只有别的构建的证据」从 5 变 0）；四读与 P/R1/R2/R3 齐全，其中 R1 撤掉这五份之后 W40/`p0-core`/W60/overall 四行与正对照逐字相同 —— 上面那句「跑完它们不会动任何一门」现在是量出来的而不是预期。**`CORE-030` 也在同日以第四刀交出，见 [第四刀记录](p0-core030-lan-run-2026-09-26.md)**：本卡第一条 **LAN** 形状的当前构建真跑（宿主客户端 publish `kinworld` 到 `25570`、加入者 `Kin2` 拨号并承认第一个快照），判据 `2/2`、复判 `AGREES`，第二半判据读的是宿主 run document 的字节且其 `settings_digest` 逐字节等于 case 钉住的 `level.dat`；底色 `attempts 59→61 / bundles 95→97`、`from_another_build` 仍是 61，B1 §6 那格由 3 变 2（只剩 deferred `HOST-030/040`）⇒ **B1 §7 定义的 9 条最小内容就此全部有当前构建 sealed bundle**。反证 P/R1/R2/R3/R4/R5 齐全（R3/R4 另量到一个机制：判据摘要移了 ⇒ 读者对 PASS 与 FAIL 都不给判决，所以具名否只能从未移判据读）。这刀经三次尝试：第一次撞 `domain.sh:657` 的确定性缺陷（新 joiner Kin 无 `run/session/` ⇒ 静默 `rc=2`，操作员建目录绕过，未 patch 已提交代码），第二次加入者崩在 `GLFW [0x1000E]Failed to detect any supported platform` 并封成 FAIL（crash report 在 bundle 里、`evidence verify rc=0`），第三次一字未改重跑即 PASS ⇒ 该 crash 记为**当前构建上不可重现**，不写根因；两条 runner 侧缺陷交主控决定是否开卡。**第五刀同样在同日交出，见[第五刀记录](p0-repo-four-case-run-2026-09-26.md)**：这一刀不是 Minecraft 真跑而是**仓库自检通道**（`run_repo_case.py` 在宿主 `.venv` 跑判据、`seal_repo_case.py` 在受控镜像里对规范卷封存），把 B1 §6 三格的第三格「判官只需仓库字节但本根零 bundle」清掉非 HOST 的 4 条（`OFFLINE-001/040/050` + `ADMIT-080`，17 → **13**），四条各一份当前构建 PASS bundle、attempt seq 1、`evidence verify rc=0`、`report_promotion` 每行 `build=True verified=True sealed=True violations= []`；底色 `attempts 61→65 / bundles 97→101`、`from_another_build` 仍是 61。该通道的复判口径是 `UNJUDGED`（bundle 不记 asserter 输入），因此第二次读法为**重跑检查**（四条各有全新 run id 的独立重跑并同意），本卡不声称 `re_judged = AGREES`。七件反证 P/R-A/R-B/R-C/R-D/R-E/R-F 齐全：一位字节的两种工件都给 `rc=12` + `ARTIFACT_DIGEST_MISMATCH` 且还原即回 `rc=0`，R-D 改产品一字节使四案各自的判据转红并如实封成卷外 FAIL（失败材料留着），R-E 删 bundle 目录 ⇒ `bundles 9→5` 而 `attempts` 仍 65。**最强的那句是量出来的**：`report_promotion.py` 的 `work_packages`+`overall` 整段 sha256 在封证前后都是 `fb0152c85d029ee0…`，四条都是 `mandatory: false` ⇒ 门一寸未动。剩下的 13 条**全部**属 `HOST*` 家族（ownership 未冻结，见 §5），E 在门前停住；这一刀另外量出两格交主控的事实：受控镜像内**没有 pytest**（硬跑会得到四条 `No module named pytest` 的假 FAIL，本轮未 pip install、未改镜像），以及「台账有 `SEALED` 行而 bundle 目录已不存在」被读者静默忽略（`unsealed 0 / unreadable 0`）。 |
| `PARALLEL-INTEGRATION-GATE-001` | **主干 `NEXT`（M，2026-09-26 随 lane_next 激活常驻）** | 主控 integration gate：按协议 §5 与 M1，逐卡双审 S/E/H/D/V 分支（允许路径、契约、测试、当前 build 真实证据），按依赖顺序每次只合一张卡入 `main`，合后核远端 SHA 并向各 lane 发新 base；分支未合并不得写成主干 `DONE`。本卡随激活持续有效，不是 docs-only 轮次卡。已合：S1 → 主干 `b88e36f`；V1 → 主干 `eb6f63d`；D1 → 主干 `8aab153`（均 2026-09-26，双审+相应门禁后）。同轮再合：E 的证据分支整条（第五刀及其前）→ `f632665`，M 自己的 `INT-EVIDENCE-INTEGRITY-001` → `759125f`。 |
| `P0-PLATFORM-MATRIX-001` | `QUEUED_CONDITIONAL`，基础证据后 | Java 17/21 与目标 OS/arch 分别做真实 runner/安装验证；Windows 缺口不凭 Linux PASS 删除。CI 仅作为辅助，优先本地/Docker。 |
| `P0-GATE-PROMOTION-001` | `BLOCKED_EVIDENCE`，上述证据后 | 独立审计 W00…W70、`p0-core` 当前门禁；`promotable` 只是机器候选，还要规格/工程审查、准确登记、commit/push。不可用单一 W 门的绿替代整体。 |

### C. HOST：Kin 自建世界与第二真实客户端（先冻结产品所有权）

| ID | 状态 / 依赖 | 完成定义 |
| --- | --- | --- |
| `HOST-OWNERSHIP-FREEZE-001` | `BLOCKED_DECISION` | 用户/主控依据[HOST §5](host-admission-session-coordinate-design.md#5-分歧矩阵所有权问题为什么不由本卡回答)逐项决定 generation 分配者、WorldCapsule 权威及落盘、无 server profile 时 Rule 2 的一致性判法；写 ADR 与迁移/失败语义。当前设计没有代答。 |
| `HOST-WORLD-LIFECYCLE-001` | `DEFERRED`，冻结后 | 精确按[HOST 存储契约](hosted-world-storage-lifecycle-contract.md)创建/恢复 save、manifest/锁/lease、拒绝越界与冲突；真 JVM 的首 JOIN、保存、关闭和冷启动证据，不触碰用户 `.minecraft`。 |
| `HOST-ADMISSION-TRACE-001` | `DEFERRED`，前项后 | 冻结 `HOST-001` case：同一 generation 的第一真实 client、Bridge、WorldCapsule、integrated server 轨迹；第二真实 client 通过 LAN 加入，规则 R1–R7 各有负例，重启重进能复判身份。无第二客户端不判 PASS。 |
| `HOST-COMMIT-RECOVERY-001` | `DEFERRED`，前项后 | 按[HOST 提交契约](hosted-world-commit-recovery-contract.md)保存/flush/stop/session/Mind 各边界强杀与重启，回滚 epoch、复制分叉新世界身份、host→remote→host 不串世界；独立 server truth 不进 Kin belief。 |
| `HOST-W80-PROMOTION-001` | `DEFERRED`，所有 host mandatory case 后 | 真封证、四读、故障矩阵和 gate 审核；W80+ 不能因设计文档或 host 命令存在而提级。 |

### D. PERSIST 与运维边界

| ID | 状态 / 依赖 | 完成定义 |
| --- | --- | --- |
| `PERSIST-CASE-FREEZE-001` | `BLOCKED_DECISION` | 从持久身份/世界/会话契约冻结 case ID、权威数据和生命周期；旧 inventory 的 `UNFROZEN_CASE_IDS` 不可由报告器凭空补号。 |
| `PERSIST-IDENTITY-TRANSACTION-001` | `DEFERRED`，冻结后 | 同一 kin_id/persona/关系/承诺/技能的持久主键与事务；重启、死亡、跨服、跨世界、模型上下文清空后连续；损坏/双实例/迁移失败明确拒绝而不造新人格。 |
| `PERSIST-MEMORY-RETRIEVAL-001` | `DEFERRED`，前项后 | 确定性装载身份/承诺，来源化召回事件与人物/地点；过期、反证、未知可表达，数据不串 Kin；本地检索基线先于可选 embedding。 |
| `PROCESS-RECOVERY-001` | `BLOCKED_DECISION` | 先定残留进程自动处置权限与接管边界；未获选择只检测/报告，不强杀未知进程。然后做进程矩阵与旧 lease/GUI/实体不重放。 |
| `OPERATIONS-RETENTION-001` | `BLOCKED_DECISION` | 先定 marker/roll/证据保留期限、备份与精确删除策略；未获选择不得批量清理用户数据。 |

### E. 产品能力：从“能进服”到真正自主 Minekin

阶段定义遵守[路线图](roadmap.md)和相关人格、记忆、指令边界契约。每阶段必须有真实客户端动作、反例与可复现验收；只写服务层逻辑不算完成。

| 阶段 / 任务簇 | 前置与交付门 |
| --- | --- |
| `S0-HARNESS-UX` | A6、必要 P0/HOST/PERSIST 基础后：独立启动入口、Server Profile/preflight、单 Kin 生命周期、最小 Dashboard/Live View/急停；浏览器不绕过 lease，媒体故障不夺控制权。先限定本地/许可目标，不因 UI 便利扩公网。 |
| `S1-PERCEPTION-NAV` | 玩家等价观察、受控导航、避障、短/长目标坐标与失败退出；墙后实体/埋矿/seed 不泄漏，额外路径模组独立评级。当前世界变化须重观测。 |
| `S1-SURVIVAL-ACTIONS` | 树木/工具/采集/背包/合成/食物/夜间安全、受伤/死亡/拾物。每种动作按“授权输入→客户端观测→必要的独立 server truth”分层验收；不凭空发物品或假设配方。 |
| `S1-SKILL-RECOVERY` | 复合技能可调用且可修订；失败、模型中断、断线、重启不重复危险动作，已有工具跳步；受控多场景 survival demo。 |
| `S2-GOAL-MODEL` | 需求、目标前提、世界书版本来源、目标暂停/放弃/改线；长期方向不越过真实身体能力。 |
| `S2-PERSONA-MEMORY` | 可自定义/可复现随机人格、身份与同一人物连续、来源化记忆与冲突修订、知识/经验分离；多日会话与冷重启证据。 |
| `S2-AUTONOMY-SOAK` | 独立/陪玩模式切换、邀请与离线退出、跨日目标/承诺/失败恢复；预算、延迟、token、数据完整性和安全长期 soak。 |
| `S3-SOCIAL-RELATIONS` | 玩家身份识别、关系/情绪/承诺/拒绝、损失误判与修正、不同 Persona 的持续行为；不强制听命、和解或报复。聊天/网页/书牌/记忆注入不得提权、外传或污染永久身份。 |
| `S4-SINGLE-KIN-DEMO` | 将 S0–S3 组合成单 Kin 多日可复现演示：起步生存、目标调整、社交互动、重启/死亡/跨服恢复及真实后果；未实现维度/战斗/建筑不能靠脚本充数。完整发布清单含安全、许可证、性能、备份恢复、未测矩阵。 |
| `S5-EXPANSIONS` | 在 S4 通过后单独排多 Kin 协作、跨维度/末影龙、深建筑/PvP/模组等；每项有新授权和独立能力评级，不能宣称为首版必备。 |

每个任务簇进入执行前写卡：目标/依赖、允许/禁止路径、可观察验收、负例、证据级别、停止条件、回滚。任何契约冲突或重大产品选择仍停下请用户拍板；此长程簿保证“不知道下一阶段是什么”不再成为理由，但**不伪装未来细节已冻结**。

## 5. 明确的决策与禁止推断

- V08 远程目标：用户曾提供测试服且声明 offline 1.20.1，但又明确选择“V08 暂不提升”。要新的本次探测/入服许可；A1–A3 绝不连接该服。V09 的控制必须另行明确动作边界。
- HOST §5 三格没有答案，不能由“先做设计”推导实现选项。PERSIST case 编号、运维删除、残留进程接管也未获产品决定。
- B1 另交出两类等产品决定的缺 case：§3.3 的六个产品事实载体问题（账本 profile/endpoint、人格未重建、oracle/canary 来源、OFF-D/OFF-N 候选、`identity_revision` 变更事件、封禁分类）与 `ADMIT-030/050` 的 case id 拆分。执行侧不自造断言、不改候选集、不翻 registry 求绿。
- 当前不会开启在线认证、扩大任意公网访问、让远程内容改变信任策略、把测试服务端真值送给 Kin，或以 CI 替代本地真跑。
- 一旦走到 A4/上述决策门且没有独立已授权安全卡，保持 `BLOCKED_DECISION` 并交付清楚的选项；不得为了维持活动量反复改 `.tmp`、盘点或文档。
