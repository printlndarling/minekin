# 首轮客户端底座核查：选择实验基线，不预装作弊动作

核查日期：2026-09-15；P0 Bridge 装配复核：2026-09-17。这里解决“先用什么版本、哪些底座值得试”的**开工前研究问题**，已固定 P0 1.21.4 candidate，但未构建 Kin，也没有用默认本地身份在 LAN/offline-mode 真客户端验证入服、寻路或合成。原版生存指服务器玩法；Minekin 产品本体采用独立 Runtime/Harness，客户端内的 Fabric 代码只是薄 Bridge。技术上它仍是 Client Mod 构件，但不承载 Soul、Memory、LLM 或 Dashboard，也不表示允许模组游戏内容。客户端不是由用户桌面启动器人工打开，而由 Minekin 自带后端按[受管理客户端契约](managed-client-runtime.md)下载校验、隔离启动并自动选择已验证版本包。

## 版本与构件取舍

固定 Minecraft Java `1.21.4` + Java `21` 作为**第一个 `candidate` Client Bundle 的兼容性实验基线**，因为 [Baritone 该分支的 gradle.properties](https://github.com/cabaletta/baritone/blob/1.21.4/gradle.properties)明确给出该目标和 Fabric Loader `0.16.9`。它不要求用户往后永远玩旧版；若实验发现该版本与 Fabric API、运行账号或服务器环境冲突，切换到能一起构建和运行的版本，再重建对应[原版世界书](world-guide.md)。Fabric [官方事件指南](https://docs.fabricmc.net/develop/events/)给出事件回调、客户端 tick 和必要时 Mixin 的接入点，但官网默认展示更新版本的 API；方法和具体类签名都要对 `1.21.4` 重核，不把最新示例直接复制进旧版工程。

| 候选 | 证据 | 本轮决定与理由 |
| --- | --- | --- |
| 薄 Fabric Client Bridge | [Fabric events](https://docs.fabricmc.net/develop/events/) | 保持首发客户端接管路线；仅负责本地 tick 反射、过滤观察、输入仲裁和反馈，经本机认证 IPC 接受独立 Runtime 的版本化 intent；不在 Bridge 中实现人物心智 |
| Baritone Fabric API 构件 | [SETUP](https://github.com/cabaletta/baritone/blob/1.21.4/SETUP.md)、[USAGE](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md) | 值得优先尝试导航/已知目标交互，其他 mod 集成应选择 API 构件而不是 standalone；命令有误入公屏风险，不用聊天接口驱动 Kin |
| AltoClef | [归档 README](https://github.com/gaucho-matrero/altoclef) | 以获得资源/任务依赖/生存规划为设计参考；官方仓库自述支持的原版 `1.18`，故不能设为 1.21.4 必装任务层 |
| Meteor | [README 及许可说明](https://github.com/MeteorDevelopment/meteor-client) | 不进入首期必需依赖：目标为 anarchy utility，GPL-3.0 与可能的自动战斗/感知超界都和当前私有规划项目的开放许可/玩家等价要求存在冲突；可独立研究正常生存动作思想，不复制源码 |
| 自写局部技能 | Fabric 客户端接入的候选架构；能力未实测 | 对 GUI 合成、拾物、盾牌、目标跟踪、建造等缺失接口允许自写；技能必须对真实客户端发正常移动/转视角/使用/容器操作，并从库存/世界反馈核对结果 |

## 需要做的最小验证，而不是一句“框架已成熟”

1. 同一本地身份 profile 和指定 LAN/offline-mode 私人测试服：正常入服，客户端能获得本人 HUD/背包、聊天与**经过过滤**的可见实体，Fabric 控制器每客户端 tick 能记录事件；异常退出/再登不复制身份。服务器规则及自动化账号的世界外披露由运行者负责。
2. 对同一已见树，分别测试导航目标、走位、转视角、持续合法破坏、拾取、库存核验与被其他玩家挡路后的停止/恢复。Baritone `legitMine` 的上游使用说明不是画面可见性保证；[固定源码审计](baritone-perception-audit.md)指出近域方块状态读数与目标可达性判断仍存在。需同时检查导航路径探索、矿点发现、方块缓存和最终目标消费链；未证明可严格隔离时只以已观察目标测试导航，并自写受限目标发现/寻路，不让墙后矿点成为人物信念或执行目标。
3. 打开真实工作台/背包 GUI，选择公开配方、逐步合成并以库存核验，记录配方/点击/客户端与服务器同步的失败。寻路命令不能代替 GUI/拾取成功；未知接口则先自写最小操作，不假报拥有整套 400+ 物品任务库。
4. 对反射与战斗，实测 Fabric tick 触发至首次输入、目标视野/遮挡和正常旋转速度。不能为了避免模型延迟打开 Meteor 的 KillAura 或直接读 360°实体精确坐标；本地反射独立于云端模型运行，成功与失败均留回放。
5. 冻结可重现的版本矩阵：游戏版本、Fabric Loader/API、Baritone API 的源码 commit 或可信发布包哈希、Java/Gradle、测试服类型与规则。把直接链接、修改分发与附带许可证作为发布前检查项；Baritone [同版源码许可](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/LICENSE)是 LGPL-3.0，当前 README 未找到以前所说的附加例外；Fabric API [1.21.4 LICENSE](https://github.com/FabricMC/fabric-api/blob/1.21.4/LICENSE)为 Apache-2.0；Meteor [GPL-3.0](https://github.com/MeteorDevelopment/meteor-client/blob/master/LICENSE)，AltoClef [MIT](https://github.com/gaucho-matrero/altoclef/blob/main/LICENSE)。具体版本和前提见[版本/许可矩阵](version-license-matrix.md)；这里不是最终法律结论。

**决策结论**：产品形态为独立 Kin Runtime/Gateway + Web Dashboard + 自带 Launcher/Identity/Version 后端；Minecraft 侧加载薄 Fabric Bridge。先以 `p0-core`（Fabric API + Bridge）证明身体闭环，再以独立 `p0-nav-exp` 试 Baritone；自写缺失动作，AltoClef 借设计，Meteor 暂不集成。详见[P0 Thin Bridge 契约](p0-bridge-bootstrap-contract.md)。这是证据支持的实验路线，**未达到“已经具备技术底座、可以开发完整 Kin”的确认等级**。后续核查与风险见[研究台账](research-tracker.md)，证据索引见[参考资料](references.md)。
