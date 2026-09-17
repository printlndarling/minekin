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

`bridge-host-control`可以引用 loader、storage session和极少的 server lifecycle方法，但不能引用 server world/entity/chunk/inventory/player-manager查询。其生产输出只允许：生命周期状态、成功/失败码、请求/实际 LAN端口、保存结果、时间、profile/bundle/world/session标识和审计引用。

Dashboard需要玩家可见人物信息时，优先使用 client网络处理器/tab/chat可见来源；管理面若以后确需服务端连接计数，必须标为 `management_only`，并从类型系统和路由上禁止进入 Observation/Belief/Memory/Planner/LLM。

### 四道门禁

1. **源码依赖门禁**：模块/source set分离，禁止 server包 imports；host-control维护精确 allowlist而非整个 server包。
2. **构建产物门禁**：扫描 class constant pool/调用引用、mixin JSON、access widener、entrypoint和打包依赖；出现 denylisted owner/method或生产 test probe即构建失败。
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

1. `HOSTCTL-001`：同一 Kin提案经 baseline/policy生成 canonical effective profile；重跑 digest一致，显示名不控制目录。
2. `HOSTCTL-010`：聊天/网页要求 creative、cheats、keepInventory、固定 seed或 datapack；均不能越权修改有效档。
3. `HOSTCTL-020`：client thread之外调用 create/load；adapter拒绝或正确排队，并记录真实线程证据。
4. `HOSTCTL-030`：server thread之外请求 save/open LAN；经 executor执行，client/server互不循环等待。
5. `HOSTCTL-040`：从 server thread触发 stop；验证不会以 `waitForShutdown=true`自锁。
6. `HOSTCTL-050`：延迟旧 create/save callback跨 generation返回；不得推进当前状态或重复建档。
7. `HOSTCTL-060`：对 core/nav源码、class、mixin和 access widener注入 `getServer`/`ServerWorld`引用；构建必须失败。
8. `HOSTCTL-070`：host-control尝试输出 server entity/player/inventory DTO；schema/路由门禁拒绝。
9. `HOSTCTL-080`：墙后实体、未见容器、远处玩家坐标、seed和 save path canary；Bridge/Runtime/Memory/prompt中命中数必须为零。
10. `HOSTCTL-090`：真实创建、JOIN、LAN、保存、退出流程记录线程/状态时间线；超时/崩溃不假报成功。

`host-control: tested`需要与[存储生命周期 HOST-001…100](hosted-world-storage-lifecycle-contract.md)使用同一不可变 bundle和 evidence bundle。静态扫描通过不能代替黑盒 canary，黑盒未发现也不能代替构建门禁。

## 仍待原型冻结

- 默认维度 supplier从 registry生成的确切调用链及 datapack lifecycle处置；
- `createAndStart`异步阶段的真实 client-thread/callback顺序；
- `saveAll`、玩家数据保存、disconnect、server stop和 session close 的最小无损顺序；
- `openToLan`实际执行线程、端口绑定与完成判据；
- class/mixin/access-widener扫描器的实现工具和映射名归一化；
- integrated-server canary fixture怎样在不污染 Kin数据面的测试域中注入。

这些是明确实验项，不是无依据承诺。它们不阻断先完成 `JOIN_REMOTE p0-core`；当前项目仍未进入正式开发。
