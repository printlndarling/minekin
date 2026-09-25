# 宿主世界会话坐标来源 —— 设计（HOST-ADMISSION-DESIGN-001）

**本文件是什么**：一张设计卡的全部交付物。它整理**方案、反例与验收设计**，然后停在必须冻结的
那一步之前。**它不实现 HOST，不选方案，不提升 `HOST/W80+`，也不声明任何面可以晋级**——
主控 2026-09-26 的口径把这张卡限定为支线设计，而它点名的那个核心问题（谁创建 host
generation / `WorldCapsule`）**不因"做了一份设计"而被回答**。

**问题**：一个**不是由 `ConnectWorld` 发起**的世界——本 Kin 自己宿主（host）的世界——要成为
一个可被监督的客户端会话，它的 `generation` 与 `WorldCapsule` 由谁创建，首快照由谁发出、由谁判。

---

## 1. 现状：两侧闸门卡在同一个缺失的东西上

### 1.1 因果链（读法：从"世界读得到"走到"会话没开成"）

Bridge 侧的快照采集器读的是**这个客户端自己的**世界与玩家，所以它对"世界是别人开的还是
自己开的"完全不敏感——宿主的世界它照样读得到。真正拦住它的是**闸门的形状**：采集要挂在一个
已开始的 `generation` 上，而"开始一个 generation"这条路径今天**只有一个入口，且它的参数类型就是
`ConnectWorld`**。Core 侧是同一个形状：判首快照的那道过滤本身不排斥宿主世界，但它的调用方
要求先存在一次**由 `ConnectWorld` 发起的 attempt**。

于是两侧卡在**同一件**东西上：**一个"Core 没有拨过、但 Kin 自己开着的世界"的坐标**。
"读得到世界"与"被准入为会话"不是同一件事——后者要的是一个有人**先声明、后核对**的期望值。

还有一条把这件事划出已冻结范围的话：远程入服契约自己写明**不扩张到 HOST 模式**。
所以宿主世界的首快照由谁发出、如何映射进激活门，**不在**那条已逐项冻结的 ADMIT 状态机管辖内——
它既不是"违反现行契约"，也不是"契约已经答了只是没人读"，而是**契约留白的地方**。

### 1.2 三条候选方案的许可性（**这是判据，不是选择**）

契约许可性是可以量的：某个形状要么被明文条款排除，要么需要改条款才成立，要么现行条款本来就
预设了它。**许可性 ≠ 选定**——三条里今天只有形状问题，所有权问题在第 5 节，它不由形状分析回答。

| 方案 | 一句话 | 契约许可性判定 | 决定性依据 |
| --- | --- | --- | --- |
| A | Bridge 侧新增一条不是 `ConnectWorld` 的入口，由它自己开始 generation | **需要改契约才成立**：它把"谁裁判"翻转成被裁判的一方 | 裁判与校验对象分工见 §1.3 第 22–24 行锚点 |
| B | Core（管理侧）为宿主世界产出胶囊并下发一条携带 generation 的开始命令，Bridge 只执行 | **现行条款已预设这个形状**：host 命令**本来就自带** `session_id/generation/world_epoch` | §1.3 第 26–28 行锚点 |
| C | 宿主世界永远只走 `MANAGEMENT_ONLY`，不作为被监督会话 | **与已冻结条款冲突**：生命周期状态机以"本地 JOIN + 首快照"为门槛 | §1.3 第 32–33 行锚点 |

### 1.3 锚点表（每条都可复算；本表的第二列是机器校验对象）

下表的第二列**不是注释**：校验脚本按 `位置 → 该行必须含有的片段` 逐条读盘核对，任何一行不符即红。
写文档的人改错一个行号、或把某行的声称内容记歪，都会在这里被抓到。

| 位置 | 该行必须含有的片段 | 这条锚点声称什么 |
| --- | --- | --- |
| `src/minekin_core/domain/world_activation.py:73` | `class WorldCapsule` | 胶囊（期望值）在域里已经定义 |
| `src/minekin_core/domain/world_activation.py:87` | `server_profile_id: str` | 胶囊字段里已经给"宿主世界 profile 为空"留了位 |
| `src/minekin_core/domain/world_activation.py:177` | `def observe(` | 规则 2：观测到的 JOIN 必须与期望一致 |
| `src/minekin_core/domain/world_activation.py:204` | `def reconcile(` | 规则 3：首份玩家等价快照确认世界与 epoch 的门 |
| `src/minekin_core/cli/session.py:1188` | `if target is None:` | 没有远端目标就直接返回，不开代 |
| `src/minekin_core/cli/session.py:1190` | `connections.begin(` | 生产里唯一的开代点，参数来自远端 profile |
| `src/minekin_core/cli/session_runtime.py:637` | `if attempt is None or recorded is None:` | 没有 attempt 时快照只记 `ignored` |
| `src/minekin_core/adapters/bridge/admission.py:40` | `CONNECTION_PHASE_PLAYABLE` | Core 认得 PLAYABLE 这个相位 |
| `src/minekin_core/adapters/bridge/admission.py:158` | `LifecycleDisposition.WITHHELD` | 但 Bridge 自报 PLAYABLE 被有意扣住不应用 |
| `src/minekin_core/domain/world_creation.py:355` | `def storage_slot_for(` | 存储槽由系统从提案算出，不由提案自己声明 |
| `src/minekin_core/domain/world_creation.py:367` | `def synthesize(` | Gateway 侧合成不可变 effective profile 的纯函数已在 |
| `src/minekin_core/domain/world_identity.py:92` | `MISSING_NEW_IDENTITY` | 没有给到身份的新世界是**拒绝**，不是编一个 |
| `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:288` | `collectSnapshotWhenPlayable` | 1.21.4 root 的快照采集入口 |
| `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:292` | `if (activeGeneration == 0) {` | 没开代就直接返回：宿主世界一条快照都不采 |
| `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:569` | `void beginGeneration(ConnectWorld command)` | 开代入口的参数类型就是 `ConnectWorld` |
| `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:589` | `beginGeneration(command);` | 该 root 内它唯一的调用点 |
| `bridge-1201/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:303` | `collectSnapshotWhenPlayable` | 1.20.1 root 同形状 |
| `bridge-1201/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:307` | `if (activeGeneration == 0) {` | 同一条提前返回 |
| `bridge-1201/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:584` | `void beginGeneration(ConnectWorld command)` | 同样只认 `ConnectWorld` |
| `bridge-1201/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:604` | `beginGeneration(command);` | 同样只有一个调用点 |
| `proto/minekin/v1/envelope.proto:58` | `world_context_id` | 线缆上早就给世界坐标留了字段 |
| `docs/p0-remote-admission-contract.md:3` | `不扩张到 HOST 模式` | 远程入服契约明示不管辖宿主世界 |
| `docs/p0-remote-admission-contract.md:95` | `每次连接分配不可复用的` | generation 由连接分配且不可复用 |
| `docs/p0-remote-admission-contract.md:103` | `Runtime 校验 session、generation` | 首快照的裁判是 Runtime，不是 Bridge |
| `docs/hosted-world-control-boundary-contract.md:15` | `它不是感知提供者` | host-control 只输出管理事件 |
| `docs/hosted-world-control-boundary-contract.md:56` | `Gateway根据固定 bundle和管理策略生成不可变` | effective profile 由 Gateway 产出 |
| `docs/hosted-world-control-boundary-contract.md:137` | `command_id, kin_id, hosted_world_id, world_epoch` | host 命令自带世界纪元 |
| `docs/hosted-world-control-boundary-contract.md:138` | `session_id, generation, expected_state, profile_digest` | host 命令**也自带 generation**：形状已预设 B |
| `docs/hosted-world-control-boundary-contract.md:144` | `每次异步完成都重验` | 完成要重验 session+generation+epoch |
| `docs/hosted-world-control-boundary-contract.md:185` | `只有第一类能进入人物认知` | `MANAGEMENT_ONLY` 不得进认知路径（C 的依据与上限） |
| `docs/hosted-world-control-boundary-contract.md:197` | `HOST_LOCAL_JOIN_VERIFIED` | 白名单里有"本地 JOIN 已核实"这一管理事件 |
| `docs/hosted-world-storage-lifecycle-contract.md:109` | `CREATING --> HOST_PLAYABLE: local JOIN + snapshot` | 状态机要求首快照才算 HOST_PLAYABLE（C 与之冲突） |
| `docs/hosted-world-storage-lifecycle-contract.md:127` | `只有本地 host player已实际 JOIN` | manifest 转 ACTIVE 的门槛含首份 authoritative snapshot |
| `docs/hosted-world-storage-lifecycle-contract.md:221` | `HOST-001` | 全新 data root 建固定 profile 世界；本地 JOIN、首保存、重启重进 |
| `docs/hosted-world-storage-lifecycle-contract.md:234` | `哪些用例首批 mandatory在实现前冻结` | mandatory 子集**尚未**冻结 ⇒ 本文件不谈晋级 |
| `docs/hosted-world-commit-recovery-contract.md:13` | `任何一个单独出现都不等` | disconnect/退出码 0 都不等于世界已安全提交 |
| `docs/hosted-world-commit-recovery-contract.md:71` | `只能来自该阶段的真实返回` | `SUCCEEDED` 只能来自真实返回（验收设计的根据） |
| `docs/hosted-world-commit-recovery-contract.md:190` | `Reality Reconciler确认 world/epoch` | 首个玩家等价快照后由 reconciler 确认 |
| `docs/world-hosting-mode-contract.md:62` | `Runtime 选择已有` | 宿主世界的两个来源：选已有、或由游戏内决定新建 |
| `docs/world-hosting-mode-contract.md:149` | `host-integrated: tested` | 这个面独立于 `p0-core: tested` |
| `docs/world-hosting-mode-contract.md:151` | `必须由 HOST 原型冻结的参数` | 契约自己点名一批**未冻结**参数 |

**表里没有的、但同样是量出来的一句话**（它们不是"某行含某片段"，而是全仓计数，故单独写）：
`WorldCapsule` 在 `src/` 内**没有任何构造点**；`synthesize(` 与 `storage_slot_for(` 的引用只出现在
`src/minekin_core/domain/world_creation.py`（定义处）与 `tests/unit/test_world_creation.py`；
`world_context_id` 在 `src/minekin_core/adapters/bridge/` 与 `bridge/src/main/java/` 内**零命中**；
`tests/fixtures/cases/host-001.json` **不存在**，而 `host-010…080` 在。四条的复算命令见 §6。

---

## 2. 三条候选方案（每条四要素，逐项写全）

四要素是：**① 谁创建 `generation` 与 `WorldCapsule`；② 首快照由谁收集、由谁判；
③ 失败与重启后的恢复语义；④ 与既有契约条款的冲突点**。缺任何一项的方案不构成本卡的交付。

### 方案 A —— Bridge 侧新增一条不是 `ConnectWorld` 的入口，由它自己开始 generation

- **① 谁创建**：Bridge。`ClientAdmissionController` 得到一条新的开始路径（例如宿主 loader 完成后由
  Bridge 内部把 `activeGeneration` 置为某个值），`WorldCapsule` 或者不存在，或者由 Core 事后追赶。
- **② 首快照**：Bridge 采集并自发（`firstSnapshotIsAuthoritative()` 那支已有），判的一方仍然是
  Core 的 `_admit_first_snapshot`——但它手里没有期望值可对照，因为胶囊从没被创建。
- **③ 失败/重启**：跨进程重启后 `activeGeneration` 归零，而 Core 一侧没有任何记录说明"曾经有过
  一个宿主会话"；重放、清理、代际隔离都失去可比对的锚。
- **④ 冲突点**：远程入服契约把"谁裁判"写成 Runtime 校验 generation 与 world-context binding
  （锚点表第 24 行）。A 让被校验的一方**自行分配**校验对象，等于把校验变成追认；
  同时 host-control 边界契约明示它"只输出管理事件、不是感知提供者"（第 25 行）。
  **判定：需要显式改这两条契约才成立。**
- **代价最小的情形**：A 不是完全不可设想——如果 generation 仍由 Core 分配、Bridge 只是**接收**一条
  不是 `ConnectWorld` 的"开始"命令，那它其实已经变成 B。A 的定义性特征是"Bridge 自己开代"，
  而这一步没有任何条款授权。

### 方案 B —— Core（管理侧）产出胶囊并下发携带 generation 的开始命令，Bridge 只执行

- **① 谁创建**：管理侧。`world_creation.synthesize` 已经能从提案算出不可变 effective profile 与
  系统生成的存储槽（第 26 行 + `storage_slot_for`），host 命令的字段表**本来就带**
  `session_id, generation, world_epoch, expected_state, profile_digest`（第 27–28 行）。缺的只是把这些
  接到运行时胶囊上：`WorldCapsule` 的构造点今天一个都没有。
- **② 首快照**：Bridge 采集（现有 `collectSnapshotWhenPlayable` 一字不改即可工作，因为它只要求
  `activeGeneration != 0`），Core 判定（`_admit_first_snapshot` → 规则 2 `observe` → 规则 3 `reconcile`）。
  分工与远程入服契约一致：发的人不是判的人。
- **③ 失败/重启**：胶囊是期望值，落盘后可在重启时重放对照；`HOST-001` 的"重启重进"半边因此有
  可判的对象。旧代回调按第 29 行的重验规则只记 `STALE_COMPLETION`。
- **④ 冲突点**：与已冻结条款**没有**正面冲突；它撞上的是留白——远程契约明示不管辖 HOST
  （第 22 行），所以"B 的确切命令形状、`HOST_LOCAL_JOIN_VERIFIED` 如何映射进 `observe`"
  没有现行条款可抄。**判定：现行条款已预设这个形状，但管线与留白处仍需冻结。**
- **B 内部仍未定**（这四项不是措辞问题，是所有权问题，全部进第 5 节的矩阵）：
  (a) `generation` 由谁分配——Gateway/控制面在建档时就分配，还是 Core 的会话运行时在下发时分配；
  (b) 胶囊的**落盘处**与权威读回路径；(c) `HOST-001` 的宿主世界没有 server profile，
  规则 2 的"profile 必须一致"这一项对宿主世界**是跳过还是以 manifest 摘要替代**；
  (d) `world_context_id` 由谁在线上填（字段在、两边都不填）。

### 方案 C —— 宿主世界只走 `MANAGEMENT_ONLY`，不作为被监督会话

- **① 谁创建**：没有人创建会话坐标；只有管理事件流。`generation` 继续只属于远程连接。
- **② 首快照**：不存在被准入的首快照；Bridge 不采（闸门保持关闭）。
- **③ 失败/重启**：无会话可言，恢复语义退化成存档文件层面的 `HOSTCOMMIT` 一家的事。
- **④ 冲突点**：生命周期状态机把 `CREATING → HOST_PLAYABLE` 的触发写成 "local JOIN + snapshot"
  （第 32 行），manifest 转 `CREATED/ACTIVE` 的门槛含"首份 authoritative snapshot 成功"（第 33 行）；
  宿主模式契约也把"Kin 可独自玩自己的 save"当作目标能力。**判定：C 不是"保守的默认"，
  而是要改写这两条已冻结条款才能成立。** 它唯一自洽的读法是"承认今天就是 C"——那是**现状描述**，
  不是一个可采纳的方案。

---

## 3. 反例（每条命名失败理由；今天的可跑性一并写清）

反例的作用是**防止验收测试空转**：一条永远绿的断言不校验任何东西。以下每条都写成将来能落成
测试的形状，并诚实标注它**今天为什么跑不了**——本卡不实现，所以这些都不进 `tests/`。

| 编号 | 断言形状（将来的测试） | 命名失败理由 | 今天可跑？ |
| --- | --- | --- | --- |
| R1 | 1.20.1 与 1.21.4 两侧各自断言：宿主 loader 完成后 `collectSnapshotWhenPlayable` 发出**至少一条**快照 | 若 `beginGeneration` 仍只有 `ConnectWorld` 入口，这条必红——它测的正是本卡的问题 | 否：要真客户端线程 |
| R2 | Core 侧断言：一次**没有** `ConnectWorld` 的宿主会话里，`_admit_first_snapshot` 不得把首快照记为 `ignored` | 今天的代码就是记 `ignored`（锚点表第 7 行），所以这条红得对 | 否：要一次真运行 |
| R3 | 反证配对：把 B 的胶囊期望值改一位（profile 摘要或 epoch），`observe` 必须以 `EVIDENCE_DISAGREES` 拒收 | 若断言只用"有快照就通过"，它就无法区分"核对过"与"没核对" | 部分可：域层可测，但需要胶囊有生产来源 |
| R4 | 非空转控制（positive control）：远程 `ConnectWorld` 路径上同一组断言必须**全绿** | 用来证明 R1/R2 的红来自"宿主路径缺坐标"，不是断言本身写坏 | 是：现有远程路径已有工件 |
| R5 | 禁止性断言：Bridge 报 `CONNECTION_PHASE_PLAYABLE` 不得推进任何宿主会话状态 | 若哪天有人图省事让 Bridge 自报 playable 过关，这条必须响 | 可（域层已有 WITHHELD，缺宿主侧的对称用例） |
| R6 | 身份拒绝：宿主世界**没有**给到 `world_context_id` 时，激活门必须拒绝而不是编一个 | 对应 `MISSING_NEW_IDENTITY` 与规则 5；写成"缺就默认一个"是这条要消灭的 | 可（域层） |
| R7 | 重启重进：`HOST-001` 的后半——冷启动后重进同一宿主世界，纪元/槽/摘要必须与首跑一致 | 不一致即说明胶囊不是期望值而只是缓存 | 否：要全新 data root 的真实两跑 |

**R4 是本卡的自我约束**：所有"红"都必须能被一个"同形状的正例"证明不是断言写坏。第 4 节的验收
设计把这条写成硬性必跑项。

---

## 4. `HOST-001` 的真实 trace 验收设计（设计，不建 fixture）

本卡**不创建** `tests/fixtures/cases/host-001.json`。这里给的是它落地时该长的样子，供主控冻结
所有权之后直接开工。

- **case id**：`HOST-001`；所属面：`host-integrated`（独立于 `p0-core`，锚点表第 40 行）。
- **场景（契约原文拆三条可判子句）**：全新 data root 创建固定 profile 世界；本地 JOIN；首保存；
  重启后重进（`docs/hosted-world-storage-lifecycle-contract.md:221`）。
- **断言 token 名**（沿用 reviewed registry 的小写从句风格，逐个可被 `tools/assert_case_evidence.py`
  在工件里找到出处）：
  - `the_bridge_collected_a_snapshot_for_the_hosted_world`（R1）
  - `the_runtime_admitted_the_first_hosted_snapshot_without_a_connect_command`（R2）
  - `the_hosted_capsule_refused_a_disagreeing_join`（R3）
  - `the_remote_path_still_admits_a_connect_command_snapshot`（R4，正例对照）
  - `the_hosted_world_reentered_after_a_cold_restart`（R7）
- **`validation_class`**：`RUNTIME_TRACE`——要真客户端线程与真实进程生命周期，本地不可判。
- **`mandatory` 建议值**：`false`，并写明理由。契约说 mandatory 子集"在实现前冻结"（第 35 行），
  而在残缺用例集上给出"可晋级"是一句假话（`docs/hosted-world-control-boundary-contract.md:211`）；
  本卡不动任何 fixture，这个建议值只是给下一张卡的输入。
- **必跑命令形状**（凭据/地址一律走未跟踪文件，文档里不出现任何 host:port）：
  1. 容器内以**全新** data root 跑一次宿主会话，产出 run document 与工件清单；
  2. `python tools/verify_tested_provenance.py --registry … --data-root /data` 断言被引 run 逐条
     `present/readable/sealed/consistent`；
  3. `python tools/report_promotion.py --data-root /data` 读该 case 那一行的
     `from_repository_build` / `re_judged`，**并断言整体仍是 `blocked`**；
  4. 冷重启后重跑第二次，比较纪元/槽/摘要三元组。
- **非空转要求**（这是设计里最硬的一条）：上面 5 个 token 必须**逐一删除后各让一个具名测试变红**；
  只删不掉任何断言的 token 就是装饰，不许留在 case 里。positive control 是同一次运行里远程路径
  的等价断言仍全绿（R4）。
- **停止条件**（写进将来的卡）：缺真客户端 trace、缺全新 data root、或必须连远程服才能凑出
  第二客户端，一律**停止并报缺哪种输入**，不拿域层测试冒充运行证据。

---

## 5. 分歧矩阵：所有权问题为什么不由本卡回答

三个所有权问题是正交的，每一个都有两个以上说得通的落点。**本卡到此为止：下面这张表就是交付物
本身**——把它交给主控，而不是替主控挑一列。

| 待冻结项 | 落点选项 | 选它的后果 | 反对它的最硬一条 |
| --- | --- | --- | --- |
| `generation` 由谁分配 | 建档时由 Gateway/控制面；下发时由 Core 会话运行时 | 前者让重启重进天然有可比对的旧值；后者复用现有 `connections.begin` 语义 | 前者要动 host 命令的产出时机，后者要在没有远端目标时也允许开代——两者都是**产品分工变更**，不是 bug 修复 |
| `WorldCapsule` 的权威来源与落盘处 | `HostedWorldManifest` 摘要；新建一份胶囊档；不持久化只内存 | 决定 `HOST-001` 后半（重启重进）今天能不能判 | 契约拒绝"编一个身份"（第 12 行锚点），所以任何"没有落盘也能过"的选项都削弱重启核对 |
| 规则 2 对宿主世界的 profile 一致性 | 跳过该项；以 manifest 摘要替代；要求一个 loopback profile | 决定胶囊的 `server_profile_id` 为空到底是"合法空位"还是"缺件" | 字段注释已写明宿主世界为空（第 2 行锚点），改成"必须有 profile"要同时动地址策略那条安全控制 |

**为什么这三格不能由设计文档代答**：它们改变的是**控制面与会话运行时的分工**（谁有权声明一个
世界开始了），属于产品策略；而委托给 Qoder 的机械流转明确不含 `BLOCKED_DECISION`、
HOST/W80+ 与新产品策略（本文件所属计划的「任务状态变更规则」）。主控 2026-09-26 的答复也已把
这一点写明：核心问题**没有被"选择做设计"本身回答**。

---

## 6. 复算命令（本文件所有计数类声称）

```bash
# 胶囊没有任何生产构造点（期望：只有类定义处命中，无 `WorldCapsule(` 调用）
grep -rn "WorldCapsule(" src --include=*.py
grep -rn "class WorldCapsule" src --include=*.py
# 开代只有一处，且它上面就是 `if target is None: return`
grep -rn "connections.begin(" src --include=*.py
sed -n '1186,1191p' src/minekin_core/cli/session.py
# Gateway 侧的两个纯函数只有定义处与单元测试引用，生产无调用点
grep -rln "synthesize(\|storage_slot_for(" src tests tools --include=*.py
# 线缆上的世界坐标两边都不填
grep -rn "world_context_id" src/minekin_core/adapters/bridge/ ; grep -rn "WorldContext" bridge/src/main/java
grep -n "world_context_id" proto/minekin/v1/envelope.proto
# 两个 Bridge root 各只有一个 beginGeneration 调用点
grep -rn "beginGeneration" bridge/src/main/java bridge-1201/src/main/java --include=*.java
# HOST-001 的 fixture 仍不存在，而 010…080 在
ls tests/fixtures/cases | grep -E "^host-"
```

**这些命令的输出是本卡验收的第 2、3 格的证据来源**；`path:line` 那 41 行由
`.tmp/check_host_design_anchors.py` 逐条读盘核对（改错任一行号即红），校验脚本自身带
"匹配行数 ≥ 30"的下限断言，防止它解析不到东西而空过。

---

## 7. 一句话结论（不含选择）

两侧闸门卡在同一个缺失的坐标上，这不是实现瑕疵而是**契约留白**：三条候选里 A 要改"谁裁判"、
C 要改生命周期门槛，B 的形状已被 host 命令的字段表预设，但**它仍然要等所有权冻结**——
`generation` 由谁分配、胶囊落在哪里、规则 2 对宿主世界的 profile 一致性怎么算，三格都留给主控。
本卡的交付物是这份分析加那张矩阵，不是任何一个"已实现"的宿主会话。
