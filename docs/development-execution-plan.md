# Minekin 开发执行计划（现行唯一队列）

更新：2026-09-26。产品主线是 **1.20.1**；1.21.4 仅作必要回归基线。本文是唯一任务状态入口；[完整产品范围](roadmap.md)、[跨版本契约](version-auto-to-server-control-plan.md) 和各专项契约决定“做对什么”，本文决定“现在做什么”。截至 `cef712b` 的六千余行旧计划及 Qoder 尚未提交的第七类审计草稿完整保存在[历史计划](development-execution-history-through-cef712b.md)，不是当前队列。

## 0. 状态与证据口径

`current_next: P0-EVIDENCE-INVENTORY-001`；全库同时只允许这一张 `NEXT`。A3 `V1201-TESTED-GATE-READOUT-001` 已于 2026-09-26 以规范卷只读机器读数收卡（见 §2 与[复判记录](tested-gate-readout-2026-09-26.md)）；A1/A2 同日收卡。A1 `V1201-LOCAL-DEMO-REHEARSAL-001`（真跑 sealed PASS）、A2 `V1201-LOCAL-NEGATIVE-MATRIX-001`（机器读数与配对反证）（[负向矩阵复判记录](version-negative-matrix-2026-09-26.md)）按 §3 的机械流转已依次完成。B 段首张是只读证据盘点，不是 V08 晋级，也不是连接用户服务器的许可。`cef712b` 时旧队列 `NEXT=0/QUEUED=0`；本计划是用户 2026-09-26 要求“一次性编写后续任务”的新排期，不把旧卡改称未完成。

已核实的基线：V01–V07 及空 store 自动安装真跑已完成；A1 已在受控本地把自动装机与同 run 的 PLAYABLE→look/move→释放→退出接成一次 sealed PASS（§2）；1.20.1 `V1201-080` 的正常停止显式松键有 sealed PASS，registry 对应缺口已划出；`HOST-ADMISSION-DESIGN-001` 只交付了[设计和三个未决所有权问题](host-admission-session-coordinate-design.md#5-分歧矩阵所有权问题为什么不由本卡回答)。这些都**不等于** V08、V09、V10 或完整 Minekin 完成。1.20.1 registry 其余缺口按现行文件和 `verify_tested_provenance.py` 重新读取，不以本文计数代替机器结果（A3 已按此重读：provenance `verified: true / rc=0`，边界见 §2 与[复判记录](tested-gate-readout-2026-09-26.md)）。旧 W00/W10/W20 的 `promotable` 读数不等于总体 `p0-core tested`；`p0-core`/七场景 campaign 仍有真实证据缺口。CI、ping、旧 bundle、单测、文档自述均不能证明真实入服。

状态语义：`NEXT` 可立即领取；`QUEUED` 必须依赖满足后才顺序提升；`BLOCKED_DECISION` 要用户明确拍板；`BLOCKED_EVIDENCE` 要真实材料；`DEFERRED` 不可开工。以下顺序是**长程任务账本**，不是对未冻结功能/案例的授权。只有本文出现一个 `NEXT`，完成一张后才原子更新队列。不会因为没有可执行卡而创建“再盘点一次”的 docs-only 任务。

## 1. 连续执行协议

1. 每次冷启动按[交接](qoder-execution-handoff.md)检查工作树、HEAD、工作分支、远端 `main` SHA；未提交改动归原作者，不 reset、stash、覆盖。读本文唯一 `NEXT`、对应专项契约和现行机器清单，写下 baseline SHA、允许路径、停止条件。
2. 只做 `NEXT`。需要产品选择、真实外部授权、修改卡外判据/registry、删除数据、接管进程时停止该分支，登记证据和 `BLOCKED_*`；继续已有的独立安全卡，不自行猜结论。测试失败先诊断是否本卡范围内的缺陷；范围外登记单独修复卡，由主控排期。
3. 一卡一可逆提交。先验路径范围和两轴审查（契约/工程），再跑与改动相称的本地门禁；运行时结论必须来自当前 build 的 Docker/受控真跑和 sealed bundle。`verify`、`rejudge`、适用 `replay`、`report_promotion` 四读、负向反证和 provenance 分开记录。失败工件不覆盖，敏感目标不入库。
4. 卡通过后更新本文及[当前 TODO](development-todo.md)，commit，立即 push 工作分支与 `main`（仅在当前共享仓库两 ref 同步且无并发冲突时），核本地 HEAD、`origin/main` 和远端 SHA 一致，才改卡为 `DONE` 并提升下一张。push 失败不领取下一张。Qoder 可以在这些条件全部满足时机械流转已明确排队的卡；`BLOCKED_DECISION`、HOST/W80+、PERSIST、在线认证、扩大公网访问不在委托内。
5. 基础门禁：`uv run --frozen pytest -q`，Ruff check/format，Pyright，`check_boundaries.py`、`check_case_assertions.py`、`verify_fixture_digests.py`、`check_workflow_pins.py`、`git diff --check`。Bridge/proto 加四项 Bridge 检查和 Java 21 `./gradlew check --rerun-tasks`（不可用 UP-TO-DATE 或 FROM-CACHE 替代）。Docker/真实客户端卡须跑其专项真实门禁。提交正文记 `Constraint`、`Rejected`、`Confidence`、`Scope-risk`、`Not-tested`。

## 2. 上一卡交付与当前 NEXT 边界

当前唯一 `NEXT` 是 **B1 `P0-EVIDENCE-INVENTORY-001`**（§4 B 段首张，依赖 A3 已满足；判据在其行内冻结，不新造卡）。A3 收卡后按 §3 的机械排期转 B 段：V08 未获新授权，A4 不设 `NEXT`。以下是刚收掉的 A3、A2 与 A1。

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

A2/A3 是本次新增的**本地安全顺序卡**，允许 A1 完成后机械提升；A4 不能因前三卡通过自动提升。A5 的新动作授权也不能从 A4 的只读/无动作入服授权推导。**机械排期**：A3 收卡后若 V08 尚未获得新授权，不把 A4 设成 `NEXT`；转取 B 段首张安全卡（A3 已于 2026-09-26 收卡，该分支已照此执行：`current_next` 现为 `P0-EVIDENCE-INVENTORY-001`）。B 段某卡受真实证据阻断时可转取其后不依赖它的已冻结安全卡（如平台验证），记录跳过原因；若剩余只涉及决策/未冻结契约，则保持 `current_next: none / BLOCKED_DECISION` 并一次性列出所需选择，不发明 docs-only 卡。V08 获新授权后主控重新排在安全卡边界，不能中断正在封证的 run。

### 3.1 A1 交出的三格缺口（按 §1.2 单独登记，不由 A1 顺手补）

| ID | 状态 / 依赖 | 交付与边界 |
| --- | --- | --- |
| `V1201-AUTO-PATH-RUNNER-001` | `QUEUED`，不依赖 A2/A3，可在 A3 之后插入 | 让**自动路径**与**服务端读数**在同一条受控通道里同时成立（G1+G2）：`domain.sh` 捕获 `--auto-bundle` 并在封存时按 `seal_run_evidence.py` 的实际必填项传参；受控 launcher 在“需要被 status 观测”的场景给出可复核的 `enable-status` 读数，并把 `data get entity <Kin> Pos/Rotation` 的控制台探针做成默认能力。判据不动产品行为；改 `domain.sh` 的判据/断言集合要另卡。 |
| `V1201-DEMO-CASE-FREEZE-001` | `BLOCKED_DECISION`（等主控冻结 G3） | “一次演示 run 到底断言哪些事实”是定义 PASS 的动作，不属于执行侧自造：需要冻结是否新增融合 case、以及如何在同一次 run 里安放 `V1201-040`（租约到期释放）与 `V1201-080`（停止时仍持有）这对互斥释放原因（两次 run、放宽阈值，还是拆成两条断言）。冻结前不落 fixture、不改 registry、不封存 host 之外的新断言。 |
| 供应链单次中断（G1/G2 之外的观察） | 记录，不建卡 | attempt 2 的 `infinite_amethyst.ogg SUPPLY_CHAIN` 拒绝启动是现行防护的正确形状，但整店 25 分钟下载中一次中断就要整卡重来。是否要断点续传/单资产重试属产品选择，随 `V1201-AUTO-PATH-RUNNER-001` 一起问主控，不自行加实现。 |

### 3.2 A2 交出的四格缺口（同样按 §1.2 单独登记，不由 A2 顺手修）

| ID | 状态 / 依赖 | 交付与边界 |
| --- | --- | --- |
| **N1** `V1201-AUTO-ENTRY-GATE-ORDER-001` | `QUEUED`，不依赖 A3，可插在 A3 之后 | 让 `--auto-bundle` 的准入与 `--profile` 等强：地址禁区、"managed session 只能 join loopback"、profile allowlist 与解析结果一致三件事必须在**任何下载/整店复核之前**判完。判据取复判记录 §3 的 X1 vs X2/Y2 与 B1/B2；实现不得改本记录的期望，收卡要能重跑那三组行并给出"先拒后装"的新读数。**不改 case 判据、不翻 registry。** |
| **N2** `V1201-MAX-BYTES-VALIDATION-001` | `QUEUED`，不依赖 A3 | `--max-bytes 0`/`-1` 今天得到 `exit=70 / INTERNAL_INVARIANT`（`ValueError` 冒到 CLI），`--max-bytes 1` 却是正确的 `SUPPLY_CHAIN` 具名拒止；`--max-bytes` 与 `--profile` 同给时被接受且被忽略，而帮助文本说它属于 `--auto-bundle`。要的是 CLI 层具名校验/具名用法错误，属产品行为。 |
| **N3** `V1201-DISK-PREFLIGHT-001` | `BLOCKED_DECISION`（等主控冻结断言） | 契约"1.20.1 工件…磁盘满 → 无可启动半包"一行在 `src/minekin_core` 无任何实现（无空间预检、无对应失败类别），因此执行侧无法用真实读数回答它。需要先决定：是否装机前预检、失败令牌叫什么、与 `--max-bytes` 预算如何分工。冻结前不自造断言。 |
| **N4** `V1201-SRV-RESOLVER-001` | `BLOCKED_DECISION` | 唯一解析实现是 `SavedAddressResolver`，profile host 必须是字面 IP（复判记录 §1 F3 的 A4 行）。契约那行"SRV/DNS 目标改变"要成为可测行为，先得决定产品是否引入 SRV/DNS；若决定不引入，则该行的正确收法是"无解析路径 + 装载期禁区拒"，需要主控确认这一口径。 |
| 真 socket 上不可达的 `length < 0` 分支 | 记录，不建卡 | `adapters/launcher/server_probe.py` 的负长度守卫在真实帧上永不命中（`_read_varint` 不产负数，`negative_length` 实测 `OVERSIZE`）。属死代码清理，随任一 probe 实现卡顺手看，不作为契约缺口。 |

## 4. 完整 Minekin 长程任务簿（设计先行、证据后置）

以下是持续执行所需的完整方向、顺序与交付门。细到尚未冻结的 case ID/阈值/接口不预编；到其前置门时从专项契约冻结，**一张大项可按真实依赖拆成多张小卡，但不能同时有两个 NEXT**。不依赖重大决策且已冻结的受控本地修复/证据卡可插入 A2/A3 之后、A4 之前；记录原因，不开无限审计格。

### B. P0 证据与运行基础（A 阶段可并行规划，不越过唯一 NEXT）

| ID | 状态 / 依赖 | 完成定义 |
| --- | --- | --- |
| `P0-EVIDENCE-INVENTORY-001` | **`NEXT`（2026-09-26 自 A3 机械提升）**，依赖 A3（已满足） | `report_cases`/`report_promotion` 在规范卷逐 case 标注“缺 fixture、缺当前 build 真证据、真实失败、产品未实现”；先复用旧清单。只把有明确必要性的 missing case 排成独立实现卡，不将盘点本身冒充门绿。 |
| `P0-CONTROLLED-CAMPAIGN-001` | `BLOCKED_EVIDENCE`，inventory 后 | 按 W00→W70/`p0-core` 契约，在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle，包括 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak；每个 case 的独立 oracle、非空转反证、版本摘要齐全，再谈 promotion。既有 `REAL-P0-CAMPAIGN-001` 历史阻断保留，不当成 DONE。 |
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
- 当前不会开启在线认证、扩大任意公网访问、让远程内容改变信任策略、把测试服务端真值送给 Kin，或以 CI 替代本地真跑。
- 一旦走到 A4/上述决策门且没有独立已授权安全卡，保持 `BLOCKED_DECISION` 并交付清楚的选项；不得为了维持活动量反复改 `.tmp`、盘点或文档。
