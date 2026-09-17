# P0 离线 Session 参数兼容与验收契约

本文解决一个比“有没有正版账号”更底层的问题：Minekin 选择 `auth_mode: offline` 后，受管理 Launcher究竟如何为 Minecraft Java 1.21.4 填充 `--username`、`--uuid`、`--accessToken`、`--clientId`、`--xuid`和 `--userType`，以及怎样证明这组参数只是本地会话材料而不是伪造的在线认证。

当前结论仍是**候选兼容设计**，不是已启动结论。

## 三种不同的“账号类型”

必须先分开三个命名空间：

| 名称空间 | 示例 | 含义 |
| --- | --- | --- |
| Minekin Identity Policy | `auth_mode=offline` | Harness选择不执行 Microsoft/Xbox认证，只面向允许离线身份的受控目标 |
| 第三方 Launcher账号模型 | Prism的 `AccountType::Offline` | 启动器内部如何保存/生成账号材料 |
| Minecraft 1.21.4 `Session.AccountType` | `LEGACY`、`MOJANG`、`MSA` | 游戏客户端内部枚举；官方Yarn映射中没有 `OFFLINE` |

同名或相似字符串不能跨命名空间直接等价。Minekin配置可以叫 offline，但不能据此构造一个并不存在的 Java枚举值。

## 已核对证据

### Mojang 1.21.4 元数据

固定 SHA-1版本JSON的 game arguments包含：

```text
--username    ${auth_player_name}
--version     ${version_name}
--gameDir     ${game_directory}
--assetsDir   ${assets_root}
--assetIndex  ${assets_index_name}
--uuid        ${auth_uuid}
--accessToken ${auth_access_token}
--clientId    ${clientid}
--xuid        ${auth_xuid}
--userType    ${user_type}
--versionType ${version_type}
```

这证明模板需要解析这些占位符，不证明离线值应该是什么。LaunchPlan必须保存参数为独立 argv元素，不能拼接 shell字符串；空字符串、缺字段和字符串 `"0"`是不同值。

### Minecraft 1.21.4 客户端映射

[Yarn Session](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/session/Session.html)构造参数包含 username、UUID、accessToken、可选 xuid/clientId 与 AccountType；[AccountType](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/session/Session.AccountType.html)只列 `LEGACY`、`MOJANG`、`MSA`。[Uuids](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/util/Uuids.html)公开 `getOfflinePlayerUuid(nickname)`。

### Prism Launcher固定源码对照

Prism Launcher commit [`a220921`](https://github.com/PrismLauncher/PrismLauncher/tree/a2209210179e156bb2b326e551262f76d94d2010)是成熟开源Launcher的**对照实现**：

- [`MinecraftAccount::createOffline`](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/launcher/minecraft/auth/MinecraftAccount.cpp)把启动器内部类型设为 Offline，把 token设为字符串 `"0"`，生成随机 client token，并用 username生成 profile id；
- 同文件的 `uuidFromUsername`对 `OfflinePlayer:<username>`做MD5并设置UUID v3/IETF位，与原版离线UUID思路一致；
- [`MinecraftAccount::typeString`](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/launcher/minecraft/auth/MinecraftAccount.h)对其内部 Offline返回字符串 `"offline"`；
- [`MinecraftInstance`](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/launcher/minecraft/MinecraftInstance.cpp)把 session的 access token、player name、UUID和 user type填入版本参数模板；同一文件的 profile映射没有 `clientid`或 `auth_xuid`，而 token替换函数会把未命中的占位符替换为空字符串；
- [`EntryPoint`](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/libraries/launcher/org/prismlauncher/EntryPoint.java)与[`AbstractLauncher`](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/libraries/launcher/org/prismlauncher/launcher/impl/AbstractLauncher.java)保留 `param `行的空值，[StandardLauncher](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/libraries/launcher/org/prismlauncher/launcher/impl/StandardLauncher.java)再把参数列表交给 Minecraft main class；
- Prism Launcher本体为[GPL-3.0](https://github.com/PrismLauncher/PrismLauncher/blob/a2209210179e156bb2b326e551262f76d94d2010/LICENSE)。

因此固定 commit 的 Prism parity 已可由源码静态定义：`token=0 + offline UUID + userType=offline + 空 clientId/xuid argv 值`。这里的“空”是 option 后存在的独立空字符串参数，不是省略 option，也不是传入字面 `${clientid}`/`${auth_xuid}`。这仍**不能证明 Minecraft 1.21.4会接受这些值或把字符串 offline解释为同名AccountType**；Minekin只把它作为兼容候选，不复制GPL实现。

## P0 参数模型

Identity Manager产生非秘密的 `OfflineIdentityMaterial`：

```yaml
schema: minekin.offline-identity.v1
local_profile_id: "<stable ref>"
identity_revision: 1
username: "Kin"
uuid_algorithm: "minecraft-offline-v3"
uuid_canonical: "<8-4-4-4-12>"
uuid_id128: "<32 hex>"
credential_kind: "offline-sentinel"
access_token_sentinel: "0"
created_at: "<timestamp>"
```

Launcher再结合固定bundle生成：

```yaml
offline_session_candidate:
  candidate_id: "prism-parity | enum-aligned | diagnostic-default"
  username_argv: "Kin"
  uuid_argv: "<candidate encoding>"
  access_token_argv: "0"
  client_id_argv: "<explicit candidate>"
  xuid_argv: "<explicit candidate>"
  user_type_argv: "offline | legacy | omitted-for-diagnostic"
  secret_classification:
    access_token: "secret-shaped-nonsecret"
    client_id: "secret-shaped-nonsecret"
    xuid: "personal-identifier-shaped"
```

即使离线 sentinel本身不是秘密，这些字段仍按认证字段统一脱敏，避免未来加入 online adapter后因日志schema不同而泄漏真 token。

随机的 launcher client token不等于 Minecraft版本JSON中的 `clientid`。任何实现都不得因为名字相似而把两者自动映射。

## 有界兼容矩阵

| Candidate | `userType` | UUID | token | clientId/xuid | 目的 |
| --- | --- | --- | --- | --- | --- |
| OFF-A Prism parity | `offline` | 原版算法，先测Id128 | `"0"` | 两个option均带显式空字符串argv值 | 验证固定Prism源码路径在1.21.4中的实际Session/日志 |
| OFF-B Enum aligned | `legacy` | 与A相同 | `"0"` | 与A相同的显式空值 | 只改变userType，验证与1.21.4公开AccountType名称对齐的候选 |
| OFF-C UUID form | 采用A/B胜者 | 带连字符canonical | `"0"` | 与胜者相同 | 只在Id128失败或身份不一致时比较解析差异 |
| OFF-D Diagnostic default | 删除整个 `--userType value`对 | 与胜者相同 | `"0"` | 与胜者相同 | 判断客户端默认值；只作诊断，不能悄悄偏离元数据 |
| OFF-N Negative | 明确无效字符串 | 固定正确值 | `"0"` | 固定值 | 证明日志与验收能识别未知类型，不能成为发布候选 |

固定Prism源码链已把 parity 收敛为 clientId/xuid 的**显式空argv元素**。实施时仍应在 dry-run 与启动证据中检查 option/value 边界，保证空值不会让下一项flag被吞作 required argument。只有真实启动对空值产生可归因失败时，才运行 OFFLINE-050 中预先登记的非空 sentinel 对照；不得把未替换的 `${clientid}`、`${auth_xuid}`传给游戏，也不得无限试值。

候选尝试次数由测试计划固定，不能在运行时遇到拒绝后无限排列组合，更不能把服务器拒绝当作授权去尝试在线账号。

## Bridge回报与成功判据

Bridge hello和首快照增加：

```text
identity_candidate_id
session_username
session_uuid
session_account_type
session_xuid_present
session_client_id_present
credential_values_exposed = false
```

不回传 access token、xuid/clientId正文。Launcher保存自身argv摘要，Bridge独立读取客户端实际Session；二者不一致时 `SESSION_MATERIAL_MISMATCH`，不得进入 `PLAYABLE`。

一个候选只有同时满足以下条件才可晋级：

1. Java 21进程正常到 Bridge握手，日志无未替换占位符或参数错位；
2. 客户端Session name/UUID与期望的本地材料一致，AccountType被明确记录；
3. 正常进入受控 `online-mode=false` 1.21.4 dedicated server；
4. 服务端oracle记录的 name/UUID与预期规则可解释，但不回流模型；
5. 重启同一 identity revision结果稳定；
6. online-mode负向目标清楚拒绝，不自动换候选或发起Microsoft认证；
7. 日志、Dashboard、crash report和evidence bundle都没有认证字段正文。

“客户端能到主菜单”只证明参数可解析；“能进离线服”也不证明适用于代理、公网服或所有服务端实现。

## Case set

| Case | 场景 | 断言 |
| --- | --- | --- |
| OFFLINE-001 | 核对Prism固定commit的参数替换与Launcher传递链 | clientId/xuid静态期望均为显式空argv值；dry-run无字面占位符或参数错位；记录源码commit，不复制GPL代码 |
| OFFLINE-010 | OFF-A启动到Bridge | 记录实际Session AccountType与警告；不预设结果 |
| OFFLINE-020 | OFF-B启动到Bridge | 与A使用相同非userType材料，可比较 |
| OFFLINE-030 | A/B分别加入受控offline-mode服 | JOIN+首快照+服务端身份证据完整 |
| OFFLINE-040 | UUID Id128/canonical比较 | 只接受解析稳定且服务端映射可解释的格式 |
| OFFLINE-050 | clientId/xuid空值/sentinel | 无argv错位；Session presence符合预期 |
| OFFLINE-060 | OFF-D/OFF-N | 默认/未知类型行为可检测，不误晋级 |
| OFFLINE-070 | 同名双登录、改名、大小写变化 | 冲突/新revision分类正确，不合并人格根 |
| OFFLINE-080 | online-mode、白名单和封禁 | 分类分别为认证/准入失败，不循环换身份 |
| OFFLINE-090 | 日志、崩溃与Dashboard脱敏 | token/xuid/clientId正文暴露次数为0 |
| OFFLINE-100 | 重启与A→B→A世界切换 | `kin_id`连续，外部身份与world context不串线 |

所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。

## 冻结输出

实验完成后生成 `OfflineSessionProfile.v1`：

```yaml
minecraft: "1.21.4"
bundle_id: "<digest>"
candidate_id: "<winner>"
argv_encoding:
  uuid: "id128 | canonical"
  user_type: "<tested>"
  client_id_policy: "<tested>"
  xuid_policy: "<tested>"
observed_session_account_type: "<actual>"
tested_targets:
  vanilla_offline_dedicated: true
  integrated_lan: "<case result>"
unsupported:
  - "online-mode without explicit adapter"
evidence_bundle: "<digest>"
```

这个profile按 Minecraft/bundle版本绑定，不能自动推广到未来版本。若没有候选通过，结果是 `OFFLINE_SESSION_UNSUPPORTED`并阻断P0，而不是伪造账号或退回协议Bot。

## 不作出的承诺

本文不证明Prism Launcher当前发布版一定使用所核commit，不证明 `userType=offline`或 `legacy`哪个会胜出，不证明token `"0"`适用于在线服务，不证明空xuid/clientId已被客户端接受，也不证明任意offline-mode服务器的身份安全。

本批只把原先模糊的“后面实测sentinel”收敛成有限候选、可观察Session和明确失败结果。
