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
| [OWASP 提示词注入指南](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | 指令与不可信内容分离、最小权限与工具/输出验证的技术参考 | 不能保证“永远无泄漏”，必须用真实对话、网页、记忆和调用的对抗回放 |
| [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)及[OpenAI Agent 注入研究](https://openai.com/index/designing-agents-to-resist-prompt-injection/) | 补充间接注入、外传目标与模型防护不足的威胁分类 | 作为风险与验收设计参考，不能代替 Kin 网关实现与测试 |

其他已有引用分布在 [Alma 参考](alma-reference.md)、[外部工具](external-tools.md)和[自主学习](learning.md)。下一轮核对 Hermes/OpenClaw/Voyager 和 Fabric 对应版本的 GUI/输入资料后才把版本、许可与适用局限写入此表；未做检索的来源不伪称“已验证”。
