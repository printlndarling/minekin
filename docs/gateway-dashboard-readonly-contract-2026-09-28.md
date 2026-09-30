# 只读 Gateway / Dashboard 契约冻结记录（`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`）

日期：2026-09-28（M 主控，第七十九轮）。base：主干 `5c73f6ac46e281f78e7e26e081decd65cf91e64f`（工作树干净，`git status --porcelain` 0 行）。
授权来源：[本地 LAN 控制队列](v1201-lan-control-next-2026-09-27.md) §3 —— 「若某条线卡住，仍可推进的独立工作」的第一类：只读接口/身份与脱敏设计，**不接线上真实写接口**。

## 0. 这张卡是什么，明确不是什么

D1 只读外壳（合并 `8aab153`，`dashboard/**` 50 个受版本控制的文件）已经把「前端读什么」写成了代码，但它自己在源码注释里 declares 那套端点与字段**是提案、不是契约**（`dashboard/src/adapters/gatewayAdapter.ts:34-39`），读模型版本号也带着 `-proposal` 后缀（`dashboard/src/domain/model.ts:8` = `kin-dashboard-readmodel/0.1.0-proposal`）。`docs/development-execution-plan.md` §2 的 D 行因此把 D2 的真实接线停在「等 G lane 冻结 Gateway 只读契约」。

本记录做那件被等待的事：**冻结浏览器侧读模型的语义与边界**，让 G 的实现卡与 D 的接线卡各自有可判的验收。它**不做**下列任何一件：

- 不实现 `gateway/**`，不在 P0 Core 里塞 HTTP/WebSocket（`docs/adr/0001-p0-modular-monolith.md` 仍成立：P0 的管理入口是本地 CLI）。
- 不改 `dashboard/**` 的字节（那是 D lane 的独占面）、不改 `src/**`、`bridge*/**`、case 判据、registry、`mandatory`。
- 不接任何线上真实写接口，不给浏览器发游戏输入的能力，不读 Bridge 凭据。
- 不伪造 `NEXT`：主干唯一的 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`，本卡不提升为 `NEXT`，也不占任何 lane 的 `lane_next`。

## 1. 卡定义

| 项 | 内容 |
| --- | --- |
| ID | `DASHBOARD-GATEWAY-READONLY-CONTRACT-001` |
| owner | **M 主控**（设计面）。下游实现分两张新卡：`GATEWAY-READONLY-PROJECTION-001`（G 候补 lane，独占新增 `gateway/**`）、`DASHBOARD-GATEWAY-WIRING-001`（D lane，独占 `dashboard/**`）。 |
| allowed_paths（本卡） | `docs/gateway-dashboard-readonly-contract-2026-09-28.md`（本文件）、`docs/development-execution-plan.md`（§4 登记 + D 行状态注）、`docs/parallel-execution-plan.md`（G 候补行的冻结时点）、`docs/v1201-lan-control-next-2026-09-27.md`、`docs/qoder-execution-handoff.md`。 |
| 禁止 | `dashboard/**`、`src/**`、`gateway/**`、`bridge*/**`、`test-orchestrator/**`、`tools/**`、`tests/fixtures/**`、registry、`mandatory`、规范卷（本卡全程未挂载任何数据卷，连 `:ro` 都不需要：全部读数取仓库字节）。 |
| 验收 | 见 §6 的三条：读模型字段全部有具名载体或被具名标为 `not_wired`；身份面只以存在性出现；写动词在契约文本与后续实现扫描里为 0。 |
| 停止条件 | 若某个想暴露的字段在 Core 里既无载体又无法具名 `not_wired`（即必须靠猜测填值），停手并登记为产品决定，不实现。 |
| 回滚 | 纯文档：`git revert` 本笔即可，不动任何门。 |

## 2. 冻结的读模型

### 2.1 端点：三条只读 GET，无其它动词

| 端点 | 方法 | 载荷形状 | 超时 |
| --- | --- | --- | --- |
| `/api/v1/dashboard/snapshot` | GET | 单个 signal 信封对象（字段见 §3） | 3000 ms（`dashboard/src/adapters/config.ts:7` `DEFAULT_TIMEOUT_MS`） |
| `/api/v1/dashboard/timeline?limit=<int>` | GET | signal 信封数组，逐项 `eventId/kind/at/title/outcome/sourceRef/monotonicMs/generation/sequence/detail` | 同上 |
| `/api/v1/dashboard/alerts` | GET | **告警数组**（见 §5.3 的具名缺陷：这条今天没有信封） | 同上 |

路径字面量在 `gatewayAdapter.ts:40-44`（`PROPOSED_ENDPOINTS`），请求侧只有 `method: "GET"` 与 `accept: application/json`（`:400`）。冻结动作 = 这三条路径与形状从此不再变；要加第四条必须先改本记录。

### 2.2 信封：缺口必须具名，值必须带出处

`dashboard/src/adapters/gatewayAdapter.ts:66-97` 的解码规则就是契约，G 侧必须逐条满足，否则前端 `contract_mismatch` 失败关闭（不猜测、不补默认值）：

1. `status ∈ {known, unknown, unavailable, not_wired, permission_denied}`（`dashboard/src/domain/signals.ts:8` 的五值枚举，`gatewayAdapter.ts:64`）。
2. `status != known` ⇒ **必须**给非空 `reason`（`:91-95`），否则整份读取判红。
3. 每个信封都要带 provenance 三件套 `sourceRef` / `observedAt` / `staleAfterMs`，缺任何一个即拒（`:84-90`）。
4. `value` 只在 `known` 时校验类型（`:99-109`）；类型不符 ⇒ 整份判红，而不是把该字段降级。
5. 顶层 `schemaVersion` 必须逐字等于冻结值（`:220-222`）。

失败分类同样冻结（`domain/adapter.ts:4-12` 的七个 kind + `gatewayAdapter.ts:378-386` 的映射）：`401/403 → permission_denied`、`404 → contract_mismatch`（明确写成「Gateway 只读接口尚未实现」）、其余非 2xx → `disconnected`，超时 → `timeout`，未配置 base URL → `not_configured` 且**零网络调用**（`:445-458`）。

### 2.3 版本号

冻结值定为 `kin-dashboard-readmodel/1.0.0`。改名那一笔属 D 的接线卡（`dashboard/**` 是它的独占面），G 的服务端必须回答同一字面量。**在两侧都改完之前，任何真实 Gateway 响应都会被前端判 `contract_mismatch`——这是期望行为，不是回归**：它保证「G 已实现」不能靠口头宣称成立。

### 2.4 v1 用轮询三条 GET，不实现 WebSocket 推送（并说明它与既有文档的关系）

`docs/standalone-runtime-dashboard.md:31` 写的是「浏览器通过 HTTPS/WSS 连接 Kin Gateway」，`:56` 又规定实时状态走「Gateway WebSocket → 状态快照增量、事件和健康信息；不能直接暴露密钥/原始私密记忆」，`:13` 把 Web API 与鉴权划进 Gateway 职责。而 D1 落地的前端只做了**轮询式 REST**：三个 GET、一个 3 秒超时、每次读取重新算新鲜度（`staleAfterMs` 在信封里由响应自报，`gatewayAdapter.ts:84-90`）。
本卡的裁决：**契约 v1 = 那三条 GET**，不实现 WS。理由不是 WS 不好，而是两条具体的：

- 加了 WS 就有**两套新鲜度语义**（推流的时间戳 vs 轮询的 `observedAt`），而 D1 的所有面板测试只固定了后一种；在一个还没有服务端实现的契约里同时冻结两种，等于让 G 的实现自己去猜它们的优先级。
- 「增量」推送会让 §2.2 的失败关闭规则失效：一条只带部分字段的增量，到底算 `unknown` 还是算沿用上一次的值？前者会把面板刷成一屏缺口，后者正是 §0 里那条「缓存值不能看起来像活着的 Kin」（`dashboard/src/domain/adapter.ts:55-58` 的 `unreadableSnapshot` 注释）所禁止的事。

所以 WS 排到 v1 之后，并且届时**必须复用同一个 signal 信封**（同一 `status` 枚举、同一 provenance 三件套、非 `known` 必填 `reason`）——这一句是对 `:56` 那条「不能直接暴露密钥」约束的字段级落实方式。`:13` 的「鉴权」今天也不实现：Core 无 HTTP 层、§5.1 的结构性不可达已经让「Dashboard 能写什么」没有实现面可答，因此 v1 不引入管理员 token；`401/403 → permission_denied` 的分类保持为空转的分支（D1 已实现它，`:378-382`），等真有鉴权形态时不需要改前端语义。



## 3. 字段 → 载体映射（本轮按当前字节实测）

方法（可复现）：扫描 `src/`、`tools/`、`test-orchestrator/` 三处共 **133** 个 `.py` 文件，对每个名字做大小写不敏感的整词字面量行计数。本轮用的批量脚本在 `.tmp/m-r79/token_census.py`（未入版本控制的暂存件，日志 `.tmp/m-r79/token-census.log`），下表每一格都可由这条仓库内命令单独复算：`grep -rni --include=*.py -w <名字> src tools test-orchestrator`。proto 侧另用 `grep -rn --include=*.proto`。三档：**A = Core 有具名载体**、**B = 只有部分载体（须改名或收窄）**、**C = 无载体（第一版必须 `not_wired`）**。

| D1 提议字段 | 档 | 载体（现字节） | 冻结口径 |
| --- | --- | --- | --- |
| `kinId` | A | `cli/status.py:87` `kin_id` | 直接投影 |
| `runtimeState` | B | `ObservedState` 恰三值 `idle/running/unresolved`（`status.py:34-40`）；`paused`/`recovering` 在 `src/**.py` 命中 **0** | 第一版只允许那三值；`paused/recovering` 撤下（无载体，不得由 UI 造） |
| `bridgeLink` / `serverLink` | A | 台账事件 `BridgeHelloAccepted`、`JoinObserved`、`PlayableEstablished`、`SessionInterrupted`、`ClientProcessExited`（`adapters/sqlite/session_log.py:47-96` 的闭集）+ run document `connection_state` | 由事件行序投影，不得自造链接状态机 |
| `session.sessionId/generation/startedAt` | A | `ClientSummary{session_id,generation,overlay,pid,liveness}`（`status.py:44-58`）、`SessionProcessStarted.argv_digest` | 可给；`overlay`/`pid` 也属只读事实，允许加 |
| `session.mode`（`A_companion`/`B_standalone`） | C | `src/**.py` 无该枚举（`companion` 命中 0，`standalone` 只命中一处无关 docstring：`adapters/evidence/trace.py:4`） | `not_wired`，理由具名「Core 尚无会话模式枚举」；等产品决定 |
| `world.profileId/profileName` | A | `AuthPolicyFrozen.server_profile_id` / `server_profile_revision`（本轮私有卷台账行逐字可见）、`server-profile.json` | 可给，取 Core 已记的值，不重新推导 |
| `world.worldContext` / `epoch` | B | `world_context_id` 15 处（首处 `domain/world_activation.py:81`）、`epoch` 55 处（首处 `domain/hosted_world.py:9`）；但规范卷上那 345 行 `world_context_id` 全为 null（读数登记在 `docs/development-execution-plan.md` §4 `P0-OFFLINE-090-100-REGISTRATION-001` 行） | 只能作「Core 记了什么」原样透出，null 就是 null；不得用 null 相等判世界相同 |
| `world.joined` | A | 服务端日志与 `JoinObserved` | 可给 |
| `world.resolvedVersion` | C | 命中 **0** | `not_wired` |
| `versions.runtime/bridge/clientBundle/java/fabricLoader` | B | 版本取料与 bundle 候选在 `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json`、`bridge-1201/**` 侧；无统一「五件套」读接口 | G 现读具名来源后才可 `known`；否则整组 `unavailable` |
| `bridgeHeartbeat.intervalMs` | A | `ControlWatchdog.__init__(interval_ms=…)`（`domain/control_watchdog.py:40-42`） | 可给 |
| `bridgeHeartbeat.lastObservedAt` | A | `LedgerSummary.last_observed_at_utc`（`status.py:65-72`） | 可给，并注明它是**台账**时间而非桥时钟 |
| `bridgeHeartbeat.lastSequence` | C | `ControlHeartbeat` 只有 `{generation, monotonic_ns}`（`control_watchdog.py:30-35`）；`last_sequence` 命中 **0** | 撤下或改映射到台账 `position`（`status.py:111` 的 `ORDER BY position`）；不得造计数器 |
| `bridgeHeartbeat.inputLeaseHeld` | A | `input_lease` 12 处（首处 `cli/session.py:92`）+ 台账 `InputLeaseGranted/InputReleased/InputRefused` | 可给，且必须是**当前布尔**而非历史计数 |
| `selfState.health/food` | A | `SelfStateValue{health,max_health,food,saturation,alive}`（`domain/perception.py:76-84`） | 可给；建议同时补 `maxHealth/saturation/alive`，它们与 health 一起才是 Core 判相干性的那组 |
| `selfState.dimension` | C | `src/**.py` 命中 2，都在启动器注释里的那句服务端日志行（`adapters/launcher/game_options.py:21`）；proto 无该字段 | `not_wired` |
| `selfState.guiOpen` | C | 命中 **0**；proto 里对应的是 `current_screen`（`proto/minekin/v1/observation.proto:136`），Core 域对象未取 | 撤下 `guiOpen`；若 G 要读 `current_screen`，须先在 Core 侧有具名载体，属产品决定 |
| `evidence.runId/attempt/bundleDigest` | A | `cli/evidence.py:136,152,171` 的 `bundle_digest`、attempt 序列 | 可给，值只来自已封 bundle |
| `evidence.sealedAt` | B | `sealed_at` 在 `src/**.py` 命中 0，只出现在 `tools/seal_repo_case.py:207` | G 现读真字段名后才可 `known` |
| `liveView.*` | C | `webrtc/mjpeg/hls/live_view` 各 0（D1 已把它硬编码 `not_wired`：`domain/adapter.ts:73`，理由是「没有 framebuffer 采集与媒体中继进程」） | 保持 `not_wired`；P2 媒体另开 lane，不用假画面充 Live View |
| `alerts[]` | C | `alert` 在 `src/**.py` 命中 **0** —— Core 不产告警 | 见 §5.3 |
| `timeline[].sourceRef` | B | Core 的出处是事件类型名 + `position` + bundle 相对路径；`source_ref`/`sourceRef` 命中 0 | G 定一个稳定格式（建议 `ledger://<kin_id>/<position>` 与 `bundle://<artifact>`），写进本记录后才允许接线 |

一句话结论：**D1 的 11 个快照字段里，今天能诚实 `known` 的是 6 组**（kinId、runtimeState 的三值版、两条链接、session 的时间/世代、heartbeat 的 interval/lastObservedAt/inputLeaseHeld、selfState 的 health 组、evidence 的 run/attempt/digest）；**必须 `not_wired` 的是 6 个**（`session.mode`、`world.resolvedVersion`、`lastSequence`、`selfState.dimension`、`selfState.guiOpen`、`liveView`），外加整条 `alerts`。

## 4. 身份与脱敏：只读面能说什么

Core 今天已经记下的身份载荷是一组固定字段（`domain/session_material.py:135-164 identity_ledger_record`）：`identity_candidate_id`、`session_username`、`session_uuid`、`observed_account_type`、`client_id_present`、`xuid_present`、`credential_values_exposed`、`matched`、`mismatches`。本轮私有卷活体台账里那行 `SessionIdentityCompared` 逐字与此一致（**私有卷读数，不是 sealed bundle**）。

冻结规则：

1. **允许出现**：`kin_id`、`session_id`、`generation`、`session_username`、`session_uuid`、四个存在性/比对布尔与 `mismatches`。名字与 UUID 不是凭据，它们是 Core 已经写进台账、并且已经封进 bundle 的事实。
2. **禁止出现**：`auth_access_token`、`auth_xuid`、`clientId` 的值、任何 argv 原文、`asserter-inputs.json` 之外的凭据面。Core 今天把这条做成了**边界处归约**而不是事后过滤：`adapters/launcher/offline_session.py:247` 列出四个身份选项（`--username/--uuid/--clientId/--xuid`），`recorded_material`（`:250-276`）读回 argv 现值之后**只把后两个折成布尔**（`client_id_present=values["--clientId"] != EMPTY_ARGV`、`xuid_present=…`），`RecordedSessionMaterial` 里没有存下凭据值的字段；证据视图 `candidate_document`（`:279-293`）的注释就是「policy and presence, never a value」，连 argv 是否在都是布尔（`access_token_argv_present`）。⇒ 契约要求 Gateway **只消费这类归约后的记录，绝不得自己读 argv 补字段**。另两条对照：Core 唯一的只读投影 `StatusReport.as_dict` 只输出 `schema_version/command/status/kin_id/state/clients/ledger`（`cli/status.py:82-91`），`ClientSummary` 只有 `session_id/generation/overlay/pid/liveness`（`:51-58`）——今天就没有凭据分量；`tools/assert_case_evidence.py:813-836 asserter_inputs_bytes` 写出的 `asserter-inputs.json` 键集合是 `schema_version/kin_id/run_id/username/previous_run_id`，另有一枚**只在真有名字时才写**的 `probed_players`（`:830-834`）——同样不含凭据值。〔该行集合在 `docs/development-execution-plan.md` §4 `P0-OFFLINE-090-100-REGISTRATION-001` 行登记时写的是 `:747-763`，现字节已被 H1i/M-C1 的增行推到 `:813`；键集合未变。〕
3. **三道既有机制留在路上**，Gateway 不得绕过或自建第二套：`domain/errors.py:53-90`（`_SENSITIVE_KEY` `:53`、`_INLINE_SECRET` `:57`、`redact_text` `:67`、`redact_data` `:82`）、`adapters/evidence/bundle.py:94 _find_secret`（含凭据字面量则整包拒写，不就地脱敏）、`domain/information_class.py:1-30`。
4. 第三道里已经为 Dashboard 预写了一句口径（`information_class.py:27-29`）：**如果线上真的需要携带信息类别（本仓库之外的消费者，或 Dashboard），那个字段必须对照这张表校验，绝不能被它的自称取信**。⇒ Gateway 必须自己判 `information_class`，不能把客户端上报的标签原样透出。
5. Bridge 侧的约束更硬：**脱敏是结构性的而不是过滤器** —— `bridge/src/main/java/org/minekin/bridge/protocol/SessionIdentityReportAdapter.java:10-16` 的类注释与 `:75-76` 的 `ObservedSession` 字段表说明，那条消息**没有** Access Token / xuid 值 / clientId 值的分量，只有 `setSessionXuidPresent`/`setSessionClientIdPresent` 两个存在性位（`:44-45`），另有 `requireRedacted`（`:51`）；`bridge-1201/` 有同一份孪生文件。⇒ 契约不新增字段穿过它，也不要求在 Bridge 侧加过滤逻辑。

## 5. 写面如何在不引入鉴权的前提下天然不可达

### 5.1 结构性不可达

- 主干没有任何 HTTP/WS 服务端实现（ADR 0001），本卡也不引入 ⇒ 「Dashboard 能写什么」这个问题今天**没有实现面可答**。
- 进程所有权表已把边界写在文档里（`docs/runtime-ipc-deployment-contract.md:23-39`）：`minekin-gateway` 拥有 Dashboard API、管理员鉴权、配置审计、Supervisor 状态；**禁止**拥有 Bridge token 与直接游戏输入；密钥不入 argv/Dashboard/日志（`:37`）。§4「Dashboard 无法取得 Bridge 凭据或发输入」（`:83-92`）是必验项。
- lease 的授予只发生在 Core 进程内路径（`cli/session.py`），Gateway 即使读到 `inputLeaseHeld` 也拿不到句柄。

### 5.2 冻结的判据（可复算，不靠自觉）

实测（本轮自量；扫描脚本在 `.tmp/m-r79/verb_scan.py`、日志 `.tmp/m-r79/verb-scan.log`，那两份是未入版本控制的暂存件，故下面给出可直接复算的仓库内命令）：

```console
grep -n '^| `/api' docs/gateway-dashboard-readonly-contract-2026-09-28.md
grep -c -E 'POST|PUT|PATCH|DELETE' dashboard/src/adapters/gatewayAdapter.ts
```

- 端点表的方法列：**3 行端点、全为 `GET`、非 GET 0 行**。
- 请求面：`gatewayAdapter.ts` 里这四个写动词命中 **0**，且该文件唯一的 `method:` 出现在 `:400` 的 `method: "GET"`。
- 诚实口径：这四个词在本文件里各只出现在 1 行上，且那一行就是上面那条复算命令自身（散文里一次都没有）；「计数为 0」判的是**端点方法与请求动词**，不是本记录的遣词。判据必须按前两条的命令复算，不按散文措辞复算。

G 的实现卡合入前必须跑同一族具名扫描（路由注册表逐条列出方法），并把读数留在它自己的 `docs/validation/` 记录里。D 侧的 `KinReadAdapter` 接口今天只有 `describe/snapshot/timeline/alerts` 四个方法（`dashboard/src/domain/adapter.ts:48-53`），**没有**任何写动词槽位 ⇒ 前端加一个按钮就等于破坏契约，这条也要在 D2 的验收里显式重述。

### 5.3 `alerts` 的具名构造缺陷：`ALERT_SOURCE_AMBIGUITY`

D1 把 alerts 解码成裸数组（`gatewayAdapter.ts:334-371`），而 Core 没有告警源（§3 普查 0 命中）。于是空数组会被 UI 读成「一切正常、没有告警」，而真相是「没有告警这件事的来源」。⇒ 冻结口径：**alerts 响应必须也带信封**，即 `{ status, reason, alerts: [...] }` 形状，第一版 `status = not_wired`、`reason` 具名「Core 无告警源：只有台账事件与 run document 的拒止计数」。这不是把数组改成对象好看一点——`domain.sh` 这一族证据已经反复证明「零读数」与「没测到」是两种事实。改这条形状属 D 的接线卡，验收见 §6.2。

## 6. 三条验收（分别落在本卡与两张下游卡）

### 6.1 本卡（M，设计面）

- ① 每个想暴露的字段都有具名载体，或被具名 `not_wired` 并给出理由 —— §3 的表即读数，普查脚本与日志在 `.tmp/m-r79/`。
- ② 身份面只以 §4 的第 1 条为准 —— 已按现字节列出允许集，且 `cli/status.py` 的 `StatusReport.as_dict` 里今天就不含任何凭据字段（`status.py:82-91`）。
- ③ 写动词为 0：端点表方法列全 GET、`gatewayAdapter.ts` 的四个写动词命中 0（§5.2 的两条命令即读数，本轮已复算）。

### 6.2 `GATEWAY-READONLY-PROJECTION-001`（G 候补 lane，新增 `gateway/**`）

- 恰好三条 GET；每条响应用 **D1 自己的解码器**跑通且零 `contract_mismatch`（判别式：故意抽掉一个 provenance 字段必须红）。
- 全部 `not_wired` 字段带非空 `reason`；`alerts` 返回信封形状。
- 响应体里凭据字面量扫描为空（复用 `_find_secret` 的名字表，不重造）。
- 不挂规范卷、不连用户远程服；离线可跑（只用 `session status` 与已封 bundle 的读路径）。
- 新增 case 一律**不登记** ⇒ 门载荷必须与实施前逐字节相同（前后各量一次并配对）。
  - 本节原先写的期望字面值是 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，那是 **H1i 时代的历史读数**，保留在此不删，但它已不是当前基线：#68 的移动窗口判据变更把 `V1201-LAN-JOINER-CONTROL-CASE-001` 的 `case_version` 从 `1e31f0003b4e30e06506e086616335db73ec975b406874d219033f151b3f812a` 移到了 `397cefb…`，于是那条已封真证被改判 `re_judged=UNJUDGED`，W60 与 p0-core 各多出一条 `CASE_VERSION_MISMATCH`，overall blocks 变为 `["CASE_VERSION_MISMATCH","REQUIRED_CASE_NOT_REGISTERED"]`。⇒ 判据变更合法地移动了门，与 G 卡无关。
  - G 卡落地时的配对读数：同一份规范卷、同一容器，**前**取 `git archive HEAD` 导出的干净树、**后**取含 `gateway/**` 的工作树，两遍 `report_promotion.py` 各 rc=1、报告 106296 字节、逐字节相同，`gate_payload_sha256` 均为 `e7e8f32f5a2261c62ce999fe690a96ae4bdf746cfddcd39a5276745c00ef8baf`。⇒ 本卡自身零门位移动，且未登记任何 case、未改任何 mandatory/registry。
- 落地侧证据（2026-09-28，提交 `0bcdc84`，远端 `main` 已核对该 SHA）：
  - 服务端与读模型在 `gateway/`（`readmodel.py` 投影、`server.py` 三条 GET 循环环绑定、`signals.py` 信封），测试在 `tests/gateway_support.py` + `tests/unit/test_gateway_readmodel.py` / `test_gateway_server.py`，共 46 条针对性用例绿。
  - 三门复量：`ruff check` 通过、`ruff format --check` 390 files、`pyright` 0 errors、`git diff --check` 净、wheel 边界 OK（`gateway` 不入包）。`pyproject.toml` 为此把 `gateway` 加进 pyright/ruff 的 `src`/`include`、把 `.` 加进 pytest `pythonpath`（读模型在产品包之外，见 `docs/adr/0001-p0-modular-monolith.md`）。
  - 真 HTTP 读数（挂规范卷 `:ro`、只读，未连任何远程服）：`kin-e7-join-0928` 上三条路由各 200（snapshot 4264 B / timeline 25 限 6770 B 实得 23 行 / alerts 256 B），POST/PUT/DELETE/PATCH 全部 405 `{"error": "the read model serves GET only"}`，表外路径 404，SIGINT 后进程 rc=0。信封规则（§2.2 四条键 + 非 known 必带非空 reason + `sourceRef` 非空串）在真字节上零违规。原始读数 `.tmp/gates/g-card-live-http-out.json`。
  - 该 kin 的真实面：`evidence` 与 `versions` 今天能 `known`（已封 bundle `a224f6c3…`、digest `5086ee42…`、`fabricLoader 0.19.5`、`java Temurin-21.0.12.1+1`、minecraft `1.20.1`），`selfState` 具名 `unavailable`，`liveView` 具名 `not_wired`，`alerts` 返回 `{status:"not_wired", reason:"Core 无告警源…", alerts:[]}`。
  - 一个字段语义澄清（下游 D 卡要用）：`versions.runtime` 装的是 bundle 清单记的**游戏运行时版本（Minecraft）**，不是 Core 自己的版本号；Core 版本今天仍无具名读接口，所以 `clientBundle` 与 `bridge` 留在 `not_wired`。UI 标签要照这个口径写，别让人读成「产品运行时 1.20.1」。

### 6.3 `DASHBOARD-GATEWAY-WIRING-001`（D lane，`dashboard/**`）

- `SNAPSHOT_SCHEMA_VERSION` 升到 `kin-dashboard-readmodel/1.0.0`，`PROPOSED_ENDPOINTS` 注释从「PROPOSAL」改为引用本记录。
- mock 与 gateway 两个适配器跑同一套面板测试；未配置 base URL 时零网络调用（`gatewayAdapter.ts:445-458` 的形状保持）。
- `alerts` 走信封形状（§5.3），且「没告警」与「无告警源」在 UI 上是两个不同呈现。
- 撤下 §3 判为 C 档的字段（`session.mode`、`resolvedVersion`、`lastSequence`、`dimension`、`guiOpen`）或显式渲染成 `not_wired`，不得留一个会自填默认值的解析分支。
- 落地侧证据（2026-09-28，提交 `a37f3c3`，远端 `main` 已核对该 SHA）：
  - 四条验收逐条：① `SNAPSHOT_SCHEMA_VERSION = "kin-dashboard-readmodel/1.0.0"`（`src/domain/model.ts:8`），端点表注释从「PROPOSAL」改成指名本记录（`gatewayAdapter.ts:56`），解码失败文案也直接引用它（`:584`）。② `src/panels/panelAdapters.test.tsx` 用同一套面板断言跑 mock 与 gateway 两个适配器，`config.ts:74` 保持「没有 base URL 就不构造取数器」的形状。③ `AlertsPanel.tsx` 分三种 DOM（有告警的列表 / `alerts-empty` / `alerts-no-source`），「没告警」与「无告警源」在界面上是两屏。④ §3 判为 C 档的字段已从模型撤下（`SelfState` 不再带 `dimension`/`guiOpen`，`KinRuntimeState` 收窄为 Core 的三值），且 `decodeField`（`gatewayAdapter.ts:159-195`）要求成员恰有 `value` 或 `gap` 之一——`value:null` 与无 `reason` 的 gap 直接判红，没有会自填默认值的分支。
  - 针对性测试：`dashboard` 内 `pnpm typecheck`（`tsc --noEmit`）rc=0；`pnpm test`（vitest）7 文件 75 passed（本卡前是 5 文件 35 条）。
  - 「不用 mock 冒充完成」按真字节量，而不是按 fixture 自证：把 §6.2 那次真 HTTP 读数的原始响应（`.tmp/gates/g-card-live-http-out.json`，真 `sourceRef` 形如 `core://status/kin-e7-join-0928/<组>`、`bundle://a224f6c3…/manifest.json`、`ledger://kin-e7-join-0928/<n>`）直接喂给 `decodeSnapshotPayload` / `decodeTimelinePayload` / `decodeAlertsPayload` ⇒ 三条零 issue；抽出 `bridgeHeartbeat.sourceRef` 后快照解码必须红。该探针要跨仓库读文件，跑完即删、未入库；把真字节形状固化进仓库的是 `src/test/realGatewayWire.ts`（成员 gap 的 `reason` 文案与真字节逐字一致，kin 名与时间戳做了中性化）。
  - 主干门读数（本卡只动 `dashboard/**`，Python 侧字节未变）：`uv sync --locked --dev`、`ruff check`、`ruff format --check`（390 files）、`pyright`（0 errors）、`uv run pytest -q`（2776 passed, 2 skipped）、`check_boundaries`、`check_case_assertions`（151 registered）、`verify_fixture_digests`、`check_workflow_pins`、`uv build --wheel` + `check_wheel_boundary`、`minekin --help`、`git diff --check` 全部 rc=0。门载荷未动：本卡不新增 case、不碰 mandatory/registry。
  - 一个未闭合的格子：`.github/workflows/ci.yml` 的 `- run:` 步里没有任何 `pnpm` / `dashboard` 步 ⇒ 上面两条 Dashboard 读数是本机会话量到的，不是 CI 量到的。要不要给 Dashboard 加 CI 门属共享基础设施变更，停在主控决定，本卡未动 `ci.yml`。

## 7. 本轮读数的可复现路径

- 普查：`grep -rni --include=*.py -w <名字> src tools test-orchestrator`（本轮批量脚本 `.tmp/m-r79/token_census.py` 与日志 `.tmp/m-r79/token-census.log` 均为未入版本控制的暂存件，故判据以上面这条 grep 为准；133 文件）。
- 契约面：`dashboard/src/adapters/gatewayAdapter.ts`（端点 `:40-44`、信封 `:66-109`、失败分类 `:378-386`、未配置零调用 `:445-458`）、`dashboard/src/domain/adapter.ts`（七个 kind `:4-12`、四方法接口 `:48-53`、`unreadableSnapshot` `:59-79`）、`dashboard/src/adapters/config.ts`（默认 mock `:24-29`、开关 `:44-55`）、`dashboard/src/domain/model.ts:8`（版本字面量）。
- Core 只读投影：`src/minekin_core/cli/status.py:34-91,108-119`、`src/minekin_core/domain/control_watchdog.py:30-42`、`src/minekin_core/domain/perception.py:76-84`、`src/minekin_core/adapters/sqlite/session_log.py:43-96`、`src/minekin_core/cli/evidence.py:136-171`。
- 脱敏：`src/minekin_core/domain/errors.py:53-90`、`src/minekin_core/adapters/evidence/bundle.py:94`、`src/minekin_core/domain/information_class.py:1-30`（第 27-29 行是那句 Dashboard 预留口径）。
- 身份面：`src/minekin_core/domain/session_material.py:135 identity_ledger_record`、`src/minekin_core/adapters/launcher/offline_session.py:247 _RECORDED_OPTIONS`、`bridge/src/main/java/org/minekin/bridge/protocol/SessionIdentityReportAdapter.java:10-16,44-51,75-76`。
- 文档边界：`docs/adr/0001-p0-modular-monolith.md:15,23`（「不引入 Web API 或 Dashboard；P0 的管理入口是本地 CLI」与其代价说明）。
- 既有 Dashboard / IPC 契约文本：`docs/standalone-runtime-dashboard.md`（全文 241 行；Gateway 职责、HTTPS/WSS、P0 以 CLI 代替、WS 不暴露密钥那几段）、`docs/runtime-ipc-deployment-contract.md:7-17,23-39,83-92`（进程所有权表与必验项 5）。本记录不推翻它们，只把「浏览器读什么」落到字段级。
- 口径提醒：本记录里唯一非仓库字节的读数是 §3 `world.profileId/profileName` 那格提到的台账行，它取自 **M 的私有卷活体**（`.tmp/r75e/out-host/r75e-online-false/90-readouts.txt` 第 (g) 段）⇒ 它证明字段形状存在，**不是 sealed bundle**，也不作为任何晋级依据。其余全部读数只取仓库字节，本卡全程未挂载任何数据卷。

- G 卡侧的可复现命令（读模型 + 真 HTTP 读，两条都只挂 `:ro`）：
  - 针对性测试：容器内 `PYTHONPATH=/src:/src/src LD_LIBRARY_PATH=/opt/sqlite/lib python -m pytest tests/unit/test_gateway_readmodel.py tests/unit/test_gateway_server.py` ⇒ 46 passed。
  - 起服务端并读三条路由：同一容器里 `python -m gateway.server --data-root <卷根> --kin <kin 名> --host 127.0.0.1 --port 8787`，脚本 `.tmp/gates/g-card-live-http.py` 会自己拉起子进程、GET 三条、对四条写动词各打一枪、再探一个表外路径，并把结果打成一份 JSON 报告。根目录是 `MINEKIN_HOME` 那一层，kin 名在它下面的 `kin/` 里（卷根有 18 个 kin，所以 `--kin` 必填）。
  - 中文全角标点走 `gateway/readmodel.py` 文件级 `# ruff: noqa: RUF001` 加三行理由（与 `restart_rules.py` 同法）；**不**放开全局 `allowed-confusables`，那会让已有文件的 noqa 变成 RUF100，等于改写未触及文件的门读数。

## 8. 未验证 / 停在决策门的格子

- **服务端已经落地并跑过真 HTTP 读**（见 §6.2 落地侧证据，提交 `0bcdc84`），**浏览器侧的解码面也已落地**（见 §6.3 落地侧证据，提交 `a37f3c3`，含「真 HTTP 字节过 D 的解码器零 issue」这条）：仍然未测的是在真实浏览器里操作一次界面的读数（§6.3 的量法是 vitest + 真字节，不是 Playwright 活体）、多客户端并发读同一个 SQLite 台账的行为、以及 3 秒超时下的时延分布。
- **`world.worldContext` / `epoch` 的值能不能给用户看**未裁决：它们与世界 seed、存档目录名相邻，而 §4 只保证凭据不外泄，没有覆盖「世界坐标类信息」。⇒ 属主控/产品决定，本轮把它留在 B 档并显式标出。
- **哪些 run document 拒止算「告警」**是产品语义（`cognition_refusals`、`report_refusals`、`snapshot_rejections`、`input_refusal` 都在文档里，但没人规定阈值）。⇒ §5.3 先按「无源」封住，等有决定再开。
- **跨 bundle / 跨世界的长期视图**（Live View、多 Kin 总览）仍在本契约之外：`P2 媒体` 与 `HOST/PERSIST` 各守原决策门。
- 本卡的门读数（`ruff check`/`ruff format --check`/`git diff --check`、门载荷是否移动）与这笔提交自身的 CI，写在 `docs/v1201-lan-control-next-2026-09-27.md` §2.74 与 `docs/qoder-execution-handoff.md` 第七十九轮，不在这里预先宣称。

## 9. 修订（2026-09-30）：台账新增 `SkillStepRecorded`，快照新增 `skillSteps` 组

本节是追加修订，上文各节字节不动。Core 侧（只读参照，非本卡面）已在 `src/minekin_core/adapters/sqlite/session_log.py` 加上事件类型 `SKILL_STEP_RECORDED = "SkillStepRecorded"`，并在 `src/minekin_core/cli/session.py` 的 `on_run_skills` 里**每个结论了的世界技能步骤**向同一枚台账追加一行，payload 键全为 JSON 标量：`step_index`（1 起的 int）、`skill`、`result`、`reason`、`action_id`、`attribution`、`decision_source`、`model_refusal`、`goal`。`result` 是 Core 由**后续世界读数**判出的 verdict，三值 `CONFIRMED/FAILED/UNKNOWN`，不是 Bridge 上报的 `SUCCEEDED`。

冻结口径的增量与不变量：

- **读源与路由计数不变**：还是 §2.1 的三条 GET，`skillSteps` 取自既有的台账只读路径（`connect_reader`，窗口 `LEDGER_WINDOW = 400`），不新增读源、不新增端点、不读活 Bridge / 其它进程 / argv。`SNAPSHOT_SCHEMA_VERSION` 保持 `kin-dashboard-readmodel/1.0.0` 不升——升版会让两侧落地前的每一读假红，与本组「向后兼容缺组字节」的解码规则（末条）二选一即可。
- **快照组 `skillSteps`**（`gateway/readmodel.py` `_skill_steps_group`，信封 `known`，`observedAt` = 最近一行的 `observed_at_utc`，`staleAfterMs = null`：与 §3 `bridgeHeartbeat.lastObservedAt` 同一口径——它是台账时间，不按时间判陈旧）。值成员恰 11 个（camelCase）：`goal / stepIndex / skill / result / reason / attribution / decisionSource / modelRefusal / stepCount / modelCost / modelConfig`，每个都是 §2.2 第 4 条同族的 `{value}` 或 `{gap}` 成员。投影走**具名 allowlist**（`_SKILL_STEP_DETAIL_FIELDS`，timeline 的 detail 同源）：`action_id` 按 §4 的恒规属台账内部标识，**绝不进面板**——两侧（`readmodel` 测试与 `gatewayAdapter.ts` `parseSkillSteps` 的 canary）各有一条测试钉住它出现即整读拒绝。
- **具名缺口的两档语义**（措辞是 `readmodel.py` 的模块常量，`dashboard/src/fixtures/mockFixtures.ts` 逐字镜像，防两侧漂移）：Core **按构造**写了空串的成员渲染为 `unavailable` 具名缺口而不是空值——脚本运行（`--skill-plan`，`decision_source = OPERATOR_PLAN`）的 `goal`、`CONFIRMED` 步的 `reason` 与 `attribution`、非模型决策或模型作答了的 `model_refusal`；行里缺失/形状不符的才是 `unknown`。`modelCost` 与 `modelConfig` 恒为 `not_wired`：调用花费（`model_calls / model_spent_micro / model_cap_refusals`）与模型配置状态只在 run document 的 mind 段记录，技能步行与已封 bundle 的清单都不携带，本投影不解析 run document。
- **不折零**：该 kin 台账里没有这类行 ⇒ 整组 `unknown` 缺口（「台账里没有技能步行（SkillStepRecorded）：最近这个 run 没有跑过世界技能——只连接、只演示输入的运行不会有这类行，这里不把它折成「0 步」。」），而不是 `stepCount: 0` 的假事实。`stepCount` 只在 400 行窗口**未满**时是确切值；窗满则降级为带窗内读数的 `unknown`（确切总步数不可得）。
- **时间线**：`SkillStepRecorded` 加入 `TIMELINE_READING`（kind `intent`），outcome 按 verdict 映射 `CONFIRMED→applied / FAILED→rejected / UNKNOWN→unknown`；它不进 `_BRIDGE_ROWS`/`_SERVER_ROWS`/`END_OF_RUN` 任何一组——一步结论既不是链接态也不是会话边界。
- **读端向后兼容**：§6.3 固化的逐字历史捕获（`dashboard/src/test/realGatewayWire.ts`）没有 `skillSteps` 键。解码规则：键缺失 ⇒ 合成组级 `not_wired` 缺口（`sourceRef = "snapshot://absent/skillSteps"`，理由具名「产自加上该投影之前的 Gateway」），**不**判 `contract_mismatch`、**不**重采捕获、**不**改捕获字节；键存在但形状不符 ⇒ 照 §2.2 整读失败关闭。`result`/`decisionSource` 在 Dashboard 侧解码为普通字符串而非钉死枚举：Core 日后新增 verdict 词时按原值渲染，而不是把整份快照拒红（有一条测试专门钉这一点）。
- **锚点**：Gateway 侧 `tests/unit/test_gateway_readmodel.py`（新行投影最近步 + 计数、脚本运行的 goal 缺口、无行 kin 的组缺口、timeline 判别含 `action_id` 不外泄）；Dashboard 侧 `contractDecoder.test.ts`（缺组旧字节 / 带组新字节 / 成员判别 / 新 token）、`panels/skillStepPanel.test.tsx`、`fixtures.test.ts`、`App.test.tsx`。面板 `SkillStepPanel.tsx` 挂在总览页会话进度之后；能力表（`shell/capability.ts`）把「自主目标 / 技能步读数 / 失败归因 / 决策来源」登记为 live 行，「人格摘要 / 关系 / 模型调用花费与配置状态」留在缺口行——有真源的与没有真源的不混在一格。

## 10. 修订（2026-09-30）：台账新增 `AutonomousRunHalted`

本节是追加修订，上文各节（含 §9）字节不动。它补的是 §9 落地后实测出的那一格缺口：一次自主运行的**收尾名字**只写在 run document 里，台账里没有行——面板最新一格因此只能是最后一步的失败理由加 `SessionInterrupted`，读起来像「频道断了」，而读数其实说「心按名字停下了」。

Core 侧（只读参照，非本卡面）在 `src/minekin_core/adapters/sqlite/session_log.py` 加上事件类型 `AUTONOMOUS_RUN_HALTED = "AutonomousRunHalted"`，由 `src/minekin_core/cli/session.py` 的 `on_run_skills` 在 `run_autonomous_loop` 返回之后、会话收尾之前追加一行，payload 成员：`goal`（心追的目标名）、`stop_reason`（循环自己的收尾词，如 `NO_FEASIBLE_SKILL` / `STEP_BUDGET_SPENT` / `CONTROL_CHANNEL_LOST`）、`error`（仅 `CONTROL_CHANNEL_LOST` 才有的**异常类名**，如 `ConnectionError`；其余收尾为空串）、`steps`（int，实际走了几步）、`confirmed`（int，其中按后续世界读数判为 `CONFIRMED` 的步数）、`excluded_skills`（字符串数组，心改线时排除掉的技能名）。走 `--autonomous` 才有这类行；脚本化的 `--skill-plan` 不跑循环，也就没有收尾可记。

冻结口径的增量与不变量：

- **读源与路由计数不变**：仍是 §2.1 的三条 GET，行仍取自既有的台账只读路径（`connect_reader`，窗口 `LEDGER_WINDOW = 400`）；`SNAPSHOT_SCHEMA_VERSION` 保持 `kin-dashboard-readmodel/1.0.0` 不升；**快照不加新组**——这一行只进时间线，面板无需改解码（时间线是逐行通用解码的）。
- **具名 allowlist**：detail 只投影 `_AUTONOMOUS_HALT_DETAIL_FIELDS` 这六个成员，顺序即 `goal, stop_reason, error, steps, confirmed, excluded_skills`；字符串数组渲染为 `a|b`，空串与空数组**整格省略**而不是渲染成 `error=` 或 `excluded_skills=[]`——按构造为空的成员渲染出来会读成投影 bug 而不是这次运行的真答案。数组成员逐元素验 `isinstance(str)` 且长度相符才投影，形状不符即整格省略（不 `str()` 兜底），非 allowlist 的键（如 payload 里刻意放的 canary）一律不出现在字节里。
- **`error` 只取类名，不取 message**：`type(error).__name__`。异常文本可能带 socket 地址、路径或环境细节，§4 的口径是「说得出形状，说不出秘密」，类名足够区分「桥关掉了套接字」与「写入被拒」，而这两者正是频道断掉之后**任何后续读数都再也拿不回**的事实——丢掉它的那一步就是唯一的证人。该成员由 `src/minekin_core/application/autonomous_play.py` 的 `AutonomousRun.stop_detail` 携带，并同名写进 run document 的 `autonomous` 段（`stop_detail`），与台账行同源。
- **`action_id` / `lease_id` 恒不进面板**：与 §9 末条同规，`tests/unit/test_gateway_readmodel.py` 的两条新用例各带一枚 canary 钉住它出现即拒绝。
- **时间线**：`AutonomousRunHalted` 加入 `TIMELINE_READING`，为 `(decision, applied)`。`applied` 说的是**这行被记下了**这个事实，不是这次运行成功了——收尾词本身（`stop_reason` / `error`）才是运行结果，把它折成 `rejected` 会让一次正常跑完的自主运行看起来像故障。它不进 `_BRIDGE_ROWS` / `_SERVER_ROWS` / `END_OF_RUN` 任何一组。
- **锚点**：`tests/unit/test_gateway_readmodel.py` 的 `test_the_halt_row_says_the_name_the_mind_stopped_on`（全成员 + canary）、`test_a_halt_row_with_nothing_excluded_names_only_the_stop`（空成员省略）、`test_a_halt_on_a_lost_channel_names_the_error_that_lost_it`（`error` 投影且非 allowlist 键不外泄）、`test_every_ledger_event_type_has_a_timeline_reading`（闭集覆盖）；`tests/unit/test_autonomous_play.py` 的 `test_a_lost_channel_names_the_error_that_lost_it` 与 `test_a_stop_the_world_caused_names_no_channel_error`（名字只在频道分支出现，别的收尾为空）。
- **活体依据**：见 `docs/local-demo-runbook.md` 六之二、六之三两节。run `a1d749937d864203ac50de8f98884882`（本地受控服务器、`minekin-local-demo` 卷）台账位置 146 是这一行的第一条真实字节：`goal=hold_a_wooden_pickaxe, stop_reason=CONTROL_CHANNEL_LOST, steps=4, confirmed=4`，`excluded_skills` 空 ⇒ 按规省略，`kind=decision / outcome=applied`，整份投影里 `action_id` 与 `lease_id` 零出现。同一条命令再跑一次的 run `78be6675c11d4661bb9f2bc86f6fb283`（位置 176）是 `error` 成员的第一条真实字节：`goal=hold_a_wooden_pickaxe, stop_reason=CONTROL_CHANNEL_LOST, error=ConnectionResetError, steps=4, confirmed=4`，而 run document 同一事实写作 `autonomous.stop_detail: "ConnectionResetError"`——两侧同源，类名之外没有任何异常文本落到面板。146 那行早于 `error` 成员，因此它**不含**该成员，这一格按实登记，不追补。
