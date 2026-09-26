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

当前唯一 `NEXT` 是 **A3 `V1201-TESTED-GATE-READOUT-001`**（规范数据根与当前构建的 registry/provenance/case inventory/四读只读报告；不改 tested 声称、不补造断言）。**禁止连接用户远程服；V08 仍未提升**，A4 是新的授权门，A3 收卡后若 V08 无新授权则转 B 段首张安全卡，不把 A4 设成 `NEXT`。A1 留下的 `V1201-DEMO-CASE-FREEZE-001` 与 A2 留下的 `V1201-DISK-PREFLIGHT-001`、`V1201-SRV-RESOLVER-001` 都是 `BLOCKED_DECISION`，留在主控手里，执行侧不自造断言、不改 case/registry 求绿；A2 另交两张已排队实现卡 `V1201-AUTO-ENTRY-GATE-ORDER-001`、`V1201-MAX-BYTES-VALIDATION-001`，与已登记的 `V1201-AUTO-PATH-RUNNER-001` 一样不在 A3 之前插队。本地真跑再受 runner 缺陷阻断时，保留原始材料并按需另登修复卡。
