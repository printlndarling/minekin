# Qoder / 新会话连续执行交接

更新：2026-09-26。旧 875 行交接（包括 Qoder 未提交的第七类审计草稿）完整保存在[历史交接](qoder-execution-handoff-history-through-cef712b.md)；其中旧 `NEXT`、旧 run 读数、旧“队列为空”不再指挥执行。现行唯一队列是[执行计划](development-execution-plan.md)。

## 每次启动与上下文丢失后的恢复步骤

1. 在 `C:\Users\darling\Documents\agent_work\minekin` 运行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、`git log -8 --oneline`、`git ls-remote origin refs/heads/main refs/heads/codex/core-state-transition`。记录 HEAD/两 ref/dirty 文件，勿 reset/stash/覆盖他人改动；远端与本地分叉先停下协商。
2. 读[执行计划](development-execution-plan.md) 的 `current_next` 和该卡、[短 TODO](development-todo.md)、[1.20.1 路线](version-auto-to-server-control-plan.md)、该卡专项契约。以当前树/当前规范数据根的机器读数确认卡的前置，不以历史 `DONE` 文本或 `.tmp` 产物代替。
3. 逐卡只改 `allowed_paths`，先本地/Docker 验证和真实 sealed evidence，再规格/工程双审查、commit、立即 push 工作分支与 `main`、核远端 SHA；下一卡只能在上一卡五项齐全后提升。CI 额度不足时不等 CI 代替本地；CI 红时如实记录，不声称绿。
4. 遇用户产品选择、远程服新授权、HOST/PERSIST、在线认证、数据删除/进程接管或判据冲突，停在 `BLOCKED_DECISION`；允许推进文档已经明确排好的独立安全卡，但不可新造“再审计一次”卡填空。

## 目前交棒点

`cef712b` 时 Qoder 已停止且留下三份未提交旧文档草稿。本次整理已把草稿连同所有历史内容保存为同级 `*-history-through-cef712b.md`，新现行文件从零建队列。

A1 `V1201-LOCAL-DEMO-REHEARSAL-001` 已于 2026-09-26 收卡：在全新 data root 与全新 Kin 上，一次自动路径 `session start` 同 run 完成装机（`installed 3639 / reused 0`）、JOIN、`PlayableEstablished`、限幅 look+move、租约到期释放与 `session stop` 退出，按现行 case `V1201-040` 封存为 PASS，四读一致（`verified PASS` / `re_judged AGREES` / replay 23 事件 / 当前 build），七类单项删除各自把对应断言判红；两次失败 attempt（服务端无读数的 sealed FAIL、供应链中断的 partial store）都原样保留。原始读数、复现命令和三格缺口在[执行计划 §2、§3.1](development-execution-plan.md#2-上一卡交付与当前-next-边界)。

A2 `V1201-LOCAL-NEGATIVE-MATRIX-001` 已于 2026-09-26 收卡：六族负向全部量出当前 build 的真实读数——18 行真 socket 状态探测（正对照 `control_1201` `OBSERVED`，其余按名归类，`FAIL=0`）、自动入口对伪造显示文本与多版本代理各 `NEEDS_PIN` 且 store 0 文件、profile 装载期禁区地址四拒（连接计数证明拒在发出字节之前）、显式路径五条准入拒 + Bridge 钉错两拒（同一 store 下未变 recipe `launchable: true`）、`V1201-060/070/080` 本 build 重读 `PASS / agrees`。新量到的产品缺口是自动入口的门序：`--auto-bundle` 下装机先于 join 授权与版本 allowlist（X1 秒拒 vs X2 下 388 文件、Y2 等 3639 全过才拒、`java=0`）。逐行读数、配对反证与四格缺口登记见[负向矩阵复判记录](version-negative-matrix-2026-09-26.md) 与[执行计划 §2、§3.2](development-execution-plan.md#2-上一卡交付与当前-next-边界)。

A3 `V1201-TESTED-GATE-READOUT-001` 已于 2026-09-26 收卡：规范卷只读复判量出 provenance `verified / rc=0`（`tested` 摘要已被真算真比，不再是文本）、六条 1.20.1 引用四读一致且 `from_repository_build: true`、条目 19 能力与六 case 断言双向差集为空、`report_promotion` 三门仍 `false`（W60 `CASE_VERSION_MISMATCH`、W70 `NO_MANDATORY_CASES`、`p0-core` 两者皆有），并列出卷内 15 次 attempt 的引用/旧 build/sealed FAIL 分布；四条反转证明读者能判红。逐条读数与边界见[tested 门禁复判记录](tested-gate-readout-2026-09-26.md)。

B1 `P0-EVIDENCE-INVENTORY-001` 已于 2026-09-26 收卡：规范卷只读四桶盘点把契约要求的 74 条 case 逐条标注为 `missing_fixture 31 / no_current_build_evidence 28 / real_failure_on_current_build 0 / current_build_pass 15`（每条恰落一桶），28 条按成因（`no_bundle_on_this_root 18`、`only_another_build 10`）与判据形状（要运行材料且本根零 bundle 1 条、只有别的构建的 bundle 10 条、只需仓库字节但零 bundle 17 条）各切一刀；11 门的 block 分成三种语义（缺定义 / 缺当前构建真跑 / 缺主控的门禁决定），收卡时 W60 与 `p0-core` 只阻在 `CORE-040`、`CORE-050` 的 `CASE_VERSION_MISMATCH`（该读数已由 B2 第一刀改变，见下一段；原读数在记录里按 `37f8deb` baseline 保留）。「产品未实现」在已注册 case 上为空，在缺 fixture 侧点名 6 条整条 + 2 个半句，HOST 18 条不判。四条反证各移一个机制（删 fixture、空数据根、把通过行改成 `FAIL`、改一位 case 摘要），后两条会同时触发视图与晋级规则的对账护栏。盘点一张门都不点亮。逐条读数见[P0 证据盘点](p0-evidence-inventory-2026-09-26.md)，两张建议卡与两类产品事实决定登记在[执行计划 §3.3](development-execution-plan.md#33-b1-交出的缺-case-排卡按-12-单独登记不由-b1-顺手写断言也不自占队列)。

B2 的第一刀 `P0-CORE-040-050-RUN-001` 已于 2026-09-26 完成（**B2 本身仍是唯一 `NEXT`，不收卡**）：在规范卷 `kin-01` 上补了三轮受控本地 dedicated offline 真跑（jar 实测与 `SERVER_RECIPES["1.21.4"]` 的 pin 相同），`CORE-040`、`CORE-050` 各留一份当前构建的 PASS bundle，`case_version` 逐字节等于今天的摘要、`from_repository_build: true`，四读齐全（封证 verdict、`evidence verify`、`report_promotion` row、独立复判 `observed=6/6` 与 `4/4`、`disagreements=[]`）；W60 因此从 `CASE_VERSION_MISMATCH` 转为 `promotable: true / blocks []`，`p0-core` 只剩 `REQUIRED_CASE_NOT_REGISTERED`。反证四组：撤掉任一判绿 run 该门立刻回红，只改一位封进去的字节则 `EVIDENCE_NOT_VERIFIED` + `rc=12` + 复判 `unjudged`、而规范卷同一 run 仍 `verified`。`CORE-050` 第 1 次 attempt 真实 **FAIL**（本次命令漏 `MINEKIN_DOMAIN_STILL=1`，`--hold-at join` 下 harness 不代跑静默等待 ⇒ `NO_SERVER_READINGS`），判据未改、材料保留。逐条读数、复现命令与「本卡不声称」见[CORE-040 / CORE-050 当前构建真跑封证](p0-core-040-050-run-2026-09-26.md)。

当前唯一 `NEXT` 是 **B2 `P0-CONTROLLED-CAMPAIGN-001`**（§4 B 段第二张，B1 已满足其「inventory 后」前置；在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle。**第一刀 `CORE-040`/`CORE-050` 已交，剩余是 `OFFLINE-030`、5 条 `only_another_build` 的 `ADMIT-001/040/060/100/110`，以及卡面后半段 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak**）。**禁止连接用户远程服；V08 仍未提升**，A4 是新的授权门，B 段推进不等于入服许可。W60 的 `promotable: true` 只是机器候选，**晋级属 `P0-GATE-PROMOTION-001`（主控）**；执行侧不翻 `status/gaps`、不改 case/registry 求绿。A1 留下的 `V1201-DEMO-CASE-FREEZE-001`、A2 留下的 `V1201-DISK-PREFLIGHT-001`/`V1201-SRV-RESOLVER-001`，与 B1 留下的六个产品事实载体问题、`ADMIT-030/050` 的 case id 拆分都是 `BLOCKED_DECISION`，留在主控手里；B1 交出的 `P0-OFFLINE-090-100-EVIDENCE-CHECK-001` 是 `QUEUED_PROPOSED`，排期是主控动作。本地真跑再受 runner 缺陷阻断时，保留原始材料并按需另登修复卡。
