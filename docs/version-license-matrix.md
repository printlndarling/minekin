# 1.21.4 试验栈的同版本证据与许可边界

核查：2026-09-16；启动元数据复核：2026-09-17。这是用于决定**首个小原型**的可复核版本矩阵，不是已构建、已入服或锁定整个成品发布版本。Minecraft Java 1.21.4 是候选锚点；客户端图形会话和默认本地身份入服、Baritone 低层缓存玩家等价约束、A/B 模式及游戏动作仍需真实私人测试服运行。

| 组成 | 实际核到的发布/源码/许可 | 目前决定及缺口 |
| --- | --- | --- |
| Mojang 1.21.4 启动元数据 | [version manifest v2](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json) 指向 SHA-1 `d152a3712859b294a2dff641f99a7fe219cd3aec` 的[1.21.4 JSON](https://piston-meta.mojang.com/v1/packages/d152a3712859b294a2dff641f99a7fe219cd3aec/1.21.4.json)：Java 21、client/assets/logging、113 项 libraries、OS/arch rules 与启动参数；2026-09-17 静态核对 | 这是可生成 LaunchPlan 的证据，不是已下载/启动。规则无法求值、摘要缺失或 native 不匹配须阻断；详见[P0 启动计划](p0-launch-plan-contract.md) |\n| Minecraft Java | [1.21.4 官方更新说明](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-4)；[EULA](https://www.minecraft.net/en-us/eula)允许原创客户端 Mod，禁止分发组合后的修改版游戏 | 先在 LAN/offline-mode 匹配版本服务器以本地身份验证；可选在线认证另测。仓库只分发自己的 Bridge/文档，不打包 Minecraft 客户端本体 |
| Java / Loader / Baritone | [Baritone 1.21.4 源码构建参数](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/gradle.properties)：MC 1.21.4、Java 21、Fabric Loader 0.16.9、Baritone 1.13.1；分支当前核到 commit `78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8` | 此 commit 固定**研究快照**而非已信任的最终 release；优先试 Fabric API 构件（[官方 SETUP](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/SETUP.md)区分 API/standalone），试验前对发布包签名、哈希、实际文件名、Gradle 和安全行为再锁 |
| Fabric API | [官方 1.21.4 源码参数](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/gradle.properties)当前指 `0.119.4`、Loader `0.16.9`、MC `1.21.4`；[对应官方 Maven 发布目录](https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/0.119.4%2B1.21.4/)有 JAR、pom 与校验侧车文件；同一源码快照 [ClientTickEvents](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/fabric-lifecycle-events-v1/src/client/java/net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientTickEvents.java)有 START/END，[ClientPlayConnectionEvents](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/fabric-networking-api-v1/src/client/java/net/fabricmc/fabric/api/client/networking/v1/ClientPlayConnectionEvents.java)列 INIT/JOIN/DISCONNECT；[1.21.4 源码许可证](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/LICENSE)为 Apache-2.0 | 优先 `0.119.4+1.21.4` 作为**候选试验构件**（Maven 发布于 2025-08-08），不再把最初查到的 `0.110.5` 当优选；它与 Baritone 的 Loader 参数同为 0.16.9，仍**不等于两者一起运行已兼容**，需原型构建/实跑 |
| Yarn 映射/合法动作 | [Yarn 1.21.4+build.8 交互管理器](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)与[客户端网络处理器](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayNetworkHandler.html)可查 GUI/破坏/战斗/连接状态签名 | 映射仅供研发，不代表动作成功；最终是否用这套 build 以相应 Fabric Loom/Gradle 对照和实际服务端同步结果决定 |
| Baritone 许可证 | [1.21.4 LICENSE](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/LICENSE)为 LGPL-3.0；[同版 README FAQ](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/README.md)允许在自定义客户端作为库使用，条件是符合 LGPL-3.0 | 原文没有找到此前文档所述 “anime exception”，撤销这条未经证实的附加说明。外发时另做动态/静态组合、修改源码、许可文本/权利义务审查；研发期不挪它的源码当自写技能 |
| AltoClef / Meteor | [AltoClef](https://github.com/gaucho-matrero/altoclef)已归档，MIT 且 README 只保证旧版 1.18；其[官方 usage](https://github.com/gaucho-matrero/altoclef/blob/main/usage.md)还有私信控制、`locate_structure`、超亮度等非 Kin 默认许可的命令；[Meteor](https://github.com/MeteorDevelopment/meteor-client) GPL-3.0 与 anarchy utility 用途 | AltoClef 只作任务依赖参考，绝不直接继承私信 Butler/结构定位/亮度及战斗模块；Meteor 不首版集成、不复制源代码，避免不必要的 GPL 与超人行为风险 |

## 首批支持级别

| 级别 | 版本 | 能力声明 |
| --- | --- | --- |
| P0 唯一执行基线 | MC 1.21.4、Java 21、Loader 0.16.9、Fabric API 0.119.4+1.21.4、Yarn 1.21.4+build.8；Baritone 固定研究快照 | 完成构建、渲染、本地身份入服、Bridge/IPC、输入、GUI、退出恢复后才能标 `tested` |
| probe-only | 可识别但无已验证 bundle 的其他协议 | 只报告检测并阻断，不能自动试连 |
| 第二 bundle | 尚未选择 | P0 后按真实需求与可构建性选择，并独立通过同一验收 |

首个原型只有 1.21.4 候选，因此“自动识别”当前主要用于正确选择或可解释阻断，不是假装全版本兼容。

必要开发阶段兼容性实验从**独立 Fabric 小 Mod + 客户端 tick/JOIN/DISCONNECT**开始，再加入 Baritone API，记录 Gradle 完整依赖锁、jar SHA256 和许可证；先比对引入前后的加载、渲染、移动/合法采集与路径隐藏信息，再接 GUI、反射和人格桥接。失败时优先自写玩家式导航/任务局部闭环或换一致可构建的 Minecraft/Fabric/Baritone 组合，并同时迁移[版本世界书](world-guide-implementation.md)；不因现成 Baritone 不合规而放弃可自写方向，也不声称换版本只要改一行。底层库再强也不能取得服主禁止的矿透/战斗权限；运行者按目标服规则处理。

许可说明仅是对仓库原始声明的审阅，不是法律意见；私人研发与未来向他人分发的合规要求不同，分发前复核具体依赖版本、许可证文件与 Minecraft Usage Guidelines。
