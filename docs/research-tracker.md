# 开发前研究台账

更新：2026-09-16。客户端动作契约已提交：[动作核查 `a8682b0`](https://github.com/printlndarling/minekin/commit/a8682b07f1b6005398deeb086c49e6ee540a106a)。`已查证候选`仅表示源码/文档支持一种可试的路线，**不表示 Kin 已具备该功能**；`需原型验证`表示运行效果必须在实现后证明。每轮复核最新仓库，按新增文档持续扩充本表；本表的编号是研究主题，不是角色每日任务。

| ID | 研究主题与对应文档 | 状态 | 已核对出处/关键限制 | 后续验收与下一步 |
| --- | --- | --- | --- | --- |
| R01 | 锁定 Java/Fabric/Java 工具链；[decisions](decisions.md)、[roadmap](roadmap.md) | 已查证候选 | [Baritone 当前构建属性](https://github.com/cabaletta/baritone/blob/1.21.4/gradle.properties)明确 Minecraft `1.21.4`、Java `21`、Fabric Loader `0.16.9`；不是所有依赖相互兼容的证据 | 暂定 `1.21.4` 作为首个兼容性实验基线；核对 Fabric API、客户端启动与登录，再最终锁栈。见[底座核查](client-foundation.md) |
| R02 | 真客户端账号、Fabric 事件和合法按键输入；[architecture](architecture.md)、[lifecycle](lifecycle.md) | 已查证候选／需原型验证 | [Fabric 事件指南](https://docs.fabricmc.net/develop/events/)说明客户端 tick 回调与需要 Mixin 的情况；不证明实际登录、入服和输入接管稳定 | 用独立账号私人测试服实跑移动/转向/使用/断线恢复，区分客户端实例与无头协议库 |
| R03 | Baritone 导航/采集与玩家等价过滤；[vanilla loop](vanilla-survival-loop.md)、[perception](perception-policy.md) | 已查证候选／需原型验证 | [USAGE](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md)列 `goto`/`mine`/`legitMine`；`legitMine` 不能独自证明寻路和目标扫描无隐藏真值 | 对 API 版进行嵌入兼容实测，审查搜索读数、观察层输入和公共聊天意外发命令 |
| R04 | AltoClef 的任务依赖与跨版本；[vanilla loop](vanilla-survival-loop.md)、[player journey](player-journey.md) | 已查证候选／需原型验证 | [原仓库](https://github.com/gaucho-matrero/altoclef)已归档，README 官方只称 Fabric MC `1.18`；不能当作首发 1.21.4 即插即用底座 | 借鉴依赖任务结构，GUI/配方/补资源技能另做版本适配或自写 |
| R05 | Meteor 战斗/生存模块和许可；[player journey](player-journey.md)、[decisions](decisions.md) | 已查证候选／需原型验证 | [Meteor README](https://github.com/MeteorDevelopment/meteor-client)自称 anarchy 服务器工具客户端、GPL-3.0 且要求使用其源码的作品开源/同许可证；默认不能假设其动作符合玩家等价 | 不作为首版强制依赖；自写正常视角跟踪/盾牌/近战动作最小闭环，许可再复核 |
| R06 | 取木/拾物/工作台/背包 GUI 合成；[动作契约](action-contracts.md)、[vanilla loop](vanilla-survival-loop.md) | 已查证候选／需原型验证 | [1.21.4 Yarn 客户端交互面](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)有正常持续破坏、配方与槽位操作；不证明真实动作/同步可靠 | 分段测试目标可见、导航、正常挖掘、拾物、GUI 输入、库存确认和中断恢复 |
| R07 | 炉、箱、床、食物、建家与权属；[动作契约](action-contracts.md)、[living](living-strategy.md)、[player mind](player-mind.md) | 已查证候选／需原型验证 | [ScreenHandler.syncId](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/ScreenHandler.html) 与[炉界面类](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/AbstractFurnaceScreenHandler.html)支持按打开的正常 GUI 执行；箱内信息仍受是否实际打开约束 | 按界面类型/同步 ID/槽位正确性回放炉、箱、床及重新进入后的核验 |
| R08 | PvE/PvP 移动目标、攻击角度、盾牌、撤退；[动作契约](action-contracts.md)、[ability](ability.md)、[attention](attention-intent.md) | 已查证候选／需原型验证 | [MinecraftClient.crosshairTarget](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html) 与正常 `attackEntity` 可作受限攻击候选，不允许遍历实体列表直接攻击 | 实测遮挡/角速度/攻速/盾牌装备/误伤和对方离开视野后失联，明确禁止 360°杀戮光环 |
| R09 | 3D 建造与红石方案、施工精度及实测；[动作契约](action-contracts.md)、[knowledge](knowledge-profile.md)、[ability](ability.md) | 已查证候选／需原型验证 | [interactBlock](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)及 [Baritone build 文档](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md)支持分步施工的研究路线，未核验审美/复杂机械 | 小屋与小电路分别测体素草图、材料、可站位置、逐块放置、朝向与运行结果 |
| R10 | 下界/末地与击败龙的分段任务；[journey](player-journey.md)、[goals](goals.md) | 未查 | — | 查当前版本公开规则，分门/跨维度/寻找/战斗/返回，不预设首版通关 |
| R11 | 本地跌落/爆炸等反射与延迟预算；[architecture](architecture.md)、[ability](ability.md) | 需原型验证 | [Fabric 事件](https://docs.fabricmc.net/develop/events/)支持事件驱动，可有本地回路；成功率和 1 tick 夺权尚无实测 | 回放触发→首次输入 tick、抢占、动作失败和响应过期；模型不得处于实时回路 |
| R12 | 玩家等价观察、声音/遮挡/有限例外和矿透开关；[感知实施](perception-implementation.md)、[政策](perception-policy.md) | 已查证候选／需原型验证 | [Yarn 准星与渲染侧目标接口](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/render/GameRenderer.html)支持候选观察，源码接口不自动意味着屏幕可见；动作例外不进入人物信念 | 在私人测试世界以截图对照视锥/遮挡/黑暗/墙后/声源并审计 Baritone 底层目标，矿透另开来源模式 |
| R13 | 自主目标、情绪、个性与跨日关系；[数据契约](mind-data-contract.md)、[player mind](player-mind.md)、[personality](personality.md) | 已查证研究参考／需原型验证 | [Generative Agents 论文](https://arxiv.org/abs/2304.03442)提供观察/反思/规划的研究依据，但不是 Minecraft/实时/防注入能力 | 逐日生活、未预排请求、关系变动、情绪改变行动和自主目标退出的回放 |
| R14 | 记忆信念、权属、证据修订、存储迁移；[数据契约](mind-data-contract.md)、[player mind](player-mind.md) | 已查证候选／需原型验证 | [SQLite WAL](https://www.sqlite.org/wal.html)、[外键](https://www.sqlite.org/foreignkeys.html)和[在线备份](https://www.sqlite.org/backup.html)支持单角色本地事件账本的可实施路线；没有实际负载数据 | 幂等事件、证据-信念连接、数据库快照/迁移、模型离线和死后重连测试 |
| R15 | 版本世界书与开局知识树、后天实战成长；[world guide](world-guide.md)、[knowledge](knowledge-profile.md)、[ability](ability.md) | 未查 | — | 公开知识版本节点与角色掌握分开；高红石知识也须真实建造验证 |
| R16 | 自主查资料与复用技能、外部能力清单；[external tools](external-tools.md)、[learning](learning.md) | 未查 | — | 查资料→待证方案→真实动作→技能晋级；额度、取消与工具超时 |
| R17 | 聊天/网页提示词注入和身份信息泄漏；[数据契约](mind-data-contract.md)、[instruction boundary](instruction-boundary.md) | 已查证防护方向／需原型验证 | [OWASP 原始防护指南](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)列指令/数据隔离与最小权限；事件来源、可信配置、输出网关可分权设计，不保证零泄漏 | 定信任标注、工具/输出网关及经过多轮摘要和重启的记忆污染测试 |
| R18 | 两种在线模式、游戏内玩家身份与对服主规则的外部告知；[lifecycle](lifecycle.md)、[identity](self-identity.md) | 未查 | — | 账号标识核验、连接停启、角色持续和具体测试服规则；不靠角色对话代替合规披露 |
| R19 | 云端模型、存储/网络/调用成本及模型断线安全；[architecture](architecture.md)、[roadmap](roadmap.md) | 未查 | — | 按实际模型与环境测 token、上下文、数据和失败退化，不提前指定不可验证价格 |
| R20 | 回放、指标和“准备开工”门槛；[roadmap](roadmap.md)、[decisions](decisions.md) | 未查 | — | 形成可分期的设计冻结与原型试验，核对误拒、泄漏、动作与场景成功率 |
| R21 | 外部项目/论文引用的真实性与适用范围；[alma](alma-reference.md)、[references](references.md) | 查证中 | 本轮重新核对 Fabric、Baritone、AltoClef、Meteor 的源码/许可证；其他链接未逐一复核 | 继续核验 Hermes/OpenClaw/Voyager/Alma 以及服务器条款、版本和证据局限 |
| R22 | 远期多 Kin、模组和服务器公开部署；[multi kin](multi-kin.md)、[roadmap](roadmap.md) | 不纳入首版门槛 | 已定范围是单 Kin、原版生存、私人测试 | 保留 future；不作为首版开发就绪的未解决阻断 |

状态说明：本轮依然没有运行原型，R12–R14/R17 增补的是资料支持的设计路线而非实际游戏成果。剩余 R10、R15–R16、R18–R21 尚须独立核查；不能只因有数据表和过滤说明就宣布具备完整人格或零泄漏。本轮 GitHub 提交 SHA 下次台账更新时回填；证据索引见[参考资料](references.md)。
