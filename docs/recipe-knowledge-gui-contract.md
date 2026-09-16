# Java 1.21.4 配方：公开知识、账号配方书与真实 GUI 的边界

核对日期：2026-09-16；Minecraft Java 1.21.4 / Yarn `1.21.4+build.8` 同版映射/Javadoc 静态研究，**未建客户端/未核服务器改变配方、未测实际合成**。本页是[世界书知识画像](world-guide-implementation.md)到[正常 GUI 动作](gui-combat-interface-audit.md)的桥梁，不把“模型知道配方”当作“这个账号现在能点一个配方按钮”。

## 三类不同对象

| 对象 | 来源与权限 | 可用于什么，不可用于什么 |
| --- | --- | --- |
| `RecipeKnowledge`：原版通用/版本节点 | 有版本/出处的简短公共知识、Kin 开局进阶知识覆盖、亲历发现或公开网页的待证主张 | 可以提出“木板→工作台”“工具怎么做”等意图；即使 LLM 熟悉机制，低知识角色也先标记猜想/查证，不故意答错；**不能从节点名字造点击配方的会话 ID或宣称已拥有材料** |
| `KnownRecipeDisplay`：当前账号配方书 | [`ClientRecipeBook`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/recipebook/ClientRecipeBook.html)有 `getOrderedResults/getResultsForCategory` 与 add/remove/clear；[`ClientPlayNetworkHandler`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayNetworkHandler.html)列 recipe book add/remove/settings 服务端更新；配方实际存在于**当前登录账号/服务器**的可用显示状态 | 游戏内配方书已经对自己显示的条目可作为知识/GUI 候选；该类内部配方表是 private，不能未经边界审计就把后台同步到客户端但未显示的所有条目当“Kin 亲自学会”。仅用当前可见 GUI 或世界书公开知识构成上层信念，服务器私有数据包仍需实际验证 |
| `CraftTransaction`：当前界面/材料/结果 | 当前已正常打开的 handler，材料、slot/cursor stack、`syncId`、客户端动作和之后同步的自身库存 | 可以按合法槽位点击或当前有效配方入口尝试做物品；任何方法返回、预测输出/游标、配方书文字都**不是**服务器确认的成品 |

同版[`RecipeDisplayEntry`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/recipe/RecipeDisplayEntry.html)明确说明 synced display **不包含 recipe 的稳定 ID**，改用**运行时分配**的[`NetworkRecipeId(int index)`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/recipe/NetworkRecipeId.html)。[交互管理器 `clickRecipe(syncId,NetworkRecipeId,craftAll)`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)可用作当前 GUI 内的候选操作，但配方条目缺失/未解锁、素材不足、会话改变、后台服务端数据包增删/重排序时都必须重查；**不能根据网页教程、旧服或上一轮 `index` 自造 ID 或跨世界持久化**。若当前界面不提供可点击的配方，公开已知配方依然可用于在真实打开的 2×2/3×3  GUI 中**合法摆放实际材料**尝试制作，服务端可能仍拒绝/改过规则。

## 最小闭环与知识成长

`intend("做镐") → resolve public/individual knowledge(version,source,confidence) → inspect actual inventory and opened 2×2/工作台 3×3 handler → if visible usable recipe entry select *current* runtime ID, else manual grid slots based on known/public mechanism → issue one normal GUI action → re-check handler/cursor/materials/result slot → take real result → wait own inventory sync → confirmed/unknown/failed`。遇到未知配方可查看已有配方书、请玩家指点或按[公开查资料契约](research-skill-contract.md)研究；外部攻略/玩家话语不能改变账号权限或执行主机代码。并非每个 `KnownRecipeDisplay` 都要写入个人高知识档案；只有 Kin 亲历发现、理解并再次能描述/使用时才调整知识证据。多次成品成功与错误复盘能更新 GUI 制作技能；**一次知道正确答案只更新知识，不升级实际操作能力**。

版本/服务器迁移时世界书条目仍作为可追溯的公开主张并重新比对当前玩法，`NetworkRecipeId` 一律丢弃；服务器改变配方但未公开时 Kin 可标“旧知识与本服不符”，通过真实 GUI、小范围试验与公开玩家信息修订，不读取私有服务器配方管理接口。在 GUI 正打开且服务端同步的当前配方显示内容与依赖材料信息的使用边界，也须跟[感知政策](perception-policy.md)一起实验验证；不声称 Javadoc 的 private map 就是正常玩家屏幕能看到。

阶段 0 私人原版服实验：正常木板/工作台/木镐 2×2/3×3；新账号无配方书条目但 Kin 知公开知识；书中有条目但库存不够；移出/重新进服与打开另一台工作台导致 ID/GUI 变化；旧攻略错误配方与私服数据包冲突；合成中受击/关窗游标归还。记录 `knowledge_source`、当前 GUI 显示/handler/slot/cursor、配方 ID 来源（**当前会话，不持久化**）、材料消耗、server-confirmed 结果、失败类型和再次成功，分别统计知识命中与真实合成成功；未完成这组实验前**不声称 Kin 已会制作一整套原版物品**。
