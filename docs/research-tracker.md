# 开发前研究台账

更新：2026-09-15。基线：[main `f1c2b28`](https://github.com/printlndarling/minekin/commit/f1c2b28fd4e6ba27c8b208348d059423f3c7a5ec)。`已查证候选`仅表示源码/文档支持一种可试的路线，**不表示 Kin 已具备该功能**；`需原型验证`表示运行效果必须在实现后证明。每轮复核最新仓库，按新增文档持续扩充本表；本表的编号是研究主题，不是角色每日任务。

| ID | 研究主题与对应文档 | 状态 | 已核对出处/关键限制 | 后续验收与下一步 |
| --- | --- | --- | --- | --- |
| R01 | 锁定 Java/Fabric/Java 工具链；[decisions](decisions.md)、[roadmap](roadmap.md) | 已查证候选 | [Baritone 当前构建属性](https://github.com/cabaletta/baritone/blob/1.21.4/gradle.properties)明确 Minecraft `1.21.4`、Java `21`、Fabric Loader `0.16.9`；不是所有依赖相互兼容的证据 | 暂定 `1.21.4` 作为首个兼容性实验基线；核对 Fabric API、客户端启动与登录，再最终锁栈。见[底座核查](client-foundation.md) |
| R02 | 真客户端账号、Fabric 事件和合法按键输入；[architecture](architecture.md)、[lifecycle](lifecycle.md) | 已查证候选／需原型验证 | [Fabric 事件指南](https://docs.fabricmc.net/develop/events/)说明客户端 tick 回调与需要 Mixin 的情况；不证明实际登录、入服和输入接管稳定 | 用独立账号私人测试服实跑移动/转向/使用/断线恢复，区分客户端实例与无头协议库 |
| R03 | Baritone 导航/采集与玩家等价过滤；[vanilla loop](vanilla-survival-loop.md)、[perception](perception-policy.md) | 已查证候选／需原型验证 | [USAGE](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md)列 `goto`/`mine`/`legitMine`；`legitMine` 不能独自证明寻路和目标扫描无隐藏真值 | 对 API 版进行嵌入兼容实测，审查搜索读数、观察层输入和公共聊天意外发命令 |
| R04 | AltoClef 的任务依赖与跨版本；[vanilla loop](vanilla-survival-loop.md)、[player journey](player-journey.md) | 已查证候选／需原型验证 | [原仓库](https://github.com/gaucho-matrero/altoclef)已归档，README 官方只称 Fabric MC `1.18`；不能当作首发 1.21.4 即插即用底座 | 借鉴依赖任务结构，GUI/配方/补资源技能另做版本适配或自写 |
| R05 | Meteor 战斗/生存模块和许可；[player journey](player-journey.md)、[decisions](decisions.md) | 已查证候选／需原型验证 | [Meteor README](https://github.com/MeteorDevelopment/meteor-client)自称 anarchy 服务器工具客户端、GPL-3.0 且要求使用其源码的作品开源/同许可证；默认不能假设其动作符合玩家等价 | 不作为首版强制依赖；自写正常视角跟踪/盾牌/近战动作最小闭环，许可再复核 |
| R06 | 取木/拾物/工作台/背包 GUI 合成；[vanilla loop](vanilla-survival-loop.md) | 查证中／需原型验证 | Baritone 官方文档支持部分取材，不提供 Kin 已核验的全链 GUI 流程 | 分段测试目标可见、移动、正常破坏、掉落物拾取、GUI 输入、库存确认和异常恢复 |
| R07 | 炉、箱、床、食物、建家与权属；[vanilla loop](vanilla-survival-loop.md)、[living](living-strategy.md)、[player mind](player-mind.md) | 未查 | — | 针对每类 GUI/放置/已知地点和存取回放，避免服务器私有权属数据 |
| R08 | PvE/PvP 移动目标、攻击角度、盾牌、撤退；[journey](player-journey.md)、[ability](ability.md)、[attention](attention-intent.md) | 未查 | — | 制定非 360°追踪与常规输入协议，测遮挡、速度、服务器 TPS 与误伤 |
| R09 | 3D 建造与红石方案、施工精度及实测；[knowledge](knowledge-profile.md)、[ability](ability.md) | 未查 | — | 把材料计划、体素草图、坐标约束、逐块施工和功能测试拆开；高知识不保成功 |
| R10 | 下界/末地与击败龙的分段任务；[journey](player-journey.md)、[goals](goals.md) | 未查 | — | 查当前版本公开规则，分门/跨维度/寻找/战斗/返回，不预设首版通关 |
| R11 | 本地跌落/爆炸等反射与延迟预算；[architecture](architecture.md)、[ability](ability.md) | 需原型验证 | [Fabric 事件](https://docs.fabricmc.net/develop/events/)支持事件驱动，可有本地回路；成功率和 1 tick 夺权尚无实测 | 回放触发→首次输入 tick、抢占、动作失败和响应过期；模型不得处于实时回路 |
| R12 | 玩家等价观察、声音/遮挡/有限例外和矿透开关；[perception](perception-policy.md)、[social](social-judgment.md) | 未查 | — | 定观察和底层技能访问的同一数据策略；分别审计短时反射例外与主动矿透 |
| R13 | 自主目标、情绪、个性与跨日关系；[player mind](player-mind.md)、[personality](personality.md)、[decision agency](decision-agency.md) | 未查 | — | 给出事件/状态/选择协议；未安排剧情的压力测试与重启一致性 |
| R14 | 记忆信念、权属、证据修订、存储迁移；[player mind](player-mind.md)、[learning](learning.md) | 未查 | — | 细化数据模式、SQLite/归档与证据来源；猜测不洗成已证实事实 |
| R15 | 版本世界书与开局知识树、后天实战成长；[world guide](world-guide.md)、[knowledge](knowledge-profile.md)、[ability](ability.md) | 未查 | — | 公开知识版本节点与角色掌握分开；高红石知识也须真实建造验证 |
| R16 | 自主查资料与复用技能、外部能力清单；[external tools](external-tools.md)、[learning](learning.md) | 未查 | — | 查资料→待证方案→真实动作→技能晋级；额度、取消与工具超时 |
| R17 | 聊天/网页提示词注入和身份信息泄漏；[instruction boundary](instruction-boundary.md)、[identity](self-identity.md) | 未查 | [OWASP 原始防护指南](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)列指令/数据隔离及最小权限，并不保证零泄漏 | 定信任标注、输出/工具网关和记忆污染测试，身份玩家式答复与后台隐私分开 |
| R18 | 两种在线模式、游戏内玩家身份与对服主规则的外部告知；[lifecycle](lifecycle.md)、[identity](self-identity.md) | 未查 | — | 账号标识核验、连接停启、角色持续和具体测试服规则；不靠角色对话代替合规披露 |
| R19 | 云端模型、存储/网络/调用成本及模型断线安全；[architecture](architecture.md)、[roadmap](roadmap.md) | 未查 | — | 按实际模型与环境测 token、上下文、数据和失败退化，不提前指定不可验证价格 |
| R20 | 回放、指标和“准备开工”门槛；[roadmap](roadmap.md)、[decisions](decisions.md) | 未查 | — | 形成可分期的设计冻结与原型试验，核对误拒、泄漏、动作与场景成功率 |
| R21 | 外部项目/论文引用的真实性与适用范围；[alma](alma-reference.md)、[references](references.md) | 查证中 | 本轮重新核对 Fabric、Baritone、AltoClef、Meteor 的源码/许可证；其他链接未逐一复核 | 继续核验 Hermes/OpenClaw/Voyager/Alma 以及服务器条款、版本和证据局限 |
| R22 | 远期多 Kin、模组和服务器公开部署；[multi kin](multi-kin.md)、[roadmap](roadmap.md) | 不纳入首版门槛 | 已定范围是单 Kin、原版生存、私人测试 | 保留 future；不作为首版开发就绪的未解决阻断 |

状态说明：本轮尚无运行原型或完整兼容测试，R01–R05 的源码证据仅支持**先试哪条路**。其余列“未查/查证中”的主题不能因已有设计文档而提前标为可开发。下轮优先推进 R06–R09，更新对应行、出处和提交链接；GitHub 提交 SHA 本轮完成后在下次台账更新时回填。完整来源表见[参考资料](references.md)。
