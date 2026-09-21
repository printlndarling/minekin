# Kin 自建世界参数、线程与同 JVM 真值边界契约

核查时间：2026-09-17。本文继续收敛 `HOST_INTEGRATED_LAN`：Kin 提出创建世界后，哪些参数可以由它决定，哪些必须由管理策略约束；client thread、integrated-server thread 与 IPC thread 如何交接；以及薄 Bridge 与 integrated server 同 JVM 时如何阻止服务端真值旁路进入 PlayerMind。

本文依据 Minecraft Java 1.21.4 Yarn 公开接口制定静态设计，不表示世界创建、线程顺序、字节码门禁或真值泄漏测试已经运行。

## 本轮决定

1. P0-host 使用结构化 `WorldCreationProposal -> EffectiveWorldCreationProfile -> LoaderArguments`，不让 LLM 直接构造 Minecraft 对象，也不自动点击创建世界 UI。
2. P0-host 首个可测试创建档固定为原版生存、非极限、普通难度、默认世界预设、生成结构、无奖励箱、无命令权限、原版默认游戏规则与随机 seed。
3. Kin 可以自主决定“是否创建、何时创建、世界显示名及生活目标”；改变难度、极限模式、世界预设、数据包、游戏规则或显式 seed 在对应组合完成独立验证前不能悄悄进入首个 P0 档。
4. 创建参数采用明确优先级：不可突破的安全/兼容约束 > 运行者的 Hosted World Policy > Kin 的提案 > 固定 vanilla baseline。玩家聊天和网页只可成为 Kin 的可疑建议，不能直接改管理策略。
5. 创建/加载入口在 client thread 调用；服务端保存、LAN 与需触达 server state 的生命周期命令通过 integrated-server executor 排队。任何线程不得互相循环同步等待。
6. `MinecraftClient.getServer()`是明确的高风险旁路：普通观察、反射、导航和 PlayerMind 数据路径禁止引用它或任何 `ServerWorld`/`ServerPlayerEntity`/服务端存储对象。
7. 仅 `host-control`适配器允许触达极小的 integrated-server 生命周期 API，并只能输出管理事件；它不是感知提供者。
8. 同 JVM 无法提供进程级隔离保证。P0 依靠模块边界、依赖/字节码扫描、mixin target allowlist、运行时 canary 与数据流回放取证；未通过测试只能称 candidate。

## 上游接口事实

| 1.21.4 接口 | 支持的设计判断 | 不足以证明 |
| --- | --- | --- |
| `WorldCreator`带 `@Environment(CLIENT)`，公开管理名字、模式、难度、cheats、seed、结构、奖励箱、世界类型和 GameRules | 原版创建界面本身把这些视为独立创建维度，可作为 Minekin schema 对照 | UI helper适合无窗口生产调用，或其默认组合已被 Minekin复刻正确 |
| `LevelInfo(name, gameMode, hardcore, difficulty, allowCommands, gameRules, dataConfiguration)` | 创建世界的玩法/规则元数据有明确不可变输入 | 任意自定义 GameRules/datapack组合都兼容纯原版 P0 |
| `GeneratorOptions(seed, generateStructures, bonusChest)`及 `createRandom/parseSeed/with...` | seed、结构和奖励箱可明确生成并记录 | seed 能进入人物感知，或随机 seed在所有重启路径一致 |
| `WorldPresets.DEFAULT/FLAT/LARGE_BIOMES/AMPLIFIED/...`与 registry-based dimension options | 默认预设可以用注册表解析；世界类型不是随便一个字符串 | 任意预设、单一生物群系、实验设置已验证 |
| `IntegratedServerLoader.createAndStart(...)` | 有正式 loader入口接收 LevelInfo、GeneratorOptions 和 dimensions supplier | 调用线程、异步失败、包警告与本地 JOIN顺序已跑通 |
| `ThreadExecutor.isOnThread/submit(...)`由 client/server executor继承 | 可在 adapter中声明线程归属、异步排队和完成回调 | 任意 Minecraft方法跨线程都安全，或 future完成等于游戏状态生效 |
| `MinecraftClient.getServer()`返回本客户端的 `IntegratedServer` | 同 JVM Bridge确实存在直达服务端对象的能力，必须显式封禁 | `client-only`元数据天然阻止服务端真值读取 |
| `MinecraftServer.getWorld/getWorlds/getPlayerManager/getSavePath`等 | 一旦取得 server引用，就能访问普通玩家不应知道的真值 | Minekin已经发生泄漏；这是必须测试的能力面 |
| `IntegratedServer.saveAll/openToLan/stop` | 生命周期适配器有保存、LAN和停止候选；`stop(true)`不能从 server thread调用 | 最终参数、超时和关闭顺序已验证 |

## 三层创建参数

### 1. Kin 提案

PlayerMind只能提交意图，不提交任意 Java/NBT/datapack对象：

```yaml
world_creation_proposal:
  proposal_id: "<uuid>"
  kin_id: "<kin>"
  reason: "想拥有自己的长期世界"
  display_name: "<player-facing name>"
  desired_style: "ordinary_survival"
  preferences:
    difficulty: "normal"
    seed_mode: "random"
  evidence_refs:
    - "<goal/persona/event>"
```

`reason`和偏好保留人格出处，但都不是权限。提案来自网页资料、聊天或外部工具时仍按不可信内容处理。

### 2. 有效创建档

Gateway根据固定 bundle和管理策略生成不可变、可摘要的 effective profile：

```yaml
effective_world_creation_profile:
  schema: "minekin.world-create.v1"
  proposal_id: "<uuid>"
  bundle_id: "<immutable 1.21.4 p0-core>"
  storage_slot: "<system generated>"
  level:
    game_mode: "survival"
    hardcore: false
    difficulty: "normal"
    allow_commands: false
    game_rules_profile: "vanilla-default-1.21.4"
    data_configuration: "vanilla-stable-1.21.4"
  generator:
    preset: "minecraft:normal"
    seed_mode: "random"
    seed_secret_ref: null
    generate_structures: true
    bonus_chest: false
  provenance:
    kin_proposal_digest: "<sha256>"
    host_policy_revision: "<id>"
    baseline_revision: "<id>"
  effective_digest: "<sha256 of canonical form>"
```

显示名和 `storage_slot`分离。显式 seed只以 secret/reference进入管理面，除非 Kin亲自选择或其他玩家把 seed告诉它，否则不得自动进入世界书、记忆或导航。

（2026-09-22 补两件在做这一层时量出来的事，都是**两条各自成立的规矩合到一起就不成立**那一类：

**一是 `storage_slot` 必须真的是一个 level 名。** 槽会变成 `saves/` 下的一个目录，而启动器拒绝含分隔符、NUL、盘符冒号的名字——但 `OpaqueId` **允许冒号**（它刻意与路径无关）。于是 `kin:01` 这个**完全合法**的 Kin 会得到一个启动器不接受的世界名，而且要到运行中途才被发现。现在槽由 **percent-encoding** 生成：任何标识符都能得到一个可用的名字，而且这个映射是**单射**的（`kin:01` 与 `kin%3A01` 都是合法 id，用"替换成安全字符"的写法会让两者撞进同一个槽——**两个 Kin 共用一个世界比一个不好看的目录糟得多**）。用例拿**启动器自己的谓词**去验每一个槽，不是抄一份规则过来。

**二是这个字段不能由提案自己声明。** 提案是不可信内容（聊天与网页都能提一份上来），而槽正是从这个字段建的。所以 `parse_proposal` 必须拿到**提交这份提案的那个 Kin**（网关知道、文档不知道），并在两者不一致时以 `KIN_MISMATCH` 拒绝——否则一个 Kin 可以指名为另一个 Kin 建世界，而整条链上没有任何东西会注意到。

### 3. Loader 参数

Bridge host adapter只接受已签名/摘要匹配的 effective profile，并在 client thread把 allowlisted值转换为：

- `LevelInfo`；
- `GeneratorOptions`；
- 从同 bundle动态注册表解析出的默认 `DimensionOptionsRegistryHolder` supplier；
- 系统生成的 level directory name；
- 与当前 session/generation绑定的取消/失败回调。

禁止把 `CreateWorldScreen`或鼠标宏作为生产依赖；`WorldCreator`只用于核对 vanilla语义和原型差异。禁止反射调用 `CreateWorldScreen.createLevelInfo/startServer`等私有方法。默认预设必须按 registry key解析，不靠本地化 UI文字。

## P0 创建参数政策

| 参数 | P0-host | 理由与后续 |
| --- | --- | --- |
| Game mode | Survival固定 | 当前项目只承诺原版生存；creative/spectator不是人物自主发展基线 |
| Hardcore | `false` | 极限死亡改变长期身份/世界可继续性，须单独设计而非顺手打开 |
| Difficulty | Normal固定 | 首个证据档减少组合爆炸；未来可让 Kin在允许范围内选择 |
| Commands/cheats | `false` | 不能由 Kin、聊天或网页提升 |
| Game rules | 1.21.4 vanilla defaults | 自定义规则逐项成为新测试组合；不暗改 keepInventory等 |
| Data configuration | stable vanilla only | datapack/experimental/customized后置，失败不自动 safe-mode丢内容 |
| World preset | `WorldPresets.DEFAULT` | Flat/amplified/large-biomes等分别验证后再开放 |
| Structures | `true` | 正常原版进度需要；与默认预设共同取证 |
| Bonus chest | `false` | 保持普通出生资源条件 |
| Seed | 随机 | 避免运行者无意把后台 seed变成人物全知；显式 seed future/管理开关 |

固定 P0 不是永久剥夺 Kin 自主性，而是先证明一套身体和世界生命周期真的可靠。以后开放参数时，Kin作出决定，Policy检查组合是否 tested；未测试组合只能解释性拒绝或进入专门实验，不能静默回退成另一种世界。

## 线程与异步所有权

### 线程角色

| 线程/执行器 | 可以做 | 禁止做 |
| --- | --- | --- |
| Runtime/IPC worker | schema、摘要、权限、generation校验；发送命令/接事件 | 直接持有 Minecraft对象或等待游戏线程无限完成 |
| Client thread | loader创建/加载、客户端 world/session切换、合法 client观察和输入 | 遍历 integrated server世界；阻塞等待 server thread同时回调 client |
| Integrated-server thread | `saveAll`、LAN/停止等经过 host-control批准的生命周期操作 | 产生 PlayerMind观察；`stop(true)`等待自己；同步等待 client thread |
| Media thread/process | 捕获已授权画面供 Dashboard | 取得 host-control或动作权限，回流默认 VLM |

### 命令封装

所有 host命令包含：

```text
command_id, kin_id, hosted_world_id, world_epoch,
session_id, generation, expected_state, profile_digest,
deadline, idempotency_class, management_capability
```

`CreateWorld`和`LoadWorld`为 client-thread命令；`OpenLan`、`SaveCheckpoint`和 server-side stop阶段由 host-control提交到 server executor。回调只返回到管理状态机，再由允许的状态摘要更新 Dashboard；不得把 server对象或任意序列化 NBT放进 IPC。

每次异步完成都重验 `session_id + generation + world_epoch + expected_state`。过期 callback只记录 `STALE_COMPLETION`，不能改变新会话或重复建档。

### 无环等待规则

1. IPC worker不持锁等待 client/server future；通过事件状态机推进。
2. Client thread提交 server任务后立即返回，不 `join/get`等待。
3. Server thread完成后把纯管理 DTO排到 client/IPC侧，不反向等待。
4. `stop(true)`只允许由确认不在 server thread的监督路径调用；server thread内只能 non-waiting stop信号。
5. 超时意味着结果未知，不自动重发 create/save/open-LAN等非安全幂等动作；先对账。

静态 Javadoc不能冻结完整 callback顺序。原型必须记录实际 thread name/id、`isOnThread`结果、命令/future时间线和 world state transition。

## 同 JVM 的服务端真值隔离

### 模块边界

P0 Bridge拆为：

```text
bridge-wire              纯 DTO/schema，无 Minecraft server 类型
bridge-client-core       ClientWorld/ClientPlayer/NetworkHandler、输入与反射
bridge-host-control      创建/加载/保存/LAN/关闭的窄生命周期 adapter
bridge-test-probes       仅测试构建；生产 bundle不存在
```

`bridge-client-core`及任何观察/导航模块禁止依赖：

- `MinecraftClient.getServer()`；
- `net.minecraft.server..`；
- `IntegratedServer`、`ServerWorld`、`ServerPlayerEntity`、`PlayerManager`；
- `LevelStorage`/save path/NBT/region文件读取；
- 反射、MethodHandles、Unsafe或动态脚本绕过以上规则。

`bridge-host-control`可以引用 loader、storage session和极少的 server lifecycle方法，但不能引用 server world/entity/chunk/inventory/player-manager查询。（2026-09-21：这个包**已存在**——`org.minekin.bridge.host` 里的 `IntegratedServerControl` 目前只做一件事，把客户端正在跑的世界开出去，并回答它在哪个端口上；`LanPublication` 承载那条规则：客户端日志与 `getServerPort()` 报告的都是**被请求的**端口，所以能命名的端口只能从 socket 地址读，读不出来就是失败而不是「0 号端口上的成功」。命令通道已接（`HostController` 持有 `OpenLan` 直到世界存在，每代只发布一次），并且已经有一次真实运行走到头：`HOST-030`/`HOST-040` 与 `CORE-030` 都以它为准封存。真实的线程名与时间线仍未量。）其生产输出只允许：生命周期状态、成功/失败码、请求/实际 LAN端口、保存结果、时间、profile/bundle/world/session标识和审计引用。

Dashboard需要玩家可见人物信息时，优先使用 client网络处理器/tab/chat可见来源；管理面若以后确需服务端连接计数，必须标为 `management_only`，并从类型系统和路由上禁止进入 Observation/Belief/Memory/Planner/LLM。

### 四道门禁

1. **源码依赖门禁**：模块/source set分离，禁止 server包 imports；host-control维护精确 allowlist而非整个 server包。（2026-09-21：**这一道已实现**，`tools/check_bridge_host_boundary.py`，进 CI 的 `bridge-static` 与本地门禁清单。它按允许清单分两层：`ServerWorld`/`ServerLevel`/`ServerPlayerEntity`/`PlayerManager`/`ServerChunkManager`/`NbtIo`/`LevelStorage` 与反射逃逸（`java.lang.reflect`、`MethodHandles`、`Class.forName`、`setAccessible`、`Unsafe`）**连适配器也不许碰**——一个能读背包的适配器就是把边界挪开而不是关掉；`getServer()`、`IntegratedServer`、`MinecraftServer`、`net.minecraft.server.` 只许 `org/minekin/bridge/host` 用，而且**适配器里也不许通配导入**（允许清单点名类型，通配永远不必回答「到底需要哪几个」）。扫描前先抹掉注释并保留行号，否则写在 javadoc 里的规则会把它自己判成违规——这条有用例。**第 2 道（构建产物门禁）见下。**
2. **构建产物门禁**：扫描 class constant pool/调用引用、mixin JSON、access widener、entrypoint和打包依赖；出现 denylisted owner/method或生产 test probe即构建失败。（2026-09-22：**这一道已实现**，`tools/check_bridge_artifacts.py`，并接进 Gradle 的 `check`——**构建真的会因它而失败**，这不是文档承诺而是 `./gradlew check` 的行为。五个面：class 常量池（含 descriptor 与 Signature 里被擦除的类型）、mixin 配置与 refmap、access widener、entrypoint、打包依赖；第六个是 test probe——`bridge-test-probes` 属于只测试的 source set，这道门禁是**唯一能看见它们有没有被打进去**的那道。两条词汇表绑在一起：`bridge_host_rules.py` 声明一次，两道门禁共用，因此不可能长成两条规则；**映射名归一化**由 `bridge/host-boundary-names.json` 完成，它从固定的 Yarn 构建推导，同时给出 intermediary 与 Yarn 两种拼写——因为本仓库会用两种方式造 Bridge（Gradle 带 Minecraft，remap 成 intermediary；`check_bridge_proto_java.py` 的桩编译，Yarn 名字），只认一种的门禁在另一种产物上就是瞎的，而 CI 只有后一种。`--derive-names` 重推、`--mappings` 校验，表与映射不一致即拒绝运行。）
3. **运行时路由门禁**：每个 DTO带 `information_class=PLAYER_EQUIVALENT|MANAGEMENT_ONLY|TEST_ORACLE`；只有第一类能进入人物认知路径。
4. **黑盒泄漏门禁**：在 server侧放置客户端不可见的实体、方块、容器和玩家位置 canary；检索 Bridge IPC、Runtime事件、Memory、prompt、工具参数和 Dashboard API。任何未授权命中均失败。

门禁目标是让违规容易被发现和阻断，不声称“零泄漏证明”。同 JVM 中恶意或被攻破的 Bridge理论上仍可访问同进程对象；若未来需要安全域而非行为公平，应把世界托管到独立 dedicated server/process，但这不是当前 P0-host默认架构。

## 生命周期事件白名单

host-control可以发出：

```text
HOST_CREATE_ACCEPTED
HOST_LOADER_STARTED
HOST_LOCAL_JOIN_VERIFIED
HOST_LAN_OPENED | HOST_LAN_OPEN_FAILED
HOST_SAVE_STARTED | HOST_SAVE_SUCCEEDED | HOST_SAVE_UNCERTAIN
HOST_STOP_STARTED | HOST_STOPPED
HOST_RECOVERY_REQUIRED
```

事件不得附带 server-side实体列表、区块内容、玩家背包/坐标、seed明文、未由客户端可见的容器、save路径或命令输出。错误用稳定 code + 本地受控日志引用，不把异常对象整段序列化进模型上下文。

## 必测用例

1. `HOSTCTL-001`：同一 Kin提案经 baseline/policy生成 canonical effective profile；重跑 digest一致，显示名不控制目录。（2026-09-22：**这一条已定义、有实现、跑得动**。用例是 `tests/fixtures/cases/hostctl-001.json`，两条断言由 `tests/unit/test_world_creation.py` 里同名的两个测试执行——判据是纯函数，客户端加不了任何东西，这条与 CORE-070 用的是同一个安排。`mandatory` 仍是 `false`，理由见下。）
2. `HOSTCTL-010`：聊天/网页要求 creative、cheats、keepInventory、固定 seed或 datapack；均不能越权修改有效档。（2026-09-22：**同样已定义并跑得动**，`tests/fixtures/cases/hostctl-010.json`。两条断言：越出 P0 档的提案被**拒绝**而不是被悄悄解决成另一个世界；拒绝必须点名**哪个字段、被要求的是什么**。cheats / keepInventory / datapack 走的是最强的那条路——**提案里没有这些字段**，所以它们是 `UNKNOWN_FIELD`，而不是"桥会拒绝一个值"。）

**为什么这两条先做，以及为什么它们还不足以点亮这个面**：它们的主体是**纯函数**（提案 + 策略 → 可摘要的档），所以既不需要客户端也不需要容器；契约的其余用例（`HOSTCTL-020…090`）要么需要真实线程证据、要么需要 canary 服务端，而 `HOST-001…100` 一条都还没有定义。晋级规则说的是"**每一个 mandatory 用例**都有 PASS evidence"——把这两条标成 mandatory 会让 `host-integrated` 报 `promotable`，而契约要求的是整套 `HOST`/`HOSTCTL` 证据。**一个在残缺用例集上给出的"可晋级"就是一句假话**，所以它们留 `mandatory: false`：判据跑着（CI 里就绿），证据也能封（见下），但这个面**还不算有门禁**。
3. `HOSTCTL-020`：client thread之外调用 create/load；adapter拒绝或正确排队，并记录真实线程证据。
4. `HOSTCTL-030`：server thread之外请求 save/open LAN；经 executor执行，client/server互不循环等待。
5. `HOSTCTL-040`：从 server thread触发 stop；验证不会以 `waitForShutdown=true`自锁。
6. `HOSTCTL-050`：延迟旧 create/save callback跨 generation返回；不得推进当前状态或重复建档。（2026-09-22：**域这一半做了**——用例 `tests/fixtures/cases/hostctl-050.json`，两条断言由 `tests/unit/test_hosted_world.py` 里同名的两个测试执行：旧 generation 的完成**不能推动世界**（返回的是同一个记录，不是被改了一半的），同一 epoch 里的**第二次创建被点名拒绝**（`DUPLICATE_CREATION`，而不是笼统的"非法迁移"）。判据是 `domain/hosted_world.py` 里那张**照存储生命周期契约的状态图逐边抄下来**的表，加上"四个坐标逐个重验"的准入规则（`session_id`/`generation`/`world_epoch`/`expected_state`，各有一个 disposition，因为"为什么被拒"才是操作者要问的）。**仍未做的是这条的真实一半**：那个延迟回调由 Bridge 真正发出、跨一次真实 generation 返回——那需要真客户端，本轮没有跑。所以这条的 `mandatory` 仍是 `false`。
7. `HOSTCTL-060`：对 core/nav源码、class、mixin和 access widener注入 `getServer`/`ServerWorld`引用；构建必须失败。
8. `HOSTCTL-070`：host-control尝试输出 server entity/player/inventory DTO；schema/路由门禁拒绝。
9. `HOSTCTL-080`：墙后实体、未见容器、远处玩家坐标、seed和 save path canary；Bridge/Runtime/Memory/prompt中命中数必须为零。
10. `HOSTCTL-090`：真实创建、JOIN、LAN、保存、退出流程记录线程/状态时间线；超时/崩溃不假报成功。

`host-control: tested`需要与[存储生命周期 HOST-001…100](hosted-world-storage-lifecycle-contract.md)使用同一不可变 bundle和 evidence bundle。静态扫描通过不能代替黑盒 canary，黑盒未发现也不能代替构建门禁。


保存不能只看 `saveAll`：玩家数据、世界数据与 Mind 数据库的双水位和故障恢复另见[自建世界提交与跨世界恢复契约](hosted-world-commit-recovery-contract.md)。

## 仍待原型冻结

- 固定 bundle 中 `WORLD_PRESET -> WorldPresets.DEFAULT -> WorldPreset.createDimensionsRegistryHolder()`候选链已找到，仍须编译/运行核对签名、三维度摘要及 datapack lifecycle；
- `createAndStart`异步阶段的真实 client-thread/callback顺序；
- `saveAll`、玩家数据保存、disconnect、server stop和 session close 的最小无损顺序；
- `openToLan`实际执行线程、端口绑定与完成判据；（2026-09-21：**能从固定 jar 里静态读出来的那半已经冻结，运行那半仍未做。** 类是被混淆的 `hje`（`extends net.minecraft.server.MinecraftServer`），签名 `openToLan(GameMode, boolean cheatsAllowed, int port) -> boolean`；以下每条都对 `hje.class` 与 `asf.class`（`ServerNetworkIo`）跑 `javap -p -c` 读出来的，可复现：
  - **线程：client thread。** 方法体里三处触达 `MinecraftClient`（`flk.aU()`、`flk.L().w()`，以及客户端玩家 `gkx` 的 profile 与权限级 `gkx.a(int)`），另有 `getPlayerManager().setCheatsAllowed(..)`。它不是可以从 IPC worker 线程随手调的 server 方法。
  - **完成判据：返回 `true`。** `getNetworkIo().bind(null, port)` 在 try 内**同步**绑定，返回之后 accept 线程（`hjh`）已经 `start()`；所以"绑定完成了没有"就是这一句返回值，不需要另设等待。
  - **端口是会骗人的。** 它 `LOGGER.info("Started serving on {}", port)`，并把**同一个请求值**存进 `getServerPort()` 返回的那个字段。请求 `0`（让系统挑）时两处都会说 `0`。真正绑到的端口只能从 `getNetworkIo().getAddress()`（`asf.a()` 返回 `SocketAddress`）读——契约要的"实际动态端口"在那边，不在日志里。
  - **失败是无声的。** 整个方法体罩在一张 `catch (IOException)` 里（异常表 `0..164 -> 165`），catch 只做 `return false`，**一行日志都不打**。"开 LAN 失败"因此在客户端日志里没有任何痕迹；`HOST_LAN_OPEN_FAILED` 不是礼貌，它是唯一会说这件事的地方。
  - **它顺带改权威状态**：设置游戏模式字段、放开 cheats、抬高宿主玩家的权限级。这与 `HOSTCTL-010` 直接相关——开 LAN 这个动作自己就在动有效档，所以"聊天/网页不得越权改档"的门禁要把这条路径也算进去，而不是只盯着提案入口。
  - **仍未做的**：真实线程名/时间线与 `isOnThread` 结果、以及一次失败的 `openToLan` 在真实运行里长什么样。端口实际绑到哪里已经量到了，但不是从这里量的：它从内核的 listener 表里读出来（IPv4 与 IPv6 两张表都要读，Java 把通配地址绑在 IPv6 上），这条留在这里的剩余理由是**静态读出来的东西不能当成运行证据**；
- class/mixin/access-widener扫描器的实现工具和映射名归一化；（2026-09-21 区分：**第 1 道门禁——源码依赖——已经实现**（`tools/check_bridge_host_boundary.py`），它管的是「谁能写出这些名字」；**第 2 道门禁——构建产物扫描——仍未实现**，它管的是「编出来的 class 常量池里有没有这些引用、mixin JSON/access widener/entrypoint/打包依赖里有没有生产 test probe」。两者不能互相代替：源码门禁看不见依赖树带进来的东西，产物门禁看不见一行被注释掉的意图。映射名归一化也仍未做。）
  - **（2026-09-22 完成）上面这一条做完了，但结论有两处是量出来之后才定下的，值得留在这里。** `tools/check_bridge_artifacts.py` 现在管产物那一半，`bridge/host-boundary-names.json` 管归一化，两者都接进了 Gradle 的 `check`。**（一）打包装进来的依赖不进词汇表扫描。** protobuf-javalite 在自己的类里大量用 `java.lang.reflect` 与 `sun.misc.Unsafe`，照词汇表扫它会把一个被评审过的依赖报成三十四次越界，然后所有人学会忽略这道门禁；管依赖的是它的摘要，不是它的内部。**（二）`MethodHandles` 在产物这一层不能按类型判。** `javac` 为每个 lambda 的 `LambdaMetafactory` bootstrap 发一次 `MethodHandles.lookup()`，于是「这个类提到了 `java/lang/invoke/MethodHandles`」在本仓库自己的 28 个类上都成立，而它们一个都没反射任何东西；这条规则在产物层收窄成**授予权限的那几个成员**（`privateLookupIn`/`unreflect*`/`defineClass*`），bootstrap 从不碰它们。两处都写进了模块的注释与用例，`--derive-names` 推导时也会点出「这个固定 Yarn 构建没有对应名字、产物门禁因此看不见」的标记（当前只有一个：`ServerLevel`，Yarn 叫 `ServerWorld`，那种拼写归源码门禁管）。
  - **仍然是开着的一段**：产物门禁**在 CI 里没有跑**。CI 的 `bridge-static` 只有源码树，而这道门禁需要产物，产物只在构建发生过的地方存在——所以它跑在 Gradle 的 `check` 里（本地与受控 runner），CI 跑的是它的**用例**。要把这一整段收进 CI，需要先让 CI 真的编译 Bridge（JDK 21 + Minecraft 下载），那是「CI 只在 3 个 job 上把关」那一条里写着的事，不是这一步偷偷扩的。
- integrated-server canary fixture怎样在不污染 Kin数据面的测试域中注入。

这些是明确实验项，不是无依据承诺。它们不阻断先完成 `JOIN_REMOTE p0-core`；当前项目仍未进入正式开发。
