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

**（2026-09-24 冻结补充）**这份清单里 `identity_candidate_id` 的承担者不是客户端：客户端看得见自己拿到的 argv，看不见产生这组 argv 的 reviewed 策略叫什么，因此线缆上该字段恒为空串（`ClientSnapshot` 传空 candidate id，`compare_session_material` 也据此只在「报了不同的名字」时拒绝）。候选归因改由 Core 的两条记录共同承担——测试域 argv 与被点名的候选、以及 Core 自己那条身份账本行——判据与反例见「OFFLINE-010 / 020 / 030 的可复判证据边界」。其余六个字段确实由客户端上报，`session_account_type` 按观测值原样承载、不预设。

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
| OFFLINE-001 | 核对Prism固定commit的参数替换与Launcher传递链 | clientId/xuid静态期望均为显式空argv值；dry-run无字面占位符或参数错位；记录源码commit，不复制GPL代码 **（2026-09-22：已定义、跑得动——`tests/fixtures/cases/offline-001.json`，五条断言全部由 `tests/unit/test_offline_session.py` 的现有用例执行，`run_repo_case.py` 跑出 `PASS` 5/5。第三条（记录源码 commit、不复制 GPL 代码）是做法说明而不是判据，契约自己写着 Prism 是「对照实现」；这一条因此没有断言。`mandatory` 仍是 `false`，因为同一个族的 010/020/030/060/070/080/090 要真实启动与入服证据。）** |
| OFFLINE-010 | OFF-A启动到Bridge | 记录实际Session AccountType与警告；不预设结果 **（2026-09-24：判据已冻结，见「OFFLINE-010 / 020 / 030 的可复判证据边界」。缺的那件产品事实是「Core 把自己已经得出的身份比对结论记成自己的账本行」——Bridge 已在报，Core 已在比，但 `BridgeHelloAccepted` 的 payload 是 `{}`、run document 没有身份字段，正向一致什么都不留，只有不一致以 `SESSION_MATERIAL_MISMATCH` 出现。）** **（同日落地补充：上面那件缺的事实已由 `OFFLINE-IDENTITY-LEDGER-FACT-001`（`ec8fb15`）补上——Core 以 `SessionIdentityCompared` 记自己的比对，一次比对一行。本节前四条判据因此各有 `tools/assert_case_evidence.py` 里的一条断言承载，`tests/fixtures/cases/offline-010.json` 把它们的 version 记进 case version。`run_repo_case.py` 对这份 fixture 跑出 `INCOMPLETE` + 四条 `NO_IMPLEMENTATION`：运行材料的判据在纯仓库运行下的正确读数就是「仓库里没有跑得动的东西」，与 `ADMIT-070` 同形。封一份真的证据是 `OFFLINE-IDENTITY-RUN-001`。）** **（`OFFLINE-IDENTITY-RUN-001` 封证落地：OFF-A 已在受控 loopback 服上真跑真封——run `f2ecb728df754826abf4a052be138a2d`、session `d852ccf0ffde42cba3edc25bd72d5766`、`argv_digest 0f4bff0d…`、case version `78053e9e31bfba6c…`、bundle digest `184d636cf028cd05…`，`result PASS`、`failures []`、现场 `evidence verify` 为 `verified: true`；四个读者（live 判读 / `rejudge` / 两次 replay / `report_promotion`）对这一份 bundle 的结论一致。本节前四条判据因此在真实运行材料上各自过了一次：归因那条读到封存的 `orchestrator-trace.json` 里的
`session_argv`，末尾两项是 `--identity-candidate prism-parity`，计数为 1（封的是操作者那一段命令行，
不含 `python -m minekin_core` 前缀——`SEALED-ARGV-001` 已记过这条形状限制）。被否证对照同样在真字节上跑过：把同一份封存材料以 `session_argv=None` 再判一次得到 `LAUNCH_ARGV_UNRECORDED`，把 OFF-B 的 case 喂给这一份 OFF-A bundle 得到 `ARGV_NAMES:prism-parity`。第 5 条（A/B 分别加入）不在这次范围内，原因记在那张卡的收尾里。）** |
| OFFLINE-020 | OFF-B启动到Bridge | 与A使用相同非userType材料，可比较 **（2026-09-24：同上冻结；「可比较」这两列写在同节的对照表里由人读，不放进任何单份 bundle 的判据。）** **（同日落地补充：判据与 `OFFLINE-010` 是同四条、各自一份 fixture（`offline-020.json`），不同的只有归因那条读的是 `enum-aligned`——所以一份 OFF-A 的 bundle 逐条喂给 OFF-B 的判据必须红，这一条有测试钉住。）** **（`OFFLINE-IDENTITY-RUN-001` 封证落地：OFF-B 在同一条受控 loopback 通道上真跑真封——run `3d5606ced37849e3b17a4c418fa33ab4`、session `6e92b314ba0e4ec69ece37b5437cbc2f`、`argv_digest e26e5661…`、case version `ff451ea358546639…`、bundle digest `ff68f67d51ba15af…`，`result PASS`、`failures []`、四个读者一致。跨列假阳性在**真字节**上又跑了一次：OFFLINE-020 的 case 读 OFF-A 的 bundle → `FAIL ARGV_NAMES:prism-parity`，OFFLINE-010 读 OFF-B 的 bundle → `FAIL ARGV_NAMES:enum-aligned`。两列的 `observed_account_type` 实测值不同：OFF-A 是空串、OFF-B 是 `LEGACY`（都按观测原样承载，见下节「两列比较」那一行「不预设」）。契约晋级条件 2 的「AccountType 被明确记录」因此是一次**人读**：判据只保证这个键被记录且是观测值，不替人决定空串算不算「明确记录」。）** |
| OFFLINE-030 | A/B分别加入受控offline-mode服 | JOIN+首快照+服务端身份证据完整 **（2026-09-24：一份 run 只启动一个候选，所以这一行按 `CORE-060` 的先例拆分——`OFFLINE-030-PRISM-PARITY-001` 与 `OFFLINE-030-ENUM-ALIGNED-001` 各自由自己那次 run 的 bundle 满足，`OFFLINE-030` 本身保留与候选无关的那半边。拆分规则、迁移语义与假阳性测试在同节。）** **（同日落地补充：三个 id 都已在 `REQUIRED_CASES` 里并列，各有一份 fixture 与一行 `manifest.sha256`。父 fixture 只登记第 5 条那一条断言，两个子 fixture 各登记本候选的 1/2/3/5 四条——父 id 的断言里没有任何候选归因字段，因此一份 bundle 声称「A 和 B 分别加入」在 registry 这一层就读不出来。迁移语义按本节所述核对，且比预想的干净：`offline-030.json` 在本次登记之前并不存在，这一行从来没有 bundle，所以它 `case_version` 的移动没有历史证据要读作 `UNJUDGED`。）** **（`OFFLINE-IDENTITY-RUN-001` 收尾时如实记下的缺口：本行的第 5 条判据（A/B 分别加入）目前**封不进 harness**。`domain.sh` 把 `MINEKIN_DOMAIN_CASE` 直接小写当作 fixture 文件名，所以 `OFFLINE-030-PRISM-PARITY-001` 会去找 `offline-030-prism-parity-001.json`，而 `CASE-001` 登记的真实文件叫 `offline-030-prism-parity.json`（`-001` 是 required-case id 的后缀，不是文件名的一部分）。两边都不许在本卡里动（runner 在 `forbidden_paths`，fixture/registry 改名在卡外），故记成一张 `QUEUED` 的前置卡 `OFFLINE-030-CASE-FILENAME-001`，本卡的验收 ① 因此只覆盖被真正封出的那四条。父 `OFFLINE-030` 与两个子 case 在此之前的封证状态仍是「没有 bundle」。）** |
| OFFLINE-040 | UUID Id128/canonical比较 | 只接受解析稳定且服务端映射可解释的格式 **（2026-09-22：已定义、跑得动——`tests/fixtures/cases/offline-040.json`，三条断言：canonical 编码可用，且 **argv 里的 id128 与一个 canonical 上报、以及一个大写上报都与记录的身份相同**（`tests/unit/test_offline_session.py` 与 `tests/unit/test_session_material.py`）。「服务端映射可解释」那一半属运行材料，故 `mandatory` 仍为 `false`。）** |
| OFFLINE-050 | clientId/xuid空值/sentinel | 无argv错位；Session presence符合预期 **（2026-09-22：已定义、跑得动——`tests/fixtures/cases/offline-050.json`，三条断言都是*声明*那一侧：空值必须仍挂在自己的 option 上（否则下一个 flag 会被吞成它的值）、空的环境变量在到达 argv 之前就被拒、候选文档报 presence 而不报值。「Session presence 符合预期」要的是**真实 Session 的**presence（Bridge 上报的那一份），所以那半边仍在运行材料那一边；非空 sentinel 对照契约也写明只在真实启动产生可归因失败时才跑。）** |
| OFFLINE-060 | OFF-D/OFF-N | 默认/未知类型行为可检测，不误晋级 |
| OFFLINE-070 | 同名双登录、改名、大小写变化 | 冲突/新revision分类正确，不合并人格根 |
| OFFLINE-080 | online-mode、白名单和封禁 | 分类分别为认证/准入失败，不循环换身份 |
| OFFLINE-090 | 日志、崩溃与Dashboard脱敏 | token/xuid/clientId正文暴露次数为0 |
| OFFLINE-100 | 重启与A→B→A世界切换 | `kin_id`连续，外部身份与world context不串线 |

所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。

## OFFLINE-010 / 020 / 030 的可复判证据边界（2026-09-24 冻结）

这一节不新增产品要求，只回答一个问题：上面 Case set 里 `OFFLINE-010`、`OFFLINE-020`、
`OFFLINE-030` 那三行，要由**哪一份封存工件**、**哪一个判官字段**来判，以及哪些结论**必须由
两次独立运行各自证明**。它的形状与 `p0-remote-admission-contract.md` 的「ADMIT-040 / ADMIT-060 /
ADMIT-070 的可复判证据边界」三节相同：每条判据都写成 `可信来源 → sealed artifact → 判官字段 →
反例`，读不出来的东西不写成判据。

### 先说清现在读不出来的那一件

Bridge 已经在报，Core 已经在看，**但没有任何一份工件留下痕迹**。逐条对物核对：

- 线缆上有 `SessionIdentityReport`（`identity_candidate_id`、`session_username`、`session_uuid`、
  `session_account_type`、`session_xuid_present`、`session_client_id_present`、
  `credential_values_exposed`），由 `ClientSnapshot` 通过 `SessionIdentityReportAdapter` 从活
  Session 读出并随 hello 与首快照发出；脱敏是结构性的——该 message 没有承载 token/xuid/clientId
  正文的字段。candidate id 恒为空串，这是**诚实的值**：客户端看得见自己拿到的 argv，看不见产生
  这组 argv 的 reviewed 策略叫什么。
- Core 在首快照准入时把它与 Launcher 记录的 `RecordedSessionMaterial` 比一次
  （`compare_session_material`），结论是 `SessionMaterialVerdict`，注释写着「evidence 可以原样
  记录」。但**它没有被记到任何地方**：`BridgeHelloAccepted` 账本行的 payload 是 `{}`，
  `SessionStateTransitioned` 只有 `{from,to}`，run document 没有任何身份字段，
  `asserter-inputs.json` 只有 `kin_id/run_id/username/previous_run_id`（那个 `username` 是
  harness 给的，不是客户端报的）。
- 于是今天 bundle 里唯一与身份有关的可判读事实是**否定形状**：比对不通过时首快照被拒，
  `snapshot_rejections` 里出现 `SESSION_MATERIAL_MISMATCH`。一份「身份正确」的运行什么都不留。
  这条不对称就是本节要堵的洞：不堵，`OFFLINE-010/020/030` 只能靠「没报错」通过，而没报错与
  根本没读身份材料是同一个读数。

缺口在 Core 的记录侧，不在 Bridge。补它是一张产品事实卡（`OFFLINE-IDENTITY-LEDGER-FACT-001`）的
范围：把 Core 已经得出的那个结论，以 Core 自己的账本行（`source=CORE`、`trust_class=CORE`）记
下来。§6 的说法在这里仍然成立——**自己声明的不算事实**，所以 candidate id 由 Core 的启动记录
承担，AccountType 由 Bridge 的观测承担，判官核对的是这两者一致。

### 两列比较：同一套判据在 OFF-A 与 OFF-B 上各自要读到什么

| 待证事实 | OFF-A `prism-parity` | OFF-B `enum-aligned` | 承担它的来源 → 工件 → 字段 |
| --- | --- | --- | --- |
| 本 run 启动的就是这一列的候选 | argv 里 `--identity-candidate prism-parity` | 同左，值为 `enum-aligned` | 测试域 argv → `orchestrator-trace.json` 的 `session_argv` → 恰好一次该 option 且值等于本 case 点名的候选 |
| Core 自认为启动的是哪个候选 | 同 A 列 | 同 B 列 | Core 的记录 → 新账本行 → `identity_candidate_id` |
| 客户端 argv 的 `--userType` 元素 | `offline`（启动器自己的词，不是客户端枚举名） | `legacy`（客户端枚举里存在的名字） | 只有摘要进 bundle：run document 的 `argv_digest` 与 `SessionProcessStarted` 的 `argv_digest` 互相核对；两列**必然**得到不同摘要，但摘要本身不声明是哪一个 |
| 除 `userType` 之外材料与另一列相同 | username/uuid/token/clientId/xuid 与 B 列一致 | 同 | 由两列各自的记录材料 + 各自的 argv 摘要承担；**跨列比较不由任何单份 bundle 判定**（见下） |
| 客户端真实 Session 的 username 与 uuid | 等于本地离线材料 | 等于本地离线材料（同一 username，故两列相同） | Bridge 观测 → 新账本行 → `session_username`、`session_uuid` 与 `mismatches` 不含 `username`/`uuid` |
| 观测到的 `AccountType` | **不预设**：可为空，可为 `LEGACY` 或其它 | **不预设** | 同上 → `observed_account_type` 原样承载；判据只问它有没有被记录、记的是不是观测值 |
| `clientId`/`xuid` 的 presence 边界 | 声明为「option 在、值为空」→ 上报 `*_present=false`，且客户端确实起得来、握得上手 | 同 | 同上 → 两个 presence 布尔 + `BridgeHelloAccepted` 在场 |
| 服务端观察到的身份 | usercache 的 name/uuid 与离线算法推导一致 | 同（同一 username ⇒ 同一推导结果） | 服务端自己的文件 → `server/usercache.json` + `server/server.log` → 既有判据 `server_observed_join_identity` |
| JOIN 与首快照 | ledger 恰好一条 `JoinObserved`（`BRIDGE`/`BRIDGE_FILTERED`）且首快照被准入 | 同 | ledger + run document（`snapshots_admitted >= 1`，`snapshot_rejections` 不含 `SESSION_MATERIAL_MISMATCH`） |

### 冻结的判据

1. **这一列的候选确实是本 run 启动的**（归因）。测试域侧：`session_argv` 里 `--identity-candidate`
   出现恰好一次，值等于本 case 点名的候选 id；Core 侧：新账本行的 `identity_candidate_id` 与它
   相同。两侧缺任何一侧、或两侧不一致，都不成立。反例：没给该 option（不给就是第一个候选，一份
   声称 OFF-B 的 case 不能靠默认通过）；给了两次；值不在 reviewed 清单里（产品本就拒绝，这样的
   run 不会存在，判官仍要拒绝冒充）；只有 argv 没有 Core 的行；只有 Core 的行而 argv 没要求。
2. **Core 把身份观测与比对结果记成自己的事实**。新账本行的 payload 至少含
   `identity_candidate_id`、`observed_account_type`、`session_username`、`session_uuid`、
   `client_id_present`、`xuid_present`、`mismatches`，并带 `session_id` 与 `generation`。反例：
   payload 缺 candidate id；`mismatches` 非空却同时记 matched（自相矛盾的记录按不成立处理）；
   行属于别的 session 或别的 generation；同一 run 出现两行且值不同；工件里出现任何 credential
   正文键（出现即失败，不看它有没有值）。
3. **客户端 Session 与记录材料一致**。`mismatches` 必须为空，且 `session_username`/`session_uuid`
   等于该 username 的离线推导（canonical 与 id128 两种编码视为同一值——`_canonical_uuid` 已经
   这么做，`OFFLINE-040` 的既有断言钉过它）。反例：uuid 不等；presence 布尔与候选声明的「option
   在、值为空」不符；`report_incomplete`（客户端什么都没报）却仍被封成通过。
4. **`AccountType` 作为观测被记录，值本身不进判据**。契约的晋级条件 2 要的是「被明确记录」，而
   矩阵的存在理由就是查哪种候选会被客户端认下来。反例：字段缺失；字段被写成 Core 推断的值——
   把 argv 里那个 `offline`/`legacy` 抄进观测字段冒充观测，正是这条要拒的形状；用 `AccountType`
   为空或不为空来单独判通过/失败（判据只问记录在不在、是不是观测）。
5. **入服与服务端身份可解释**：本 run 恰好一条 `JoinObserved`、首快照被准入、
   `server_observed_join_identity` 成立，且 `snapshot_rejections` 不含 `SESSION_MATERIAL_MISMATCH`
   与 `NOT_AUTHORITATIVE`。反例：只有服务端日志的 join 行没有 ledger 的 `JoinObserved`（客户端的
   话不是准入）；有 JOIN 但首快照被拒；usercache 的 uuid 与推导不同。

### 哪些结论必须由两次独立 run，以及 `OFFLINE-030` 的拆分规则

- 「A/B 分别加入」**不能由一份 bundle 判**：一次 run 只启动一个候选（`candidate_by_id` 在点名
  不存在的候选时拒绝而不是回退，正是为了让「要 B 却静默拿到 A」封不出 bundle）。所以承载它的
  必须是**两个 case id**，各自被自己那一次 run 的 bundle 满足。
- 拆分沿用 `CORE-060` / `CORE-060-CLIENT-001` / `CORE-060-SERVER-001` 的先例（父 id 保留自己那一
  半边、子 id 各加一条进程边界，三个 id 在 `REQUIRED_CASES` 里并列，且都在被引用的契约里逐字
  出现）：新增 `OFFLINE-030-PRISM-PARITY-001` 与 `OFFLINE-030-ENUM-ALIGNED-001` 两个 required id，
  各自认领上面第 1/2/3/5 条在**该候选**上的读法；`OFFLINE-030` 这个 id 保留下来，含义收窄为
  **与候选无关**的那半边（离线身份在受控 `online-mode=false` 1.21.4 专服入服、服务端身份与离线
  推导一致），一份 bundle 就能满足它——这正是父 id 在 `CORE-060` 里的处境。
- 迁移语义：**没有既有 case id 被改名、被删除或被重新编号**。`OFFLINE-001`/`OFFLINE-040`/
  `OFFLINE-050` 三份 fixture 与它们的 digest 行因此不动；`OFFLINE-030` 的 fixture 需要重新登记
  （它现在要认领的判据变了），这是它自己的 `case_version` 移动，不影响别的 case。新增的两个子 id
  各是独立 fixture、独立 `manifest.sha256` 行。
- 假阳性测试（拆分卡必须先有这些测试再动 registry）：① `OFFLINE-030` 的断言里**不出现**候选归因
  字段，因此一份 bundle 不能同时被声称证明「A 和 B 分别加入」；② 一份 OFF-A 的 bundle 逐条喂给
  `OFFLINE-030-ENUM-ALIGNED-001` 的归因判据必须红；③ inventory 测试要求两个子 id 都在 required
  清单里，只满足一个时另一个必须仍出现在 `report_cases.py` 的 `missing` 里；④ 两个子 id 的 case
  version 相互独立，改一条不移动另一条。
- 跨 run 的比较（「A 与 B 除 userType 外材料相同」「A 得到 X 而 B 得到 Y」）写在本文这两列表里，
  由人读、由实现卡的 fixture 注记指向本节；**不放进任何单份 bundle 的判据**，也不允许判官去读
  活目录里的另一份 run。要机器核对，只能核对两份**已封存**的 bundle，那是 `EVIDENCE-SEQUENCE-001`
  的形状，不属本场景。

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

**（2026-09-24：这份 profile 仍是模板，上面的尖括号占位符一个都没有填。**`OFFLINE-IDENTITY-RUN-001` 封出了两列各自的真实 bundle（见 Case set 的 `OFFLINE-010`/`OFFLINE-020` 两行），但它按自己的 `non_goals` 明确不挑胜出候选——`candidate_id: "<winner>"` 要的是晋级决定，而晋级条件 2 在这一版里是人读。已经能对物填的只有观测本身：`observed_session_account_type` 在 OFF-A 读为空串、在 OFF-B 读为 `LEGACY`，两列的 `evidence_bundle` digest 也各自存在。它们记在两行的注记里而不是这里，因为这一块是「实验完成后生成」的输出，填它等于宣布实验完成。）**

## 不作出的承诺

本文不证明Prism Launcher当前发布版一定使用所核commit，不证明 `userType=offline`或 `legacy`哪个会胜出，不证明token `"0"`适用于在线服务，不证明空xuid/clientId已被客户端接受，也不证明任意offline-mode服务器的身份安全。

本批只把原先模糊的“后面实测sentinel”收敛成有限候选、可观察Session和明确失败结果。
