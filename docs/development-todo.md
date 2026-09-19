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
- [x] 固定 Java 21；本机以 JDK 21.0.12.1 完成 Gradle 8.12.1 的 Bridge `clean check`，并在改过 proto 与 Bridge 源码之后以 `--offline` 重新验证过：strict verification、锁定依赖、`BUILD SUCCESSFUL`。Bridge 源码树摘要在反复跑 Gradle 之后保持不变，说明 `build/` 与 `.gradle/` 确实被排除在摘要之外。
- [x] Bridge 源码树摘要不再随平台变化：recipe 的 `source_digest` 原来按**后缀白名单**决定要不要把 CRLF 归一到 LF，白名单里有 `.java`、`.kts`，唯独漏了 `.xml`，于是 `gradle/verification-metadata.xml` 一个文件就让同一个 commit 在两平台上摘要不同（23c7bfe：Linux 等价树 `40664fab…`、Windows 检出 `4bd0189c…`）。记录下来的那个值其实哪个检出都对不上，代价是 launch plan 一路失败——因为 CI 因账单停摆，这个红灯没有任何人看见。现在改为按 git 自己的判据（前 8000 字节内有 NUL 即二进制）归一所有文本文件，二进制逐字节保留，并有测试断言「同内容 LF 树与 CRLF 树摘要相同」「只差一个 CRLF 的两个 jar 摘要不同」。**由此产生的纪律：Bridge 源码一改，recipe 的 `source_digest` 就必须重算**，否则所有依赖 launch plan 的用例都会报「Bridge source tree digest differs」而不是它们真正要报的错。
- [x] 以固定版本的 Buf action 提供 schema build/lint/format 门禁；本机用固定 Buf `v1.50.0` 完成 lint 并复现同一生成字节。
- [x] 补上 Buf **CLI** 的版本 pin：原来只钉了 action（`bufbuild/buf-action@v1.5.0`），而 action 下载的是哪个 CLI 并没有指定，等于用「最新的那个」。lint 规则与 format 输出会随 Buf 版本变化，所以这道门禁本来可以在本仓库毫无改动的情况下变红或悄悄改成在检查别的东西。现在显式写 `version: v1.50.0`，并有契约测试断言这条 pin 存在（同一个测试也覆盖「哪些工具由 workflow 自己安装就必须自己钉住」）。
- [x] Buf CLI 的 `checksum` 已补上：重试后取到了 release 的官方 `sha256.txt`，并先确认 action 下载的是**裸二进制** `buf-Linux-x86_64`（其 dist 里完全没有 `tar.gz`），因此用的是该条目而不是压缩包的摘要。契约测试同时断言 version 与 checksum 存在且是 64 位小写十六进制。
- [ ] workflow 里的 action 本身仍按 tag 引用（`actions/checkout@v5`、`astral-sh/setup-uv@v6`、`bufbuild/buf-action@v1.5.0`），没有按 commit SHA 固定。本仓库对工件一律做摘要核验，action 是另一类供应链入口；是否改成 SHA 引用需要单独决定（它会让升级更麻烦，但能挡住 tag 被移动）。
- [x] 完成 Gradle 依赖锁与 SHA-256 verification metadata；固定 Wrapper 8.12.1 已在 Java 21 下通过离线 strict verification `clean check`。**但这份 metadata 目前只在一台机器上成立**：它记录了 Loom 本地**中间**工件的本机摘要，换平台即 mismatch——注意这与发布物无关（最终 JAR 两边同字节），所以这纯粹是一道门禁的可移植性问题，不再阻断可复现性结论；W10 有完整证据与待定选项。
- [x] 用 Docker 实测过 Linux 侧：容器里的 Linux 构建**能完整跑通**（为此需要在命令行加 `--dependency-verification=off`，不改任何已提交配置），产出与 Windows 逐字节相同的 JAR。JDK、依赖缓存与锁文件本身够用；拦住的不是构建，而是上面那道门禁。
- [x] **客户端侧的受控 runner 已建好并验证**：`test-orchestrator/runner/` 里有 Dockerfile、驱动脚本与说明。基础镜像是 `eclipse-temurin:21-jdk-noble`（glibc），因为冻结的 WAL 门禁要 SQLite >=3.51.3，而实测各发行版自带的是 Ubuntu 24.04 `3.45.1`、Debian trixie `3.46.1`、Alpine `3.53.4`——满足门禁的只有 musl 的那个，而 Minecraft 的 LWJGL native 是 glibc 构建，两个要求指向不同镜像，所以这里取 glibc 镜像**自己带一个新的 SQLite**：构建时抓 `sqlite-autoconf-3530400.tar.gz`，先用上游公布的 SHA3-256 `454e45f6…` 核对（`openssl dgst -sha3-256`），核对通过才编译，装到 `/opt/sqlite` 并**不**放进系统库路径——由驱动脚本在命令行上给 `LD_LIBRARY_PATH`，于是「用的哪个 SQLite」写在命令里而不是藏在镜像里。**实测结果**：`run.sh doctor` 四项全过（Python 3.12.3、Java 21、protobuf 6.33.6、SQLite 3.53.4），同一个命令在 stock Ubuntu 容器里只有 SQLite 那项失败；`xvfb-run -a --server-args="-screen 0 1280x720x24" glxinfo -B` 报 llvmpipe（LLVM 20.1.2）Mesa 25.2.8、**max core profile 4.5**——Minecraft 1.21.4 要 GL 3.2 core，所以客户端有可用的渲染后端；**软件光栅下的实际帧率仍未测**，那正是这个 runner 存在的意义。
- [ ] runner 的**另一半**仍未做：原版 1.21.4 dedicated server、隔离账号与逐 run 目录。客户端侧环境已就绪，但还没有任何东西可以被连接。
- [x] 顺带修掉一个**可诊断性**缺陷：上面那次实测里 `minekin init` 在容器里以 `INTERNAL_INVARIANT`（退出码 70）失败，消息是「unexpected internal failure」——因为 `SQLiteCompatibilityError` 原先只是 `RuntimeError`，未分类异常会被 CLI 脱敏成内部不变量错误，于是**把话说得最清楚的那条消息恰好被吞掉了**（实际内容是：SQLite 3.45.1 outside the validated multi-connection WAL safety set）。现在它是有分类的 `MinekinError`（`STORAGE` / `OPERATOR_ACTION`），消息里还会点名「本构建接受 3.51.3 或更新，或回补版 3.44.6 / 3.50.7」，于是操作者拿到的是可执行的拒绝而不是一句内部错误。已做变异验证：把它改回 `RuntimeError`，那条 CLI 用例立刻失败（分类退回 INTERNAL_INVARIANT）。**一般化的那条教训**：任何「我明确知道哪里不对」的拒绝都不该以裸异常形式抛出，否则它在 CLI 那一层会被降级成不可诊断的错误。
- [x] 照那条教训把整棵代码树扫了一遍（非 `MinekinError` 的 `raise`），三处**命令路径上会被脱敏成 INTERNAL_INVARIANT** 的都修了：**（一）** `select_kin` 对磁盘上发现的 Kin 目录名不做校验，`KinId(...)` 抛裸 `ValueError`——一个名字带空格的目录会让 `session start/status/stop` 全部以「unexpected internal failure」失败，而真正的原因（目录名不是合法标识符）不可推导；现在点名那个目录。**（二）** `session start` 在读身份根**之前**没有「库在不在」的检查，而 `session status` 有（`cli/status.py`）；`connect_reader` 是 `mode=ro` 打开的，文件缺失只会得到一个驱动层错误。现在两者措辞一致：点名路径并让人去 `minekin init`。**（三）** 账本读路径上「存下来的 payload 与它自己的摘要对不上」抛的是裸 `ValueError`，于是**连事件 id 一起丢了**——而那正是唯一能让它对账的东西；现在是有分类的 `STORAGE` 错误并把事件 id 写进消息。三处都做了变异验证：各自回退后，对应用例分别失败。
- [x] 上一条挂着的那个洞已经按同一个判据堵上了：读连接现在**拒绝任何不是本构建写出的账本**（`connection.assert_reviewed_ledger`）。这里先要回答的是那个问题本身——**未迁移的库该不该可读**——答案是「不该，而且是刻意的」：本构建没有任何路径会产生这样一个文件（`connect_writer` 在同一次调用里就把它迁移了），所以没有 schema 的库只可能是**迁移回滚后的残骸**或**别人的数据库**，两者都应该在这里被点名，而不是稍后以 `no such table: kin_identity` 出现在驱动层再被 CLI 脱敏。校验顺序是先看 `user_version` 是不是本构建认识的（否则 `_EXPECTED_TABLES` 会 KeyError），再复用写路径已有的 `_validate_schema` 查 application_id 与期望表。**刻意没有**用「捕获 `OperationalError`」来做这件事——「文件不是我们的」与「文件被锁住」是两种不同的状况，把前者当成后者会是新的误报。已做变异验证：去掉 `connect_reader` 里的那次调用，三条用例（外来库、未迁移库、以及 CLI 上的 STORAGE 报告）同时失败；同时加了一条反向用例，确认校验不会拒掉它本该保护的正常账本。
- [x] 已实测 wheel 装出来能不能跑：把 `uv build --wheel` 的产物装进一个干净 venv 再逐条执行命令。`doctor`、`init`、`session status` 都正常（migrations 与 `schema.sql` 确实被打进 wheel，否则 `init` 会在 importlib.resources 上炸）。但 `launch-plan`（以及依赖它的 `session start`）在源码树之外必然失败，因为它用 `Path(__file__).resolve().parents[4]` 猜工作区根，装在 site-packages 里就猜到了 venv 的 `Lib`，于是去找 `<venv>/Lib/bridge` 并报「Bridge source root is missing」。现在改为按标记目录（同时存在 `bridge/` 与 `proto/`）向上查找工作区，并在找不到时把查找起点和「已安装的 wheel 不带源码树」写进错误里。这条 CI 结构上抓不到：CI 会 build wheel，但所有命令都在源码树里跑。

## W00：规格、夹具与整体框架

- [x] 建立 `pyproject.toml`、`uv.lock`、Python 3.12–3.13 范围与 Node-free P0 产品依赖清单。
- [x] 固定 Pyright 门禁的 Node 运行时（原始记录如下）：产品与构建确实不需要 Node，但 `uv run pyright` 需要，且它默认先用 `PATH` 上的 node、找不到就用 nodeenv 联网下载。实测本机用 PATH 上的 v22.22.3，把 node 移出 PATH 后下载了 26.9.0——同一份代码在不同主机跑在不同 Node 上，完全离线的环境跑不了这道门禁。要么预先提供固定版本 node，要么上 `pyright[nodejs]` + `PYRIGHT_PYTHON_GLOBAL_NODE=0`。详见[开发环境](development.md)。**已解决**：依赖改为 `pyright[nodejs]`，锁文件里多了逐平台记摘要的 `nodejs-wheel-binaries`（24.19.0），Pyright 只用它。两条实测：`PATH` 上完全没有 node 时 `pyright --version` 照常返回；把必然失败的假 `node` 放在 `PATH` 最前面，Pyright 仍正常通过。**没有**顺手加 `PYRIGHT_PYTHON_GLOBAL_NODE=0`——装上这个 extra 之后它不改变任何结果，而留一个不控制任何东西的设置正是本仓库一直在清理的那类问题。
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
- [x] 复核过 W10 计数：实际 4,120 个去重工件 = 4,039 asset + 69 library + 9 native + client + asset-index + logging，与文档所写一致。
- [x] 逐项校验 URL、大小、SHA、Java 21、main class、规则与固定 mod 集；计划覆盖 4,120 个去重工件（含 4,039 个 asset object、9 个 Linux native 和 logging 配置）。
- [x] recipe 的 `fabric` 段全部成为受检 pin：`api` 与 `yarn` 此前只是一段没人校验的字符串，而评审者正是靠这段了解这个 bundle 由什么组成，于是"写下来的"可能和"实际用的"不一致。现在两者都按固定常量 fail closed，并有一条测试把它们与 Bridge 的 Gradle 版本目录逐项对齐，两处版本无法再各自漂移。
- [x] 使用独立 argv 元素；JVM 占位符必须全部解析、game 占位符必须转为 typed entry，并禁止 shell 拼接与宿主 `.minecraft` 访问。
- [x] 建立带 staging/quarantine/原子发布的内容寻址 artifact store、逐文件复核的只读 bundle 与 generation 隔离的可写 session overlay。
- [x] 工件抓取：只走 https（重定向降级到 http 也拒绝）、URL 不得带凭据；已在校验通过的缓存中的工件直接复用、不重发请求；只有传输错误才重试，策略拒绝与摘要不符立即返回——重下同样的错字节只会浪费镜像；单次 pass 不因一个失败中止，交由调用方在 `complete` 为假时拒绝启动。暂存、隔离、原子发布与只读封存由 `ArtifactStore.install` 负责，抓取层只提供传输。
- [x] 有界地核对了固定上游**如今仍然**提供固定字节：`tools/verify_supply_chain.py` 只取每个上游主机上最小的那个工件，外加 recipe 唯一的 mod（fabric-api）。它在**抓取之前**先印出本次会用掉多少字节、超出预算即拒绝——全量抓取是一个 GB，不该被顺手做掉。2026-09-19 实测：6 个工件覆盖全部五个上游主机，全部通过；其中 fabric-api 的 size 2,149,128、sha256 `d183bacb…`、sha1 `1c7871b6…` 与 recipe 及文档所记逐位相同。这个工具**不进 CI**：它需要网络，而 CI 不该依赖 Mojang；可离线验证的那一半（预算拒绝）有测试。
- [ ] 全量 4,120 个工件与真实客户端仍未跑：需要受控 runner。
- [x] 原版 server JAR 的 pin 也核对过了：契约与资料索引记的 SHA-1 `4707d00e…`、大小 56,880,250 bytes，与冻结元数据 `downloads.server` 逐位相同，且 Mojang 的 URL 本身把 SHA-1 写在路径里（内容寻址），因此三者互相印证。这三条现在都是**离线**断言（`tests/contract/test_server_artifact_pin.py`），契约或元数据被改就会失败，不必每次重下 54 MB。
- [x] 真实上游也核过了：`tools/verify_supply_chain.py --include-server --max-bytes 60000000` 实测 7 个工件（五个 bundle 主机 + fabric-api + 原版 server）全部匹配，server JAR 56,880,250 bytes、SHA-1 相同。server 是 opt-in：默认预算下工具会先印出会花 59,531,345 bytes 然后**拒绝**，所以 54 MB 不会被人顺手拉下来。
- [x] 门禁：所有工件与参数可复核；元数据/asset/bundle 篡改、未知 mod、路径越界或不兼容 runtime 均 fail closed；Bridge 未构建时保持明确 blocker，不谎称 launchable。
- [x] 实测 Bridge JAR 并修正了对 `build_required` 的理解：`./gradlew build` 产出 `minekin-bridge-0.0.0.jar`（1.17 MB、157 项，含 `fabric.mod.json`、生成的 `io.minekin.protocol.v1.*`，以及 include 进去的 `META-INF/jars/protobuf-javalite-4.36.2.jar`），连续三次 `clean build` 的 SHA-256 完全相同，所有条目时间戳都是 1980-01-01（DOS epoch）。
- [x] 但那份确定性**不是构建声明出来的**：在 `build.gradle.kts` 里加 `withType<Jar>` 的 `isPreserveFileTimestamps = false` / `isReproducibleFileOrder = true` 之后产物字节完全没变——连条目顺序都没变有序，因为真正产出 remapped jar 的是 Loom 的 `RemapJarTask`。既然那条声明不控制真正发布的东西，就没有留下它：一个看起来保证、实际不保证的设置，正是本仓库一路在清理的那类问题。
- [x] recipe 现在**按固定 SHA-256 钉住 Bridge JAR**，`build_required` 消失了。依据是供应链契约那句「缺散列的自有工件使用 Minekin 发布签名或固定 SHA-256，不把 TLS 当唯一完整性保证」——Bridge 是自有工件，没有上游替它公布摘要，所以固定 SHA-256 就是它该有的形状；schema 本来就允许（`verification: sha256` + `digest`/`size`/`source`/`license`，`source_digest` 仍作为「这份摘要出自哪棵源码树」的审计链保留），因此不需要改 schema。
- [x] 判断"这个 jar 在不在、对不对"挪到了**启动时**（`require_built_bridge`），而不是写进 plan。理由是 plan 必须是纯函数：如果把「本机有没有构建过」算进 blockers，`plan_sha256` 就会随机器变化，而它正是 descriptor 里的 `bundle_digest`——bundle 身份随构建状态漂移正是契约要避免的。三种拒绝各自明确：没构建（点名路径与 `./gradlew build`）、大小不符、字节不符（后两者是 `SUPPLY_CHAIN`，因为"计划声称这个摘要却运行别的字节"才是这个 pin 存在的理由）。已用**真实构建产物**端到端验证：`sha256sum` 与 `size` 都等于 pin，`require_built_bridge` 接受；`minekin bundle verify` 现在报 `launchable: true`、`blockers: []`。
- [x] 由此产生一条**更严的纪律**：改 Bridge 源码不再"改完就好"。jar 必须重建，`recipe.py` 的 `BRIDGE_JAR_SHA256` / `BRIDGE_JAR_SIZE` 与 recipe fixture 里的 `digest`/`size` 必须同时更新——否则所有 recipe 用例会以"pin 不描述这次构建"失败。这与 `source_digest` 是同一条纪律的两个部分：一个说"哪棵源码树"，一个说"它构建出的字节"。
- [x] ~~仍未做的、也是它与"能启动"之间的真正距离：没有任何东西把固定 mod 集放进客户端的 mods 目录。~~ **已在 W30 收口**：`fixed_mods` 现在是完整记录而非两个名字，`install_fixed_mods` 按 pin 校验后把两个 jar 放进 overlay 的 `mods/`（见 W30 对应条目）。
- [x] 把上一条追到底，结论比「那条声明没用」更精确：`RemapJarTask` **确实**继承 `org.gradle.jvm.tasks.Jar`（实测层级：`RemapJarTask_Decorated` → `RemapJarTask` → `AbstractRemapJarTask` → `Jar` → `Zip` → `AbstractArchiveTask` → …），所以 `withType<Jar>` 的确配置到了它；但把 `isPreserveFileTimestamps` 反过来设成 `true` 之后产物仍然逐字节相同（时间戳仍是 1980、顺序仍未排序、摘要不变）。也就是说决定最终字节的是 Loom 的 remap 阶段，不是 `Jar` 任务自己的写档。
- [x] 这修正了「确定性来路不明」的判断：它来自 Loom 刻意为之的可复现输出，而 Loom 本身是**被钉住的**——版本目录写死 1.9.2，`verification-metadata.xml` 有它的 SHA-256，`check_bridge_scaffold.py` 也会校验。因此确定性依赖的是一个被固定并核验过的构件，而不是运气；Loom 升级时必须重新评审摘要，这正是钉住 recipe 的含义。
- [x] **跨平台可复现问过了，答案是可以**：Bridge JAR 在 Windows（`21.0.12.1+1-LTS-4`）与 Linux x86_64（Temurin `21.0.12+8`）上逐字节相同，两边都是 `fc1692d2…`——Linux 侧连做三次 `clean build`、Windows 侧连做两次，六次全一致。**所以 W10 那条「在受控 Linux runner 上产出同一摘要之前不得把 JAR 摘要写进 recipe」的前提已经成立**，JAR 摘要有资格被钉住。
- [x] 更正上一条曾经给出的结论：这里先记的是「答案是不」，**那是错的**，错在把依赖校验的失败读成了「构建产物不同」。两者不是一回事：失败的是 51 个 **Loom 本地产出的中间工件**（remap 过的 Fabric API mods 与 merge 过的 Minecraft jar），它们的字节确实随平台变（`fabric-api-base-0.4.54+b47eab6b04.jar` 记录 `59f44704…`、Linux 产出 `1d4b01ea…`），但**我们自己那些类经过 remap 后的最终产物是同字节的**。也就是说随平台变的是中间物，不是发布物。
- [x] 同一次调查里我自己还犯了一个会误导下一人的错，一并记下：容器里只拷了 `bridge/`，而 `build.gradle.kts` 写的是 `proto { srcDir("../proto") }`，于是 `:generateProto` 报 `NO-SOURCE`、`compileJava` 报满屏 `package io.minekin.protocol.v1 does not exist`——看起来像移植性缺陷，其实是**我给的源码布局缺了 `proto/`**。要复现就把 `bridge/` 与 `proto/` 按原相对位置一起拷进去。
- [x] 在容器里跑完整构建需要在**命令行**上加 `--dependency-verification=off`（不改任何已提交配置），因为严格校验会被上面那 51 个中间工件挡住。这解释了为什么这条路以前走不通：不是构建不可复现，而是**门禁把跨平台构建挡住了**，而门禁本身是被本地工件摘要钉死的（见环境门禁那条）。
- [x] ~~下一步由此明确：既然摘要可复现，就应该把 JAR 摘要钉进 recipe~~ **已做**（ef45c22）：recipe 现在按固定 SHA-256 钉住 Bridge JAR，`build_required` 消失，`launchable` 为真，jar 是否存在改为启动时检查（见本节前一条与 W30）。
- [x] 顺带补上了一个真实的缺口：依赖校验只钉了 **Windows** 的 `protoc-4.36.2-windows-x86_64.exe`，而 protobuf 插件按当前平台挑 classifier，于是 Linux/macOS 上要么「没有缓存版本」（离线）要么「摘要未列出」。现在 `protoc-4.36.2-linux-x86_64.exe` 也进了 `verification-metadata.xml`：摘要由下载到的工件实算（SHA-256 `f6ee22d6…`），并先与 Maven Central 公布的 SHA-1 `bb3742d0…` 逐位对上作为出处证明。macOS 仍缺条目——没有人在那个平台上构建过，不凭猜测补。
- [ ] 由上面第一条引出一个**需要单独决定的**问题：`verification-metadata.xml` 里那 50 个 `net_fabricmc_yarn_*` 组件与被 merge 的 Minecraft jar 都是 **Loom 本地产出**，它们被记录了 Windows 摘要，于是这道严格校验门禁**只可能在被生成的那台机器上通过**。它看起来是供应链控制，实际是一把平台锁——CI 没发现是因为 `bridge-static` 根本不跑 Gradle。可选做法是把这类本地工件列入 `<trusted-artifacts>`（前提是它们的输入仍被严格校验），但那是**放宽**一项安全控制，代价是 Windows 那边也失去这层检查，所以不在这一批里顺手做。
- [x] 让下一次能直接重跑（命令已按实测修正）：`docker volume create minekin-gradle`，把 `~/.gradle` 的 `caches/modules-2`、`caches/fabric-loom`、`caches/jars-9`、`wrapper` 用 tar 管进这个卷（**先 `./gradlew --stop`**，否则活锁文件会以「Unexpected lock protocol found in lock file」或读错误的形式破坏拷贝），然后
  `docker run --rm -v <repo>:/src:ro -v minekin-gradle:/gradle -e GRADLE_USER_HOME=/gradle eclipse-temurin:21-jdk-jammy bash -c 'mkdir -p /work && cp -a /src/bridge /work/bridge && cp -a /src/proto /work/proto && cd /work/bridge && ./gradlew --dependency-verification=off build && sha256sum build/libs/minekin-bridge-0.0.0.jar'`。
  三条经验：**不能**把 Windows 的 `~/.gradle` 直接 bind mount 进容器（Gradle 的 file-access journal 在那种挂载上直接 `Input/output error`）；**不能**把宿主已有的 `bridge/build/` 一起拷进去（会拿旧 jar 当成本次产物，得到一个假的"一致"）；**必须**把 `proto/` 按原相对位置一起拷进去，否则 `generateProto` 会是 `NO-SOURCE`。

## W20：只读 Thin Bridge

- [x] 建立 Java 21/Fabric 1.21.4 client entrypoint 与固定 manifest。
- [x] Java gencode 归 Gradle protobuf plugin 在构建期从 `proto/` 生成，不提交生成目录；`bridge/src/generated` 的旧 Buf 产物已移除，避免污染 bundle source digest。
- [x] 实现 control/event 双通道的长度前缀 Protobuf framing。
- [x] 实现 nonce、protocol、generation、bundle 与 capability 握手。
- [x] Bridge 默认 `OBSERVE_ONLY`，握手前无连接和输入能力。
- [x] IPC/编码在后台有界队列运行，Minecraft 对象只在 client thread 访问。
- [x] Core 侧 Windows loopback IPC 主机静态子集：control/event 各绑定独立随机 `127.0.0.1` 端口，以独占创建的一次性 protobuf descriptor 交付 256-bit nonce/key；服务端先按四字节网络序长度上限解帧，再校验 protocol、channel、sequence、session/generation/client identity 和 HMAC，只有双向证明通过才启动心跳及 control/event 收发。事件队列有界且溢出时清空旧观察、显式报错；Windows Proactor 挂起读在关闭时先断 transport，整个收尾有界。错误 proof、超长帧、descriptor 覆盖与不安全参数均有本地 loopback 契约测试。Windows descriptor 的私有 ACL 仍由尚未接线的 session overlay 创建者负责，真实 Bridge 握手尚未以此替代下方实测门禁。
- [x] 门禁（静态子集）：错误 nonce/protocol、未协商 capability 与越界心跳/帧长被拒并 safe-stop，未知 mod 被 bundle recipe 拒绝，握手后仍为 `OBSERVE_ONLY`（无连接、无输入）；由 `BridgeProtocolSelfTest`、`BridgeIpcWorkerSelfTest` 与 `test_unknown_mod_is_rejected` 覆盖，并已接入 CI 的 `bridge-static`。
- [x] Gradle 侧终于有测试：`build.gradle.kts` 一直声明 JUnit 并配置 `useJUnitPlatform()`，但 `:test` 始终是 `NO-SOURCE`，于是「manifest 里写的 entrypoint 类是否真的存在、是否真的实现 `ClientModInitializer`」从来没人验过——而 manifest 指向一个不存在的类是 Fabric 启动失败的经典形态，文本检查抓不到。现在 `BridgeEntrypointTest` 用编译产物验证这条链，并复核 manifest 的固定依赖集与 client-only 环境。它需要 Fabric API 在 classpath 上，但不需要 Minecraft 运行时，因此在依赖已缓存时本机离线可跑；普通 CI 仍不下载 Minecraft 资产，所以不进 CI。
- [ ] 门禁（实测）：真实 1.21.4 客户端内 tick/render 回调预算的 P50/P95/P99 尚未测量；W20 只有“worker 启动不阻塞、队列有界不阻塞”的结构证据，实测随 W30 首次真实启动补齐。

## W30：Offline Session

- [ ] 按 OFF-A（`offline`）→ OFF-B（`legacy`）运行有界候选，不静默漂移。
- [x] 冻结 `token=0`、offline UUID 与 clientId/xuid 显式空 argv 语义：`domain/offline_identity.py` 复刻 `UUID.nameUUIDFromBytes("OfflinePlayer:"+name)`，向量取自 JDK 实际输出；`adapters/launcher/offline_session.py` 冻结 OFF-A/OFF-B 候选，并强制每个空值仍是紧跟自己 option 的独立 argv 元素。
- [x] OFFLINE-001 静态子集：dry-run 无字面 `${...}`；未声明占位符直接拒绝而不是替换成空字符串；空值位置与候选声明不一致即失败。
- [x] 身份根可持久化：`kin_identity` 单行存储 `kin_id`、local profile、identity revision 与 username；缺失时读取直接失败而不隐式新建，第二次 `init` 被拒绝，未知 `uuid_algorithm` 被拒绝。
- [x] `minekin init` 接线完成：数据根来自 `MINEKIN_HOME`、username 来自 `MINEKIN_USERNAME`，两者都**没有默认值**，未设置即 `CONFIG` 失败并点名变量；相对根在 `resolve()` 之前拒绝。目录布局为 `<root>/kin/<kin_id>/{kin.sqlite3, run/}`，`run/` 就是启动计划相对路径所相对的根。`init` 不幂等：数据库已存在即拒绝，且拒绝时不留下任何痕迹。这两项都是**提案**，见[数据根与身份创建提案](run-directory-proposal.md)——契约都没有规定它们，改起来只涉及一个函数与 `init` 的读取点。
- [x] 把冻结的 session argv 与计划里的 JVM 参数组装成完整命令行：计划中的路径按契约是 run-root 相对，只有 `adapters/launcher/process.py` 把它们变成绝对路径，因此"到底指向哪个目录"只有一个答案。classpath 逐项重建而不是重写拼接串；`-cp` 后面若不是类路径就拒绝（否则会把下一个选项当成类路径吞掉）；仍为相对计划路径、或 `.minecraft` 作为路径分段出现的参数一律拒绝。该判别必须按路径分段——`net.minecraft.client.main.Main` 是类名，不是目录，第一版按子串判断会误杀它。
- [x] **发现并修掉了一处契约违规：受管理客户端此前根本不在自己的会话 overlay 里运行。** 启动计划契约写的是 `runtime.game_dir: "<session overlay>"`，`managed-client-runtime.md` 也说"为每次世界会话创建独立 managed run directory/可写 overlay：options、服务器资源包、日志、崩溃报告和会话临时文件"，而 overlay 预建的目录名（`logs`、`crash-reports`、`cache`、`server-resource-packs`、`ipc`）本身就是 Minecraft run directory 的形状。但实现把 `game_dir` 写成 `session/game` 并对 **run root** 解析，于是客户端跑在 `<run_root>/session/game`——一个与该 Kin 的**每一次会话、每一代 generation 共享**的目录，而真正的 overlay 在它旁边。后果不是抽象的：两代之间客户端的 `options.txt`、它自己的 `logs/`、`saves/`、资源包缓存全部互相污染，而"残留进程拦截""generation 隔离"这些说法都建立在"每代一个干净目录"之上；`HOME`/`XDG_*`/`TMPDIR` 的重定向也跟着落在那个共享目录里（`session_redirects` 取的是工作目录的**父目录**）。
- [x] 修法是让计划路径明确命名**两个根**，而不是一个：`artifact-store/` 与 `bundle/` 仍在 run root 下（只读、内容寻址），`session/` 指向本代 generation 的可写 overlay，因此 `session/` 单独出现就是 overlay 本身（契约说的 game_dir），`session/natives` 是它里面的目录。`session_redirects` 也改为以工作目录自身为会话根。顺带发现并修掉一个自己引入的漏洞：`_require_materialised` 这道"不许留下相对路径"的兜底只认 run-root 前缀，`session/` 一旦成为合法前缀，一个残留的 `session/...` 参数就不会再被拦下——它现在检查全部计划路径前缀。
- [x] 固定 mod 集**现在真的会被放到客户端会加载的位置**。契约要求 `artifacts.mods` 带工件与摘要，而计划里原来只有 `fixed_mods` 这两个名字，于是 fabric-api 的 jar 被 recipe 校验过却从未被放到任何地方，Bridge 的 jar 同理——客户端会以原版状态起来，然后握手永远不来（一个看起来像超时、实际是文件没放的失败）。现在计划里的 `fixed_mods` 是完整记录（name/kind/sha256/size/source，取回型 mod 另带 sha1），`adapters/launcher/mods.py` 把每一个按 pin 校验后放进**会话 overlay 的 `mods/`**——overlay 就是客户端的 game directory，所以 Fabric Loader 找得到它们；overlay 预建目录也补上了 `mods`。放置走 staging 名再原子替换，读方不会看到半个文件。拒绝分成四种且各自说清：没构建、大小不符、字节不符、不在 store 里。已做变异验证：去掉 pin 校验，两个用例立刻失败。
- [x] fabric-api 的 SHA-1 成为 recipe 常量：store 按 SHA-1 寻址（上游元数据就是这么发的），而 recipe 钉的是 SHA-256，所以两者都记——pin 是更强的声明，SHA-1 是 store 找到文件的键。值就是 bootstrap 契约与供应链核查工具里已经记过的那个，不是新引入的数字。
- [x] 工件**现在真的能被抓进 store 了**：`adapters/launcher/provision.py` 是那个一直缺的驱动——它从计划里读出工件、算出缺哪些、把缺的交给 `ArtifactFetcher`（后者本身早已完整：已验证的复用、只重试传输错误、一个失败不中断整趟），并汇总成一份可入证据的报告。计划工件的读取逻辑原来只存在于 `cli/session.py` 的私有函数里，现在提到 `launch_plan.artifacts_from_plan` 供两侧共用：同一份形状被两处独立解析，就是两处会各自漂移的地方。
- [x] 但那次抓取**漏掉了 fabric-api**：抓取集来自 `plan["artifacts"]`（Minecraft 元数据那 4,120 个），而 fabric-api 是**固定 mod**、按契约从 game directory 加载而不是走 classpath，因此不在那张表里——于是「抓完整个 bundle」之后 `install_fixed_mods` 仍会以「fabric-api is not in the content-addressed store yet」拒绝，而且看起来像一次缺失的下载。现在 `plan_fetch_set` 把**取回型的固定 mod**也算进工作集，并且这条身份只构造一次（`mods.fetched_mod_artifact`，抓取与放置共用）——两处各构造一次就会漂移，而漂移的 store key 表现为「文件永远找不到」。已做变异验证：把 mod 从工作集里去掉，接缝用例与两条工具用例同时失败。
- [x] 顺带**修正了一个文档里的小数字**：计划自己声明的抓取量是 **523,911,981 bytes（约 500 MiB）**，而不是各处沿用至今的「一个 GB」。工具现在打印的就是这个数（`--dry-run` 可见），预算拒绝也按它算；原来那个「GB」是估算，没人在真实计划上量过。
- [x] 谁来驱动抓取，结论是**操作者工具**而不是产品命令：冻结的 CLI 表面里没有抓取动词；`session start` 的设计原则是"先验证就绪再创建任何东西"，`require_store_complete` 明确选择**拒绝**并让运行者去抓，而不是让启动命令变成一次 GB 级网络操作；`bundle verify` 则有一条测试钉住它是只读的。三个显而易见的落点都被已定的设计挡住，所以它落在 `tools/fetch_bundle.py`，与需要网络、因此不进 CI 的供应链核查工具同类：它按 `session start` 同样的方式解析 data root 与 Kin，把解析出的 store 路径**打印出来**（抓错地方要看得见），并默认先 `--dry-run` 看清单再真抓。
- [x] 预算不是装饰：它**在发出任何请求之前**就按"缺的那部分字节数"拒绝，且只约束"这一趟要抓多少"，不约束"已经有多少"——一个已经填满的 store 无论预算多小都不会被拒。已验证：库层用注入的 opener 断言预算拒绝时 opener 一次都没被调用（变异验证：去掉预算检查，该用例立刻失败）。**一条操作经验值得记下**：绕过预算去跑真实 profile 的测试会真的开始联网抓那 1GB——所以变异验证要在库层做（注入 opener），不要在工具层做。
- [x] 抓取**从「一个一个来」改成「同时来几个」**，因为实测推翻了原来的理由：拿真实 p0-core 计划量过，缺失 3,970 个工件 / 386 MB，**顺序抓取每个工件约 2.9 秒**——将近三小时，而带宽只用到约 35 KB/s，也就是说它一直在等往返而不是等链路；原来那句「工件都很小，有界、可续、易诊断的一趟比并行更值」在为并不紧的那一头辩护。现在并发仍然**有界**（`jobs`，默认 8，是参数而不是循环的性质）：每个工件仍由 store 先校验再发布，blob 名由内容本身决定，因此 worker 之间不争抢同一个路径；失败仍按自己的坐标报出；中断一趟仍靠「已在的不再抓」续上。报告保持**计划顺序**，与哪个 worker 先完成无关；`on_progress` 由**调用线程**在 future 完成时回调，调用者不会从 worker 里打印。工具侧：进度走 stderr，stdout 仍是那唯一一份文档——几千个工件的一趟在完成前**一个字都不打**，那不是能盯着的进度，而这次要跑的正是几十分钟到几小时的一趟。已做变异验证：新循环的四种改法（永远串行、按完成顺序报、只在末尾报一次进度、去掉 jobs 下界检查）各自让对应的用例失败。
- [ ] 由此剩下的就不再是"能不能抓"，而是两个仍然悬着的决定，加上外部环境：**(一)** Core 还没有发出过 `ConnectWorld`（没有对应命令，也没有从 Server Profile 到它的入口），所以即使抓齐、起得来，会话也只会停在 `READY_MENU`；**(二)** 受控 Linux runner（Java 21、Xvfb、原版 1.21.4 server、隔离账号）尚未准备。两者都不是可以在本机顺手补完的。
- [x] **受控 runner 里第一次真的把客户端拉起来了，也因此挖出两个让它根本起不来的缺陷**（只有在 runner 上跑 `session start` 才可能发现：本机没有 store、没有虚拟显示，任何一步都够不着）。
  - **（一）计划把 store 路径重述错了**：`launch_plan` 自己拼 `artifact-store/sha1/...`，而 `ArtifactStore` 实际写的是 `artifact-store/blobs/sha1/...`，于是计划里**每一条** classpath 条目都指向一个从未写出的文件。JVM 对不存在的 classpath 条目是静默忽略的，所以报错完全指向别处：`Could not find or load main class net.fabricmc.loader.impl.launch.knot.KnotClient`。它一直没被发现，是因为**就绪检查与启动各用了自己的答案**——`require_store_complete` 问 store（真布局，通过），classpath 用计划（重述的布局，全错），而没有任何东西比较过两者；测试里的 `session_support.fabricated()` 又照抄了同一个错路径，整套测试于是跟着一起错。修法只留一处定义：`artifacts.store_relative_path()`，`ArtifactStore.path_for` 与 `launch_plan._store_path` 都从它来；新增用例把两侧接上——计划声明的每条路径必须等于 store 自己算出的路径，且 classpath/native_artifacts 必须是这些已声明路径的子集。变异验证：把 `_store_path` 改回重述（去掉 `blobs`），用例立刻失败。（把 store 的 blob 目录整体改名则**不会**失败——那是一次一致的改名，两侧仍然相符，这条用例断言的是「相符」而不是某个字面量。）
  - **（二）Fabric 档案对父库的覆盖从未生效**：Fabric profile 是 `inheritsFrom` 1.21.4 并**重述**它需要的库，两张表因此有交集；计划把两张表直接接起来，于是 classpath 上同时有 ASM 9.6（Minecraft 的）与 ASM 9.7.1（Fabric 的）。Loader 一发现同一个类有两份就拒绝启动：`duplicate ASM classes found on classpath`。现在 `PinnedMetadata.resolved_libraries` 给出**合并且已覆盖**的整套库（profile 的声明替换父级同 group:artifact 的那条，分类符不算身份的一部分），并且是整套而不是父级那一半——把 profile 的表再接上去正是要防的那个错误，现在接不上去。变异验证：取消覆盖、把版本计入覆盖键、把分类符计入覆盖键，三者各自让用例失败。
  两条都指向同一件事：**「就绪检查通过」与「客户端起得来」是两个不同的断言**，只要它们各自去问不同的东西，就都可能为真而不相容。
- [x] **原生库现在真的被解出来了**：计划把 natives 与 classpath 分开命名（`native_artifacts` 是那些 jar、`native_extract_excludes` 是不要拿出来的前缀、`natives_dir` 最终以 `-Djava.library.path=<overlay>/natives` 交给客户端），而**没有任何东西把它们从 jar 里取出来**。在受控 runner 上的表现是一连串离病因很远的症状：Loader 解析完整个 classpath、加载了 54 个 mod（含 Bridge）、把 Minecraft 启动起来，直到渲染线程第一次碰 LWJGL 才报 `UnsatisfiedLinkError: Failed to locate library: liblwjgl.so`——在此之前一切都像一次成功的启动。新增 `adapters/launcher/natives.py`：只打开计划**点名为 native** 的工件（classpath 的 jar 不是 native 容器，全都打开就会把计划里的一处失误变成「客户端会从中加载代码的目录里的文件」）；条目经 staging 名再原子替换；排除前缀跳过；条目名一律要求留在 natives 目录内（jar 按定义是上游输入，条目名里的 `../` 就是从目录里出去的老办法）；两个 native 对同一个库给出不同字节时**拒绝**，而不是让后一个悄悄覆盖；解出来是空的时候在这里拒绝，而不是留给客户端晚得多的时候报——空的 natives 目录正是这一步要防的那个失败。变异验证：把条目名当可信路径、允许重复覆盖、允许空解出、打开所有工件、跳过排除前缀，五者各自让对应用例失败。
  - **一个平台细节值得记**：`zipfile` 在**读**的时候也会把 `os.sep` 换成 `/`，所以在 Windows 上条目名里的反斜杠对读者是不可见的、构造不出这样的 jar 来测；而目标平台是 Linux（`os.sep` 是 `/`，没有东西改写这个名字）。因此反斜杠那条规则直接在它所在的函数上测（`entry_relative_path`），其余名字仍走「真的造一个 jar」的端到端路径。
- [x] spawn 与基本进程监管：直接 `Popen`（`shell=False` + 列表 argv，无 shell 复解析），cwd 为 session game 目录，日志落盘；身份记录为 `(pid, started_at, argv_digest)` 而不只是 PID——PID 会被系统复用，单独用不能跨 run 认人。停止是有界的：先请它退出，到点仍在则 kill，因为它还占着 session overlay、在服务端看来还像一名玩家。同一 supervisor 第二次 start 被拒。
- [x] 客户端环境显式化：不隐式继承宿主环境。`HOME`/XDG/TEMP 一律改指 session 目录（继承了宿主 `HOME` 的客户端仍然够得到运行者的文件，而受管运行目录存在的意义正是挡住这件事），需要宿主提供的东西（虚拟显示要的 `DISPLAY`）必须逐个指名转发，且转发值中出现 `.minecraft` 路径分段即拒绝。改指到的目录必须在启动前存在——实测传给子进程一个不存在的 `TMPDIR` 会让它告警并可能无法建临时文件。
- [x] `session start` **现在真的把宿主显示交给客户端了**。库层一直有这道口子也有测试（`client_environment(..., forward={"DISPLAY": ":99"})`），但产品里**没有一个调用者给它传过值**：`bootstrap` 调 `start_and_supervise` 时 `forward_environment` 始终是默认的 `None`。后果在受控 runner 上很具体——客户端拿不到 `DISPLAY`，窗口根本开不出来，而 runner 存在的意义正是一个虚拟显示上的真实客户端。修法照 `MINEKIN_HOME`/`MINEKIN_USERNAME`/`MINEKIN_JAVA` 已有的样式，在边缘（`bootstrap`）读环境：`config.FORWARDED_VARIABLES` 是**代码里的名单**而不是运行者给的名单——被转发的值按定义是「宿主定的值」，若让运行者来点名字，那唯一一道可审的门就会把 `LD_PRELOAD` 一起放进来；未设置或设为空白的变量就是「没有」，不编造值。已做变异验证：名单里加上 `LD_PRELOAD`、把空白当有值、去掉 `bootstrap` 那行转发，三者各自让对应用例失败。
- [x] 启动前的残留进程拦截：每个会话 generation 在 overlay 里留下 `process.json`（记录 pid / started_at / argv digest），`session start` 在创建任何东西之前先扫这些标记；只要有一个「未解决」就拒绝并把会话、pid 与要删除的标记文件指名报出来。
- [x] 三值活性判定而不是猜：`ALIVE` / `GONE` / `UNKNOWN`。探针只在 POSIX 上可信——实测 Windows 上 `os.kill(pid, 0)` 会把已回收的进程报成仍然存在，所以那里一律答 `UNKNOWN`。`UNKNOWN` 与 `ALIVE` 一样拦启动，因为「大概没了」不是往世界里再放一个玩家的理由。
- [ ] 残留进程的处置策略（接管 / 终止 / 人工阻断）在真实事件流中的接线：本步只做「发现并拒绝」，不做「替运行者决定」。判断一个活着的 pid 是否真属于我们需要的证据（命令行、启动时间）在本机不可移植，所以宁可停下并要求人工确认；在受控 runner 上再决定接管或终止。
- [x] `session stop` 接线完成，并且找到了「凭什么敢杀这个 pid」的答案：运行者**明确要求停止**本身就是授权，仍需挣得的是「对这个 pid 发信号」的资格，而这次是**可证明**的——`/proc/<pid>/cmdline` 报的正是进程被启动时的那串参数，而标记里记的 `argv_digest` 就是把同样的参数用 NUL 连起来做 sha256（`/proc` 是 NUL 分隔并以 NUL 结尾，去掉末尾 NUL 后逐字节相同）。因此判定是三值：`PROVEN` 才终止，`NOT_OURS`（pid 被复用）不碰并报出，`UNVERIFIABLE`（本平台问不了）不碰且**不算完成**，退出码为 `PROCESS`。宁可停下也不猜，因为在这里猜错的代价是杀掉无关进程。
- [x] 由此收紧了上一条的口径：真正被推迟的只是**自动**处置策略（运行者不在场时该接管、终止还是升级），而运行者主动发起的停止路径已经完整，并且只有在能证明身份时才动手。`session` 三个子命令现在都已实现。
- [x] 重启语义固化：同一 `kin_id` 重启后身份根逐字不变（revision、created_at、credential_kind 都一样），但每次 Core 调用是新 run（run_id 不同、sequence 各自从 1 起）、新 session、新 overlay，旧 overlay 原样留在原处；启动前会重新读并重新校验身份根（改坏 `uuid_algorithm` 即拒绝重启）与重新检查工件就绪，没有任何东西从上一次运行被缓存下来。失败的启动不写 marker，所以重试不会被自己的失败挡住——marker 只在进程真的起来之后才写，顺序反了就会把重试锁死。
- [ ] 标记文件不会被自动清理：跑完的 run 留下标记就是它跑过的痕迹，与「失败 run 只追加不覆盖」一致。长期累积的清理策略未定。其 `tests/fixtures/replay/session-preparing.v1.json` 仍**没有消费者**——这是「先提交 fixture 与预期、再提交实现」的顺序，不是死文件，不要删；已核对它的 `payload_hash` 就是自身 payload 的规范 JSON 摘要。crash fixture 现在有消费者了，见下一条。
- [x] crash fixture 的 `expected_recovery` 不再是无人认领的期望：`domain/recovery.py` 把 §8「不是所有副作用都能重试」那张表落成了代码，并**直接以该 fixture 的三条期望为准**——`START_CLIENT` → `RECONCILE`（先问进程身份，别再起一个 JVM）、`INPUT_LEASE` → `INVALIDATE`（lease 本就不持久化，这条只可能是「按过键」的陈旧意图，重放它正是要防的失败）、`CONNECT_WORLD` → `INVALIDATE`（那一代已经结束，重连是新 generation 而不是续上旧的那个）。判据是「重复它是不是同一个请求」：内容寻址的下载与幂等的松键可重试，凡是正确性依附于某个 generation 或某个已持有 lease 的都不能。本版本不认识的 effect 一律 `FAIL_CLOSED`——「我不知道它原本要做什么」的安全读法不是「再做一次」；重试次数也封顶（`MAX_ATTEMPTS`），因为无限重试是一种永远不干净地失败的方式。已做变异验证：把 `INPUT_LEASE` 改成可重试，三个用例同时失败，其中一个是直接读 fixture 的那条。
- [x] 那条策略**现在跑在真实启动路径上了**：`application/recovery_service.py` 读未决 outbox、按策略办事，`session start` 在**创建任何东西之前**调用它（§13 的第 4、5 步）。四种结局里只有两种是动作，这是刻意的：**必须永不重放**的在这里就地关闭（带原因），这样之后任何一次启动都不会再把它捡起来；**可重试**与**需要先看世界**的则原样留着并上报——「记录里的客户端还在不在」属于持有进程身份的启动器，在这里悄悄关掉那条就等于把一个活着的进程从专门用来找它的检查面前藏起来。本版本读不懂的 effect 与已经重试到上限的，直接让这次启动停下而不是猜。拒绝之前先把所有决定都读完，所以一次拒绝不会留下「处理了一半」的账本（有测试钉住这一点）。已做变异验证：把「等待世界」也当成可关闭，那条「活着的客户端必须仍然可见」的用例立刻失败。账本侧新增 `reconcile_outbox`/`reconcile_outbox_async` 一对入口，理由与写事件那对相同：监督中的启动已经在循环里，不能再套一层 `asyncio.run`；这一条接线时正是先踩了这个坑。
- [x] §8 的事务性 outbox 现在**真的被用上了**：`session start` 在**尝试效果之前**先把意图写进账本（一条 outbox 项，`effect_type=START_CLIENT`，幂等键是这次 run 的 `run_id`），效果有结果之后再写成功/失败事件并把它标记完成。这条顺序就是崩溃恢复能成立的全部理由——没被记下来的效果，没有人能对账；上一批那条「对账跑起来只会读到空账本」的说明由此作废。有测试直接钉住这个顺序：假 supervisor 在 spawn 的**那一刻**读账本，断言那里的 `START_CLIENT` 还是 pending（已做变异验证：把意图挪到 spawn 之后，该断言立刻失败）。两个附加决定：失败的一次启动**也算已结清**（它有结果，不该被下一次启动重放），而 `open_effect` 会拒绝 recovery 读不懂的 effect 类型——写一行 recovery 只会拒绝的记录，只会让下一次启动无谓地停下。
- [x] `session start` 接线完成：读数据根与 Kin（根下只有一个 Kin 时无需选择，多于一个必须显式指定，否则拒绝——启动错的 Kin 是后续步骤挽不回来的）、读身份根、构建计划，然后**先验证就绪再创建任何东西**：计划自己说 not launchable 就带着 blocker 拒绝，计划点名的每一个工件都必须已在 store 中校验通过，缺一个就报出第一个缺失项。通过后建 session overlay、组装命令行、交给 supervisor 启动。overlay 的路径由 `session_overlay_path` 计算而非事后发现，所以 supervisor 的日志目录在 overlay 存在之前就能命名。
- [x] 事件记录：契约要求 adapter 拿到结果之后再追加成功/失败事件，`session start` 现在在进程启动后记 `SessionProcessStarted`、在启动失败时记 `SessionProcessFailed` 并照常抛出。记录用的是已经脱敏的 `safe_message` 与错误分类，从不记原始异常正文；`source`/`trust_class` 标为 LAUNCHER，与"这是启动器报告的事实"一致。sequence 按 run 续号而不是从 1 重来，payload 哈希用账本自己的规范 JSON 摘要。启动之前的拒绝（没有 Kin、计划不可启动、工件缺失）不写事件——那是运行者错误而不是一次运行的结果。`sequence`/`generation` 在库里是 TEXT，因为 uint64 放不进 SQLite 的有符号 INTEGER。
- [x] `session status` 接线完成，且是严格只读的：数据库以 query-only 打开、绝不启动 writer 线程，也不隐式建档——「报告」与「创建」分开。它把已有事实合起来报出：会话 overlay、记录在案的客户端进程与其活性、账本的计数与最后一条事件；状态判为 `idle` / `running` / `unresolved`，其中 `unresolved` 与 `start` 的拒绝条件完全一致，命令之间不会互相矛盾。
- [x] 与冻结 CLI 的措辞有一处偏离并已记明：`status` 的 help 写的是「read the current projection」，但目前没有任何 projector 写投影表，照字面读只会读到空。因此它报告的是从真实存在的东西推导出的同一幅图景；等 projector 落地，这里应当改为读投影。
- [x] Bridge 脱敏报告：`SessionIdentityReport` 随 hello 与首快照上报候选、用户名、UUID、AccountType 与 clientId/xuid presence；凭据按结构不可携带——消息没有 `bytes` 字段、观测 record 没有 token/secret/key 分量、`credential_values_exposed` 为 true 时拒绝。形状由已发布的 descriptor 断言，不靠人工复查。
- [x] `SESSION_MATERIAL_MISMATCH` 规则：从**实际 argv** 读回 Launcher 记录的 session 材料（不是从候选重新推导），与 Bridge 上报逐项比较；uuid 按规范化后的身份比较以容纳 id128/canonical，`userType` 与 `AccountType` 分属不同命名空间故只记录不比较，任一不一致都阻断 `PLAYABLE`。
- [ ] 读取真实客户端 Session 回填该报告：需要真实客户端，尚未实现。
- [ ] 执行 `OFFLINE-001…100`，仅在条件满足时运行 UUID/sentinel 对照。
- [ ] 门禁：启动、握手与身份材料可解释，失败分类明确。

## W40：原版服务器准入

- [ ] 启动隔离的 vanilla 1.21.4 `online-mode=false` dedicated server。
- [x] 受控 server runner 已准备：只接受显式 `--accept-eula`，先复核官方 1.21.4 server JAR 的大小与 SHA-1，再写全新的 run 目录；固定 loopback、offline、survival、difficulty、seed、白名单、无 op、无 RCON/query/command-block/console 广播，并按 vanilla 离线 UUID 规则生成白名单。旧 run 目录、非法或仅大小写不同的玩家名均 fail closed；启动未就绪时不会因 `--keep-running` 误报成功，退出始终有界停服。配置与拒绝路径已有离线契约测试，但尚未代替上一条真实启动门禁。
- [x] 静态子集：可信 Server Profile 加载与地址策略——只接受冻结 schema 里的 `127.0.0.1`/`::1` 两个 loopback literal，拒绝 DNS 名、私网、通配、第二条 loopback 与未知字段；profile 内容摘要作为 revision。以 `schemas/server-profile.schema.json` 做逐项对照测试，产品规则只允许比 schema 更严。
- [x] 地址策略判定：解析后的 endpoint 必须再过一次策略，只接受 profile 声明的网络；名称永不解析入位（可重绑定），link-local（含云元数据 `169.254.169.254`）、unspecified 与 multicast 是任何策略都不能放宽的无条件拒绝。profile 加载与判定共用同一份规则，不再各写一遍 loopback 字面量。
- [ ] DNS/SRV 解析本身，以及「每次重连重新解析、不永久信任旧 SRV 结果」的时序：需要真实客户端连接路径。
- [x] connection generation 的纯领域门禁：每次 begin 从 1 单调分配且必须先显式 close 当前 generation；旧 generation 的 DNS/Netty/JOIN/snapshot 回调只返回 `STALE_GENERATION`，关闭后的晚到回调只返回 `CLOSED_GENERATION`，均不改变新状态；未分配的未来 generation 与当前 generation 的乱序回调 fail closed，JOIN 与 authoritative snapshot 缺一不可 `PLAYABLE`。真实 client-thread 事件接线仍随 ConnectWorld 实测完成，不能用此静态状态机代替。
- [x] 冻结 W40 wire schema：`ConnectWorld` 只携带已保存 profile 的 id/revision、原始 host/port、资源包策略、generation 与 deadline；`CancelConnection` 使用枚举原因；`ConnectionLifecycle` 只上报稳定 phase/failure enum，不给服务端任意文本开产品通道。profile binding 属于生命周期管理元数据，world context 由 Envelope 承载，二者都不塞进玩家等价 `InitialObservation`；Python gencode、`.pyi` 与 Java lite 编译检查已同步。
- [x] Bridge command ingress 与 client-thread 适配静态子集：IPC worker 只在握手协商 `admission.connect.v1` 后解析 `ConnectWorld`/`CancelConnection`，再次限制 loopback、profile revision、deadline、资源包策略与单调 connection generation，再以非阻塞有界 inbox 交给 client tick；client tick 使用固定 1.21.4 的公开 `ConnectScreen.connect`、`ServerAddress`、`ServerInfo(OTHER)`、`quickPlay=false` 与空 cookie storage，资源包只映射 deny/prompt。取消先失效 generation，再经 required Mixin accessor 精确执行 vanilla Cancel 按钮所用的 future/connection 路径，无反射；队列满、能力缺失、重放/跳号、非法目标或 tick 适配异常均 safe-stop。真实 JOIN/DISCONNECT 回调的 generation 绑定与生命周期上报尚未接入。
- [x] 生命周期上报的**出站路径**已接通并实测：`BridgeIpcWorker` 增加一条独立的事件写线程，`publishLifecycle` 从 client tick 非阻塞投递进有界 outbox，队列满即 fail-closed——这是「必须送达」的状态事件，丢掉一条就等于让 Core 永远等一个不会来的相位。只有相位与失败原因自洽的事件才准出去：终止相位必须自称 `terminal`，`FAILED` 必须带具体原因，`CANCELLED` 只能带 `CANCELLED` 或不带原因，其余相位一律不得携带失败原因。Core 用「相位 + 原因」共同分类，放行一个不属于该相位的原因就等于让它把取消读成白名单拒绝。`BridgeIpcWorkerSelfTest` 现在真的从 event channel 读回事件，断言 channel、message type、**从 1 起逐条递增的 sequence** 并逐条比对 payload，被拒的形态一条都不许占用 outbox；已做变异验证：把事件写进 control channel 测试即失败。同一提交修好了 `tools/check_bridge_proto_java.py` 里那份手写 stub——它与真实 `ClientAdmissionController` 的构造签名是各自演化的，构造函数一改，离线编译门禁立刻红（这次就是这样红的）。
- [ ] 仍未接入的是**真实 JOIN/DISCONNECT 回调**：目前只有 `RESOLVING`（发起连接时）与 `CANCELLED`（取消时）两种相位由 `ClientAdmissionController` 上报，`LOGIN_NEGOTIATING`/`PLAY_INIT`/`JOIN_SEEN`/`PLAYABLE`/`DISCONNECTED`/`FAILED` 需要 Fabric 客户端事件回调用当前 generation 绑定后回填；在那之前 `PLAYABLE` 仍只能由 Core 侧推断，Bridge 也不会自己报告一次意外断线。
- [x] Core 侧终于有人读这些事件了：`adapters/bridge/admission.py` 是唯一读 wire 相位枚举的地方，把「客户端说自己到了 X」翻成「这次尝试前进到 Y」，并交由 `ConnectionGenerations` 做 generation 门禁。三条绑定在这里落地——**报告自己的 generation**（不是当前活跃的那个：晚到的旧 generation 报告是正常的，把它当当前读，正是让一个陈旧 Bridge 进程把新连接读成 PLAYABLE 的方法；这条在写测试时立刻抓到了一个真实 bug）、**profile 绑定**（名字与 revision 都要与当前尝试一致，否则是别人的连接）、**相位与原因自洽**（Core 按「相位 + 原因」分类，对不上的报告等于不可分类，拒绝而不是修补）。无法归类的报告返回稳定 token（`UNKNOWN_PHASE`/`MISPAIRED_REASON`/`FOREIGN_PROFILE`/`UNBOUND`/`INVALID_GENERATION`），`FAILED` 的原因按 proto 枚举名作为分类 token 带出来——服务端文本本来就没有通道，这个枚举名就是契约里的稳定分类。
- [x] 由此补上了领域状态机里一个真实的洞：Bridge 现在会发一个**终止、不带原因**的 `DISCONNECTED`，而 `ConnectionState` 里根本没有能表示「连上了又正常结束」的状态，`apply(FAILURE)` 在 PLAYABLE 上还会被判为乱序。于是加了 `DISCONNECTED` 状态与信号（只允许从 `PLAY_INIT`/`JOIN_SEEN`/`PLAYABLE` 进入：PLAY_INIT 之前断掉的 socket 是一次**带原因**的登录失败，不是这个），并把「终止态」抽成一处常量：终止态不再被后续矛盾报告改写成 `FAILED`——把一次已观测到的断开改写成失败，等于往证据里塞一个没人发过的原因码。
- [x] 连接相位现在能推动**会话**状态机了：§7 那张冻结表一直是座孤岛（`SessionState` 除自身模块与测试外没有任何使用方），而 W40 报上来的相位无处安放。`domain/session_state.py` 新增 `advance_for_connection`：把一次连接决策翻成会话该去的状态，**合法性完全由那张冻结表裁决**——`READY_MENU` 只能进 `CONNECTING`，所以一个跳过 CONNECTING 直接报 JOIN 的相位会被拒（`IllegalSessionTransition`），而不是被快进到 `JOINED_UNVERIFIED`。四个准入前相位（REQUEST_ACCEPTED/RESOLVING/LOGIN_NEGOTIATING/PLAY_INIT）对会话是同一件事，因此第二个相位是 no-op 而不是一次自跳转（自跳转在冻结表里也是非法的）。只有 `ADVANCED`/`FAILED`/`OUT_OF_ORDER`/`FUTURE_GENERATION` 这四类决策代表当前这次尝试：`STALE_GENERATION` 与 `CLOSED_GENERATION` 是重连留下的东西，正是 generation 门禁存在的理由，绝不允许它们移动会话。契约用例现在断言整条链——字节从 loopback event channel 出来，经 `apply_lifecycle`，再经 `advance_for_connection`，得到 `CONNECTING → CONNECTING → CONNECTING → JOINED_UNVERIFIED → PLAYABLE → READY_MENU`。已做变异验证：把 `DISCONNECTED` 映射到别的信号、或改掉它对会话的落点，单元与契约用例都失败。
- [x] 失败与终止也接线了：连接侧 fail-closed（`FAILED`）与「当前 generation 收到不可能顺序的报告」（`OUT_OF_ORDER`）都会把会话推进到 `FAILED`；而 PLAYABLE 之后的一次正常断开走 `DISCONNECTED` → `READY_MENU`。连接侧那条「终止态不被后续矛盾报告改写」的规则在这里得到报偿：`FAILURE` 在 PLAYABLE 上被判乱序、状态不变，于是会话也不会莫名其妙变成 `FAILED`。
- [x] ~~这条链仍然没有运行时调用方~~ **已接线**（59d60d3 / 8211c71）：`session start` 建 host、写 descriptor、在有界窗口内等待握手，并用 §10 的任务树陪着会话直到客户端离开；今天的调用方是契约测试与真实命令两条路径。
- [x] 一次性 descriptor 里该装什么，现在有唯一答案：`adapters/bridge/bootstrap.py` 从**已评审的 launch plan** 推导 `kin_id`/`session_id`/`generation`/`client_instance_id` 与两条摘要，并生成 32 字节 nonce 与 session key。`bundle_digest` 取 `plan_sha256`——它是"这次启动出自哪份已评审计划"的唯一值，也正是 Core 拿去和 Bridge 回显值比对的东西。`bridge_digest` 取 `bridge_source_sha256`（Bridge **源码树**摘要）而**不是** JAR 摘要，并在代码与本文里都写明：JAR 摘要要等 Loom 输出在第二个平台上被证明可复现之后才能写进 recipe（见上文 W10 两条尚未完成的项），所以现在能诚实记录的就是源码摘要——它绑定的是"Core 与客户端来自同一份源码"，不是关于发布字节的主张。descriptor 路径由 overlay 算出而不是由调用方指定（它装着 session key，必须落在本次会话自己的目录里），并有测试拒绝相对路径。
- [x] 名字一侧也不再有第二个真值：`MINEKIN_BRIDGE_DESCRIPTOR` 只由 `adapters/launcher/process.py` 定义一次，并**不允许经 `forward_environment` 传入**——转发列表装的是"运行者主机必须提供的事实"，而 descriptor 是 Core 为本次会话创建的，一个由主机提供的同名值会把 Bridge 指向运行者控制的文件。写这条测试时立刻抓到了这个洞：原来的实现只在转发名与会话重定向名冲突时才拒绝，所以不带 descriptor 启动时，主机可以通过转发列表把 `MINEKIN_BRIDGE_DESCRIPTOR` 塞进去。
- [x] 顺带补上了 Python↔Java 那条**没有任何东西在盯**的接缝：两边的 message type 字符串与那个环境变量名都是各自硬编码的，而现有的两道 Java 门禁都看不见它——离线检查用 stub 编译，loopback 契约测试本身就是 Python 侧。所以只有真客户端才能发现的改名，现在由 `tests/contract/test_bridge_java_constants.py` 读两侧源码比对（已做变异验证：把 Java 的 `CONNECTION_LIFECYCLE_TYPE` 改一个字母，测试即失败）。它只校验**拼写**，不校验行为——它说不出 Bridge 是否真的处理了那条消息。
- [x] §10 的任务树有了第一个可运行版本：`cli/session_runtime.py` 的有界握手等待 + 事件读取 + 收尾。它放在组合根而不是 `application/`，理由是它必须同时点名具体 transport、两台具体状态机与具体 supervisor，而 §2 本来就把 entrypoints 定为唯一允许知道这三者的层；改成 port 形状只会多出一个只有一种实现的 `Any` 接缝。收尾按 §13 的次序取其中已存在的部分：**先让 generation 失效，再关 transport**，这样从已关连接晚到的报告无法推动一个正在停止的会话（已做变异验证：去掉失效这一步，两个用例立刻失败）。握手失败与「Bridge 丢了」分开计：前者是 `HANDSHAKE_TIMEOUT`/`HANDSHAKE_FAILED`，后者是 `BRIDGE_LOST`，且**只**把 transport 契约错误算作后者——其它异常是本进程的 bug，必须冒泡成 INTERNAL_INVARIANT，不能被折进一个网络结论里。
- [x] 写这些用例时确认了一条本就该成立、但此前没被任何东西断言的规则：报 JOIN 而不报中间的登录相位**不会**前进。连接状态机只允许 `PLAY_INIT → JOIN_SEEN`，所以跳过 `LOGIN_NEGOTIATING`/`PLAY_INIT` 直接报 JOIN 会把这次尝试判为乱序并 fail-closed（`test_a_join_that_skips_the_login_phases_fails_the_attempt_closed`）。我最初的用例就是跳着报的，于是被自己的机制就地抓住——这条现在是文档化的断言，而不是我记住的巧合。
- [x] 会话状态机的收尾也确认了一次 §7 表的形状：**menu 里丢掉 Bridge 不算失败**。`READY_MENU` 在冻结表里没有通向 `FAILED` 的出口，因为"客户端停在主菜单、控制通道断了"是要停止的会话，不是坏掉的会话；而在连接内部丢掉 Bridge 就是失败，表也是这么给的。`_wind_down` 只用 `can_advance` 依次尝试 `FAILED`(可选) → `STOPPING` → `STOPPED`，没有自己的一套转移表。
- [x] `session start` 现在真的会托管会话了。顺序是「就绪检查 → 建 overlay → 独占写出 descriptor → 启动客户端 → 有界等待握手 → 跟着 Bridge 直到客户端离开」，其中 descriptor **必须先于 spawn 存在**：客户端在自己的启动过程中读它，读不到就根本起不来。这条顺序不是靠约定，`tests/unit/test_session_supervision.py` 让假 supervisor 在 spawn 的瞬间记下「文件在不在」（已做变异验证：把 prepare 挪到 spawn 之后，用例立刻失败）。假客户端也从**文件**里读回 descriptor 再握手，与真 Bridge 的路径一致，因此用例同时断言了 descriptor 携带的 `bundle_digest` 就是这次启动那份 plan 的摘要——绑错了就是"证明了一次并没有发生的启动"。
- [x] 接线时撞上一个真的冲突：ledger 的写入是 `asyncio.run(...)`（每次写自建一个 writer），而它现在被一个**正在运行的**事件循环调用，直接 `RuntimeError: asyncio.run() cannot be called from a running event loop`。当时先把它推到线程里（`asyncio.to_thread`）绕开，**根因已在下一批修掉**：`SessionEventLog` 现在每个事件都有异步入口（`*_async`），同步入口只是它的 `asyncio.run` 薄壳，`launch_prepared` 同样拆成同步壳 + `launch_prepared_async`，`start_and_supervise` 直接 await 异步版本——于是既没有嵌套的 `asyncio.run`，也不再需要那个线程。
- [x] 会话运行时现在**真的把观察到的事实写进账本**了，因为 §7 要求「状态转换由 application service 决定并**持久记录**」，而在此之前它只改状态、不留痕。写入的是 §5 点名的四个事实：`BridgeHelloAccepted`（握手证明通过）、`JoinObserved`、`PlayableEstablished`、`SessionInterrupted`、以及 `ClientProcessExited`；事件名是 `session_log.py` 里的**闭集**，写错一个名字会在写入时就被拒，而不是等到有人查一个永远不存在的事件类型。来源与信任等级按 §6 分类：**Core 自己得出的结论**（握手被验证通过、进程消失、Bridge 丢失）记 `CORE`/`CORE`，**Bridge 报上来的相位**记 `BRIDGE`/`BRIDGE_FILTERED`；两个字段在 `record_session_event` 上是必填而不是默认值，因为 §6 明说信任等级不能由输入正文自报，每个调用点都必须表态。已做变异验证：把握手的来源改成 `BRIDGE`，用例立刻失败。
- [x] 运行时**不**决定事实怎么落账：`supervise_session` 只通过 `on_handshake()` 与 `on_connection(state)` 报告「这次运行观察到了什么」，事件名、来源与信任等级都在组合根里映射。这也意味着运行时会报告**每一个**前进到的相位（含 RESOLVING/LOGIN_NEGOTIATING/PLAY_INIT 这类只是过程的），由调用方决定哪些值得记——契约用例断言了这一点。
- [ ] 但 **`JoinObserved`/`PlayableEstablished` 目前还到不了账本**：`start_and_supervise` 传的是空的 `ConnectionGenerations()`，因为 Core 还没有发出过 `ConnectWorld`（没有 Server Profile 选择，也没有对应命令），于是每条相位报告都被判 `UNBOUND`。所以今天真实路径能记下的是 `SessionProcessStarted`、`BridgeHelloAccepted`、`ClientProcessExited` 与失败时的 `SessionInterrupted`；连接类事实的接线已在运行时层用回调验证过，但要等 Core 会发 `ConnectWorld` 之后才会在真实会话里出现。
- [x] 由此 `session start` 的语义变了，并且必须写下来：它**不再启动完就返回**，而是留在会话里直到客户端退出（这正是"Core 是一个长期进程、客户端才有 Bridge 对端"的必然结果——Core 一退出 socket 就断，Bridge 会按 control lost 自保）。退出码按结局给：客户端离开是 `OK`，握手失败/Bridge 丢失是 `IPC_PROTOCOL`，握手超时是 `TIMEOUT`。**尚未接线的是信号**：Ctrl-C 只让本进程收摊（关 transport、generation 失效），不会去停客户端；停客户端仍然只有 `session stop` 那条已实现且要证明进程身份的路。
- [x] 测试助手不再靠"pytest 恰好把两个目录都塞进 sys.path"来互相 import：`session_support.py` 与 `bridge_peer.py` 移到 `tests/` 下，并由 `tests/conftest.py` 显式把这个目录放进 `sys.path`，`unit/` 与 `contract/` 现在可以各自引用同一份定义。
- [ ] **仍未接入的是真实客户端**：目前没有真 1.21.4 客户端跑过这条路径，所以「Bridge 真的读到了 descriptor」「descriptor 的端口真的能连上」仍然只有离线证据。`ADMIT-001…120` 与 W50/W60 的实测项都还压在这上面；`MINEKIN_BRIDGE_DESCRIPTOR` 现在已经会传给客户端，因此第一次真实启动应当能走到握手，而握手能不能过正是第一个要看的信号。
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
- [x] 输入仲裁（Core 侧）：唯一 input owner、lease、deadline、priority 与前置状态检查全部落在 `domain/input_control.py`。取值方式来自冻结的 proto 而不是自创：优先级用 `INPUT_PRIORITY_NORMAL/URGENT/EMERGENCY` 的排序，lease 字段与 `InputLease` 一致，能力名沿用 `control.<skill>.v1` 约定（`control.move.v1`/`control.look.v1`）。规则：一次只允许一个 lease；同级或更低优先级不得抢走输入（EMERGENCY 可以抢占，这是反射路径需要的）；lease 在 deadline 处失效；引用已被替换 lease 的迟到动作一律只判为 `LEASE_SUPERSEDED` 而不执行；能力未被 lease 覆盖、动作自身 deadline 已过、或不在 PLAYABLE，都拒。所有拒绝原因一并收集，一次就说清全部原因。
- [x] Core 侧 watchdog（双 watchdog 的第二层）：`domain/control_watchdog.py` 在会话进入 PLAYABLE 时**先武装、再等心跳**——启动途中就死掉的 Bridge 一个心跳都不会发，等收到才开始的看门狗永远不会发现它。超时阈值由协商的 `heartbeat_interval_ms` 推出（容忍若干个间隔，因为漏一个间隔是普通调度抖动），并且：**旧 generation 的心跳既不计数也不续期**（否则一条已关闭连接的数据包会让新连接显得还活着），乱序到达的旧时间戳同样不算新信息。与 `InputArbiter` 的合成为「静默 → 判超时 → withdraw(TIMEOUT) → 无 lease → 拒绝一切输入」，这条链路有测试覆盖。
- [ ] Bridge 侧 watchdog（真正保证松键的第一层）与其本地按键释放：需要真实客户端；契约明确它是最终保障，Core 这层只是第二层。
- [x] 松键的**判定**（Core 侧）：八种失效原因（显式、IPC 断、客户端死亡、GUI 冲突、超时、generation 改变、离开 PLAYABLE、被抢占）走同一条 `withdraw`，结果都是「没有任何 lease 留下」，因此都意味着松全部按键；重复 withdraw 无害，在本来就没有 lease 时 withdraw 依然报出「需要松键」——Bridge 必须照做，而不是因为 Core 以为自己没持有就跳过。有一条测试遍历全部八种原因逐一验证这一不变量。
- [ ] 松键的**执行**（Bridge 侧）与 `look`/短时 `move` 的实际施加：需要真实客户端，Bridge 的本地 watchdog 才是最终保障。
- [ ] 门禁：服务端离线核验真实位移；不得瞬移、直接写状态或残留按键。

## W70：恢复与证据晋级

- [ ] 注入 Core、Bridge/client、server 与连接阶段故障。
- [ ] 对账未决 outbox，失效历史 generation/lease，防止危险动作重放。
- [ ] 验证重复启动、同一 `kin_id` 重启与瞬时世界状态重验。
- [x] 不可变 evidence bundle 的封存与校验：manifest 与冻结形状一致，工件按 sha256 记账，bundle 摘要覆盖 manifest 字节；同一目录绝不覆盖旧 run（改正是新 run，不是编辑）；工件或 manifest 含凭据正文即整体拒封——不做就地脱敏，静默改写的日志比缺失的日志更糟；校验端重新对账摘要并检出缺失、篡改与未声明文件。工件名走白名单而非黑名单：Windows 上 `/x` 既非绝对路径、拼接又会替换 bundle 根。
- [x] 报告诚实性规则：缺 expected/observed 对照时结果不得是 `PASS`（只能 `INCOMPLETE`），`PASS` 不得带 failures，`FAIL` 必须有 reason code，只有先后无法在时钟误差窗口内判定时才用 `AMBIGUOUS`。
- [x] candidate→tested 晋级检查：case manifest 按冻结 schema 校验（含 `mandatory` 必须是布尔——真值字符串会把用例悄悄移出晋级门禁；`assertions` 不得为空），`case_version` 用用例定义自身的摘要，因此改过用例就必须产生新 run；只有 mandatory 用例全部拿到「已校验且结果为 `PASS` 且版本一致」的证据才可晋级，缺证据/未校验/非 PASS/版本不符分别给出稳定原因码；非 mandatory 用例不拦晋级。
- [x] case 声明的断言必须有实现：case manifest 里的断言名一直是自由字符串，晋级机制又照单全收 bundle 里记的东西，于是「用例点名了一个没有任何东西实现的断言」或「实现被改名」都不会被发现。现在 `tools/check_case_assertions.py` 维护一张名字→实现位置的登记表（实现分 `tool` 与 `pytest` 两种），既拒绝用例点名未登记的名字，也核对每个登记目标确实存在（pytest 那条还会确认函数名仍在文件里），改名即失败。它只校验**声明**而不运行检查——运行是 orchestrator 的事，属于需要真实客户端的运行时用例。已接入 CI 的 python job。
- [ ] 还未接线的是让 case 真正跑出 bundle：现有 evidence bundle 的字段形状（minecraft/loader/world/identity/server 摘要）是为**运行时**用例设计的，而 `W00-CONTRACT-001` 这类仓库自检用例根本没有启动，套用那个形状就得编造 launcher 摘要。因此没有为它伪造 bundle，而是把「断言有实现」这一步先做实。
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
