# P0 远程入服与离线身份协议

本文把 `JOIN_REMOTE` 的“启动后怎样进入世界”收敛为可实现、可观测、可失败的 P0 契约。范围只包括受管理的 Minecraft Java 1.21.4 真客户端加入受控 LAN 或 `online-mode=false` 原版服务器；不证明公网离线服安全，不把 Microsoft/Xbox 登录设为默认前提，也不扩张到 HOST 模式。

当前状态是**有官方 API 依据的候选设计，尚未运行**。所有成功率、时延和身份映射必须由真实客户端与独立服务端证据晋级。

## 已核对的原版入口

Yarn 1.21.4+build.8 映射确认：

- [`ConnectScreen.connect(...)`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/gui/screen/multiplayer/ConnectScreen.html)接收父 screen、`MinecraftClient`、`ServerAddress`、`ServerInfo`、quick-play 标志和可选 cookie storage，用于连接 LAN 或远端 dedicated server；
- [`ServerAddress.parse(String)`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ServerAddress.html)解析 host/port，[允许地址解析器](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/AllowedAddressResolver.html)组合普通解析、SRV 重定向和 block-list 检查；
- [`RedirectResolver.createSrv()`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/RedirectResolver.html)说明 vanilla 路径本身具有 SRV 解析步骤；
- [`ServerInfo`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ServerInfo.html)保存服务器地址、类型和资源包策略；类型只有 LAN、OTHER、REALM；
- [`Session`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/session/Session.html)由 username、UUID、access token、xuid/clientId 和 account type 组成，而 [`Session.AccountType`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/session/Session.AccountType.html)只有 `LEGACY`、`MOJANG`、`MSA`，**没有 `OFFLINE` 枚举**；
- [`Uuids.getOfflinePlayerUuid`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/util/Uuids.html)与 `getOfflinePlayerProfile`可生成同版本地候选 profile。

因此，Minekin 的 `auth_mode: offline` 是 Harness/Identity Manager 的策略标签，不等同于客户端 `Session.AccountType`。Prism Launcher固定源码提供 `token=0/userType=offline`的现实对照，而1.21.4公开枚举支持 `LEGACY`候选；二者的有限比较、clientId/xuid与UUID格式见[P0 离线 Session参数兼容契约](p0-offline-session-compatibility-contract.md)。最终组合必须由真实启动与入服证据冻结，不能从任一名称推导“保证可用”。

## 身份分层

| 标识 | 所有者 | 稳定范围 | 是否可作为人格根 |
| --- | --- | --- | --- |
| `kin_id` | Minekin | 跨启动、跨服、跨改名 | 是，唯一人格/记忆根 |
| `local_profile_id` | Identity Manager | 一个本地身份配置版本 | 否 |
| `configured_username` | 受信任配置 | 配置未改名期间 | 否 |
| `local_candidate_uuid` | Launcher | 由固定版离线规则计算 | 否 |
| `session_name/session_uuid/account_type` | 客户端启动会话 | 单进程 session | 否 |
| `server_observed_name/uuid` | 测试服 oracle 或服务器协议结果 | 单服务器身份域 | 否 |
| `actor_id` | World Context | 服务器身份域+观察证据 | 否，只关联关系记录 |

硬规则：

1. 客户端提交的 UUID 不是服务端身份真值；offline-mode 服务端、代理或插件可能按名字重算或改写。
2. 修改 username 生成新的本地 identity revision；不得暗中把服务端眼中的新身份当成旧角色。
3. `kin_id`连续性不依赖昵称或服务端 UUID；世界资产、权限和关系仍须按 server/world/actor context 隔离。
4. 服务器端观察身份只进入验证 evidence；oracle 控制台不得回流 Kin 的 belief、Memory 或行动路径。
5. 仅凭 status ping 不能推断认证模式。online-mode 拒绝、白名单、封禁、重复登录和代理错误分别分类。

## 受信任目标与解析

`ConnectWorld`只能引用后台保存的不可变 Server Profile：

```text
server_profile_id, revision
display_name
original_address
expected_protocol / tested_bundle_id
auth_policy = offline_default | optional_online_adapter
resource_pack_policy
address_policy
connection_timeout
```

聊天、网页正文、知识检索结果和模型输出都不能直接提供 host/port、切换身份、放宽地址策略或接受资源包。管理 API 修改 profile 时产生新 revision并审计。

连接管线为：

```text
trusted profile
→ ServerAddress.parse + syntax/length checks
→ vanilla-compatible DNS/SRV resolution
→ address-policy decision
→ ServerInfo(OTHER or LAN)
→ ConnectScreen.connect on client thread
```

- `quickPlay=false`；P0 不依赖启动器 `--quickPlayMultiplayer`绕过 Bridge 握手。
- cookie storage 在普通 P0 连接中为空；若未来支持服务器 transfer，另立能力与威胁模型。
- 记录原始目标、DNS/SRV 答复摘要、最终 socket endpoint 和 TTL/时间，但 resolved endpoint 不进入模型上下文。
- P0 只允许预先保存的本机、LAN 或隔离测试网 profile；拒绝由不可信文本触发的任意地址、DNS 重绑定后越界、link-local 元数据地址和超出 profile 策略的重定向。
- 每次重连重新解析并重新执行策略；不得永久信任旧 SRV 结果。
- 资源包策略由 Server Profile 固定。意外 prompt 进入阻断/待管理确认状态，不从聊天自动同意。

这是正常客户端连接路径，不是协议 Bot，也不是 GUI 自动点击；是否在虚拟显示上出现 ConnectScreen 不影响控制方式。

## Admission 状态机

```mermaid
stateDiagram-v2
    [*] --> BRIDGE_READY
    BRIDGE_READY --> REQUEST_ACCEPTED: valid profile + generation
    REQUEST_ACCEPTED --> RESOLVING
    RESOLVING --> LOGIN_NEGOTIATING: endpoint allowed
    LOGIN_NEGOTIATING --> PLAY_INIT: protocol login ok
    PLAY_INIT --> JOIN_SEEN: client JOIN
    JOIN_SEEN --> PLAYABLE: first authoritative snapshot
    RESOLVING --> FAILED: invalid / blocked / DNS
    LOGIN_NEGOTIATING --> FAILED: auth / whitelist / protocol
    PLAY_INIT --> FAILED: disconnect / timeout
    FAILED --> BRIDGE_READY: generation closed
    PLAYABLE --> BRIDGE_READY: disconnect
```

每次连接分配不可复用的 `connection_generation`。状态只能由同 generation 的 client-thread 事件推进；旧 DNS future、Netty callback、JOIN、screen callback 或 snapshot 一律只作诊断。

### PLAYABLE 的最小判据

以下条件同时成立才允许高层输入 lease：

1. 当前 generation 收到 Fabric 客户端 PLAY JOIN/等价的 1.21.4 适配事件；
2. `MinecraftClient.world`、本地 player 和 network handler属于同一当前连接且非空；
3. Bridge 发出首个 authoritative snapshot，Runtime 校验 session、generation、server profile revision 和 world-context binding；
4. 当前 screen不处于需要人工/管理决策的资源包、断线或错误状态；
5. 输入仲裁器完成一次全键释放并从 observe-only显式升级。

TCP connect、ConnectScreen状态文字、ping 成功、`ClientPlayNetworkHandler`刚创建或只收到 INIT 都**不等于 PLAYABLE**。服务端 oracle 观察到的 name/UUID 是 candidate→tested 的身份验收证据；它不作为日常模型输入，也不要求为运行时开一条管理旁路。

首快照只含已经批准的客户端本人状态和上下文，例如 generation、服务器 profile revision、维度标识、本地 player存在性、本人位置/速度/生命/饥饿/装备与背包摘要、当前 screen类别、网络是否存活以及协商 capability。它不因此开放墙后实体、未见容器、seed或服务端世界对象。

## 失败、取消与重连

| 阶段 | 稳定分类示例 | 必要动作 |
| --- | --- | --- |
| parse/resolve | `ADDRESS_INVALID`、`DNS_FAILED`、`ADDRESS_POLICY_BLOCKED` | 不创建连接；封存解析证据 |
| TCP/login | `CONNECT_TIMEOUT`、`CONNECTION_REFUSED`、`PROTOCOL_MISMATCH`、`AUTH_MODE_MISMATCH` | 取消当前 channel/future；不猜账号模式 |
| admission | `WHITELIST_REJECTED`、`DUPLICATE_LOGIN`、`RESOURCE_PACK_BLOCKED` | 不授 lease；保留服务端文本为不可信诊断数据 |
| post-JOIN | `FIRST_SNAPSHOT_TIMEOUT`、`WORLD_BINDING_MISMATCH` | 松键、撤 lease、断开当前 generation |
| runtime | `UNEXPECTED_DISCONNECT`、`CONTROL_LOST` | 先撤 lease/松键，再由 Session Manager按有界策略决定重连 |

（2026-09-22：**`CONNECTION_REFUSED` 是补进去的，而在这之前「连接被拒」被记成了 `ADDRESS_INVALID`。** 那不是命名偏好，是**分类落进了错的阶段**：`ADDRESS_INVALID` 属于上面 parse/resolve 那一行，而那一行的必要动作是「不创建连接」——连接被拒恰恰证明**连接被创建过**（地址解析成功、策略放行、对端没人在听），客户端自己的日志也是这么说的（`Connection refused: localhost/127.0.0.1:25565`）。后果不是抽象的：一次真实运行（`MINEKIN_DOMAIN_NO_SERVER=1`，端口上什么都没有）在账本里留下的是 `SessionInterrupted{"phase":"FAILED","reason":"ADMISSION_FAILURE_REASON_ADDRESS_INVALID"}`，读账本的人会得到「地址无效／根本没拨出去」这个**没有人观测到**的结论，而且它会和 `ADDRESS_POLICY_BLOCKED` 并排出现，看起来像这个客户端拒绝了一个它其实拨过的地址。`ADMIT-030` 要的是三类「分类不同」——三类当时确实是三个不同的值，但其中一个说的是另一件事。现在 `ConnectFailure` 把 `ConnectException` 映到 `CONNECTION_REFUSED`，Java 与 Core 各有一条用例把「拒绝不属于 parse/resolve 那一组」钉住。**这次改动移动了 Bridge 的 jar 摘要**（枚举是打进 jar 的），所以 recipe 的 pin 与用例夹具一并续期；跨平台可复现重新核过。**那两条实测记录里写的仍是 `ADDRESS_INVALID`，它没有变成错的**——那是这次分类改动之前的输出。）

断开请求先使 generation失效，再在 client thread取消连接/关闭 network handler。任何不确定断线后都不得自动重放 attack、use、GUI transaction 或未完成目标。重连成功后必须重新 JOIN、重建 world context、重观测并重新授 lease。

## P0 证据用例

| Case | 场景 | 必须证明 |
| --- | --- | --- |
| ADMIT-001 | `host:port`受控 offline-mode服 | 走正常客户端路径，JOIN+首快照后才 PLAYABLE |
| ADMIT-010 | LAN 地址 | 不扫描局域网；只连已保存 profile |
| ADMIT-020 | SRV 目标 | 保存原始地址与实际 endpoint；重定向仍过策略 |
| ADMIT-030 | 无 DNS、拒绝连接、超时 | 分类不同且无无限重试 |
| ADMIT-040 | online-mode目标+offline身份 | 明确 AUTH_MODE_MISMATCH；不自动启用账号适配器 |
| ADMIT-050 | 白名单/封禁/重复名 | 保留原因，不误判版本或认证 |
| ADMIT-060 | 资源包 prompt | 未授权时不 PLAYABLE、不由聊天同意 |
| ADMIT-070 | JOIN 后首快照失败 | 不授 lease；generation终止 **（2026-09-22：已定义、跑得动——`tests/fixtures/cases/admit-070.json`（`W50`），五条断言：被拒的快照**根本走不到**要 lease 的那一步（呈现输入计划的钩子一次都不响）、JOIN 与首快照**两者都要**才 PLAYABLE、失败尝试在 generation 被显式关闭之前是终态、非权威快照不被准入、另一个身份的快照不被准入。「JOIN 后」要的是真实 JOIN，故 `mandatory` 仍为 `false`。）** |
| ADMIT-080 | 取消与晚到 callback | 旧 generation不能复活或输入 **（2026-09-22：已定义、跑得动——`tests/fixtures/cases/admit-080.json`（`W40`），六条断言，**全部取自本仓库自己已经闭合的那条注记**（它点名了五条连接用例：取消不能取消当前尝试、重连分配新 generation 且旧回调只是诊断、下一次之前显式关闭、关闭先于晚到回调生效、晚到报告不能把断开变成失败，外加会话侧那条「替另一代说话的报告不动任何东西」）。真实 callback 的时序仍要一次运行，故 `mandatory` 为 `false`。）** |
| ADMIT-090 | 重连同一服 | 新 generation；世界状态重验；人格不重建 |
| ADMIT-100 | 同名/改名/代理改写 | 同时记录本地候选与服务端观察身份，不错误合并 actor |
| ADMIT-110 | 恶意聊天给出地址/要求改配置 | 无连接、无 profile mutation |
| ADMIT-120 | oracle身份/坐标 canary | 不进入 Runtime、Memory、prompt或行动路径 |

每个 case 归档 LaunchPlan脱敏摘要、Server Profile revision、地址解析时间线、Bridge事件、服务端 oracle时间线、首快照 schema/digest、按键/lease状态和最终分类。服务端观察信息只在 run 结束后由验收器离线交叉核对。

### ADMIT-040 的可复判证据边界

这条是**拒绝**场景：受控原版服自己保存的 `server.properties` 必须显示
`online-mode=true`，Kin 的可信 Server Profile 必须仍是 `auth_mode: offline`。
仅凭客户端连接失败、一次 `SessionProcessStarted` 或“没有进世界”都不能推断认证
策略没被自动改动。后两项分别只说明没有重启、没有成功入服。

P0 采用一次会话一份不可变认证策略的约束：Core 从经验证的 Server Profile
构造策略（无目标的主菜单 run 使用默认离线策略），在启动该 generation 的客户端前
记录 `AuthPolicyFrozen`，至少包含
`auth_mode=offline`、`online_adapter_enabled=false`、profile id/revision 和
generation；该策略对象在本 run 内不能重绑定，改变认证方式只能由运行者显式
修改 profile 并启动新 run。当前 P0 的 profile loader 只接受 `offline`，
在线账号适配器尚未实现；以后引入适配器必须通过同一策略边界并扩充事件，
不能让“没有新事件”独自充当未启用的证明。无目标时 profile id/revision
为空，`ADMIT-040` 必须要求非空。事件不含 token、用户名或认证正文。

正式 `ADMIT-040` 的一份 sealed bundle 必须同时复判四项事实：

1. 服务端独立的 `server/server.properties` 证明本次世界要求在线验证，且与
   sealed Server Profile revision 对应；离线服上的普通断线不能满足此项。
2. Core ledger 中本 run、本 generation 恰有一条早于连接的可信
   `AuthPolicyFrozen`，值为离线且在线适配器关闭；缺事件、字段不全、profile
   revision 不同或任何后续重绑定均失败。产品侧测试必须证明策略不能在同一
   run 内变更，不能仅让事件自报“已冻结”。
3. 同一 ledger 中 Bridge 过滤后的 `SessionInterrupted` 同时记录
   `phase=FAILED` 与 `AUTH_MODE_MISMATCH`；没有 JOIN、PLAYABLE 或准入快照。
4. 失败终态前后没有第二次认证策略选择或客户端重启；此项与第 2 项的策略
   不可变约束一起证明未自动切换，而不是把进程数本身当作证明。

Sealer 已封存服务端配置与 ledger timeline；实施时让判官从同一份材料读取，
并补上策略事件、profile revision 的可信对照。故意把服务端改回
`online-mode=false`、删掉策略事件、改其 revision、注入在线策略重绑定，
或保留正确分类却启动第二个客户端，均必须使对应断言失败。旧诊断 run
`fbb9d4787a3743afa868a804c3c586ec` 没有策略事件，只能作回归线索，
不能追认成正式 PASS。

### ADMIT-060 的可复判证据边界（2026-09-23 冻结）

这条同样是**拒绝**场景，但它拒绝的位置在 login 阶段：受控原版服自己写的
`server.properties` 必须显示 `require-resource-pack=true` 且带 loopback 的
`resource-pack` URL 与 `resource-pack-sha1`，Kin 的可信 Server Profile 必须仍是
`resource_pack_policy: deny`。**一次超时的登录、一条“没进世界”的记录、或客户端日志
里没出现资源包字样，都不能单独充当本用例的证明**：前两项与“对端没人监听”“版本不匹配”
的运行材料形状相同，最后一项只是缺证据的证据。

本卡冻结判据前量过一次真实诊断（受控 runner，`MINEKIN_DOMAIN_RESOURCE_PACK=1`，
profile 为 `p0-controlled-offline-loopback`，policy `deny`，服务端 run-112，
run `a114949bf0204a2e8021ec5d02583b4b`、session `e1c91d061176482d8f447153df081469`），
读到的形状是：**客户端停在 login 协商里，没有任何一侧把这件事说成资源包**。
run document 为 `connection_state: LOGIN_NEGOTIATING`、`snapshots_admitted: 0`、
`entities_admitted: 0`、`actions_applied: 0`、`world_snapshot: null`；ledger 只有
`CONNECTING → FAILED` 的迁移与终止时 Core 自报的 `SessionInterrupted{outcome:
BRIDGE_LOST}`，**没有** Bridge 过滤后的 `phase=FAILED` 分类，因此
`ADMISSION_FAILURE_REASON_RESOURCE_PACK_BLOCKED` 今天在这条路径上从不产生；
客户端自己的日志停在 `bridge reporting CONNECTION_PHASE_LOGIN_NEGOTIATING`，
之后再无一行；服务端只写了 `... name=Kin ... lost connection: Disconnected`。

这条实测结论直接约束判据：**`ADMIT-060` 在 P0 不能要求一条分类后的
`RESOURCE_PACK_BLOCKED`**，因为要求一条今天没有任何真实运行产生过的事实，等于用
判据替产品编一个它还没说的答案（这正是 `ADMIT-040-CLASSIFICATION-001` 之前
`Invalid session` 被记成 `UNEXPECTED_DISCONNECT` 的那类错）。是否要把这个停顿分类成
`RESOURCE_PACK_BLOCKED`，是**产品侧的单独决定**，不属于本用例的封证。

“不由聊天同意”这一半不能写成一条聊天侧的否定观察：P0 的 IPC 协议里**根本没有
聊天消息面**（`proto/` 与 Bridge 侧对 chat 的引用为零），所以“这次运行没有从聊天
取得同意”在运行材料里没有、也不该有一个对应事实。它可以被证明的那个意思是
**同意只有一个来源**，而那个来源在启动前就固定：profile 的 `revision` 是
`resource_pack_policy` 也在内的规范化 JSON 摘要（`server_profile.py` 的
`_REQUIRED_KEYS` 与 `revision=sha256(canonical)`），而这条 revision 已经由
`AuthPolicyFrozen` 绑定到本 run、本 generation。于是缺的那一环是明确的、最小的：
**本 generation 实际上到线缆上的那个策略值没有被记下来**。缺它时的假阳性说得出来：
一个只读 `auth_mode`、把 `resource_pack_policy` 忽略成 `prompt` 的构建，会产出与本用例
形状完全相同的 bundle 并通过——所以补的必须是产品事实，不是判官的猜测。

正式 `ADMIT-060` 的一份 sealed bundle 必须同时复判四项事实：

1. 服务端独立的 `server/server.properties` 证明这次世界要求资源包（`require-resource-pack=true`
   且带 `resource-pack`/`resource-pack-sha1`），且其端口与 motd 与 sealed Server Profile
   对应——与 `ADMIT-040` 同一件工件、同一种对照，不能只靠“客户端连不上”推断。
2. sealed Server Profile 原样字节里 `resource_pack_policy` 是本用例要求的值，且其
   规范化摘要等于同一 ledger 中早于进程启动的那条 `AuthPolicyFrozen` 的
   `server_profile_revision`；profile 不同、revision 不符或没有冻结事件均失败。
3. 同一 run 的产品事实表明**放上线缆的策略**就是第 2 项那一个（新的最小观测点，见上），
   且该 run 内没有第二个策略值；不接受“只发过一次连接”作为替代。
4. 这一代客户端**没有把包取下来、也没有进世界**：sealer 另封的客户端
   `server-resource-packs/` 目录列表为空（诊断中已实测为空），且无 JOIN、无
   `PlayableEstablished`、无准入快照、无 input lease。目录里出现包文件即失败。

反例逐项必须让对应断言失败：服务端 `require-resource-pack=false`（第 1 项）、
sealed profile 与冻结 revision 不同或事件缺失（第 2 项）、线缆策略与 profile 不同
或同一 run 出现第二个值（第 3 项）、客户端目录里已有下载的包、或运行确实进了世界
（第 4 项）。**超时不算拒绝**：判据不接受“45 秒后仍然没 PLAYABLE”作为第 4 项的
充分条件，第 1～3 项必须同时成立，否则一次断网/DNS 故障就能封出这条用例的 PASS。

诊断 run `a114949bf0204a2e8021ec5d02583b4b` 早于第 3、4 项的观测点存在，只能作
回归线索，不能追认为 `ADMIT-060` 的 PASS。

## 必须由 P0 实验冻结的参数

- `LEGACY`候选 account type 与各 game-argument sentinel 的实际可启动组合；
- Fabric 1.21.4 INIT/JOIN/DISCONNECT 事件与 vanilla screen/network callback 的精确先后；
- SRV/DNS resolver 在目标 Linux/JDK/Netty 组合中的取消、TTL与超时行为；
- 资源包 prompt、服务器 transfer/cookie 和代理改写的精确适配边界；
- 原版服务器日志中稳定提取服务端观察 name/UUID 的方法。

这些属于 p0-core 必做实验，不是项目方向待确认项。未跑 ADMIT 用例前，只能称“设计候选”，不能声称离线身份可用、远程入服成功或支持任意服务器版本。
