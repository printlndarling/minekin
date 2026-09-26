# Minekin 开发执行计划（现行唯一队列）

更新：2026-09-26。产品主线是 **1.20.1**；1.21.4 仅作必要回归基线。本文是唯一任务状态入口；[完整产品范围](roadmap.md)、[跨版本契约](version-auto-to-server-control-plan.md) 和各专项契约决定“做对什么”，本文决定“现在做什么”。截至 `cef712b` 的六千余行旧计划及 Qoder 尚未提交的第七类审计草稿完整保存在[历史计划](development-execution-history-through-cef712b.md)，不是当前队列。

## 0. 状态与证据口径

`current_next: V1201-LOCAL-DEMO-REHEARSAL-001`；全库同时只允许这一张 `NEXT`。这是一张新排的**本地 1.20.1 端到端预演卡**，不是 V08 晋级，也不是连接用户服务器的许可。`cef712b` 时旧队列 `NEXT=0/QUEUED=0`；本计划是用户 2026-09-26 要求“一次性编写后续任务”的新排期，不把旧卡改称未完成。

已核实的基线：V01–V07 及空 store 自动安装真跑已完成；1.20.1 `V1201-080` 的正常停止显式松键有 sealed PASS，registry 对应缺口已划出；`HOST-ADMISSION-DESIGN-001` 只交付了[设计和三个未决所有权问题](host-admission-session-coordinate-design.md#5-分歧矩阵所有权问题为什么不由本卡回答)。这些都**不等于** V08、V09、V10 或完整 Minekin 完成。1.20.1 registry 其余缺口按现行文件和 `verify_tested_provenance.py` 重新读取，不以本文计数代替机器结果。旧 W00/W10/W20 的 `promotable` 读数不等于总体 `p0-core tested`；`p0-core`/七场景 campaign 仍有真实证据缺口。CI、ping、旧 bundle、单测、文档自述均不能证明真实入服。

状态语义：`NEXT` 可立即领取；`QUEUED` 必须依赖满足后才顺序提升；`BLOCKED_DECISION` 要用户明确拍板；`BLOCKED_EVIDENCE` 要真实材料；`DEFERRED` 不可开工。以下顺序是**长程任务账本**，不是对未冻结功能/案例的授权。只有本文出现一个 `NEXT`，完成一张后才原子更新队列。不会因为没有可执行卡而创建“再盘点一次”的 docs-only 任务。

## 1. 连续执行协议

1. 每次冷启动按[交接](qoder-execution-handoff.md)检查工作树、HEAD、工作分支、远端 `main` SHA；未提交改动归原作者，不 reset、stash、覆盖。读本文唯一 `NEXT`、对应专项契约和现行机器清单，写下 baseline SHA、允许路径、停止条件。
2. 只做 `NEXT`。需要产品选择、真实外部授权、修改卡外判据/registry、删除数据、接管进程时停止该分支，登记证据和 `BLOCKED_*`；继续已有的独立安全卡，不自行猜结论。测试失败先诊断是否本卡范围内的缺陷；范围外登记单独修复卡，由主控排期。
3. 一卡一可逆提交。先验路径范围和两轴审查（契约/工程），再跑与改动相称的本地门禁；运行时结论必须来自当前 build 的 Docker/受控真跑和 sealed bundle。`verify`、`rejudge`、适用 `replay`、`report_promotion` 四读、负向反证和 provenance 分开记录。失败工件不覆盖，敏感目标不入库。
4. 卡通过后更新本文及[当前 TODO](development-todo.md)，commit，立即 push 工作分支与 `main`（仅在当前共享仓库两 ref 同步且无并发冲突时），核本地 HEAD、`origin/main` 和远端 SHA 一致，才改卡为 `DONE` 并提升下一张。push 失败不领取下一张。Qoder 可以在这些条件全部满足时机械流转已明确排队的卡；`BLOCKED_DECISION`、HOST/W80+、PERSIST、在线认证、扩大公网访问不在委托内。
5. 基础门禁：`uv run --frozen pytest -q`，Ruff check/format，Pyright，`check_boundaries.py`、`check_case_assertions.py`、`verify_fixture_digests.py`、`check_workflow_pins.py`、`git diff --check`。Bridge/proto 加四项 Bridge 检查和 Java 21 `./gradlew check --rerun-tasks`（不可用 UP-TO-DATE 或 FROM-CACHE 替代）。Docker/真实客户端卡须跑其专项真实门禁。提交正文记 `Constraint`、`Rejected`、`Confidence`、`Scope-risk`、`Not-tested`。

## 2. 当前唯一 NEXT：1.20.1 本地完整预演

### `V1201-LOCAL-DEMO-REHEARSAL-001` — `NEXT`

目的：在**全新 Kin、全新 data root、受控本地 offline 1.20.1 服务器**上，验证“保存目标→只读探测→自动解析 tested bundle→空 per-Kin store 安装→真实启动/JOIN/首快照→PLAYABLE→一次限幅 look/move→松键/退出”的**同一 run/generation**闭环。现有 `V1201-040`（移动与转向）和 `V1201-080`（正常停止松键）是分开的证据；本卡要量集成连续性，不能把两份旧 bundle 拼成同 run。可先用当前 CLI/runner 直接跑；若工具不支持该流，记录确切缺口并单独排实现卡，不临时扩产品范围。

- 依赖：已完成 V07 真自动安装和 `V1201-080`；受控本地 runner、Java 21、当前 1.20.1 tested registry/provenance 可读取。先确认基线，不用旧构建结果代替。
- 允许：`.tmp/` 未跟踪运行脚本、私有 profile、受控 runner 数据卷、必要的本卡证据与本计划/TODO/交接；若只需编排，可跟踪最小 runner/test 调用文件。禁止：用户远程服、HOST/PERSIST、online auth、产品行为/安全契约改变、registry `status/gaps` 无证据翻转、历史 bundle 改写。运行结束只清理**本卡新建且精确验证路径**的临时会话/marker；材料先封存，不批量删。
- 验收：自动选择确切 1.20.1 bundle 且空 store `installed > 0`；同 run 的 `PlayableEstablished`、同 generation 的 lease/实际 look+move、释放及退出；客户端与独立本地服务端的位移/朝向读数分别标源；当前 build 的 sealed bundle 四读一致，至少包含一条“缺真实 JOIN/动作/释放即红”的非空转反证；失败时保留失败 attempt。先把已有 `V1201-040/080` 与新结果作清晰对照，**不把本地预演宣称为 V08 远程入服**。
- 停止：客户端不能完成自动路径、需要修改判官来让结果绿、runner 无法同 run 控制、证据材料不齐、需要碰用户服或扩大权限时停在具体阻断。不能用多次碰运气跑隐藏失败。
- 交付：本卡 run/attempt/bundle/digest、四读原始摘要、当前 build 与 runner 版本、未测项、复现命令、commit 与远端 SHA。若没有 sealed PASS，状态保持 `BLOCKED_EVIDENCE`，不提升后续远程卡。

## 3. P0 到可操作的 1.20.1 demo（按序，不跳门）

| 顺位 / ID | 状态 | 交付、验收和停止边界 |
| --- | --- | --- |
| A1 `V1201-LOCAL-DEMO-REHEARSAL-001` | `NEXT` | 上述全新 data root 同 run 预演。 |
| A2 `V1201-LOCAL-NEGATIVE-MATRIX-001` | `QUEUED`，依赖 A1 | 受控本地复判歧义协议、错误版本/身份、恶意 status/SRV、hash/磁盘/下载中断、断连与旧 generation；对照[版本契约](version-auto-to-server-control-plan.md)现有负向用例，**只补实际缺失的组合**，不能修改断言求绿。每例需可重跑的拒绝类别，真实行为需 sealed 证据；若已全覆盖，以索引/机器读数收卡，不造重复 fixture。 |
| A3 `V1201-TESTED-GATE-READOUT-001` | `QUEUED`，依赖 A1–A2 | 在规范数据根重读 registry/provenance、case inventory、四读和负向矩阵，给出“1.20.1 本地可玩”与“不代表远程/全版本”的精确能力边界。只做只读报告和必要的真实证据补封；需要改变 tested 声称时另开卡审查。 |
| A4 `VERSION-REMOTE-SMOKE-001`（V08） | `BLOCKED_DECISION` | 用户先明确**本次**是否允许对其指定 1.20.1 测试服做一次只读 ping 和非破坏性普通玩家入服，以及运行窗口/频率。旧地址和“关闭正版验证”不是持续授权。获授权后依[原卡](version-auto-to-server-control-plan.md#v08-version-remote-smoke-001用户测试服只读探测与非破坏性入服)先 ping 后 JOIN/PLAYABLE，地址只在私有 profile，不扫描、不改服务器、不使用 op/RCON；拒绝/限流/资源包异常立即停。 |
| A5 `VERSION-SIMPLE-CONTROL-001`（V09） | `BLOCKED_DEPENDENCY` | A4 真通过后，在用户指定安全位置、另一次明确动作授权下，≤2 秒前进+小幅转向+release/退出；先 client-observed，只有独立只读 server oracle 才能声称 server-confirmed。保护插件拒绝或残留按键即停。 |
| A6 `VERSION-DEMO-ACCEPTANCE-001`（V10） | `BLOCKED_DEPENDENCY` | A1–A5 真完成后写可复现 CLI demo、风险/未测清单、1.21.4 必要回归、负向与封证索引。缺证据只能交 `PARTIAL/BLOCKED`，不写“全部完成”。 |

A2/A3 是本次新增的**本地安全顺序卡**，允许 A1 完成后机械提升；A4 不能因前三卡通过自动提升。A5 的新动作授权也不能从 A4 的只读/无动作入服授权推导。**机械排期**：A3 收卡后若 V08 尚未获得新授权，不把 A4 设成 `NEXT`；转取 B 段首张安全卡。B 段某卡受真实证据阻断时可转取其后不依赖它的已冻结安全卡（如平台验证），记录跳过原因；若剩余只涉及决策/未冻结契约，则保持 `current_next: none / BLOCKED_DECISION` 并一次性列出所需选择，不发明 docs-only 卡。V08 获新授权后主控重新排在安全卡边界，不能中断正在封证的 run。

## 4. 完整 Minekin 长程任务簿（设计先行、证据后置）

以下是持续执行所需的完整方向、顺序与交付门。细到尚未冻结的 case ID/阈值/接口不预编；到其前置门时从专项契约冻结，**一张大项可按真实依赖拆成多张小卡，但不能同时有两个 NEXT**。不依赖重大决策且已冻结的受控本地修复/证据卡可插入 A2/A3 之后、A4 之前；记录原因，不开无限审计格。

### B. P0 证据与运行基础（A 阶段可并行规划，不越过唯一 NEXT）

| ID | 状态 / 依赖 | 完成定义 |
| --- | --- | --- |
| `P0-EVIDENCE-INVENTORY-001` | `QUEUED_CONDITIONAL`，A3 后 | `report_cases`/`report_promotion` 在规范卷逐 case 标注“缺 fixture、缺当前 build 真证据、真实失败、产品未实现”；先复用旧清单。只把有明确必要性的 missing case 排成独立实现卡，不将盘点本身冒充门绿。 |
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
