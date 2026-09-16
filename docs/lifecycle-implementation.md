# 真客户端身份模式与服务器准入契约

本文是单 Kin / Java 原版生存的**待实跑实施方案**，不是已经证实无人值守真客户端能稳定登录。暂选 Java 1.21.4 客户端兼容性试验；Fabric 默认文档现在展示更新版本，不能把“今天的 Fabric 示例”直接视作 1.21.4 SDK 证据。[Minecraft EULA](https://www.minecraft.net/en-us/eula)允许购买者安装/玩 Java 版并创建原创 Mod，但不允许分发游戏修改后的客户端本体；同版 Yarn `MinecraftServer.isOnlineMode()` 区分 Session Service 验证并说明集成服务器可接受未认证玩家；默认首测本地离线身份，实际入服、聊天、端到端稳定性仍须测试。Microsoft 账号只属于可选 online-mode 适配器。

## 启动前世界外流程

独立 Gateway 通过 Web Dashboard 维护版本化 Server Profile：至少包括 host、port、版本策略/探测协议、已解析 bundle、身份 profile 引用与 `auth_mode`、A/B 模式、锚定玩家、服务器规则、感知/能力配置、资源包与重连策略。Minekin 自带 Launcher/Identity/Version 后端，不调用用户已有启动器；host + port 只是必要信息；身份模式不匹配、白名单、未知协议、未验证 Bridge、资源包或服规仍可阻断入服。详情见[独立 Runtime 与 Dashboard](standalone-runtime-dashboard.md)和[受管理客户端契约](managed-client-runtime.md)。

1. 运行者在**可信的本地/管理界面**选择 A（陪玩）或 B（独立），指定私人测试服务器、运行者玩家身份、权限、服规及身份模式。默认创建稳定的本地离线 profile，用于 LAN 集成世界或明确允许未认证玩家的私人服务器；它不需要 Microsoft/Xbox 账号，也不能绕过 online-mode。目标服明确要求在线验证时，运行者才显式配置可选 Microsoft profile，令牌留在隔离层。跨服务器连续性由 `kin_id` 保证，服务端名字/UUID按服务器分别核验。
2. 人工核对**当前目标服务器**的自动化客户端、PvP、改动感知/矿透、24 小时在线、聊天/骚扰与信息披露规则；私人可控测试服由运行者确定允许范围并通知参与者。禁止的能力在游戏外网关直接不可用，不交给 Kin 的人设自行越权。“邪恶人格”可在各参与者知情且允许的游戏规则内引发冲突，不是豁免 [Minecraft 社区标准](https://www.minecraft.net/en-us/community-standards)或管理员规则；公开服若不允许就不部署。
3. 若服务规则要求说明自动化账号性质，运行者使用服主同意的**账号标识/服务器注册/管理员渠道/欢迎告知**。Kin 在世界内仍从第一人称认为自己是 Kin 玩家，回答不展开模型/后台，也不假冒别人的账号；世界内角色自述不能替代合规渠道。官方 EULA 没有给所有服务器同一“必须在公屏披露机器人”的统一步骤，具体方式须取自目标服规则。

## A 模式的信号边界

指定真人上线且邀请 Kin，是**世界外管理侧**的 `anchor_invite`（经认证来源、账号绑定、时效和单次 nonce），不是玩家在公屏“我是主人”或服务器人数增加。Kin 尚未入服时，它的游戏客户端不可能亲自观察目标服里这个人的在线状态；单纯 ping 人数不能识别锚定玩家。首批可靠路线是运行者手动邀请/授权控制器通知；若以后需要自动联动玩家上线，必须定义运行者侧可信上线信号和授权，不能偷偷查询服务端管理数据库来给 Kin 看世界真值。运行者邀请决定连接资格，不等于要求 Kin 跟随、挖矿或接受危险计划。

连接后可从**正常客户端已呈现的玩家身份**复核锚定对象与观察。锚定玩家离线时状态转 `leave_requested`，立刻停止接收新高层目标、取消攻击/破坏/转移 GUI 等危险写操作、保存未决承诺/意图，在有界时间内正常退出。安全边界意味着停止危险输入而不是继续战斗数分钟，网络断线不应假记自己安全退出。其他真人还在线也依预选锚定规则退出；这个选择由运行者上线模式决定，不能让任意玩家“来就加入”。自动检测离线的具体源/延迟须原型核对，信号不可用时 A 模式默认不再自动入服。

## B 模式与共用状态机

`stopped → probing → bundle_ready → identity_ready → client_starting → bridge_ready → connecting → joined → active/idle → leaving/disconnected → stopped/retry_pending`；A 另需要有效邀请，B 可在服务启动且规则允许时自行连接。B 可持续在线，但不是“断电仍行动”：客户端崩溃/服务器停机后经验冻结，重连核对地点、生命、背包、可见世界和承诺，再由 Kin 决定恢复、换目标或休息。闲置允许站着等炉或降低认知调用频率；本地保命不因此关闭。

同一个角色固定 `kin_id`、`game_identity_profile`、`world/server_identity`、`persona_id`、长期事件账本和出生→死亡→重生记录；服务找不到或无法验证既有身份库时进入恢复态，绝不自动随机一个新人格顶替。启动/崩溃/迁移与旧动作失效遵守[持久化与恢复契约](persistence-recovery-contract.md)。新服务器不把旧箱子权属硬套进来；重生还是同一个人。模式变更写入版本化世界外配置并有效时刻生效，角色人格与过去不重抽；只允许可信运行者设置连接/工具权限，其他玩家聊天仅可影响 Kin 的世界内决定。客户端 1.21.4 Yarn 的 [ClientPlayNetworkHandler](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayNetworkHandler.html)列 `isConnectionOpen`、`getConnection`及断线处理，是观察连接状态的候选接口，**不是自动登录或某服务器兼容的证据**。

开发阶段实测：在正常图形 Minecraft Java/Fabric 客户端、默认本地离线身份与匹配版本的 LAN/offline-mode 私人测试服，验证入服/渲染/移动/聊天、A 信号与退出、B 无人在线仍操作、锚定角色重名/改名、崩溃/断线/重连/切模式后无重复动作；核对服务端按所选身份模式准入、记录其观察到的名字/UUID，且重启仍映射到同一 `kin_id`。Linux/Windows 长驻图形会话与资源消耗须实测，不能把协议 headless 客户端或关闭渲染的任务框架偷换为真实游戏客户端。
