# 技术与研究出处索引

最后逐项在线核对：2026-09-15。此表区别**源码给出的事实**、**可借鉴的思路**、**Kin 需自行验证的能力**；不是下载这些项目就能形成 Kin 的说明书。GitHub 链接标分支时仍须在决定依赖前锁具体 commit 与发布包哈希；官网文档可能随默认 Minecraft 版本更新。

| 来源 | 当下核对到的事实与适用版本 | 局限与使用方式 |
| --- | --- | --- |
| [Fabric 官方事件指南](https://docs.fabricmc.net/develop/events/) | 官方说明 Fabric API 的事件/回调机制、`ClientTickEvents` 以及事件不足时可用 Mixin；当前默认网页展示新版文档 | 不等于 1.21.4 代码无需迁移；下一步使用对应版本的 API/Javadoc 对照，在真客户端实测 |
| [Fabric Example Mod 源码](https://github.com/FabricMC/fabric-example-mod) | Fabric 官方组织示例模组，当前默认分支为 `26.2`，许可证 CC0-1.0 | 只能作为工程结构参考，不能直接认为示例当前代码适配 1.21.4 |
| [Baritone 1.21.4 构建参数](https://github.com/cabaletta/baritone/blob/1.21.4/gradle.properties) | 分支的 Minecraft `1.21.4`、Fabric Loader `0.16.9`、Java `21`、Baritone `1.13.1` 见属性文件 | 构建参数不是 Kin + Fabric API + 测试服真实兼容、也不保证仓库所有默认分支常年停留 1.21.4 |
| [Baritone 官方 SETUP](https://github.com/cabaletta/baritone/blob/1.21.4/SETUP.md) | 列出支持版本与 Fabric API/standalone/unoptimized 构件；API 构件适合其他模组集成 | 发布包与源码 commit 均需锁定；不能用 standalone 构件声称它允许 Kin 调用 API |
| [Baritone USAGE](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md) | 文档有 `goto`、`mine`、`follow`、`build`、`legitMine` | 它是算法能力和命令级文档，不证明正常玩家可见域过滤；聊天命令有错发公屏风险，优先 API 接口 |
| [Baritone LICENSE](https://github.com/cabaletta/baritone/blob/1.21.4/LICENSE) | 仓库元数据标 LGPL-3.0，README 还标“anime exception” | README 与 LICENSE/源码头的附加措辞需发布前复核；链接、修改、分发义务另做许可审查，避免贸然复制代码 |
| [AltoClef 官方仓库](https://github.com/gaucho-matrero/altoclef)及[LICENSE](https://github.com/gaucho-matrero/altoclef/blob/main/LICENSE) | 仓库已归档，官方 README 自述原版 Fabric `1.18`，MIT | 400+ 物品、自动通关是原项目对旧版能力的报告，不是 1.21.4 可直接集成/继承的证据；借鉴任务依赖和执行反馈 |
| [Meteor 官方仓库/README](https://github.com/MeteorDevelopment/meteor-client)及[LICENSE](https://github.com/MeteorDevelopment/meteor-client/blob/master/LICENSE) | 自称用于 anarchy 服务器的 Fabric utility mod，GPL-3.0，README 明确使用其源码的同许可证/源码披露要求 | 其默认战斗/感知功能可能越过玩家等价边界；不作为首版强制底层依赖，不挪源码到私有 Kin |
| [Yarn `ClientPlayerInteractionManager` 1.21.4+build.8](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html) | 当前 Javadoc 列正常破坏/攻击/对方块交互、配方书、槽位点击以及持续挖掘进度 | 方法存在不代表动作成功；需要真实游戏服核验服务器同步和玩家式感知 |
| [Yarn `ScreenHandler` 1.21.4+build.8](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/ScreenHandler.html)、[工作台](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/CraftingScreenHandler.html)、[炉](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/AbstractFurnaceScreenHandler.html) | 当前 Javadoc 区分屏幕同步 ID、界面槽位以及炉进度 | GUI 切换、服务端同步与版本改动要求按界面类型测试；未打开箱子内容不因此可读 |
| [Yarn `MinecraftClient.crosshairTarget` 1.21.4+build.8](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html) | 常规客户端有当前准星命中结果与目标实体状态 | 战斗只能对合法视野与朝向目标动作；不从底层实体列表生成 360°攻击 |
| [Yarn `GameRenderer` 1.21.4+build.8](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/render/GameRenderer.html) | 常规客户端查当前准星目标并限制交互距离；可作过滤候选入口 | 准星命中不是完整视觉识别；投影视锥、射线遮挡/光照还需截图和私人场景验收 |
| [SQLite WAL](https://www.sqlite.org/wal.html)、[外键](https://www.sqlite.org/foreignkeys.html)、[UPSERT](https://www.sqlite.org/lang_upsert.html)、[在线备份](https://www.sqlite.org/backup.html) | 官方资料支持本地单角色事件账本的并行读写、约束、幂等和备份候选 | WAL 不适合跨主机网络文件系统；要测试写负载/重连和关闭期间事务，不直接拷运行中 `.db` |
| [Generative Agents 原论文](https://arxiv.org/abs/2304.03442)及[作者源码](https://github.com/joonspk-research/generative_agents) | 2023 年论文与原仓库研究观察、反思、检索、规划和社会互动 | 研究为类 Sims 环境；不能当作 Fabric 客户端、低延迟反射或 Minecraft 社会人格现成实现 |
| [OWASP 提示词注入指南](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | 指令与不可信内容分离、最小权限与工具/输出验证的技术参考 | 不能保证“永远无泄漏”，必须用真实对话、网页、记忆和调用的对抗回放 |
| [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)及[OpenAI Agent 注入研究](https://openai.com/index/designing-agents-to-resist-prompt-injection/) | 补充间接注入、外传目标与模型防护不足的威胁分类 | 作为风险与验收设计参考，不能代替 Kin 网关实现与测试 |

| [Minecraft Java 1.21.4 官方更新说明（2024-12-02）](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-4) | 官方版本变更有 Pale Garden、Pale Oak、Creaking Heart、Resin 和 Eyeblossom；候选世界书版本锚点，2026-09-16 复核 | 不是完整百科，更不透露本世界物品/坐标；工程基线与游戏结果仍须实测 |
| [官方 Stronghold 指南（2024-07-04）](https://www.minecraft.net/en-us/article/stronghold) | 说明珍珠+烈焰粉→眼、投掷指向要塞、填门框，2026-09-16 复核 | 方向是正常游戏观察，不等于直接查要塞位置；动作成功须现场验证 |
| [官方速通指南（2022-05-18）](https://www.minecraft.net/en-us/article/how-beat-minecraft-under-30-mins) | 下界、堡垒、烈焰棒、珍珠与末地龙的实例，2026-09-16 复核 | 旧速通策略不是 1.21.4 机制规范，也不是 Kin 必走路线 |
| [Voyager 原论文（2023）](https://arxiv.org/abs/2305.16291)及[作者项目](https://github.com/MineDojo/Voyager) | 自动课程、可执行技能库与执行反馈自验证，2026-09-16 复核 | 其环境和代码技能不能直接作为 Kin 的 Fabric 真客户端技能 |
| [Hermes 官方技能系统](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)及[使用指南](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills) | 按需载入和自写技能，2026-09-16 复核；官网可能更新 | Kin 不照搬无审批脚本写入权限，只借目录与归纳思路 |
| [OpenClaw 官方网页工具](https://docs.openclaw.ai/tools/web)及[技能系统](https://docs.openclaw.ai/tools/skills) | 网页搜索/读取与技能范围设计参考，2026-09-16 复核 | 外部 Agent 权限不能等同玩家可见游戏行为 |

| [Minecraft EULA（2026-09-16 复核）](https://www.minecraft.net/en-us/eula) | Java 版正常购买/游玩与原创 Mod 授权、禁止分发组合后的修改游戏本体、社区规范和账号条件 | 活文档可变；并未规定所有私人服一致的自动化账号披露格式，更非允许规避目标服规则 |
| [Minecraft Usage Guidelines（2026-09-16 复核）](https://www.minecraft.net/en-us/usage-guidelines)及[社区标准](https://www.minecraft.net/en-us/community-standards) | 分发原创 Mod 的限制与多人社区安全边界，可作为服务器准入参考 | 当前服管理员的 bot/矿透/PvP/陷阱规则还须独立取得；人格不覆盖运营规则 |
| [Minecraft 官方账号要求](https://help.minecraft.net/hc/en-us/articles/19615552270221-Accounts-Required-to-Play-Minecraft) | 登录和账号资格的官方说明，2026-09-16 复核 | 未提供 Kin 免手工登陆、长期 token 保存或私服兼容的保证 |
| [Yarn 1.21.4+build.8 ClientPlayNetworkHandler](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayNetworkHandler.html) | `getConnection/isConnectionOpen`及断线相关正常客户端接口，2026-09-16 复核 | 接口存在不证明自行发起正版连接/渲染/图形服务稳定 |
| [Minecraft 快照 23w43a（2023-10-25）](https://www.minecraft.net/en-us/article/minecraft-snapshot-23w43a) | 官方说明玩家模拟默认 20 ticks/s；2026-09-16 复核 | 50ms 是逻辑周期换算，不是输入/网络/图形/水桶救援端到端保证；目标 1.21.4 仍要实测 |
| [OpenTelemetry traces 官方概念（2026-09-16 复核）](https://opentelemetry.io/docs/concepts/signals/traces/) | span 时间事件/属性/link 说明可跨本地动作与异步模型任务记录关系 | 不强制选用远端收集器，原始玩家聊天/坐标/密钥不能因此自动上传 |
| [SQLite 在线备份官方说明](https://www.sqlite.org/backup.html)及[WAL](https://www.sqlite.org/wal.html) | 为单 Kin 本地事件账本的一致性备份和并行查询候选提供出处，2026-09-16 复核 | 非实际负载/故障恢复证明，磁盘、加密、迁移、WAL 清理还要实测 |

其他已有引用分布在 [Alma 参考](alma-reference.md)、[外部工具](external-tools.md)和[自主学习](learning.md)。下一轮核对 Alma/服务器资料和 Fabric 对应版本的 GUI/输入资料后才把版本、许可与适用局限写入此表；未做检索的来源不伪称“已验证”。
