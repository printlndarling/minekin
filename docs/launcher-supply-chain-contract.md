# 启动器供应链、版本包与账号会话契约

研究时间：2026-09-16。本文件把“Minekin 自带本地启动器后端”落实为可审计的版本解析、下载、缓存、授权与启动边界。它不表示这些路径已经跑通；所有组合仍须在全新 Linux 主机和正版账号上原型验证。

## 结论

1. Minekin 发布物只包含 Harness、Launcher、Thin Bridge 与其开源依赖；Minecraft 客户端、libraries、assets 和 Java 运行时由运行者授权后从受信任上游按需取得，不打包再分发游戏本体。
2. “服务器版本可识别”与“客户端组合受支持”是两件事。探测结果只能选择 `tested` bundle；能下载到的版本不自动成为受支持版本。
3. 版本切换通过停止旧客户端、失效旧 session generation、启动另一不可变 bundle 完成，不在同一 JVM 内热换 classpath。
4. 上游元数据、下载工件、Bridge 和运行参数都进入不可变清单。下载须校验大小与上游提供的散列；缺散列的自有工件使用 Minekin 发布签名或固定 SHA-256，不把 TLS 当唯一完整性保证。
5. refresh token 只由 Account Broker 持有。游戏进程只获得本次会话所需的短期凭据；LLM、Bridge、Dashboard 普通状态流、日志和回放均不得获得它们。

## 证据与边界

- Fabric Meta 官方仓库明确把自身定义为可供 launcher 查询版本的 JSON API；`/v2/versions/loader/:game/:loader` 返回 Intermediary、Loader、libraries 与 client main class，profile 端点可生成标准 launcher JSON。
- Mojang/Minecraft 版本清单和每版本 JSON 是客户端、library、asset index、native、logging 与启动参数的来源。Minekin 必须保存取得时间和原始内容 hash，不能只保存“1.21.4”字符串。
- Prism Launcher 的公开实现会消费 Mojang 工件的 `url`、`sha1`、`size` 等字段；它是成熟 launcher 的实现证据，不是 Minekin 可直接复制全部认证/许可逻辑的授权。
- Microsoft 官方 device authorization grant 适合无本地浏览器的设备，但需要应用注册的 `client_id`，并会产生 access/refresh token。它只覆盖 Microsoft 身份层，不单独证明 Xbox 与 Minecraft entitlement/profile 全链可用。
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

## 账号与秘密边界

### Web 授权

1. Dashboard 请求 Account Broker 创建一次性授权会话；
2. 用户在自己的浏览器完成 Microsoft 登录；
3. Broker 完成 Xbox/Minecraft entitlement 与 profile 链；
4. refresh token 进入系统 secrets store，数据记录只保存 opaque credential reference；
5. 启动前生成短生命周期的会话材料并绑定 account/session/bundle；
6. 登出、撤销或异常刷新后会话进入 `AUTH_REQUIRED`，不以离线盗版账号兜底。

必须自己注册并合规使用 OAuth client；不能借用官方启动器 client id、抓取官方启动器 token、让用户粘贴密码或把第三方 refresh token 导入普通配置文件。具体 Minecraft 服务链和应用注册仍是原型阻断项之一。

### 启动参数泄漏模型

标准 Minecraft 启动链会把 access token 作为 game argument 传入；Linux `/proc/<pid>/cmdline` 保存进程完整命令行。因此仅在日志里替换 token 不能声称无泄漏。首版最少要求：

- 客户端在专用 Unix uid、PID namespace 或等价进程隔离中运行；Dashboard/媒体/网页工具不与其共享可读进程边界；
- refresh token 永不进入客户端进程；access token 只在启动窗口生成并尽量缩短有效期；
- Supervisor 在生成进程、异常、崩溃上传和诊断包时按字段而非字符串猜测进行打码；
- 禁止在 shell 拼接启动命令，使用 argv 数组；审计 `/proc`、进程列表、core dump、日志、遥测、错误页面和备份；
- 原型记录实际暴露面并据宿主机策略收紧 `hidepid`/namespace/uid，不宣称“零泄漏”。

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
| token 失效 | 清理会话材料，转 `AUTH_REQUIRED`；不删除 Kin 记忆 |
| 进程崩溃 | 松键、失效 generation、保存诊断；按预算重启或停机，不循环风暴 |

## 原型验收

必须在全新 Linux 主机完成并保留清单与回放：

1. Web 交互授权、entitlement/profile、重启后安全续期和撤销；
2. 两个不同版本私人服的 SRV/status/protocol 解析和两个 `tested` bundle 间重启切换；
3. 错误/关闭/伪造 ping、ViaVersion 一对多、未知协议和显式 pin；
4. 下载中断、篡改 hash、上游超时、磁盘满、并发安装、缓存复用与垃圾回收 lease；
5. bundle/Bridge schema 不匹配、旧 generation 消息和崩溃重启；
6. access/refresh token 在 argv、环境、日志、崩溃报告、遥测、Dashboard、媒体进程和备份中的泄漏测试；
7. 构建 SBOM/许可证报告，以及镜像中不存在 Mojang 客户端工件的检查。

## 仍待原型选择

- Account Broker 采用 MSAL 加自写 Minecraft 服务链，还是经许可审查后复用成熟认证库；
- Java runtime 选官方 manifest 指定发行物还是受支持的固定发行版镜像缓存；
- Artifact Store 物化使用 hardlink、reflink 还是只读 bind mount；
- 首批支持版本数量。文档当前只把 1.21.4 作为第一个候选，不承诺任意服务器版本即刻可用。

