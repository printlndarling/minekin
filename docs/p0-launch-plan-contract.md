# P0 1.21.4 启动计划与离线身份契约

核查时间：2026-09-17。本文把首个受管理客户端 bundle 从“可以下载若干文件”收敛为可生成、可审计、失败即阻断的启动计划。它是静态设计与上游元数据核对，不代表 Minekin 已经构建、启动或进入过服务器。

## 结论

P0 只接受一个候选组合：Minecraft Java 1.21.4、Java 21、Fabric Loader 0.16.9、Fabric API 0.119.4+1.21.4、Yarn 1.21.4+build.8、同版 Thin Bridge；Baritone 仍是可拆除的研究候选。Launcher 不需要 Microsoft/Xbox 账号才能组装该 bundle；默认身份面向 LAN 集成世界与运行者明确配置的 offline-mode 私服。online-mode 被拒绝时返回 `AUTH_MODE_MISMATCH`，不得绕过、猜 token 或循环换身份。

## 已核对的上游事实

| 输入 | 2026-09-17 核对结果 | 设计含义 |
| --- | --- | --- |
| [Mojang version manifest v2](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json) | 1.21.4 条目指向带 SHA-1 `d152a3712859b294a2dff641f99a7fe219cd3aec` 的[版本 JSON](https://piston-meta.mojang.com/v1/packages/d152a3712859b294a2dff641f99a7fe219cd3aec/1.21.4.json)，正式发布时间为 2024-12-03 | 版本名不是供应链身份；保存 URL、原始响应摘要与取得时间 |
| 1.21.4 版本 JSON | `mainClass=net.minecraft.client.main.Main`，`javaVersion.majorVersion=21`，113 项 libraries；client JAR SHA-1 为 `a7e5a6024bfd3cd614625aa05629adf760020304`，asset index 19 SHA-1 为 `8d07e20a532738f3ee13392a23871abb5927fd79` | Java major、client、libraries、assets、logging、规则和参数均从固定 JSON 解析，不能手写猜测 |
| [Fabric Meta profile](https://meta.fabricmc.net/v2/versions/loader/1.21.4/0.16.9/profile/json) | `inheritsFrom=1.21.4`，入口为 `net.fabricmc.loader.impl.launch.knot.KnotClient`，追加 8 项库和一项 JVM 参数 | 只覆盖允许的入口/附加项；继承目标不符立即阻断 |
| [Fabric Meta API 说明](https://github.com/FabricMC/fabric-meta/blob/b40c08d703827ed09a54006a48a90c4320f6d05d/README.md) | profile/json 被定义为标准 Minecraft launcher 可用的 profile | 支持采用该端点，但不证明 Minekin 的合并器正确 |
| Fabric Maven | profile 中 Intermediary 与 Loader 项没有内嵌摘要；官方 Maven 有 checksum sidecar，例如 [Intermediary 1.21.4 SHA-1](https://maven.fabricmc.net/net/fabricmc/intermediary/1.21.4/intermediary-1.21.4.jar.sha1) 与 [Loader 0.16.9 SHA-1](https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar.sha1) | 缺摘要不等于允许未校验下载；构建 bundle 前补齐固定摘要 |
| [Yarn Uuids](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/util/Uuids.html) | 同版代码面提供 `getOfflinePlayerUuid(nickname)` 和 `getOfflinePlayerProfile(nickname)` | 可生成确定性的本地候选 GameProfile；服务端/代理观察身份仍须入服后记录 |

Fabric profile 是动态生成的响应，其中时间字段可能变化。Artifact Store 必须同时保存原始响应及摘要；bundle id 则由规范化的语义启动计划、所有实际工件摘要和 Bridge 构建决定，不能因无关时间字段漂移，也不能忽略依赖变化。

## 确定性组装

Launcher 生成 `LaunchPlan`，不直接把下载结果拼成一条不可审计的 shell 命令：

1. 从 manifest 精确选择 `id=1.21.4`，核对版本 JSON 的 SHA-1，再解析版本 JSON。
2. 校验 `javaVersion.majorVersion == 21`；选择已登记的 OS/arch Java 21 build，不接受宿主机任意 `java`。
3. 按版本 JSON 的 rules 计算当前 OS/arch 可用的 base libraries、native artifacts、JVM/game arguments；未知 OS、arch、rule 或 feature 阻断。
4. 获取 Fabric profile，要求 `inheritsFrom == 1.21.4` 且入口恰为已审核的 Knot client。
5. base metadata 是底座；Fabric 只能追加其 profile 中声明的 libraries/JVM/game arguments并替换 main class。相同 Maven 坐标出现不同版本、重复路径或摘要冲突时不自行“取最新版”，而是阻断并要求更新已审核 bundle recipe。
6. Fabric API、Thin Bridge 和可选技能适配器作为固定摘要的 mod 工件进入只读 bundle；不把它们伪装成 Mojang base library。
7. 下载 client、libraries、assets、logging、natives 与 mod 工件到临时区；逐项验证大小及清单摘要。无上游摘要的 Fabric Maven 项必须从已保存 checksum sidecar补齐；仍无摘要则不能发布。
8. 物化只读 classpath/assets/natives/mods 视图，生成规范化 `LaunchPlan` 与 `bundle_id`，原子发布为 `candidate`。
9. 每次启动只创建可写 session overlay；bundle 本体永不原地修改。

P0 不用 quick-play 参数直接入服。客户端先启动并完成 Thin Bridge 的 nonce/bundle/schema 握手；Session Manager 再让 Bridge 连接 Server Profile 中的 host/port。这样未知 Bridge、旧 generation 和错误 bundle 会在接触游戏世界前失败，服务器地址也不必成为模型可见的任意启动参数。

## LaunchPlan 最小字段

```yaml
bundle:
  minecraft: "1.21.4"
  java_major: 21
  os_arch: "linux-x86_64"
  fabric_loader: "0.16.9"
  fabric_api: "0.119.4+1.21.4"
  bridge_build: "<digest>"
  main_class: "net.fabricmc.loader.impl.launch.knot.KnotClient"
artifacts:
  base_metadata_digest: "<digest>"
  libraries: ["<url,size,digest,rule>"]
  assets: ["<index/object digests>"]
  natives: ["<artifact,digest,extract policy>"]
  mods: ["<artifact,digest,license>"]
runtime:
  jvm_args: ["<resolved non-secret args>"]
  game_arg_template: ["<typed placeholders>"]
  classpath: ["<ordered immutable paths>"]
  natives_dir: "<session path>"
  game_dir: "<session overlay>"
identity:
  auth_mode: "offline"
  local_profile_id: "<stable internal ref>"
  username: "<configured name>"
  local_uuid: "<nickname-derived candidate>"
session:
  session_id: "<new>"
  generation: "<monotonic>"
  launch_nonce: "<one time>"
```

序列化清单不得存真实在线 token；在线适配器以后只能在启动瞬间填短期字段，并另做泄漏验收。

## 字段所有权

| 类别 | Launcher 可自动生成 | 必须由运行者/已审核 registry 提供 |
| --- | --- | --- |
| 版本工件 | 固定 manifest 解析、规则求值、URL/大小/摘要、classpath、assets、logging、natives | 允许的 bundle recipe、OS/arch、Java runtime build、Bridge/mod 摘要 |
| 世界连接 | DNS/SRV/status 证据、protocol 候选、连接结果 | Server Profile、host/port、`auth_mode`、版本 pin/自动策略、资源包与服规策略 |
| 离线身份 | 由配置名生成本地候选 profile、非秘密会话占位、session/generation | 唯一 `kin_id`、本地 profile、用户名、该服务器是否明确允许 offline |
| 在线身份 | 默认完全不运行 | 只有显式 `auth_mode: microsoft` 才由独立适配器提供；不属于 P0 离线放行条件 |
| 游戏决策 | 无 | Kin Runtime；Launcher 不根据聊天改配置或权限 |

1.21.4 的 base game arguments仍包含 username、UUID、access token、client id、xuid、user type 等占位符。离线启动计划必须为解析器提供类型正确的**非秘密本地值**，但不得把它们称作有效认证。具体 sentinel 和 `userType` 组合在 P0 启动实验中冻结；未验证前不在文档伪造一条“保证可用”的命令。

## 离线身份与服务端身份

> 完整连接状态、地址解析、身份分层和 ADMIT 验收见[P0 远程入服与离线身份协议](p0-remote-admission-contract.md)。

- `auth_mode: offline`是 Minekin 管理策略，不是原版 `Session.AccountType`；1.21.4 映射只有 `LEGACY`、`MOJANG`、`MSA`。P0 将 `LEGACY`仅作为候选映射实测，不能把枚举名当作已验证的离线启动方案。
- 本地 username 是运行者配置，不从聊天临时改名；首先检查 Minecraft 名称约束与本机 profile 冲突。
- 本地候选 UUID按同版 nickname→offline profile 规则生成，用于客户端自洽；进入 LAN/offline-mode 后，以服务端实际观察到的 name/UUID 建立 `server_observed_identity` 证据。
- 内部人格、记忆与计划仍以 `kin_id` 为根。不同服务器同名、代理改写 UUID、改名或世界切换都不能合并/重建 Kin。
- 状态 ping 不证明服务端认证模式。online-mode 拒绝、白名单、封禁、重复登录与代理错误分别记录，不得统一解释成“版本不对”。
- offline-mode 有冒名风险；管理员权限、白名单和高价值权属不能只靠昵称建立。

## 失败即阻断

| 条件 | 结果码/动作 |
| --- | --- |
| 版本 JSON/hash 不符、工件无可验证摘要、下载大小或摘要错误 | `ARTIFACT_INTEGRITY_FAILED`；隔离临时区 |
| Java 非 21、OS/arch 无匹配 native、规则无法求值 | `RUNTIME_INCOMPATIBLE` |
| Fabric inheritance/main class/库冲突异常 | `PROFILE_MERGE_REJECTED` |
| Bridge/bundle/schema/nonce 不匹配 | `BRIDGE_HANDSHAKE_FAILED`；不给输入 lease |
| 目标协议没有 tested bundle | `UNSUPPORTED_SERVER_VERSION`；只报告 probe |
| offline 身份被在线验证拒绝 | `AUTH_MODE_MISMATCH`；不自动启用 Microsoft |
| 用户名冲突、白名单、封禁、资源包策略或普通登录失败 | 保留原始分类证据；不循环换版本/身份 |
| 客户端启动后未握手、崩溃、黑屏或超时 | 回收进程/显示/按键，bundle 保持 candidate 或进入 quarantine |

## P0 必做实验

1. 全新 Linux x86_64 主机/容器只安装 Minekin 基础服务，自动取得并校验上述工件，不借用 `.minecraft` 或现有启动器。
2. Java 21 + 虚拟显示启动至 Bridge 握手；记录完整解析计划的脱敏摘要、启动时长、RSS/CPU、渲染和错误分类。
3. 分别进入一个 LAN 集成世界和一个受控 offline-mode 1.21.4 私服，记录客户端名、本地候选 UUID、服务端观察身份和重启连续性。
4. 对 online-mode、错误版本、错误 Java、错误摘要、缺 native、重复用户名、白名单和断网做负向测试，必须可解释失败且无无限重试。
5. 连接前强杀 Launcher、启动中强杀 Minecraft、握手后断 Bridge；验证临时区清理、按键释放、旧 generation 拒绝和世界状态重验。
6. 先验收不含 Baritone 的 `p0-core`（Fabric API + Bridge），再独立验收加入 Baritone 的 `p0-nav-exp`；后者失败不阻断 core 或自写技能路线。装配、entrypoint、线程和握手状态机见[P0 Thin Bridge 契约](p0-bridge-bootstrap-contract.md)。
7. 只有上述启动、入服、退出/恢复和最小合法输入完成，且[P0 隔离验证与证据门禁](p0-validation-evidence-contract.md)中的 mandatory case、真值隔离与 evidence bundle 全部满足，P0 bundle 才能从 `candidate` 变为 `tested`；手工演示或单侧日志不能晋级。
8. 跑 ADMIT-001…120，特别核对 `LEGACY`候选 session参数、SRV/地址策略、JOIN与首快照门禁、本地候选身份和服务端观察身份；未通过时不得写“默认离线身份已支持”。

## 不作出的承诺

本文不证明官方工件的再分发权、不证明任意 offline-mode 公网服安全、不证明 profile 合并实现无误、不证明 113 项库都已下载运行、不证明 Linux 渲染或 Bridge 已成功，也不把可下载版本称为全版本自动兼容。当前项目仍处于开发前设计核查，下一阶段首先是受控原型，不是完整 Kin 开发。
