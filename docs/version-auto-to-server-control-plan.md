# 跨版本自动入服与最小控制：连续执行计划

> 状态：`VERSION-AUTO-DESIGN-001` 的设计交付；以下实现卡初始均为 `QUEUED`，
> **不是已经实现**。唯一可执行 `NEXT` 只看
> [开发执行控制计划](development-execution-plan.md) 的 `current_next`。
> 基线：`94ad677`（2026-09-24）。用户已明确把跨版本路线排在 HOST/PERSIST 之前，
> 目标是自动识别目标服、自动准备已验证的受管理客户端，并在服内完成一次简单控制。
> 目标测试服是用户提供的离线认证 Minecraft 1.20.1 服务器；它的地址只放在运行者的
> 私有 Server Profile/环境中，不写入仓库、fixture、日志示例或提交信息。

## 0. 一句话边界与完成定义

这条路线的终点是：同一个 `kin_id` 在已有 1.21.4 受控环境之后，面对运行者明确保存的
1.20.1 测试服，先用只读探测得出可解释的版本候选；从**独立完成真实验收的** 1.20.1
Client Bundle 中选择并按需安装；旧客户端、旧 generation 和输入 lease 先失效；新真实
Minecraft/Fabric/Bridge 客户端正常连接，JOIN 与权威首快照使其进入 `PLAYABLE`；操作员
显式请求一次小幅转向和短时前进，客户端执行、lease 到期松键，之后可安全断开。

完成要同时满足两层，不能互相替代：

1. **受控本地服务器层**：1.20.1 专服与 1.21.4 基线分别有 current-build 的构建、启动、
   Bridge 握手、JOIN、首快照、最小输入、服务端位移和安全松键证据；负向版本/身份/地址/
   下载用例 fail closed，sealed bundle 的 verify、rejudge、适用 replay、promotion 四读一致。
2. **用户测试服层**：仅对运行者明确保存的目标，先只读 ping，再非破坏性入服；真实客户端
   达到 `PLAYABLE` 并完成一次显式授权的小幅 look + 有上限的 move + release。若没有目标服
   的只读 server oracle，只报告“客户端观测的控制闭环”，不冒称服务端确认了位移。

这不是 `P0_CORE_TESTED`、HOST、Dashboard、自动探索、在线认证或任意 Minecraft 版本兼容的
声明。当前七场景 campaign 已走完而总体仍 `BLOCKED/INCOMPLETE`；本路线有独立的
`cross-version-remote-demo` 验收，不改写原 campaign 结果。

## 1. 当前事实、可信来源与不变约束

- 已有 1.21.4 Linux 受控原型具备 Launcher、Bridge、离线身份、JOIN/首快照、受 lease 限制的
  move/look/use、封存证据及本地 Docker runner；这**不是** 1.20.1 或任意公网服的证明。
- `server_profile.py` v1 只接受 loopback、`auth_mode=offline`、`minecraft_version=1.21.4`。
  `session start` 当前仍要求调用者提供 bundle recipe；没有接入启动路径的 Server Probe、
  Protocol Catalog、多版本 tested registry 或自动 bundle 选择。
- 现有 `ArtifactStore`、`ArtifactFetcher`、`provision_bundle` 可复用，但其 1.21.4 recipe、
  pin、Bridge JAR 与封存摘要不得改名当作 1.20.1。1.20.1 的 Java/Fabric/Yarn/Bridge
  组合必须从受信上游材料和独立构建实测确定，不能在这份计划里预填一个未经核对的版本号。
- status ping、DNS/SRV 和版本展示文本来自目标服务器，都是**不可信提示**；它们既不证明
  `online-mode=false`，也不授权下载 URL、认证切换、Mod 安装或放宽地址策略。
- 默认离线身份，账号/令牌不进本路线。`auth_mode` 仅由可信 Server Profile 指定；在线验证
  拒绝时分类 `AUTH_MODE_MISMATCH`，不静默改用 Microsoft 认证。
- P0 产品进程形态仍是一个 Python Core 和一个 Minecraft JVM；测试域 server/runner 不进入
  产品 wheel/JAR。切换版本必须停旧 JVM、撤旧 lease、开启新 generation，不在一个 JVM 内热换。
- 只对保存的目标连接：不扫描 LAN，不让聊天、网页、MOTD 或 status response 改写目标；DNS/SRV
  的最终地址须再过 `AddressPolicy`。继续无条件拒绝 link-local、unspecified、multicast。
- 不下载/分发未核查许可证的游戏组合，不把 Minecraft 客户端烘进镜像；未验证工件只能是
  `candidate`，只有独立验收后才可进 `tested`，失败进入 `quarantined`。

权威契约：[受管理客户端](managed-client-runtime.md)、[启动器供应链](launcher-supply-chain-contract.md)、
[P0 启动计划](p0-launch-plan-contract.md)、[远程准入](p0-remote-admission-contract.md)、
[证据与 oracle](p0-validation-evidence-contract.md)、[离线身份](p0-offline-session-compatibility-contract.md)。
上述早期文档若仍把“第二 bundle 未选择”当现状，按用户本次明确选择 **1.20.1 作为第二个
候选目标**解释；“候选”并不等于 `tested`。若较具体契约与此执行文档真正冲突，停下记录，
不得通过悄悄放宽测试解决。

## 2. 深模块与接口：实现者不得把步骤散到 CLI 各处分支

下表给的是模块接口的行为约束，不是命令行名字或 Python 签名的先验承诺。每张卡落实
一个 seam；测试通过同一接口观察结果，内部 HTTP/DNS/文件细节不泄漏给调用者。

| 模块 / seam | 接收 | 返回及拒绝 | 所有权与测试 adapter |
| --- | --- | --- | --- |
| Saved Target / Address Policy | 运行者保存的 profile revision、host/port、版本策略、认证策略 | 不可变目标与允许的最终 endpoint；地址变更/重绑定明确阻断 | `domain/admission.py` 保留无条件禁区；profile loader 不接受聊天/服务器回写 |
| Server Probe | 上述目标、DNS/SRV 与只读 status transport、超时/字节预算 | `ProbeObservation`：原始地址、最终地址、协议号、展示文本、来源/TTL/时刻、拒绝原因；绝不返回“已认证” | 网络 adapter 与假 DNS/status adapter 两个实现；无游戏登录 |
| Bundle Registry / Resolver | observation、可选 reviewed pin、OS/arch、已审 registry | `Resolution`：唯一 tested bundle 或 `NEEDS_PIN`/`UNSUPPORTED`/`STALE_PROBE`；不遍历试登 | 纯领域决策；1.21.4/1.20.1 与歧义反例共用同一接口 |
| Artifact Installer | tested manifest、受信来源、store、预算 | 完整可启动安装或可分类失败；半成品不可见，已验证 blob 不回滚 | 现有 fetch/store/provision 扩展；文件系统故障 adapter 注入 |
| Session Switch | 已安装 bundle、目标、旧 session/generation | 新 session 或明确失败；旧 lease/旧观察先失效，绝不同时控制两个 JVM | Core 的 session manager 持有次序；Bridge 不负责版本解析 |
| Demo Judge | 同一 run 的 CLI/ledger/client/server 材料 | `JOINED_CONTROLLED`、`JOINED_UNCONFIRMED`、`BLOCKED` 等有来源结论 | 测试域 sealed bundle；无 server oracle 时不可推导 server-confirmed |

不要为了未来多进程形态新增 RPC。`Probe`、`Resolver`、`Installer` 可有供测试注入的内部 seam，
对 CLI 只暴露“准备并启动已允许目标”的小接口；失败原因和证据引用是接口的一部分。先复用现有
`adapters/launcher`、`domain/admission`、`cli/session`，有两种真正不同 adapter 才引入新 port。

## 3. 状态机、选择规则与失败口径

`SAVED_TARGET → PROBING → RESOLVING → INSTALLING/REUSING → PREFLIGHT → STOPPING_OLD →
STARTING → BRIDGE_READY → CONNECTING → JOINED_UNVERIFIED → PLAYABLE → INPUT_LEASED →
RELEASED → STOPPED`。每个转移都记录同一 `kin_id`、profile revision、session/generation、
bundle id 与结果；旧代回调不能推进新代。`BLOCKED` 不自动回退旧版本继续玩。

1. protocol id 是主要索引，展示版本只是旁证。一个协议号映射多个可行客户端、代理宣称多版本、
   ping 关闭/不一致/过期、SRV 改向或目标响应可疑时返回 `NEEDS_PIN` 或更具体的阻断；
   pin 指向已审 bundle id，不能是任意字符串或服务端推荐的下载地址。
2. 同一协议只有**唯一**与 OS/arch、身份策略、Bridge capability 匹配且 `tested` 的 bundle 时
   才可自动选。`auto_then_pin` 的首次选择记入审计；后续服务器协议变化暂停自动重连。
3. 缓存未命中只从 reviewed manifest 的受信 URL 安装。hash/size/签名不符、磁盘不足、上游不可达、
   并发争抢或中断都不能发布“可启动”视图；有可用旧缓存时仍须符合当前 policy/有效期。
4. 连接拒绝不能被探测层改写成版本切换理由。`AUTH_MODE_MISMATCH`、白名单/封禁、资源包拒绝、
   网络失败、版本不匹配分别归类；不自动重试多个版本，不自动更换身份。
5. 控制只在当前 generation 的 `PLAYABLE` 之后获得 lease；一次 look 与有界 move 后
   `release_all`，超时/断连/Bridge 丢失由 watchdog 松键。服务端位置证明只能来自受控 oracle
   或运行者提供的只读服务端记录，不能从客户端日志自己复制一份冒充。

## 4. 连续执行队列与进度台账

下表是全路线，不等于同时开放十张卡。`D` 是本设计卡；`V01` 起一张一张由
`development-execution-plan.md` 提升。状态以主计划为准，下面初始状态仅作交接快照。

| 顺序 | ID | 初始状态 | 交付里程碑 | 前置 |
| --- | --- | --- | --- | --- |
| D | `VERSION-AUTO-DESIGN-001` | `DONE`（本次设计交付） | 本路线、反例和停机边界冻结 | 用户已指定优先级 |
| V01 | `VERSION-REMOTE-PROFILE-001` | `NEXT`（由主计划提升） | 受信目标 v2 / 显式远端地址策略 | D |
| V02 | `VERSION-SERVER-PROBE-001` | `QUEUED` | 只读 DNS/SRV/status 与归因 | V01 |
| V03 | `VERSION-BUNDLE-1201-001` | `QUEUED` | 独立 1.20.1 candidate 构建、pin、SBOM | D |
| V04 | `VERSION-LOCAL-1201-001` | `QUEUED` | 受控 1.20.1 真服/真客户端验收到 `tested` | V01,V03 |
| V05 | `VERSION-RESOLVER-001` | `QUEUED` | catalog / tested registry / 歧义阻断 | V02,V04 |
| V06 | `VERSION-INSTALLER-001` | `QUEUED` | 缺缓存自动安全安装与原子发布 | V03,V05 |
| V07 | `VERSION-SESSION-SWITCH-001` | `QUEUED` | 自动选包、停止旧代、启动新代 | V01,V05,V06 |
| V08 | `VERSION-REMOTE-SMOKE-001` | `QUEUED` | 用户目标只读探测及非破坏性入服 | V07 |
| V09 | `VERSION-SIMPLE-CONTROL-001` | `QUEUED` | 目标服一次 look/move/release 闭环 | V08 |
| V10 | `VERSION-DEMO-ACCEPTANCE-001` | `QUEUED` | 本地+目标服证据、回归与诚实能力声明 | V09 |

任务卡只从 `QUEUED → NEXT → DONE/BLOCKED_*` 流转；完成一张先 commit/push/核远端 SHA，
再在**下一次单独提交**提升下一张。允许按依赖关系先写 V03 的材料调查，但不可越过唯一 `NEXT`
改代码或把未验证的 candidate 标 `tested`。某卡触发停止条件时保留失败与进度，不自行改写路线。

原设计卡要求的五类交付在这里有明确归属：`probe` = V01/V02、`bundle-1.20.1` = V03/V04、
`resolver/installer` = V05/V06、`remote-profile` = V01、`end-to-end` = V07–V10。拆得比五张
更细是为了让每次可逆提交只回答一个问题；不另造与这五类竞争的产品路线。

跨卡必须保留的负向矩阵（每一项至少一个自动化反例，涉及真实线程/连接的再加受控运行）：

| 输入/故障 | 必须读到的结果 | 禁止出现 |
| --- | --- | --- |
| ping 不响应、畸形或协议号缺失 | `NEEDS_PIN`/明确探测失败 | 随机试登、默选 1.21.4 |
| 版本文本与协议号冲突、代理多版本 | 带原始观测的歧义阻断 | 按文本下载任意客户端 |
| SRV/DNS 目标改变或命中禁区 | profile revision/endpoint 拒绝 | 向新目标发送游戏会话 |
| 1.20.1 工件损坏、下载中断、磁盘满 | 无可启动半包、旧 blob 仍可验 | `candidate → tested` 自动跳级 |
| Bridge/bundle/schema 不匹配 | 握手前或准入前停机 | `PLAYABLE`、输入 lease |
| offline 身份遇在线验证 | `AUTH_MODE_MISMATCH` | 自动切换账号或 token 来源 |
| 旧 generation 回调、切服中旧 JVM 未停 | 旧 lease 作废、阻断新控制 | 两个可控客户端并存 |
| 入服无首快照、动作无回执、断连后键未松 | `PARTIAL/FAIL` 并保留 attempt | 从超时推断 PASS |
| 目标服缺只读 server oracle | `CLIENT_OBSERVED_CONTROL` 上限 | `SERVER_CONFIRMED_CONTROL` |

### V01 `VERSION-REMOTE-PROFILE-001`：保存可信目标，而非放开任意连接

- **输入/输出**：Server Profile v1 继续原样接受受控 loopback；新增 v2 仅由管理者写入
  `profile_id`、显式 host/port、`auth_mode: offline`、`version_policy`、可选 `pinned_bundle_id`、
  resource-pack policy 与目标授权/修订。私有目标配置不提交；公开 fixture 使用文档保留地址。
- **允许路径**：`src/minekin_core/domain/admission.py`、`src/minekin_core/adapters/launcher/server_profile.py`、
  `tests/unit/test_admission_address.py`、`tests/unit/test_server_profile.py`、
  `tests/contract/test_server_profile_schema.py`、新增版本化 profile schema/匿名 fixture、相关文档。
  若需额外路径，先修订卡再改。`bridge/`、`proto/`、`tools/`、已有 sealed bundle 禁改。
- **验收**：v1 字节/语义回归不变；v2 明确授权的单一目标可保存且 revision 变动可见；
  endpoint 经解析后再核对，不允许链接本地元数据地址、未授权 SRV 目标、DNS rebinding、
  地址族混淆、端口溢出；profile 缺失/未知字段拒绝；聊天/MOTD 无写权限。
- **停止**：如果要求“默认允许任意公网/IP 网段”或改变无条件禁区，停下交用户决策；
  不把用户测试服地址写进 repo；此卡不向目标发送游戏协议，也不推断版本或在线验证。

### V02 `VERSION-SERVER-PROBE-001`：只读、可归因的版本探测

- **输入/输出**：V01 的 profile；有字节/时间上限的 DNS/SRV 与 Server List Ping；
  `ProbeObservation` 包含原始地址、解析链、最终地址、协议号、展示文本、TTL/时刻、
  profile revision、失败类别。日志可用脱敏目标引用，不公开运行者地址。
- **允许路径**：新 `src/minekin_core/adapters/launcher/server_probe.py`、必要的
  `src/minekin_core/domain/version_probe.py`、`src/minekin_core/cli/parser.py` 与只读
  `server probe` 入口、定向 unit/contract 测试、匿名 DNS/status fixtures、相关文档；
  不动 Bridge、游戏登录、认证、已有 bundle pins。
- **验收**：真实只读探针可报告受控 1.21.4 和用户指定 1.20.1 目标的**观测值**；
  fake adapter 覆盖无 SRV/SRV 重定向、关闭 ping、超时、畸形/超大 response、伪造版本文本、
  protocol 缺失、代理多版本、DNS 重绑定与 TTL 过期；前后地址策略一致。探针不创建
  Session/JVM/lease，不连接未授权目标。
- **停止**：目标不响应或信号矛盾时输出 `NEEDS_PIN`/阻断，不换端口扫描或尝试登录；
  不把一次 ping 写成“服务端 1.20.1 已证实”或“offline 已证实”。

### V03 `VERSION-BUNDLE-1201-001`：第二套独立 candidate

- **输入/输出**：从 Mojang/Fabric 官方元数据核对 1.20.1 的 Java、Loader、API、Yarn/映射、
  client/libraries/assets/natives 与许可证；独立 Bridge target 的源码变更、构建和摘要；
  新 recipe/pins 与 `candidate` 清单。`1.21.4` 既有 recipe 与 Bridge JAR 不被覆写。
- **允许路径**：`bridge/` 的显式 1.20.1 target/build 配置与确需版本适配的 hook，
  `src/minekin_core/adapters/launcher/{metadata,recipe,launch_plan,mods}.py` 的必要泛化，
  `tests/fixtures/runtime-input/` 新 1.20.1 recipe 与元数据 pin、Gradle/Bridge/launcher 定向测试、
  `docs/version-license-matrix.md` 与供应链记录。不得改已封 bundle 或把测试域 jar 放进产品镜像。
  **主干回归例外（2026-09-25 补）**：`tests/unit/test_report_promotion.py` 一项——CI 自 run 423 起
  红在封存 bundle 目录的 rename 上，根因与判归见主执行计划 V03 `progress_record`；只改测试的模拟
  手法（rename 前 `unseal_bundle`），不改封存语义、不改判据。
- **范围修订（2026-09-25，登记后生效）**：1.20.1 Bridge 取**顶层独立 source root `bridge-1201/`**
  （与 `bridge/` 同构、自成一体的 Loom 工程），1.20.1 适配源只落该 root，`bridge/` 一字不改——因为
  1.21.4 已封 recipe 把 `source_digest = source_tree_sha256(workspace/bridge)` 钉死，往 `bridge/`
  里加任何源都会改 1.21.4 的 source identity。据此允许把 Bridge 身份从单一硬编码 root 泛化为按
  recipe 命名的 root：`adapters/launcher/recipe.py` 与 `tools/check_bridge_{scaffold,host_boundary,
  artifacts,protocol,proto_java}.py`、`tools/check_boundaries.py` 的 `BRIDGE_ROOT`，CI `bridge-static`
  按 root 各跑一遍。禁区分外不变：不改 1.21.4 的 pin/源码/已封 bundle，不冒名 digest，不放宽
  host-boundary 名单。取证与理由见主执行计划 V03 `progress_record`。
  **登记连带（同次修订内补，2026-09-25）**：`tools/check_bridge_scaffold.py` 的**全文摘要**被
  `tests/fixtures/cases/hostctl-060.json` 的 `assertion_digests` 钉住（该门的判据原文就是这条 case
  的一条断言），所以把这道门泛化成「按 root 各查一遍」必然移动它的实现摘要——这正是那道门设计出来
  要拦住的状态（同一个 case version 底下换了一套判据）。据此允许用既有的
  `tools/check_case_assertions.py --record` 重登记 `tests/fixtures/cases/hostctl-060.json` 的那一行，
  并同步 `tests/fixtures/manifest.sha256` 里该 case 文件的摘要行。除这两处摘要外不动任何 case 判据、
  不动 1.21.4 在门内的 pin 字符串、不重封 bundle；`HOSTCTL-060` 的 `case_version` 因此前移，其后果
  如实记在主执行计划里。
- **验收**：隔离构建/`check --rerun-tasks`、源码/产物 digest、依赖锁、SBOM/许可、Bridge
  协议/能力清单均可复判；1.21.4 全套回归无漂移；新产物仍仅 `candidate`。
- **停止**：元数据无可靠摘要、关键 Mod/映射无可审组合、Bridge hook 需超出当前能力契约、
  或 Java/OS 目标不明时记录选项并停；不可“编得过”就设 `tested`。

### V04 `VERSION-LOCAL-1201-001`：先在受控真服证明 candidate

- **输入/输出**：隔离的 1.20.1 `online-mode=false` 专服、V03 candidate、离线身份；
  独立 real-run bundles 和测试记录，不复用 1.21.4 的 case version/证据。
- **允许路径**：1.20.1 的测试域 server profile/runner 配置、版本化 case/断言/fixture、
  仅为版本适配必要的 Bridge/launcher 修复、进度/契约文档。修复触及冻结产品语义时先另开卡；
  不改用户服、不覆盖旧 evidence。
- **验收**：真实 client+Bridge 主菜单握手、离线 Session 可归因、JOIN+同代权威首快照、
  look/有界 move/release、服务端 name/UUID/位移、断连松键及正常停止；错误版本、
  错误 Bridge、认证策略拒绝和旧 generation 反例；每个 required 结果独立封证四读。
  全部成立后才在 reviewed registry 中把**精确的** 1.20.1 Linux/arch 组合升为 `tested`。
- **停止**：不能安全启动/入服、没有服务端 oracle、身份观测与声明不符、或必须放宽
  Player-Equivalent/lease 语义时保留 `FAIL`，停在 candidate；不要改判据凑 PASS。

### V05 `VERSION-RESOLVER-001`：只从 tested 清单选包

- **输入/输出**：V02 observation、V04 tested registry、OS/arch 与 operator pin；
  唯一 `bundle_id` 或稳定失败类别，附协议/版本/Bridge/能力决策痕迹。
- **允许路径**：新 `src/minekin_core/domain/version_resolution.py`、reviewed bundle registry
  loader/清单、`tests/unit/test_version_resolution.py`、registry fixture 与进度文档；
  不动网络下载、游戏连接、现有 Bridge hooks。
- **验收**：1.20.1 与 1.21.4 各自选到唯一 tested bundle；未知协议/一对多/代理/伪造文本/
  缺 OS 构件/非 tested 或 quarantine 返回 `NEEDS_PIN`/`UNSUPPORTED`，不循环试登；
  pinned id 也必须匹配当前目标和 tested 约束。变 registry 字节会移动决策版本。
- **停止**：协议共享版本的优先级不能由既有契约唯一确定时不新增默认排序；
  候选冲突进入 `NEEDS_PIN`，必要时交用户决定。

### V06 `VERSION-INSTALLER-001`：缺缓存时自动安全准备

- **输入/输出**：V05 的 reviewed tested manifest；现有 `ArtifactStore`、`ArtifactFetcher`、
  `provision_bundle`；原子发布的只读 bundle view 或有类别的失败。
- **允许路径**：`src/minekin_core/adapters/launcher/{artifacts,fetch,provision,launch_plan}.py`、
  CLI 的 `bundle install`/进度入口、`tests/unit/test_{artifact_store,artifact_fetch,provision}.py`、
  supply-chain contract/匿名 fixture。不得从 status/MOTD URL 下载、改 `tested` 状态或自动 GC。
- **验收**：空缓存可安装两套各自受审组合；已有缓存逐字节复验后复用；并发同 digest、
  下载中断、hash/size 错、上游失联、磁盘满、原子 rename 失败及重启恢复均不留下
  可启动半成品；受保护运行中 bundle/native 不被回收。镜像不含 Mojang 客户端。
- **停止**：可信上游无法提供可核验材料或需要向第三方镜像回退时停止并记录来源；
  不把“下载成功”当作 capability/tested 证据。

### V07 `VERSION-SESSION-SWITCH-001`：接通会话启动而不热换

- **输入/输出**：保存的 profile → V02/V05/V06 → `session start` 自动路径。旧的
  `session start --profile PATH` 显式配方形状保持可用；新自动入口可由独立
  `--auto-bundle` 表达，且与显式 `--profile` 互斥，最终 CLI 形状以本卡测试冻结。
- **允许路径**：`src/minekin_core/cli/{parser,session}.py`、相应 session runtime/状态机、
  launcher supervisor、定向 unit/contract 测试、状态/账本 schema（仅确需字段）和文档；
  不重写 Host/PERSIST/在线认证或测试域 oracle。
- **验收**：1.21.4→1.20.1 切换先停止旧 JVM、失效旧 generation/lease/瞬时观察，
  再以新 bundle/overlay/nonce 启动；同一 `kin_id` 不变。Bridge bundle/schema 不匹配、
  探测中目标变化、安装失败、旧进程未停、旧代回调晚到都 fail closed；自动路径
  不触碰宿主 `.minecraft`，不同时存在两个可控客户端。
- **停止**：如果需要替用户决定残留进程自动接管/强杀（`PROCESS-RECOVERY-001`），
  停在 `BLOCKED_DECISION`；不为维持切服进度暗中实现该策略。

### V08 `VERSION-REMOTE-SMOKE-001`：用户测试服只读探测与非破坏性入服

- **输入/输出**：运行者私有 profile（目标地址不进仓库）、V07 自动路径；仅一次受控
  1.20.1 入服 attempt，封存客户端/账本/必要服务端只读材料。
- **允许路径**：私有运行配置与受控 runner、必要的目标 profile/证据记录、进度文档；
  产品代码原则上冻结，若暴露新 bug 先登记独立修复卡。不得写目标服配置或世界文件。
- **验收**：probe 报告实际 protocol 与风险、resolver 选精确 tested bundle、Installer 命中
  完整缓存或安全安装；真实客户端 Bridge 握手、JOIN、首快照、`PLAYABLE`，服务端看到的
  name/UUID 如有只读来源则交叉核对。白名单/封禁/online-mode/版本拒绝分别分类。
- **停止**：目标未授权、协议歧义、账号验证拒绝、资源包策略冲突、服务端限流、
  或三次同一外部阻断；不改目标设置、不扫描、不用管理员/op/RCON 帮 Kin 入服。

### V09 `VERSION-SIMPLE-CONTROL-001`：服务器内最小可控闭环

- **输入/输出**：V08 同一 profile 上**新** run/attempt；操作员显式选择一个安全位置与
  限定动作——小幅 look，`hold-forward` 最多 2 秒（可先在本地受控服用更小值校准），
  然后 `release_all` 与主动退出。默认没有动作，绝不自动 use/挖掘/攻击/放置。
- **允许路径**：既有控制 CLI/runner 的必要小修、专属 case/判官/fixture 与证据文档；
  目标服只执行普通玩家输入，不使用服务端管理命令改变结果。若需新能力，先另开卡。
- **验收**：同 generation 先 `PLAYABLE` 再授 lease；Bridge 确认 look/move 被应用，
  客户端随后重新观测到可解释的位置/朝向变化；lease 到期、断开时松键，不能继续走。
  受控本地服再以服务端坐标独立证明位移；用户服若没有只读 server oracle，报告只限
  `CLIENT_OBSERVED_CONTROL`，不得升级成 `SERVER_CONFIRMED_CONTROL`。
- **停止**：区域不安全、保护插件拒绝、输入没有回执、客户端无重观测或发生残留按键，
  保留真实失败并停；不加长动作/重复跑来碰运气。

### V10 `VERSION-DEMO-ACCEPTANCE-001`：交付可重复的 demo，而非假全绿

- **输入/输出**：V01–V09 的 commit/远端 SHA、版本 manifest、sealed bundle、负向表；
  一份可由操作者重复的 CLI demo 手册和能力/未测声明。
- **允许路径**：`docs/` 的 demo/进度/契约、必要的只读报告调用；不改产品代码、
  case 判据或历史 sealed bundle。
- **验收**：按本节第 0 条逐项打勾；展示“目标→探测→选择→安装/复用→启动→入服→
  一次控制→松键→退出”的同 run/generation trace；验证 1.21.4 未回归；全量本地门禁、
  Java 21 `check --rerun-tasks`（Bridge 变更时）、Docker 真实运行与四读结果如实列出。
  公网目标地址、密钥与服务器世界数据不进公开 artifact。
- **停止**：任何所需证据缺席就交付 `PARTIAL/BLOCKED` 报告，不把演示视频、CLI 退出 0、
  ping 成功或一份旧 build PASS 冒充 tested/晋级。

## 5. 每卡启动、验证、提交与上下文恢复

每次启动先读 `git status --short`、`git log -8 --oneline`、本地/两个远端 SHA；已有脏改动归
原作者，不 reset/stash/覆盖。再读主计划唯一 `NEXT`、本文件对应卡、专项契约、最新
`report_cases.py`/`report_promotion.py`，记录 `baseline_sha`、允许/禁止路径、反例、真实运行
需求。卡外发现新阻断时**先登记为 QUEUED**，确认为当前 NEXT 的前置且修订范围后才提升；
不得在旧卡里顺手扩实现。`docs/development-todo.md` 记录原始 run/bundle/attempt/digest，
失败运行只追加不覆盖。

每张卡至少跑：全量 `uv run --frozen pytest -q`、Ruff check/format、Pyright、
`check_boundaries.py`、`check_case_assertions.py`、`verify_fixture_digests.py`、
`check_workflow_pins.py`、`git diff --check`；Bridge/proto 另跑四项 scaffold/host/protocol/Java
门禁与 Java 21 Gradle `check --rerun-tasks`。涉及 Linux/图形/供应链必须在 Docker 真跑；
涉及连接、身份、客户端 tick、输入或切服必须有 real-run evidence，本地绿灯不替代。

一张卡一组可逆提交（必要时先独立提交 scope 修订），commit message 包含
`Constraint`/`Rejected`/`Confidence`/`Scope-risk`/`Not-tested`；完成后立即 push 当前工作分支
和 `main`，用 `git ls-remote` 核对两 SHA。未 push 不得标 `DONE`；收卡提交记录准确的
verified/unverified 项，再在下一提交提升已登记的下一卡。CI 可看作辅助信号，但不作为
Minecraft 场景的完成证明。

推荐私有 demo 命令形状（**设计目标，不表示现在可运行**）：

```text
python -m minekin_core server probe --server-profile <PRIVATE_PROFILE>
python -m minekin_core session start --server-profile <PRIVATE_PROFILE> --auto-bundle
python -m minekin_core session start --server-profile <PRIVATE_PROFILE> --auto-bundle \
  --look-yaw-degrees <SMALL_ANGLE> --hold-forward-seconds <AT_MOST_2>
```

实际参数由 V07 的 parser 测试冻结；V08 先无控制入服，V09 才单独有界动作。
`<PRIVATE_PROFILE>` 是不入仓库的本地文件，勿在公开日志贴其内容。完成 V09 前不得称
“可进用户服控制”；完成 V10 后仍只称这两个精确 tested 组合与这类授权目标可用。

## 6. 停机决策清单（不让执行者在缺口处猜答案）

以下不是默认授权：在线账号接入、任意公网目标放行、未知协议优先级、代理多版本偏好、
第三个 Minecraft 版本、自动清理/接管残留进程、HOST 自建世界、PERSIST 编号、导航/采集。
若本路线触发它们，提交最小事实、可选方案、各方案的安全与兼容代价，并停在
`BLOCKED_DECISION`。用户此次明确给出的两项决定只有：**优先跨版本路径**，以及以其
**1.20.1 离线认证测试服**为最终受限 smoke/control 目标；这不等于允许改该服配置、
公开其地址或替它做安全承诺。

当前独立的 `REAL-P0-CAMPAIGN-001` 总账继续显示 `BLOCKED/INCOMPLETE`，直至其缺口按
原契约分别封闭。跨版本 demo 的成功不会自动清除那 31 个 missing required case。
