# 开发 TODO 与执行门禁

更新：2026-09-18。

本文把现有设计文档转换为可执行开发队列。若本文与专项契约冲突，以更新且更具体的契约为准；P0 的实现入口是 [P0 核心原型执行计划](p0-prototype-execution-plan.md)与 [P0 core 内部架构](p0-core-internal-architecture.md)。

## 执行原则

- 严格按 `W00 → W10 → W20 → W30 → W40 → W50 → W60 → W70` 晋级；前置门禁失败时不以 mock 或后续结果覆盖。
- 每批只增加一个可逆能力，按“schema/fixture/预期 → 实现 → 真实 evidence digest”提交。
- 失败 run 只追加、不覆盖；无实际证据不得标记 `PASS`、`tested` 或 `P0_CORE_TESTED`。
- P0 仅包含一个 Python `minekin-core` 进程与一个 Java 21 Minecraft/Fabric JVM。Dashboard、PlayerMind、LLM、媒体、导航和 HOST 均后置。
- 产品代码不得读取测试 oracle；服务端真值只允许验收器在运行结束后交叉核对。

## 环境门禁

- [x] Git 工作树与 `origin/main` 基线确认。
- [x] Python 与 uv 可用。
- [ ] 安装并固定 Java 21；当前开发机仅检测到 Java 17，W20 及真客户端实验不得在此条件下宣称通过。
- [x] 以 CI 中固定版本的 Buf action 提供 schema build/lint/format 门禁；本机另用固定 Buf `v1.50.0` 完成 W00 lint。
- [ ] 完成 Gradle 依赖锁与 verification metadata；Wrapper 及发行包 SHA-256 已固定，但 Java 21 环境首次解析仍待执行。
- [ ] 为受控 Linux runner 准备 Java 21、Xvfb、原版 1.21.4 server 与隔离账号/目录。

## W00：规格、夹具与整体框架

- [x] 建立 `pyproject.toml`、`uv.lock`、Python 3.12–3.13 范围与 Node-free P0 依赖清单。
- [x] 建立 `src/minekin_core` 的 domain/application/ports/adapters/entrypoints/generated/cli 边界。
- [x] 建立 `bridge`、`proto/minekin/v1`、`tests` 与 `test-orchestrator` 骨架。
- [x] 实现并测试 Session 状态与合法转换表。
- [x] 冻结 ID、generation、sequence、deadline 与 monotonic/wall-clock 语义。
- [x] 冻结 proto v1：envelope、hello、fault、observation、lease、`release_all`。
- [x] 冻结 SQLite schema/migration v1、单 writer-thread 与 transactional outbox 契约。
- [x] 冻结错误分类、退出码、脱敏规则与未知错误 fail-closed 行为。
- [x] 冻结 CLI schema；`doctor` 为只读实现，其余命令在实现前明确无副作用地失败。
- [x] 提供 fake Clock/Launcher/Bridge/EventStore/Evidence ports。
- [x] 提供 protobuf、framing、event replay 与 crash golden fixtures，并固定跨平台摘要。
- [x] 自动检查依赖方向、Bridge 引用与产品 wheel 不得包含 oracle。
- [x] 写 ADR：P0 不引入 Web、ORM、通用 Agent 框架和多 Python 服务。
- [x] 门禁：schema 可版本化、fixtures 摘要固定、oracle 与产品输入目录隔离。

## W10：Launcher 元数据与 dry-run

- [ ] 解析并校验 Mojang 1.21.4 与 Fabric 0.16.9 固定元数据。
- [ ] 生成可审计的 classpath、natives、JVM/game argv 与内容摘要。
- [ ] 逐项校验 URL、大小、SHA、Java 21、main class、规则与固定 mod 集。
- [ ] 使用独立 argv 元素；禁止 shell 拼接、未替换占位符与宿主 `.minecraft` 访问。
- [ ] 建立内容寻址 artifact store、只读 bundle 与可写 session overlay。
- [ ] 门禁：所有工件与参数可复核；篡改、未知 artifact 或不兼容 runtime 均 fail closed。

## W20：只读 Thin Bridge

- [ ] 建立 Java 21/Fabric 1.21.4 client entrypoint 与固定 manifest。
- [ ] 实现 control/event 双通道的长度前缀 Protobuf framing。
- [ ] 实现 nonce、protocol、generation、bundle 与 capability 握手。
- [ ] Bridge 默认 `OBSERVE_ONLY`，握手前无连接和输入能力。
- [ ] IPC/编码在后台有界队列运行，Minecraft 对象只在 client thread 访问。
- [ ] 门禁：错误 nonce/protocol/未知 mod 被拒，client tick/render 不被阻塞。

## W30：Offline Session

- [ ] 按 OFF-A（`offline`）→ OFF-B（`legacy`）运行有界候选，不静默漂移。
- [ ] 冻结 `token=0`、offline UUID 与 clientId/xuid 显式空 argv 语义。
- [ ] Bridge 脱敏报告实际 Session；日志不得出现敏感正文。
- [ ] 执行 `OFFLINE-001…100`，仅在条件满足时运行 UUID/sentinel 对照。
- [ ] 门禁：启动、握手与身份材料可解释，失败分类明确。

## W40：原版服务器准入

- [ ] 启动隔离的 vanilla 1.21.4 `online-mode=false` dedicated server。
- [ ] 实现可信 Server Profile、地址/SRV 策略与 connection generation。
- [ ] 经普通客户端执行 ConnectWorld，按 JOIN/认证/白名单/资源包等原因分类。
- [ ] 取消、重连与晚到 callback 不得改变新 generation。
- [ ] 执行 `ADMIT-001…120`；Kin 不得获得 op、RCON 或 console 权限。

## W50：玩家等价首快照

- [ ] 实现 self、inventory 与 visible-world 最小快照及过滤器。
- [ ] 同 generation 的 JOIN、world/player/network handler 与首快照共同构成 `PLAYABLE`。
- [ ] 建立 Bridge/Runtime、server truth、orchestrator 三条时间线。
- [ ] 加入视锥/遮挡/oracle canary 与目录、字段泄漏扫描。
- [ ] 门禁：首快照失败不授 lease；隐藏实体、容器与服务端坐标不得进入产品输出。

## W60：最小合法输入

- [ ] 实现 `look`、短时 `move` 与幂等 `release_all`。
- [ ] 实现唯一 input owner、lease、deadline、priority 与前置状态检查。
- [ ] 实现 Core/Bridge 双 watchdog。
- [ ] 断 IPC、死亡、GUI 冲突、超时或 generation 改变时全部松键。
- [ ] 门禁：服务端离线核验真实位移；不得瞬移、直接写状态或残留按键。

## W70：恢复与证据晋级

- [ ] 注入 Core、Bridge/client、server 与连接阶段故障。
- [ ] 对账未决 outbox，失效历史 generation/lease，防止危险动作重放。
- [ ] 验证重复启动、同一 `kin_id` 重启与瞬时世界状态重验。
- [ ] 生成不可变 evidence bundle、三时间线、脱敏日志、结果摘要与所有 digest。
- [ ] 实现 evidence verify/replay 与 candidate→tested 晋级检查。
- [ ] 跑完 `CORE-001…090`、mandatory OFFLINE/ADMIT cases 与 L6 baseline。
- [ ] 门禁：mandatory case 全部有真实 `PASS` evidence 后才能标记 `P0_CORE_TESTED`。

## W70 之后

- [ ] W80：独立 `p0-nav-exp` 导航实验；核验输入冲突、隐藏真值与 SBOM/许可。
- [ ] 生存底座：可见树导航、正常破坏/拾取、GUI 合成、工具链、食物与首夜。
- [ ] P1 PlayerMind：身份/人格、运行者关系种子、自主目标、承诺、世界书、知识画像、分层记忆、SkillSpec、注入与工具安全。
- [ ] HOST 专题：独立 `p0-host-exp`，执行 `HOST`、`HOSTCTL`、`HOSTCOMMIT` 用例。
- [ ] P2 产品化：Gateway、Dashboard、Live View、systemd/cgroup、备份与可观测性。
- [ ] P3 社会 MVP：权属、拒绝、承诺、损失、归因不确定性、调查与和解。
- [ ] P4 单 Kin 综合演示：独居、等待、死亡调整、合作/分歧与跨日连续性。
- [ ] 扩展：仓储/熔炼/施工/战斗/跨维度/末影龙；之后才评估多 Kin、模组、多版本与在线认证。

## 已消歧的文档口径

1. `technical-stack-selection.md` 的早期“首个切片”提到 Gateway/Dashboard，但更具体且更新的 P0 契约明确 P0 无 Web/Node；因此 Gateway/Dashboard 后置 P2。
2. P0 core 没有模型或网页工具；W00–W70 只实现来源、trust、脱敏与 oracle 隔离基础。完整 `INJECT-001…120` 在 PlayerMind/工具层进入后执行。
3. Xvfb 可作为真实客户端启动环境，但 FFmpeg/Live View 不进入 P0 core。
