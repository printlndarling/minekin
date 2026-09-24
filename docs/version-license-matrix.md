# 1.21.4 试验栈的同版本证据与许可边界

核查：2026-09-16；启动元数据复核：2026-09-17。这是用于决定**首个小原型**的可复核版本矩阵，不是已构建、已入服或锁定整个成品发布版本。Minecraft Java 1.21.4 是候选锚点；客户端图形会话和默认本地身份入服、Baritone 低层缓存玩家等价约束、A/B 模式及游戏动作仍需真实私人测试服运行。

| 组成 | 实际核到的发布/源码/许可 | 目前决定及缺口 |
| --- | --- | --- |
| Mojang 1.21.4 启动元数据 | [version manifest v2](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json) 指向 SHA-1 `d152a3712859b294a2dff641f99a7fe219cd3aec` 的[1.21.4 JSON](https://piston-meta.mojang.com/v1/packages/d152a3712859b294a2dff641f99a7fe219cd3aec/1.21.4.json)：Java 21、client/assets/logging、113 项 libraries、OS/arch rules 与启动参数；2026-09-17 静态核对 | 这是可生成 LaunchPlan 的证据，不是已下载/启动。规则无法求值、摘要缺失或 native 不匹配须阻断；详见[P0 启动计划](p0-launch-plan-contract.md) |
| Minecraft Java | [1.21.4 官方更新说明](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-4)；[EULA](https://www.minecraft.net/en-us/eula)允许原创客户端 Mod，禁止分发组合后的修改版游戏 | 先在 LAN/offline-mode 匹配版本服务器以本地身份验证；可选在线认证另测。仓库只分发自己的 Bridge/文档，不打包 Minecraft 客户端本体 |
| Java / Loader / Baritone | [Baritone 1.21.4 源码构建参数](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/gradle.properties)：MC 1.21.4、Java 21、Fabric Loader 0.16.9、Baritone 1.13.1；分支当前核到 commit `78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8` | 此 commit 固定**研究快照**而非已信任的最终 release；优先试 Fabric API 构件（[官方 SETUP](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/SETUP.md)区分 API/standalone），试验前对发布包签名、哈希、实际文件名、Gradle 和安全行为再锁 |
| Fabric Loader / Bridge 装配 | [Loader 0.16.9 tag commit](https://github.com/FabricMC/fabric-loader/commit/083a4dc339655bddec498ffd75f13580d9b9722d)、[mod discovery](https://github.com/FabricMC/fabric-loader/blob/083a4dc339655bddec498ffd75f13580d9b9722d/src/main/java/net/fabricmc/loader/impl/FabricLoaderImpl.java)、[client hooks](https://github.com/FabricMC/fabric-loader/blob/083a4dc339655bddec498ffd75f13580d9b9722d/minecraft/src/main/java/net/fabricmc/loader/impl/game/minecraft/Hooks.java)及[1.21.4 mod 结构](https://github.com/FabricMC/fabric-docs/blob/53dd9650e7ecb3566b03bfe260556407b5ff4267/versions/1.21.4/develop/getting-started/project-structure.md) | 拆成 `p0-core`（API+Bridge）与后续 `p0-nav-exp`（再加 Baritone）；同步 entrypoint 不得等待 IPC。须真实 Loader/主菜单/入服测试，见[Bridge 契约](p0-bridge-bootstrap-contract.md) |
| Fabric API | [官方 1.21.4 源码参数](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/gradle.properties)当前指 `0.119.4`、Loader `0.16.9`、MC `1.21.4`；[对应官方 Maven 发布目录](https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/0.119.4%2B1.21.4/)有 JAR、pom 与校验侧车文件；候选 aggregate JAR 的 SHA-256 sidecar 为 `d183bacb845167f09264c2f90322b7ecffe8826debda6f60e597889264bef4af`；同一源码快照 [ClientTickEvents](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/fabric-lifecycle-events-v1/src/client/java/net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientTickEvents.java)有 START/END，[ClientPlayConnectionEvents](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/fabric-networking-api-v1/src/client/java/net/fabricmc/fabric/api/client/networking/v1/ClientPlayConnectionEvents.java)列 INIT/JOIN/DISCONNECT；[1.21.4 源码许可证](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/LICENSE)为 Apache-2.0 | 优先 `0.119.4+1.21.4` 作为**候选试验构件**（Maven 发布于 2025-08-08），不再把最初查到的 `0.110.5` 当优选；它与 Baritone 的 Loader 参数同为 0.16.9，仍**不等于两者一起运行已兼容**，需原型构建/实跑 |
| Yarn 映射/合法动作 | [Yarn 1.21.4+build.8 交互管理器](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)与[客户端网络处理器](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayNetworkHandler.html)可查 GUI/破坏/战斗/连接状态签名 | 映射仅供研发，不代表动作成功；最终是否用这套 build 以相应 Fabric Loom/Gradle 对照和实际服务端同步结果决定 |
| Baritone 许可证 | [1.21.4 LICENSE](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/LICENSE)为 LGPL-3.0；[同版 README FAQ](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/README.md)允许在自定义客户端作为库使用，条件是符合 LGPL-3.0 | 原文没有找到此前文档所述 “anime exception”，撤销这条未经证实的附加说明。外发时另做动态/静态组合、修改源码、许可文本/权利义务审查；研发期不挪它的源码当自写技能 |
| AltoClef / Meteor | [AltoClef](https://github.com/gaucho-matrero/altoclef)已归档，MIT 且 README 只保证旧版 1.18；其[官方 usage](https://github.com/gaucho-matrero/altoclef/blob/main/usage.md)还有私信控制、`locate_structure`、超亮度等非 Kin 默认许可的命令；[Meteor](https://github.com/MeteorDevelopment/meteor-client) GPL-3.0 与 anarchy utility 用途 | AltoClef 只作任务依赖参考，绝不直接继承私信 Butler/结构定位/亮度及战斗模块；Meteor 不首版集成、不复制源代码，避免不必要的 GPL 与超人行为风险 |

## 1.20.1 candidate 供应链核对（V03，2026-09-25 静态核对）

以下是 V03 对**第二 bundle 1.20.1** 逐项从官方上游核对到的事实，均给出可复核来源与摘要。
它们只证明「元数据存在且摘要已核」，**不**证明已构建、已入服或可 `tested`；candidate 的
构建与真实验收分别是本卡剩余项与 V04。所有条目默认仅 `candidate`。

| 组成 | 实际核到的发布/源码/许可 | 决定与缺口 |
| --- | --- | --- |
| Mojang 1.20.1 启动元数据 | [version manifest v2](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json) 指向 SHA-1 `599695fee750ab157846886c6e69583003f22d07` 的 [1.20.1 JSON](https://piston-meta.mojang.com/v1/packages/599695fee750ab157846886c6e69583003f22d07/1.20.1.json)（releaseTime 2023-06-12，本地下载后 `sha1sum` 复算即此值）：`mainClass=net.minecraft.client.main.Main`、`javaVersion.majorVersion=17`（`java-runtime-gamma`）、88 项 libraries、assetIndex、client/logging | 可据以生成 recipe，但 recipe/metadata 层当前把 1.21.4 的 libraries 数、native 数、asset 对象数等做成常量，泛化到 1.20.1 是本卡剩余 LOCAL 项，不在此伪造 |
| Minecraft Java 1.20.1 客户端 | 官方 client.jar 位于 [piston-data](https://piston-data.mojang.com/v1/objects/0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838/client.jar)，SHA-1 `0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838`、大小 23,028,853；[EULA](https://www.minecraft.net/en-us/eula) 允许原创客户端 Mod、禁止分发改后游戏本体 | 仓库不打包 Minecraft 本体；真实下载/校验并入服在 V04 |
| 资产索引 | 1.20.1 JSON 内 `assetIndex.id=5`、[5.json](https://piston-meta.mojang.com/v1/packages/78fe335ef048443d060bc53ace10bb0f41af7d50/5.json) SHA-1 `78fe335ef048443d060bc53ace10bb0f41af7d50`、大小 413,067 | 1.21.4 用的是 asset-index 19，两套不同，candidate 需各自的本地 fixture 与 digest 门禁 |
| Fabric Loader | [meta.fabricmc.net](https://meta.fabricmc.net/v2/versions/loader/1.20.1) 对 1.20.1 报告最新 stable 为 `0.19.5`；[jar](https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.19.5/fabric-loader-0.19.5.jar) SHA-1 `ff9e65cffca4a67f31523e1807fe0855940fcbfa`、大小 1,984,980；intermediary `net.fabricmc:intermediary:1.20.1` [jar](https://maven.fabricmc.net/net/fabricmc/intermediary/1.20.1/intermediary-1.20.1.jar) SHA-1 `97d0bff94981e37bd7a4362deee53c9a84e3fb21`、大小 573,365 | candidate 选 stable `0.19.5`（1.21.4 已封的是 `0.16.9`）；loader 版本是**可复核选择**而非既成 tested 事实，跨版本是否复用同一 Bridge 见下方可构建性评估 |
| Fabric API | maven-metadata 中 1.20.1 线最新 release `0.92.12+1.20.1`；[jar](https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/0.92.12%2B1.20.1/fabric-api-0.92.12+1.20.1.jar) SHA-1 sidecar `3e9cdd3e2f827ca9a259df9eb8e31949437b6bd4`（下载后 `sha1sum` 复算即此值）、大小 2,137,232、自算 SHA-256 `4197ff4fbdac13cffccd267c1bc59e9fbabb2b5683a9d5f8023f4b5ea16a1c1e`；源码 [LICENSE](https://github.com/FabricMC/fabric-api) 为 Apache-2.0 | SHA-256 是 recipe 的强断言、SHA-1 是内容寻址缓存的键；两者都在此留痕。选该 release 只是可构建候选，不声称与 Bridge/Baritone 同跑已兼容 |
| Yarn 映射 | [meta.fabricmc.net/v2/versions/yarn/1.20.1](https://meta.fabricmc.net/v2/versions/yarn/1.20.1) 最新 `1.20.1+build.10`（`net.fabricmc:yarn:1.20.1+build.10`，Yarn 一律标 stable=false） | 映射仅供研发；最终采用哪套 build 由 Loom/Gradle 对照与真实同步结果决定 |
| Minekin Bridge | 本仓库自产产物，许可 `NOASSERTION`；**尚无 1.20.1 构建产物** | recipe 只能记为 `build_required`、无 digest；不得用 1.21.4 的 jar digest 冒名，也不得凭旧 build 称 tested |

### 可构建性评估与停止点（不猜测，留证据）

- Bridge 是**单模块 Fabric Loom** 工程，版本经 `bridge/gradle/libs.versions.toml` 锁到
  MC 1.21.4 / Loader 0.16.9 / API 0.119.4+1.21.4 / Yarn 1.21.4+build.8，且启用
  `dependencyLocking` 与 `check` 里挂的构建产物边界门（`tools/check_bridge_artifacts.py`）。
  1.20.1 要么参数化 loom 版本、要么建第二个显式 target，并触发真实 1.20.1 反编译/remap。
- Bridge 的 mixin/hook 是按 1.21.4 映射写的，**已在隔离 1.20.1 工程实测：不改源码无法编译**。
  把 `bridge/` + `proto/` 复制到 gitignored `.tmp/v03build/`、仅把 `libs.versions.toml` 的
  minecraft/yarn/loader/fabric-api 换成上表已核对的 1.20.1 值，用本机 Java 21 跑
  `./gradlew --no-daemon -Dorg.gradle.dependency.verification=off compileJava`
  （scratch 副本仍带 1.21.4 的 `verification-metadata.xml`，故只在这份一次性 probe 里关校验；
  真正 commit 的 candidate 须补齐 yarn/intermediary/loader 的 sidecar pin，见上表摘要）。
  下载并对 1.20.1 反编译/remap 后，`compileJava` 出 **15 个「找不到符号/程序包不存在」错误**，
  全部源于 4 处 MC 客户端类在 **1.20.2–1.20.5 之间迁移或新增**，1.20.1 里不存在或换了包：
  1. `net.minecraft.client.gui.screen.multiplayer.ConnectScreen`——1.20.1 该类在
     `net.minecraft.client.gui.screen` 下（`.multiplayer` 子包是 1.20.2 才拆出的），影响
     `MinekinBridgeClient`、`ClientAdmissionController`、`ConnectScreenAccessor`（后者报
     「Mixin has no targets」）；
  2. `net.minecraft.client.network.ClientCommonNetworkHandler` 与
     `net.minecraft.network.packet.s2c.common.DisconnectS2CPacket`——1.20.2 才有 common
     handler/`s2c.common` 包，影响 `CommonDisconnectMixin`（「Mixin has no targets」）；
  3. `net.minecraft.network.DisconnectionInfo`——约 1.20.5 引入，影响 `LoginDisconnectMixin`；
  4. `net.minecraft.client.session.Session`——1.20.1 的 `Session` 在 `net.minecraft.client`
     下（`.session` 子包未存在），影响 `ClientSnapshot`。
  这不是「超出能力契约」的产品决策，而是本卡允许路径点名的「确需版本适配的 hook」：四处仍是
  同一观测面（连接失败/登出原因/登录断开会话），只是 1.20.1 的类名/包/方法签名不同。失败材料
  （`.tmp/v03build/v03compile.log`）保留、不猜过，也不据此称 1.20.1 可构建或 tested。
- 启动器侧 `recipe.py`、`metadata.py`、`schemas/bundle-manifest.schema.json` 及约 15 个测试把
  1.21.4 身份（版本/ loader / api / java / libraries 数 / native 数 / asset 对象数 / classpath 数）
  做成常量或 `const`。**在不产生 1.21.4 漂移的前提下**把它们改成按版本键入的 pin 表，是
  让 1.20.1 candidate recipe 通过校验的前置 LOCAL 项，仍在本卡允许路径内，此提交不做。
- 因此本卡**尚未收 `DONE`**：已完成官方供应链逐项核对、可构建性实测取证（上述 1.20.1 编译
  失败），以及启动器侧无漂移泛化（`recipe.py`/`metadata.py`/`launch_plan.py`/
  `bundle-manifest.schema.json` 按版本键入 pin，candidate recipe fixture 端到端 `bundle verify`
  通过）；剩余是 **Bridge 的 1.20.1 target 版本适配 hook**（上述 4 处类迁移的按版本源集/
  目标切换）与隔离构建产出可复判的 1.20.1 Bridge jar；真实入服属 V04。以上任何一项都未、
  也不会被记为 `tested`/PASS。

## 首批支持级别

| 级别 | 版本 | 能力声明 |
| --- | --- | --- |
| P0 唯一执行基线 | MC 1.21.4、Java 21、Loader 0.16.9、Fabric API 0.119.4+1.21.4、Yarn 1.21.4+build.8；Baritone 固定研究快照 | 完成构建、渲染、本地身份入服、Bridge/IPC、输入、GUI、退出恢复后才能标 `tested` |
| probe-only | 可识别但无已验证 bundle 的其他协议 | 只报告检测并阻断，不能自动试连 |
| 第二 bundle | 1.20.1 已被用户选为下一候选（2026-09-24），官方供应链已逐项核对（见上「1.20.1 candidate 供应链核对」） | 仍**未**独立构建、入服或晋级 `tested`；无漂移泛化与隔离构建是本卡剩余项，按[跨版本连续执行计划](version-auto-to-server-control-plan.md)逐卡核对 |

首个原型只有 1.21.4 候选，因此“自动识别”当前主要用于正确选择或可解释阻断，不是假装全版本兼容。

必要开发阶段兼容性实验从**独立 Fabric 小 Mod + 客户端 tick/JOIN/DISCONNECT**开始，再加入 Baritone API，记录 Gradle 完整依赖锁、jar SHA256 和许可证；先比对引入前后的加载、渲染、移动/合法采集与路径隐藏信息，再接 GUI、反射和人格桥接。失败时优先自写玩家式导航/任务局部闭环或换一致可构建的 Minecraft/Fabric/Baritone 组合，并同时迁移[版本世界书](world-guide-implementation.md)；不因现成 Baritone 不合规而放弃可自写方向，也不声称换版本只要改一行。底层库再强也不能取得服主禁止的矿透/战斗权限；运行者按目标服规则处理。

许可说明仅是对仓库原始声明的审阅，不是法律意见；私人研发与未来向他人分发的合规要求不同，分发前复核具体依赖版本、许可证文件与 Minecraft Usage Guidelines。
