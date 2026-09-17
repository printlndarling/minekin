# 受管理客户端目录与世界承载模式契约

核查时间：2026-09-17。本文澄清“固定 mods 清单、不读取用户原有 `.minecraft/mods`”的真实含义，并把 Kin 作为加入者与 Kin 自己创建世界并开放 LAN 两种玩法正式分开。

这仍是设计与静态接口核查，不表示已经创建世界、保存区块、开放端口或让第二名玩家加入。

## 先澄清 `.minecraft`

`.minecraft`只是常见启动器默认采用的客户端运行目录名称，不等于“单机存档本身”。Minecraft 1.21.4 的 `MinecraftClient.runDirectory`被同版 Yarn 文档定义为保存 options、worlds、resource packs、logs 等内容的目录；客户端还持有独立的 level storage、resource-pack directory 和连接状态。

因此，即使一个客户端一生只加入别人的服务器，它仍需要一个 writable run directory，用于选项、日志、崩溃报告、服务器资源包缓存等。它可以没有任何 Kin 自建的 world save，也不要求使用用户主目录下的默认 `.minecraft`。

Minekin 的正确边界是：

- 不读取、不发现、不挂载宿主用户已有的 `~/.minecraft`、启动器实例、`mods`、`saves`、账号或设置；
- Launcher 为受管理客户端显式指定 Minekin 自己的 run directory、assets directory、classpath、natives 和 bundle；
- “固定 mods 清单”只约束**这个 Minekin 客户端实例**可加载哪些 Bridge/依赖，不涉及用户原有游戏；
- 加入远端世界时，Kin 没有本地世界存档；自己承载世界时，world save 才进入 Kin 的持久世界存储。

文档后续优先使用“managed run directory”，避免把所有目录都口语化叫成 `.minecraft`。

## 两个正交维度

原有 A/B 模式只决定**什么时候在线**：

- A 陪玩：满足锚定真人在线/邀请策略时才运行世界会话；
- B 独立：没有真人在线也可继续生活。

本文件新增的 world attachment mode 决定**世界由谁承载**：

- `JOIN_REMOTE`：加入别人的 dedicated server，或加入别人客户端开放的 LAN integrated world；
- `HOST_INTEGRATED_LAN`：Kin 创建或加载自己的本地 save，启动真实 integrated server，并开放 LAN 让其他玩家加入。

二者正交，不生成四套人格：

| 在线策略 | JOIN_REMOTE | HOST_INTEGRATED_LAN |
| --- | --- | --- |
| A 陪玩 | 真人邀请后加入其服务器/LAN；真人离开后退出 | 在锚定真人需要陪玩时启动 Kin 的世界并开放 LAN；锚定真人离开后按 A 策略保存并关闭 |
| B 独立 | 无人在线也可留在目标服务器生活 | Kin 可独自玩自己的 save；客户端运行时其他玩家可加入其 LAN 世界 |

模式切换不改变 `kin_id`、Persona、关系或全局技能。它只切换 session policy、当前 world context 和存储挂载。

## 世界承载模式一：JOIN_REMOTE

目标包括：

- 独立 dedicated server；
- 另一名玩家或测试 host 开放的 LAN integrated server；
- 明确允许本地离线身份的私人服务端/代理后端；
- 未来显式配置在线身份后允许的 online-mode 服务端。

运行目录仍存在，但其 `saves`不是世界权威。当前位置、背包、区块、实体和世界进度由远端逻辑服务端负责；本地只保存客户端配置、日志、资源包缓存、截图/回放证据和 Bridge 会话文件。

Server Profile 继续拥有 host/port、认证模式、版本策略、服务器规则和 reconnect policy。远端世界身份不得由本地目录名推断。

## 世界承载模式二：HOST_INTEGRATED_LAN

同版 `MinecraftClient`明确可以创建并启动 `IntegratedServer`；`IntegratedServer.openToLan(gameMode, cheatsAllowed, port)`明确只支持 integrated server，并返回是否成功开放 LAN。该模式技术上可行，但必须新增世界持久化、端口生命周期和 host 崩溃语义。

基本流程：

1. Runtime 选择已有 `hosted_world_id`，或由 Kin 的游戏内决定创建新世界；
2. Launcher 将对应 world save 以单写者方式挂载到该客户端的 managed run directory；
3. Bridge 在 client thread 启动/加入 integrated world，等待本地主机玩家真正进入；
4. 若策略要求开放 LAN，调用同版受控适配器，以配置端口、默认 game mode 和 `cheatsAllowed=false`开放；
5. Gateway 发布实际监听地址/端口给获准玩家；游戏聊天无权改绑定地址、端口或权限；
6. 关闭时先停止新连接与动作，保存/flush integrated server，关闭世界，再提交世界 checkpoint；
7. 重启后恢复同一 `kin_id + hosted_world_id + world_epoch`，但玩家、实体、GUI 与未完成动作全部重验。

重要限制：

- integrated server 与 Kin 客户端同进程生命周期；客户端退出/崩溃时 LAN 世界也停止服务，其他玩家会断线；
- “Kin 独立在线”不等于世界永远在线，仍受 Supervisor 运行窗口、机器故障和资源预算约束；
- 默认不允许 commands/cheats；`cheatsAllowed=true`只能是显式管理配置，且不能被玩家聊天或 Kin 自己升级；
- LAN 端口是会话端点，不是世界身份；端口变化不能创建新人格或丢失旧世界；
- 只有客户端正在运行且 integrated server 成功开放时，其他玩家才能加入；
- 远程公网托管、NAT 穿透和把 LAN 暴露到互联网不属于本模式默认能力。

## 存储拓扑

Minekin 不应把所有东西塞进一个长期可写的“它自己的 `.minecraft`”。推荐按职责拆分：

| 存储 | 生命周期 | 内容 | 能否由客户端写 |
| --- | --- | --- | --- |
| Artifact Store | 跨 Kin/版本、内容寻址 | 官方 client/libraries/assets、Java、natives、开源依赖 | 否；安装后只读 |
| Client Bundle | 版本化、不可变 | Loader、Fabric API、Bridge、批准的可选组件与 manifest | 否；启动前核摘要 |
| Client Profile | Kin + bundle 持久 | 必要 options、语言、键位和已审核客户端偏好 | 受 schema 控制 |
| Session Overlay | 单次 generation | logs、crash reports、临时资源包、IPC descriptor、缓存 | 是；结束后按策略归档/清理 |
| Hosted World Store | Kin + hosted world 持久 | save、world manifest、epoch、checkpoint 与备份 | 仅 active host session 单写 |
| Mind/Memory Store | Kin 持久 | Persona、事件、关系、目标、技能 | Minecraft JVM 不可访问 |

Hosted World Store 不直接等于整个 run directory。Launcher 只把当前 save 以受控路径映射到 `saves/<slot>`；remote-join session 不挂载任何 hosted save。世界备份使用安全停服/flush 后的 checkpoint 或经验证的一致性方案，不把正在写入的目录当成完整备份。

每个目录必须在 manifest 中解析为 Minekin data root 下的规范化绝对路径；拒绝 symlink/path traversal 指向用户 home、其他 Kin 或外部 `.minecraft`。

## 固定 mods 清单的准确含义

Fabric Loader 会从配置的 game directory/mods 或显式 mods folder发现候选。为了可复现性与权限最小化，每个 Client Bundle 固定：

- Minekin Thin Bridge；
- 与该版本匹配的 Fabric API/Loader；
- 明确批准且已核许可/摘要的可选组件；
- 禁止未声明 JAR、用户投放目录和跨 bundle 共享可写 mods 目录。

这不是假设用户有现成 `.minecraft`，也不是让 Kin 使用用户的世界。它是防止宿主机上随便一个旧 mod、作弊客户端、恶意 JAR 或不兼容 mixin 被受管理进程顺手加载。

`HOST_INTEGRATED_LAN`尤其需要更严格：Bridge 必须是 client entrypoint，不能注册新方块/物品/datapack、改变世界生成或把 server-side 真值送入 PlayerMind。因为 integrated server 与客户端同 JVM，任何触及 common/server 类的 mixin 都要单独审计；首个 host 原型只运行 `p0-core`，`p0-nav-exp`之后独立验证。其他玩家不应因 Kin 的 Bridge 被迫安装客户端 mod。

## World Context 身份

`world_context`新增：

- `attachment_mode: JOIN_REMOTE | HOST_INTEGRATED_LAN`；
- remote 使用 `server_profile_id`和经确认的远端 world identity；
- hosted 使用 `hosted_world_id`、save manifest digest、创建事件和 `world_epoch`；
- `session_endpoint`记录当次 host/port，但不参与人格或世界主键；
- save 被复制、回滚或替换时必须创建候选新 epoch，不能仅凭目录名自动合并。

同一个 Kin 可在自己的世界与多个远端世界间切换，但任一时刻仍只有一个 active world session。自己的世界不意味着它可以把服务器真值当人物感知：integrated server 内部数据仍受 Player-Equivalent Filter 隔离。

## Dashboard 配置

Dashboard 将原“Servers”扩展为“Worlds & Servers”：

- Remote Profile：host、port、版本、认证、规则与资源包策略；
- Hosted World：创建/导入、版本、seed 设置来源、难度、game mode、LAN 开关/端口、允许玩家、备份和存储占用；
- 当前 attachment/online policy 的二维状态；
- integrated server 状态、实际端口、连接玩家和保存/备份健康；
- host stop 前的玩家提示与强制停止倒计时；
- 明确区分“停止 Kin 客户端”“关闭 LAN”“删除世界”；删除必须另有高风险确认，不能由聊天触发。

Kin 可以在世界内自主决定“我想新开一个世界/继续旧世界”或是否邀请朋友，但创建、网络暴露、导入、删除、磁盘限额和 cheats 属系统权限，必须经管理策略许可。

## 分阶段验证

`JOIN_REMOTE`仍是 `p0-core`最先闭环的范围，因为它能最小化 world-save 和 host 生命周期变量。随后增加独立的 `host-integrated` capability，不改写已通过的 remote 证据：

1. 全新 Minekin data root 启动 remote client，确认未访问宿主 `.minecraft`；
2. 只加入 dedicated/LAN 时 run directory 产生正常客户端文件，但没有被当成 Kin-owned world；
3. 创建固定 seed 的 hosted world，退出、重启、备份恢复后仍是同一 save/epoch；
4. `cheatsAllowed=false`开放固定/动态端口，第二个真实客户端加入、离开、重连；
5. host 正常关闭、client 强杀、磁盘满、save lock 冲突、端口占用与世界损坏；
6. A/B × JOIN/HOST 四组合的上线/下线和计划暂停；
7. 验证 Bridge/任何 mixin 不改变服务端内容、协议或向 PlayerMind泄漏 integrated-server 真值；
8. 切 hosted→remote→hosted，同一 Kin 连续，背包/地点/人物/计划不串世界。

`host-integrated: tested`独立于 `p0-core: tested`。没有保存、第二客户端加入、崩溃恢复和真值隔离证据时，Dashboard 不得显示“可托管世界”。

## 尚待原型冻结

- 新世界创建 UI/registry 如何用客户端现有 world-creation pipeline稳定驱动，而不伪造 GUI 成功；
- hosted save 的一致性 checkpoint、增量备份、配额和迁移实现；
- LAN 只绑定局域网地址的实际行为、防火墙策略和端口发现；
- host 玩家暂停菜单、窗口失焦与 integrated-server tick 行为；
- 第二客户端使用 offline 身份时的白名单/同名冲突与运行者体验；
- Bridge/common mixin 对 integrated server 的完整触达审计。

这些不改变产品结论：所有游戏资源、客户端目录和 hosted saves 都属于 Minekin 自己的受管理数据根，与用户已有 Minecraft 安装完全隔离。
