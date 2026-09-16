# 启动器供应链、版本包与玩家身份契约

研究时间：2026-09-16。本文件把“Minekin 自带本地启动器后端”落实为可审计的版本解析、下载、缓存、玩家身份与启动边界。它不表示这些路径已经跑通；默认离线身份路径仍须在全新 Linux 主机、LAN 与 offline-mode 私服上原型验证；可选在线认证另行验证。

## 结论

1. Minekin 发布物只包含 Harness、Launcher、Thin Bridge 与其开源依赖；Minecraft 客户端、libraries、assets 和 Java 运行时由 Launcher 从受信任上游按需取得，不打包再分发游戏本体。
2. “服务器版本可识别”与“客户端组合受支持”是两件事。探测结果只能选择 `tested` bundle；能下载到的版本不自动成为受支持版本。
3. 版本切换通过停止旧客户端、失效旧 session generation、启动另一不可变 bundle 完成，不在同一 JVM 内热换 classpath。
4. 上游元数据、下载工件、Bridge 和运行参数都进入不可变清单。下载须校验大小与上游提供的散列；缺散列的自有工件使用 Minekin 发布签名或固定 SHA-256，不把 TLS 当唯一完整性保证。
5. 默认离线身份不产生认证 token。仅在显式启用可选在线认证时，refresh token 由 Online Auth Adapter 隔离持有，游戏进程只获得本次会话所需短期材料；LLM、Bridge、Dashboard 普通状态流、日志和回放均不得获得它们。

## 证据与边界

- Fabric Meta 官方仓库明确把自身定义为可供 launcher 查询版本的 JSON API；`/v2/versions/loader/:game/:loader` 返回 Intermediary、Loader、libraries 与 client main class，profile 端点可生成标准 launcher JSON。
- Mojang/Minecraft 版本清单和每版本 JSON 是客户端、library、asset index、native、logging 与启动参数的来源。Minekin 必须保存取得时间和原始内容 hash，不能只保存“1.21.4”字符串。
- Prism Launcher 的公开实现会消费 Mojang 工件的 `url`、`sha1`、`size` 等字段；它是成熟 launcher 的实现证据，不是 Minekin 可直接复制全部认证/许可逻辑的授权。
- Yarn `MinecraftServer.isOnlineMode()` 明确区分是否向 Session Service 验证，集成服务器可接收未认证玩家；这是默认 LAN/offline 身份路径的代码级依据，不证明任意公网服都会准入。
- Paper/Velocity 文档说明关闭后端 `online-mode` 会停止后端自行认证，也警告不安全的转发/暴露入口可被冒名；offline 身份只能在运行者明确配置且受控的服务器使用。
- Microsoft device authorization grant 仅是可选 online-mode 适配器候选，需要应用注册并产生令牌；它不是默认链，也不单独证明 Xbox/Minecraft entitlement/profile 可用。
- Minecraft EULA 允许正常购买者下载、安装和游玩，同时限制分发游戏本体或 Modded Version；因此容器镜像不得预装完整 Minecraft 客户端。

## 元数据与版本解析

### 受信任来源

首版允许列表只包含：

- Mojang/Minecraft 官方版本元数据、libraries、assets 与 logging 工件来源；
- Fabric Meta 与 Fabric Maven；
- Minekin 自己的签名 Bridge/adapter release；
- 经许可证和来源核验后列入 bundle registry 的导航依赖。

Dashboard 不接受任意 manifest URL、任意 Maven repository、任意 classpath 或 JVM/game arguments。开发模式可导入本地候选，但必须显示 `untrusted-development`，不得升级为生产 `tested`。

### Server Probe

Server List Ping 只是为选择真实客户端而做的窄协议探测，不是游戏身体，也不进入 PLAY 状态。流程是：

1. 规范化 host/port，并在未指定端口时解析 Java Edition SRV；
2. 保存最终连接地址、SRV 来源、DNS 结果和探测时刻；
3. 读取服务端公开状态响应中的 protocol id 与展示版本；
4. 以 protocol id 为主、展示文本为辅映射到 Protocol Catalog；
5. 若代理、多版本入口、关闭/伪造 ping 或一对多映射造成歧义，进入 `NEEDS_PIN`，不得轮番下载和试登；
6. 管理者 pin 的是受支持 bundle id，不是任意伪装版本字符串。

探测结果有 TTL。DNS/SRV 或服务器状态改变后，下次会话重新探测；正在玩的客户端不因后台探测变化突然热切版本。

## 不可变 Client Bundle

建议 bundle id 为清单规范化序列化后的 SHA-256。至少冻结：

| 类别 | 必需字段 |
| --- | --- |
| 游戏 | Minecraft version、protocol id、version JSON URL/hash、client/assets/logging 清单 |
| JVM | Java major、发行版/build、OS/arch、下载来源/hash、JVM 参数模板 |
| Fabric | Loader、Intermediary、Fabric API、launcher meta/profile 的来源与 hash |
| Bridge | Bridge 版本、协议 schema、能力清单、适配的 Minecraft mapping/version |
| 可选技能 | Baritone/adapter 版本、来源、hash、许可、启用策略 |
| 图形 | virtual-display driver、renderer profile、窗口尺寸/FPS 上限 |
| 策略 | Player-Equivalent Filter、输入仲裁、世界书/配方 schema 版本 |
| 验收 | 构建时间、测试报告 id、状态与隔离原因 |

状态只允许单向受控迁移：`candidate → tested`；出现上游撤回、安全问题或回归时为 `quarantined`；不再维护为 `unsupported`。旧 `tested` 不自动随“最新版”漂移，升级要生成新 bundle 并重新过门。

### 缓存布局与原子安装

- `blobs/<sha256>`：只读内容寻址工件；下载到随机临时文件，校验后原子 rename。
- `manifests/<bundle-id>.json`：不可变规范化清单和出处。
- `bundles/<bundle-id>/`：从 blobs 物化的只读 classpath/assets/natives 视图。
- `sessions/<session-id>/`：每次会话的可写 overlay，只放 options、服务器资源包、日志、崩溃报告和临时状态。
- `quarantine/`：hash 不符、来源异常或测试失败的工件与报告，不进入正常解析。

并发安装同一工件要按 digest 加锁；中断后只清理过期临时文件，不删除已验证 blob。垃圾回收必须先建立 bundle/session lease，再按不可达 blob 清理，不能在客户端运行时删 native 或 asset。磁盘不足在启动前阻断，不边玩边回收未知文件。

## 玩家身份与认证边界

### 默认本地离线身份

每个 Server Profile 必须显式带 `auth_mode`，默认值为 `offline`。Identity Manager 保存内部稳定 `kin_id`、本地 `profile_id` 与游戏用户名，以及按 `server_id` 记录的服务端观察名字/UUID和证据级别。

Launcher 对 LAN 集成服务器或 offline-mode 私服创建本地 GameProfile，不运行 Microsoft→Xbox→Minecraft 链，也不存在 refresh token。此模式不能越过 online-mode、白名单、封禁或目标服务器规则。状态 ping 负责协议选择，但不能可靠证明认证策略；会话验证拒绝时记录 `AUTH_MODE_MISMATCH`，只能由管理侧显式换 profile。

### 离线身份的安全含义

offline-mode 表示服务端不以 Session Service 证明玩家身份，用户名和派生 UUID可能被冒用、代理改写或随配置变化。因此关系/Soul 连续性以内部 `kin_id` 为根；服务端权限、白名单、物品权属和高风险运行者绑定则按服务器观察身份核验。同名不自动合并人物，UUID变化进入待核验事件。直接暴露且未保护的 offline-mode 服务端、旧式不安全代理转发和“任意名字即管理员”配置不得列入安全部署示例。

### 可选 Microsoft 在线认证

只有 `auth_mode: microsoft` 时才加载 Online Auth Adapter。Dashboard 发起一次性交互式授权，Adapter 完成仍待实测的 Microsoft/Xbox/Minecraft 链并隔离持有 refresh token。游戏进程仅获得短期会话材料；LLM、聊天、网页、Bridge 观察、日志、回放与备份都不得得到 token。

不得借用官方启动器 client id、抓取官方 token、要求用户粘贴密码或在离线失败后静默升级为 OAuth。在线认证是独立能力声明；未完成 entitlement/profile、续期、撤销与泄漏验证前只能标为实验性。

### 可选在线令牌的进程暴露

标准客户端参数可能包含会话材料，Linux `/proc/<pid>/cmdline`、崩溃报告、进程检查工具和错误日志构成暴露面。仅对 online profile：Client Supervisor 使用隔离用户/容器，不记录 argv/环境/完整启动命令，诊断采用白名单与 redaction，禁止 Dashboard/媒体/模型侧读进程环境，并以 token canary 审计残余风险。

## 跨版本 Bridge 策略

Thin Bridge 不追求一个 jar 通过反射兼容所有 Minecraft 版本。每个正式 bundle 绑定一个已编译并测试的 Bridge target；共享的是稳定的外部 Bridge Protocol，而不是内部 Yarn 名称。

Bridge 握手至少含 `bundle_id`、`minecraft_version`、`protocol_id`、`bridge_build`、`schema_version`、`capabilities`、`session_generation` 和启动 nonce。任何不匹配都在入服前失败。版本升级时可以复用生成器、共享模块和测试规范，但映射/GUI/输入/渲染 hook 必须逐 target 验证。

## 故障语义

| 故障 | 行为 |
| --- | --- |
| 元数据不可达 | 使用仍在有效策略期内、已完整验证的本地 bundle；否则阻断 |
| hash/size 不符 | 隔离工件、终止安装、显示来源，不换镜像碰运气 |
| 下载中断 | 保留或清理临时分片；已验证 blob 不受影响 |
| 磁盘不足 | preflight 阻断并给出所需/可用空间与可安全清理项 |
| 探测歧义 | `NEEDS_PIN`；不无限试连，不回退协议 Bot |
| Bridge 握手失败 | bundle quarantine 候选；客户端不得获得输入 lease |
| 离线身份被在线验证拒绝 | 转 `AUTH_MODE_MISMATCH`；保留 Kin 记忆，管理侧可显式改用在线档案 |
| 离线名字/UUID冲突或变化 | 转 `IDENTITY_REVIEW`；不自动合并关系、权限或权属 |
| 可选在线 token 失效 | 清理会话材料，转 `AUTH_REQUIRED`；不删除 Kin 记忆 |
| 进程崩溃 | 松键、失效 generation、保存诊断；按预算重启或停机，不循环风暴 |

## 原型验收

必须在全新 Linux 主机完成并保留清单与回放：

1. 默认本地身份在 LAN 集成服与受控 offline-mode 私服的首次连接、重启、改名/UUID变化、拒绝原因和人物连续性；
2. 可选在线适配器另测 Web 授权、entitlement/profile、续期和撤销；
3. 两个不同版本私人服的 SRV/status/protocol 解析和两个 `tested` bundle 间重启切换；
4. 错误/关闭/伪造 ping、ViaVersion 一对多、未知协议和显式 pin；
5. 下载中断、篡改 hash、上游超时、磁盘满、并发安装、缓存复用与垃圾回收 lease；
6. bundle/Bridge schema 不匹配、旧 generation 消息和崩溃重启；
7. 仅对可选在线适配器检查 access/refresh token 在 argv、环境、日志、崩溃、遥测、Dashboard、媒体和备份中的泄漏；
8. 构建 SBOM/许可证报告，以及镜像中不存在 Mojang 客户端工件的检查。

## 仍待原型选择

- Identity Manager 的本地 GameProfile/服务器身份绑定实现；可选 Online Auth Adapter 采用 MSAL 加自写 Minecraft 服务链，还是经许可审查后复用成熟认证库；
- Java runtime 选官方 manifest 指定发行物还是受支持的固定发行版镜像缓存；
- Artifact Store 物化使用 hardlink、reflink 还是只读 bind mount；
- 首批支持版本数量。文档当前只把 1.21.4 作为第一个候选，不承诺任意服务器版本即刻可用。

