# 开发 TODO 与执行门禁

更新：2026-09-19。

本文把现有设计文档转换为可执行开发队列。若本文与专项契约冲突，以更新且更具体的契约为准；P0 的实现入口是 [P0 核心原型执行计划](p0-prototype-execution-plan.md)与 [P0 core 内部架构](p0-core-internal-architecture.md)。

## 执行原则

- 严格按 `W00 → W10 → W20 → W30 → W40 → W50 → W60 → W70` 晋级；前置门禁失败时不以 mock 或后续结果覆盖。
- 每批只增加一个可逆能力，按“schema/fixture/预期 → 实现 → 真实 evidence digest”提交。
- 失败 run 只追加、不覆盖；无实际证据不得标记 `PASS`、`tested` 或 `P0_CORE_TESTED`。
- P0 仅包含一个 Python `minekin-core` 进程与一个 Java 21 Minecraft/Fabric JVM。Dashboard、PlayerMind、LLM、媒体、导航和 HOST 均后置。
- 产品代码不得读取测试 oracle；服务端真值只允许验收器在运行结束后交叉核对。

## 环境门禁

- [x] Git 工作树与 `origin/main` 基线确认。
- [x] Python 与 uv 可用。
- [x] 固定 Java 21；本机以 JDK 21.0.12.1 完成 Gradle 8.12.1 的 Bridge `clean check`。
- [x] 以 CI 中固定版本的 Buf action 提供 schema build/lint/format 门禁；本机另用固定 Buf `v1.50.0` 完成 W00 lint，并复现同一生成字节。
- [x] 完成 Gradle 依赖锁与 SHA-256 verification metadata；固定 Wrapper 8.12.1 已在 Java 21 下通过离线 strict verification `clean check`。
- [ ] 为受控 Linux runner 准备 Java 21、Xvfb、原版 1.21.4 server 与隔离账号/目录。

## W00：规格、夹具与整体框架

- [x] 建立 `pyproject.toml`、`uv.lock`、Python 3.12–3.13 范围与 Node-free P0 依赖清单。
- [x] 建立 `src/minekin_core` 的 domain/application/ports/adapters/entrypoints/generated/cli 边界。
- [x] 建立 `bridge`、`proto/minekin/v1`、`tests` 与 `test-orchestrator` 骨架。
- [x] 实现并测试 Session 状态与合法转换表。
- [x] 冻结 ID、generation、sequence、deadline 与 monotonic/wall-clock 语义。
- [x] 冻结 proto v1：envelope、hello、fault、observation、lease、`release_all`。
- [x] 提交 `src/minekin_core/generated` 的 Python gencode 与 `.pyi` stub，并提供 `tools/generate_protos.py` 与 CI 漂移门禁：生成字节可复现，导入路径统一为 `minekin_core.generated.minekin.v1`，缺 stub 即视为未完成。
- [x] 冻结 SQLite schema/migration v1、单 writer-thread 与 transactional outbox 契约。v1 文件本身未改动，仅在其上追加。
- [x] 把单步 v1 迁移泛化为有序迁移执行器：每条迁移自己记账、抬升 `user_version` 并更新 `schema_version`，重复打开是 no-op，v1 库可原地升到 v2 且保留既有事件；比当前代码更新的库版本被拒绝而不是降级。
- [x] `0002_identity_root.sql` 落 `kin_identity` 单行身份根：`kin_id` 不可变，离线 UUID 由 `uuid_algorithm` + `username` 推导而不是存储（存了就会和规则本身不一致），不保存任何必须失效的瞬时状态。
- [x] `schema.sql` 是当前 schema 的 golden 文档表示，与迁移产物对齐到 v2；新增漂移测试：把 golden 文件与迁移各建一个库、比对 `sqlite_master` 的建表语句与版本。此前它已悄悄停在 v1 而无人发现，因为没有东西会因它过时而失败。
- [x] 冻结错误分类、退出码、脱敏规则与未知错误 fail-closed 行为。
- [x] 冻结 CLI schema；`doctor` 为只读实现，其余命令在实现前明确无副作用地失败。
- [x] 提供 fake Clock/Launcher/Bridge/EventStore/Evidence ports。
- [x] 提供 protobuf、framing、event replay 与 crash golden fixtures，并固定跨平台摘要。
- [x] 自动检查依赖方向、Bridge 引用与产品 wheel 不得包含 oracle。
- [x] 写 ADR：P0 不引入 Web、ORM、通用 Agent 框架和多 Python 服务。
- [x] 门禁：schema 可版本化、fixtures 摘要固定、oracle 与产品输入目录隔离。

## W10：Launcher 元数据与 dry-run

- [x] 保存上游原始响应并解析、校验 Mojang 1.21.4 与 Fabric 0.16.9 固定元数据；版本身份、Java/main class、规则与 Fabric 继承均 fail closed。
- [x] 生成可审计的内容寻址 classpath、session natives 目录、独立 JVM argv、typed game argv 模板与规范化计划摘要。
- [x] 逐项校验 URL、大小、SHA、Java 21、main class、规则与固定 mod 集；计划覆盖 4,120 个去重工件（含 4,039 个 asset object、9 个 Linux native 和 logging 配置）。
- [x] 使用独立 argv 元素；JVM 占位符必须全部解析、game 占位符必须转为 typed entry，并禁止 shell 拼接与宿主 `.minecraft` 访问。
- [x] 建立带 staging/quarantine/原子发布的内容寻址 artifact store、逐文件复核的只读 bundle 与 generation 隔离的可写 session overlay。
- [x] 门禁：所有工件与参数可复核；元数据/asset/bundle 篡改、未知 mod、路径越界或不兼容 runtime 均 fail closed；Bridge 未构建时保持明确 blocker，不谎称 launchable。

## W20：只读 Thin Bridge

- [x] 建立 Java 21/Fabric 1.21.4 client entrypoint 与固定 manifest。
- [x] Java gencode 归 Gradle protobuf plugin 在构建期从 `proto/` 生成，不提交生成目录；`bridge/src/generated` 的旧 Buf 产物已移除，避免污染 bundle source digest。
- [x] 实现 control/event 双通道的长度前缀 Protobuf framing。
- [x] 实现 nonce、protocol、generation、bundle 与 capability 握手。
- [x] Bridge 默认 `OBSERVE_ONLY`，握手前无连接和输入能力。
- [x] IPC/编码在后台有界队列运行，Minecraft 对象只在 client thread 访问。
- [x] 门禁（静态子集）：错误 nonce/protocol、未协商 capability 与越界心跳/帧长被拒并 safe-stop，未知 mod 被 bundle recipe 拒绝，握手后仍为 `OBSERVE_ONLY`（无连接、无输入）；由 `BridgeProtocolSelfTest`、`BridgeIpcWorkerSelfTest` 与 `test_unknown_mod_is_rejected` 覆盖，并已接入 CI 的 `bridge-static`。
- [ ] 门禁（实测）：真实 1.21.4 客户端内 tick/render 回调预算的 P50/P95/P99 尚未测量；W20 只有“worker 启动不阻塞、队列有界不阻塞”的结构证据，实测随 W30 首次真实启动补齐。

## W30：Offline Session

- [ ] 按 OFF-A（`offline`）→ OFF-B（`legacy`）运行有界候选，不静默漂移。
- [x] 冻结 `token=0`、offline UUID 与 clientId/xuid 显式空 argv 语义：`domain/offline_identity.py` 复刻 `UUID.nameUUIDFromBytes("OfflinePlayer:"+name)`，向量取自 JDK 实际输出；`adapters/launcher/offline_session.py` 冻结 OFF-A/OFF-B 候选，并强制每个空值仍是紧跟自己 option 的独立 argv 元素。
- [x] OFFLINE-001 静态子集：dry-run 无字面 `${...}`；未声明占位符直接拒绝而不是替换成空字符串；空值位置与候选声明不一致即失败。
- [x] 身份根可持久化：`kin_identity` 单行存储 `kin_id`、local profile、identity revision 与 username；缺失时读取直接失败而不隐式新建，第二次 `init` 被拒绝，未知 `uuid_algorithm` 被拒绝。
- [x] `minekin init` 接线完成：数据根来自 `MINEKIN_HOME`、username 来自 `MINEKIN_USERNAME`，两者都**没有默认值**，未设置即 `CONFIG` 失败并点名变量；相对根在 `resolve()` 之前拒绝。目录布局为 `<root>/kin/<kin_id>/{kin.sqlite3, run/}`，`run/` 就是启动计划相对路径所相对的根。`init` 不幂等：数据库已存在即拒绝，且拒绝时不留下任何痕迹。这两项都是**提案**，见[数据根与身份创建提案](run-directory-proposal.md)——契约都没有规定它们，改起来只涉及一个函数与 `init` 的读取点。
- [x] 把冻结的 session argv 与计划里的 JVM 参数组装成完整命令行：计划中的路径按契约是 run-root 相对，只有 `adapters/launcher/process.py` 把它们变成绝对路径，因此"到底指向哪个目录"只有一个答案。classpath 逐项重建而不是重写拼接串；`-cp` 后面若不是类路径就拒绝（否则会把下一个选项当成类路径吞掉）；仍为相对计划路径、或 `.minecraft` 作为路径分段出现的参数一律拒绝。该判别必须按路径分段——`net.minecraft.client.main.Main` 是类名，不是目录，第一版按子串判断会误杀它。
- [ ] 真正 spawn 与进程监管（PID identity、接管/终止判定）；run root 的来源仍未定，见上文。
- [x] Bridge 脱敏报告：`SessionIdentityReport` 随 hello 与首快照上报候选、用户名、UUID、AccountType 与 clientId/xuid presence；凭据按结构不可携带——消息没有 `bytes` 字段、观测 record 没有 token/secret/key 分量、`credential_values_exposed` 为 true 时拒绝。形状由已发布的 descriptor 断言，不靠人工复查。
- [x] `SESSION_MATERIAL_MISMATCH` 规则：从**实际 argv** 读回 Launcher 记录的 session 材料（不是从候选重新推导），与 Bridge 上报逐项比较；uuid 按规范化后的身份比较以容纳 id128/canonical，`userType` 与 `AccountType` 分属不同命名空间故只记录不比较，任一不一致都阻断 `PLAYABLE`。
- [ ] 读取真实客户端 Session 回填该报告：需要真实客户端，尚未实现。
- [ ] 执行 `OFFLINE-001…100`，仅在条件满足时运行 UUID/sentinel 对照。
- [ ] 门禁：启动、握手与身份材料可解释，失败分类明确。

## W40：原版服务器准入

- [ ] 启动隔离的 vanilla 1.21.4 `online-mode=false` dedicated server。
- [x] 静态子集：可信 Server Profile 加载与地址策略——只接受冻结 schema 里的 `127.0.0.1`/`::1` 两个 loopback literal，拒绝 DNS 名、私网、通配、第二条 loopback 与未知字段；profile 内容摘要作为 revision。以 `schemas/server-profile.schema.json` 做逐项对照测试，产品规则只允许比 schema 更严。
- [x] 地址策略判定：解析后的 endpoint 必须再过一次策略，只接受 profile 声明的网络；名称永不解析入位（可重绑定），link-local（含云元数据 `169.254.169.254`）、unspecified 与 multicast 是任何策略都不能放宽的无条件拒绝。profile 加载与判定共用同一份规则，不再各写一遍 loopback 字面量。
- [ ] DNS/SRV 解析本身，以及「每次重连重新解析、不永久信任旧 SRV 结果」的时序：需要真实客户端连接路径。
- [ ] connection generation 的分配与「旧 generation 回调只作诊断」在真实事件流中的接线；`Generation.accepts` 已有，接线未做。
- [ ] 经普通客户端执行 ConnectWorld，按 JOIN/认证/白名单/资源包等原因分类。
- [ ] 取消、重连与晚到 callback 不得改变新 generation。
- [ ] 执行 `ADMIT-001…120`；Kin 不得获得 op、RCON 或 console 权限。

## W50：玩家等价首快照

- [x] visible-world 过滤器与首快照准入：未确认视线的候选只丢弃不猜位置，距离、非有限坐标（NaN 会绕过朴素距离判断）、缺失或重复的目标令牌各自计数；快照未准入时**不交出任何实体**，漏检 `admitted` 的调用者也拿不到世界。
- [x] self 与 inventory 一致性过滤器：生命不在 `0..max_health`、`max_health` 非正、饥饿不在 vanilla 的 `0..20`、饱食为负、非有限数值，以及 `alive` 与 `health > 0` 互相矛盾都判为不可用读数——按拒绝处理而不是钳制，300 点生命不是满血玩家。背包侧拒绝未设置的 revision、非 1..64 的堆叠数、缺 item id 与同槽重复；`bool` 是 `int`，因此每个整数上界都单独挡 `true`（否则 `food=true` 会被读成食物 1）。
- [x] 同 generation 与身份绑定的准入：`authoritative`、快照 generation 必须是当前 generation、快照内 session 报告必须与 Launcher 记录一致，三者任一不成立都不准入。
- [ ] 建立 Bridge/Runtime、server truth、orchestrator 三条时间线：需要真实运行。
- [x] oracle canary 与字段泄漏扫描：canary 值进入 wheel 路径/内容即失败（已验证能抓到人为注入），产品源码与 runtime-input 也扫描；观察消息的字段集与命名按已发布 descriptor 断言，容器、seed、服务端坐标没有字段可落。
- [ ] 门禁：首快照失败不授 lease（实体侧已按结构保证）；实测部分需要真实客户端。

## W60：最小合法输入

- [ ] 实现 `look`、短时 `move` 与幂等 `release_all`。
- [ ] 实现唯一 input owner、lease、deadline、priority 与前置状态检查。
- [ ] 实现 Core/Bridge 双 watchdog。
- [ ] 断 IPC、死亡、GUI 冲突、超时或 generation 改变时全部松键。
- [ ] 门禁：服务端离线核验真实位移；不得瞬移、直接写状态或残留按键。

## W70：恢复与证据晋级

- [ ] 注入 Core、Bridge/client、server 与连接阶段故障。
- [ ] 对账未决 outbox，失效历史 generation/lease，防止危险动作重放。
- [ ] 验证重复启动、同一 `kin_id` 重启与瞬时世界状态重验。
- [x] 不可变 evidence bundle 的封存与校验：manifest 与冻结形状一致，工件按 sha256 记账，bundle 摘要覆盖 manifest 字节；同一目录绝不覆盖旧 run（改正是新 run，不是编辑）；工件或 manifest 含凭据正文即整体拒封——不做就地脱敏，静默改写的日志比缺失的日志更糟；校验端重新对账摘要并检出缺失、篡改与未声明文件。工件名走白名单而非黑名单：Windows 上 `/x` 既非绝对路径、拼接又会替换 bundle 根。
- [x] 报告诚实性规则：缺 expected/observed 对照时结果不得是 `PASS`（只能 `INCOMPLETE`），`PASS` 不得带 failures，`FAIL` 必须有 reason code，只有先后无法在时钟误差窗口内判定时才用 `AMBIGUOUS`。
- [x] candidate→tested 晋级检查：case manifest 按冻结 schema 校验（含 `mandatory` 必须是布尔——真值字符串会把用例悄悄移出晋级门禁；`assertions` 不得为空），`case_version` 用用例定义自身的摘要，因此改过用例就必须产生新 run；只有 mandatory 用例全部拿到「已校验且结果为 `PASS` 且版本一致」的证据才可晋级，缺证据/未校验/非 PASS/版本不符分别给出稳定原因码；非 mandatory 用例不拦晋级。
- [x] case manifest 的 oracle 边界由 `tools/check_boundaries.py` 检查：`inputs` 不得出现 oracle 标记，`oracle_inputs` 必须落在 oracle 目录内。产品侧只校验结构——产品代码连 oracle 的名字都不许出现，这条规则曾经被我错误地放进产品里，是 `check_boundaries` 抓出来的。
- [ ] 三条时间线（Bridge/Runtime、server truth、orchestrator）与 `evidence verify`/`replay` 的 CLI 接线：前者要真实运行，后者要 run 目录约定与断言谓词语义，两者都未定，因此 bundle 与晋级检查目前只有库、没有命令入口。
- [ ] 跑完 `CORE-001…090`、mandatory OFFLINE/ADMIT cases 与 L6 baseline。
- [ ] 门禁：mandatory case 全部有真实 `PASS` evidence 后才能标记 `P0_CORE_TESTED`。

## W70 之后

- [ ] W80：独立 `p0-nav-exp` 导航实验；核验输入冲突、隐藏真值与 SBOM/许可。
- [ ] 生存底座：可见树导航、正常破坏/拾取、GUI 合成、工具链、食物与首夜。
- [ ] P1 PlayerMind：身份/人格、运行者关系种子、自主目标、承诺、世界书、知识画像、分层记忆、SkillSpec、注入与工具安全。
- [ ] HOST 专题：独立 `p0-host-exp`，执行 `HOST`、`HOSTCTL`、`HOSTCOMMIT` 用例。
- [ ] P2 产品化：Gateway、Dashboard、Live View、systemd/cgroup、备份与可观测性。
- [ ] P3 社会 MVP：权属、拒绝、承诺、损失、归因不确定性、调查与和解。
- [ ] P4 单 Kin 综合演示：独居、等待、死亡调整、合作/分歧与跨日连续性。
- [ ] 扩展：仓储/熔炼/施工/战斗/跨维度/末影龙；之后才评估多 Kin、模组、多版本与在线认证。

## 已消歧的文档口径

1. `technical-stack-selection.md` 的早期“首个切片”提到 Gateway/Dashboard，但更具体且更新的 P0 契约明确 P0 无 Web/Node；因此 Gateway/Dashboard 后置 P2。
2. P0 core 没有模型或网页工具；W00–W70 只实现来源、trust、脱敏与 oracle 隔离基础。完整 `INJECT-001…120` 在 PlayerMind/工具层进入后执行。
3. Xvfb 可作为真实客户端启动环境，但 FFmpeg/Live View 不进入 P0 core。
