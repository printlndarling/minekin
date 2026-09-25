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
| Minekin Bridge | 本仓库自产产物，许可 `NOASSERTION`；1.20.1 的构建产物出自**顶层独立 root `bridge-1201/`**，当前 jar sha256 `e50d61c2…`/1,310,604B（V03 收口时为 `9e162d83…`/1,308,469B，`801f9ba` 后换代） | recipe 按固定 SHA-256 钉住该 jar（不再是 `build_required`）；**不**用 1.21.4 的 digest 冒名，也不因构建成功称 1.20.1 为 `tested`——入服验收属 V04 |

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
  （`.tmp/v03build/v03compile.log`）保留、不猜过。**这四处已在 `bridge-1201/` 按 1.20.1 的拼写落进
  源里并构建通过（见下节），但「能构建」只说明产物存在，不说明 1.20.1 客户端可用——入服验收属 V04。**
- 启动器侧 `recipe.py`、`metadata.py`、`schemas/bundle-manifest.schema.json` 及约 15 个测试把
  1.21.4 身份（版本/ loader / api / java / libraries 数 / native 数 / asset 对象数 / classpath 数）
  做成常量或 `const`。**在不产生 1.21.4 漂移的前提下**把它们改成按版本键入的 pin 表，是
  让 1.20.1 candidate recipe 通过校验的前置 LOCAL 项，仍在本卡允许路径内，此提交不做。
- 因此本卡在 2026-09-25 **收口**：官方供应链逐项核对、可构建性实测取证（上述 1.20.1 编译失败及其
  四处类迁移的定位）、启动器侧无漂移泛化（`recipe.py`/`metadata.py`/`launch_plan.py`/
  `bundle-manifest.schema.json` 按版本键入 pin）、`bridge-1201/` 隔离构建与跨平台复现取证（见下节）、
  以及 candidate recipe 回填后 `bundle verify` 端到端通过，均已完成。**剩余不在本卡**：真实 1.20.1
  入服验收（V04）与把 candidate 提升为 `tested` 的登记（V05 只从 `tested` 里选包）。本卡交付的
  任何一项都未、也不会被记为 `tested`/PASS。

### 1.20.1 Bridge 隔离构建与 SBOM（V03，2026-09-25 实测）

- **顶层独立 source root `bridge-1201/`**（与 `bridge/` 同构、自成一体的 Loom 工程，
  `rootProject.name = minekin-bridge-1201`）。取独立 root 而不是往 `bridge/` 里加 per-version
  源集，是因为 1.21.4 已封 recipe 把 `source_digest = source_tree_sha256(workspace/bridge)`
  钉死了：本卡收口时复算 `bridge/` 仍为 `507f708dc4e3…`，即 1.21.4 的 source identity **一字未动**。
- **产物**：`bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`，1,308,469 字节，
  sha256 `9e162d8359a886394ddd80db87477d9196ef3d2972e7a4d942df54a2f1e349bc`。只有这一个 jar
  进 recipe；同目录的 sources jar 不钉摘要（跨平台复算时它的字节并不稳定）。
  **（2026-09-25 更正：该 jar 摘要与字节数是 V03 收口时的现场，`801f9ba` 让 1.20.1 root 声明自己真实运行的
  版本后已换代为 1,310,604 字节 / `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`。
  新 jar 的跨平台复现做的是三次（Windows `build`、Windows 依赖校验严格 `build`、Linux 容器 `clean build`）
  且逐字节相同；本节 V03 的第四次（`--no-daemon check --rerun-tasks`）未对新 jar 重做。
  读数见主计划 `reproducibility_hello`，本节其余内容不改写。）**
- **跨平台可复现（这一步是量出来的）**：同一棵 1.20.1 源树在 (a) Windows + JDK
  `21.0.12.1+1-LTS-4` 与 (b) `eclipse-temurin:21-jdk-jammy` 容器（`Temurin-21.0.12+8`）各构建
  一次，(b) 又分「空 Gradle 缓存 + `--write-verification-metadata` 记录」与「用合并后的元数据、
  依赖校验**强制**打开、`gradlew build -x checkHostBoundaryArtifacts` 跑绿」两轮，三次 jar 摘要
  逐字节相同。收口当天再加第四次：Windows 上 `./gradlew --no-daemon check --rerun-tasks`（11 个任务
  全部重执行、含 `test`），产物仍逐字节等于同一摘要。1.21.4 那道 pin 当年做过同样的双平台演示、
  此后没再重复；本卡对 1.20.1 重做了它。
- **依赖校验元数据**：`bridge-1201/gradle/verification-metadata.xml` 是两次真实构建记录的**并集**
  ——Windows 903 条 component/artifact 摘要、Linux 冷缓存 918 条，前者经逐条比对
  （group/name/version/artifact/sha256）是后者的真子集，共同条目的摘要**无一条不一致**。
  15 条 Linux-only 全部是平台/解析差异：`org.lwjgl:*:3.3.2` 的 7 个 `natives-linux` jar、
  `net.fabricmc:intermediary:1.20.1` 的 `.pom` 与 `-v2.jar`、`guava-parent-33.0.0-jre.pom`、
  `junit-bom` 的 4 个 `.module`/`.pom`。两条 `<trust>` 与被审的 1.21.4 版本**同一顺序、同一字面**
  （Loom 合成命名空间无法钉摘要，原因写在文件内注释块里，该注释块一并保留），`verify-metadata`
  仍为 `true`。
- **依赖锁与版本目录**：`gradle.lockfile`/`settings-gradle.lockfile` + Loom 1.9.2 + Gradle 8.12.1
  wrapper（带 `distributionSha256Sum`）+ `dependencyLocking { lockAllConfigurations() }`；
  loader 0.19.5、Fabric API 0.92.12+1.20.1、Yarn 1.20.1+build.10、protobuf-javalite 4.36.2。
- **host-boundary 名单按 root 派生**：`bridge-1201/host-boundary-names.json` 由 1.20.1+build.10
  映射派生（17 个 marker、631 条 intermediary 拼写；`ServerLevel` 为空即该版本候选映射里没有
  `getServer()` 拼写）。沿用 1.21.4 的表会让构建产物门**看不见** 52 个 server-state 拼写——
  这是量出来的（改前/改后对照），并已作为正控写进 `tests/contract/test_bridge_artifact_gate.py`。
- **许可证**：Bridge 自身 `NOASSERTION`（自有产物，按供应链契约用固定 SHA-256 而不以 TLS 作唯一
  完整性保证）；Fabric API Apache-2.0；loom/loader/intermediary/yarn/Mojang 材料/
  protobuf-javalite/lwjgl 与本文件上表 1.21.4 栈同一套条款，逐项见上表。
- **未测与停止点（不猜结论）**：构建镜像里没有 python，`checkHostBoundaryArtifacts` 在 Linux
  真跑里以 `-x checkHostBoundaryArtifacts` 跳过，同一道门由 CI `bridge-static`（uv 提供的解释器）
  与本机各跑一遍；一次冷缓存 Linux 构建因 `libraries.minecraft.net` TLS 抖动失败
  （`.tmp/v03docker4.log` 保留），重试后成功——那是网络瞬断证据，**不是**依赖校验失败；
  1.20.1 的客户端就绪谓词、`--quickPlaySingleplayer`（1.20.2+ 才有的参数）在 1.20.1 的替代、
  以及真服握手/入服，全部留给 V04 的真实运行。本节任何一项都不构成 `tested`。

## 首批支持级别

| 级别 | 版本 | 能力声明 |
| --- | --- | --- |
| P0 唯一执行基线 | MC 1.21.4、Java 21、Loader 0.16.9、Fabric API 0.119.4+1.21.4、Yarn 1.21.4+build.8；Baritone 固定研究快照 | 完成构建、渲染、本地身份入服、Bridge/IPC、输入、GUI、退出恢复后才能标 `tested` |
| probe-only | 可识别但无已验证 bundle 的其他协议 | 只报告检测并阻断，不能自动试连 |
| 第二 candidate bundle | 1.20.1：官方供应链已逐项核对（见上「1.20.1 candidate 供应链核对」），`bridge-1201/` 已独立构建、jar 与 source tree 摘要已回填进 `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json` | 仍**未**入服、未跑过真实 1.20.1 客户端、未晋级 `tested`；入服验收与 `tested` 登记按[跨版本连续执行计划](version-auto-to-server-control-plan.md)的 V04/V05 逐卡核对 |

首个原型只有 1.21.4 候选，因此“自动识别”当前主要用于正确选择或可解释阻断，不是假装全版本兼容。

必要开发阶段兼容性实验从**独立 Fabric 小 Mod + 客户端 tick/JOIN/DISCONNECT**开始，再加入 Baritone API，记录 Gradle 完整依赖锁、jar SHA256 和许可证；先比对引入前后的加载、渲染、移动/合法采集与路径隐藏信息，再接 GUI、反射和人格桥接。失败时优先自写玩家式导航/任务局部闭环或换一致可构建的 Minecraft/Fabric/Baritone 组合，并同时迁移[版本世界书](world-guide-implementation.md)；不因现成 Baritone 不合规而放弃可自写方向，也不声称换版本只要改一行。底层库再强也不能取得服主禁止的矿透/战斗权限；运行者按目标服规则处理。

许可说明仅是对仓库原始声明的审阅，不是法律意见；私人研发与未来向他人分发的合规要求不同，分发前复核具体依赖版本、许可证文件与 Minecraft Usage Guidelines。
