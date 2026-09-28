# 1.20.1 LAN 加入者的最小控制：E6 后连续任务卡

状态：`PROPOSED_FOR_M_INTEGRATION`，基线 `main=d26a2dd15c370002945e500e8cfd3adeff58252d`。本分支经 M 按真实增量审查并合入后才激活。主干唯一 `current_next` 继续是 `PARALLEL-INTEGRATION-GATE-001`；下面的 H、V、M、E 卡逐张推进，绝不同时把两个 lane 卡标成 NEXT。

## 0. 裁决：E6 真证明了什么，没证明什么

H1g 已让受控 1.20.1 加入者使用现有 v2 loopback/offline/单版本 profile，V4 在**私有本地卷**实测两个客户端的 LAN 加入者达到 `JOIN`、首快照、`PLAYABLE`。E6 的真封证也成立，但它跑的是 `MINEKIN_DOMAIN_CASE=V1201-020` 加 `--server-profile ...controlled-offline-server-1.20.1.json` 的**本地专服 + 单客户端**路径：规范卷 seq4 `73a52bfb…`/bundle `b2b4133b…`，三条断言为服务端身份、首快照、离场。它没有 `MINEKIN_DOMAIN_JOIN`、没有第二客户端 `Kin2`、没有验证 H1g 的 LAN 加入者 path；所以不得把 E6 改述为“V4 的同一条 LAN 形状已封证”。这是一处任务拆分的范围缺口，**不是 E6 bundle 失效**。

`reviewed-tested-bundles.json` 已有 `V1201-020` 的同构建 PASS 引用（attempt 2，run `ece5d0cb…`），还引用 `V1201-040` 的同构建 PASS（attempt 2，run `155dcb4a…`）。E6 seq4 没有解决一个“registry 缺 V1201-020 引用”的问题。主控当前裁决：**暂不替换该引用，也不把 `V1201-020` 翻成 mandatory**；两种动作都会动 case/registry 或门载荷，却不是 LAN 加入者控制的前置。保留 seq4 为独立可复验的新证据。后续若发现旧引用不能通过当前 `verify_tested_provenance.py`，先给出真实失败读数，再单独审查替换；`mandatory` 的集合属于 `P0-GATE-PROMOTION-001`，应在完整 required-case 表和反例复判后整体决定，不以一条新 PASS 求绿。

用户已授权 1.20.1 为主线、自动按目标版本选受审 bundle；这**不是** V08 连接用户远程服的新授权。本队列只连接受控 runner 本次自己启动的 loopback 专服或 LAN 世界。`domain.sh` 对 `--auto-bundle` × joiner 的现有拒止不动；在线认证、任意远程地址、HOST/PERSIST 与封存 schema 扩字段仍守各自门。

## 1. 完成定义及不可混用的证据等级

下一阶段要回答的是：1.20.1 第二客户端 `Kin2` 加入**第一客户端临时发布的 LAN 世界**后，能否在同一 generation 里取得有限 lease，执行一次小幅 look 和有界 move，显式 release 并退出，且宿主世界的独立读数证实转向/位移/停止。已有 V4 只到 JOIN/首快照，已有 E6 只在专服单客户端上 sealed JOIN，已有 V1201-040 是专服单客户端控制。三者不能拼成这条新结果。

执行中的证据标识固定为四态：`私有活体读数`、`规范卷 SEALED`、`机器候选 promotable`、`主控已晋级 tested`。只有真正发生且经过相应复核，才能逐级写入；任何一级不能代替下一层。记录每次 run 的真实 recipe/bridge/runner SHA、Kin/session/generation、服务端版本、客户端日志、控制命令和 server oracle，远程地址不入仓库。

## 2. 连续队列与文件所有权

### H1h `V1201-LAN-JOINER-BOUNDED-CONTROL-DRIVER-001` — 第一张，H lane

前置：H1g/V4/E6 已合主干；M 确认 H lane 的 `domain.sh` 与契约测试无活动写者。允许改 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/` 记录；若必须改其他测试 runner 文件，先单笔范围修订交 M，不能顺手碰产品 `src/**`、Bridge、case 判据/fixture、registry、门禁或封存 schema。独立 worktree/分支从最新远端 main 起卡，H 不直接写 main；规范卷至多只读，不能建 attempt/bundle。

先读现有 `join_the_published_world()` 与 host-side look/hold/release 路径，确认加入者达到 `PlayableEstablished` 后仍有可控窗口。提供一条**显式 opt-in、默认关闭**的本地测试驱动，使动作目标是加入者 Kin 而不是宿主 Kin：在加入者本代 `PLAYABLE` 后、停止前，以现有受 lease 约束的 CLI/API 发一次不超过本地契约限幅的 look、一段不超过 2 秒的 forward、`release_all`，然后停止加入者。控制请求的 Kin/session/generation 必须与加入者自己的台账一致；旧代/错误 Kin/未 PLAYABLE/无 lease/超限请求一律具名拒绝且零输入下发。不得靠 `sleep` 时长、CLI rc=0 或 grep 到动作字样代替实际执行。不能修改 `domain.sh` 的 auto+joiner 拒止，也不能为了这张卡改公网准入。

红绿验收：旧字节上新的加入者控制定向测试应红；新字节上 host-only 默认路径与 1.21.4 正对照不变，显式 opt-in 路径可分辨 joiner 和 host；至少两项非空转反证（把目标 Kin 换宿主、把 `PLAYABLE` 前置绕掉）各使具名测试红。`bash -n`、runner 契约、ruff/pyright/边界/fixture 守卫和可运行的全量本地测试通过；局部/Docker 读数用私有 root，规范卷不可写。若现有产品 API 无法对加入者安全取 lease，只停在该层，交 M 另立**单独产品卡**，不在 H 卡里放宽控制语义。

### V5 `V1201-LAN-JOINER-LOCAL-CONTROL-READOUT-001` — H1h 合入后 V lane

只在私有数据根和本地 loopback 世界运行；V 只写一份 `docs/validation/` 活体记录及忽略的私有原物，不改 H、产品、判据或 registry，不写规范卷。以 H1h 当前字节驱动一次 1.20.1 host+joiner，逐步记录两侧 JVM/Bridge、joiner `PLAYABLE`、授 lease、look/move 的应用回执、宿主 server oracle 的 yaw 与水平坐标、lease 到期或显式 release 后停止、加入者离开、宿主最终退出。动作限幅，遇不安全出生点或服务器拒绝则不加长、不重试撞绿。

必须做同形状无动作对照、错误 Kin/旧代或未 `PLAYABLE` 的拒止反例；区分“客户端自报转/走”“宿主服务端确认转/走”和“只看见命令发出”。若第一真实停点是库存、Bridge、lease 或 server oracle，保留原始日志并交 M 按单一层开窄卡。V5 即使全绿仍只叫私有活体读数，不写成 sealed。

### M-C1 `V1201-LAN-JOINER-CONTROL-CASE-001` — V5 有可判载体后由 M 独占

M 先判现行 `V1201-040`（W60、专服控制）和 `CORE-030`（1.21.4 LAN 加入）各自输入/判据/服务端 oracle 能否在**同一真实 1.20.1 LAN 加入者 run**上诚实成立；不可拿两份旧 bundle 拼答案。若现行 case 不能表达，登记新的 1.20.1 LAN 加入者 case（建议预留 `V1201-090`，实际 id 先查未占用再冻结），初始 `mandatory:false`，输入含受审 1.20.1 recipe 与受控 world pin，断言至少覆盖“所拨世界的首快照”“加入者同代有界控制”“宿主服务端确认转向/水平位移”“释放后停止”。若一个断言缺当前 seal 可承载的字段，明确标 `BLOCKED_EVIDENCE`，先做只读设计/反证，不改 `minekin.p0.evidence.v1` 求绿。M 独占 `tools/assert_case_evidence.py`、`tools/check_case_assertions.py`、新 case fixture/manifest、对应 unit/contract 测试及一份卡记录；分成 case 设计冻结与注册两笔提交，每笔量 case_version 与门载荷前后差，不顺手翻旧 case mandatory/registry。缺字段的证据 schema 是另外的产品决定，不混进这张卡。

### E7 `V1201-LAN-JOINER-CONTROL-SEAL-001` — C1 有可判 case 且 V5 真绿后 E lane

E 独占规范卷写窗，使用新 Kin/attempt，在同一 1.20.1 LAN run 中重做 JOIN→首快照→限幅 look/move→release→停止；旧 E6、旧 CORE-030 与所有失败 attempt 不覆盖不改。只调用已登记且适用的 case，不改判据/fixture/registry。封存应有 joiner 自身 run document/trace、宿主世界运行文档与服务端 oracle、动作回执和停止载体；具体内容依 C1 冻结的断言。四读 `evidence verify` / 独立 `rejudge` / 适用 `replay` / `report_promotion`，连同一项材料级非空转反证、当前 build/case_version 与门载荷前后摘要一起交。若做不到，把真实 FAIL/UNJUDGED 留在卷上并指名缺字段或第一失败层，不冒称 PASS。

### M-G1 `V1201-LOCAL-CONTROL-GATE-AUDIT-001` — E7 后只读审计，不自动晋级

M 只读规范卷并重跑 `verify_tested_provenance.py`、case 报告及门报告，列出 1.20.1 registry 每条既有引用的当前 build/SEALED/复判状态、新 LAN 证据的范围、W40/W60/p0-core 的 required/mandatory/absent/blocks 差分。若旧 `V1201-020` 引用仍全绿，维持不替换；若有真实失败，独立登记引用修正卡并证明不会掩盖 FAIL。任何 `mandatory`/registry/capabilities/gaps 或 tested 晋级，必须有完整 required-case 策略、反例和独立提交，不能由本只读卡“顺手”改变。

## 3. 若某条线卡住，仍可推进的独立工作

H1h/V5/C1/E7 任一失败只阻断其依赖链，不把整个项目标成完成或 blocked。M 可在不共享文件、规范卷写窗和未冻结产品决策的前提下，另排 `DASHBOARD-GATEWAY-READONLY-CONTRACT-001`（只读接口/身份与脱敏设计，不接线上真实写接口），或把 B2 尚无 fixture 的非 HOST case 按“先设计 oracle/载体、后真跑”的顺序逐张排卡；两者不得伪造 `NEXT`，先写 owner/allowed_paths/验收并保持主干只有一个 integration `NEXT`。HOST/PERSIST、在线认证、跨 bundle 链 schema 和 V08 仍各守原决策门。

本地 LAN 控制封证不是用户远程服 demo。远程目标 V08 目前仍未获本轮新授权；没有它就不能声称 V09/V10 或完整 Minekin 完成，也不能以这条本地链代替远程服的 PLAYABLE/输入闭环。

## 4. 给 Qoder 的续跑文本

```text
/goal 你是 Minekin 的 M 集成主控。先按 docs/qoder-execution-handoff.md 恢复现场，核 main/工作树/规范卷写窗，再审查并合入 codex/minekin-local-control-next 的文档增量；与真实 main 冲突就停在具体差异，不覆盖活动 lane。读 docs/v1201-lan-control-next-2026-09-27.md：E6 的 V1201-020 seq4 是本地专服单客户端 sealed JOIN，不是 V4 的第二客户端 LAN 加入封证；registry 已有同构建 V1201-020 seq2 PASS，所以现在不替换引用、不翻 mandatory。维持唯一主干 current_next=PARALLEL-INTEGRATION-GATE-001，顺序派 H1h（受控 LAN 加入者显式限幅控制驱动）→V5（1.20.1 私有本地真实控制读数）→M-C1（冻结/登记能诚实判 LAN 加入者控制的 case）→E7（规范卷独占同 run 封证）→M-G1（只读门禁/registry 差分审计）；每张依赖满足才提升，逐卡本地/Docker 验证、双审、commit、push、核远端 SHA，失败按第一真实停点开独立窄卡，推进不依赖的只读 Gateway 或非 HOST case 设计，不因暂时无待合分支结束 goal。绝不连接用户远程服、不放宽认证/地址/lease、不删历史材料、不把单测或私有活体记录写成规范卷 PASS。按“已合主干／仅在分支／真实封证／未验证”四态报告；重大 HOST/PERSIST、跨 bundle schema、V08 授权仍留决策门。
```

## 派工状态（2026-09-27 第三十七轮，M 回写）

- **H1h 已派工**：工作树 `minekin-wt-h1h`，分支 `codex/minekin-lan-joiner-bounded-control`，base `24ac6e0`；卡在工、远端尚无该 ref，因此**仅在分支**一格目前为空。
- 派工面按本文 §2 原样收窄：只允许 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/` 记录；规范卷**不挂载**（H1h 不封证）。
- 派工前 M 亲量的新增事实：加入者的产品调用（`domain.sh:1179-1184`）只有 `--profile` 与 `--server-profile`，而 `session start` 已接受 `--hold-forward-seconds/--look-yaw-degrees/--look-pitch-degrees`（`parser.py:115/172/179`）且 hold 只 needs `--server-profile`；加入者启动时已注入 `MINEKIN_KIN_ID="${joiner}"`（`~:1166`）⇒ **lease 定向第二客户端不需要新产物 API**，本卡应为零 `src/**` 改动。若 lane 实际停在 lease 层，按 §2 的规定交 M 另立单独产品卡，不在本卡内越界实施。
- V5/M-C1/E7/M-G1 未派工；registry 引用不替换、`mandatory` 不翻转（本文 §0 的裁决仍生效）。

## §2.1 M-C1 的前置裁决（2026-09-27 第三十七轮，M 派工前实测后补）

M 在等 H1h 的窗口里把「有没有可判载体」量成了事实，结论改变了 M-C1 的形状：

1. **单 bundle 双载体不需要扩 schema**：封存入口本就有 `--server-directory` 与 `--world-run-document` 两个参数（`tools/seal_run_evidence.py:870` 与 `:876`，分别封成 `server/server.log` 与 `host-run-document.json`）。卷内 6 份 `CORE-030` 加入者 bundle 之所以只有后者、没有前者，是因为当时那次封存没传 `--server-directory`——**缺的是参数，不是实现**。⇒ E7 仍是「一个 bundle、同一次 run」封证，不触主控保留的跨 bundle 链上载体。
2. **但服务端位置读数是无名的，加入者的移动今天不能自证归属**。实测三件事：
   - `tools/run_controlled_server.py:489/507` 把探针发成 `data get entity <player> Pos|Rotation`，目标名只出现在**命令**里；
   - 卷内真 `server/server.log` 里只有答案行 `has the following entity data: [...]`，`data get entity <name>` 形式的命令行 **0 次出现**（抽样 CORE-060 ×3、CORE-020 ×1，答案行 0~6 条）；
   - 判据侧 `tools/assert_case_evidence.py:246,266-280` 的 `_PROBE`/`probe_readings` 与 `the_server_saw_the_kin_move`(`:1599`) 取的是**全日志所有答案行的首尾两次读数**，只按分量数区分位置/朝向，不按名字区分；
   - 卷内 100 份 `orchestrator-trace.json` 里**没有一份提到 probe** ⇒ 探针目标今天没有被封进任何产物。
   单客户端时这不成问题（一次 run 只问一个名字，且 `domain.sh:482` 的 `--probe-player "${probe:-${player}}"` 只有一个目标）；两客户端时，若两个名字都被问过，轨迹就会被错配。
3. **裁决（写死 M-C1 的边界）**：M-C1 的**第一份提交**必须先补「探针目标归属」这一格载体——把本次 run 被问过的玩家名记进**已有**封存产物 `asserter-inputs.json`（`seal_run_evidence.py:795` 的 `ASSERTER_INPUTS`），并在 case 判据里要求「被问过的名字恰为加入者用户名，且仅此一个」。这是 `tools/**` 面内的新增字段/新增 artifact 名，沿用既有名字常量纪律，**不是** `minekin.p0.evidence.v1` 的 schema 扩展。
4. **反证要求**：M-C1 必须现场演示——把同一份日志的归属换成主客户端名字、或塞进第二个被探针的名字，判据要**具名失败**（`the_server_saw_the_kin_move` 不得在归属不成立时仍返回 None）。做不到这一条，M-C1 不得登记 case，E7 不得排封证窗口。
5. **不因此改动现有 case 的判据**：既有单客户端案的「一个目标」前提不变，H1h/V5 之前也不依赖本节。

## §2.2 拆分：M-C0 载体卡 + H1i 交接卡（第三十七轮，M 裁决）

§2.1 的归属载体横跨两个面，而 M-C1 还排在 V5 之后。为不浪费时间又不越序，把它拆成两张各自独立可判的卡：

- **M-C0（先派，不依赖 H1h/V5）** `V1201-PROBE-TARGET-CARRIER-001`，只动 `tools/**`：
  - `tools/seal_run_evidence.py` 新增可选、可重复的 `--probed-player`，把它原样记进**已有**的封存产物 `asserter-inputs.json`（`:795` 的 `ASSERTER_INPUTS`），不新增 artifact 名、不动 `minekin.p0.evidence.v1`。
  - `tools/assert_case_evidence.py` 暴露该读数，并新增一个判定词：被问过的名字**恰为**本 run 的 `--username` 且仅此一个；缺失时**具名失败**而不是当作「没问过」。
  - 向后兼容要求：既有 case 的判定结果不得改变（用真 bundle 重判做正对照）；新字段缺省时不得让旧 bundle 重判转红。
- **H1i（排在 H1h 之后，同一文件不可并发）** `V1201-PROBE-TARGET-HANDOVER-001`，只动 `test-orchestrator/runner/domain.sh`：封存调用要把本 run 实际问过的名字（`domain.sh:482` 的 `${probe:-${player}}`）交给 `--probed-player`，且不得改动 auto+joiner 拒止段。
- **M-C1 的相应收窄**：M-C1 不再实现载体，只在 V5 证明活体可判后冻结/登记 case（两次提交，逐次量 `case_version` 与门载荷 delta）。E7 的封证窗口以 M-C0 + H1i 已合入为前置。

## §2.3 M-C0 的 parity 对照件与门载荷口径（第三十七轮，M 派工后亲量）

M-C0 的验收里「既有 case 的判定结果不得改变」这条不能靠 lane 自选 bundle，M 先把哪些是真对照件量清楚（脚本 `.tmp/m-r38-base-readings.sh`，容器 `/src:ro` + `/data:ro`，输出 `.tmp/m-r38-mc0-base-readings.log`）：

- **合法的改前改后对照（两份，改前逐字 `rc=0 / status agrees / PASS`）**：
  - `kin-01/61b4f0253cc84e2183d8913f3ad77867` = `OFFLINE-010`，`case_version 78053e9e…`；
  - `kin-01/87229052d24f4772a512dee497bab29c` = `V1201-020`，`case_version e7c3b722…`（与 E6 的 `73a52bfb…` 是不同 run，两枚都可用作正对照）。
- **不是对照件**：`kin-01/01ca65e397354f1489a3a299e8c44973`（`CORE-060`）改前就 `rc=2 status unjudged`——封于 `case_version 30ac59a0…` 而当前是 `d1ea32d8…`，判据已移动。若 lane 拿它当「改前绿」基线，读数本身就错。
- **M-C0 的改前门基线**（同一棵树 `77329dc`，不是引用旧记录）：`report_rc=1`、`status blocked`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']`、`promotable ['W00','W10','W20','W60']`、`attempts 77 / bundles 113 / from_another_build 61 / repo_checks_not_from_the_controlled_interpreter 9`、`visibility_gaps` 只有 `ORCHESTRATOR_REVISION_NOT_PINNED`；`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`。
- **口径（写死，避免 lane 自报不可比的数）**：`gate_payload_sha256` 不是 `tools/**` 打印的字段（全仓 grep `tools/ src/` 命中 0），而是 M 侧对 `report_promotion.py` 输出的 `{work_packages, overall}` 子集做 `json.dumps(..., sort_keys=True)` 后取 sha256（定义见 `.tmp/m-r12-payload.sh:8-12`）。报告顶层也没有 `promotable` 键（`tools/report_promotion.py:752-753` 只写 `gated`/`status`），那行 `promotable [...]` 是按各 work package 的 `promotable` 真值算出来的。M-C0/H1h 若自报门载荷，须以 M 的上述脚本口径为准。
- **M-C0 不移动门的理由已核**：它只新增可选封存字段与一个新判定词，不注册 case、不动 registry ⇒ 上述子集应逐字节不变；一旦 `cfa0f118…` 变了，就是它把判据挂进了既有 case，按 §2.2 的边界即不成立。

### 派工状态更新（本轮收口时的实读）
- H1h：`minekin-wt-h1h` @ base `24ac6e0`，**零提交**，未提交改动只在 `domain.sh` + `tests/contract/test_runner_scripts.py`（允许面内）。
- M-C0：`minekin-wt-mc0` @ base `5d0cd2a`，工作树干净、**零提交**。
- H1i 仍不派（与 H1h 同改 `domain.sh`）。远端 ref 复核要用全称 pattern：`git ls-remote origin refs/heads/codex/minekin-lan-joiner-bounded-control refs/heads/codex/minekin-probe-target-carrier`（畸形 pattern 得到的空输出不构成「未推送」证据）。

## §2.4 H1i 的精确形状：加入者 bundle 缺服务端日志是 `domain.sh` 的**有意丢弃**（本轮读源码量清，含对 §2.1 第 1 条的自我修正）

§2.1 第 1 条说「缺的是 `--server-directory` 参数，不是实现」。读了封存调用现场后要修正一半：**sealer 侧确实现成，但 `domain.sh` 的 joiner 分支是主动把它清掉的**，所以这一格不是「E7 补传参数」就能拿到，必须走 H1i 的 runner 改动。

实测字节（主干 `3d46686`）：
- `test-orchestrator/runner/domain.sh:2443-2444`：主持有形状把 `--server-profile` 与 `--server-directory "${server_directory}"` 一起放进 `world_args`。
- `:2472-2489`：`case_on=joiner` 时改成 `subject_document=/tmp/domain-join-session.json`、`subject_username="${join_username}"`、`world_run_args=(--world-run-document /tmp/domain-session.json)`，并且 **`world_args=()`**（`:2484-2487` 的注释给出理由：专用服务器 profile 是**另一种世界**，留着名字会让「宿主文档不可读」的加入 run 退化成记录一个从未跑过的世界，而不是被拒）。⇒ 这就是全卷「同时含 `server/server.log` 与 `host-run-document.json` 的 bundle = 0 份」的机制，不是遗漏。
- 关键副作用检查（决定 H1i 能不能只加一个参数）：
  - `tools/seal_run_evidence.py:255-258`：`server_directory` 一旦给出就封**三件**产物（`server.log`、`usercache.json`、`server.properties`）；
  - `:419-428`：加入者 bundle 的世界记录走 `world_run_document` 分支并**先返回** ⇒ 加 `--server-directory` **不会**改动 `world` 字段（`:434` 的 `world_seed` 分支在 joiner 形状上根本到不了）。这条先量清楚，否则 H1i 会被误判成「会改世界身份，因而不许做」；
  - `:529-531`：`server_observed_name_uuid` 从 `""` 变成按 `subject_username` 查宿主 `usercache.json` 的读数——而 `subject_username` 在 joiner 形状正是 `${join_username}`（`domain.sh:2482`、`:2590`）。⇒ 这一格加的不是噪声，是**服务端自己对加入者身份的记账**，与 §2.1 第 3 条要求的归属正好同向。

**M 对 H1i 卡面的裁决（默认关闭，别碰已登记案）**：
1. 只在**新的 opt-in** 下补传：给加入者封存分支加一个默认关闭的开关（旗标名由 H lane 定），置位时才把 `--server-directory "${server_directory}"` 加回 joiner 的 `world_args`。默认关闭 ⇒ 未来再跑的 `CORE-030` 加入者 bundle 形状逐字节不变，已封存 bundle 更不受影响（重判读的是 bundle 内字节）。
2. **绝不**因此把 `--server-profile` / `--server-jar` 带回来——`:2484-2487` 的拒止理由要原样成立；契约测试要盯住「opt-in 打开时 argv 里出现 `--server-directory` 且不出现 `--server-profile`」。
3. 探针目标（§2.2 M-C0 的 `--probed-player`）与这一格同批交给封存调用，来源都是 `domain.sh:482` 的 `${probe:-${player}}`；不得动 `:400-406` 的 auto+joiner 拒止。
4. H1i 的验收含一条反证：opt-in 关闭时 joiner 的封存 argv 与当前主干逐字相同（默认关闭等值的同一口径，H1h 已用 `.tmp/m-r37-h1h-argv-judge.py` 立过形状）。
5. 排程不变：H1i 等 H1h 与 M-C0 都合入后再派（同改 `domain.sh`，不并发）。V5 的活体读数**不依赖** H1i——H1i 只服务「同 run 封证」（E7）与 case 登记（M-C1）。

## §2.5 V5 的预登记验收判据（M 在 V lane 交付前写下，不事后发明）

V5 是活体读数，不是封证，也不是 case。M 先把**今天就存在的载体**逐条钉住（行号取自主干 `6af5a77`）：

1. **探针目标今天就能指向加入者，无需任何代码改动**：`domain.sh:27` 读 `MINEKIN_DOMAIN_PROBE`、`:165` 读 `MINEKIN_DOMAIN_PROBE_SECONDS`（默认 5），二者进 `:482` 的 `--probe-player "${probe:-${player}}"`。V5 的 run 必须显式把 `MINEKIN_DOMAIN_PROBE` 设为**加入者用户名**，否则默认探的是主持有者 `${player}`，日志里的位移读数就不是加入者的。⇒ V5 是单目标 run，§2.1 的归属歧义在活体读数上不成立，但**封进 bundle 后读不出被问过谁**——这正是 M-C0 存在的理由，两者别混。
2. **PLAYABLE 的载体是加入者自己的账本**：`/data/kin/<joiner>/kin.sqlite3` 里 `event_type='PlayableEstablished'` 且 `position > <baseline>`（`domain.sh:1211-1213`）。`arrived` 与 `playable` 是两条独立读数（`:1195` 的「the world heard … arrive」只证明服务端听到了 join 行），V5 记录必须分别报，不得把「听到了 arrival」写成「已可判 PLAYABLE」。
3. **位移的载体是服务端自己的答案行**：`${server_directory}/server.log` 里的 `has the following entity data: [...]`（判据侧的解析常量见 `assert_case_evidence.py:246`），V5 要按第 1 条的目标名读数并报**首末两次的具体坐标/朝向差**。
4. **释放（release）**：加入者 session 文档 `/tmp/domain-join-session.json` 与客户端流 `logs/latest.log` 是客户端侧的账；服务端侧只到 `<join_username> left the game`。V5 记录要说明 release 是从哪一侧读到的，不得用服务端离场行冒充 lease 释放。
5. **非恒真要求（两条都必须出现在 V5 记录里）**：
   - 同一 run 的**主持有者**读数首末不变（否则「加入者动了」与「整个世界在漂/重生噪声」分不开）；
   - 一次**关闭控制**的对照 run，加入者首末读数不变。
   做不到这两条，V5 只能是「看到数字变了」，不构成可判载体。
6. **边界**：V5 只写一份带日期的 `docs/validation/` 记录 + 私有数据根；**不挂规范卷、不封存、不注册 case、不动 registry 或 mandatory**；不得引用 E6 的 `V1201-020` seq4 作为 LAN 第二客户端的证据（§0 的裁决）。
7. **停止条件**：若控制已 arm 而 PLAYABLE 未到，第一真实失败层在「H1h 的 argv 是否真到达加入者客户端」，V5 就地停并报告，不得在 V 卡里顺手改 runner。

## §2.6 H1i 的验收判据已钉成可复算工具（M 侧 `.tmp/m-r39-h1i-seal-argv-judge.py`）

§2.4 第 4 条要求「opt-in 关闭时 joiner 的封存 argv 与当前主干逐字相同」，此前只是话。本轮把它写成与 H1h 判官同形状的一件工具（`report` / `compare --base --tip` / `mutate`），并在主干 `95b1b00`（`domain.sh ff69c879…`）标定，日志 `.tmp/m-r39-h1i-judge-calibration.log`：

1. **主干基线**：加入者封存区段（`subject_document=/tmp/domain-join-session.json` 起至该分支 `fi`，绝对首行 2481、共 9 行）sha `4270b51cba07e4da32b9dc979f531afa96026596548b2a059d651e8a04763dee`；封存调用区段（`python /src/tools/seal_run_evidence.py` 至 `--session-argv`）sha `7d83721fdf0138216da051cdd5653d6bb10bbfe29a56225394e7ade7f5c2b9a6`；`world_args=()` 在位；三个外部旗标 `--server-directory/--server-profile/--server-jar` 在加入者区段内出现 0 次；`faults: []`；四条不变量（auto+joiner 拒止、非 PLAYABLE 分支、账本 `PlayableEstablished`、`--world-run-document /tmp/domain-session.json`）全在。
2. **两条反例都被具名抓出**（`mutate`，写在工作树之外的临时文本上，不落 lane 树）：无条件把 `--server-directory` 交给加入者 ⇒ 「reaches the joiner seal unconditionally … the opt-in is not default-off」；opt-in 里顺手带上 `--server-profile` ⇒ 「is handed to the joiner seal (line 10), guarded or not」。⇒ H1i 只能加那一格，且必须在具名 env 的 guard 下。
3. **正对照 + 判官自测的修正（申报）**：第一次 `compare` 拿主干对 H1h 在飞树，判 `equal: false`——唯一差是 `joiner_region_abs_start_line` 2481→2719（H1h 在其上方加了 238 行），两段内容 sha 逐字相同。这是**我口径的缺陷**（行号不是字节），已改为「行号只报告、不参与相等判断」，重跑后：主干 vs H1h ⇒ `equal: true rc=0`；主干 vs 植入无条件 `--server-directory` 的临时树 ⇒ `equal: false rc=1` 并具名同一条 fault。⇒ 这条对照现在既能证明「H1h 没碰到封存配方」，也不会把任何合法加行误读成配方漂移。
4. **对排程的意义**：H1i 到货时 M 只需 `compare --base <merge-base 树> --tip <lane 树>`，要求两段 sha 只在 opt-in 打开的那一格不同，另跑一次「opt-in 名不存在 ⇒ 与主干逐字相同」。H1h 到货时的判据仍是 §2.3 的 `.tmp/m-r37-h1h-argv-judge.py` + `.tmp/m-r38-review-gates.sh`。本轮仍零封证、规范卷未被写（全程未挂 `/data`），registry 与 `mandatory` 未动。

## §2.7 M-G1 的「改前」半张差分已量下来（E7 之后再也取不到）

M-G1 卡面要求列出 registry 每条既有引用的当前 build/SEALED/复判状态，并做差分。差分有两半，**改前那一半只在 E7 写卷之前可取**，所以本轮（主干 `e458818`、规范卷全程 `:ro`）用 `.tmp/m-r41-mg1-census.py` 从 registry 本身枚举，不手挑 bundle：

1. **18 条引用全部仍是当前构建的可判证据**：`1.20.1` 6 条（`V1201-010/020/040/060/070/080`）+ `1.21.4` 12 条（`ADMIT-070`、`CORE-010/020/060/060-CLIENT-001/060-SERVER-001/090/100`、`OFFLINE-010/020/030-ENUM-ALIGNED-001/030-PRISM-PARITY-001`）。逐条读数：bundle 在卷、`sha256(manifest.json)` 与 registry 记录的 `bundle_digest` 相同、`rejudge=agrees`、`re_judged.result == cited result == PASS`、`disagreements=0`、`unimplemented=[]`，判据条数 2~5（`criteria` 列）。汇总 `cited=18 absent_bundles=0 digest_mismatch=0`。日志 `.tmp/m-r41-mg1-census-before.log`。
2. **溯源校验同向**：`tools/verify_tested_provenance.py --data-root /data` ⇒ `rc=0`、顶层 `verified: true`、`skipped_not_tested: []`、`registry_revision 35bdd1c043c188797060af0bc26b775541f78e597b6c819e279d22d8bc8eedad`。**注意跑法**：它要在持有两份桥 jar 的工作树里跑（本轮用 `../minekin-wt-v4`，其 `tests/fixtures/registry/reviewed-tested-bundles.json` 与主干 **sha256 逐字相同** `06cac798…`，所以引用集一致）；从 integration 树跑必报 `BRIDGE_JAR_MISSING`。日志 `.tmp/m-r41-provenance-before.log`。
3. **对 §0 裁决的意义**：「不替换 registry 同构建引用」此前是**规约**，现在有了证据——被引用的 `V1201-020` 那条（`ece5d0cb…`）在当前构建下仍 `agrees/PASS`，没有任何一条引用需要修正；因此 E7 之后 M-G1 的差分只需看**新增**那一行，不必重查旧行。
4. **复现命令**（Git Bash，`/src` 与 `/data` 全程只读）：
   ```text
   export MSYS_NO_PATHCONV=1
   docker run --rm --entrypoint /bin/bash -v "$(cygpath -m "$PWD"):/src:ro" \
     -v minekin-runner-data:/data:ro -e PYTHONPATH=/src/src -e MINEKIN_HOME=/data \
     -e LD_LIBRARY_PATH=/opt/sqlite/lib minekin-runner:local \
     -lc 'cd /src && python .tmp/m-r41-mg1-census.py'
   ```
   溯源那一条把 `-v` 换成 `$(cygpath -m ../minekin-wt-v4):/src:ro`、命令换成 `python tools/verify_tested_provenance.py --data-root /data`。
5. **口径提示（M 自记）**：`rejudge_evidence.py` 的判定载荷在 `re_judged` 下（`expected/failures/observed/result/unimplemented`），顶层 `status` 只说「与自身记录是否一致」。只读 `status=agrees` 而不读 `re_judged.result`，会把「一致地 FAIL」也念成绿——census 因此两样都印。

## §2.8 H1h 已合主干（第三十八轮，M 从真实 merge-base 复审后合入并推远端）

- **合入**：`58856453510c24d63790545d38f6ea37d3981d68`（`705e58a..5885645`，远端 `refs/heads/main` 已用 `git ls-remote` 核到同一 SHA）。并入的两笔：`e941f96`（`domain.sh` +244 / `tests/contract/test_runner_scripts.py` +734）、`99a18ef`（一份 `docs/validation/v1201-lan-joiner-bounded-control-driver-2026-09-27.md`）。真实 merge-base = `24ac6e0`，允许面逐字未越界：`src/**`、`tools/**`、case fixture、registry、`test-orchestrator/runner/run.sh`、`config.FORWARDED_VARIABLES` 在 `git diff --stat 24ac6e0 99a18ef` 里均为 0 行。
- **M 亲量（不是复述 lane）**：容器内六道门全绿（bash -n / 契约 64 passed / asserter 单元 487 passed / 150 registered / digests OK / boundaries OK），`/src:ro` + `/data:ro`，日志 `.tmp/m-r42-h1h-gates.log`；改前即 PASS 的两份对照件（`OFFLINE-010/61b4f025`、`V1201-020/87229052`）在新字节下仍 `agrees/PASS`；**门载荷逐字不变**：`gate_payload_sha256 cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、`promotable W00/W10/W20/W60`、`overall_blocks REQUIRED_CASE_NOT_REGISTERED`——本卡不注册 case，因此也不得动门。
- **H1i 那一格没被顺手改**：`.tmp/m-r39-h1i-seal-argv-judge.py compare --base <24ac6e0> --tip <99a18ef>` ⇒ `equal:true`（加入者封存区间 sha `4270b51c…`、seal argv 区间 sha `7d83721f…` 双向相同）。同一工具在容器里跑不通（`Path.read_text(newline=)` 要 python≥3.13，镜像是 3.12），已换成 `read_bytes().decode()` 并在两份字节上复量；此前那份校准是 M 在宿主 python 3.13 上量的——**工具对解释器版本敏感**这一点记在这里，别再当成 lane 的差异。
- **判官口径修正申报（第二次，同一类）**：`.tmp/m-r37-h1h-argv-judge.py` v1 把加入者区间锚在字面量 `python -m minekin_core session start` 上，本卡合法地把该字面量搬进 `build_joiner_session_argv()`，v1 于是在合入瞬间**失明**（报 `the joiner region has no ending redirection`）。v2 改锚在 `minekin-joiner-launch` 标记上，并把断言从「这一块字节不变」换成形状断言：控制旗标不得落在加入者启动行、旗标旁不得出现字面数字、三个上界不得宽于 45/30/2、数组只许在加入者区块内展开一次。v2 在基线字节与本卡字节上双双 `faults=[]`，六个植入反例（行内字面量、两个方向的越界上界、双 splice、splice 到别处、组线函数内硬编码数字）全部具名抓出；日志 `.tmp/m-r42-h1h-judges.log`。**教训**：判官若锚在“实现写法”上而不是“契约形状”上，它就会在被审卡片落地的同一刻静默失效——写判官时优先选不会被卡片合法重命名的标记。

## §2.9 第一真实停点：`run.sh` 不转发四个新名字 ⇒ 独立窄卡 H1j（不扩 H1h 面）

H1h 交付时把这条摆明：`test-orchestrator/runner/run.sh:88-110` 的转发名单里没有 `MINEKIN_DOMAIN_JOIN_LOOK_YAW / _LOOK_PITCH / _HOLD_FORWARD_SECONDS / _CONTROL_PRINT`，因此**经 `run.sh` 的真跑目前无法武装该驱动**；lane 还把它钉成契约里的精确集合（`JOINER_CONTROL_KNOBS`），使「第四名出现在 `run.sh`」这件事当前是**被测试要求为假**的。M 裁决：不在 H1h 里回补，另开一张窄卡，因为它改的是另一个文件、且必须**故意推翻**一条刚合入的契约断言——这种事要在自己的提交信息里发生，不能藏进上一张卡的尾巴。

### H1j `V1201-JOINER-CONTROL-RUNSH-FORWARDING-001` — H lane，紧跟 H1h

- **允许面**：`test-orchestrator/runner/run.sh`、`tests/contract/test_runner_scripts.py`、一份新的 `docs/validation/v1201-joiner-control-runsh-forwarding-<date>.md`。**禁**：`domain.sh`（H1h 已定形）、`src/**`（含 `config.FORWARDED_VARIABLES`——那是产品转发名单，把 runner 的名字加进去就是放宽产品入口）、`tools/**`、case fixture、registry、规范卷（**不挂载**）。
- **实现边界**：只把四个既有名字加进 `run.sh` 的容器环境转发名单，语义为「宿主设了才带进去，没设就不带」；不得新增第五个名字、不得给任何名字加默认值、不得改 `domain.sh` 的限幅或拒止、不得改加入者/宿主两条命令行的构造。
- **红绿验收（四条，全部要字面输出）**：
  1. 四个名字一个都没设时，`run.sh` 组出的容器 argv 与基线逐字相同（把 argv 打印出来比对，不许只说“应该一样”）；
  2. 只设其中一个时，它出现在 argv 且其余不出现；
  3. 契约里那条精确集合断言被**有意翻转**：`JOINER_CONTROL_KNOBS` 的四名必须真出现在 `run.sh` 里、且仍不得出现在 `src/minekin_core/config.py`；出现第五个未转发的 `MINEKIN_DOMAIN_JOIN_*` 控制名仍要变红。翻转那一条测试是本卡唯一被允许改写的既有断言，必须在提交信息里点名；
  4. 反证：把名单改成无条件 `-e NAME=`（不带值判断）→ 验收 1 变红；把名单加到第五个名字 → 验收 3 变红。
- **门载荷上界**：H1j 不注册 case ⇒ `gate_payload_sha256` 必须仍是 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`。若它变了，说明本卡越界动了 registry/fixture，直接退回。
- **依赖关系**：H1j 不阻塞 V5——V5 走「容器内直接 `domain.sh` + 显式 `-e`」即可取活体读数；H1j 只补操作者路径（经 `run.sh` 的战役）与 E7 之后的可复现性。V5 的预登记判据仍按 §2.5，且**等 V5a 的探针目标归属读数**落地后才起。

## §2.10 M 的 census 判官自身的非恒真控制（第三十八轮补）

`.tmp/m-r41-mg1-census.py` 报「18/18 `agrees/PASS`」，一个恒真的读法同样能报出这句话，所以补了一次扰动实验（`.tmp/m-r41-census-negcontrol.sh`，全部写在容器 `/tmp`，`/src` 与 `/data` 只读）：

- **正对照**：把 `tools` + `tests/fixtures/{cases,registry}` 原样拷进 `/tmp/fs` 再跑 ⇒ `OFFLINE-010 run=61b4f025 digest_matches=True rejudge=agrees result=PASS criteria=4`，`census: cited=18 absent_bundles=0 digest_mismatch=0`。即“拷贝”这一步本身不动读数。
- **反对照**：只往 `offline-010.json` 的 `assertions` 里塞一个多余能力（`the_server_saw_the_kin_turn`）⇒ 该行翻成 `rejudge=unreadable rc=2`，诊断行写着 `… — the criteria moved, so the recorded verdict answers a question this repository no longer asks`，而 `OFFLINE-020`、`OFFLINE-030-ENUM-ALIGNED-001` 两行仍 `agrees/PASS`。**结论**：census 的绿是测量，不是常量；它按 case 逐行敏感，且不会把一次改动抹匀到 18 行。
- **已知读法缺陷（记着，M-G1 后半要用）**：`rejudge_evidence.py` 在 case_version 不符时把诊断 JSON 打到 **stderr**、stdout 为空，于是 census 只能报 `unreadable`。判读要点在于翻绿的证据仍在 note 里；若 E7 之后要精确区分「未判」与「读不出」，得让 census 在 stdout 为空时回读 stderr（M 侧工具，不占 lane 面）。

## §2.11 H1j 已合主干（第三十九轮，M 从真实 merge-base 复审后合入并推远端）

- 审查从 merge-base `dcd914a` 起算。真实增量只有三个允许面文件：`test-orchestrator/runner/run.sh` +12/-1、`tests/contract/test_runner_scripts.py` +55/-20、新 `docs/validation/v1201-joiner-control-runsh-forwarding-2026-09-27.md`。`domain.sh`、`src/**`（含 `config.FORWARDED_VARIABLES`）、`tools/**`、fixtures、registry 全为 0 行 ⇒ 与主干这两笔类型/格式修复无重叠，自动合并干净。合入提交 `bcdaf17`，远端 `main` 已核为该 SHA。
- M 在**合并后的树**上亲量（容器内 `/src` 与规范卷都挂 `:ro`）：`bash -n` 过、契约 64 passed、断言器单测 487 passed、`check_case_assertions` 150 registered、`verify_fixture_digests` OK、`check_boundaries` OK；两份对照 bundle 仍 `rc=0 / agrees / PASS`（OFFLINE-010 `78053e9e…`、V1201-020 `e7c3b722…`）；`gate_payload_sha256` 逐字节仍是 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，`overall_blocks` 仍只有 `REQUIRED_CASE_NOT_REGISTERED`；`domain.sh` 字节仍为 `baad190aaa5ee1695a88b52e98cc270c8e1a4bc878a0bcd2d0c27f94b74ff6f3`（本卡未动）。
- **M 自己的反证**（`.tmp/m-r44-h1j-reversal.sh`，一次性副本跑在容器 `/tmp`，日志 `.tmp/m-r44-h1j-reversal.log`）：正对照（未改动的副本）`1 passed`；把转发名从 `run.sh` 删掉 ⇒ `AssertionError: … run.sh stopped delivering them: ['MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS', '…LOOK_PITCH', '…LOOK_YAW']`；只往 `domain.sh` 加第五个「读了而未转发」的名 ⇒ 同一检查在 `read - delivered` 上 FAIL。两条方向都抓得住，说明这条断言不是恒绿。**申报一处口径**：脚本按整行匹配只删到 4 名中的 3 名，因为 `MINEKIN_DOMAIN_JOIN_CONTROL_PRINT` 与数组的闭合 `)` 同行；这不影响该判据被抓住，但「删光四名」今天没有实量。
- **CI 侧的收尾（与本卡平行，但是主干自己的账）**：`python` 作业在 `d19714f` 仍红，日志（job `108582287753`，356 行）里真实失败步是 `Run uv run pyright` —— 98 个错误全在 `tests/contract/test_runner_scripts.py:1793-2417`，即 H1h 新增区。根因两处 `subprocess.CompletedUnicode[str]`：该名字在 typeshed 里不存在（仓库其余 10 处一律 `subprocess.CompletedProcess[str]`），未知类型沿 helper 传播刷成 98 条；另有一处 `ids=lambda value: …` 把 `Any` 收窄成 `dict[Unknown, Unknown]`。`4ad3db2` 修完后 CI `python=success`（protocol/bridge-static 亦 success），恒不等对照：把 HEAD 版本另存为临时模块单独 `--collect-only`，7 条参数化 id 逐字节相同。
- **流程缺口已钉进工具**：`.tmp/m-r43-host-gates.sh` 现在按 CI 的 `python` 作业原样跑三步（`ruff check` / `ruff format --check` / `pyright`）并把 pyright 行纳入 CI 抽取。此前 M 只跑 `ruff check`，连漏两次（format 与 pyright）都出自主干侧闸门不全，而非 lane 单方失守。

## §2.12 对 §2.1 第 2 条的自我修正：服务端读数**不是**无名的（第三十九轮，M 在规范卷上复量后改判）

V5a（`codex/minekin-v5-probe-target-preflight` @ `7f67aac`，交付物只有一份 `docs/validation/v5-probe-target-preflight-2026-09-27.md`）交回一条与 §2.1 相反的读数。M 没有采信报告，而是在**规范卷自己的封存字节**上复量（容器只读挂 `/data`，脚本内联于本轮记录）：

- 卷内带 `server/server.log` 的 bundle 共 **78** 份，探针回答行共 **460** 条，形如 `[00:20:31] [Server thread/INFO]: Kin has the following entity data: [-5.5d, -60.0d, 4.5d]` —— **460/460 行内带被问名，裸形 0 条**。V5a 在私有活体材料上给的形状（c2 的 6 条按名回答、d/e 的 0 条回答 + `No entity was found`）与卷内形状一致。
- 于是 §2.1 第 2 条「服务端位置读数是无名的」**只在“`data get entity <name>` 命令行不被回声”这个意义上成立**；回答行本身自带名字。而判官侧 `_PROBE`（`tools/assert_case_evidence.py:246`）是子串匹配，名字前缀并不妨碍它命中——它命中之后**把名字丢掉了**。这才是今天真正缺的东西，且缺在一个可以就地解析的位置。
- **改判（写死 M-C1 的口径）**：M-C1 的归属判据应当**直接从 `server/server.log` 的行内名解析**（「被问过、且答案归属加入者用户名的读数 ≥2 条且首末不同」），不需要扩 `minekin.p0.evidence.v1`——该 schema 扩展仍是主控保留项，且今天被证明不必要。M-C0 的 `probed_players` 申报件不作废、但降级为**交叉判据**：`No entity was found` 行不带名，「本次 run 究竟问过谁」只有宿主申报件能回答；所以 M-C1 要同时要求「申报集合恰为 {加入者用户名}」与「行内名归属成立」，两者缺一即具名失败。
- 这条改判不动任何既有 case 的判据，也不回头改 M-C0 的字节：M-C0 加的确实是加法（见 §2.14 的 census 差分）。

## §2.13 第一真实停点：两种 run 形状互斥 ⇒ 新窄卡 H1k，V5/M-C1/E7 全部顺移（第三十九轮，M 裁决）

- 主干字节上的形状事实（M 本轮逐行复核 `domain.sh`）：能回答 `data get entity` 的只有 `run_controlled_server.py`，它在 `:812` 起、且**只在 `--server-profile` 形状里被启动**；等待链是 `elif` 结构——`:1800` 起 `elif [ -n "${open_lan}" ]` 的分支等的是宿主**客户端** `latest.log` 里的 `Started serving on ${lan_port}`（`:1813`），随后 `join_the_published_world "${latest}"`（`:1823`）把加入者送进的是宿主客户端发布的 LAN 世界。也就是说 LAN 加入者形状里根本没有服务端日志可封（V5a 的 a4/b 实测 `server.log ABSENT`、回答行 0 条），而专服形状里加入者分支不被调用（V5a 的 e 形实测门 120s 永不打开）。
- **结论**：§2.5 给 V5 预登记的验收（第二客户端 PLAYABLE → 服务端具名 look/move → release）在主干字节下**不可执行**。这不是 H1h/H1j 的缺陷，也不是判据过严——是载体不存在。按「前置不满足就按第一真实失败层开窄卡」的规矩，V5 从这里改挂 H1k，M-C1 与 E7 顺移；本轮不替换 registry 引用、不翻 mandatory，也不把 V5 写成「H1h 合入后自然会绿」。
- 另记一条环境约束（V5a 申报、M 侧同型复算过）：Core 桥握手 30s 预算（`session.py:173`，无 CLI 旋钮）与并发 pytest 争用会烧掉整次活体 run。**V5/H1k 的活体窗口须预约静默**，同窗口不跑容器全量单测。

### H1k `V1201-LAN-JOINER-ON-CONTROLLED-SERVER-001` — H lane，紧跟本卡面
- **要解决的那一格**：给「有 `--server-profile` 且要有加入者」的 run 一条**默认关闭、显式选择**的路径，把第二客户端送进那个受控专服的世界（专服已经在答探针、日志已在 `${server_directory}/server.log`），而不是只能送进宿主客户端发布的 LAN 世界。今天这条路径不存在，所以「服务端看见加入者移动」在双客户端形状里无从谈起。
- **允许面只有三样**：`test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、一份新 `docs/validation/v1201-joiner-on-controlled-server-<date>.md`。**规范卷不挂载**（本卡不封证）；`src/**`（含 `config.FORWARDED_VARIABLES`）、`tools/**`、fixtures、registry、schema 一律 0 行。
- **形状要求**：新 `MINEKIN_DOMAIN_JOIN_*` 名字由 lane 自取并在记录里申报；它必须同时接进 `run.sh` 的转发名单（H1j 的四向名单是现成形状）——若 lane 判断这一步会扩到 `run.sh`，**停下来交 M 另立窄卡**，不要在本卡内越界实施。加入者的目标地址与端口只能读自**本次 run 自己的** `${server_directory}/server.properties`；就绪等待只能落在本 run 的服务端日志上。宿主客户端是否同进该世界，由 lane 在记录里明确申报它选了哪一种，并说明该选择对「两个名字都被问过」这一反证是否可用。
- **硬边界（逐条要字节证据）**：绝不连接用户远程服，绝不硬编码或 widening 地址/认证/白名单/lease；`--allow-player` 的语义不变；`domain.sh` 的 auto+joiner 拒止条款与 H1h 驱动区字节不动（`baad190aaa5ee…` 之外只允许新增）；未设新名时既有三种形状的组出的 argv / 等待目标逐字不变（要 base↔tip 对照，不许只说"应该一样"）。
- **验收读数（四条 + 两则反证）**：① 默认关闭等值的字节级对照；② 设了新名后加入者 argv 里目标确实来自本次 `server_directory`（打印来源行）；③ 专服日志里出现按加入者名的回答行（≥2 条、首末不同）；④ 契约里对三种形状的等待链各有一条形状断言，且 `check_case_assertions`/`verify_fixture_digests`/`check_boundaries` 全绿。反证两则：把端口写死成常量 → ②变红；把新名当默认开 → ①变红。
- **门载荷上界**：H1k 不注册 case ⇒ `gate_payload_sha256` 必须仍是 `cfa0f118…`；变了就是越界，直接退回。
- **交回前必跑（第三张卡漏了这一步，写死）**：`uv run ruff check .`、`uv run ruff format --check .`（**markdown 记录里的 python 代码块也算**）、`uv run pyright`（注解里不许出现 typeshed 没有的名字，`subprocess.CompletedUnicode` 就是上一张卡的教训），以及容器内 `python -m pytest -q tests/contract/test_runner_scripts.py`。
- **四态口径**：H1k 的交付物最多算**仅在分支**；在它合入并有活体读数之前，V5 不得登记为 PASS，M-C1 不得登记 case，E7 不得排封证窗口。

## §2.14 M-C0 已合主干（第三十九轮，census 差分为「改前」半张留档）

- merge-base `5d0cd2a`，surface = `tools/assert_case_evidence.py` +118、`tools/seal_run_evidence.py` +25、新 `tests/unit/test_probe_target_carrier.py`（313 行 / 10 个用例）、新 `docs/validation/v1201-probe-target-carrier-2026-09-27.md`。没有注册 case、没有动 fixtures/registry、没有动 `minekin.p0.evidence.v1`。
- **决定性差分（M-G1 的「改前」半张，E7 之后再取不到）**：同一份规范卷、registry 的 18 条 `tested` 引用，在主干树与 M-C0 树上分别跑 `.tmp/m-r41-mg1-census.py`，两份日志 `diff` 为空——`census: cited=18 absent_bundles=0 digest_mismatch=0`，每行 `rejudge=agrees result=<cited>` 一致（`--src` 换成 mc0 树即证「载体是加法，不动任何既有判据的读数」）。
- 合并树上门禁同 §2.11 那一份清单（契约 64、断言器 487、carrier 10、150 registered、digests/boundaries OK、两份 bundle agrees/PASS、门载荷 `cfa0f118…`、`domain.sh` 字节不变）。
- **主干侧修了一处 M 自己合入前该抓到的东西**：M-C0 那份 `docs/validation/` 记录内嵌的 python 代码块不合 `ruff format`（本仓 `format` 会检查 markdown 里的 python 块），合并树上表现为 `1 file would be reformatted`。M 已按 format 的建议改写该代码块（前后字节差只有那 5 行重排），并把「markdown 代码块也算」写进 H1k 卡面。至此**连续三张**卡（H1h、M-C0、H1j 自报未修）在同一个闸门上失守，根因是派工文本此前没有逐字列全 CI 的 `python` 作业三步——从 H1k 起列全。

- **落地时序（第四十轮补，写清楚以防读数被误读成事后追认）**：本节 §2.11–§2.14 的 plan 回写在上一轮就已写进工作树，而 M-C0 的合并当时**只进了索引、没有提交**——`main` 与 `origin/main` 仍停在 `bcdaf17`（只含 H1j）。本轮恢复现场时按字节查出这一格（`git ls-tree HEAD` 里既无 `tests/unit/test_probe_target_carrier.py` 也无那份 `docs/validation/` 记录），随后在提交前把主干侧闸门重跑了一遍（`ruff check` 通过、`ruff format --check` 364 files already formatted、`pyright` 0 errors、boundaries / `150 registered` / digests / workflow-pins 全 OK），M-C0 合并以 `97dc0ef` 真正入干。合并树容器读数（门载荷、两份 bundle、census 差分、domain.sh 字节）来自上一轮亲跑的 `.tmp/m-r44-mc0-gates.log` 与 `.tmp/m-r44-census-{main,mc0}.log`，两份 census 日志本轮 `diff` 复确为空。也就是说：**§2.14 的“已合主干”在写作为时点上是提前了半轮，在本节补写之后才是事实**；这类“文档先于提交”的格子以后按同一方式当场纠正。

## §2.15 第四十轮落地：M-C0 与 V5a 入干、H1k 开工（M 的 integration gate 读数）

- **恢复现场抓到的不实陈述（本轮第一个动作）**：§2.14 写作时 M-C0 的合并只进了索引、没有提交，`main`/`origin/main` 仍停在 `bcdaf17`。按字节证据确认（`git ls-tree -r HEAD` 里查不到 `tests/unit/test_probe_target_carrier.py` 与那份 `docs/validation/v1201-probe-target-carrier-2026-09-27.md`，而两文件在工作树里；`.git/MERGE_HEAD` 仍在，指向 `1e42ea6`）后，先重跑主干侧闸门再把合并落成真 SHA。这类“文档先于提交”已写进 §2.14 末尾的时序申报。
- **已合主干**（远端 `main` 逐笔 `git ls-remote` 核过）：
  - `97dc0ef` = M-C0 合并（四文件：`tools/assert_case_evidence.py` +118、`tools/seal_run_evidence.py` +25、新 carrier 单测 313 行 / 10 用例、新验证记录）。容器侧六项门禁 + 门载荷 `cfa0f118…` 未动 + 两份对照 bundle 仍 `agrees/PASS` + `domain.sh` 仍 `baad190aaa5ee…` + census 差分 `diff` 为空，全部沿用 `29c5187` 提交信息里逐条列出的亲跑读数。
  - `29c5187` = plan §2.11–§2.14 回写（纯文档）。**CI 三门对 `29c5187` 全绿**：`protocol=success`、`python=success`、`bridge-static=success`（REST `check-runs` 读数）。
  - `4640983` = V5a 合并（只一个新文件 `docs/validation/v5-probe-target-preflight-2026-09-27.md`，145 行含 M 的两处现在时修正）。**M 修的两处**：`domain.sh` 的 `ff69c879…` 收窄为「等于本卡 base `8dfeac6`」而非「等于主干」（入干时主干已是 `baad190…`，宿主 `sha256sum` 与容器读数一致，`run.sh` = `70349060…`）；§4「主干没有任何加入者控制驱动」收窄为「本卡测量时的 base 字节没有」。历史读数与逐字材料一律不追改。合并树 `ruff check` 通过、`ruff format --check` 365 files already formatted、`git diff --check` 干净；`4640983` 的 CI `python` 作业截至本节写作仍 `in_progress`。
- **仅在分支**：`codex/minekin-v1201-joiner-on-controlled-server`（H1k，worktree `minekin-wt-h1k`，起点 `29c5187`）。已按 §2.13 卡面派工，约束逐条写进派工文本：三个允许面文件、**不挂规范卷**（活体 run 只能用私有数据根）、新名默认关闭、目标地址/端口只读自本次 run 自己的 `server_directory/server.properties`、就绪等待只落在本 run 的服务端日志、`run.sh` 若需扩面即停手交回、门载荷必须仍是 `cfa0f118…`、四条验收 + 两则反证要字面输出、交回前必跑 `ruff check` / `ruff format --check`（含 markdown 代码块）/ `pyright` / `bash -n` / 容器内契约测试。
- **真实封证**：本轮**零新增**。LAN 第二客户端控制封证仍为 **0**；E6 的 `V1201-020 seq4` 仍是本地专服单客户端封证，不冒充 V4/V5 那一格。
- **未验证 / 顺移**：V5 活体读数、M-C1 的 case 冻结与登记、E7 的同 run 封证全部仍挂在 H1k 之后（§2.13）。M-G1 的「改后」census 与门载荷复量本可在 `4640983` 上做，但**故意压后**：H1k 的活体窗口需要静默（Core 桥 30s 握手预算 + 并发争用已烧掉 V5a 三次尝试，见 §2.13 末与 V5a §0），M 不再往同一窗口里塞容器读数。H1k 交回后、或活体窗口关闭后，M 立刻取这一份「改后」读数并把 §2.14 的差分补成完整一对。
- **下一格可安全推进的**：等 H1k 的交回（含它自取的新名与「宿主是否同进专服世界」的申报）；其间不排任何要独占卷或活体窗口的卡。

## §2.16 H1k 之后各卡的判据预登记（第四十一轮，M 在活体读数存在之前写下）

本节的全部判据在 H1k 交付、V5′ 真跑、M-C1 登记、E7 封证**之前**写定。之后任何一条若要改口径，必须另起一节具名申报「改了哪条、为什么、旧口径下哪些读数作废」，不得静默替换——§2.5 的第 1 条刚被 V5a 活体证否，就是这条规矩的来由。

### 排程裁决：H1i 仍排在 H1k 之后，不合并施工

H1i（§2.4：默认关闭地把宿主 LAN 日志与探针目标交给加入者的**封存**调用）与 H1k 改的是同一个文件 `test-orchestrator/runner/domain.sh`，且都在加入者区段附近动笔。按并行协议「同一文件仅一名 owner」，两张卡不得同时在飞；顺序为 **H1k → H1i**：H1k 决定加入者进哪个世界、读哪份服务端日志，H1i 才知道要把哪条路径交给 `seal_run_evidence.py`。§2.6 那件判官工具（`compare --base --tip`，两段 sha、行号只报告不参与相等判断）届时直接复用，且 H1i 的反证仍是「无条件把 `--server-directory` 递给加入者 ⇒ 具名 fault」。

### V5′（H1k 落地后的活体量测）判据

1. **载体行号不许沿用 §2.5**：H1k 入干后由 M 当场重读 `domain.sh`，把「加入者目标地址/端口来源行」「就绪等待落点行」「`--probe-player` 生效行」三处行号写进 V5′ 的派工文本；派工前量不到就不派（旧行号已在 §2.13 里失效过一次）。
2. **首末差必须按加入者的名字读**：`${server_directory}/server.log` 里 `has the following entity data:` 的**行内名**须等于加入者用户名，≥2 条，且首末**至少一个分量不同**（Pos 三元组或 Rotation 二元组）。仅「计数增加」不算。
3. **PLAYABLE 与 arrival 分别取证**（沿用 §2.5 第 2 条，载体不变）：加入者账本 `PlayableEstablished` 且 `position > baseline`；`the world heard … arrive` 只算服务端听到 join 行，不得写成「已可判 PLAYABLE」。
4. **两条非恒真对照，缺一即 V5′ 判不成立**：
   - 同一 run 内**主持有者**（或专服世界里另一具名实体）的读数首末**不变**——否则「加入者动了」与「整个世界在漂/加载噪声」分不开；
   - 一次**控制关闭**的同形状对照 run，加入者首末读数**不变**——这是 H1h 驱动真的在动、而不是探针节奏自己在动的唯一分界。
5. **目标归属的反证**：H1k 若申报「宿主不同进该专服世界」，则「两个名字都被问过」这条反证在该形状下不可用，V5′ 必须改用一个显式设 `MINEKIN_DOMAIN_PROBE=<世界里不存在的名>` 的具名失败格（V5a 的 run d 已证该形状产出 `No entity was found` 而非答案行），并在记录里说明这一替代。
6. **release 一侧**（沿用 §2.5 第 4 条）：客户端侧 `/tmp/domain-join-session.json` + `logs/latest.log` 为账；服务端侧只到 `<join_username> left the game`。不得用服务端离场行冒充 lease 释放。
7. **边界与停止条件**：V5′ 只写一份带日期的 `docs/validation/` 记录 + 私有数据根；不挂规范卷、不封存、不注册 case、不动 registry/`mandatory`；控制已 arm 而 PLAYABLE 未到 ⇒ 第一真实失败层是「H1h 的 argv 是否真到达加入者客户端」，就地停并报告，不在 V 卡里改 runner。活体窗口须预约静默（§2.13 末的 30s 握手预算）。

### M-C1（登记 `V1201-LAN-JOINER-CONTROL-CASE-001`）判据与面

- **判据冻结（§2.12 的改判口径，双条缺一不可）**：① 从 `server/server.log` 解析**行内名**归属，「被问过且归属加入者用户名的读数 ≥2 条、首末不同」；② `asserter-inputs.json` 的申报集合（M-C0 载体）恰为 `{加入者用户名}`。V5a 已证失败行 `No entity was found` 不带名 ⇒ 「本次究竟问过谁」只有申报件能答，所以两条并列，任一缺即具名失败。
- **允许面**：`tools/assert_case_evidence.py`、`tools/check_case_assertions.py` 的 `IMPLEMENTATIONS`、新 `tests/fixtures/cases/*.json` + `tests/fixtures/manifest.sha256` 行、`tests/unit/test_case_evidence_assertions.py`。由 **M 独占实施**（判官与登记同面，不派 lane）。
- **入册必动门载荷 ⇒ 先量后量各一次**：登记前取 `gate_payload_sha256`（今天 `cfa0f118…`）与 `W30.absent/non_mandatory`、`p0-core.absent` 逐项，登记后再取一次，逐格报差异；新 case 以 `mandatory: false` 入册，**不翻 mandatory、不晋级任何门**；`--record` 只允许移动新 case 那一个文件的摘要，否则即为重封全卷事故，立即退回。
- **反证要有**：把归属名换成主持有者 ⇒ 判据具名失败；把申报集合换成含第二个人 ⇒ 具名失败；首末读数改成相同 ⇒ 具名失败。三条都在单测面上，不靠卷。

### E7（同 run 封证）窗口条件

只有 V5′ 的 §2.16 第 2/4 条**全部成立**、且 M-C1 的 case 已在册，才开 E7 的规范卷独占写窗。E7 必须是**同一 run 的字节**同时供给控制侧与读数侧，不得用两次 run 拼；封成的 bundle 过 `rejudge_evidence.py` 要 `agrees`；E6 的 `V1201-020` seq4 是本地专服单客户端封证，**不得**被引用或复制成本卡那一格。

### M-G1 的「改后」半张（本轮故意压后的那一份）

H1k 在飞活体窗口期间 M 不往同一窗口塞容器读数（V5a 的三次 `HANDSHAKE_TIMEOUT` 是实测代价）。窗口关闭后立刻在合并树取：census 全行（与 §2.14 的「改前」配成一对）、门载荷、`report_promotion` 的 `promotable/blocks` 逐项、两份对照 bundle 的 `agrees/PASS`。

## §2.17 H1k 的静态复审发现：拒止集合漏了 `MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT` 这一组合（第四十二轮，M 在活体读数存在之前读 lane 的未提交字节得到）

- **测量对象**：`../minekin-wt-h1k` 的**未提交**工作树字节（`test-orchestrator/runner/domain.sh` sha256 `d9a0acfc…`、`tests/contract/test_runner_scripts.py` `7fe48b9d…`，与 `.tmp/m-r41-h1k-wip-hashes.txt` 逐字节相同）。本节只读 lane 字节与主干字节，不碰容器、不读规范卷；写下它是在任何活体读数之前，所以不构成对已交读数的追认。
- **形状事实（逐行读得）**：新名在 `:167` cast、`:173` 具名拒坏值；`--- joiner-controlled-server-guard ---` 区间是 `:461–:488`，六条具名拒止分别在 `:464`（无 joiner）、`:468`（无 `--server-profile`）、`:472`（与 `MINEKIN_DOMAIN_OPEN_LAN` 冲突）、`:476`（黑洞）、`:480`（`MINEKIN_DOMAIN_NO_SERVER`）、`:484`（`MINEKIN_DOMAIN_NOT_WHITELISTED`）。等待链的次序是 `:1839 elif [ "${refusal_asked}" -eq 1 ]` ⇒ `:1936 elif [ -n "${open_lan}" ]` ⇒ `:1968 elif [ "${join_on_controlled_server_asked}" -eq 1 ]`（区间 `:1969–:1988`）⇒ `:1989 elif [ -z "${server_profile}" ]`。
- **后果（静态可推，无需活体）**：`MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1`（`:106` 读、`:120` cast）与新名同给时，链在 `:1839` 就拐进首快照注入分支，`:1968` 永不执行 ⇒ 加入者已 `join_ready` 却从未被送出，run 交出的是宿主注入的读数，而调用方以为自己要的是「第二个 Kin 进了专服世界」。这正是那条 guard 自己的措辞要杀的形状——`:464` 写着 *refused rather than carried as a knob that does nothing*；也是 §2.13 说的「静默错答」这一类。
- **要求（在 H1k 分支内补齐，不开第二张卡、不由 M 代 lane 写）**：① 在 `:461–:488` 那个区间里加第七条具名拒止，点名两个旋钮、说明「一次 run 只能选一个目的地」，`exit 2`，位置与其余六条同样在任何拆除点之前；② 契约测试补一条**同给两名 ⇒ `rc=2` 加那句具名 stderr、且 `/tmp/domain-join-profile.json` 没被写出**；③ 默认关闭的字节等价对照扩到这一组合（去掉新名 ⇒ `:1839` 分支的注入读数一字不变）。M 的复审口径：交付里没有这三件就不合入，按第一真实失败层退回。
- **本节的复现命令（全部只读，M 本轮已逐条跑过）**：

```bash
cd ../minekin-wt-h1k
grep -n 'MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER\|joiner-controlled-server-guard begin\|joiner-controlled-server-guard end' test-orchestrator/runner/domain.sh
grep -n '^elif \[ "${refusal_asked}" -eq 1 \]; then\|^elif \[ -n "${open_lan}" \]; then\|^elif \[ "${join_on_controlled_server_asked}" -eq 1 \]; then\|^elif \[ -z "${server_profile}" \]; then' test-orchestrator/runner/domain.sh
grep -n 'REFUSE_FIRST_SNAPSHOT' tests/contract/test_runner_scripts.py
```

  第三条今天只命中 `:382/:384/:390` 那组「默认关闭 + 具名 cast + `run.sh` 转发」断言，没有任何一条把两个名字放在一起 ⇒ 这一组合今天未被覆盖。


## §2.18 H1k 候选字节上 M 侧的独立复审读数：组合缺口的活体演示、七项门禁、以及这轮量到的两格空白（第四十三轮，2026-09-27）

- **测量对象**：H lane 工作树 `../minekin-wt-h1k` 的**未提交字节**（`domain.sh` sha256 `d9a0acfc07719f0eab35305ba21e5a0821a88e100c86b016a80226e695f51a5c`、`tests/contract/test_runner_scripts.py` `7fe48b9d6f92db6f966dfc8d854eb5a5f0403dd0d4fc3bec39e883387ca6419d`，与 §2.17 记的同一对，本轮 `sha256sum` 逐字复现）。M 不在 lane 树里写任何东西：把这两个文件复制进 M 自建的只读复审树 `../minekin-wt-m-r45`（`git worktree add -B m-r45-h1k-review … main`，起点 `ceb079f`），在那里量。
- **§2.17 那条缺口从静态推升级为活体演示（带正对照，非恒真）**：把 `:461–:488` 的 guard 区间用 `sed` 逐字抽出来，前面预置「新名已问、`joiner` 有、`--server-profile` 有、其余六条各自为空」，只换最后一个变量：

```bash
cd ../minekin-wt-m-r45
probe() { { echo 'join_on_controlled_server_asked=1; joiner=kin-probe; server_profile=/tmp/p.json; black_hole=""; no_server=""; not_whitelisted=""'; echo "$1"; sed -n '/joiner-controlled-server-guard begin/,/joiner-controlled-server-guard end/p' test-orchestrator/runner/domain.sh; echo 'echo REACHED_END_OF_GUARD'; } > /tmp/gp.sh; bash /tmp/gp.sh; echo "rc=$?"; }
probe 'refuse_first_snapshot=1'
probe 'open_lan=25570; refuse_first_snapshot=1'
```

  读数：第一条打印 `REACHED_END_OF_GUARD` 且 `rc=0` ⇒ `MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1` 与新名同给时 guard 原样放行，§2.17 推出的「加入者被备好却从未送出」这条路在这份字节上确实可达；第二条 `rc=2` 并打印 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER and MINEKIN_DOMAIN_OPEN_LAN name two worlds…` 那句 ⇒ 探针真的走进了 guard 区间，第一条的 `rc=0` 不是探针没接上。复现只读、不碰产品 `src/**`、不挂载任何卷。
- **候选字节上的门禁读数（每条单独一步、先读退出码再落字）**：`bash -n test-orchestrator/runner/domain.sh` ⇒ `rc=0`；`uv run --frozen --offline pytest tests/contract/test_runner_scripts.py -q` ⇒ `81 passed`（`rc=0`，M 侧独立复量，lane 自报的那轮是整树 `578 passed in 64.79s`，见 `../minekin-wt-h1k/.tmp/h1k-suites.log`）；`ruff check .` / `ruff format --check .`（`365 files already formatted`）/ `pyright`（`0 errors, 0 warnings`）/ `check_boundaries.py` / `check_case_assertions.py`（`OK (150 registered)` ⇒ 这份字节没有登记任何 case）/ `verify_fixture_digests.py` / `check_workflow_pins.py` / `git diff --check` ⇒ **各自 `rc=0`**。合入门禁的静态面今天是清的。
- **lane 侧的失败材料完好、且规范卷确实一次都没挂**（M 只读 `docker inspect h1k-live-b` 核）：挂载为 `/src`=`../minekin-wt-h1k` **只读**、`/data`=私有卷 `minekin-h1k-live`、`/out` 可写、服务端 jar `:ro`；`minekin-runner-data` 不在列表里。该容器 `Exited (255)`。两轮活体都留下了材料而没有覆盖：`live-a-rejected-singleword/` 在 header 的 `session argv` 里明明带着 `--server-profile …`，guard 却报 `:468` 那句 `--server-profile is absent`（argv 形状问题，属 lane 的驱动侧），lane 把目录改名保留后另起 `live-b`；`live-b/` 过了 guard（`domain: server run directory /data/server-runs/run-1`、`server ready`、`enable-status=false`），新名的两条具名行都打了出来（`… dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-1/server.properties` 与 `… is sent into the controlled server world this run started …`）⇒ **§2.16 要的目的地读数已经出现**；但随后 `domain: Kin2 never arrived within 420s`（而 `:1563–:1564` 的等待循环带 `kill -0 … || break`，容器实跑约 1 分钟 ⇒ 加入者进程早已退出，`/tmp/domain-join-session.err` 当时为空），`client-environment.txt` 的写入报 `Read-only file system`（`:1459` 那句 `>>` 的失败由 bash 自己报出，脚本 `|| true` 吞掉；`:1301` 早就用 `if ! : > "${client_environment_readout}"` 容忍了这个文件不可写，所以这是一条噪声而不是新的阻因），下游判语 `THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers 127.0.0.1:25570`——探针目标 `25570` 是 LAN 形状的旧端口，而这轮目的地是 `25566`，两者不一致正是 H1i/#52 要交接的那一格。**所以 `live-b` 只到「目的地读对」，①–④ 的到达/PLAYABLE/受控/释放读数一格都还没封出，H1k 不能凭这份材料合入**；第一真实失败层在加入者进程自身为何早退，归 lane 判。
- **本轮未量的两格（照实登记，不补口径）**：① 合并树的门载荷仍要 `report_promotion.py --data-root /data` 才能算，lane 侧那次尝试被引擎挡回（`../minekin-wt-h1k/.tmp/h1k-gate-payload.log` 全文是 `request returned 500 Internal Server Error … /pipe/dockerDesktopLinuxEngine/_ping`）；M 侧本轮也没能挂 `:ro` 复算 ⇒ 该读数留到 H1k 交付后在合并树上量，`cfa0f118…` 的相等结论今天仍是「未验证」而不是「已复核」。② 主干推送：`git fetch origin` 报 `Failed to connect to github.com port 443 via 127.0.0.1`（本机代理此刻拒绝外连，`uv` 走索引时同因失败，故上面所有 Python 门禁都改用 `--offline`）⇒ 本节只能先落本地提交，远端 SHA 与 CI 结论等网络恢复再核，不据此声称已合入远端。


## §2.19 同一轮里的补量：门载荷在主干字节上重新算到了，§2.18 那两格空白收掉一格（第四十三轮后半，2026-09-27）

- **门载荷（`report_promotion` 的 `work_packages` + `overall` 整段按 `sort_keys` 序列化再取 sha256）在当前主干字节上复算**：容器 `minekin-runner:local`，规范卷 `minekin-runner-data:/data` 以 **:ro** 挂、`/src` 挂主干 worktree（同样 `:ro`），`LD_LIBRARY_PATH=/opt/sqlite/lib`、`PYTHONPATH=/src/src`：

```bash
cd ../minekin-wt-integration
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker run --rm \
  -v minekin-runner-data:/data:ro \
  -v 'C:\Users\darling\Documents\agent_work\minekin-wt-integration:/src:ro' \
  -e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src \
  minekin-runner:local python /src/tools/report_promotion.py --data-root /data > /tmp/promotion.json
echo "rc=$?"                       # 读数是 1
python .tmp/trunk_digest.py /tmp/promotion.json
```

  本轮输出：`rc=1`、`/tmp/promotion.json` 103921 字节、`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ **与登记的常量逐字相同，而且这次是量出来的而不是引用的**。跑前 `docker ps` 为空（无并发活体窗口），跑时只读挂载、未封存任何 attempt/bundle。
- **这把 §2.18 的 ① 从「未验证」改成「主干侧已复核」**：仍**没有**的那半是 H1k 合入后在合并树上的同一读数（PRE==POST 的对照要等 lane 交付），所以 §2.18 里那句「`cfa0f118…` 今天仍是未验证」在 §2.18 自身的时间点是如实的，本节只把时点往后推一格，不回收它。
- **§2.18 的 ②（推送不可用）在同一轮后半已经不复存在**：外连恢复后 `git -c credential.helper= -c credential.helper=wincred push origin HEAD:main` 报 `ceb079f..4a8fec3  HEAD -> main`（`rc=0`），本节的提交随后一并推上去并核远端 SHA。CI 结论仍按协议在浏览器/REST 里读过才写，本节不预先声称。
- **一个纯操作性的坑，记下来省下一轮**：Git Bash 会把 `C:/Users/...` 这类 Windows 路径当 POSIX 路径吃掉（第一次 `docker run -v C:/…:/src:ro` 变成在容器里找 `/work/C:/…`，`rc=2` 且 stdout 为空）。带盘符的挂载源要用反斜杠原样写并置 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`。


## §2.20 live-b 的第一真实失败层：材料指向容器引擎事件而不是 H1k 的字节（第四十三轮收尾，M 只读取证，2026-09-27）

- **取证口径**：`live-b` 的容器 `h1k-live-b` 是 `Exited (255)` 而不是被正常拆掉的，`/tmp` 还在容器层里 ⇒ `docker cp h1k-live-b:/tmp` 到 M 自己的 `.tmp/m-r43-btmp/`（不写 lane 树，不动任何卷）；卷侧用一次性 `--rm` 容器以 `minekin-h1k-live:/data:ro` 读（这是 H 的私有卷，**不是**规范卷 `minekin-runner-data`）。
- **量到的形状**：
  * H1k 新写的加入者 profile **是对的**（`/tmp/domain-join-profile.json`，503 字节）：`schema_version 2`、`host 127.0.0.1`、`port 25566`（正是这轮 `server.properties` 的号）、`auth_mode offline`、`allowed_versions ["1.20.1"]`、`target_authorization.basis` 写明「只授予本受控 runner 为这一轮起的回环世界，不点名任何回环外或操作员给的地址」⇒ §2.16 的目的地判据在这一格是**通过了**，且没有放宽认证/地址。
  * 服务端真的起来了：`/data/server-runs/run-1/server.log` 80 行，最后一行 INFO 是 `[10:48:03] [Server thread/INFO]: Done (5.395s)!`；此后**没有任何 join 行**（`Kin2|joined the game|has the following entity data` 三类 grep 全空）。
  * **宿主自己也没进去**：`/tmp/domain-session.json` 与 `/tmp/domain-join-session.json`、`/tmp/domain-join-session.err`、`/tmp/domain-server.log` **全为 0 字节**——两条 CLI 连一个字节都没来得及写出，而 joiner 的 kin 根 `/data/kin/kin-h1k-join/run/` 已建好，`client-environment.txt` 有 502 字节、`session/` 与 `bundle/` 目录也在。
  * 同一分钟里 `:1459` 报 `Read-only file system`，而更早的写入（`:1301`、launch 探针）成功过；紧接着 lane 下一次要用引擎时拿到 `request returned 500 Internal Server Error … /pipe/dockerDesktopLinuxEngine/_ping`（`../minekin-wt-h1k/.tmp/h1k-gate-payload.log`，18:48 之后那轮）。现在 `docker version` 报 `linux/amd64`、Server `29.5.3`，引擎是活的。
- **判读（照实两条，不提前定案）**：最 Supported 的解释是**容器引擎在 10:48 前后出事**，把 `/data` 打成只读、把宿主与加入者两条 CLI 一起掐掉 ⇒ 容器 `Exited (255)`，于是 `Kin2 never arrived within 420s` 与 0 字节会话文档都是这件事的影子，而不是 H1k 的形状不通。**未被排除的另一条**是专服形状下宿主根本进不去自己那格世界（若如此，重跑会稳定复现）。两者的判别子只有**在健康引擎上重跑一轮**：如果宿主进得去、`Kin2 joined the game` 出现、两条会话文档非空，就归环境；如果仍然 0 字节且 `Done` 之后无 join 行，才轮到 H1k 的字节背。
- **对合入的后果（M 的复审口径）**：`live-b` 现在**不能作为 H1k 的活体封证**，也**不能作为 H1k 的反证**；§2.18 里「①–④ 一格未封 ⇒ 不合入」不变，退回项仍是 #56（组合拒止）加这一条重跑要求。复现命令：

```bash
docker ps -a --format '{{.Names}} {{.Status}}'
docker cp h1k-live-b:/tmp/. <M 自己的 .tmp>/m-r43-btmp
MSYS_NO_PATHCONV=1 docker run --rm -v minekin-h1k-live:/data:ro minekin-runner:local \
  bash -c 'wc -l /data/server-runs/run-1/server.log; grep -nE "joined the game|has the following entity data|Done \(" /data/server-runs/run-1/server.log | tail'
```

- **本轮没有发生的事**：没有写 lane 树、没有写规范卷、没有封存或撤销任何 attempt/bundle、没有改 case 判据或 registry 字节；失败材料（`live-a-rejected-singleword/`、`live-b/`、`domain.sh.h1k-pristine`、两组反例日志）全部原地保留。


## §2.21 判别子跑完了：H1k 的专服形状在 M 的私有卷上真到达、真 PLAYABLE、真受控、真释放（第四十四轮，2026-09-27）

- **为什么补这一轮**：§2.20 留了两条并列解释（容器引擎事件 vs 专服形状下宿主进不去），判别子只有一件事——在健康引擎上原样重跑。M 不做二次推测，直接重跑：脚本 `minekin/.tmp/m-r45-rerun.sh`，卷 `minekin-m-r45-live`（**M 自建的私有卷**），`/src` 与 `/drv` 以 `:ro` 挂 H lane 的树（跑前核 `domain.sh` 仍是 `d9a0acfc0771…`，跑后再核未变），种子 store 来自 `minekin-v4-join:/ro`，服务端 jar `:ro`，**规范卷 `minekin-runner-data` 全程未挂载**；材料落 `minekin/.tmp/m-r45-out/live-m/`。第一次尝试因 docker argv 顺序写错（`bash` 被当成镜像名拉了 `bash:latest`，`rc=127`）没有跑起来，改正后重跑。
- **逐字读数（`90-readouts.txt`，`domain.sh rc=14 finished_utc=2026-09-27T12:11:36Z`）**：
  * (a) 本轮自己的服务端目录与设置：`/data/server-runs/run-1`，`server-ip=127.0.0.1`、`server-port=25566`、`white-list=true`、`enforce-whitelist=true`、`max-players=2`、`online-mode=false`；`server.log` sha256 `09f89cf18f7671550dc1ebbcf0ee553b7b56eece4612b34442b982537ea0dcba`（19061 字节）。
  * (b) H1k 新写的目的地行：`domain: the joining client dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-1/server.properties`。
  * (c) 加入者 profile 文档（503 字节，sha256 `4cc3995e8eb6ac5bf58a1260c91f9a6f0b7deae3a699301ac897442d578c7e1f`）：`port 25566`、`host 127.0.0.1`、`auth_mode offline`、`allowed_versions ["1.20.1"]`、`target_authorization.basis` 只授本轮回环世界 ⇒ 目的地与授权都没放宽。
  * (d) **到达与按名应答**：`[12:08:15] Kin joined the game`、`[12:08:16] Kin2 joined the game`；`Kin2 has the following entity data:` 共 **80 行**，首三行是 `[-2.5d, -60.0d, -3.5d]` / `[0.0f, 0.0f]` / `[-3.387…, -60.0d, -2.398…]`，末三行是 `[45.0f, -20.0f]` / `[2.853…, -60.0d, 6.462…]` / `[45.0f, -20.0f]` ⇒ 转体读数是 H1h 那对限定输入（yaw 45 / pitch −20），位置从 `-2.5,-3.5` 走到 `2.85,6.46` ⇒ 前进按住生效；**正对照同轮量到**：宿主名 `Kin has the following entity data` 计数 **0**（宿主自己从不被这样应答，所以这 80 行按名指向的确实是第二个客户端）。
  * (e) `domain.sh` 自己说的那两句：`domain: the world heard Kin2 arrive`、`domain: Kin2 admitted its first snapshot of that world`。
  * (f) 加入者自己的 run 文档末行：`connection_state: PLAYABLE`、`session_state: STOPPED`、`input_release_failed: false`、`status: ended`、`run_id fe0f26c044524ca5b2dba867f03c25d3`；台账事件类型含 `InputLeaseGranted`、`InputReleased`、`JoinObserved`、`PlayableEstablished`、`SessionInterrupted` ⇒ PLAYABLE→受控→**释放**这条链在专服形状上闭合。宿主文档同态：`connection_state PLAYABLE`、`input_release_failed false`、`run_id a2bbca0640fd45d58a21d13e4c9ac4ce`。
  * (g) 停止侧：`session stop said {"asked": [342], "nothing_held": [342], "released": [], "unconfirmed": [], "terminated": [342], "status": "stopped"}`，随后 `session exited 14`，两份文档的 `outcome` 都是 `BRIDGE_LOST`。
- **判读（能说到哪、不能说到哪）**：**能说**的是——H1k 的形状本身通：宿主进得了本轮专服世界、第二个客户端按 `server.properties` 的号 dial 并按名被服务端听见、PLAYABLE 拿到、限定输入生效、释放闭合；因此 `live-b` 的 0 字节会话文档与 `Kin2 never arrived` 归 §2.20 那条引擎事件，**不归这份字节**。**不能说**的是——这不是封证：材料在 M 的私有卷上，没有 attempt 登记、没有 bundle、没有四读，`rc=14` 与 `outcome: BRIDGE_LOST` 这两格是否落在 `assert_case_evidence.py` 的 PASS 判据内，本轮**未判**（判它属 V5′/M-C1，封它属 E7 独占规范卷）。同理，本轮也不改变任何门：`check_case_assertions` 仍 `150 registered`，主干门载荷仍是 §2.19 量到的 `cfa0f118…`。
- **对 H1k 合入的口径（不变的那半 + 新的那半）**：lane 仍要交付 §2.17/#56 的三件（第七条组合拒止、同给两名 ⇒ `rc=2` 且不写 profile 的契约测试、默认关闭对照扩到该组合），并在**它自己的**记录里带上活体读数；M 这一轮的重跑作为**判别证据**登记，不代替 lane 的封证，也不作为合入判据里「活体已通」的替身——它证明的是「这形状今天能跑通」，所以 §2.20 里「归环境还是归字节」那一问已经关闭（任务 #57 由此收口）。
- **复现**：

```bash
bash C:/Users/darling/Documents/agent_work/minekin/.tmp/m-r45-rerun.sh
# 材料：minekin/.tmp/m-r45-out/live-m/{00-header.txt,90-readouts.txt,server.log,domain-join-profile.json,
#       domain-join-session.json,domain-session.json,domain-stderr.log}
```


## §2.22 lane 的记录到了、双方判定一致，而引擎已经活了：H1k 下一轮的具体三件（第四十五轮，M 主控裁决，2026-09-27 20:20 +0800）

- **lane 交付的现场（M 只读核对，不代 lane 提交）**：`../minekin-wt-h1k/docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md`（389 行，`19:35` 落盘，仍是未跟踪状态；分支仍是 `29c5187` + 未提交的 `domain.sh d9a0acfc…` / `test_runner_scripts.py 7fe48b9d…`）。记录里两处与 M 直接相关：
  * §5 把 `live-b` 的第一真实失败层**具名为基础设施**：`500 Internal Server Engine … dockerDesktopLinuxEngine`、`docker info` 超时 `rc=124`、私有卷 `minekin-h1k-live` 在宿主机侧被降级为只读，并写了引擎恢复尝试（重启 Docker Desktop ×2、`wsl --terminate docker-desktop` 后轮询 ≥10 分钟）。这与 M 的 §2.20 取证同因、与 §2.21 的判别子结论一致 ⇒ **归因两侧闭合，不是分歧**。
  * §9 逐字复确 §2.17 的三条形状事实（guard 恰六条无第七条、`:1839` 在 `:1968` 之前拐走注入组合、`REFUSE_FIRST_SNAPSHOT` 在契约测试里只有 `:382/:384/:390` 那组断言），如实申报「本交付未含」三件，四态封顶为「仅在分支、待 §2.17 补齐」并**不请求合入**。理由也成立：加第七条拒止会让 `d9a0acfc…` 失效，§2/§3/§4 的容器内读数必须在新字节上整体重跑，而当时引擎挂死——本卡的纪律是不交未重测的改动。**M 接受这个口径：H1k 未合入是双方共同的判定，M 不在此处替 lane 动字节。**
- **解锁事实（这是本轮唯一的新外部状态）**：引擎自 20:05 起是活的——M 在 §2.21 里用 `minekin-runner:local` 起了三个容器并跑完整程（`domain.sh rc=14`，服务端日志 `Kin joined the game` 12:08:15 / `Kin2 joined the game` 12:08:16 / 80 行按名应答）。所以 lane 下一轮不再有「做不了半套」这个约束。
- **主控裁决（H1k 下一轮的范围，按序）**：① 在 guard 区间加第七条具名拒止 + 契约测试「同给两名 ⇒ `rc=2` 且不写 `/tmp/domain-join-profile.json`」+ 默认关闭字节等价对照扩到该组合；② 在新字节上整体重跑 §2/§3/§4 的容器内读数与两组反证（旧字节的那批读数在记录里保留为历史，不改写）；③ 在 `minekin-h1k-live` 卷上补一轮活体 ③（卡面 §2.13 只认真实 run 的 `server.log`；M 的私有卷重跑**不代替**这一格，只证明形状可通）；④ 量 `report_promotion` 门载荷（引擎已可用，§2.19 的命令形状可直接复用）。四件齐了才进入 M 的合入复审。
- **队列一寸未动**：主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；H lane 的 `lane_next` 仍是 **H1k（仅在分支，待 §2.17 三件 + ③ 补读 + 门载荷）**，其后严格接 H1i（同一 `domain.sh` 面）；V 的 `lane_next` V5′ 仍停等 H1k 入干；E lane 仍不派工，规范卷写窗仍归 E 独占、本轮 M 只以 `:ro` 读。真实封证计数不变：LAN 第二客户端在专服形状下的同 run 封证 **0**。

### 2.23 第四十六轮：H1k 第①项的 M 侧只读预读（lane 字节已移动），以及本轮的停放状态

**本轮只读、只量、不写 lane 面。** 20:30 复量 `../minekin-wt-h1k` 的未提交候选字节，相对 §2.18 已移动：`test-orchestrator/runner/domain.sh` 由 `d9a0acfc07719f0eab35305ba21e5a0821a88e100c86b016a80226e695f51a5c` 变为 `e1d8dbb98d5f760d…`（156,083 → 156,467 字节），`tests/contract/test_runner_scripts.py` 由 `7fe48b9d6f92db6f966dfc8d854eb5a5f0403dd0d4fc3bec39e883387ca6419d` 变为 `02ec23c2586aa79d…`（159,426 → 161,021 字节）⇒ §2.22 的第①项在飞，第②③④项尚无读数。

**第七条组合拒止已在 guard 区间内（只读确认，不代表复审通过）**：新块以 `if [ "${join_on_controlled_server_asked}" -eq 1 ]; then` 包住整段，七条具名拒止依次是 joiner 缺席、`--server-profile` 缺席、`open_lan`、`black_hole`、`no_server`、`not_whitelisted`，第七条为 `if [ "${refusal_asked}" -eq 1 ]`，文案具名「name two destinations for one wait; the chain answers the snapshot refusal before any joining client is sent」并 `exit 2`。两条置位读法逐行核过：`refusal_asked` 在 `domain.sh:120` 置 0、`:122` 仅对 `1|true` 置 1；`join_on_controlled_server_asked` 在 `:168` 置 0、`:171` 同形状 ⇒ 默认关闭时整段惰，不新增允许面、不引入操作者未给的地址（§2.22 第①项的「两名字同真 ⇒ rc=2 且不落 `/tmp/domain-join-profile.json`」契约断言与「默认关闭字节相等扩展到该组合」仍待 lane 交付与 M 复跑）。契约侧已有逐字引用：`tests/contract/test_runner_scripts.py:2807`、`:2834`。

**CI 读数（各自单独一步，`/actions/runs?per_page=3`）**：run 866 `d933fbe` `completed/success`、run 867 `c982a32` `completed/success`、run 868 `fcce60c` 在 20:30:49Z 时点 `in_progress` ⇒ 该笔的绿读数本轮不作。主干工作树 `git status --short` 空、`git ls-remote origin refs/heads/main` = `fcce60cb41dadb5a42a931d3c834a19c35ddaa01`。

**停放状态（供接手会话）**：M 侧无未提交改动，规范卷写窗仍归 E 独占且 M 全程只 `:ro`；H lane 的续跑会话在飞，允许面未变（`domain.sh`、`tests/contract/test_runner_scripts.py`、`docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md`），其未提交候选必须先备份 + 记 sha256 再动，禁止 `git checkout --`/`restore`/`reset --hard`。下一格仍是 §2.22 的第②③④项，其后才是 M 的合入复审与 V5′→M-C1→E7→M-G1。真实封证计数不变：**LAN 第二客户端在专服形状下的同 run 封证 0**。

### 2.24 第四十六轮补：§2.23 的字节读数只活到它自己的时点

20:32 复量同一 lane 树：`domain.sh` 仍是 `e1d8dbb9…`（156,467 字节），`tests/contract/test_runner_scripts.py` 已从 §2.23 记录的 `02ec23c2…`（161,021 字节）移动到 `33f7d7f02222dd4f…`（171,525 字节），分支 HEAD 仍 `29c5187`、仍未提交 ⇒ lane 在第①项内持续加契约面，§2.22 的第②③④项尚无读数。**下一位接手者不要引用 §2.23 的测试摘要作为候选字节**：复审前必须自己重取 sha256。CI 同刻实读：run 866/867 `completed/success`，run 868 `fcce60c` 与 run 869 `bd5ee23` 仍 `in_progress` ⇒ 这两笔的绿读数本轮不作。主干工作树 clean，规范卷仍只 `:ro`，本轮零封证：**LAN 第二客户端在专服形状下的同 run 封证 0**。

### 2.25 第四十七轮：H1k 在途字节上的 M 侧冲突对普查——第八对缺口 `ONLINE_MODE=true` × `JOIN_ON_CONTROLLED_SERVER=1`（未做活体对照）

lane 的第①项已落字节（guard 区间由 §2.18 的 `:461–:488` 变为 `:461–:492`，第七条 `refusal_asked` 具名拒止在位，盘上 sha256 `domain.sh e1d8dbb98d5f760d…`／测试 `33f7d7f02222dd4f…`，本节读数为 20:53 时点，复审时须自取）。M 按 §2.17 的路子把新旋钮与盘上全部 `MINEKIN_DOMAIN_*` 名字做逐对普查，得到两类结论。

**已被既有拒止覆盖的对（不追）**：`--server-profile` 缺席、joiner 缺席、`OPEN_LAN`、`BLACK_HOLE`、`NO_SERVER`、`NOT_WHITELISTED`、`REFUSE_FIRST_SNAPSHOT` 七对在 guard 内；`auto_bundle × joiner` 由 `domain.sh:433` 的既有早停承担 ⇒ 「auto run 强制 `--online-mode`」那条 H3/V2 时期记录无法经由 auto 路径污染新形状（auto 根本带不了加入者）。

**缺口一对**：`MINEKIN_DOMAIN_ONLINE_MODE=true` × `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`。字节证据三条：`:88` 取变量；`:883–:886` 把 `true` 铸成 `online_args=(--online-mode)`、`false` 铸成 `--no-online-mode`、空串不传；`:914` 把这组 argv 直接拼进 `--server-profile` 那条受控专服启动调用（与 `:920` 的 `--keep-running` 同一条命令）。新形状把加入者送进的正是这条命令起起来的专服（等待分支 `:1988` `join_the_published_world "${server_directory}/server.log"`，答题行按加入者名读自同一文件——§2.21 的私有卷重跑在默认可铸形状下量到 80 条按名回答行，即该文件确实载着判据）。于是 `true` 那一式要求服务端向 Mojang 校验加入者，而受控加入者没有凭据路径：这一 run 会以「加入者从未到达」的超时／`BRIDGE_LOST` 形状收场，而不是具名拒止——**与 §2.17 同一失败族**（冲突对缺具名拒止 ⇒ run 不可判），且让它变绿的唯一「修法」是放宽认证，属目标硬禁。

**本节未做活体对照**，缺口只按字节形状申报。判别实验（谁都能重跑，须在该 lane 的活体窗之外）：A 式 `MINEKIN_DOMAIN_ONLINE_MODE=true` + `JOIN_ON_CONTROLLED_SERVER=1` + `--server-profile` ⇒ 期望当前为超时形状、补第八条拒止后为 `rc=2` 且不落 `/tmp/domain-join-profile.json`；B 式（正对照）把 `ONLINE_MODE` 置 `false` ⇒ 期望仍走到 §2.21 那种按名回答；C 式（默认关闭等值）不设新名 ⇒ 加入者 argv 与 base 逐字节相同（lane 读数① 已在盘上字节做过五组 base↔tip 对照）。

**处置**：登记为 H1k 的复审退回项 #58，排在 §2.22 四项之后（同一 `domain.sh` 独占面，不另开 lane、不并行改）。M 不在 lane 在飞时改它的面，也不代为提交。

### 2.26 第四十七轮纠正：§2.25 的「第八对缺口」归因错了，撤回「补第八条拒止」的处置

**上一笔（`52e78b5`）的判定不成立，按新证据改正，不修改它写下的历史句子。** §2.25 把 `MINEKIN_DOMAIN_ONLINE_MODE=true` × `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1` 判成 §2.17 同族的「冲突对缺具名拒止」。M 当时只读了 `domain.sh` 的 `:88/:883–:886/:914/:1988` 四条字节，没读 tools 侧与案名侧的既有承担者。补读之后：

- `tools/run_controlled_server.py:226–:235`：`_online_mode_text` 在 `online_mode is None` 时按 `profile.auth_mode` 派生，显式传入时才强制——**强制是设计出来的出口，不是漏网**。
- 同文件 `:303–:312` 的 docstring 逐字写着：这个 override 存在的唯一理由就是「an offline client dialling a server that requires session verification」，而该形状「must end in `AUTH_MODE_MISMATCH` and must never be worked around」，并明说「the point of that case is that the client cannot satisfy the server, not that it should try」。
- 该案有名字：`tests/unit/test_case_evidence_assertions.py:3715` ⇒ 「ADMIT-040: an offline identity that met a server demanding online authentication」；`domain.sh:1788` 把这一形状收在 `case_id = ADMIT-040` 的判定分支里，且要求 `--server-profile` 在场，缺任一即 `rc=2`；契约测试 `tests/contract/test_runner_scripts.py:299` 钉着那条拒止文案。
- 同族护栏还在别处：`tools/run_controlled_server.py:264–:271` 在强制 online-mode 的形状下**拒绝** `--enable-status`，理由正是「不给一个客户端进得去的服务器打广告」。

⇒ **不新增第八条 guard 拒止**；`guard 461–492 未列该对` 不等于 `无人拒止该对`。#58 由「复审退回项」降级为一条**待判问题**并保留材料不删：真正没读过的只剩一格——`JOIN_ON_CONTROLLED_SERVER=1` 与 `ONLINE_MODE=true` 都被显式设、而 `case_id` **不是** ADMIT-040 时，产物是「具名失配」还是「加入者静默超时」。这一格要么靠一次容器内形状断言、要么靠一次活体，M 不在 lane 的活体窗里抢跑，也不拿 §2.21 的默认可铸形状冒充它的读数。

**方法申报（防同类错判）**：判「冲突对缺不缺具名拒止」之前，除 guard 区间外必须先 grep `tools/**` 与 `tests/unit/**` 里有没有该形状的既有具名承担者（本案的承担者是 `AUTH_MODE_MISMATCH` + ADMIT-040 的 case 门）。§2.25 那句「唯一让它变绿的『修法』是放宽认证，属硬禁」仍然成立，但它推出的正确动作是**先找既有失配再谈补拒止**，不是补拒止。

### 2.27 第四十八轮：#56 的契约侧在 H1k 当前候选字节上预检通过（M 自己的树，含 4-fail 反证与还原）

lane 仍在收 §2.22 第③④项（它的容器窗在用，M 不进那棵树、不代提交）。M 用等待期只做一件事：**把退回项 #56 的验收要求拿到 M 自己的审查树上按当前候选字节量一遍**，好让真正合入时不靠推测。

**候选字节仍是 §2.23/§2.24 记的那对，无需再开过期申报**：`test-orchestrator/runner/domain.sh = e1d8dbb98d5f…`（156,467 B，mtime 20:50:45 起未再动）、`tests/contract/test_runner_scripts.py = 33f7d7f02222…`（171,525 B）。M 审查树里原有的两份是**旧副本**（`d9a0acfc…`/156,083 与 `7fe48b9d…`/159,426——前者正是 lane 记录里那次破桩前的备份），已按当前字节覆盖并重新 sha256 验证。

**lane 交付的内容对上了 M 退回时提的口径**（行号读自 `tests/contract/test_runner_scripts.py` 当前候选字节）：

1. **逐字引用而非转述**：`:2806–:2810` 的 `FIRST_SNAPSHOT_COMBINATION_REFUSAL` 把那句拒止按两个方向存下来，且注释明写「A copy of the card's own wording here would let the guard rephrase itself and stay green, so the constant is compared against the shipped bytes before it is ever driven」。
2. **`rc=2` 且不留下会被误读成「发送过加入者」的载体**：`:2963` 起那条测试是三段式——组合答案 `exit 2` + 那句原文、下游 `reached-joiner-plan` 不出现、`bash_probe "test -e /tmp/domain-join-profile.json"` 不为 `yes`（用 bash 自己问路径，避开 Windows 与镜像里 `/tmp` 的异义），并额外钉了**位置条款**：`# --- joiner-controlled-server-guard begin` 必须仍在 `JOINER_PROFILE_WRITER` 上游。
3. **默认关闭等值延伸到这一对**：`:3011` 的 `test_the_combination_stays_a_trunk_shape_while_the_new_name_is_off` 要求新名未开时第七条款**一个字都不说**（既不拒也不评论），否则它就成了主干既有形状里的一条新拒止。
4. 非恒真另有两道：guard 区间内 `exit 2` 计数必须恰等于 `CONTROLLED_SERVER_GUARD_REFUSALS` 的 7 条、每条拒止的话在区间内恰好出现一次；lane 另自己写了 `test_the_seventh_refusal_is_not_an_always_true_claim`。

**M 侧读数（全部在 `../minekin-wt-m-r45`，分支 `m-r45-h1k-review`）**：

- 当前候选字节契约全绿：`uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q` ⇒ **`85 passed in 32.62s`**。lane 记录里那份是 `81 passed` ⇒ 那串数字早于它自己追加的这 4 个案（第七拒止的参数化行 + 三条专测），**不是矛盾，是过期**：lane 仍须按最终字节重跑本地/Docker 门禁，这也正是本轮目标写死的动作。
- M 自放的反向证明：只删 guard 里那 4 行（`:487–:490`，`refusal_asked` 出现次数 8→7）⇒ **`4 failed, 81 passed in 12.85s`**，红的正是 `…[first-snapshot-combination]`、`test_the_two_destination_combination_is_refused_before_any_plan_is_written`、`test_the_combination_stays_a_trunk_shape_while_the_new_name_is_off`、`test_the_seventh_refusal_is_not_an_always_true_claim`。破桩前先备份 `../minekin-wt-m-r45/.tmp/m-r46-domain-before-break`（sha256 `e1d8dbb9…` 已验），还原后两份副本 sha256 与候选一致 ⇒ 这 4 个案不是恒真断言。
- CI 欠账：`52e78b5` 的远端作业 `completed / success`；`e33d109` 本轮单次读为 `in_progress`（创建于 13:01:45Z），下一轮按「每轮一次读」续读。

**#56 的契约侧到此可判「已满足」**，但 M 不在候选未提交时合它，也不替 lane 跑它的活体。合入时点仍需四件：①lane 自己 push 的提交 SHA；②真实 merge-base `29c5187` 上的合并 diff 复审；③第③项活体读数（§2.21 的 M 私有卷重跑**不替代**它，且那次读数是 `rc=14 / BRIDGE_LOST`，本就不是封证）；④`report_promotion` 门载荷前后一对。

### 2.28 第四十九轮：lane 的 §2.22 四项读数已到（仍未提交），M 从这批读数里量出两处按构造取不到的前置，各开窄卡

**读数载体与 M 的动作边界**：lane 的补齐轮写在 `docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md` §10（追加节，§5「③ 未验证」与 §9「本交付未含」两句原文保留不 rewrite）。M **没进 lane 的树**，读的是自己在 21:17 做的哈希快照：`../minekin-wt-m-r45/.tmp/h1k-validation-snapshot-21-17.md`，`1f344420499bc8c3…`、48,454 字节。代码字节自 §2.27 之后**未再移动**（`domain.sh e1d8dbb9…`/156,467 mtime 20:50:45、`test_runner_scripts.py 33f7d7f0…`/171,525 mtime 20:31:25），分支仍 `29c5187`、远端仍无该分支的 ref ⇒ **合入仍以 lane 自己 push 为闸**，M 不代提交。
**一处 M 自己的操作瑕疵（如实记）**：本轮 21:11 派续做会话时，压缩前那个 lane 会话其实还活着（它随后在 150 轮上限处停住，停手时正在「加一轮控制关闭活体以免 ③ 恒真」）⇒ **同一棵树上有过两个写者约 6 分钟**。M 的快照恰好落在两者之后、代码字节未变、记录只增不减（§10 是追加节），无覆盖证据；但「先确认在飞会话已停，再派接手」这条要在后续轮里变成硬前置。

**lane 四项的读数（照它记录的原文，M 未复量的地方标出来）**：① 第七条拒止在 `domain.sh:487–:490`、区间由 `:461–:488` 变 `:461–:492`、下游行号整体 +4，契约侧四格（逐字常量、三段式 `rc=2`/无 `reached-joiner-plan`/`test -e` 不为 `yes`、默认关闭字节等值扩到该组合、`test_the_seventh_refusal_is_not_an_always_true_claim`）⇒ 与 §2.27 M 独立做的「删 `:487–:490` ⇒ `4 failed, 81 passed`」配成一对，CE(c) 那格 lane 侧得 `3 failed`。② 新字节上重跑：容器内契约 `85 passed rc=0`、三门 `150 registered` / `W00 …OK` / `boundaries: OK`、静态五门 `rc=0`、大套件 `3 failed, 2517 passed, 5 skipped` 且**三格红逐格关掉**（两格在主干同测同红、第三格单跑 `22 passed rc=0` ⇒ 时序噪声）；另如实申报 §8 复现命令里 `tests/assertions`、`tests/carrier` 两个目录不存在 ⇒ 旧口径 `578 passed` 今天无法按原样复算。③ 它自己私有卷 `minekin-h1k-live` 上两轮真活体：live-c 的 `server.log` 里 `Kin2 has the following entity data` **80 行**、首 Pos `[8.5,-60,-0.5]` → 末 `[-4.11,-60,12.87]`、Rotation `[0,0]` → `[45,-20]`、宿主名 0 行、账本 `JoinObserved → PlayableEstablished` + `InputLeaseGranted/InputReleased(TIMEOUT, EXPLICIT)`、`Kin2 left the game`；live-d 只抽掉三个控制名 ⇒ `Kin2` 仍 80 行但 Pos **40/40 全同**、Rotation **40/40 全同**、租约两条都没有。两轮 `domain.sh` 都以 `session exited 14 / outcome BRIDGE_LOST` 收场，**判级仍写作「不是封证」**。④ 门载荷前后一对：`PRE == POST == cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（6051 字节）、`report_promotion rc=1`、`150 registered` ⇒ 本卡一字未移门。**M 未复量**：③ 的两轮活体、② 的大套件逐格红、CE 三组破桩。

**前置缺口 A（开卡 `H1l`）——专服形状在战役路径上按构造不可达**：`test-orchestrator/runner/run.sh` 的转发名单（`:88–:120`，24 条 `-e MINEKIN_DOMAIN_*`）里**没有** `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`；M 按集合差实测（`domain.sh` 读的名 vs `run.sh` 递的名）在候选字节上确认这条差**恰只此一名**。lane 自己已经把它**具名登记在契约里**（`test_runner_scripts.py:142–:161`：`registered_gap = {JOINER_CONTROLLED_SERVER_KNOB}`，同时要求它出现在 `read`、缺席于 `delivered`，并写明「转发了它的那张卡要删登记，不是删断言」）⇒ 不是隐瞒，是待办。后果正是 `run.sh` 自己注释里那句最坏形状：`domain.sh` 读到一个never-arriving的名 ⇒ 走「not asked for」分支 ⇒ run 照样跑完、照样封，却是**另一个场景的证据**。`H1l` 面：`run.sh` + `tests/contract/test_runner_scripts.py`；验收：转发该名、删除 `registered_gap`、集合差双向为空、默认关闭字节等值不变，外加一次**经 `run.sh` 的真实形状读**（证明容器里的 `domain.sh` 确实看见该名），不是只在 `domain.sh` 直调上通。排序：**H1k 合入之后**（同一契约测试文件，且 `run.sh` 是 H1j 已合的独占面）。

**前置缺口 B（开两张按序卡）——§2.16 第 4 条第一格「同 run 内另一具名实体读数不变」取不到**：`domain.sh:715` 的注释与 `:794` 的 `probe_args=(--probe-player "${probe:-${player}}" …)` 都是**单值**，全仓只有这一处铸名点；`tools/run_controlled_server.py:740` 的 `--probe-player` 是 `default=None` 的单个 `NAME`（非 `append`）。⇒ 一个 run 只能问一个名字，live-c/live-d 里宿主名 0 行是**按构造**而非「宿主没动」。lane 已交 4b（控制关闭对照），4a 明确标为未采并交回 V5′。**M 不动判据**（§2.16 前言要求改口径必须另起一节具名申报，而这里的正确动作是让这一格可取，不是取消它）：先 `M-T1`＝M 独占的 `tools/run_controlled_server.py`（允许重复 `--probe-player`、逐名产出探测序列、缺名与重名的具名拒止、单测含反证、不挂规范卷），后 `H1m`＝`domain.sh` 把第二个名字接上（默认关闭、默认仍单名、旧字节等值照旧）。两张都在 H1k/H1l 之后，且 V5′ 的派工文本必须等 `H1m` 入干后现读三处载体行号（§2.16 第 1 条）。

**CI 与方法一条**：`52e78b5`/`e33d109`/`21a0784` 已于 21:13 复读为 `completed/success`；`5379d3a`、`8bbf3ab` 在 21:15 单读为 `in_progress` ⇒ 绿读数不作。**方法**：凡判据要求「同 run 内两个名字/两个目标」的格，派工之前必须先 grep 铸名点与被调 CLI 的取值形状（本轮就是 M 在派工前量到取不到，符合 §2.16 第 1 条那句「量不到就不派」，也避免了把一张注定红在载体缺失上的活体卡派出去）。

**四态**：已合主干＝本轮零（主干只动了 §2.27/交接/todo 三笔文档）；仅在分支＝H1k 四项读数齐但**未提交未 push**；真实封证＝**0**（lane ③ 自己写明不是封证，M 私有卷那次也不是；LAN 第二客户端在受控专服形状下的同 run 封证仍为 0）；未验证＝M 未复量的 ③/②大套件/CE 三组，以及上面 A、B 两格的闭合。规范卷对 M 仍只 `:ro` 且本轮未挂；未连接用户远程服；未改判据/registry/门禁；失败材料（`live-a-rejected-singleword/`、`live-b/`、旧红字 log、私有卷 `run-1`）逐条申报未删未覆盖。

## §2.29 M-T1 落地：同一 run 现在能问两个具名实体，H1m 的派工文本按已定接口写死（第四十九轮，2026-09-27 21:39 +0800，M 主控）

**收掉的是 §2.28 的 B 格，且在 M 自己的独占面上收**。`tools/run_controlled_server.py` 的 `--probe-player` 由单值转为可重复（`action="append"`、`default=[]`），新 `probe_console_commands()` 把每个名字的 `Pos` 与 `Rotation` 成对相邻排出，at-join 的补测由单 flag 改为逐名 `bursted` 集合；两条具名拒止同时立：重名 ⇒ rc=2 且在落盘前，`--use-target` 配多名 ⇒ 拒（一块方块只挡得住一个视线）。单名形状逐字不变——这不是修辞，是下面那条零名/单名/双名三读里的一格。改面恰 2 文件（该工具 + `tests/contract/test_controlled_server_runner.py`），`domain.sh` 那半张归 H1m。

**读数（退出码单步读）**：契约文件 `28 passed in 3.38s` rc=0；全量 `2645 passed, 3 skipped in 301.14s` rc=0；`ruff` / `check_boundaries` / `check_case_assertions`（仍 `150 registered`，未新增 case）/ `verify_fixture_digests` / `git diff --check` 全 rc=0。两枚反证各自红在该红的案上：`for command in probe:` 改 `probe[:2]` ⇒ 恰 `test_the_console_of_one_run_receives_the_question_of_every_named_kin` 1 failed（零名与单名两案仍绿）；重名拒止改 `if False and …` ⇒ 恰 `test_repeated_probe_names_are_refused_before_the_run_is_written` 1 failed。种桩前先把原字节备份到 `.tmp/m-t1-pre-ce/run_controlled_server.py.orig` 并记 sha256，还原后复量仍 `263ce1046e19e0b3337af4174a84b5cce778c42390a6e8ef068a600e6dfc9466`；全程未对该文件用 `git checkout --`/`restore`/`reset`。

**合入**：施工支 `codex/minekin-m-t1-multi-probe` @ `5ec0500`（真实 merge-base 就是当时的主干 `17a6537`，未动他人面），`--no-ff` 合入主干为 `070390d`，push 后 `git ls-remote origin refs/heads/main` = `070390d1dd7024b6a2655176d2a0a01403e4a611`；分支同轮已 push。

**H1m 的派工文本（接口已定，不必再猜 tools 侧形状）**
- 载体行号（`domain.sh`，主干字节现读）：`:27` `probe="${MINEKIN_DOMAIN_PROBE:-}"`、`:133` `use_target="${MINEKIN_DOMAIN_USE_TARGET:-}"`、`:171` `probe_seconds`、`:715` 唯一铸名点 `probe_args=(--probe-player "${probe:-${player}}" --probe-every-seconds "${probe_seconds}")`、`:716–:717` 的 `--use-target` 追加分支、`:821` `"${probe_args[@]}"` 交给 `run_controlled_server.py`。
- 新旋钮 `MINEKIN_DOMAIN_PROBE_SECOND`，默认关闭：未设 ⇒ `probe_args` 与今日逐字节相等（契约测试按 `:715` 的字面串钉住，沿用 `test_runner_scripts.py` 现在钉 `--probe-player "${probe:-${player}}"` 的写法）；设了 ⇒ 在 `:715` 之后追加**第二个** `--probe-player <该名字>`，不替换第一个。
- 两条具名拒止要在 domain.sh 的 guard 区里早退，不把下游 rc 当自己的判据：① 第二名与第一名同名；② `MINEKIN_DOMAIN_USE_TARGET` × 第二名（tools 侧那句 `--use-target puts a block in front of one kin's look, and 2 --probe-player names do not say which` 是兜底，不是替代）。
- `run.sh` 的 `-e MINEKIN_DOMAIN_*` 名单必须带上这个新名，否则容器里读到空、旋钮什么都不做——与 H1l 同一族缺陷，允许面 `test-orchestrator/runner/run.sh` + `tests/contract/test_runner_scripts.py`，验收里要有一次**经 run.sh 的**真实形状读（两名都被问过）。
- 反证三枚：删追加分支 ⇒ 两名案红；放宽默认关闭的等值断言 ⇒ 单名案红；删同名早退 ⇒ 具名拒止案红。门载荷前后一对（本卡不动 cases/registry ⇒ 期望 PRE==POST）。
- 排程：H1m 严格排在 H1k 收口之后（同文件一名 owner）；V5′ 排在 H1l 与 H1m 之后，§2.16 第 4 条第一格到那时才可取。

**欠账（如实，不冒充）**：门载荷的 POST 没量到。这次 `docker run --rm -v <树>:/src:ro -v minekin-runner-data:/data:ro … minekin-runner:local python tools/report_promotion.py --data-root /data` 返回 **rc=127**（M 的调用姿势问题，该镜像入口是 `/__cacert_entrypoint…`，需按镜像入口复核），且取读时 lane 的活体容器 `unruffled_goldstine` 正在飞 ⇒ 不抢引擎。所以 `cfa0f118…` 在这一节只能作为 §2.19 的 **PRE** 引用，M-T1 的入干不构成「门载荷已在新字节上复量」。**CI**：`070390d`（含 `5ec0500`）待读；`873/874/875` 已读为 `completed/success`（`21a0784`/`5379d3a`/`8bbf3ab`），`876`（`17a6537`）在 21:23 单读仍 `in_progress`。

**四态**：已合主干＝M-T1（`5ec0500` → `070390d`，远端 SHA 已核）；仅在分支＝H1k 候选**仍未提交未 push**（lane 树停在 `29c5187` + 同样三处脏改动，`.tmp/h1k-recheck/` 21:34 还在写 ⇒ lane 会话在飞，M 不进其树、不代提交）；真实封证＝**0**（LAN 第二客户端在受控专服形状下的同 run 封证一格未动，`E6` 的 `V1201-020` seq4 仍是本地专服单客户端，不得顶替）；未验证＝M-T1 的门载荷 POST、H1m 全卡、V5′ 第 4 条第二格（控制关闭的同形状对照）。规范卷对 M 仍只 `:ro` 且本轮未写成；未连接用户远程服；未改判据/registry/`mandatory`；备份原字节与两枚 CE 日志（`.tmp/m-t1-ce-a.log`、`.tmp/m-t1-ce-b.log`）逐条申报未删未覆盖。

## §2.30 §2.29 那格欠账当场补上：门载荷在含 M-T1 的主干字节上重测，PRE==POST（第四十九轮后半，2026-09-27 21:41 +0800）

在 `7546ec9`（已含 M-T1 的合入 `070390d`）的树字节上、规范卷 `:ro`、私有工作树未挂写：`report_promotion` rc=**1**（按构造 blocked），整份文档 103,921 字节，`{work_packages, overall}` 子集（`sort_keys=True`）sha256 = **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`** ⇒ **与 §2.19 的 PRE 同值**，M-T1 入干没有移动门载荷。逐格未变：`W30.promotable False`（`NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`）、`p0-core` 仍 `REQUIRED_CASE_NOT_REGISTERED`、`overall_blocks` 仍是那一条、`W30` 的 `absent` 两条 OFFLINE（060/080）与 `non_mandatory` 11 条、`p0-core` 的 9/24 条、`misattributed` 两侧为 0。这不是「所以可以晋级」的相反论断，只是把 §2.29 里那格「只能引用 PRE」换成量到的读数。

**操作教训（省下一个人的时间）**：§2.29 那次 rc=**127** 与引擎无关，是 M 自己把卷源写成了反斜杠 `C:\Users\…` —— Docker Desktop 对 `-v` 源路径要 `C:/Users/…` 正斜杠配 `MSYS_NO_PATHCONV=1`，配错时报的是 `Error response from daemon: The system cannot find the file specified`，看起来像镜像坏了。镜像入口 `/__cacert_entrypoint…` 与 `python` 都正常（同轮最小探针 `docker run --rm minekin-runner:local python -c …` 返回 3、rc=0）。取读时 lane 的活体容器（`affectionate_ardinghelli`，Up 5 分钟）在飞，但 `minekin-runner-data` 只做 `:ro` 且本轮 E 不在写，未占他 lane 写窗。

四态增量：真实封证仍 **0**；已合主干仍是 M-T1 那一笔；此轮只补读数、未动 case/registry/`mandatory`、未删任何材料（`.tmp/m-r49-report-post.json`、`.tmp/m-r49-report-post.err` 在案）。

## §2.31 主干红了五次，红因是 M 自己：M-T1 漏跑 CI 的两道门（第五十轮，2026-09-27 21:57 +0800，M 主控）

**这一节具名申报 M 的失误，并纠正 §2.29 的口径**。§2.29 那句「读数（退出码单步读）：…`ruff` / `check_boundaries` / … 全 rc=0」在它自己的时间点是如实的——它列的是 M 真跑过的那些——但它**不是 CI 的门禁清单**，读者有理由当成「CI 会过的全套」。真实情况：`.github/workflows/ci.yml:44-55` 里含 `ruff format --check .` 与 `pyright` 两道，M-T1 一道都没跑就落了地。

**红范围（`/actions/runs?per_page=9`，21:57 单读）**：`876`（`17a6537`，M-T1 之前的主干）`completed/success` ⇒ `877`（分支上 `5ec0500`）、`878`（合入 `070390d`）、`879`（`7546ec9`）、`880`（`f29b77d`）、`881`（`8b66ccf`）五笔连续 `completed/failure` ⇒ **第一真实失败层就是 M-T1 的字节**，不是 lane 的在途改动（lane 从未 push，远端无其 ref），也不是引擎。jobs 端点对未认证请求仍 404，所以定位走的是「读 `ci.yml` 步骤清单 + 在本地逐道复跑」，不靠浏览器。

**两道门各自红在哪（本地复量）**：
* `ruff format --check .` ⇒ rc=**1**，`2 files would be reformatted, 363 files already formatted`（正是 M-T1 的两个文件）。
* `pyright` ⇒ rc=**1**，3 errors 全在 `tests/contract/test_controlled_server_runner.py:616`：那里 M-T1 用内联 `lambda path, recipe: None` 作 `verify_jar` 的桩，参数类型未知 ⇒ `Argument type is partially unknown`。

**修复（新提交，未 amend）**：`8b66356` 落 `codex/minekin-m-t1-multi-probe`——`ruff format .` 重排 2 文件（+6/-7，唯一实质是一处 `initial_block` 三元式收回一行），桩改成带注解的内嵌 `def skips_the_jar_pin(path: Path, recipe: _Recipe) -> None`。**无行为改动**。合入主干为 `d1ba27e`（真实 merge-base 是 `5ec0500`，评审过 merge diff 恰那 2 文件），push 后 `git ls-remote origin refs/heads/main` = **`d1ba27e61e9ad7bf5ba9c91e8c19327aba433485`**。CI：`882`（`8b66356`）与 `883`（`d1ba27e`）均 `completed/**success**` ⇒ 主干复绿。M-T1 的字节因此再动了一次，格式后的 `tools/run_controlled_server.py` sha256 是 `311ecf6a34875ed29faad215c8de87ccd817cc6d90e2ff6507e2555f3e4be820`（§2.29 里的 `263ce104…` 是格式前那一份，保留不 rewrite）。

**在含修复的主干字节上把 §2.30 那格往后推一格里**：`docker run --rm -v minekin-runner-data:/data:ro -v C:/Users/…/minekin-wt-integration:/src:ro … python /src/tools/report_promotion.py --data-root /data` ⇒ rc=**1**、stdout 103,921 字节、`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ 与 §2.19/§2.30 同值，M-T1 的两笔（`5ec0500` + `8b66356`）都未移动门载荷。全程 `:ro`，未挂任何 lane 的活体树，E 的写窗未占。

**本地按 `ci.yml` 逐项复量的全套（各自单独一步读 rc）**：`ruff format --check .` rc=0（`365 files already formatted`）、`ruff check .` rc=0、`pyright` rc=0（`0 errors`）、`pytest tests/contract/test_controlled_server_runner.py -q` rc=0（28 passed）、`check_boundaries` rc=0、`check_case_assertions` rc=0（`150 registered`）、`tools/verify_fixture_digests` rc=0、`check_workflow_pins` rc=0、全量 `pytest -q` rc=0（`2645 passed, 3 skipped in 284.61s`）、`git diff --check` rc=0。中途一次 `digest_rc=2` 是 M 把脚本路径记成了 `scripts/verify_fixture_digests.py`（实在 `tools/`），属读路径错、不是门失败，按 `ci.yml` 现读后重跑为 0。

**方法（这一条才是本轮真正的产出）**：以后 M 落地前先 `sed` 现读 `ci.yml` 的 `- run:` 清单并逐道跑，commit message 只写那一份清单上的 rc；「跑了几道常见的门」不等于「CI 的门跑全了」。同一条已写进本轮给 H1k 续跑的验收里（明列 `ruff format --check` 与 `pyright`），避免 lane 交上来一笔同样红在主干上的合入。

**现场与四态**：lane 树本轮 21:54 只读复量仍是 `29c5187` + 三处脏（`domain.sh` +169 / `test_runner_scripts.py` +953 / 未跟踪验证记录），最后写点是 21:35 的 `.tmp/h1k-recheck/`、`docker ps` 已空 ⇒ 判上一段会话已停，M 按「先确认在飞会话已停再派接手」这条硬前置派了续跑会话**收口 §2.22 并自己 push**（M 不代提交、不进其树）。已合主干＝M-T1 的修复两笔（`5ec0500`+`8b66356` → `d1ba27e`，CI 绿）；仅在分支＝H1k（在跑收口）；真实封证＝**0**（LAN 第二客户端在受控专服形状下的同 run 封证一格未动）；未验证＝lane ③ 的两轮活体、② 的大套件逐格红、CE 三组破桩（M 未复量），以及 H1m/V5′ 全卡。未连接用户远程服；未改判据/cases/registry/`mandatory`；失败材料（红 run 清单在 `.tmp/m-r50-ci.json`、`.tmp/m-r49-jobs.json`，各 `.tmp/g-*.log`）未删未覆盖。

## §2.32 补正 §2.31 的「全套」：CI 侧逐步读数其实拿得到，而 M 本地那套仍漏了三道（第五十轮后半，2026-09-27 22:10 +0800）

§2.31 有两处要说得更准，这里以新的一笔补上，原文不 rewrite。

**其一：CI 的逐步结论不必靠浏览器。** §2.31 写「jobs 端点对未认证请求仍 404」——那 404 是 M 自己用了错的 run id。按 `actions/runs?per_page=9` 返回项里的真实 `id` 请求 `https://api.github.com/repos/printlndarling/minekin/actions/runs/<id>/jobs` 得到 **http=200**，`jobs[].steps[]` 就是逐步结论。材料已存在（`conclusion` 的原文取法见 `reference-github-ci-access-windows` 一节，本轮把它从「引用」变成「实测可用」）。真正拿不到的仍只是**日志正文**（`…/logs` 未认证 404）。

**其二：M 本地跑的并不覆盖 `ci.yml` 的全部步骤。** 用 CI 自己的读数摆出来：

- `881`（红，`8b66ccf`）的 `python` job：step 5 `ruff check` **success**、step 6 `Run uv run ruff format --check .` **failure**、step 7 `pyright` 及其后全部 **skipped**。⇒ CI 侧只证到 format 这一道；`pyright` 的红是 M 本地 `rc=1`（3 errors，`:616` 的内联 `lambda`）实测的，它的绿由 `883` step 7 **success** 证。两侧合起来才是这两道门的完整证据，任一单独引用都不足。
- `883`（绿，`d1ba27e`）的 `python` job **15 步全 success**，含 M 本地从没跑过的 step 13 `uv build --wheel`、step 14 `check_wheel_boundary.py dist/*.whl`、step 15 `minekin --help` ⇒ §2.31 那句「全套按 `ci.yml` 现读逐项复量」在**清单意义上仍不完整**（现读了清单却只跑了 10/13 道）。这三道已在主干字节上补跑：`build_rc=0`、`wheel_rc=0`（`Wheel oracle boundary: OK dist\minekin_core-0.0.0-py3-none-any.whl`）、`help_rc=0`（`usage: minekin [-h] {init,doctor,bundle,launch-plan,session,server,evidence,replay} …`）。

**因此把口径钉成一句可执行的话**：M 的门禁清单 = `.github/workflows/ci.yml` 里 `python` job 的**全部** `- run:` 步骤（现读到，不背），加上 `uv sync --locked --dev` 之外的所有道；对 lane 的派工同样把这三道列进去。

## §2.33 H1k 已合主干（第五十轮，2026-09-27 22:10 +0800，M 从真实 merge-base 独立复审后合入并推远端）

**lane 的收口（它自己提交、自己 push，M 未代做）**：分支 `codex/minekin-v1201-joiner-on-controlled-server` 首推，远端 = `84648c0f718985c12de3b49697c229f999b0b7d1`，三笔 `b0c816c`（harness：第七具名拒止 + 目标读法 + 等待支）/`727fe1c`/`84648c0`（验证记录 §11–§12）。lane 树工作区现已干净。**M 派工时把 `ruff format --check` 与 `pyright` 明写进验收**（§2.31 的教训直接用上了），lane 交回的退出码含这两道各自 0。

**真实 merge-base 与改面**：`git merge-base origin/main origin/<lane>` = **`29c5187`**（M 施工支那两笔不在 lane 的祖先里，两侧自 `29c5187` 分叉）；merge diff 恰 **3 文件 `+1820/-4`**：`test-orchestrator/runner/domain.sh` +169、`tests/contract/test_runner_scripts.py` +953、`docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md` +702。`--no-ff` 合入为 **`a452e84`**，push 后 `git ls-remote origin refs/heads/main` = `a452e8497cc17f84c593de2a896294bcada9a6a3`。

**M 侧独立复审的落点（读 lane 字节本身，不读它的结论）**：
1. **默认关闭是真关闭**：`join_on_controlled_server="${MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER:-}"` + `case` 只对 `1|true` 置位、坏值 `exit 2`（不是静默忽略）。
2. **七条具名拒止在任何落盘之前**：guard 块位于 `--server-profile` 已扫过、服务端目录未建、Kin 未造、JVM 未起之处；七条依次是 joiner 缺席 / `--server-profile` 缺席 / `open_lan` / `black_hole` / `no_server` / `not_whitelisted` / **`refuse_first_snapshot`（第七条，即 §2.17 的退回项 #56）**，每条都点名是哪两个名字打架并 `exit 2`。
3. **允许面没有变宽**：`--allow-player` 只在置位时追加 `${join_username}` —— 本 run 自己启动的那个名字，也是入场 grep、账本基线、seal 的 `subject_username` 读的同一个值；白名单与 enforcement 未动；未写入任何字面玩家名。
4. **地址面是收紧不是放宽**：加入者端口/地址从**本 run 自己的** `${server_directory}/server.properties` 读（读不到即具名拒），且 `server-ip != 127.0.0.1` ⇒ `exit 2`。这条正是「不连用户远程服」在 harness 侧的机器化：这一形状的 run 不可能 dial 到容器自己没起的那台机器。
5. **oracle 归属清楚**：新等待支读 `${server_directory}/server.log`——与 `data get entity` 的应答同一份文件，故「服务端看见加入的 Kin 转向」是读数而不是客户端自述；`join_ready` 为 0 时打的是「没送任何客户端」的具名话术。
6. **契约不是装饰**：11 个新案，含 `test_the_seventh_refusal_is_not_an_always_true_claim`、`test_the_controlled_server_joiner_shape_is_not_an_always_true_claim`、`test_the_combination_stays_a_trunk_shape_while_the_new_name_is_off`（默认关闭时字节等价扩到该组合）、`test_the_joiners_target_under_the_new_name_is_this_runs_own_server_endpoint`、`test_each_wait_shape_keeps_its_own_oracle_and_the_new_one_waits_on_this_runs_log`；`run.sh` 的转发缺口是**具名登记**（`registered_gap = {JOINER_CONTROLLED_SERVER_KNOB}` + 双向集合差断言），不是隐瞒 ⇒ 归 H1l（#59）。
7. **§2.22 四件闭合**：① 第七条（上列）；② 新字节容器内契约 `85 passed`、三门 `150 registered`/digests/boundaries、静态五门含两道新列的、全量在宿 `0`；③ 私有卷 `minekin-h1k-live` 上 live-e（武装）/live-f（控制关闭）两条真 run，且**自报口径更正**：live-f 的位移含 `run-5/server.log:106 Kin2 was slain by Slime`，故纯净对是 live-e↔live-d、混淆对是 live-c↔live-f；④ 门载荷 PRE==POST==`cfa0f118…`。
8. **#58 保持为待判问题**：lane 未验证清单第 (iv) 格正是 `ONLINE_MODE=true × 新名 × 非 ADMIT-040` 那格，与 §2.26 的撤回一致，未有人偷偷「顺手关掉」。

**M 在合并树上重跑的读数（各自单步读 rc）**：`ruff check` 0、`ruff format --check` 0（`366 files already formatted`）、`pyright` 0、`check_boundaries` 0、`check_case_assertions` 0（`150 registered`）、`verify_fixture_digests` 0、`check_workflow_pins` 0、全量 `pytest -q` 0（**`2666 passed, 3 skipped in 292.44s`**，相对 `d1ba27e` 的 2645 恰多 21 格 ⇒ lane 的 11 个新案 + 参数化展开）、`uv build --wheel` 0、`check_wheel_boundary` 0、`minekin --help` 0、`git diff --check` 0；门载荷在合并树字节 + 规范卷 `:ro` 上 `report_promotion` rc=**1**、103,921 字节、`gate_payload_sha256` 仍 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ **H1k 一字未移门**，且 M 这次是自己量的而不是引用 lane 的。lane 报的「容器内全量 2 failed + 3 errors」M **未复现也未复量**（那是镜像侧 jsonschema 缺集与既有红，CI 的 `python` job 在 `uv sync --locked` 下跑，不受该缺陷影响），按未验证列报。

**队列现在能动的三格**：H1k 入干 ⇒ **H1l（#59）解除 blocked**（它要改的 `tests/contract/test_runner_scripts.py` 已不再是脏文件）、**H1m（#61）解除 blocked**（派工文本 §2.29 已写死，`domain.sh` 单 owner 空出）、V5′ 仍排在 H1l 与 H1m **之后**——§2.16 第 4 条第一格「同 run 内另一具名实体读数不变」在 H1m 入干前仍取不到，M-T1 只把 tools 侧备好。

**四态**：已合主干＝H1k（`a452e84`，CI 待读）+ M-T1 的修复两笔；仅在分支＝无（lane 已 push 并入干）；**真实封证仍为 0**（LAN 第二客户端在受控专服形状下的同 run 封证未动，私有卷 live-c/d/e/f 全部按 lane 自己的口径「不是封证」计）；未验证＝lane 自报 5 格（专用 `No entity was found` 对照 run、同 run 内主持有者读数不变、`rc=14/BRIDGE_LOST` 是否落在 PASS 判据内属 V5′/M-C1、#58 那格、容器 2 红的成因）+ M 未复量的 lane 活体两跑与 CE 三组 + `a452e84` 的 CI 结论。规范卷对 M 仍只 `:ro`；未连接用户远程服；未改判据/cases/registry/`mandatory`；材料未删（`.tmp/m-r50-jobs881.json`、`.tmp/m-r50-jobs883.json`、`.tmp/m-r50m-*.log` 在案）。

## §2.34 §2.33 那格「CI 待读」当场闭合：H1k 入干后主干绿，lane 分支自己也是绿的（第五十一轮后半，2026-09-27 22:14 +0800）

`/actions/runs?per_page=4` 单读（材料 `.tmp/m-r51-ci.json`）：

- `885` = lane 分支 `codex/minekin-v1201-joiner-on-controlled-server` @ `84648c0` ⇒ **`completed/success`**（lane 自己的字节在 CI 上就是过的，包括 §2.31 漏跑过的那两道门）。
- `886` = 主干合并笔 **`a452e84`** ⇒ **`completed/success`** ⇒ **H1k 入干没有把主干弄红**，第五十轮那五次红的教训在这张卡上闭合（派工时把 `ruff format --check` 与 `pyright` 明列进验收的直接效果）。
- `884` = `4df1b2f`（§2.31 那笔文档）⇒ `completed/success`。
- `887` = `ac1d7fb`（本轮 §2.32/§2.33 文档笔）在 22:14 时点 `in_progress` ⇒ **本笔不作绿读数**，接手会话须重读。

job 级 `python`/`protocol`/`bridge-static` 三支对 `886` 全 `success`；步骤级读数按 §2.32 的姿势可复算（`/actions/runs/36324944629/jobs` ⇒ http=200），本轮不重复挂一遍。**四态增量**：`a452e84` 由「已合主干、CI 待读」升为「已合主干、CI 绿」；真实封证仍 **0**（这条路的封证是 E7 的活，H1k 只把形状与守卫接上）；`run.sh` 转发那一格由 H1l 在飞，H1m 排其后。

## §2.35 M 的在飞判据被当场证否：靠 mtime + `docker ps` 判「lane 已停」不够（第五十一轮后半，2026-09-27 22:15 +0800，M 主控自报）

**发生了什么**：M 在 21:54 只读复量 lane 树（最后写点 21:35 的 `.tmp/h1k-recheck/`、`docker ps` 空、HEAD 仍 `29c5187`）后判「上一段会话已在轮次上限处停手」，据此在 21:55 派了续跑会话去收口 §2.22。**这个判定是错的**：原会话还活着，并在 **21:59:20 / 21:59:37 / 22:01:31** 连落 `b0c816c`、`727fe1c`、`84648c0` 三笔并于 22:01 自己 push 了分支。M 派的会话在 22:06 复量时发现「HEAD 已移动、远端 ref 已存在、记录多出 §11/§12」⇒ **按令停手转只读**，未写文档、未提交、未 push。

**为什么这次没造成损失（逐条核过，不是安慰话）**：
1. 派的会话动手前做了哈希快照备份（`.tmp/h1k-final/*.pre-GATE`，三文件），且发现字节移动后没有覆盖任何 lane 字节；
2. lane 自 push 的字节与 M 21:17/21:54 快照一致（`domain.sh` blob==盘==`e1d8dbb9…`，`.py` blob `e059ed58…` == 盘上 `tr -d '\r'`）⇒ 记录只增不减；
3. M 的合入复审用的是**远端 ref 的 `84648c0`**（`git fetch` 后 `merge-base` 实测 `29c5187`），不是任何本地脏态 ⇒ `a452e84` 合的就是 lane 自己交付的那三笔。

**但这是同一族缺陷第二次**（§2.28 已申报过一次「同树两写者约 6 分钟」，当时归因于压缩前会话还活着）。两次的共同点：**M 用的是间接证据推断会话生命周期**。因此把口径换掉：

- **可判停的正面信号只有一个**：该会话自己的收尾回报/完成通知（它说了「已提交并 push、工作树干净」或「停手」），或远端 ref 出现它自己的提交。二者皆无 ⇒ 视为**在飞**，不派第二个写者。
- `mtime` 静默、`docker ps` 为空、HEAD 未动，都**不是**停止的证据：一次容器活体之间、一段长思考之内、一轮工具调用之后都可能出现几分钟到十几分钟的写入空窗（本轮实测 21:35→21:59 是 24 分钟空窗）。
- 派工文本里那句「动手前先复量现场，若字节仍在移动则停手转只读」**有效且要保留**：本轮正是它让第二个写者自己退成只读，把双写者的损害面缩到零。

**顺手得到的三格独立读数**（派的会话转只读后跑完的，全部是它自己量的）：
- lane 最终字节上的 CI 全 12 道各自 rc=0：`ruff check` 0、`ruff format --check` 0（`365 files already formatted`）、`pyright` 0（`0 errors`）、全量 `pytest` 0（`2663 passed, 2 skipped in 309s`）、boundaries/cases（`150 registered`）/digests/pins 各 0、`git diff --check` 0、`uv build --wheel` 0、`check_wheel_boundary` 0、`minekin --help` 0；容器门 `tests/contract/test_runner_scripts.py` `85 passed` rc=0，宿主同文件 parity 亦 85。
- **门载荷的第三个对照**：base `29c5187` ↔ lane `84648c0` 两遍 rc=**1**、doc 103,921 B、子集 6,051 B、`sha256 PRE==POST==cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` ⇒ 与 §2.33 的合并树读数和 §2.30 的主干读数三者同值 ⇒ 「H1k 一字未移门」现在有三份独立材料，不再依赖 lane 自报。
- 第七条拒止的绿色半边复量：区间内 `exit 2` 恰 **7** 条、四格断言在契约 `:2948/:2976/:3025/:3073/:3088`，`-k` 定向三案 3 passed；其非恒真半边由**内存副本**里种 silenced/hoisted 双反证复现（盘上破桩的 `4 failed/81 passed` 与 CE(c) `3 failed` 仍是历史读数，该会话未复破）。
- 一处 lane 文档行号小差：其 §11.1 记 `:488–:489`，实测第七条在 `:487–:490` ⇒ 不涉判据，留给 lane 下次追加节自正（M 不改 lane 的记录）。

**四态增量**：本轮 M 的派工瑕疵一处（已具名，材料在 `.tmp/h1k-final/` 与两份会话回报）；已合主干且 CI 绿的仍 `a452e84`；真实封证仍 **0**。

## §2.36 V5′ 派工文本的前置：§2.16 第 1 条的三处载体行号在主干字节上现读（第五十二轮，2026-09-27 22:19 +0800，M 主控）

§2.16 第 1 条要求「**H1k 入干后**由 M 当场重读 `domain.sh`」，把三处行号写进 V5′ 的派工文本，量不到就不派。H1k 已在 `a452e84` 入干 ⇒ 这一格的门今天开了，所以在 H1l/H1m 之外并行做掉。

**测量对象（主干字节，逐字复现）**：`6429725703d044c2315ae255f306e53586199be3` 的 `test-orchestrator/runner/domain.sh` ⇒ blob `1254e6fb9fdcb93ecf615ca8cf3a28c72ae663a2`、sha256 `e1d8dbb98d5f760db5c2583f001941e48485e0240f61b8061120504c36714015`、156,467 字节。盘上工作树同摘要（`sha256sum` 直接量到同一串），即该文件在主干是 LF 钉住的，行号可对盘上读。

1. **「加入者目标地址/端口来源行」= `:1089–:1119`**（`# --- joiner-controlled-server-target ---` 区）。逐点：`:1089` 默认仍取 `joiner_target_port="${lan_port}"`；`:1090` 新名的 `if`；`:1091` 源文件为本 run 自己的 `${server_directory}/server.properties`；`:1096/:1097` 分别 `sed -n 's/^server-ip=//p'`、`s/^server-port=//p` 并 `tail -1`；`:1102–:1108` 端口不可读/非数字 ⇒ 具名 `exit 2`；`:1109–:1113` `server-ip != 127.0.0.1` ⇒ 具名 `exit 2`；`:1114` 才把 `${controlled_server_port}` 赋给目的地；`:1115–:1116` 打印「dials the controlled server this run started at `%s:%s`, read from `%s`」；`:1119` 起 python 把该端口铸进 `/tmp/domain-join-profile.json`。⇒ **V5′ 的目的地判据（§2.16 第 1 条要的那处）有单一承载，且不问任何非回环地址。**
2. **「就绪等待落点行」= 函数 `:1472`，两个落点 `:1967`（LAN 形状，读 `${latest}`）与 `:1988`（新形状，读 `${server_directory}/server.log`）**，新区间为 `:1973–:1992`，其中 `:1985–:1986` 先打印目的地日志路径、`:1990` 是 `join_ready=0` 时的「备好了但没送出」具名行。⇒ 两种形状的 oracle 各自独立，V5′ 若走专服形状就只能引 `:1988` 那条。
3. **「`--probe-player` 生效行」= `:794`（全仓唯一铸名点，仍是单值 `${probe:-${player}}`）+ `:795–:797`（`--use-target`）+ `:917`（拼进 `:908` 那条 `python /src/tools/run_controlled_server.py` 调用，同一命令还带 `:920` 的 `--keep-running`）**。M-T1 已把 tools 侧转成可重复 `--probe-player`，**主干这处仍是单值** ⇒ §2.16 第 4 条第一格（同 run 内另一具名实体读数不变）在 H1m 入干前依然取不到，与 §2.27 的前置缺口 B 一致。

**这三处的时效（写死在派工口径里，免得下一个人沿用）**：第 1、2 处只被 `domain.sh` 的加入者区段改动，H1l 不动它们；**第 3 处正是 H1m 要改的那一行**（`:794` 由单值变两名、或新增铸名点），所以 V5′ 的派工文本必须在 **H1m 入干后**按当轮字节把第 3 处再读一遍才可引用——本轮记录只作「H1k 入干时点成立」的证据，不作 V5′ 的最终行号。§2.16 第 1 条那句「旧行号曾在 §2.13 里失效过一次」就是这条时效的来由。

**顺带量到、与 H1l/H1m 排程有关的一件**：主干 `run.sh` 的 `-e MINEKIN_DOMAIN_*` 名单实测跨 `:88–:120`，其中 **既无 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`（H1l 要加的）也无 `MINEKIN_DOMAIN_PROBE_SECOND`（H1m 要加的）**，两卡都写这同一段 ⇒ §2.29 那句「H1m 严格排在 H1l 之后」在字节面上成立，不是保守排程。契约侧的登记缺口在 `tests/contract/test_runner_scripts.py:148–:157`（`registered_gap = {JOINER_CONTROLLED_SERVER_KNOB}` 与「转发了它就删登记、别删断言」那三条），名字常量在 `:1806`。

**四态增量**：本轮零封证、零改判据/registry/门禁，主干只动这一节文档；真实封证仍 **0**（LAN 第二客户端在受控专服形状下的同 run 封证未动）；已合主干且 CI 绿的最近一笔仍 `a452e84`（`ac1d7fb` 14:12Z 已 `completed/success`，`a1c9f45`/`6429725` 14:14/14:15Z 起跑、本笔读为 `in_progress` ⇒ 不作绿，接手会话须重读）。H1l 仍在飞：lane 树 `../minekin-wt-h1k` 的 `run.sh`、`tests/contract/test_runner_scripts.py` 两文件未提交、分支 HEAD 仍 `ac1d7fb`——按 §2.35 的口径，这只算 22:17 的**时点读数**，M 不据此判它停过、不进它的工作面、不代提交。规范卷 `minekin-runner-data` 本轮未挂。

## §2.37 #58 那一格在主干字节上分裂成两格：`--enable-status` 的谓词决定哪一半才有起服前的具名拒止（第五十二轮后半，2026-09-27 22:24 +0800，M 主控）

**为什么现在做**：H1l 在飞、引擎窗不抢，#58 是队列里唯一不依赖真跑就能推进的待判问题。它从 §2.25（M 判「缺第八条具名拒止」）经 §2.26（M 撤回，改说「早有具名承担者 `AUTH_MODE_MISMATCH`」）走到这里——**本轮按当轮字节逐字读，两笔各自说对了一半，合起来的正确句子第一次写下来。**

**三条字节证据**（`4a2778f` 的主干）：

1. `tools/run_controlled_server.py:238–:272` 的 `status_switch_refusal(profile, *, online_mode, enable_status)` 第一句是 `:254  if not enable_status: return None` ⇒ 那条点名 `(AUTH_MODE_MISMATCH)` 的具名拒止（`:264–:271`）**只在被要求开状态端口时才成立**；文案本身说得很清楚，它拒的是「一台要求会话校验的服务器还对外应答 status ping」。
2. `test-orchestrator/runner/domain.sh:904–:907`：`status_args=()` 为空，只有 `[ -n "${auto_bundle}" ]` 才 `status_args=(--enable-status)` ⇒ 同一个 `--online-mode` 是否撞上一条落盘前的拒止，就分在这一行。`:883–:886` 仍按 `MINEKIN_DOMAIN_ONLINE_MODE` 铸 `true/false/空` 三式，`:914` 把它拼进同一条启动调用。
3. 判据侧另有承担者，但层级不同：`tools/assert_case_evidence.py:195` 定义 `AUTH_MODE_MISMATCH = "ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH"`，`:2700–:2722` 的 `the_auth_mode_mismatch_was_classified_in_the_ledger` 要 ledger 里有一条 `phase=FAILED` **且** `reason=` 该枚举 **且** `source=BRIDGE` **且** `trust_class=BRIDGE_FILTERED` 的 `SessionInterrupted`，否则报 `NO_CLASSIFIED_AUTH_MODE_MISMATCH`；`:2724–` 的第二条再要求「拒止之后只有一份策略、一个进程」。**它读的是加入者客户端 ledger 里已经发生过的分类，不是起服之前的拒止。**

**于是那一格分成两格**：

- **(甲) `ONLINE_MODE=true × JOIN_ON_CONTROLLED_SERVER=1 × --auto-bundle`** ⇒ `run_controlled_server.py:264–:271` 在 run 目录出现之前 `rc=2` 具名收口（H2 收卡时 M 侧容器复量已直接量到过这一式：`--enable-status --online-mode` ⇒ rc=2 具名 `AUTH_MODE_MISMATCH` 且 run 目录不存在）。这一格 **不需要第八条 guard**，§2.26 的撤回在它是站得住的。
- **(乙) 同一对旋钮的非 auto 形状**（正是 H1k 的 live-c…f 那类 run 的形状）⇒ **没有**任何起服前的具名拒止：服务端照写 `online-mode=true`，加入者以 `auth_mode: offline` 打它，按契约这一式「必须**不**被绕开」；编排侧看到的是加入者永不到达 ⇒ 等待超时／`rc=14`。§2.25 说的「guard 未列该对」在这格是字面真的；§2.26 说的「有具名承担者」也真——但承担者在 **ledger 判定层**（第 3 条那两式），不在 guard 层。当时那句撤回没错，只是它把「有人在判」写成了像是「有人在门口拒」。

**剩下唯一的未知，以及它归谁**：(乙) 那格真跑一次会留下什么——加入者 ledger 是否真落 `ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH`（+「一次策略、一个进程」），编排侧又停在哪一层——按构造只能由一次真跑回答（420s 等待预算）。**不开新卡**：#58 的口径收窄为「只问 (乙) 的实测」，且排在 H1m 入干之后的引擎窗，只用 M 的私有数据根、不挂规范卷、不封存。

**本轮明确不做的动作**（写给下一个读到这节的人）：不因 (乙) 缺门口拒止就去补第八条 guard、不改 `MINEKIN_DOMAIN_*` 的默认、不动判据/registry/`mandatory`；让 (乙)「变可判」的唯一快法是给受控加入者一条在线凭据路径，那是硬禁，不在任何卡的面上。

**四态增量**：零封证、零改判据，主干只动本节与账目；真实封证仍 **0**；`4d04f3b`/`4a2778f` 的 CI 绿读数仍待重读（`a1c9f45`、`6429725` 14:17Z 读为 `in_progress`）；H1l 在飞（22:16 时点两文件未提交），M 未进其工作面。规范卷 `minekin-runner-data` 本轮未挂；未连接用户远程服；未放宽认证/地址/lease/判据；旧材料与失败材料一字未删。

## §2.38 H1l 的 M 侧独立复审与合入：转发那一格现在由 M 亲手量到过，但 lane 的门表有两行抄错了自己的日志（第五十三轮，2026-09-27 22:41 +0800，M 主控）

**合入事实**：真实 merge-base 实测 `ac1d7fb`（= lane 分支自己声明的起点，也是 H1k 之后远端 `main`）；lane 侧两笔 = `c345c0f`（字节）+ `1ce9dc0`（记录），远端分支 `codex/minekin-h1l-forward-join-name` 头即 `1ce9dc0`；M 以 `--no-ff` 合入成本地合并笔 **`d95e59d59d1ea3fa807f78cb539b046dc6c04dfd`**（parents `16e0df8` + `1ce9dc0`）。**lane 字节零改动**：M 未进它的工作面、未替它提交、未 rebase 它的分支，合的就是它自己 push 的那两笔。

**改面复审（逐条核过）**：`git diff --stat ac1d7fb c345c0f` ⇒ 恰 **2 文件**（`test-orchestrator/runner/run.sh` +10/−1、`tests/contract/test_runner_scripts.py` +25/−26），加记录 1 支。`domain.sh` 在合并树上与主干**同一 blob**（`1254e6fb9fdcb93ecf615ca8cf3a28c72ae663a2`）、盘上 sha256 `e1d8dbb9…36714015` ⇒ H1l 没碰加入者区段，§2.36 的前两处行号仍然有效；`tools/**`、`src/**`、fixtures、registry、`mandatory`、封存 schema 全 0 行。语义两格也对得上：`run.sh:120–:129` 落的是**裸** `-e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`（同 H1j 那四名的写法，不铸任何默认值），契约侧按登记注释自己写的口径处理——**删登记、不删断言**，`registered_gap` 那一条整体换成「逐一要求已转发」，`read - delivered == set()` 与 `delivered - read == set()` 双向集合差保留 ⇒ H1k 留下的那格登记现在是零，且退回成缺口的方向有断言守着。

**M 自己量到的动态转发证据（不再依赖 lane 的日志）**：在合并树字节上直接跑仓库的 `run.sh`（宿主 Git Bash，`MINEKIN_RUNNER_DATA=minekin-m-r45-live` 即 M 的私有卷），两式互为对照，材料 `.tmp/m-r52-live-forward-proof.log`：
- 设 `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1` 且不设加入者 ⇒ **`rc=2`**，容器打出第七条之前的第一条具名拒止 `domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER names where a joining client goes and this run has none (MINEKIN_DOMAIN_JOIN is unset); refused rather than carried as a knob that does nothing`。这行只可能在容器内的 `domain.sh` 把该名读成「已要求」时打印 ⇒ 经真实 wrapper 的转发是活的。
- 不设该名（其余同）⇒ **不出现**上面那行，改在更后面一处落下 `domain: this run cannot name its ledger (found 2), so nothing here can be attributed`，`rc=2`（这一式的 rc 来自 M 私有卷里已有 2 份台账，与本卡无关，如实记）。⇒ 读数是**判别性**的，不是恒真。
- 两式都在任何 JVM、任何 run 目录之前返回，未起服、未起客户端、未写台账；**这两条是私有卷活体读数，不是 sealed bundle**，规范卷 `minekin-runner-data` 在整轮里只出现在门载荷那一条 `:ro` 挂载。

**M 侧门禁重跑（合并树，13 道逐道单步、先读 rc 再落表；这次把日志存下来了）**：`.tmp/m-r52-gates.log` ⇒ `ruff check` 0、`ruff format --check` 0（`367 files already formatted`）、`pyright` 0（`0 errors`）、`check_boundaries` 0、`check_case_assertions` 0（**`150 registered`**）、`verify_fixture_digests` 0、`check_workflow_pins` 0、`git diff --check` 0、`bash -n run.sh` 0、`bash -n domain.sh` 0、`uv build --wheel` 0、`check_wheel_boundary` 0、`minekin --help` 0；全量 `pytest -q` ⇒ **`2666 passed, 3 skipped in 292.55s`** rc=0（`.tmp/gate-merge-pytest.out`，三处 skip 逐条具名：`tests/unit/test_orphans.py:686`、`tests/unit/test_silent_listener.py:123`、`tests/unit/test_tested_provenance.py:354` 因本树未构建 `bridge-1201` 产物 ⇒ 与 lane 树的 `2667 passed, 2 skipped` 差一格是**该树有桥产物**，总数同为 2669）。契约 parity：容器内 `tests/contract/test_runner_scripts.py` **85 passed** rc=0、宿主同文件 **85 passed** rc=0。门载荷：容器 + 规范卷 `:ro` ⇒ `report_promotion` **rc=1**（按构造 blocked）、整文档 103,921 字节、`{work_packages, overall}` 子集 sha256 **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**，同一姿势两遍（`m-r52-payload.json`、`m-r52-payload2.json`）同值 ⇒ **「H1l 未移门」从 lane 自报升级为 M 自量**，与 §2.30/§2.33/§2.35 三个读数同串。

> 一处 M 侧自己的流程缺陷要具名：本笔前半段的门跑输出了屏幕但未落盘（`.tmp/gate-merge.out` 是 **0 字节**），而 §2.35 那轮的教训正是「读数要留材料」。因此上面的 13 道是**第二次跑**、且先落 `.tmp/m-r52-gates.log` 再写进本节，不是引用那次没留存的输出。全量 pytest 与门载荷两条各有一份独立留存日志（`.tmp/gate-merge-pytest.out`、`.tmp/m-r52-payload*.json`）。

**退回项（M 不改 lane 的记录，留它下一笔追加节自正）**：H1l 交付记录 §4 那张「现读 `ci.yml` 清单、逐道真实输出末行」的表里，有**两行的末行与它自己留存的日志不符**：
1. `pytest 全量` 记 `2737 passed, 1 warning in 417.05s`，而它的 `.tmp/h1l/gate-pytest-full.log` 末行是 `2667 passed, 2 skipped in 311.90s (0:05:11)`；lane 树 `.tmp/` 里**没有任何** pytest 日志含 `2737`（`grep -rl 2737 .tmp/` 的命中全是 `uv.lock`、`verification-metadata.xml`、asset index 里的字节片段），也没有四位数 `passed` 的第二处读数。
2. `ruff format` 记 `366 files already formatted`，而它的 `.tmp/h1l/gate-ruff-format-final.log` 末行是 `367 files already formatted`（M 在合并树量到的也是 367）。

**这两行的性质要说清**：`rc` 列与「每道都过」的结论不受影响（M 在合并树上独立重跑，13 道全 0、契约容器/宿主各 85、门载荷同串），错的是**抄进表里的读数文本**。但这张表存在的意义就是「读数可复算」——末行与实际日志不一致，等于该表的证据价值落回「依赖作者的手」。所以按 §2.35 的同一口径退回，不代改：lane 在下一次追加节里把这两行换成它自己日志的末行（或重跑一遍再抄），并说明 `2737/1 warning/417.05s` 这一串从哪来；若指不出来源，就删掉该格改写留存日志的值。

**观察项（不退回、本轮不派工）**：契约的 `delivered` 正则 `-e\s+(MINEKIN_DOMAIN_[A-Z_]+)` 与逐名 substring 断言都看不见「把裸名退化成 `-e NAME="${NAME:-}"`」这一轴——lane 自己在 §3 CE(b) 里就把这件事写明了（契约在那具变异体上保持绿，靠的是 argv 层 dump 而不是契约）。同一缺陷对 H1j 那四名同样成立，且它的边界在 `config.py` 的转发名单那条主控保留决策上（此前已登记、未实施），要收就得连着「裸名单元不许铸默认值」一起加一条 argv/文本层判据 ⇒ 记为一张未开的小卡候选，排在 H1m 之后由 M 判。另一处纯文本小差：契约 docstring 里那个名字被换行拆成 `…CONTROLLED_`/`SERVER`，全文按完整名 grep 会少命中这一处（不涉判据，断言与注释另两处是完整的）。

**四态增量**：真实封证仍 **0**（LAN 第二客户端在受控专服形状下的同 run 封证未动，那是 E7 的活）；**已合主干**新增 `d95e59d`（H1l 字节，本笔随后 push 并核远端 SHA、读 CI 到 completed）；`c345c0f`/`1ce9dc0` 由「仅在分支」升为「已合主干」；仅在分支的只剩 lane 自己的 `codex/minekin-h1l-forward-join-name` ref（M 不删）。未连接用户远程服；未放宽认证/地址/lease/判据；未翻 `mandatory`/registry；旧材料与失败材料（含被退回的两行所在文件）一字未删。H1m（#61）的派工文本已在 §2.29 写死，H1l 入干即开该窗；V5′ 的派工仍须按 H1m 入干后的字节重读 §2.36 第 3 处行号。

## §2.39 H1m 的载体行号在 `dcc3e24` 的主干字节上重读：§2.29 那六处里四处已随 H1k 的 +1,820 行失效，本轮第五十三轮 ⑥ 把「仍有效」写错了一次（第五十三轮后半，2026-09-27 22:46 +0800，M 主控）

**为什么单独一节**：§2.29 写 H1m 的派工文本时给的是「主干字节现读」的六处行号，但它量的是 `7546ec9`——**H1k 的 `domain.sh`（+1,820 行）在那之后才入干**。本轮 ⑥ 初稿把「H1l 未动 `domain.sh`」当成「§2.29 的行号仍有效」，这是错的：H1l 确实没动它，动它的是 H1k，而我刚在 §2.38 写下「合并树 `domain.sh` 与主干同 blob」这句时手上有正确字节，却没有回头核对 §2.29 的编号。派工前按 §2.16 第 1 条的同一条规矩现读一遍，错了四处。

**六处逐条：旧 → 新（`dcc3e24` 的 `test-orchestrator/runner/domain.sh`，blob `1254e6fb9f…`、盘上 sha256 `e1d8dbb9…`/156,467 B，行号可对盘上读）**

| 载体 | §2.29 记 | 现读 | 位移 |
| --- | --- | --- | --- |
| `probe="${MINEKIN_DOMAIN_PROBE:-}"` | `:27` | **`:27`** | 未动（在读旋钮区之上） |
| `use_target="${MINEKIN_DOMAIN_USE_TARGET:-}"` | `:133` | **`:133`** | 未动 |
| `probe_seconds="${MINEKIN_DOMAIN_PROBE_SECONDS:-5}"` | `:171` | **`:194`** | +23 |
| 唯一铸名点 `probe_args=(--probe-player "${probe:-${player}}" --probe-every-seconds "${probe_seconds}")` | `:715` | **`:794`** | +79 |
| `--use-target` 追加分支 `if [[ -n "${use_target}" ]]; then probe_args+=(--use-target); fi` | `:716–:717` | **`:795–:796`** | +79 |
| `"${probe_args[@]}"` 交给 `run_controlled_server.py` 的调用位 | `:821` | **`:917`** | +96 |

**顺带钉住的两件（H1m 会直接踩到）**：
1. 契约把铸名串按字面钉住的位置是 `tests/contract/test_runner_scripts.py:1210`（`'probe_args=(--probe-player "${probe:-${player}}" '`），其读数说明在 `:1188` ⇒ 「默认关闭时 `probe_args` 与今日逐字节相等」这一格要在**那一行**加断言，而不是另起一处新读法。
2. `run.sh` 的 `-e MINEKIN_DOMAIN_*` 名单现在跨 **`:88–:129`**（H1l 把新名落在末尾 `:129`），`MINEKIN_DOMAIN_PROBE_SECOND` 要接在 `:129` 之后并同形采用**裸声明**；契约侧 `read`/`delivered` 的双向集合差（§2.38 复审过的那三条）会同时管住这个新名，无需再登记缺口。
3. guard 落点供它二选一（口径不变：**落盘前、`rc=2`、具名**，且不许拿下游 tools 侧那句 `--use-target …` 兜底当自己的判据）：加入者守卫区是 `:461–:492`（含逐条 `exit 2` 于 `:465/:469/:473/:477/:481/:485/:489`，该区被契约按标记整段抽出 ⇒ 往那里加名字要连带扩契约区间），或直接落在铸名点 `:789–:796` 之前（此处已在任何 run 目录、任何 JVM 之前，`server_directory=""` 到 `:821` 之后才铸）。

**这条更正的账目**：本轮第五十三轮 ⑥ 的原句已在同一笔里就地改正并指向本节（按「只改现在时断言、历史读数保留」的规矩，§2.29 那一节一字不动，它对自己的时间点是如实的）。真实封证仍 **0**；门载荷未动（本笔改面恰 2 个 docs 文件）。

## §2.40 CI 欠账一次闭合、H1l 的合并笔读到绿；H1m 已按 §2.39 的行号派到独占新树（第五十三轮收尾，2026-09-27 22:50 +0800，M 主控）

**CI 一次 REST 读**（`/actions/runs?per_page=10`，材料 `.tmp/m-r53-ci.json` 与 `.tmp/m-r53-ci2.json`）：`887`＝`ac1d7fb`、`888`＝`a1c9f45`、`889`＝`6429725`、`890`＝`4d04f3b`、`891`＝`4a2778f`、`892`＝`16e0df8` **全部 `completed/success`** ⇒ §2.34/§2.36/§2.37 三处逐笔欠的读数一次闭合，第五十二轮那句「那四道由 push 后的 CI 全量执行，绿读数待重读」到此兑现。lane 分支头 `893`＝`1ce9dc0` 亦 `completed/success`（CI 对 branch push 同样触发 ⇒ lane 自己的字节在 CI 上过的这一格，从它的自报变成 M 自读）。**H1l 的合入：`894`＝`dcc3e24` `completed/success`** ⇒ 合并笔 `d95e59d`（它的父提交）连同 M 的复审记录笔一起被 CI 判绿 ⇒ **H1l 入干没有把主干弄红**，「已合主干且 CI 绿」的最近一笔从 `a452e84` 前进到 `dcc3e24`。`895`＝`dc0067c`（§2.39 的更正笔）在 22:49:54 时点为 `in_progress` ⇒ 不作绿，留给接手会话重读（`in_progress` 既不作绿也不作红）。

**H1m 的派工（已发，独占面已隔离）**：M 为主干之外新建工作树 `C:\Users\darling\Documents\agent_work\minekin-wt-h1m`，分支 `codex/minekin-h1m-second-probe-target`，起点 = 当时的远端 `main`（`dc0067cdcbc962266750c5ccbaa5535a0972945d`），与上一张卡的交付树 `../minekin-wt-h1k`（停在 `1ce9dc0`）零重叠。派工文本按 §2.29 的接口 + §2.39 的更正行号写死：`MINEKIN_DOMAIN_PROBE_SECOND` 默认关闭、未设时 `probe_args` 与今日逐字节相等、设了就在 `domain.sh:794` 之后追加第二个 `--probe-player <名>`；两条落盘前具名早退（同名、`USE_TARGET × 第二名`，不许拿 tools 侧兜底顶替）；新名以**裸声明**接进 `run.sh:88–:129` 名单末尾；契约的默认关闭等值断言加在既有字面钉处 `tests/contract/test_runner_scripts.py:1210`，且**不得新增 `registered_gap`**。验收要求里点名了三件本族最容易漏的：一次经真实 `run.sh` 的两名都被问过的形状读（用 lane 自己的私有卷 `minekin-h1m-live`）、三枚各红在该红案上的反证（破桩前备份 + 记 sha256，禁用 `checkout --`/`restore`/`reset`/`stash`）、门表每一格必须逐字取自自己落盘的 `.tmp/h1m/gate-*.log` 末行（§2.38 那条退回项就是给它看的）。门载荷按期望 PRE==POST==`cfa0f118…`（本卡不注册 case）。

**四态增量**：真实封证仍 **0**（LAN 第二客户端在受控专服形状下的同 run 封证未动，那是 E7 的活）；已合主干且 CI 绿 = `dcc3e24`（含 H1l 的 `d95e59d`）；仅在分支 = lane 的 `codex/minekin-h1l-forward-join-name` ref（M 不删）与 H1m 的新分支（刚建，尚无提交）；未验证 = §2.39 那笔的 CI（`895` 时点 `in_progress`）、H1m 全卡、V5′ 全卡、#58 的 (乙) 格。排序不变：**H1i 严格排在 H1m 之后**（同一 `domain.sh` 独占面），V5′ 派工前须按 H1m 入干后的字节重读 §2.36 第 3 处（现为 `:794/:795–:796/:917`）。本轮 M 侧材料未删（`.tmp/m-r52-gates.log`、`.tmp/m-r52-container.log`、`.tmp/m-r52-contract.log`、`.tmp/m-r52-contract-host.log`、`.tmp/gate-merge-pytest.out`、`.tmp/m-r52-payload*.json`、`.tmp/m-r52-live-forward-proof.log`、`.tmp/m-r53-ci*.json`、`.tmp/gate-merge.out`（0 字节，M 自身缺陷留证））；规范卷对 M 仍只 `:ro`；未连接用户远程服（未读 `.tmp/local-test-server.txt`）；未放宽认证/地址/lease/判据；未翻 `mandatory`/registry。

## §2.41 V5′ 判据落在字节上的映射：专服形状里两个客户端同在一个世界，所以 §2.16 第 4 条第一格自 H1m 起是**可取**的（第五十四轮，2026-09-27 22:54 +0800，M 主控；H1m 在飞，本节只读仓库字节、不挂引擎）

派工前把 §2.16 那七条逐条钉到 `af514d1` 的主干字节上（`domain.sh` blob `1254e6fb9f…`、sha256 `e1d8dbb9…`/156,467 B）。**这一节要解决的是排程里最容易被顶替的一格**：V5′ 的判据第 4 条要求「同一 run 内主持有者的读数首末不变」，而这一格在 H1m 之前按构造读不出（`domain.sh` 只会问一个名字）——但**它究竟能不能读出来**，取决于专服形状里宿主到底进不进那个世界。逐点量过：

1. **宿主的名字与探针的默认名同出一处**：`:25` `player="${MINEKIN_USERNAME:-Kin}"` 是本 run 自己的账号名；`:794` 的唯一铸名点是 `probe_args=(--probe-player "${probe:-${player}}" …)` ⇒ `MINEKIN_DOMAIN_PROBE` 未设时，被问的第一个名字**就是宿主自己的名字**，且默认每个专服 run 都带这个问句（`:786–:793` 的注释写明「asking is a default」）。
2. **宿主真的进了那个专服世界**：宿主会话的启动行 `:1692–:1695` 是 `python -m minekin_core "$@" "${lan_args[@]}"`，而 `:1633–:1635` 说明 `lan_args` 只在 `MINEKIN_DOMAIN_OPEN_LAN` 时才带 `--open-lan` ⇒ 专服形状下宿主拿到的正是它自己的 `--server-profile`（`:413` 从同一串参数里扫出来）。这条不是推断：E6 封成的 `V1201-020` seq4 就是「本地专服 + 单客户端」的 sealed bundle，那个客户端只能经由 `--server-profile` 进服。
3. **加入者进的是同一个世界**：`:684` 让加入者 `session start` 带 `--server-profile /tmp/domain-join-profile.json`（该文件由 `:1119` 起按本 run 自己的 `server.properties` 铸出，端口在 `:1114` 才定），而 H1k 写在这条支路入口的注释 `:155–:162` 逐字写着：设了这个名 ⇒「**the server that answers `data get entity` probes is the server both clients stand in**」。白名单侧同向：`:875–:877` 只在 `join_on_controlled_server_asked=1` 时把 `${join_username}` **追加**进 `allow_args`（该值默认 `:148` = `Kin2`），没有放宽任何地址、模式或人数。
4. **到达判据与读数同源**：新形状的等待支 `:1973–:1992` 读 `${server_directory}/server.log`（`:1988` 调用、`:1985–:1986` 打印路径），与 `data get entity` 的答案行是**同一份文件** ⇒ §2.16 第 2 条的「行内名归属加入者 + 首末不同」与第 3 条的 arrival 取证在同一 run 内可分读。

**于是 V5′ 的判据映射可以写死**（H1m 入干后即成立，接口由 §2.29 定）：

| §2.16 条 | 在专服形状下的取法 | 何时才可取 |
| --- | --- | --- |
| 第 2 条（首末差按加入者名读） | `MINEKIN_DOMAIN_PROBE_SECOND=${join_username}`（默认 `Kin2`）⇒ `server.log` 里行内名等于该名的读数 ≥2 条、首末至少一分量不同 | H1m 入干后 |
| 第 4 条第一格（主持有者不变） | 第一名仍走默认 `${probe:-${player}}` = 宿主 `Kin`，同一 run 内它的首末读数**必须不变** | H1m 入干后（此前按构造不可取） |
| 第 4 条第二格（控制关闭对照） | 同形状、不铸任何 `MINEKIN_DOMAIN_JOIN_*` 控制词，加入者首末不变 | 今天即可 |
| 第 5 条（归属反证） | **不再需要替代格**：本形状两个客户端同在世界，「两名都被问过」是直接读数。`MINEKIN_DOMAIN_PROBE=<不存在名>` 那格降级为**额外的非恒真对照**，不再是唯一出路 | H1m 入干后 |
| 第 3 条（PLAYABLE 与 arrival 分开） | 载体不变：`${joiner}` 账本 `PlayableEstablished` 且 `position > baseline`（`:1590–:1600` 的读法）与 `the world heard … arrive`（`:1577`）各记各的 | 今天即可 |

**这条判停要留在文档里**：§2.16 第 5 条当初写成条件句（「H1k **若**申报宿主不同进该专服世界」）是因为写它时（第四十一轮）专服形状还不存在。H1k 落地后字节给的是反面 ⇒ 该条件不成立，替代格降级为附加对照。**这不是改判据**（第 4/5 条要求的读数一个都没少，只是取法从「只能间接」变成「可以直读」），按本节具名，不静默替换。

**时效**：本节的 `:794`、`:1973–:1992`、`:1692–:1695` 三处行号在 H1m 入干后必须由 M 当场重读一遍才可写进 V5′ 派工文本——H1m 正是改 `:794` 那一段的卡（§2.39 的教训已在案，不再重复一遍错法）。**四态**：真实封证仍 **0**；已合主干且 CI 绿 = `dcc3e24`（`895`=`dc0067c` 22:51 读为 `completed/success`，`896`=`af514d1` 时点 `in_progress` 不作绿）；仅在分支 = H1m（在飞，尚无提交）与 lane 的 `codex/minekin-h1l-forward-join-name` ref；未验证 = V5′ 全卡、H1i 全卡、#58 的 (乙) 格。本轮零容器活体（不与 H1m 抢引擎）、规范卷未挂；未连接用户远程服；未放宽认证/地址/lease/判据；未翻 `mandatory`/registry；材料未删。

## §2.42 V5′ 的派工草案已在 H1k 的活体脚本上写死（三式形状 + M 自己的私有卷），并具名判停「不拆卡提前跑今天可得的格」（第五十四轮，2026-09-27 23:00 +0800，M 主控；H1m 在飞，本节不挂引擎）

**CI 一笔闭合**（`.tmp/m-r54-ci.json`，一次 REST 读）：`896`=`af514d1` **`completed/success`** ⇒ §2.41 里那格 `in_progress` 现读已闭合；`897`=`c87089d`（本节所属的 §2.41 记录笔）22:59 时点 `queued` ⇒ 不作绿，须由接手会话重读。远端 `main` 经 `git ls-remote` 现场核为 `c87089d2ddefd13e0414fc917a9e36e5c1e99ce7`，本地 `main` 同值。§2.41 入干笔 = `c87089d`（改面恰 1 个 docs 文件、`git diff --cached --check` rc=0 先读后写）。

**H1m 的在飞现场（正面信号仍为零，故不动它）**：`../minekin-wt-h1m` 分支头仍 `dc0067c`、`git status --short` 回空、`git diff --stat dc0067c..HEAD` 回空；`git ls-remote` 全仓只有 `refs/heads/main` 与 lane 的 `codex/minekin-h1l-forward-join-name`（`1ce9dc0`），**无 H1m 分支的 ref** ⇒ 按 §2.35 口径它仍在飞，M 不进它的工作面、不代提交、不派第二写者。

**为什么这一节值得在等待窗写**：V5′ 的七条判据里，真正欠的只有「同一 run 问两个具名名字」这一格，而**命令形状 H1k 已经在盘上留全了**。M 只读、不改 lane 材料：`../minekin-wt-h1k/.tmp/h1k-live/run-live-c.sh`（outer，含挂载与全部具名 env）与 `drive-c.sh`/`drive.sh`（inner，含读数清单）⇒ V5′ 派工不必重新设计，只改五处，且每处都能落到字面。

**三式形状（全部经真实 `run.sh` 的 docker 形状，`minekin-runner:local`，`MINEKIN_HOME=/data`，`PYTHONPATH=/src/src`，`LD_LIBRARY_PATH=/opt/sqlite/lib`，`--server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json`）**：

| 式 | env 面（相对 H1k live-c 的差量） | 取哪条判据 |
| --- | --- | --- |
| **A 双名 armed**（主证） | `MINEKIN_DOMAIN_PROBE` **不设**（⇒ 第一名走默认 `${probe:-${player}}` = 宿主 `Kin`）、加 `-e MINEKIN_DOMAIN_PROBE_SECOND=Kin2`、保留三名 `JOIN_LOOK_YAW=45`/`LOOK_PITCH=-20`/`HOLD_FORWARD_SECONDS=2` | 第 2 条（按 `Kin2` 行内名读首末差）、第 4 条第一格（同 run 内 `Kin` 首末**必须不变**）、第 5 条（两名都被问过 = 直读）、第 3 条（`PlayableEstablished`+`position>baseline` 与 `the world heard … arrive` 分记） |
| **B 同形状 control-off**（非恒真对照） | 与 A 同，**抽掉**那三名控制词（H1k 的 `H1K_SHAPE=control-off` 分支已是这个形状）⇒ 加入者首末读数应**不变** | 第 4 条第二格：区分「H1h 驱动真在动」与「探针节奏自己在动」 |
| **C 不存在的名字**（附加对照，非唯一出路） | 与 A 同，另 `-e MINEKIN_DOMAIN_PROBE=<本 run 从未加入的名>`（第二名仍 `Kin2`）⇒ 该名的答案行应为 `No entity was found`，`Kin2` 仍应有答案行 | §2.16 第 5 条的替代格，§2.41 已把它从「唯一出路」降级为「附加非恒真对照」 |

**M 侧的隔离面**（不共用 lane 卷、不冒充封证）：私有数据根用**新卷** `minekin-m-v5p-live`，按 H1k `prep.sh` 的同款从 `minekin-v4-join:/ro` 灌种（记忆 `kin-01-stale-process-markers` 的教训 ⇒ 宿主与加入者都用**全新 Kin**：`MINEKIN_KIN_ID=kin-v5p-host`、`MINEKIN_DOMAIN_JOIN=kin-v5p-join`，加入者名 `MINEKIN_DOMAIN_JOIN_USERNAME=Kin2`）；jar 仍指主机 `.tmp/mc-1.20.1-server.jar:ro`；材料落 `minekin-wt-integration/.tmp/v5p/`；**规范卷 `minekin-runner-data` 全程不挂**（E 的写窗），三式读数一律写作「M 私有卷活体读数」而非 sealed bundle。活体窗须先看 `docker ps` 静默并预约（§2.13 末的 30s 握手预算 ⇒ 三式串行、不并行）。

**判停（具名，不改判据）**：§2.41 表里有两格标着「今天即可」（第 3 条、第 4 条第二格）。**V5′ 不拆成「今天跑两格 + 之后再跑五格」**，理由三条，都写死在此以免日后被顶替：① 第 4 条两格按判据原文要在**同一形状、同一节奏**下成对读，拆跑等于换成两次会话的比较，非恒真性下降；② 活体窗此刻被 H1m 占（它也要经真实 `run.sh` 跑两名），M 抢引擎会同时污染两边的 30s 握手预算；③ 半张卡的记录会留下一条「V5′ 部分绿」的口径，E7 封证与 M-C1 登记都只认整卡七条。⇒ 三式在 H1m 入干后**一次会话内串行发**，前置不满足（H1m 未入干 / 行号未重读 / 引擎不静默 / 灌种失败）则保留失败材料并就地停，不拿 B、C 两格冒充卡绿。

**四态**：真实封证仍 **0**；已合主干且 CI 绿 = `af514d1`（`896` success，含 `dcc3e24` 的 H1l 合并链）；`c87089d` 已 push、CI `queued` 不作绿；仅在分支 = H1m（在飞，尚无提交、无远端 ref）与 lane 的 `codex/minekin-h1l-forward-join-name` ref；未验证 = V5′ 全卡（本节只写形状，未跑一发）、H1i 全卡、#58 (乙)。本轮零容器活体、规范卷未挂、未读 `.tmp/local-test-server.txt`（未连接用户远程服）、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删（`.tmp/m-r54-ci.json` 在案）。

## §2.43 H1i 的真缺口在 `38854ea` 的字节上是**两处**而不是「LAN 日志那格」；另开窄卡 H1n 收 `domain.sh:2430` 的字面 `\n`（第五十四轮后半，2026-09-27 23:05 +0800，M 主控；只读仓库字节，不挂引擎、不进 H1m 工作面）

**为什么现在量**：H1i（#52）严格排在 H1m 之后，而它的卡面口径来自第四轮之前的世界——那时加入者只能进宿主的 LAN 世界。项目记忆里那条「LAN 日志那格是 `domain.sh:2472-2489` 有意丢弃」的编号早已失效（§2.39 的同一族教训），H1k 又把专服形状送了进来 ⇒ 不重读就派工，等于拿旧地图画新脸。本轮只读主干盘上字节（`domain.sh` = `38854ea` 树内），零容器。

**缺口一（封存里根本没有服务端日志载体）**：`case_id` 分支 `:2825` 之内，`world_args` 在 `:2846–:2847` 被铸成 `--server-profile … --server-directory …`，但 `case_on=joiner` 那一支 `:2875–:2891` 把它**整组清空**——`:2887–:2890` 的注释逐字为「And this run's own world inputs are dropped, deliberately: a dedicated server profile is a *different* kind of world, and leaving it named would let a join with an unreadable host document fall back to recording one that never ran rather than being refused.」⇒ `seal_run_evidence.py:255–:258` 那三行按 `${server_directory}/server.log`、`usercache.json`、`server.properties` 取 artifact 的代码**不会跑到**（`server_directory is None`）。后果直白：E7 若按加入者侧封存，bundle 里没有 §2.16 第 2 条要的按名答题行载体。注释的理由属于「加入者进的是**别的 run** 的世界」那代形状；专服形状下起这个服务端的是**本 run 自己**（`:821` 置空、`:850` 铸 `server-runs/run-N`、`:923` 打印，`:1988` 等待读的就是同一份 `${server_directory}/server.log`）⇒ 该理由在这一支不成立，交出去是安全的、且默认关闭才有得谈。

**缺口二（探针问的是谁，封存里读不出）**：`--probed-player` 在 `tools/**` 侧**已有承担者**（`seal_run_evidence.py:929` 收参数、`:337–:338` 拼进命令面、`:805` 带进材料；`assert_case_evidence.py:712/:1051` 读回），而 `grep -n "probed-player" test-orchestrator/runner/domain.sh` **回空** ⇒ `domain.sh:2984` 的那次 `seal_run_evidence.py` 调用从不递这个名。于是 M-C0 造的归属载体在战役路径上是**空转**的：判据能读「谁被探」，但没人把「谁被探」写进 bundle。这正是 §2.4 卡面里「探针目标交给加入者封存调用」那一半，且它不依赖 LAN 日志那格。

**⇒ H1i 的卡面据此收窄为两格**（不放宽任何判据，只是把「宿主 LAN 日志」这一格换成它在今日字节上的等价物）：① 专服形状下把本 run 的 `--server-directory`（连带 `--server-profile`/`--server-jar` 三条，形状与 `:2846–:2852` 同）交回加入者侧的封存；② 把本 run 实际问过的名字按 `--probed-player <名>` 逐一递出（H1m 入干后是两名）。两格都要**默认关闭**：不设 `MINEKIN_DOMAIN_*` 新旋钮 ⇒ 加入者侧封存命令与今日逐字节相等（`world_args=()` 原样保留 = 旧行为不变），坏值落盘前具名 `exit 2`。反证照本族口径：(a) 破默认 ⇒ 加入者 bundle 多出 `server.log` artifact 且含按名答题行；(b) 不设旋钮 ⇒ 该 artifact **不出现**（否则该格恒真）；(c) 递出的名字里含一个本 run 从未问过的名 ⇒ 具名拒止。

**H1n（新开窄卡，与本队列正交）**：`test-orchestrator/runner/domain.sh:2430` 的离场等待里，一条本该续行的语句被压成一行，行内留着**字面** `\n`——`if grep -qE "${kick} (lost connection|left the game)" \n            "${server_directory}/server.log" 2>/dev/null; then`。`git blame` 归到 `eb26bb0`（2026-09-20，本队列之外），`git log -S'left the game)" \n'` 同笔。bash 里未加引号的 `\n` 就是一个裸词 `n` ⇒ 该命令实为 `grep -qE <模式> n <server.log>`，`n` 被当作**文件操作数**，其打开失败的报错被 `2>/dev/null` 吞掉。

**这不是推断，已按最小形状量过并留材**（`.tmp/m-r54-nldefect.sh` → `.tmp/m-r54-nldefect.log`，末两行 `n_absent_rc=2`、`n_present_rc=0`；两式只差一个名为 `n` 的文件，`server.log` 两式都**不含**该模式）：

```text
$ printf 'nothing relevant here\n' > server.log
$ rm -f n; grep -qE 'Stevedor (lost connection|left the game)' \n server.log 2>/dev/null; echo $?
2                       # n 缺席：rc=2（grep 的报错被吞，落到「继续等」）
$ printf 'Stevedor lost connection\n' > n
$ grep -qE 'Stevedor (lost connection|left the game)' \n server.log 2>/dev/null; echo $?
0                       # n 在场且含该模式：rc=0 —— 服务端从未说过这句话
```

⇒ 危险具体化为：工作目录一旦出现名为 `n` 且含 `${kick} (lost connection|left the game)` 的文件，`kicked` 就在服务端没有说过这句话时置 1（**假绿**，且正是离场/踢线那一格）；另一条次要后果是「日志无命中」（rc=1）与「grep 自己出错」（rc=2）在 `2>/dev/null` 之下不可分辨。修法面：`domain.sh` 一处续行 + 一条契约断言（扫 `domain.sh` 命令位置的字面 `\n`）+ 上面这两枚对照（`n` 缺席 ⇒ 不置位；`n` 在场 ⇒ 现字节置位、修后不置位）。独立独占面，与 H1m/H1i 无先后耦合（`:2424–:2435` 属 kick 等待支），可插空档派。

**§2.43 补记（同轮 23:09 +0800，M 主控；不静默覆盖上一段）**：上面「缺口一」的处方里写了「连带 `--server-profile`/`--server-jar` 三条，形状与 `:2846–:2852` 同」，这与 M 早前的一条更严口径相冲（当时的判据是：**opt-in 打开时只补 `--server-directory`，绝不带回 `--server-profile`/`--server-jar`**，理由正是 `:2887–:2890` 那段注释所防的「记录一个从未跑过的世界」，且当时已量过加入者 bundle 的世界记录走 `seal_run_evidence.py` 的 `world_run_document` 分支并先返回 ⇒ 只加目录**不改 `world` 字段**）。**该口径此前只存在于 M 的记忆库里（那次「单 bundle 双载体是否需要扩 schema」的卷内实测：6 份 `CORE-030` 加入者 bundle 全不含 `server/server.log`），仓库文档里没有它的落点** ⇒ 本条补记即入册，并记下这条流程缺陷：**判据口径只进记忆不进文档，就会在下一轮被自己的处方顶替**。该口径**继续作默认**，上一段的改口不成立。⇒ H1i 的第①格按「只交 `--server-directory`」写死；`--server-profile`/`--server-jar` 是否要在专服形状下随件，**须先量 `server_profile` 在 sealer 里的实际用途再判**，量不出必要性就保持缺席。这是收窄、不是放宽。

## §2.44 CI 三笔闭合、补记入册、H1m 的现场从「无提交」变成「允许面三文件在写」——#62 因此**不派**（第五十四轮末，2026-09-27 23:11 +0800，M 主控）

**CI 一次读**（`.tmp/m-r54-ci2.json`）：`896`=`af514d1`、`897`=`c87089d`（§2.41 笔）、`898`=`38854ea`（§2.42 笔）三笔 `completed/success` ⇒ §2.41/§2.42 两笔记录笔由 CI 判绿，「已合主干且 CI 绿」的最近一笔前进到 `38854ea`；`899`=`3298532`、`900`=`095c852` 23:09 时点 `in_progress` ⇒ 不作绿，接手会话重读。远端 `main` 现场 `git ls-remote` = `095c8521ba5d0272aa16e4376b034acbda20bc03`。

**§2.43 补记的意义要说白**：M 自己在上一段处方里把「加入者封存只交 `--server-directory`」这条更严口径顶替成了「连 profile 带 jar 三条一起交」，而该口径此前**只活在 M 的记忆库里、仓库文档无处可对** ⇒ 本轮以新笔（`095c852`，不 amend）收回，并把「判据口径只进记忆不进文档就会被自己的下一轮顶替」这条缺陷写进补记。**流程结论**：凡影响卡面的口径，落卡面文档才算存在；记忆库只作索引与提醒。

**H1m 的现场升级（正面信号仍为零，但性质变了）**：`../minekin-wt-h1m` 分支头仍 `dc0067c`、远端仍无该分支 ref，而 `git status --short` 现读到**恰三个脏文件**——`test-orchestrator/runner/domain.sh`、`test-orchestrator/runner/run.sh`、`tests/contract/test_runner_scripts.py`，与派工允许面逐一对应、无越界文件 ⇒ 判「正在施工」，M 不进其树、不代提交（§2.35 口径：只有它自己的收尾回报或远端 ref 上它自己的提交才算收尾）。

**⇒ #62 H1n 此刻不派**：它要改的 `domain.sh:2430` 与 H1m 在写的 `domain.sh` 是**同一个文件** ⇒ 「该文件无其它写者」这一前置不满足，按并行协议排到 H1m（及紧随其后的 H1i）落干之后再开树。#58 (乙) 同理仍需等引擎窗。**四态**：真实封证仍 **0**；已合主干且 CI 绿 = `38854ea`；`3298532`/`095c852` 已 push、CI 待读；仅在分支 = H1m（在写，未提交）与 lane 的 h1l ref（不删）；未验证 = V5′ 全卡、H1i 全卡、H1n 全卡、#58 (乙)。本轮零容器活体、规范卷未挂、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删（`.tmp/m-r54-nldefect.sh`/`.log`、`.tmp/m-r54-ci*.json`、`.tmp/m-r54*-diffcheck.log` 在案）。

## §2.45 门载荷在当前主干字节 `eb8aaa9` 上的 PRE 基线：实测未动（不是「按构造」推出来的）（第五十四轮收尾，2026-09-27 23:13 +0800，M 主控；容器只读，规范卷 `:ro`，零 JVM）

`docker ps` 现场为空 ⇒ 不与 H1m 抢窗。两枚读数（`minekin-runner:local`，`/src:ro` 挂主干树，`-e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src`）：

- `python /src/tools/report_promotion.py --data-root /data`（规范卷 **只读**挂载）⇒ **rc=1**（按构造 blocked）、stdout `103,921 B`、`{work_packages, overall}` 子集 sha256 = **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**（材料 `.tmp/m-r54-payload-e.json` / `.err`，摘要手 `.tmp/trunk_digest.py`）。
- `python /src/tools/check_case_assertions.py` ⇒ **rc=0**、末行 `Case assertion implementations: OK (150 registered)`（材料 `.tmp/m-r54-assertions-e.log`）。

**为什么要实测而不是引用**：`d95e59d` 之后主干连着落了八笔纯 docs（`dcc3e24`、`dc0067c`、`af514d1`、`c87089d`、`38854ea`、`3298532`、`095c852`、`eb8aaa9`），此前每笔都按「门载荷输入面不含 `docs/**`」判它不动——那是**构造性论断**，本轮把它换成一次现读。⇒ 这就是 H1i / V5′ / H1n 三张卡的 **PRE 基线**：交付时 `POST` 必须仍等于 `cfa0f118…63afd6`、`report_promotion` 仍 rc=1、`check_case_assertions` 仍 `150 registered`（这三张卡都不注册 case；若谁动了 registry，就要按 OFFLINE 那族的规矩量出差值并具名）。**四态增量**：真实封证仍 **0**；本轮零 JVM/零引擎活体、规范卷只 `:ro`；未连接用户远程服；未放宽认证/地址/lease/判据；未翻 `mandatory`/registry；材料未删。

## §2.46 V5′ 的第二条前置量到字节：集成树没有 1.20.1 桥产物——失败面是**具名拒止**（不是静默降级），而「就地建一次」不会动 recipe 的 source 钉（第五十四轮末第三格，2026-09-27 23:22 +0800，M 主控；全程只读，零 JVM、零 gradle、零容器、规范卷未挂）

**缺口本身**：`ls minekin-wt-integration/bridge-1201/build/libs/` ⇒ `No such file or directory`（该目录下 `build/` 整层不存在）。而 lane 两棵树各有一份产物，且**同摘要**：

```text
e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f  2026-09-27 18:45:12 +0800  1310604  minekin-wt-h1k/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar
e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f  2026-09-27 23:14:43 +0800  1310604  minekin-wt-h1m/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar
```

两棵树、相隔 4.5 小时、字节相同 ⇒ 「在集成树现建一次会拿到什么摘要」这一格不必猜：期望值就是 `e50d61c2…7006f` / `1,310,604 B`，它同时是 `recipe.py:72–:73` 的钉值（`BRIDGE_1201_JAR_SHA256` / `_JAR_SIZE`）。

**失败面读到了码，不是推断**：1.20.1 的桥在 recipe 里是 `source: "workspace:bridge-1201"`（`recipe.py:274`），装 mod 那一步对 `workspace:` 来源只问一件事——文件在不在：`src/minekin_core/adapters/launcher/mods.py:93–:97` 对缺失路径抛 `… has not been built: {jar} is missing`，`ErrorCategory.SUPPLY_CHAIN` + `Retryability.OPERATOR_ACTION`。⇒ V5′ 若直接拿主干树起活体，会在**任何世界动作之前**具名拒止，可判、可读、不会伪装成一次通过的读数。这是「前置不满足就保留失败材料」那一类里最省事的一种：拒止即证据。

**但另一轴是沉默的，必须写进 V5′ 验收**：盘上那份 jar 的字节**从不被 rehash**——`BRIDGE_1201_JAR_SHA256` 只在 recipe 审计里与 bundle 记录里的 `digest`/`size` 字段比对（`recipe.py:267–:280`），`workspace:` 分支只 `is_file()`（`mods.py:95`）。⇒「在位但内容不对的桥」会照常起程。所以 V5′ 的记录必须**自己 `sha256sum` 它挂进 `/src` 的那一份并写值**，正如 H1k 的 `.tmp/h1k-live/drive.sh` 已经在 `00-header.txt` 里做的那样（其读数 = 钉值，本轮已在盘上核到）。这条是取数要求，不是改判据。

**「就地建一次」为什么不会碰钉**：`_candidate_1201_audit` 除比摘要外还比 `source_digest = source_tree_sha256(workspace_root / "bridge-1201")`（`recipe.py:281–:283`，不符 ⇒ `candidate Bridge source tree digest differs from the bundle recipe`）。而 `source_tree_sha256` 在 `recipe.py:138–:145` 具名剔除路径分量属于 `{".gradle", "build"}` 的一切 ⇒ gradle 的产物落进 `build/` 之后，源树摘要**逐字节不变**，那一格不会被自己碰响。⇒ 前置动作 = 在集成树跑一次 `bridge-1201/gradlew :bridge-1201:jar`（注意 wrapper 在 `bridge-1201/` 下，仓库根无 wrapper），然后核摘要；**若新摘要 ≠ `e50d61c2…` 就停**：那说明在盘两份与主干源树有差异，先具名差异再判，M 不改钉（改钉 = 重封全卷级别，主控保留决策）。

**H1m 的现场从「三文件在写」升级为「正在真跑 armed 形状」**（仍不构成交付）：`docker ps` 读到 `friendly_mcclintock`，`docker inspect` 留存 `.tmp/m-r54-h1m-inspect.txt` ⇒ `/src` = `C:/Users/darling/Documents/agent_work/minekin-wt-h1m` 只读、`/data` = `minekin-h1m-live` 读写、`/server/server.jar` = 主目录 `.tmp/mc-1.20.1-server.jar` 只读、`StartedAt = 2026-09-27T15:16:18Z`；具名 env 里读到了 **`MINEKIN_DOMAIN_PROBE_SECOND=Kin2`** 与 `MINEKIN_DOMAIN_PROBE=Kin`、`MINEKIN_DOMAIN_JOIN=kin-h1m-join`、`MINEKIN_KIN_ID=kin-h1m-host`、`MINEKIN_DOMAIN_JOIN_USERNAME=Kin2`、`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`、`PROBE_SECONDS=4`、`DOMAIN_SECONDS=300`、`SOAK_SECONDS=120`、`SOAK_INTERVAL=15` ⇒ §2.29 的 armed 形状正在它自己的私有卷上跑。其树 HEAD 仍 `dc0067c`、远端仍无该分支 ref ⇒ 按 §2.35 仍是「在飞」，M 不挂容器、不跑 gradle（不与它抢 CPU/引擎）、不进其树、不代提交。

**三条 probe 相关远端 ref 的归属已核，都不是新的在途 lane 工作**：`8b66356`（21:53，M-T1 的格式化笔）、`1e42ea6`（16:19，M-C0 探针载体）、`7f67aac`（16:37，V5a 前置量测）三笔 `git merge-base --is-ancestor … HEAD` 全部 YES ⇒ 早已合主干；卷 `minekin-v5-probe` 同源于那一轮 ⇒ V5′ 仍按 §2.42 用**新建**的 `minekin-m-v5p-live`，不复用它、也不清它。

**⇒ V5′ 派工前置合并为三条**（全部 M 可控、全部不动认证/地址/lease/判据）：① H1m 入干（§2.42、§2.45）；② 集成树桥产物在位且摘要 = `e50d61c2…`（本节，含「摘要写进记录」那条新增验收）；③ `docker ps` 静默（引擎窗）。

**§2.46 补记（同轮 23:28 +0800，M 主控）＝M 侧的 V5′ 驱动已经落盘并量过语法门，种子源已核**：趁 H1m 的活体窗不抢 CPU，M 只做了零 JVM 的准备面——`.tmp/v5p/prep.sh`（灌种：`init --kin-id kin-v5p-host` + `cp -a` 自 `/ro/kin/kin-v4-host/run/artifact-store`）、`.tmp/v5p/drive.sh`（一次 `domain.sh` 真跑 + 七组读数，**含本节那条新验收：把 `/src/bridge-1201/build/libs/*.jar` 的 `sha256sum` 写进 `00-header.txt`**；按名答题行按 `Kin`/`Kin2`/`PROBE_SECOND` 三名各自计数并留首尾，服务端日志整份拷贝 ⇒ 读数不依赖本脚本的 grep 是否猜对）、`.tmp/v5p/run-shape.sh`（§2.42 三式 = `armed`/`control-off`/`ghost`，`minekin-m-v5p-live:/data` + `minekin-v4-join:/ro:ro` + 主干树 `:/src:ro` + `../minekin/.tmp/mc-1.20.1-server.jar:/server/server.jar:ro`，**起前强制 `docker ps` 非空即 `exit 3`**）。`bash -n` 三份各 rc=0；`docker volume create minekin-m-v5p-live` rc=0（此前不存在）；种子源只读核过 ⇒ `blobs=7565`、`sha1 0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838` 与 `1.20.1.jar` 路径逐字对上 H1k 的 `prep.sh` 所记。⇒ 前置 ②/③ 的执行面已备好，**只差 H1m 入干后的现读行号**（`:794` 那三处）与摘要核对；这一格不因等待而重做。另读到 `../minekin-wt-h1m/.tmp/h1m/` 目录 mtime 23:20、其活体容器 7 分钟仍在飞（其 `DOMAIN_SECONDS=300` + soak 一轮即数分钟，静默不等于已停）。


**（归位说明，第五十五轮 23:41 +0800，M 主控）**：下面这段「四态」原属 §2.46 —— `5eb5546` 那次追加 §2.47 的 Edit 把它接在了 §2.47 的收束段之后，内容一字未丢、位置错成了 §2.47 的尾巴。这里只把它搬回 §2.46 末尾，读数不改。

**四态**：真实封证仍 **0**；已合主干且 CI 绿前进到 **`e8fc436`**——一次读 `.tmp/m-r54-ci3.json`（23:22 +0800）把 §2.44/§2.45 欠的四笔一次闭合：`899`=`3298532`、`900`=`095c852`、`901`=`eb8aaa9`、`902`=`e8fc436` 全 `completed/success`（连同 `895`–`898` 亦 success，即第五十四轮全部记录笔 CI 判绿，本轮无 `in_progress` 欠账）；仅在分支 = H1m（在飞，真跑中、尚无提交）与 lane 的 `codex/minekin-h1l-forward-join-name` ref（不删）；未验证 = V5′ 全卡、H1i 全卡、H1n 全卡、#58 (乙)。**M 自己的手误具名**：本节量测中途把 `docker inspect` 的落盘写进了 `../minekin/.tmp/`（那是 E/lane 的 `codex/core-state-transition` 工作树，M 的边界是不进它的工作面）⇒ 已 `mv` 回 `minekin-wt-integration/.tmp/m-r54-h1m-inspect.txt`，主目录该项现不存在。记下以免重复：**M 的只读材料只写自己的树**。本轮零 JVM、零 gradle、零容器活体、规范卷未挂、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删（`.tmp/m-r54-h1m-inspect.txt`、`.tmp/m-r54-ci3.json` 在案）。
## §2.47 等待窗内的三格预备读数：V5′ 的守门是非恒真的、H1m 的允许面在主干上零漂移、H1i 的 PRE 基线在当前字节复算等于校准时值（第五十五轮首格，2026-09-27 23:33 +0800，M 主控；宿主 `uv` + 只读容器，零 JVM 构建、规范卷未挂）

H1m 仍未交付（其树 `dc0067c` + 允许面三文件脏、远端无 ref；23:28→23:32 在写 `live-B-default-off`/`live-B2-default-off` 两式 ⇒ 正在跑 §2.29 的对照形状）。等待不空手，三格读数各自单步跑并先读 rc：

- **V5′ 的守门读数（非恒真）**：`.tmp/v5p/run-shape.sh` 趁 lane 容器在飞跑一次 ⇒ 打印 `V5P: refusing to start — another run is in flight: thirsty_cerf Up 2 minutes` 并 **rc=3**，未起任何容器；随后只读核 `minekin-m-v5p-live` 仍 `entries: 0`（材料 `.tmp/v5p/guard-nonvacuity.log`）。⇒ §2.42 那条「三式串行且先验 `docker ps` 静默」是**活的路径**而非文档意图；另一半（`ps` 空 ⇒ 真放行）留待第一式实跑同格记录。
- **复审前提：主干自 H1m 分支点后没碰过它的允许面** ⇒ `git log --oneline dc0067c..HEAD -- test-orchestrator/runner/domain.sh test-orchestrator/runner/run.sh tests/contract/test_runner_scripts.py` **回空**（rc=0）；`git merge-base dc0067c HEAD` = `dc0067c` 且 `--is-ancestor` 判 YES。三文件当前主干 sha256 前 16 位 = `e1d8dbb98d5f760d`（`domain.sh`）/`10681b18fac76f8b`（`run.sh`）/`e33a1da96a53cc2a`（契约），`domain.sh` 与第四十九轮复审记录同值。⇒ H1m 的 diff 不因主干漂移失真，复审可按「主干三文件字节 == 它分支时的字节」判；其交付后这三值只允许按它自己声明的改面移动。
- **H1i 的 PRE 基线在当前主干字节上复算＝校准时值**：`uv run --frozen --offline python .tmp/m-r39-h1i-seal-argv-judge.py report --tree .` ⇒ **rc=0**，`joiner_region_sha256 = 4270b51cba07e4da32b9dc979f531afa96026596548b2a059d651e8a04763dee`、`seal_argv_region_sha256 = 7d83721fdf0138216da051cdd5653d6bb10bbfe29a56225394e7ade7f5c2b9a6`、`joiner_world_args_dropped = true`、`world_flags_in_joiner_branch` 三旗标各 `[]`（材料 `.tmp/m-r55-h1i-judge-trunk.log`）。两枚 sha 与 `95b1b00` 上的标定值**逐字相同**，唯一动的是绝对行号（现读 `joiner_region_abs_start_line = 2884`）——该判官在 §2.6 那笔改正后只报行号不判等 ⇒ 恰好再次实证「行号不是字节」。**意义**：H1i 交付时「不设新旋钮则加入者侧封存命令与今日逐字节相等」这一格有 M 自量的 PRE，不必引用 lane 的表。

**CI 收口**：`903`=`f885a3b`、`904`=`0b2feda` 均 `completed/success`（`.tmp/m-r55-ci.json` 及后续一次重读）⇒ §2.46/§2.46 补记两笔记录笔判绿，本轮无 `in_progress` 欠账；「已合主干且 CI 绿」= 远端 `main` `0b2feda`。**四态**：真实封证仍 **0**；仅在分支 = H1m（在飞，正在跑对照式，尚无提交）与 lane 的 `codex/minekin-h1l-forward-join-name` ref（不删）；未验证 = V5′ 全卡、H1i 全卡、H1n 全卡、#58 (乙)。本轮零 JVM 构建、零引擎活体（只跑了一次只读容器核卷）、规范卷未挂、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删（`.tmp/v5p/guard-nonvacuity.log`、`.tmp/m-r55-h1i-judge-trunk.log`、`.tmp/m-r55-ci.json` 在案）。

## §2.48 H1m 在飞期的 M 侧预复审：它自报的 PRE 门载荷与主干基线逐字同值、活体读数可经 `pristine` 摘要链归到最终 runner 字节，但**日志头部没打印脚本摘要**这一格要在合入时硬核（第五十五轮第二格，2026-09-27 23:41 +0800，M 主控；全程只读 lane 材料 + 主干 collect，零 JVM、零 gradle、零容器）

判停口径不变：H1m 到本笔写作时仍未交付（其树 `dc0067c`、允许面三文件脏、远端无该分支 ref、23:39 全量 pytest 跑到 85%）。下面每一格都是**对 lane 私有材料的读法**，不构成合入决定，也不是 sealed bundle。

- **PRE 门载荷：M 用我的手对 lane 落盘的报告复算 = 主干基线**：`python .tmp/trunk_digest.py ../minekin-wt-h1m/.tmp/h1m/gate-payload-pre.json` ⇒ `gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，与 §2.45 在 `eb8aaa9` 主干字节上量的值**逐字相同**；文件本身 `103,921 B` 亦同值。⇒ 六格清单的第 6 格 PRE 侧不必等它交付就已闭合，`POST` 仍须在合并树上由 M 自量。
- **改面是真的**：其工作字节 `domain.sh = e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954`、`run.sh = 323f521a3141fa3c613d02b93500612aa1ec943a2467a4da1d4a5080f1669126`、契约 `= 86b216853a6cf8bf0edce27d372870808e89973e71b34d96d0f899b2c028a3cb`，主干三值 = `e1d8dbb9…`/`10681b18…`/`e33a1da9…`（§2.47）⇒ 三份都动过，且 `git diff --stat` 只报这三文件（+265/−2）。
- **活体＝最终 runner 字节的出处链（本轮补上的那一格）**：`.tmp/h1m/domain.sh.pristine` 的 sha256 = `e04524d6…`（与其工作字节同值），`counterexamples.log` 在 CE(a)/CE(b)/CE(c) 每枚反证后都打 `RESTORED: sha256 matches pristine (e04524d6…)`，FINAL CHECK 时间戳 `15:13:19Z` 与 `domain.sh` 的 mtime `23:13:19` 对上 ⇒ 那 mtime 是**种桩后还原**写的，不是其后又改过。三组活体起跑于 `15:16:16Z`/`15:20:51Z`/`15:29:28Z`（本地 23:16/23:20/23:29），全在其后；`23:33:42` 的 `ruff format` 只改 `tests/contract/test_runner_scripts.py`（其日志第 2 行具名该文件，且 shell 文件不经 ruff）。⇒ 「活体读数取自最终提交字节」目前由 **mtime + pristine 摘要链**推得。**缺陷申报**：lane 的三份 live 日志头部**不含 `domain.sh` 摘要**（`.tmp/h1k-live/prep.sh` 那一格它没抄）⇒ 合入时以 `git show <tip>:test-orchestrator/runner/domain.sh | sha256sum == e04524d6…`、`run.sh == 323f521a…` 作硬核查，不等则退回。
- **代码面（M 现读其 diff，不读它的结论）**：`probe_second` 绑在 `domain.sh:35`、`use_target` 绑在 `:141`，两者都早于 guard `:802–:826` ⇒ `set -u` 下不会 unbound；guard 早于 run 目录编号 `:892`（`while [ -e "${runs}/run-${n}" ]`）与服务端 `--jar` 起动 `:953` ⇒ 「before anything is written」是行序可判的事实，不是措辞；forge `:833–:837` 只有一行 `probe_args=(...)` 原句 + `if [[ -n "${probe_second}" ]]` 内的 `probe_args+=(--probe-player "${probe_second}")`，未设时该分支不执行 ⇒ 默认等值由构造成立；`run.sh` 只是在名单末尾加裸 `-e MINEKIN_DOMAIN_PROBE_SECOND`（`git diff` 可见它不带任何默认值）。
- **三枚具名拒止是真跑出来的**：`refuse-1-same-name.log`（同名 ⇒ 具名消息 + `rc=2`）、`refuse-2-use-target.log`（`USE_TARGET × 第二名` ⇒ 具名消息 + `rc=2`）、`refuse-3-absence.log`（同容器内 `PROFILE-ABSENT`/`RUNDIRS-ABSENT`/`NO-JVM`，拒止后什么都没留下），三枚都在 `15:15Z`（早于活体、晚于最终字节）。
- **活体形状**：`live-A`（两名）⇒ 同一份 `server.log`（`1be9518b…`，274 行）里 `Kin has the following entity data` 72 行、`Kin2 …` 66 行，各名首尾读数分列（`Kin [-2.5,-60,-5.5]` / `Kin2 [3.5,-60,0.5]`）；`live-B2`（默认关闭、但 `Kin2` 真加入并 left）⇒ `Kin` 68 行、`Kin2` **0 行** —— 这一枚才是非恒真对照（`live-B` 那式 `Kin2` 从未到场，只证明「没到场时也没有按名答题行」）。三式 `rc=14` + `outcome BRIDGE_LOST` 与 M 私有卷同族 ⇒ 属**私有卷活体读数**。
- **计数基线**：主干 `tests/contract/test_runner_scripts.py` `--collect-only -q` ⇒ **85 tests**、其中名含 `second_probe` 者 **0**（`.tmp` 屏幕读数）；lane 最终该文件 `94 passed` ⇒ 净 +9，与「未注册 case」一致，所以 §2.45 的三条主干常量（载荷值 / `report_promotion` rc=1 / `150 registered`）对它全部适用。
- **不抢窗**：lane 的全量 pytest 在飞（23:39 到 85%）⇒ M 本轮不起 `bridge-1201` 的 gradle 构建（§2.46 前置 ②），该构建留到它结束后再跑；`docker ps` 此刻为空但我不用它。
- **CI 收口**：`905` = `5eb5546` `completed/success`（连同 `903`/`904`）⇒ 第五十五轮已推的三笔记录笔全绿，本轮无 `in_progress` 欠账。

**同轮的另一件我自己造成的缺陷已当场改正（纯 docs，不动门载荷）**：`5eb5546` 那次以 §2.46 补记末句为锚追加 §2.47 的 Edit，把 §2.46 原本的收束「四态」段（记 `899`–`902` 判绿 + M 手误具名那段）接到了 §2.47 的收束段之后 ⇒ 内容一字未丢、**段落归属错位**。本轮用 `.tmp/m-r55-fix-section-order.py`（幂等，撞见标记唯一才动）把它搬回 §2.46 末尾并留一条归位说明。教训入册：**在同一物理行结尾追加新章节前，先确认那一行不是某段的收束段** —— 锚在「上一节最后一段」上就等于把那段推到自己的节之后。

**四态**：真实封证仍 **0**；已合主干且 CI 绿 = 远端 `main` `5eb5546`（本轮这笔为「已写、待推」）；仅在分支 = H1m（在飞、尚无提交）与 lane 的 h1l ref（不删）；未验证 = V5′ 全卡、H1i 全卡、H1n 全卡、#58 (乙)。本轮零 JVM、零 gradle、零容器、规范卷未挂、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、lane 材料一律只读未改、材料与失败材料未删。

## §2.49 第五十六轮：H1m 交付 → M 侧七格独立复审 → 合入并推 `012f56b`；V5′ 前置 ② 当场闭合

- **交付事实（不是 M 代提交）**：lane 分支 `codex/minekin-h1m-second-probe-target`，两笔 `6e4c424`（feat(runner)）+ `dff4550`（docs(validation)），`git ls-remote` 与本地 HEAD 同为 `dff45504910c2ca3cf645f03f770bcd9eba1d3b0`；其工作树 `git status --porcelain` 行数 **0**。上一轮那个死在「写 POST 配对」一步的执行体由续接体收完（按 `feedback-resume-stalled-lane-subagent`：只补测只交付，不重设计）。
- **格 1 交叠面 = 空**：真实 merge-base `dc0067c`；lane 自该点动 `docs/validation/v1201-domain-second-named-probe-target-2026-09-27.md`（新增）+ `test-orchestrator/runner/domain.sh` + `run.sh` + `tests/contract/test_runner_scripts.py`，主干自该点只动 `docs/**` 四文件 ⇒ `comm -12` 两侧文件清单**零交集**，合入是 `ort` 干净合并（+426/−2），无需裁决。
- **格 2 摘要硬核（补上 lane live 日志缺的那一格）**：`git show dff4550:...domain.sh | sha256sum` = `e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954`（与 lane 报的工作字节逐字同）、`run.sh` = `323f521a3141…669126` 同值；契约文件两种口径分列：盘上（CRLF 工作树）= `86b216853a6c…28a3cb`（lane 报的值），`git show` blob（LF）= `a1c677baaad4…4887cc`，`sed 's/\r$//'` 回算即得后者 ⇒ **口径差异而非篡改**（`project-fixture-digest-conventions`）。合并树 `012f56b` 上二者仍为 `e04524d6…`/`323f521a…` ⇒ 合入未动 runner 字节。
- **格 3 构造判官 + 三枚变异（`.tmp/m-r56-h1m-judge-calibration.log`）**：判官 `.tmp/m-r55-h1m-judge.py` 在合并字节上读到 `probe_second_binds=1`、`env_name_uses=3`、`guard_start_line=802`、`guard_refusals_named=['same_name','use_target_x_second']`、`guard_exit_2_count=2`、`guard_before_first_write=True`、`use_target_bound_before_guard=True`、`forge_default_off_equals_pre_knob=True`、`forge_appends_second_name=True`、`forge_unguarded_append_count=0`、`run_forwards_bare=[True]`、`run_forward_line_count=1`；主干同一判官 `env_name_uses=0`、`run_forward_line_count=0`、`guard_present=False`、`forge_present=False` ⇒ 每一格都在「主干没有、lane 才有」的方向上取值。**M 自己判官的两处缺陷由反证当场暴露并已修（如实申报）**：(a) `MINEKIN_DOMAIN_PROBE_SECOND` 作子串会命中主干既有的 `MINEKIN_DOMAIN_PROBE_SECONDS`（`domain.sh:194`、`run.sh:89`）⇒ 假 `env_name_uses=1`，改为 `\b` 词边界 + 只认独立 `-e NAME` 项；(b) 默认等值那格原先按**行集合**过滤追加句 ⇒ 把「无条件追加」也读成默认等值（正是该判的缺陷），改为只剥掉整个 `if [[ -n "${probe_second}" ]]; then … fi` 包裹后比余句，并另读 `forge_unguarded_append_count`；顺带修掉 `plant` 里按集合删行误伤全文 `fi` 的桩。三枚变异在 `mktemp` 副本上各翻对应项：`unconditional-append` ⇒ `forge_default_off_equals_pre_knob=False` + `forge_unguarded_append_count=1`；`guard-after-first-write` ⇒ guard 起点 `802→868`、`guard_before_first_write=False`；`run-casts-default` ⇒ `run_forwards_bare=[False,False]`。种桩后 lane 树字节与 `git status` 行数 **0** 未动。
- **格 4 两枚具名拒止在 M 侧真跑复现**：以 `minekin-runner:local` + 只读挂 `/src`（合并树）直接 `bash domain.sh`：同名式打印 lane 那句 `one run asking the same name twice is not a reading of two kins -- refused here, before anything is written` 且 `domain_rc=2`；`USE_TARGET × 第二名` 式打印 `the pair does not say whose look the block is placed in -- refused here, before anything is written` 且 `domain_rc=2`（两句与 lane `refuse-1/2.log` 逐字一致）。guard 只在冲突形状上应答，非恒真由上面第三格的变异与 lane CE(c) 共同保证。
- **格 5 合并树门读数（逐条单步跑并先读 rc，`.tmp/m-r56-merged-gates.log`）**：`bash -n domain.sh`/`run.sh` rc=0；契约 `94 passed in 17.78s` rc=0；`check_case_assertions` = **`150 registered`** rc=0；`check_boundaries`/`verify_fixture_digests`/`check_workflow_pins` rc=0；`ruff check` rc=0、`ruff format --check` = 368 files already formatted rc=0、`pyright` 0 errors rc=0、`git diff --check HEAD~2 HEAD` rc=0。
- **格 6 门载荷四度同值**：合并树 + 规范卷 `:ro` 跑 `report_promotion` ⇒ rc=1、stdout `103,921 B`、`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` —— 与 lane 的 PRE、lane 的 POST、§2.45 主干基线（`eb8aaa9`）**四方逐字相同** ⇒ H1m 全程未动门载荷，六格清单闭合，`150 registered` 亦证它未注册 case。
- **格 7 计数解释（合并树实测，非推断）**：契约函数名 `49 → 52`（净 +3 函数、用例 `85 → 94` 净 +9），新增具名为 `test_the_second_probe_guard_answers_the_pairs_it_cannot_ask_about`（7 参数）、`test_the_second_probe_name_rides_after_the_first_when_the_run_names_one`、`test_the_second_probe_refusals_are_shipped_verbatim_and_answer_before_any_write`。合并树全量 pytest 由 M 自跑 ⇒ **`2676 passed, 2 skipped in 340.66s` rc=0**，与 lane 的 `2676 passed, 2 skipped in 327.92s` **同数**；两枚 skip 逐名为 `tests/unit/test_orphans.py:686`（本平台答不出「gone」）与 `tests/unit/test_silent_listener.py:123`（Windows terminate 不是信号）⇒ **M 上一轮「主干 2669 与 lane 差 9 = 新增案 + 一枚缺桥产物 skip」那条推断被本轮实读推翻**：差量恰为 +9 新案（`2669 + 9 = 2678 = 2676 + 2`），桥产物在不在都不产生具名 skip（`mods.py:93–:97` 对 `workspace:` 来源只判存在，缺则真跑时报 `SUPPLY_CHAIN`，见 §2.46）。
- **CI 一次读（`.tmp/m-r56-ci.json`）**：`906` = `fbfd9d0`、`907` = `dff4550`（lane 分支自己的构建）、**`908` = `012f56b`（M 的合并笔）全部 `completed / success`** ⇒ 「已合主干且 CI 绿」前进到 `012f56b`，第五十五轮欠的那笔一并闭合。
- **V5′ 前置 ② 当场闭合（本次合入的直接收益）**：合并后在 M 树就地建桥 —— 第一次用 `:bridge-1201:jar` 失败（`bridge-1201` 本身就是 Gradle 根 `minekin-bridge-1201`，任务路径应为 `:jar`；失败材料 `.tmp/m-r55-build-bridge-1201-FE1-wrong-task-path.log` 保留未删），且 `:jar` 只产 **dev** 件 `bridge-1201/build/devlibs/minekin-bridge-1201-0.0.0-dev.jar`（359,641 B、`b05d24fa…`）≠ 钉值。正确任务是 **`:remapJar`**：`.tmp/m-r56-remapjar.log` ⇒ `BUILD SUCCESSFUL in 1m 48s`，产物 `bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar` = **`e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`、1,310,604 B**，与 `recipe.py` 钉值**逐字同**；同一构建里仓库自带的 `:checkHostBoundaryArtifacts` 亦 OK（常量池/mixin/入口无服务端态）。构建前后 `source_tree_sha256` 均为 `ab33714672dc48a8ebd3f288a1e9ffe96ec11b9315a41a85ed26742b11eed979`（= 评审候选件的 `source_digest`）⇒ 就地建产物不动仓库字节、不需重钉。
- **合入与推送**：`git merge --no-ff` ⇒ `012f56bfd8576a90ba90dad6f342ec96e97ff497`，`push origin HEAD:main` rc=0，`git ls-remote origin refs/heads/main` = **`012f56b…`** 与本地同值。CI（含上轮 `fbfd9d0` 与本笔）读数落在这节的补记里。
- **H1i 锚点按合并后字节重测（present-tense 更正，旧值只作历史）**：`probe_second` 绑 `domain.sh:35`、guard `:802–:826`（应答句 `:814–:822`）、forge `:834–:837`；`hold_requested=0` `:403`、`hold_at="playable"` `:408`、旗标 `:416`、`--hold-at` `:423`；armed 等待环 `:2182`（H1m 前 `:2139`）；`refuse_first_snapshot` 绑 `:114`、其客户端环境注入 `:1686`；加入者侧 `world_args=()` 清空在 `:2869`（另一次 `:2934`）、`--server-directory` 只出现在 `:2890`、`--probed-player` 在 `domain.sh` **零命中**（该面的载体在 `tools/assert_case_evidence.py` 的 `probed_players` 输入侧）⇒ §2.43 的两格在合并字节上位置成立，行号以本条为准。

**四态（本轮收束）**：真实封证仍 **0**；已合主干且 CI 绿 = 远端 `main` **`012f56b`**（`908` `completed/success`，连同 `906`=`fbfd9d0`、lane 自己的构建 `907`=`dff4550`）；仅在分支 = lane 的 `h1l`、`h1m` ref（均不删，后者已入干但分支保留）；未验证 = V5′ 全卡、H1i 全卡、H1n 全卡、#58 (乙)。本轮 M 侧起了 1 次 gradle（`:remapJar` + `:checkHostBoundaryArtifacts`，只写 `bridge-1201/build/**`）与两枚容器拒止真跑（`/src:ro`，无任何加入者 JVM 到场）；规范卷只 `:ro` 挂载读门载荷；未连任何外部地址、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、lane 树只读未改、FE1 失败材料保留未删。

## §2.50 H1i 第①格的前置量测闭合：`server_profile` 在 sealer 里的实际用途逐处都量得出「不必随件」，「只交 `--server-directory`」由记忆口径升级为字节判定（第五十六轮第二格，2026-09-28 00:16 +0800，M 主控；全程只读主干字节 + 只读容器，零 JVM、零 gradle、规范卷未挂；V5′ 三式活体在飞，本节不与其抢窗）

**为什么现在量**：§2.43 补记留下一笔债——「`--server-profile`/`--server-jar` 是否随件，须先量 `server_profile` 在 sealer 里的实际用途再判，量不出必要性就保持缺席」。当时支撑该口径的只有 M 的记忆库和一段 `domain.sh` 注释；H1m 入干（§2.49）后锚点整体 +43，正是把这笔债以今日字节还清的时点。H1i 卡面要写死，就必须让第①格的口径**可复算**，而不是让 lane 信 M 的转述。

**量法（复算式，全部只读）**：

```bash
grep -n '"--server-profile"\|"--server-directory"\|"--world-run-document"\|"--server-jar"\|"--probed-player"' tools/seal_run_evidence.py
sed -n '690,706p;735,755p;760,790p' tools/seal_run_evidence.py   # profile → 判官输入/sealed bytes/guard/manifest/artifact
sed -n '466,540p' tools/seal_run_evidence.py                      # build_manifest：target 只喂 _world_record 与 server_config_digest
sed -n '422,463p' tools/seal_run_evidence.py                      # _world_record 的判定顺序：hosted → 宿主文档 → target → none
grep -n "world_args\|world_run_args\|seal_run_evidence" test-orchestrator/runner/domain.sh
```

**`server_profile` 在 sealer 里的四处实际用途**（`tools/seal_run_evidence.py` 当前主干字节）：① `:692–:705` 用产品自己的门 `load_session_server_profile(...)` 校验一次，产出 `SERVER_PROFILE_ARTIFACT` 的 sealed bytes；② `:719` 把同一份文本以 `--server-profile-document-json` 递给判官（`:329–:330`）；③ `:766` → `build_manifest :499–:504` 的 `target`，它唯一的下游是 `_world_record :395`（世界三元组 `kind/config_digest/name`，其中 `server_config_digest` 取自 `target.revision`）；④ `:783` 把 ① 的 bytes 交 `collect_artifacts`（`:235–:239`）。另有一条**负向**用途：`:735–:754` 的守门只在 `server_profile is None **且** world_run_document_path is None` 时才因「记录显示有世界」而拒封。

**三条构造结论**（加入者侧、且只补 `--server-directory`）：

1. **世界三元组不动**：`_world_record :395–:463` 的顺序是先看本 run 文档的 hosted 快照、再看宿主 run 文档（`:422` → `:426` 一带），两支都在 `target` 那支**之前**返回；joiner 案 `domain.sh:2929` 恒递 `--world-run-document /tmp/domain-session.json`，所以走的正是「由宿主文档命名世界」那一支。⇒ 加目录不改 `world_kind/server_config_digest/seed_or_snapshot_id`。
2. **不会新增拒止**：`:735` 的守门要求 profile 与 world-run-document **同时**缺席，而加入者侧的 world-run-document 恒在 ⇒ 只补目录不会触发「no server profile was given, but the record shows a world」。
3. **真正变化的只有三处**：`collect_artifacts :255–:258` 按 `${server_directory}/server.log`、`usercache.json`、`server.properties` 取三件 artifact（`_artifact :189–:192` 的语义是「在才收，不在就不出现」）；`build_manifest :536–:538` 的 `server_observed_name_uuid` 从 `""` 变为按 `subject_username`（= 加入者名）读该 `usercache.json`；判官 `:319` 多收到一个 `--server-directory`。`--server-jar` 缺席 ⇒ `server_jar_sha1 :528` 仍为 `""`。

⇒ **`--server-profile`/`--server-jar` 量不出必要性**：① 世界记录不需要它；② 拒止面不需要它；③ 按名答题行的载体（缺口一要的 `server.log`）只来自目录。§2.43 补记的口径由「记忆＋注释推断」升为「字节判定」，**继续作默认**：H1i 第①格只交 `--server-directory` 一条。

**必须写进卡面的风险面（这是要实测的，不是我已判的）**：结论 3 的第三处——判官多看见一个 `--server-directory`——意味着凡「按服务端日志取证」的检查从『无载体可读』变成『有载体可读』。默认关闭 ⇒ 今日 150 案的登记读数与封存命令面逐字节不变（`check_case_assertions.py` 仍须 `150 registered`）；但**若把开关顺手用于已登记的 joiner 案，就是在改旧案的 verdict 口径**，那正是 §2.43 补记点过的流程缺陷族。⇒ M-C1 只登记**新案**，E7 只封该新案；旧案不得回指求绿。

**⇒ H1i 卡面定稿（#52，两格、两枚独立旋钮、默认全关）**

- **① 日志载体交回**：`case_on=joiner` 支（`domain.sh:2918–:2935`）在旋钮打开时把 `world_args` 从 `()` 换成**只含** `--server-directory "${server_directory}"` 的一组；`--server-profile`/`--server-jar` 按本节结论保持缺席。旋钮名由 lane 定（建议 `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG`），**必须与②的旋钮互相独立**，否则 (a)(b) 两枚反证会互相掩盖。
- **② 实际探过的名字逐一递出**：`domain.sh` 现在从不递 `--probed-player`（缺口二），而 `tools/**` 侧承担者齐备（sealer `:929` 收参数、`:337–:338` 拼进命令面、`:721` 带进本次 `run_asserter`；`assert_case_evidence.py` 读回）。递出的名字**必须取自 `probe_args` 的实际值**（`:833` 的 `"${probe:-${player}}"` 与 `:835` 的 `"${probe_second}"`），**不得**重新读 env：`MINEKIN_DOMAIN_PROBE` 未设时 launcher 探的是**玩家本人**，重读 env 会递出空名或一个本 run 没问过的名。② 的两枚名与 H1m 的守门（`:814–:822`）共用同一处真值，因此不引入新的名字来源。
- **坏值落盘前具名 `exit 2`**：沿用 H1m 的形状（守门早于 run 目录编号 `:892` 与服务端起动 `:953`）。
- **反证四枚**：(a) 破默认（打开旋钮①）⇒ 加入者 bundle 多出 `server/server.log` artifact 且其中含按名答题行；(b) 关闭旋钮① ⇒ 该 artifact **不出现**（否则该格恒真）；(c) ② 递出一个本 run 从未问过的名 ⇒ 具名拒止；(d) 未设 `MINEKIN_DOMAIN_PROBE` 而打开 ② ⇒ 递出的名 = 玩家本人（非空、非 env 名），且未设 `MINEKIN_DOMAIN_PROBE_SECOND` 时**只递一名**。
- **允许面**：`test-orchestrator/runner/domain.sh` + 本族契约测试；起点 `edfd8c5`（H1m 入干后的记录笔）。门载荷输入面不含 runner/tests 字节 ⇒ 合入侧须实测仍为 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（第四次同值后的第五次），不等即退回。
- **派工时点**：V5′ 三式活体结束后（`domain.sh` 无其它写者，且不与活体量测抢 CPU）。

**本轮收束与四态**：V5′ 已开跑并过了 prep（`rc(prep)=0`；`kin-v5p-host` 于 `16:09:16Z` 建成、`7565` 个 blob 与宿主一致；header 打印 `domain.sh = e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954`、桥 jar = `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`，两值逐字对上 §2.49 的硬核口径），三式 `armed/control-off/ghost` 的读数待下一格记录，**私有卷读数不得冒充 sealed bundle**；CI 已读到 `909`（`edfd8c5`）与 `908`（`012f56b`）均 `completed success`，`906/907` 亦绿；真实封证仍 **0**；本轮 lane 材料零改动、`#62 H1n` 仍未派（`domain.sh` 现由 M 只读、V5′ 在飞）、`#58 (乙)` 待引擎窗；未连用户远程服、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删。

## §2.51 V5′ 三式活体读数入册：控制词在专服形状下真的改动了被探者的位置与朝向、默认关闭时不动，而「问一个从未到场的名」在日志面上与「没问」不可分辨（第五十六轮第三格，2026-09-28 00:24 +0800，M 主控；私有本地卷 `minekin-m-v5p-live`，规范卷 `minekin-runner-data` **未挂载**，桥 jar 以 `:ro` 挂入，未连用户远程服）

**逐字记录**：`docs/validation/v1201-lan-joiner-local-control-readout-2026-09-28.md`（三式并列表、复算式、材料落点、两处 M 侧驱动缺陷的具名申报都在里面；材料 `.tmp/v5p/out-host/<shape>/` 未删，私有卷未清理）。本轮是**私有卷活体读数**，不是 sealed bundle，不进 `mandatory`/registry，也不支撑任何 `tested` 晋级。

**三式的判别面（同一 `domain.sh` 字节 `e04524d6…`、同一钉值桥 jar `e50d61c2…`）**：

| 式 | 差异 | `server.log`（sha256 前 8 / 行数） | `Kin` 答题行 | `Kin2` 首→末位置 | `Kin2` 末朝向行 |
| --- | --- | --- | --- | --- | --- |
| `armed` | 三名齐发（yaw 45 / pitch -20 / hold-forward 2s） | `c6052d38` / 294 | 84 | `[10.5,-60,-9.5]` → `[4.399447156,-60,-3.399447156]` | `[45.0f, -20.0f]` |
| `control-off` | 三名全部 unset | `975ecd6d` / 286 | 84 | `[10.5,-60,-8.5]` → `[10.5,-60,-8.5]`（未动） | `[0.0f, 0.0f]` |
| `ghost` | `armed` + `MINEKIN_DOMAIN_PROBE=Ghostz` | `d7bfbcdc` / 289 | **0** | 有位移 | `[45.0f, -20.0f]` |

1. **判据 4（控制词生效）在活体路径上成立且非恒真**：`armed` 的朝向末值与两个赋值逐字相等、位置发生位移；默认关闭的 `control-off` 两项都不动 ⇒ §2.5 的断言第一次拿到活体证据（此前只有契约与静态判定）。
2. **H1m 的第二具名目标在活体上真被回答**：`armed` 同一份 `server.log` 里 `Kin` 84 行、`Kin2` 82 行，时间戳交错。
3. **`ghost` 式给出缺口二的最强证据**：`grep -c 'Ghostz' .tmp/v5p/out-host/ghost/server.log` = **0**、`answer-lines-Kin.txt` **0 字节**、`domain-stderr.log` 里也没有一句关于该名——「探过一个不存在的名字」与「没探」在服务端日志面上**不可分辨**。能把「本 run 问过谁」写进 bundle 的唯一通道是 `--probed-player` 交回（H1i 第②格；`tools/seal_run_evidence.py:929` 收参数、`:337–:338` 拼命令面、`:721` 带进 `run_asserter` 已在位），而 `domain.sh` 三式的 (c) 格全是 `(no probe-target line)` ⇒ §2.43 缺口二在活体路径复现。
4. **两枚 M 侧驱动缺陷具名申报（不改判据、不改材料）**：`.tmp/m-r56-v5p-all.sh` 记的 `rc(live)=0` 是 `drive.sh` 末段 `| tee` 的管道状态，权威值取每式打印的 `V5P: domain.sh rc=14`（`domain.sh:2731` `status=$?` → `:3090` `exit`，三式同为 14 ⇒ 不作判别量）；`drive.sh` 的 (d) 名单写死 `[host, join, PROBE_SECOND]`，本形状下 `join == PROBE_SECOND` ⇒ `Kin2` 那格重复打印两遍（数值一致）。⇒ 顺带一条给 M-C1 的口径：三式 `server.log` 行数 289/286/294 不等（探测节奏与时长的差），**行数是噪声、行内容是判据**。

**次序随之更新**：V5′（#47）收完 ⇒ H1i（#52）的两个前置（V5′ 结束、`domain.sh` 无其它写者）此刻都成立，下一格即派工；`#62 H1n` 与 H1i **同改 `domain.sh`** ⇒ 二者不得并行，排到 H1i 复审入干之后再派。真实封证仍 **0**；本轮零 gradle、零新容器构建、规范卷未挂、未连用户远程服、未放宽认证/地址/lease/判据、材料与失败材料未删、lane 材料零改动。

## §2.52 M-C1 的判据形状在今日字节上量清了：三段链已存在、唯一缺的是 `server.log` 载体；而「两名同 run」会把名字盲的位移判据变成**为错误的 Kin 作证**，所以新案必须落在**单名探测**的形状上（第五十七轮第二格，2026-09-28 00:31 +0800，M 主控；全程只读仓库字节 + 只读 §2.51 的私有卷材料，零容器、零 JVM、lane 材料零改动）

**为什么现在量**：M-C1（#48）排在 H1i 之后，而它的判据此前只写到「按名答题行的内容差分」。§2.51 的三式材料落盘后，可以把这句话逐字段钉死，也能提前暴露一个会做出坏 case 的陷阱。

**判据链已经在 `tools/assert_case_evidence.py` 里，不需要新造**（检查名→实现，登记面 `check_case_assertions.py:305–:307`，已在用的案：`tests/fixtures/cases/core-040.json`、`v1201-040.json`）：

1. `move_input_was_leased :1602–:1618` —— 账本要有 `INPUT_LEASE_GRANTED` 且 `capability == MOVE_CAPABILITY`，否则 `NO_LEASE_GRANTED` / `LEASE_IS_NOT_FOR_A_MOVE:<caps>`（§2.51 的加入者账本事件序列里 `InputLeaseGranted` 与 `InputReleased` 都在）。
2. `the_bridge_carried_the_input_out :1621–:1633` —— 读**本 run 自己的文档** `run.actions_applied / actions_refused`。§2.51 三式实测：`armed` 加入者文档 `applied=2, refused=0`；`control-off` `applied=0`；`ghost` `applied=2`；三式的**宿主**文档都是 `applied=0` ⇒ 该格在这一族形状上非恒真，且默认关闭式会落到 `NOTHING_WAS_APPLIED`。
3. `the_server_saw_the_kin_move :1647–:1661` —— `probe_readings(material.server_log, 3)` 取首末两次位置、按 `_horizontal :1636–:1644`（忽略 Y）比对 `MINIMUM_STEP_BLOCKS = 2.0`。**这一格正是 H1i 第①格要喂的**：`server_log` 载体在加入者侧今天为空。

**陷阱（本轮量出来的，不是推的）**：`_PROBE = re.compile(r"has the following entity data: \[([^\]]*)\]")`（`:246`）**不带名字**——它收日志里所有三元组。把 §2.51 的三份 `server.log` 按名拆开算：

| 式 | 三元组读数 | 名字盲 首→末 水平位移 | 按名拆开 |
| --- | --- | --- | --- |
| `armed` | 83 | **3.926** | `Kin` 42 次 = 3.926；`Kin2` 41 次 = **8.627** |
| `control-off` | 82 | 0.000 | `Kin` 0.000；`Kin2` 0.000 |
| `ghost` | 40 | 8.627 | 只有 `Kin2`（探的是 `Ghostz`，宿主名 0 次） |

⇒ `armed` 那份日志上，名字盲算出的 3.926 是**宿主自己走的那一段**，而加入者真实位移是 8.627。一个加入者案若直接复用第 3 格，就会拿宿主的成绩替加入者作证——而且两式的数都 `> 2.0`，**看不出问题**；只有把名字拆开对照才看得见（`control-off` 两项都是 0.000，所以「控制词是否生效」这一维仍判得对，坏掉的是**归属**这一维）。同族第 4 格 `the_probed_player_is_this_run_s_kin :1664–:1690` 更进一步：`probed_players` 多于一个就 `MORE_THAN_ONE_PLAYER_PROBED:<names>` ⇒ **两名 run 里这条现有检查根本不可能通过**（H1i 第②格交回两名时必被它拒）。

**⇒ M-C1 的卡面据此钉死为「单名探测形状」**：新案的活体形状取 `MINEKIN_DOMAIN_PROBE = <加入者本人的名>` 且**不设** `MINEKIN_DOMAIN_PROBE_SECOND`。`ghost` 式恰好是这一形状的现成证据：日志里只剩该名的 40 次答题行，名字盲 ≡ 按名，污染面消失，且 `the_probed_player_is_this_run_s_kin` 在「恰一名且是本 run 的 Kin」上通过。判据四项落为：`move_input_was_leased` + `the_bridge_carried_the_input_out` + `the_server_saw_the_kin_move`（位移 8.627 ≫ 2.0，默认关闭式 0.000 ⇒ 反例在位）+ `the_probed_player_is_this_run_s_kin`（需 H1i ①② 才有载体）。**不新增、不改名、不放宽任何一条现有检查的口径**；朝向那格（`[45.0f, -20.0f]` = 两个赋值）今天**没有任何检查读它**（`probe_readings(..., 3)` 只收三元组，二元组被丢掉），要不要为它加一条具名检查属于 M-C1 的实现选择，登记新案不外溢旧案。
复算式：`grep -n "MINIMUM_STEP_BLOCKS\|_PROBE = \|def move_input_was_leased\|def the_bridge_carried\|def the_server_saw\|def the_probed_player" tools/assert_case_evidence.py`，位移按名拆解式见 `.tmp` 里本轮所用的 `N = re.compile(r"INFO\]: (\S+) has the following entity data: \[([^\]]*)\]")` 读法（输入 = `.tmp/v5p/out-host/*/server.log`）。


## §2.53 H1i 交付、M 按真实 merge-base 独立复审入干（合并 `b243366`，远端已核）：门载荷 PRE==POST 的第七、八次同值，三枚具名拒止在容器里逐字复现——而交付同时把两处真实前置缺口量了出来 ⇒ 开 #63 H1o / #64 H1p（第五十八至六十一轮收束，2026-09-28 02:05 +0800，M 主控；规范卷只 `:ro`，lane 树全程只读未改）

**为什么这一节先摆事实链**：H1i 改了 `domain.sh`（封存命令面）与契约（+604 行），是本项目里最靠近「门载荷」的一次 runner 改动；复审必须让每个结论都有 M 自己的退出码，而不是转抄 lane 的表。

**① 事实链（逐笔先量后写）**

- lane 交付：树 `../minekin-wt-h1i`，分支 `codex/minekin-h1i-probe-target-handover`，HEAD = **`9cd58aa`**（`docs(lan-control): hand H1i's four counterexamples as live private-volume readouts, plus the gate table`），`git status --porcelain` **空**，分支远端 ref = `9cd58aa` ⇒ lane 自己提交、自己推送，两格实现笔为 `9e7e47d`。M 全程未代提交、未清理、未 reset。
- 真实 merge-base：`git merge-base main 9cd58aa` = **`b35bc370982f222d0774bc1a8568c7671b63f61d`**。lane 两笔合起来的 diffstat = `domain.sh +161` / `tests/contract/test_runner_scripts.py +604` / 新验证文档 `+224` ⇒ **985 insertions, 4 deletions**（`diff --stat` 全貌在 `.tmp/m-r58-h1i-post-gates.log` 首段）。
- M 的合并笔：**`b2433665f5a06543f2e3a3282c3c6e4e626efa33`**（`--no-ff`），合入字节与 lane 提交**逐字节相同**：`domain.sh = df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2`、契约 `= daecfa01a5827534fd6db6eb8c70e3a09659804748cbfe88dfd2b9f4af7da471`；两把 tools 面未动（`seal_run_evidence.py = 4970381c…`、`assert_case_evidence.py = d89bf64b…`）。
- push 与远端核对：`git -c credential.helper= -c credential.helper=wincred push origin HEAD:main` 后 `git ls-remote origin refs/heads/main` = **`b243366…`**（本地 `main` 已快进到同一 SHA，不是只推不跟）。CI 一次读（REST，`.tmp` 无泄漏项）：`916 168cc67`、`917 4776f26`、`918 9cd58aa` 全 `completed/success`；`919 b243366` 写本节时点为 `in_progress` ⇒ **不作绿，须重读**。

**② PRE / POST 门表（M 亲跑，逐条单步、先读退出码再写这里）**

| 门 | PRE（主干 `b35bc37`，`domain.sh e04524d6…`） | POST（合并字节 `b243366`，`domain.sh df86c258…`） |
| --- | --- | --- |
| `bash -n domain.sh` / `bash -n run.sh` | rc=0 / rc=0 | rc=0 / rc=0 |
| 契约 `tests/contract/test_runner_scripts.py` | rc=0 `94 passed in 18.81s` | rc=0 **`118 passed in 15.43s`** |
| `check_case_assertions.py` | rc=0 `150 registered` | rc=0 `150 registered`（未动 registry） |
| `check_boundaries.py` / `verify_fixture_digests.py` / `check_workflow_pins.py` | rc=0 ×3 | rc=0 ×3 |
| `ruff check` / `ruff format --check` | rc=0 / rc=0（369 files） | rc=0 / rc=0（**371 files**） |
| `pyright` | rc=0 `0 errors` | rc=0 `0 errors` |
| 全量 pytest | 本轮未跑（PRE 侧以 `916` 的 CI 绿为据） | rc=0 **`2700 passed, 2 skipped in 284.54s`** |
| 容器内 `report_promotion --data-root /data`（规范卷 `:ro`） | rc=1、103,921 B、`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` | rc=1、103,921 B、**同一枚 sha256**（第七、八次同值） |
| `git diff --check HEAD~2 HEAD` | — | rc=0 |

工装与原始日志：`.tmp/m-r57-h1i-pre-gates.sh`/`.log`、`.tmp/m-r58-h1i-post-gates.sh`/`.log`（工作树内绝对路径 `C:/Users/darling/Documents/agent_work/minekin-wt-integration/.tmp/`，逐条 `run()` 把 rc 落盘后才允许被 prose 引用）。两份 payload 也留存：`.tmp/m-r57-h1i-pre-payload.json`、`.tmp/m-r58-h1i-post-payload.json`，各 103,921 B。

**③ 默认关闭面在合并字节上的实证（这是 H1i 卡面的承重格，不是 lane 的自报）**：`world_args=()` 仍恰 **2** 处（`:2869`、`:2934`）；`--probed-player` 在 `domain.sh` 的 6 处命中**全部落在 guard 与注释内**（`grep -n` 上下文逐条在 `.tmp/m-r58-h1i-post-gates.log`）；不设两枚旋钮 ⇒ 加入者侧封存命令与 PRE 逐字节等值，这一格由「门载荷 sha 不变」与「`world_args=()` 计数不变」两侧同时兜住。

**④ 三枚具名拒止由 M 在容器里复现（`--entrypoint /bin/bash`，`/src:ro`，无加入者 JVM 到场）**——消息逐字、`domain_rc=2`（材料 `.tmp/m-r60-h1i-refusals.log`）：

1. `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=maybe` ⇒ `domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG must be 1/true or 0/false, got maybe`
2. `MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=2` ⇒ `domain: MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS must be 1/true or 0/false, got 2`
3. `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=1` + `MINEKIN_DOMAIN_CASE_ON=host` ⇒ `domain: … hands the server log back to a case sealed on the joining run and this run seals its case on the host (MINEKIN_DOMAIN_CASE_ON is host); the hosting branch already carries this directory, so the switch would do nothing here`

「先拒后写」的行号证明在第五十九轮已入册并随合并字节复核：新拒止面 `:219`/`:230`（取值）、`:540–:561`（第①格三种形状）、`:905–:984`（第②格空名 / 非法名 `^[A-Za-z0-9_]{3,16}$` / 集合与数量不符），而脚本第一处落盘是 `:1230 mkdir -p /data/kin/${joiner}/run/session`（其后才 `:1492`、`:2681`、`:3183`）⇒ 四枚拒止按构造都早于任何写。

**⑤ tools 侧正/负对照由 M 自量（不取信 lane 的 `collect` 表）**：`.tmp/m-r58-carrier-control.py` 以 `importlib` 装载 `tools/seal_run_evidence.py` 后直接调 `collect_artifacts` ⇒ 给目录时多出 `['server/server.log', 'server/server.properties']`（`usercache.json` 受「在才收」约束，M 的样本目录里没有它，lane 的真实 run 目录里有），不给目录时只剩 `['orchestrator-trace.json', 'run-document.json']`；`SERVER_LOG_ARTIFACT = server/server.log`（`assert_case_evidence.py:744`）。同一份日志按名拆行：`Kin` 84、`Kin2` 82，总 166 = **83 位置三元组 + 83 朝向二元组**（探测行成对，读数行数是被读名字数的两倍——记忆 `project-probe-answer-line-pairs` 在合并字节上再次成立）。**该脚本第一次运行失败并已如实留档**：`importlib` 装载后不注册 `sys.modules["sealer"]` 会在 `@dataclass(slots=True)` 处抛 `AttributeError: 'NoneType' object has no attribute '__dict__'`（记忆 `project-joiner-seal-log-carrier`）。

**⑥ 交付暴露的两处真实前置缺口（按目标要求保留失败材料并开窄卡，不翻口径求绿）**

- **#63 H1o — `run.sh` 不转发两枚旋钮**：在合并字节上 `grep -c "MINEKIN_DOMAIN_SEAL" test-orchestrator/runner/run.sh` = **0** ⇒ 经 `run.sh` 的规范入口根本到不了这两格；契约 `tests/contract/test_runner_scripts.py:82` 的 `SEAL_HANDOVER_KNOBS` 是**精确缺口登记**（`:197` 断言 `read - delivered == SEAL_HANDOVER_KNOBS`，注释 `:194` 明写「在同笔删除该登记时必须一并转发」）。⇒ M-C1（#48）与 E7（#49）的**可派工前置此刻未满足**：活体形状若走 `run.sh`，旋钮只能靠容器 `-e` 直连 `domain.sh`，那不是被封的入口。允许面 `test-orchestrator/runner/run.sh` + 契约同笔；起点 `b243366`；门载荷须仍 `cfa0f118…63afd6`；全量 pytest 基线 `2700 passed, 2 skipped`。
- **#64 H1p — 战役路径在专服形状下封不出加入者 bundle**：lane 的 `.tmp/h1i-live/out-host/ce_ab/30-campaign-switch-{on,off}.err` 两枚**逐字相同**的失败：`{"message": "the run that hosted this world did not record a world of its own", "schema_version": 1, "status": "unsealed"}`。M 按字节复核互锁来源：`seal_run_evidence.py:426–:434` 在递了 `--world-run-document` 而该文档没有世界快照时抛 `Unsealable`（注释 `:432–:433` 明确「given and says nothing ≠ not given」），而去掉该文档又撞上 `:735` 的守门（要求 `server_profile` 与 `world_run_document_path` **同时**缺席才放行）⇒ 加入者侧在 `--enable-status` 专服形状下**两条路都封不出**（H1k 的宿主 run 不写世界快照，正是 `:426` 那支拒的因）。反面对照：绕开战役路径的 dev-seal 形状**能封出**——`ce_ab2/70-reprint.txt` 里 switch-on 的 bundle 含 `server/server.log`（`size=10633`、`sha256=628b36b5…`、manifest 与盘上字节一致），`asserter-inputs.json` 的 `probed_players=['Kin']` 而该 run 的 `username='Kin2'`，且 `MANIFEST result="FAIL"`。**这段读数的边界要说死**：它是 lane 私有卷 + 容器里的 dev-seal 产物，**未进规范卷 ⇒ 不是 sealed bundle，更不是晋级**；`result=FAIL` 恰说明载体到位不等于判据点头。
  - 由 `probed_players=['Kin']` vs `username='Kin2'` 这一对现读还能提前否掉一种坏 case：即使第②格交回了名字，只要活体形状仍用**默认问宿主名**，现有检查 `the_probed_player_is_this_run_s_kin` 就不可能通过 ⇒ §2.52 钉的「单名探测形状（`MINEKIN_DOMAIN_PROBE=<加入者本人的名>` 且不设 `PROBE_SECOND`）」是 M-C1 的**硬前置**，不只是防名字盲污染。
  - #64 的收卡判据：量清 `:426–:434` × `:735` 互锁下 E7 到底能封哪种形状（战役路径 / dev 路径 / 需要宿主 run 补世界快照），**若结论要求放宽封存口径 ⇒ 停下申报，属主控保留决策**（记忆 `project-controller-reserved-decisions`），lane 与 M 都不得自行改 `world` 记录的语义。

**⑦ 次序与四态**：H1i（#52）收口 ⇒ 下一格 **H1o（#63）**，其后才轮到 **M-C1（#48）**，再 E7（#49）需先有 H1p（#64）的可封形状判定；`#62 H1n` 与 H1o 不同文件（`domain.sh` vs `run.sh`）⇒ 可与 H1o 并行开树；按合并字节重读它的目标行是 **`:2617`**（`if grep -qE "${kick} (lost connection|left the game)" \n            "${server_directory}/server.log" 2>/dev/null; then`），§2.43 里的 `:2430` 与更早的 `:2472` 都是历史行号——H1i 的 `+161` 行把它推下去了，再次实证「行号不是字节」；`#58 (乙)` 仍待引擎窗。**真实封证仍 0**（LAN 第二客户端在受控专服形状下的同 run 封证未动；私有卷 dev-seal 读数不得冒充 sealed bundle）。已合主干且待读绿 = `b243366`（CI `919` 写本节时 `in_progress`）；仅在分支 = lane 的 `h1i`/`h1l`/`h1m` refs（均不删）。未验证 = H1o 全卡、H1p 全卡、M-C1 全卡、E7 全卡、M-G1 全卡、#58 (乙)。本轮 M 侧零 gradle、零新构建；容器只以 `:ro` 挂源码与规范卷读门载荷；未连用户远程服、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、lane 材料与失败材料零改动未删。


## §2.54 H1p 的判定：专服形状下加入者侧封存**只剩一条可封形状**（交回 `--server-profile` + `--server-directory` 并按形状弃 `--world-run-document`），而三条退路各自撞在字节上——是否采纳这条改口径属**主控保留决策**，本轮不实施（第六十二轮，2026-09-28 02:20 +0800，M 主控；只读主干字节 + 规范卷 `:ro` 的 100 份已封 bundle，零容器活体写入、零 JVM）

**为什么这格必须 M 自己量**：E7（#49）是「独占规范卷的同 run 封证」，它要求 `case_on=joiner`；而 §2.53 记下战役路径两枚 `unsealed` 时只给了现象。判「E7 能不能封、要改哪一格」之前，得先把「加入者侧的 bundle 到底靠什么命名世界」量到构造级。

**① 世界块的三条来源与它们各自的落点（`tools/seal_run_evidence.py:395–:444`，按判定顺序）**
- 路线 1 `:422–:424`：本 run 自己的文档带 `run.world_snapshot` ⇒ `kind: lan`。
- 路线 2 `:426–:435`：给了 `--world-run-document` ⇒ 取**宿主**文档的快照；`world_snapshot(宿主文档)` 为 None 时 `:434` 抛 `Unsealable("the run that hosted this world did not record a world of its own")`。
- 路线 3 `:437–:442`：给了 `--server-profile`（`target` 非 None）⇒ `kind: dedicated`、`config_digest = target.revision`、`name = world_seed(server_directory)`（目录缺席才是 `none`；seed 读不到记 `unrecorded`，`:141–:157` 明写「缺席照实记，不拿配置值顶替」）。
- 都没有 ⇒ `:444` `kind: none` + `EMPTY_DOCUMENT_SHA256`。

**② 为什么专服形状下路线 2 结构性不通（不是「这次没跑到」）**：`src/minekin_core/cli/session.py:644–:657` 只在**核心会话自己播种世界**（`world_save is not None and world_name is not None`）时才写 `world_snapshot`；H1k 形状的服务端是 `domain.sh` 直接起的受控专服，核心从不播种 ⇒ 宿主文档**永远**没有 `run.world_snapshot` ⇒ `:427` 取到 None ⇒ `:434` 必抛。而加入者支 `domain.sh:3073` 是**无条件**递 `--world-run-document /tmp/domain-session.json` 的 ⇒ 只要 `case_on=joiner`，今日字节在专服形状下**必**拒。lane 的两枚 `ce_ab/30-campaign-switch-{on,off}.err` 逐字同值正是这条构造的两次实例（旋钮开否都不影响：拒在世界判定，早于 artifact 收集）。

**③ 两条看着像出路的退路，字节上都堵**
- 「干脆不递 `--world-run-document`」：`:735` 的守门在 `server_profile` 与 world 文档**同时**缺席时生效，读的是本 run 文档的 `connection_state` / `snapshots_admitted` 与台账里的 `PLAYABLE_ESTABLISHED` ⇒ 加入者跑到 PLAYABLE 就撞（注释 `:740–:742` 自己写明「Without that input this guard is what refuses a join」）。再退一步只交目录（= H1i 第①格现状）：`evidence.py:188–:195` 的 `WORLD_RECORD_INCONSISTENT` 顶住——**lane 的 `ce_ab2/50-switch-off.err` 就是这一枚**（`bundle.py:113` 抛出），而 switch-on 能封出 bundle 是因为那次把世界字段留空的路径没走到这条一致性检查（`MANIFEST world fields` 三格皆 null）。
- 「让 `:428` 把『给了文档但文档没说世界』当成『没给』往下走路线 3」：`:411–:419` 的 docstring 就是把这条否定掉的——它记了一次真实测量（Kin 在 `kinworld` 里并已在 25570 发布，却封成 `kind: "none"` + 无之摘要），并写明「否认 Kin 生活过的世界的 bundle 比描述一个没人去过世界的更糟，因为旁边的 run 记录说不是」。**这判据不放宽。**

**④ 规范卷 100 份已封 bundle 的现读（正对照齐备，`.tmp/m-r61-worldscan.log`，脚本 `.tmp/m-r61-bundle-worldscan.py`，容器只 `:ro` 挂卷）**
- 世界块分布：`dedicated` **81** / `lan` **11** / `none` **8**。
- **`probed_players` 在 100 份 bundle 的 `asserter-inputs.json` 里全部缺席**（`recorded: none`）⇒ `the_probed_player_is_this_run_s_kin`（`assert_case_evidence.py:1664–:1690`）今日对每一份已封 bundle 都只能回 `PROBE_ATTRIBUTION_NOT_RECORDED`（H1i 第②格之前按构造如此）。
- **加入者侧封证的全部历史**就是那 6 份 `CORE-030`（`kin-02`×2、`kin-04`×2、`kin-e-rr-seal`、`kin-e-rr-seal2`；`username` 为 `Kin2` 或无），它们**全部**是路线 2 的产物：`kind: lan`、`name = 5c14c5638566a8b3f3`（宿主快照摘要）、**且一律没有 `server/server.log`**。⇒ 路线 2 只在「宿主真发布过世界」的 LAN 形状里成事，正是 §2.49/§2.50 的旧地图。
- **路线 3 的正对照在卷上是真实的、且与目录载体共存**：`V1201-020` 的 `73a52bfb8f24…`（E6 的本地专服单客户端封证）为 `kind: dedicated`、`name = minekin-p0-control`、`server_config_digest = 77a19c94…`，**同一份 bundle 里 `server/server.log` 在列**。⇒ 「profile 命名的世界 + 日志载体」这个组合不是新造语义，而是卷内 81 份的常态。
- 附注（要留给 H1q 实测的，不是本轮结论）：路线 3 的 `name` 取自 run 目录里 vanilla 落定后的 `level-seed`——同批 bundle 里既有 `minekin-p0-control`（V1201-040/V1201-080/V1201-020），也有 `unrecorded`（`ADMIT-110`，PASS 且照常入册）⇒ 采纳路线 3 时须量 1.20.1 受控专服的 run 目录落在哪一侧；`unrecorded` 是合法记录而非伪造，但它进不进 M-C1 的判据要另判。

**⑤ 判定（E7 的可封形状）**：**唯一**可封形状 = 路线 3 的形状门版——加入者支在「本 run 确实起了那个被加入的专服」（`server_profile` 非空，且 H1i 第①格的三枚拒止已把 `case_on != joiner`（`:547`）/ profile 缺席（`:552`）/ black hole（`:556`）三种形状挡在前面，整段守门 `:546–:561`）时，把 `world_args` 交成 `--server-profile "${server_profile}" --server-directory "${server_directory}"`（`--server-jar` 仍**不**交：这一支不挂载 jar，`domain.sh:3035–:3040` 只在宿主支补它），并**同时弃** `--world-run-document`（否则 `:426` 先拒）。`--server-profile` 缺席时保持今日的完全丢弃 + 递 world 文档 ⇒ LAN 形状逐字节不变。

**⑥ 为什么本轮不实施**：它改的是「加入者 bundle 的世界块允许由谁命名」——§2.43 补记与 §2.50 把「绝不带回 `--server-profile`/`--server-jar`」定成默认口径，理由是「profile 会让封存记下一个不同种类的世界」。该理由在 LAN 形状成立、在 H1k 专服形状**恰好不成立**（那枚 profile 就是本 run 起的那台专服，也就是加入者真站进去的世界）。**把口径按形状分裂是一项封存语义裁决**，按本项目纪律属主控保留（记忆 `project-controller-reserved-decisions`；同一类先例：`project-offline-100-triple-not-judgeable-by-construction` 的扩 schema、`project-bundles-do-not-pin-orchestrator-bytes` 的加 seal 字段）⇒ 本轮只落判定与卡面，不动 `domain.sh`。
- **⇒ 新卡 #65 H1q（V1201-JOINER-WORLD-BY-DEDICATED-PROFILE-001）**：允许面 `test-orchestrator/runner/domain.sh` + 本族契约测试；形状门如上；须带具名拒止（至少：`--world-run-document` 与 `--server-profile` 同时在场 ⇒ 拒；旋钮打开但 profile 缺席 ⇒ 沿用 `:553` 那句；LAN 形状 ⇒ 逐字节不变）；默认关闭 ⇒ 门载荷仍须 `cfa0f118…`、`check_case_assertions` 仍 `150 registered`、加入者侧封存命令与今日逐字节相等。**开工前置 = 主控对该口径的裁决**（本卡只写形状，不预先实施）。

**⑦ 次序随之定死**：**H1o（#63，在飞）⇒ M-C1（#48）可跑**（它冻结判据并登记新案，载体面 H1i 已给；但登记会动门载荷，须量 PRE/POST 并具名）；**E7（#49）在 H1q 的口径裁决落地前不可开跑**——它要求 `case_on=joiner` 的同 run 封证，而 §2.54 ②③ 表明该封证在专服形状下今日**按构造**封不出。E7 不得改用 `case_on=host` 顶替（宿主支封的是 `Kin` 这一格，`the_probed_player_is_this_run_s_kin` 会把「探加入者名」的案拒在归属那一格（`assert_case_evidence.py:1687`：本 run 的 `username` 不在 `probed_players` 里即 `PROBED_PLAYER_IS_NOT_THIS_RUN_S_KIN`）），也不得拿卷外/私有卷的 dev-seal 产物充数。M-G1（#50）为只读审计，排在 E7 之后。真实封证仍 **0**；本轮零 JVM、零 gradle、零容器写入，规范卷只 `:ro`（读 bundle 不写），未连用户远程服、未读 `.tmp/local-test-server.txt`、未放宽认证/地址/lease/判据、未翻 `mandatory`/registry、材料与失败材料未删、lane 树只读未改（`../minekin-wt-h1o` 归 H1o lane，M 未入其工作面）。

**§2.54 具名更正与时点申报（同轮 02:20 +0800，M 主控；不静默覆盖）**：① §2.53 的落笔时点原写 `02:30 +0800`，本笔量到该记录笔 `b9b0d25` 的 commit date 实为 **`2026-09-28 02:05:12 +0800`** ⇒ 标题里的钟点改为 02:05（笔误，不是两个事件）。② §2.53 记「`919 b243366` 写本节时点为 `in_progress` ⇒ 不作绿」是 **02:06 的真实读数**，予以保留；02:18 一次 REST 重读（`.tmp/m-r61-ci.json`）为 `919 b243366 completed/success（updated_at 2026-09-27T17:59:46Z）`、`920 b9b0d25 completed/success` ⇒ **H1i 合并笔与其记录笔都判绿**，「已合主干且 CI 绿」前进到 `b9b0d25`。本轮（H1p）改面恰两份文档，未动 `domain.sh`/`run.sh`/契约/tools。

## §2.55 H1o 交付、M 按真实 merge-base 独立复审入干（合并 `77fd13d`，远端已核）：契约的 delivered 方向三笔反证非恒真，跨界改由「换回 trunk 包装器」做实对照，门载荷第九次同值（第六十三轮，2026-09-28 02:45 +0800，M 主控；私有卷 `minekin-m-r63-live`，规范卷只 `:ro`，lane 树全程只读未改）

**① lane 事实链**：lane 树 `../minekin-wt-h1o`、分支 `codex/minekin-h1o-forward-seal-knobs`、起点 `b9b0d25`（= 派工时的远端 `main`）。交付为单笔 `f84d4c397130f20a767e13a83eba2b9b5db4a4c0`（commit date `2026-09-28 02:22:14 +0800`），远端分支 SHA 与本地一致、lane 工作树干净、`.tmp/h1o/` 材料在位（25 项）。**真实 merge-base = `b9b0d25`** ⇒ 主干在 lane 起飞后只多出文档笔 `6fb974b`，与代码面无交叉；合并后 `git diff f84d4c3 HEAD` 只剩那两份文档（48 insertions / 1 deletion）。lane diffstat 恰三文件：`test-orchestrator/runner/run.sh` 14+/1-、`tests/contract/test_runner_scripts.py` 30+/29-、新 validation 记录 198+/0-；`domain.sh` 与 `tools/**` **0 行**——合并字节上复算 `df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2` / `4970381c…` / `d89bf64b…`，逐字节等于主干。转发名单现 25 枚 `-e MINEKIN_DOMAIN_*`，末两枚即 `:146` `:147` 的 `SEAL_JOINER_SERVER_LOG` / `SEAL_PROBED_PLAYERS`，均为裸 `-e NAME`、不铸默认值。

**② 门表（POST 全部是 M 在合并字节上单跑亲量，材料 `.tmp/m-r63-h1o-post-gates.log`；PRE 出处逐格具名，未亲量的不写「同值」）**

| 门 | POST rc | POST 末行读数 | PRE 出处（同一命令） |
| --- | --- | --- | --- |
| `bash -n domain.sh` / `bash -n run.sh` | 0 / 0 | 无输出 | lane §6 同命令 0；`domain.sh` 本笔 0 改动 |
| 契约 `pytest tests/contract/test_runner_scripts.py` | 0 | `118 passed in 16.06s` | **本轮亲量 `6fb974b` ⇒ `118 passed in 15.94s`**（同数） |
| `check_case_assertions` | 0 | `OK (150 registered)` | `.tmp/m-r62-doc-gates.log` 同读数 |
| `check_boundaries` / `verify_fixture_digests` / `check_workflow_pins` | 0 / 0 / 0 | 三条 OK | 同上 |
| `ruff check` | 0 | `All checks passed!` | 同上 |
| `ruff format --check` | 0 | **372** files already formatted | 上轮同树 371 ⇒ +1 的成因见 ④，不作代码面漂移 |
| `pyright` | 0 | `0 errors, 0 warnings, 0 informations` | 同上 |
| 全量 `pytest -q` | 0 | `2700 passed, 2 skipped in 289.55s` | 主干基线 2700/2 **同数**；lane 自报 2699/3，判定见 ⑤ |
| `git diff --cached --check`（提交前） | 0 | 无输出 | — |
| 容器只读 `report_promotion --data-root /data` | **1**（按构造 blocked，本卡不注册 case） | 文档 103,921 B、`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` | §2.53/§2.54 的 PRE 同值 ⇒ **PRE==POST 第九次同值**，门载荷一字未移 |

**③ 契约非恒真：M 亲跑三笔（材料 `.tmp/m-r63-h1o-reversals.log`，全程在 M 自己的树里，破桩前 `cp` 备份 + 记 sha256，复原后按 sha 复验，不用 `checkout`/`restore`/`reset`/`stash`）**

- **M1** 摘掉 `run.sh` 的 `-e MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG` 一行 ⇒ `bash -n` 仍 0、契约 **rc=1**，红消息逐名：`domain.sh arms the seal handover on MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG and run.sh stopped delivering it: … evidence for a different shape than the one the operator asked for`（`1 failed, 117 passed`）。
- **M2** 只删 `SEAL_PROBED_PLAYERS` 前面的 `-e` 前缀（数组元素退化成裸词，语法仍合法）⇒ 契约 **rc=1**、逐名同一句式 ⇒ 两枚各自被钉，删一枚不会靠另一枚蒙过。
- **M3** 把 `domain.sh` 里的读取整体改名 ⇒ 契约 **rc=1** 且首条红消息走 `domain.sh no longer reads …` 支，同时同族另外三段具名拒止断言一起转红 ⇒ `in read` 方向也是活的，不只有 `in delivered`。
- 三笔复原后：`run.sh = 93642dd3…`、`domain.sh = df86c258…` 与破桩前逐字节相同，`git diff`（worktree vs index）0 行，契约回到 `118 passed`。
- 断言的**强度方向**核过：旧面是「每枚必须缺席于 `run.sh`」+「`read - delivered == SEAL_HANDOVER_KNOBS`」，新面是「每枚必须在 `run.sh`」+「`read - delivered == set()`」⇒ 精确登记缺口退役，但集合仍 exact、`delivered - read == set()` 与 config.py 外溢断言原样保留，缺任何一枚都红。

**④ `ruff format --check` 的 371→372 实测归因**：ruff 0.16.8 的 `format` 遍历把 markdown 一并计入（`ruff format --check docs/validation/v1201-h1o-forward-seal-knobs-2026-09-28.md` ⇒ `1 file already formatted`）⇒ 新增一份 validation 文档就给这个数 +1；lane 现字节同命令亦报 **372**（与它 §6 自报 371 只差在它自己落笔文档的前后）。此后引用该数须说明它是文档面敏感的，不能当代码面漂移的证据。

**⑤ 全量 pytest 差一格的判定（M 亲量到条件本身）**：lane `2699 passed, 3 skipped` vs M `2700 passed, 2 skipped`，收集总数同为 2702 ⇒ 无增删测试函数。差异实测落在 `tests/unit/test_tested_provenance.py:354` 的 `BRIDGE_1201_JAR_RELATIVE_PATH` 条件跳过：M 树有 `bridge-1201/build/` 与 loom 缓存（本机建过 1.20.1 桥），lane 新树只到 gradle wrapper ⇒ 那一格在 lane 上 skip。M 树单跑该文件族读数 `60 passed, 2 skipped`（两条 skip 具名为 `test_silent_listener.py:123`「a Windows terminate is not a signal」与 `test_orphans.py:686`）⇒ lane §6.1 的「平台/材料条件、非本卡因果」归因成立，不追环境、不改数字。

**⑥ docker 边界的反对照（H1o 卡面本体，M 不采信 lane 自报；材料 `.tmp/m-r63-boundary.log`）**：私有卷 `minekin-m-r63-live`（新建，规范卷 `minekin-runner-data` 不出现在这两条命令里），发前 `docker ps` 空列表核验。同一 env（`MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=maybe` + `PROBE=PROBE_SECOND=kin-mr63dup`）、同一参数（`domain session start --profile /src/tests/fixtures/launcher/1.20.1.json`）：

- **正例（合并后 `run.sh`，`93642dd3…`）** ⇒ **rc=2**，stderr 里 SEAL 句恰 **1** 次：`domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG must be 1/true or 0/false, got maybe`。该句只可能由容器内 `domain.sh` 的取值 case 打印 ⇒ 值确实经 `-e` 跨过了 `docker run` 边界，且它**抢在**同命令更晚的重复名守卫之前回答。
- **反对照（同形状，只把包装器换成 `git show b9b0d25:test-orchestrator/runner/run.sh` 的临时副本 `323f521a…`，跑完即删）** ⇒ 同样 **rc=2**，但 stderr 中 SEAL 句 **0** 次，落到更晚的 `MINEKIN_DOMAIN_PROBE_SECOND` 重复名守卫。这一格比「不设旋钮」的负对照更强：它把差异**钉在包装器字节上**，直接证明 H1o 之前战役路径问不到这枚旋钮、run 会带着「not asked for」继续走下去。
- 两发前后卷清单各 3 条、逐条相同 ⇒ 拒止确实早于任何落盘。合入后 `grep MINEKIN_DOMAIN_SEAL src/minekin_core/config.py` ⇒ 空 ⇒ 产品入口面 0 外溢。

**⑦ 次序随之更新**：H1o 入干 ⇒ 战役路径今日**设得了**这两枚旋钮，**#48 M-C1 解锁可跑**（它冻结 §2.52 的单名判据并登记 `V1201-LAN-JOINER-CONTROL-CASE-001`；登记必动门载荷 ⇒ 量 PRE/POST 并具名申报，不改旧案 `core-040`/`v1201-040`）。**E7（#49）仍不可开跑**：转发只解决「设不设得了」，不解决 §2.54 判定的「专服形状封不封得出」——它阻塞在 **#65 H1q 的主控口径裁决**之上。真实封证仍 **0**。CI：`6fb974b`（文档笔）与 lane 分支 `f84d4c3` 均已 completed/success，合并笔 `77fd13d` 的读数写在 handoff 本轮。

## §2.56 M-C1 落地并分两笔入干（`4a5d353` 登记 + `163e350` 注册）：`V1201-LAN-JOINER-CONTROL-CASE-001` 以 §2.52 的单名四格冻结，门载荷第十次、第十一次连两次同值——并且这一格「同值」这次带正对照：把「入册必动门载荷」改判为「只有 `REQUIRED_CASES` 点名的行才动载荷」（第六十四轮，2026-09-28 03:30 +0800，M 主控；只读规范卷 `:ro`、零容器活体、零 JVM、lane 树全程未碰、不连用户远程服）

**⓪ 为什么分两笔**：§2.12 要求「每笔量 case_version 与门载荷前后差」，而本卡的改动天然有两个面——判据名册（`tools/` 两行）与案本身（fixture + manifest 行 + 测试）。合在一笔就只能回答「这六行字节合起来动没动门」，答不出「注册名册动没动门」。于是先只暂存两枚 `tools/` 文件提交（`4a5d353`，2 files / +3 行），再把 C2 的三份文件按备份字节复原后提交（`163e350`，3 files / +177 行），**每笔的读数都在那一笔自己的字节上取**：取 C1-only 读数时把 C2 三文件 `cp` 进 `.tmp/m-r64-c2stage/` 并记 sha256（`.tmp/m-r64-c2stage.sha`），manifest 与测试文件写回 `git show HEAD:<path>` 的字节、新 fixture 移出 cases 目录（`.tmp/m-r64-c2stage-removed-fixture.json`），量完逐份 `sha256sum -c` 复验回来（`493faf67…` / `47d13f93…` / `f4b94e03…` 三份 OK），全程不用 `checkout --` / `restore` / `reset` / `stash`。
C1-only 字节上的读数（`.tmp/m-r64-c1-gates.log`）：`check_case_assertions` ⇒ `OK (151 registered)` rc=0、`verify_fixture_digests` ⇒ OK rc=0、`pyright` ⇒ `0 errors` rc=0、`pytest tests/unit/test_case_evidence_assertions.py tests/unit/test_case_registry.py tests/contract/test_runner_scripts.py -q` ⇒ `695 passed in 24.68s` rc=0；容器只读规范卷 ⇒ rc=1、103,921 B、`cfa0f118…`（与 trunk 同值）；载荷里新案名出现 0 次；case_version 全表 52 行与 PRE 逐行同值（`.tmp/m-r64-caseversions-C1.txt`，CR 归一后 diff 空）⇒ **只补名册不让任何旧案版本漂移**。

**① 冻结的形状落在字节上**（判据形状由 §2.52 钉死，本节不改它，只把它写成登记）：

- `tests/fixtures/cases/v1201-lan-joiner-control-case-001.json`（文件名 = `case_id.lower()+".json"`，`tests/unit/test_case_registry.py:224–:243` 的派生规矩）：`work_package W60`、`mandatory false`、inputs 为 `bundle-candidate-1.20.1.json` + `controlled-offline-server-1.20.1.json`（与 `v1201-040` 同一对受审 recipe / 受控 world pin），assertions 按 §2.52 的链序四条：`move_input_was_leased` → `the_bridge_carried_the_input_out` → `the_server_saw_the_kin_move` → `the_probed_player_is_this_run_s_kin`。
- 两枚注册表各补一行：`tools/check_case_assertions.py:308` 的 `_runtime("the_probed_player_is_this_run_s_kin")`、`tools/assert_case_evidence.py:4162` 的 `ASSERTIONS` 同名条目。**这两行都是 M-C0 允许面之外的遗留**（M-C0 交付了函数本体，注册面属本卡），补上后 `test_the_registry_and_the_asserter_name_the_same_assertions` 两侧仍相等，登记枚数 `150 → 151 registered`。
- `tests/fixtures/manifest.sha256` 追加一行 `afe9aa015722452d05e23660536fae70e2260e9b56e6f08e45b94528c0fa0a57`（= 该 JSON 的 CRLF→LF 归一字节摘要，88→89 行；`FROZEN_PATTERNS` 含 `tests/fixtures/**/*.json` ⇒ 漏行即 `unlisted frozen file` 事故）。
- **§2.12 那句「断言至少覆盖首快照 / 释放后停止」在本案里没有落进 assertions**，具名申报而非静默：那两格今天分别由 `V1201-020`（`first_snapshot_admitted` + `leave_after_join_observed`）与 `the_lease_expired_and_was_released` 承担，而 §2.52 把这张卡的判据四项钉为「租约→桥接搬运→服务端位移→位移归属」，理由是位移格 `the_server_saw_the_kin_move` **名字盲**（`_PROBE :246` 不收行内名），两名同 run 时第 4 格必拒 ⇒ 冻结的形状只能是单名探测。旧口径下作废的读数为「新案自带首快照/停止」——它从未有过，本轮也没有把它写进去。

**② 先拒后写（不拿叙述当证据）**：把 cases 目录整份 `cp` 成草稿副本（`.tmp/m-r64-nodigest-cases/`），只在新案那一份里用正则摘掉 `assertion_digests` 块（`.tmp/m-r64-strip-digests.py`，897→451 B），再 `check_case_assertions.py --cases-dir <草稿>` ⇒ **rc=1** 且四条逐名 `V1201-LAN-JOINER-CONTROL-CASE-001: assertion_digests has no entry for <name>`；同一命令指向真实目录 ⇒ rc=0、`151 registered`。⇒ 「摘要块是判据的门槛而不是装饰」是量出来的（材料 `.tmp/m-r64-reversals.log` 的 R0 段）。
**`--record` 的作用域实测**：写前/写后对 53 份 case 文件逐个 sha256 列表（`.tmp/m-r64-cases-before.txt` / `-after.txt`）⇒ **只有新案那一份**移动，其余 52 份逐字节相同；`git status` 亦只列出新文件。三枚共用判据的记录摘要与 `core-040`/`v1201-040` 里的值逐字符相同（`e1ec3b7c…` / `ef4e96df…` / `c9adaf98…`），新格为 `05e9ea31…` ⇒ 旧案标准一字未移，不触发重封全卷（[[project-reseal-is-atomic]]）。
**case_version 全表差分**：`git archive HEAD` 取出登记前的 cases 目录，两侧都用 `load_case_registry(...).cases[].digest` 打印（`.tmp/m-r64-caseversions-{PRE,POST}.txt`）⇒ 52 行逐行相同，只多出 `V1201-LAN-JOINER-CONTROL-CASE-001 1e31f0003b4e30e06506e086616335db73ec975b406874d219033f151b3f812a`。中间态也量了：C1-only 字节的表（`.tmp/m-r64-caseversions-C1.txt`，52 行）由与 `src/minekin_core/domain/cases.py:731` 同式的内联重算（`sha256(json.dumps(doc, sort_keys=True, separators=(",",":")))`）得到，它与 PRE 那份走 `load_case_registry` 的表逐行同值 ⇒ 两套算法互证，且版本漂移只发生在新增的那一案上（名册笔 0 行、注册笔 1 行）。

**③ 反证三格 + 正对照，全部落在单测面上（§2.16 要求「不靠卷」）**：`tests/unit/test_case_evidence_assertions.py` 末节新增 6 条（该文件 `493 passed`）。共享的 `material()` 多了一个可选的 `probed_players=`，并**经 `ASSERTER_MODULE.recorded_probed_players` 归一**而不是在测试里抄一份排序去重规则。

- 正对照：单名形状（只探这一 run 自己的 Kin，位置三元组首末水平差 8.627 块，取自 §2.51 私有卷真跑的那个数）⇒ `result PASS`、`failures ()`、`unimplemented ()`、`observed == expected`。
- 反证 1 归属名换成主持有者 ⇒ `the_probed_player_is_this_run_s_kin:PROBED_PLAYER_IS_NOT_THIS_RUN_S_KIN:Kin2`。
- 反证 2 申报集合含第二人 ⇒ `…:MORE_THAN_ONE_PLAYER_PROBED:Kin,Kin2`。
- 反证 3 首末读数改成相同 ⇒ `the_server_saw_the_kin_move:MOVED_LESS_THAN_A_STEP:0.00`，**且另三格保持绿** ⇒ 这一格区分的是「没被驱动」而不是「什么都没记下来」。

**④ 仪表非失灵：三笔破桩反证（材料 `.tmp/m-r64-reversals.log`；每笔先 `cp` 备份 + 记 sha256，复原后按 sha 复验，不用 `checkout`/`restore`/`reset`/`stash`）**

- **M-A** 把 `the_probed_player_is_this_run_s_kin` 改成恒 `None` ⇒ 恰反证 1、2 两条转红（`FAIL → PASS`），正对照与反证 3 不动。
- **M-B** 把 `MINIMUM_STEP_BLOCKS = 2.0` 改成 `0.0` ⇒ 恰反证 3 转红，其余不动。（第一版补丁没打上：那三行读取在位移格与转向格里各出现一次，锚点不唯一——按定义行改锚后才成立，量到 `count == 2` 才动手。）
- **M-C** 摘掉 `check_case_assertions.py` 的新注册行 ⇒ 门 **rc=1** 且具名 `names an assertion nothing implements: the_probed_player_is_this_run_s_kin`，同时「四条判据命名一致」那条元测试转红 ⇒ 注册行本身被钉，不是装饰。
- 三笔复原后 `assert_case_evidence.py = 8e358d1e…`、`check_case_assertions.py = 9c0e4470…` 与破桩前逐字节相同，`git diff --numstat` 回到本卡的 +2 / +1 行。

**⑤ 门载荷：PRE==POST 第十次同值，这次配了正对照，所以它是读数而不是仪表失灵**

| 量 | 出处 | 结果 |
| --- | --- | --- |
| PRE | `5795600` 代码字节上的 `.tmp/m-r63-post-payload.json`（上轮在合并字节上亲量） | `gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、103,921 B、`rc=1`（按构造 blocked） |
| POST | 登记后的树，规范卷 `:ro` + 工作树 `:ro` 容器内 `report_promotion --data-root /data`（`.tmp/m-r64-post-payload.json`，提交前；`.tmp/m-r64-c2-payload.json`，C2 复原字节复量） | 同尺寸、同 `rc=1`、**同摘要**（第十次与第十一次连读两次同值）；26 行逐格表 diff 为空（`.tmp/m-r64-cells-{pre,post}.txt`）；新案 id 在整份载荷里出现 **0** 次 |
| 正对照 | 同一命令，只把 cases 目录换成「删掉 `core-040.json` 的副本」（`.tmp/m-r64-positive-control.log`） | 摘要 `→23b3631e…`；`W60 promotable True→False`、`blocks -→REQUIRED_CASE_NOT_REGISTERED`、`p0-core.absent 9→10`、`overall.blocking 28→29` |

⇒ **具名更正 §2.16 的前置口径**：「入册必动门载荷 ⇒ 先量后量各一次」只在**这一行属于 `REQUIRED_CASES` 策略**时成立。历史上 `OFFLINE-070` 入册确实把 W30/p0-core 的 `absent` 挪动过（它本来就在 required 名单里，见 `test_the_070_row_is_registered_without_being_made_mandatory` 的说明）；而一张 `mandatory:false`、不在 required 名单里的新案，按构造不会出现在 `work_packages`/`overall` 的任何一格——载荷只由 required 名单与卷上被引 bundle 驱动，新案两者都不是。量的规矩保留（仍逐格 diff），断言的强度降级为「若动则必须能指名是哪一格的哪一行」。
**登记生效的正面读数在 `report_cases`**（不挂卷也能跑，`.tmp/m-r64-report-cases-{pre,post}.json`）：`cases 52→53`、`assertions 194→198`、`by_judge.run-material 32→33`，而 `mandatory 7→7`、`required 74→74`、`required_present 46→46`、`required_missing 28→28` 一字未动 ⇒ 「注册看得见、门不吃它」是同一次量测的两面，不是遗漏。

**⑥ 门表（每道单跑、先读退出码再落笔；材料 `.tmp/m-r64-local-gates.log`）**

| 门 | rc | 末行 | 与登记前 |
| --- | --- | --- | --- |
| `ruff check .` | 0 | `All checks passed!` | 同 |
| `ruff format --check .` | 0 | **372** files already formatted | 同数（本卡只加 `.json` 与测试函数，ruff 不收 `.json`；§2.55 ④ 的「文档面敏感」口径继续适用） |
| `check_boundaries` / `verify_fixture_digests` / `check_workflow_pins` | 0/0/0 | 三条 OK | 同 |
| `check_case_assertions` | 0 | `OK (151 registered)` | 150 ⇒ +1，即本卡的全部注册面 |
| `pyright` | 0 | `0 errors, 0 warnings, 0 informations` | 同 |
| 全量 `pytest -q` | 0 | `2706 passed, 2 skipped in 286.48s` | 基线 2700 passed, 2 skipped ⇒ +6 条本卡新测试，无旧测试转红 |

两笔各自的复量：C1-only ⇒ `check_case_assertions 151 registered` / `verify_fixture_digests OK` / `pyright 0 errors` / 定向三文件 `695 passed`，全 rc=0（`.tmp/m-r64-c1-gates.log`）；C2 复原字节 ⇒ `pyright 0 errors`、`pytest -k "joiner or probed_player or asked"` `44 passed`、`ruff check` 与 `ruff format --check`（本笔 3 文件 `already formatted`）全 rc=0（`.tmp/m-r64-c2-gates.log`）。提交前各自读 `git diff --cached --check` ⇒ rc=0。

**⑦ 落点与次序**：两笔已入干——`4a5d353`（名册）、`163e350`（注册），`git push origin HEAD:main` 后 `ls-remote` 读回 `163e350d3213aa6b7bc429489fb33efbf2f78917`，`5795600..163e350`；CI run `36344057387` 首读 `in_progress`、重读 `completed/success`（`head_sha=163e350`、`run_attempt=1`），`python`/`protocol`/`bridge-static` 三 job 按 ci.yml 自有步骤逐步核过全 `success`（jobs 端点留存 `.tmp/m-r64-ci-jobs.json`）⇒ **「已合主干且 CI 绿」前进到 `163e350`**。M-C1 入册 ⇒ **E7（#49）的前置里「case 已在册」这一格闭合**，其余前置不变——它仍阻塞在 **#65 H1q 的主控口径裁决**（§2.54：专服形状下加入者侧只剩一条可封形状，采纳与否属主控保留决策），且 E7 必须是同一 run 的字节同时供给控制侧与读数侧。**真实封证仍 0**：本节新增的是一个**能判的案**，不是判定结果——判据在单测材料上绿，在卷上没有任何一份 bundle 引用它。文档顺序上下一个可动的是 **M-G1（#50，E7 之后的只读审计）**，其「改前」半张已在 §2.14 落档；未开工存量：`#62 H1n`（`domain.sh:2617` 字面 `\n` ⇒ kicked 可假绿）、`#58 (乙)`。本轮不碰 mandatory / registry / 晋级，不连用户远程服，私有卷读数不当作 sealed bundle。

## §2.57 #62 H1n 的派工前量材：`domain.sh:2617` 的字面 `\n` 在整棵 `test-orchestrator/` 里是**唯一**一处「命令位裸词」，而它双向都坏——有 `n` 文件 ⇒ 假绿 `rc=0`，无 `n` 文件 ⇒ 错误码 2 被 `2>/dev/null` 一起吞掉；顺带记 M 自己那枚普查脚本的死循环（第六十五轮，2026-09-28 04:05 +0800，M 主控；只读仓库字节 + 主机 bash 临时目录，零容器活体、零 JVM、lane 树只在它的 `.tmp/` 写过材料，不连用户远程服）

**⓪ 远端与 CI 时点**：`main = 9fe3eb455a6a68a80c782f666e0fc6065ec55efd`，其 CI run `36344447789`（`run_number=926`）读回 `completed/success`，jobs 端点留存 `.tmp/m-r65-ci-jobs-9fe3eb4.json`，三 job 按 `ci.yml` 自有步骤逐步核过全 `success`（`python` 15 步：`uv sync --locked --dev`、`ruff check`、`ruff format --check`、`pyright`、`pytest`、`check_boundaries`、`check_case_assertions`、`verify_fixture_digests`、`check_workflow_pins`、`uv build --wheel`、`check_wheel_boundary`、`minekin --help`；`protocol`：buf build/lint/format + 校验签入的 Python protobuf；`bridge-static`：3 步）⇒ **「已合主干且 CI 绿」前进到 `9fe3eb4`**。
**具名更正（不 amend）**：`9fe3eb4` 自己的 commit message 把 `163e350` 的 CI 运行号写成了 `16344057387`，正确值是 `36344057387`——该笔正文里（§2.56 ⑦ 与 handoff 第六十四轮）的数字是对的，只有 message 手误。按纪律用新提交具名更正，绝不 `--amend`。

**① 缺陷字节（行号当场重读，不沿用别节）**：`grep -nE '[[:space:]]\\n[[:space:]]' test-orchestrator/runner/domain.sh` ⇒ 只命中一行；同一命令在整棵 `test-orchestrator/` 递归也**只命中这一行**：

```
2617:        if grep -qE "${kick} (lost connection|left the game)" \n            "${server_directory}/server.log" 2>/dev/null; then
```

⇒ 契约扫描的判据形状就取「**两侧留白的裸词 `\n`**」，零误报、也不需要注释豁免。对照口径：判据若放宽成「行内任何位置出现反斜杠紧跟字母 n」，该文件命中 **201 行**（复跑：`grep -cE '\\n' test-orchestrator/runner/domain.sh` = 201），绝大多数是 `printf`/`tr` 串内的合法换行 ⇒ 判据若取松口径必假红一片。这就是卡面把判据写死成命令位裸词的原因，也是给 lane 的正对照（合法串内换行样本必须命中 0）。

**② 语义双向读数**（主机 bash 临时目录，材料 `.tmp/m-r65-kick-grep-shape.log` 与 `.tmp/m-r65-kick-grep-shape2.log`，同名 `.sh` 可复跑；`grep (GNU grep) 3.0`）：

| 量 | 形状 | 读数 | 判读 |
| --- | --- | --- | --- |
| 词表 | `for w in "${pattern}" \n server.log` | `[Kin (lost connection|left the game)] [n] [server.log]` | `\n` 就是一个裸词 `n` ⇒ grep 的第二操作数 |
| 假绿 | `server.log` **无** kick 句 + 内容为 `Kin lost connection` 的文件 `n` | `false_green_test_server_says_nothing_n_says_kick=0` | `kicked=1` ⇒ 报 `domain: the server ended the session while the client kept running` |
| 错误码被吞 | `server.log` 无句 + **无** `n` 文件 | `shipped_shape_with_n_absent=2`（不是 1） | `if` 只看非零 ⇒「grep 报错」与「没发生」在字节上不可分辨 |
| 真信号（起点形状） | `server.log` 含句 + 无 `n` | `A_shipped_kick_present_no_n_file=0` | 起点形状不是恒假，改判据前它是靠匹配文件拿到 0 的 |
| 修复形状 + 假绿环境 | 真续行 + `n` 在场 + `server.log` 无句 | `fixed_shape_server_says_nothing_n_present=1` | 假绿消失 |
| 修复形状对照 | 真续行 + `server.log` 含句 | `fixed_shape_server_says_kick_present=0` | 非恒真：真读数没被一起抹掉 |

**③ 伤害面按构造只到读数**：`kicked` 在 `:2623–:2627` 只决定打印哪一行 stderr，既不置 `injection_failed` 也不参与 outcome；但这行读数在 `test-orchestrator/runner/README.md:834` 被当成可观察量登记 ⇒ 修它是**撤掉一枚假绿的来源**，不解锁任何封证。lane 的交付记录不得写成「修好后某案可判」。

**④ 派工落点**：`../minekin-wt-h1n`（分支 `codex/minekin-h1n-kick-grep-literal-n`，起点 `9fe3eb4`；`git worktree add` 后 `git status --porcelain` 为空，`domain.sh` 摘要 `df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2` 与集成树逐字节相同 ⇒ ①②的读数对该起点直接有效）。卡面 `.tmp/h1n-brief.md`；允许面恰两文件（`domain.sh` 一处续行 + `tests/contract/test_runner_scripts.py`）加 `.tmp/h1n/**` 与一份 `docs/validation/v1201-h1n-delivery-2026-09-28.md`；两笔提交**先红后绿**（红段原文落 `.tmp/h1n/contract-red.log`）；门表逐道单跑读 rc；门载荷 PRE/POST 必须仍 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（`domain.sh` 不在载荷输入面）；只 push 自己的分支，M 不代提交不代合并。M 侧基线材料 7 份已放进 `.tmp/h1n-baseline/`（扫描器 + 两枚形状脚本与日志 + `trunk_digest.py`）。

**⑤ M 自己那枚普查脚本首版死循环（记账，不删）**：首版 `unquoted_spans()` 用变量 `quote` 记录引号状态，跳过带引号区间后**没有复位成 `None`** ⇒ 从第一条含引号的行起外层 `while` 既不推进也不退出，整脚本无限循环。连挂三次（两次后台 `uv run`、一次 `timeout 45`）我都先把原因猜成「lane 树要建 venv／引擎忙」，实际是脚本自己的 bug。定位姿势值得固化：同一棵树里 `timeout 60 uv run --frozen --offline python -c "print('hello')"` 秒回 rc=0 ⇒ 嫌疑才锁到脚本本身。**两条教训**：① 普查工具同样需要对照与超时归因，hang ≠ 环境；② 引号状态机必须在闭引号处复位，而且这种 naive toggle 对 `backend="… $(printf "%s" "${probe}" | tr "\n" " " …)"` 的嵌套写法本就不精确——修好复位后它仍把 `:1425` 报成命中（`bare-word literal backslash-n outside quotes=2`）。⇒ 最终契约判据**不依赖引号识别**，只用「两侧留白」一个条件，误报面为零（1 命中且正是缺陷行）。

**⑥ 次序与欠账**：#62 H1n 在飞；E7（#49）与 M-G1（#50）仍阻塞在 **#65 H1q 的主控口径裁决**（§2.54：专服形状下加入者侧只剩一条可封形状——把 `--server-profile` + `--server-directory` 交回加入者侧并按形状弃 `--world-run-document`）。它改的是**证据口径**（加入者 bundle 的「世界」由谁命名），不是实现细节，按主控保留口径本轮不实施，已向用户申报并列出两条路（采纳 ⇒ 开 H1q 再 E7；不采纳 ⇒ E7 只能停在跨 bundle 形状，队列在此分裂）。`#58 (乙)` 待引擎窗。**真实封证仍 0**，M-C1 入册只让「有案可判」成立，没有产生判定。

## §2.58 H1n 交付、M 按真实 merge-base 独立复审入干（合并 `c1f6518`，parents `7d97188`+`fdd9f88`，merge-base `9fe3eb4`）：判据复算 + 破桩反证 + **把提交字节逐字提出来驱动语义**，门载荷第十二次同值——并记下 M 自己在复跑时踩到的转义陷阱（第六十六轮，2026-09-28 04:35 +0800，M 主控；规范卷只 `:ro` 跑一次只读 `report_promotion`，零容器活体、零 JVM、未连用户远程服）

**① 允许面与出处核查**：分支对 merge-base 只动 3 个路径——`test-orchestrator/runner/domain.sh`（+2/−1，只有 `:2617` 那一处续行）、`tests/contract/test_runner_scripts.py`（+92：1 枚测试 + helper + 两枚判据常量）、`docs/validation/v1201-h1n-delivery-2026-09-28.md`（+111）。合入时的硬核查式照旧成立：`git show fdd9f88:test-orchestrator/runner/domain.sh | sha256sum` = `16124b5bf3a18b2985d14ca27bf2514d3f630fe4db60827abb4b274e35988401`，与合并工作树读数、与 lane 报告**三者同值** ⇒ 「活体/测试取自最终提交字节」这一格由 M 自证而非取信旁证。

**② M 复算判据（不取信 lane 的门表）**：`.tmp/m-r66-h1n-predicate-check.py` 用 `chr(92)` 构造字符、不依赖任何 shell 转义——
- 合并后工作树：`lines=3252 loose=200 bare_word=0`；
- merge-base 的 blob（`.tmp/m-r66-pre-fix-domain.sh`）：`lines=3251 loose=201 bare_word=1`，且报出的正是 `2617: … \n            "${server_directory}/server.log" …`。
⇒ 修复的净效果在字节上是「行数 +1、松口径 −1、命令位裸词归零」，与 §2.57 ① 的派工前量材首尾相接。契约测试断言的是 `loose > 0 且 bare_word == 0` 成对，而不是钉死 201 这个会随别的卡移动的数——这一点做对了。

**③ 破桩反证（M 在合并树上重跑那张卡的核心验收格）**：`cp` 备份 + 记 sha，再把缺陷逐字植入（`.tmp/m-r66-h1n-reversal.py`）——
- 植入后 `domain.sh` 摘要**恰好回到** `df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2`（= §2.57 ④ 记的起点摘要）⇒ 证明「这一处修复」在字节上就是一行，没有夹带；
- 新测试转红并具名：`AssertionError: a bare-word literal backslash-n survived in domain.sh (201 lines carry the loose shape; …)` + `domain.sh:2617: …`，`1 failed in 1.99s`；
- 还原后摘要回到 `16124b5b…`、测试 `1 passed`，`git status` 只剩合并本身。全程未用 `checkout`/`restore`/`reset`/`stash`。

**④ 按提交字节驱动语义（把 lane 的「谓词形状复现」升格为「驱动 domain.sh 自己的那四行」）**：`.tmp/m-r66-h1n-lifted-shape.py` 从文件里**定位并逐字提出** `:2617` 起的 grep 条件与 `kicked=1`/`break`，拼成可执行片段，在 cwd 里放一个内容为 `Kin lost connection` 的文件 `n`、另备两份 `server.log`（一份不含 kick 句、一份含）跑两式：

| 取字节的来源 | server.log 不含 kick 句 | server.log 含 kick 句 |
| --- | --- | --- |
| merge-base blob（缺陷形状） | `kicked=1`（**假绿复现**） | `kicked=1` |
| 合并后的 `domain.sh` | `kicked=0`（假绿消失） | `kicked=1`（**真信号未被抹掉**） |

材料 `.tmp/m-r66-h1n-lifted-prefix.log`、`.tmp/m-r66-h1n-lifted-merged.log`。两行表就是这张卡的验收判据：它同时排除「恒假」（修好了但也读不到真离场）与「恒真」（没修也报好）。片段里那句 `break: only meaningful in a loop` 是 M 包装器的产物，不是 `domain.sh` 的行为。

**⑤ 门表（M 在合并树逐道单跑、退出码单独读、日志落盘 `.tmp/m-r66-gate-*.log`）**：`bash -n domain.sh` rc=0；契约单文件 rc=0（`119 passed in 16.06s`）；新测试单枚 rc=0；全量 `pytest -q` rc=0（`2707 passed, 2 skipped in 297.39s` ⇒ 可比量 passed+skipped = **2709** = 基线 2708 + 本卡新增 1 枚；skip 与 lane 的 3 格差一格仍是 `test_tested_provenance.py:354` 的桥产物条件 skip，按旧口径归一后同值）；`ruff check` rc=0；`ruff format --check` rc=0（**373 files**，比第六十四轮的 372 多的唯一一格就是本卡新增的 `docs/validation/` 记录文件——ruff 0.16.8 把 md 计入文件数，lane 的 `ruff-format-final.log` 与 M 的读数同形，不是漂移）；`pyright` rc=0（`0 errors, 0 warnings, 0 informations`）；`check_boundaries`/`verify_fixture_digests`/`check_workflow_pins` rc=0/0/0；`check_case_assertions` rc=0（`OK (151 registered)`，本卡未注册案）。门载荷 POST（合并树、规范卷 `:ro`）= `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、103,921 B、`report_promotion` rc=1（按构造 blocked）⇒ **第十二次同值**，与 §2.56 的 PRE 面一致。

**⑥ 转义陷阱（M 本轮自己踩的，写成可复用的判据写法）**：通过本会话的命令层写 grep 判据时，单反斜杠形式 `'[[:space:]]\n[[:space:]]'`（bash 收到的是「一个反斜杠 + n」，ERE 把它读成**转义后的 n**，即匹配裸字母 n）会退化成匹配字母 n，于是 M 一度在合并树上「量到」一条新命中 `2773: n += 1; rss[n] = $2`——那是 awk 程序里的普通 `n`，不是字面反斜杠-n。同一形式作用在 merge-base blob 上时**没有**命中 `:2617`（真缺陷），这才暴露判据被转义层吞掉。**正确写法**：bash 单引号里要放两个反斜杠，即 `grep -nE '[[:space:]]\\n[[:space:]]'`（ERE `\n` = 一个字面反斜杠 + `n`）；更稳的做法是像 `.tmp/m-r66-h1n-predicate-check.py` 那样用 `chr(92)` 构造字符、绕开所有层。**通用后果**：任何以「反斜杠 + 字母」为判据的扫描，落盘前必须同时跑「缺陷 blob 必命中」与「修好的树必不命中」两式，缺一格就是假读数。

**⑦ 已申报偏差的处理口径（入册为一般规则）**：lane 的第二笔提交首次落盘为 `5f78720`，因 commit message 混入不应有的署名 trailer，在**分支尚未推送**的前提下用 `git reset --soft` 原地重做为 `3d95a31`，内容字节逐字不变（前后 `domain.sh` 摘要同为 `16124b5b…`）并已在交付记录 §0 具名申报 ⇒ M 接受。口径：**未推送的本地提交允许以 `reset --soft` 重做 message，但必须（a）具名申报旧 SHA 与原因，（b）证明内容面零改动（按路径摘要配对），（c）不对已推送提交做任何重写**。这不改变「绝不 `--amend`、绝不 `--no-verify`」的既有边界。

**⑧ 落点与次序**：`c1f651845ba0e42c7c561ec86f76a72d22203cbc` 已 push，`git ls-remote` 读回同值（`7d97188..c1f6518`）。CI：`7d97188` 的 run `36345957828`（编号 927）按 `ci.yml` 自有步骤逐步读为全 `success`（`python` 18 步、`protocol` 10 步、`bridge-static` 9 步，`non_success=[]`；jobs 原文 `.tmp/m-r66-ci-jobs-7d97188.json`）⇒「已合主干且 CI 绿」前进到 `7d97188`；本合并笔的 run `36348081759`（编号 **929**）落档时为 `in_progress`（只作时点申报，接手会话必须重读才可在文档写「合并笔 CI 绿」）。**E7（#49）与 M-G1（#50）仍阻塞在 #65 H1q 的主控/用户口径裁决**（§2.54 那条唯一可封形状：加入者 bundle 的「世界」由谁命名），M 不代决定；未开工存量剩 `#58 (乙)`（待引擎窗）。**真实封证仍 0**——本卡撤掉的是一枚读数面假绿的来源。

**⑨ 时点移动（补记，不改写 ⑧ 的读数）**：⑧ 落笔时合并笔的 run 929 是 `in_progress`；随后的重读把它读绿了——`36348081759` = `completed/success`，jobs 端点留存 `.tmp/m-r66-ci-jobs-c1f6518.json`，按 `ci.yml` 自有步骤逐格核对：`python` 18 步、`protocol` 10 步、`bridge-static` 9 步，三 job 的 `non_success` 列表均为空，`head_sha` 前缀 `c1f65184`、`run_attempt=1` ⇒ **「已合主干且 CI 绿」前进到 `c1f6518`**，H1n 没有把主干弄红是 M 自读而非 lane 自报。⑧ 里那句时点申报按「已落读数不改写」的口径保留。
## §2.59 主控对 §2.54 那格口径的裁决：**采纳**「按形状分裂」——专服形状下加入者 bundle 的世界块由**本 run 自己起的** `--server-profile` 命名，并据此派 #65 H1q（第六十七轮，2026-09-28 04:41 +0800，M 主控；只读仓库字节 + 只读 REST，零容器活体、零 JVM、未连用户远程服、未读 `.tmp/local-test-server.txt`）

**⓪ 落笔现场（脚本当场读，不凭记忆）**：远端 `main` = `354f34e`（`ls-remote` 回 `354f34e`），`domain.sh` 最后一次改动是 `3d95a31`（H1n），本轮起摘要 `\16124b5bf3a18b2…`、3252 行；Case assertion implementations: OK (151 registered)；记录笔 `354f34e` 的 CI run 930 = `completed/success`，三作业步数 {"bridge-static": 9, "protocol": 10, "python": 18}、`non_success=[]`（原文 `.tmp/m-r67-ci-jobs-354f34e.json`，第一次抓时 python 作业尚在 step 8，随后整读全绿 ⇒ §2.58 ⑧ 那格「未读绿之前不得写合并笔 CI 绿」在此闭合）。

**① 裁决**：§2.54 ⑤ 那条唯一可封形状**采纳**——加入者支在「本 run 确实起了那台被加入的专服」时，把世界输入交成 `--server-profile "${server_profile}" --server-directory "${server_directory}"`，并**同时弃** `--world-run-document`；`--server-profile` 缺席的 LAN 形状逐字节不变。`--server-jar` 仍**不**交（加入者支不挂载 jar，`domain.sh:3035–:3040` 只在宿主支补它）。
- **这格属主控、不属用户**：§2.54 ⑥ 把它判给「主控保留」，而本项目里主控就是 M（本会话）。用户在第六十六轮目标里给的口径是「按文档顺序推进 …E7、M-G1，前置不满足就保留失败材料并开对应窄卡」——E7 的前置正是这条口径，卡（#65）也已开；把它当作用户决策往上顶会停在原地。记忆 `project-controller-reserved-decisions` 保留的是**晋级门、V08/真实用户服、HOST 侧封存与实施**三样，封存形状不在其列。

**② 为什么只有这一条形状（三段都在字节上，不是「这次没跑到」）**
- **(a) 递宿主文档必拒**：`tools/seal_run_evidence.py:426–:434`——给了 `--world-run-document` 就取宿主快照，宿主无 `run.world_snapshot` 时 `:434` 抛 `the run that hosted this world did not record a world of its own`；而 `src/minekin_core/cli/session.py:644–:657` 只在核心自己播种时写该字段，H1k 形状的服务端由 `domain.sh` 直接起 ⇒ 按构造为空。加入者支今日无条件递（今日字节上是 `:3074` 那一行）⇒ `case_on=joiner` 在专服形状下**必**拒。
- **(b) 只交目录也封不出**：`_world_record` 的路线 3 在 `target is None` 时按 `kind: none` 走，而 `name` 取自目录（`world_seed`）⇒ `src/minekin_core/domain/evidence.py:189–:193` 的一致性判据 `no_kind != unnamed` 命中 `WORLD_RECORD_INCONSISTENT`（`bundle.py:113` 抛出）。这就是 H1p 量到的 `ce_ab2/50-switch-off.err`，也是 H1i 第①格「只补 `--server-directory`」在今日字节上的**唯一**结局——那一格本身封不出 bundle，它的价值在把载体（`server.log` 等三件）接进采集。
- **(c) 交 profile + 目录才自洽**：路线 3 的 `target` 非空 ⇒ `kind: dedicated`、`config_digest = target.revision`（非空）、`name = world_seed(目录)` ⇒ 三格同侧，`evidence.py:189–:193` 无 violation。规范卷 100 份 bundle 的现读（§2.54 ④）证明这不是新造语义：`dedicated` 81 份，其中 E6 的 `73a52bfb…` 同一份 bundle 里 `server/server.log` 在列。

**③ 这不是「放宽」，而是补完一个只有一半的口径**：`seal_run_evidence.py:411–:419` 的 docstring 否定的是「给了文档、文档没说世界 ⇒ 当成没给、往下走路线 3」，本裁决一处都不碰它——被弃的是**注定被 `:434` 拒**的那次递件，且只在 profile 在场时弃。§2.43 补记 / §2.50 那句「绝不带回 `--server-profile`」的理由是「profile 会记下一个不同种类的世界」，该理由在 LAN 形状成立、在 H1k 专服形状**恰好不成立**（那枚 profile 就是本 run 起的那台专服，也是加入者真站进去的世界）。默认关闭、LAN 逐字节不变、`:546–:561` 三枚拒止全保留 ⇒ 关闭态与今日等价。

**④ 复用现有旋钮 `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG`，不新开第三枚**：该旋钮打开时 `:552` 已保证 `server_profile` 非空、`:556` 已排除 black hole、`:547` 已要求 `case_on=joiner` ⇒ 打开态的**全部**可达形状都满足「profile 就是本 run 的专服」，交 profile 不需要新的守门；新开一枚只会给冲突矩阵添一对需要具名拒止的组合（记忆 `project-knob-conflict-named-refusals`）。代价是该旋钮的名字只说了「server log」而它从现在起交两件——所以 `:206–:210` 那段注释必须同步改写，且契约要按名要求两格同时在场。**回退条件（具名）**：若 H1q 的活体读数显示「只交目录」在某形状下能干净封出 bundle（即 (b) 被证否），本裁决作废、回到两枚旋钮的形状，失败材料留在 lane 的 `.tmp/` 里改名 `-FE1` 保存。

**⑤ 今日字节锚点（`grep -n` 现读；H1n 在 `:2617` 净 +1 行 ⇒ §2.54 里 `:2617` 之后的行号一律 +1）**
- 旋钮读法与取值判定：`domain.sh:206–:210`（注释，含「Only the directory」那句要改）、`:213–:222`（`seal_joiner_server_log_asked`）。
- 三枚拒止的守门区域：`:540` begin / `:546` `if asked` / `:547` `case_on != joiner` / `:552` `server_profile` 缺席 / `:556` black hole / `:561` end（区域名 `joiner-server-log-seal-guard`，契约按名提取）。
- 加入者封存支：`:3062` `world_run_args=()` / `:3074` 无条件递 `/tmp/domain-session.json` / `:3090–:3095` 区域 `joiner-server-log-seal-forge`（`:3091` 清空、`:3093` 只给目录）。**本裁决要动的两处**：`:3074` 的条件化与 `:3091–:3094` 的 argv；契约现在只提取 forge 区域 ⇒ 两处必须落在**同一具名区域**内（或新增第二个区域并在契约里逐名要求），否则「两格同时在场即拒」这条判据在契约面上读不到。
- 封存调用拼接：`:3192` `"${world_args[@]}"` / `:3194` `"${world_run_args[@]}"`；宿主支 `:3034–:3040`（对照用，不改）。
- sealer 侧：`tools/seal_run_evidence.py:426/:427/:434`（路线 2）、`:437–:442`（路线 3）、`:735`（profile 与 world 文档同时缺席时的守门）、`:141–:157`（`world_seed`，读不到记 `unrecorded`）；`src/minekin_core/domain/evidence.py:189–:193`。**这些本轮全部零改动。**

**⑥ #65 H1q 卡面（`V1201-JOINER-WORLD-BY-DEDICATED-PROFILE-001`）**
- 允许面两份：`test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`；交付记录另落 `docs/validation/v1201-h1q-joiner-world-by-dedicated-profile-2026-09-28.md`。**不动** `tools/`、`src/`、`tests/fixtures/cases/**`、`run.sh`（H1o 已转发该旋钮）。
- 改动：打开态下加入者支交 `--server-profile` + `--server-directory` 且不交 `--world-run-document`；关闭态逐字节等于今日（含继续无条件递宿主文档）；`:206–:210` 注释改写；新增具名拒止：**同一 argv 上 `--world-run-document` 与 `--server-profile` 同时在场 ⇒ `exit 2`**，且必须早于任何封存落盘（按 `project-knob-conflict-named-refusals` 的行号法对首次落盘证明）。
- 验收格：(1) 关闭态加入者封存 argv 与主干逐字节相等（契约提取比对）；(2) 打开态 argv 恰为两件、不含 world 文档、不含 `--server-jar`；(3) LAN 形状（profile 缺席）沿用 `:553` 那句；(4) 冲突拒止 `rc=2` + 具名 + 未落盘；(5) `bash -n` ×2 + `ci.yml` 自有步骤全表 + 契约；(6) **活体一读**（lane 自有私有卷，规范卷不挂）：专服形状 `case_on=joiner` + 旋钮开 ⇒ 真封出 bundle，并打印 `manifest` 的 `world_kind / seed_or_snapshot_id / server_config_digest` 三格与 `violations()`，回答 §2.54 附注那格（1.20.1 受控专服的 run 目录落 `minekin-…` 还是 `unrecorded`；`unrecorded` 合法但须具名入册）。
- 门基线（lane 的 PRE 必须与这些值逐字同源）：`domain.sh` 摘要 `\16124b5bf3a18b2985d14ca27bf2514d3f630fe4db60827abb4b274e35988401` / 3252 行；Case assertion implementations: OK (151 registered)；门载荷仍 `cfa0f118…63afd6`（第 12 次同值是在 `3d95a31` 之后的合并字节上量的，`354f34e` 起 `domain.sh`/`tools/`/`tests/fixtures/` 零改动 ⇒ 该值仍是当前基线）。POST 须与之配对：非 `REQUIRED_CASES` 的注册才不动载荷（§2.56），本卡不注册案 ⇒ 载荷必须仍同值。
- 只 push 自己的分支；M 按真实 `git merge-base` 独立复审后才合 `main`。

**⑦ 次序随之前进**：H1q（#65，本轮派）⇒ 复审入干 ⇒ **E7（#49）可开跑**（它要的就是 `case_on=joiner` 的同 run 封证，载体面 H1i、旋钮转发面 H1o、判据案面 M-C1 均已入干，形状面本轮裁决）⇒ M-G1（#50）只读审计排最后。空档仍做 #58 (乙)。**LAN 第二客户端在受控专服形状下的同 run 真实封证仍 = 0**；本轮零 JVM、零 gradle、零容器写入、规范卷未挂、未翻 `mandatory`/registry、材料与失败材料未删、未碰任何 lane 工作面（`../minekin-wt-h1n` 归 H1n lane）。

## §2.60 H1q 的复审判据在 lane 交付之前就写成了可复算脚本：把加入者分支**逐字提出来在桩环境里执行**，读 bash 真正拼出的 argv（第六十七轮补格，2026-09-28 04:51 +0800，M 主控；宿主 bash + 只读仓库字节，零容器、零 JVM、规范卷未挂）

**为什么不用文本扫描**：这张卡要判的是「旋钮开/关时封存调用拿到哪几个 argv」，注释、字符串、区域外的行都能骗过模式匹配。§2.58 ④ 已经用过一次更硬的办法——把提交字节提出来的执行——本轮沿用它：`.tmp/m-r67-h1q-joiner-argv-judge.py`（`report` / `compare --base --tip` / `mutate`）。它按 `if [ "${case_on}" = "joiner" ]; then` 起、到四个空格缩进的 `fi` 止切出整段加入者分支，配一份只含既有变量名的桩（`case_on/join_ready/player/join_username/server_profile/server_directory/black_hole/两枚 asked`），在 `set -u` 下跑两遍（`seal_joiner_server_log_asked=0/1`），打印 `world_args` 与 `world_run_args` 的**实际内容**。桩里若引用了新变量名，`set -u` 会直接把它暴露成 rc≠0，而不是静默漏判。

**校准三格（全部落在 `.tmp/m-r67-h1q-judge-calibration.log`，脚本 `.tmp/m-r67-h1q-reference-shape.py`）**
- **(甲) 主干今日字节 = 判官必须报出 §2.59 ② 的两格**：`domain.sh` 摘要 `16124b5bf3a18b29…`（与派工值同值；校准副本落在 `.tmp/m-r67-shape/trunk`）；`closed: branch :3063+34 sha=7767e883 rc=0 world_args=[] world_run_args=[--world-run-document /tmp/domain-session.json]`；`open: branch :3063+34 sha=7767e883 rc=0 world_args=[--server-directory /tmp/domain-run/server] world_run_args=[--world-run-document /tmp/domain-session.json]` ⇒ faults=2，逐字为 `open state does not hand --server-profile` 与 `open state still hands the host run document (route 2 refuses it)`。**这就是「打开态今日封不出 bundle」在 argv 面上的形状**（②(a)/(b)）。
- **(乙) 采纳形状必须被判官接受**：把 `:3074` 的无条件递件挪进 `else`、`world_args` 改交两件（profile + directory），`bash -n rc=0`，打开态读到 `open: branch :3063+41 sha=6b37342e rc=0 world_args=[--server-profile /tmp/domain-join-profile.json --server-directory /tmp/domain-run/server] world_run_args=[]`，faults=0；`compare --base trunk --tip adopted` 给出 `VERDICT accept`，且关闭态 argv 逐字不变（`--world-run-document` 仍在、`world_args` 仍空）。⇒ §2.59 ⑤ 的形状在 bash 里**可满足**，卡面不是空要求。**注意坑**：这一版把弃件写成 `else` ⇒ 冲突守门成为死码；真交付若同形，契约的「删掉该分支必红」变异格（卡面 §4.3）必须自己抓到它，判官不代替契约。
- **(丙) 非恒真对照**：另造 `both-handed` 形状（保留 `:3074` 的递件，同时打开态交 profile + 目录）⇒ 冲突守门真触发，`rc=2` 且 stderr 打出那句具名拒止，判官报 `open state exited rc=2`。⇒ 「两格同时在场即拒」这条判据有判别力，不是恒真也不是恒假。

**判官自己的两处首版缺陷（当场修，记账以免重犯）**：① 提取起点原先锚在 `subject_document=` 那一行 ⇒ 切出来的片段少了 `if … then`，bash 报 `syntax error near unexpected token 'fi'`，而 `classify` 把它翻译成「关闭态不再递宿主文档」的假故障——**没有这条 rc≠0 的读数，一次语法错误就会被我当成形状判定**；现锚在分支开句，并要求 `subject_document=` 必须落在片段之内。② `compare` 原先拿区段 sha 判「关闭态未变」⇒ 源码面必然变（多一个分支），行为面才是等值；改为只比 `rc / world_args / world_run_args`（与 [[project-v1201-lan-control-queue]] 里「行号不是字节」同族：**sha 也不是 argv**）。③ 顺带记一次编号口径：`report` 起初把 1-based 行号自加了两遍（显示 `:3064`，`grep -n` 实为 `:3063`），已修。

**四态增量**：本轮 M 只写这两份主干文档与自己的 `.tmp/`（判官、参考形状、校准日志）；`domain.sh` 与契约测试零改动（校准副本全在 `.tmp/m-r67-shape/`，摘要 `16124b5b…` 仍与派工时同值）；lane 树未碰；规范卷未挂；未连用户远程服；未动 mandatory/registry/晋级；材料与失败材料未删。**真实封证仍 0**。

## §2.61 H1q 复审入干（合并 `f5b239e`，parents `483eb76`+`efd3169`，真实 merge-base `354f34e`，远端已核）与加入者支的**活体封证**：打开态真封出 bundle、§2.54 附注那格答了——同时 M 自己 §2.59 ②(b) 的机制判定被本轮量到**证否**，④ 的回退条件按字面触发（第六十八轮，2026-09-28 06:35 +0800，M 主控；M 私有卷 `minekin-m-v5p-live` 活体 + 规范卷只 `:ro`，未连用户远程服、未读 `.tmp/local-test-server.txt`）

**⓪ 落笔现场（脚本当场读，不凭记忆）**：`git ls-remote` 回 `refs/heads/main = f5b239e889f43a9119012b87b2e386d72c742c56`（与本地同值）；合并树 `domain.sh` 摘要 `65947145714373b7…` / 3276 行，lane 提交 blob == lane 工作字节 == 合并树三处同值；`Case assertion implementations: OK (151 registered)`；门载荷仍 `cfa0f118…63afd6`（**第十三次同值**，`.tmp/m-r68/gate-payload-merge.json` 103,921 B、rc=1 按构造 blocked）。

**① 复审判据（M 侧独立重做，不取信 lane 的自报）**
- argv 判官在**合并树**上重跑（`.tmp/m-r68/judge-merge.txt`）：`closed: branch :3068+53 sha=92e404e2 rc=0 world_args=[] world_run_args=[--world-run-document /tmp/domain-session.json]`；`open: rc=0 world_args=[--server-profile /tmp/domain-join-profile.json --server-directory /tmp/domain-run/server] world_run_args=[]`；`faults=0`。⇒ §2.59 ① 的形状落在字节上，关闭态 argv 与 trunk 行为等值（判官只比 `rc / world_args / world_run_args`，沿用 §2.60 ② 的「sha 也不是 argv」口径）。
- 落盘普查（`.tmp/m-r68/write-census.py` ⇒ `VERDICT refusal precedes every disk write in the span; jar absent from the region`）：冲突拒止的 `exit 2` 在 `:3117`，落在 forge 区域 `:3079–:3119` 之内，早于两枚首次落盘 `:3208` 与封存调用 `:3212`。
- 契约 diff 逐格精读（`.tmp/m-r68/contract.diff`，+244/−46，119→**123** passed）：五枚格分别是关闭态等值、打开态恰两件且无 `--server-jar`、冲突拒止（含「删守卫 ⇒ rc≠2」的非恒真变异 + 字节偏移对首次落盘证明）、`world_args=(--server-directory "` 的缺陷样本命中／真文件 0 命中的成对格、`Only the directory` 注释格。⇒ 无恒真格、无越允许面文件（`domain.sh` 的 hunk 只在 `:206` 与 `:3074–:3100` 两片，宿主支 `:3020..:3041` 零改动）。
- 注释与判据同面：`:206–:215` 已改写为「profile + directory，jar 仍不交」，`:218` 起读法不变，`:545–:566` 三枚拒止（`case_on!=joiner` / `server_profile` 空 / `black_hole`）全保留。

**② 合并树门表（17 道，逐道单跑并先读 rc；日志 `.tmp/m-r68/gates-merge/`）**：`bash -n domain.sh` 0／`bash -n run.sh` 0／契约 0（123 passed, 17.14s）／`uv sync` 0／ruff-check 0／ruff-format 0（374 files already formatted）／pyright 0（0 errors）／全量 pytest 0（**2711 passed, 2 skipped**, 313.79s ⇒ 可比量 2713）／boundaries 0／case-assertions 0（151 registered）／fixture-digests 0／workflow-pins 0／wheel 0／wheel-boundary 0／cli-help 0／tee-mkdir 普查 0／`git diff --check` 0。

**③ CI（三次 REST 读，逐 job 逐步读结论后才写绿）**：记录笔 `23fa81c` = run 931 `36349218694`、`483eb76` = run 932 `36349613855`、合并笔 `f5b239e` = run 934 `36352444589`，三者均 `completed/success`，步数 `{python 18, protocol 10, bridge-static 9}`，`non_success=[]`（原文 `.tmp/m-r68/ci-23fa81c.json`、`.tmp/m-r68/ci-483eb76.json`、`.tmp/m-r68/ci-f5b239e-jobs.json`）。

**④ 活体：打开态真封出加入者 bundle**（lane 交付记录 §6 说「本环境无 1.20.1 受控专服活体资产」——**这格在 M 侧被推翻**：桥产物 `minekin-bridge-1201-0.0.0.jar` 1,310,604 B `e50d61c2…`、`.tmp/mc-1.20.1-server.jar` 47,791,053 B `3af73a9d…`、私有卷 `minekin-m-v5p-live` 的 `server-runs/run-1..run-4` 齐备，M 自行跑完整战役）
- 战役 `case_on=joiner` + `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=1` + `--case` 真跑 ⇒ 封存报告 `rc=1`、`status=sealed`、`attempt_sequence=1`、`run_id 889828dab7604e4c8812a5315641064e`、`bundle_digest 1960b0f85c27c451aa77c1419dc2d1d50532c431d2cd699f872cf69876384453`、`case_version 1e31f0003b4e30e0…`、`result FAIL`（四枚失败：`move_input_was_leased:NO_LEASE_GRANTED`、`the_bridge_carried_the_input_out:NOTHING_WAS_APPLIED`、`the_server_saw_the_kin_move:NO_SERVER_READINGS`、`the_probed_player_is_this_run_s_kin:PROBE_ATTRIBUTION_NOT_RECORDED`）。
- bundle 世界块 `{"kind": "dedicated", "seed_or_snapshot_id": "minekin-p0-controlled", "server_config_digest": "77a19c94c4467231e0431891939b09a94e3acd72c8e25edf3d28b24fb66f4df8"}`；`evidence verify` ⇒ `sealed:true verified:true violations:[]`；15 枚 artifacts 含 `server/server.log`（`0223128f…` 21,349 B）、`server/server.properties`、`server/usercache.json`、`trusted/server-profile.json`。⇒ **§2.54 附注那格答了**：1.20.1 受控专服的 run 目录里 `world_seed` 读得到种子名 `minekin-p0-controlled`，**不是** `unrecorded`；与仓库既有断言 `tests/unit/test_seal_run_evidence.py:320` 同值。
- **私有卷读数不当 sealed bundle**：这一枚只是形状证明。E7 要的「规范卷、同一 run 的真实封证」仍为 **0**；`result FAIL` 不作任何求绿引用，也不去翻 mandatory/registry。

**⑤ 具名更正：§2.59 ②(b) 的机制判定被本轮活体证否**
- 在未封存的载体（宿主 run `9c46a963…`，第 2 枚尝试）上**只交** `--server-directory /data/server-runs/run-4` ⇒ **封成功**：`status=sealed`、`bundle_digest 67a3a0aa24e5c3834d2d31d38035ea1c1a67855343dd6d477d46765ac6b0d3f3`、世界块 `kind=none / seed=none / digest=e3b0c44298fc1c14…`（EMPTY_DOCUMENT），**没有** `WORLD_RECORD_INCONSISTENT`；而且它照样带 `server/server.log`（`a82bfb19…` 22,190 B）等三件 `server/*` 载体。
- 为什么 `evidence.py:189–:193` 打不到：`_world_record` 在 `target is None`（无 profile）且未给 world 文档时**根本不进路线 3**，直接落到末支 `NO_WORLD / EMPTY / NO_WORLD`——三元同侧，一致性判据按构造不可能命中；`world_seed(目录)` 只在 `target` 非空那一支被读。⇒ §2.59 写的「只交目录时 `kind: none` 与目录算出的名字不成一侧」把两段代码的出处拼错了。
- H1p 的 `ce_ab2/50-switch-off.err` 实际是**交 profile 而不交目录**那一枚（`kind: dedicated` 借 `none` 作名 ⇒ 判据命中），不是「只交目录」；`docs/validation/v1201-probe-target-handover-counterexamples-2026-09-28.md` §5-1 的原文本就写着「两侧都补 `--server-profile`…只差第①格那一枚 flag」。lane 交付记录 §6「回退条件未被触发」在它自己的环境里如实成立（它没量到任何 bundle），那是带日期的读数，不改写；以本节 M 的实测为准。
- 顺带记 M 自己的一次**假读数**：第一次打印 artifacts 用了不存在的键 `name`（真实键是 `path`），得到 `server/* artifacts = []` 的假象，一度让我把「只交目录没有服务端载体」当成事实。本轮按正确键重读（`.tmp/m-r68/live/out-host/dump-manifests.txt`）才确认两枚 bundle 都带 `server/server.log`。教训：键名先从盘上读出来，再断言「缺席」。

**⑥ ④ 的回退条件按字面触发了——处置（不静默继承，也不撤销已合入字节）**
- 条件原文：「量到『只交目录』在某形状下能干净封出 bundle ⇒ ②(b) 被证否 ⇒ 本裁决作废、回到两枚旋钮的形状」。前半句本轮**量到了**，所以 §2.59 不再被当作「理由仍然成立」来继承。
- 但「回到两枚旋钮」这条补救与本轮另两格读数冲突：**(a) 仍成立且添了新证**——两份 run 文档（宿主 `9c46a963…`、加入者 `889828da…`）的 `run.world_snapshot` 现读皆为 `null` ⇒ 递 `--world-run-document` 必撞 `tools/seal_run_evidence.py:434`；**只交目录封出的那枚 bundle 否认了本 run 待过的世界**（`kind=none`），而 sealer 自己的 docstring 把这条列为「the same lie as before」；**交 profile 而不交目录** ⇒ 正是 H1p 量到的 `WORLD_RECORD_INCONSISTENT`（`evidence.py` 的注释：「a real kind cannot borrow either to sidestep the world requirements」）。三格合起来，只有「profile + directory」同时满足「弃掉注定被 `:434` 拒的那次递件」与「世界块自洽且指名」。
- 因此本轮处置是：**已合入的形状保留，但支撑它的理由换成上面这组实测**；(b) 作废本节具名记账。会翻转这格的条件也具名写下：若主控判定「加入者 bundle 的世界块记 `kind: none` 可接受」，该撤的是 `--server-profile` 那一枚 flag（另开窄卡），不是整个 H1q。本轮全仓 grep 证据：世界三字段只由封存端与 `src/minekin_core/domain/evidence.py` 的一致性判据消费，**没有任何 asserter／`REQUIRED_CASES` 判据读它** ⇒ 记 `none` 不会让哪一格变绿，只会让记录说谎。
- 失败与对照材料留存：`.tmp/m-r68/live/out-host/{joiner-seal,ce,ce2}/` 与 `dump-manifests.txt`、`run.log`。本轮无 revert ⇒ 不涉 `-FE1` 改名；#66 的「加入者未到达」材料在 `joiner-seal/domain-stderr.log`（`Kin2 never arrived within 420s` → `THE_WORLD_STATUS_IS_NOT_PROBEABLE` → `HANDSHAKE_TIMEOUT` → `the case verdict is FAIL`）。

**⑦ 次序与四态**：#65 H1q 闭合（复审 ⇒ 合并 `f5b239e` ⇒ push ⇒ CI 934 逐步绿 ⇒ 本记录）。E7（#49）的**形状面**因此解锁，但活体证据显示它现在阻塞在 **#66**：专服形状 + `--case` 的战役路径里加入者 `HANDSHAKE_TIMEOUT`、四枚判据 FAIL ⇒ E7 现在直接开跑只会封出另一枚 FAIL bundle。下一步按文档顺序：先派 #66（窄卡：把加入者到场接进战役路径），空档做 #58 (乙)，M-G1（#50）排最后。四态：M 本轮写入只有这两份主干文档 + 自己的 `.tmp/`（判官、普查、门日志、活体脚本与读数）；lane 树 `../minekin-wt-h1q` tip `efd3169`、`git status --porcelain` **0 行**，M 未在其中写过字节；`../minekin` 未碰；规范卷只 `:ro`；未连用户远程服、未读 `.tmp/local-test-server.txt`；未翻 `mandatory`/registry/晋级；材料与失败材料未删；无 `--amend`/`--no-verify`。**LAN 第二客户端在受控专服形状下的规范卷真实封证仍 = 0。**

## §2.62 #66 派工前把「加入者未到达」量成事实：加入者 JVM 在**游戏初始化**阶段就崩于 GLFW（`0x1000E`），崩溃报告本来就在 bundle 里——所以靶面不在服务端判据、也不在 H1q 的封存 argv，而在 `--case` 那一侧的客户端环境/启动次序（第六十八轮补格，2026-09-28 06:10 +0800，M 主控；M 私有卷 `minekin-m-v5p-live` 只读取材 + 宿主 bash，零新战役、零 JVM、规范卷未挂、未连用户远程服）

**① 新读数（本轮才有的，lane 不必重做）**
- 加入者 bundle `889828da…` 的 artifacts 里有一枚 `client/crash-reports/crash-2026-09-27_21.36.07-client.txt`（7,036 B，`9f2db49ebd1a05ea…`）。M 把这枚文件按原字节取出来复算摘要，与 manifest 记录**同值** ⇒ 取的是封进去的那份，不是同名副本。
- 抬头逐字：`java.lang.IllegalStateException: Failed to initialize GLFW, errors: GLFW error during init: [0x1000E]125198044773776`；`Description: Initializing game`；栈 `com.mojang.blaze3d.platform.GLX._initGlfw` → `RenderSystem.initBackendSystem` → `net.minecraft.class_310.<init>` → `Main.main`；系统面 `Minecraft Version: 1.20.1`、`Backend library: LWJGL version 3.3.1 SNAPSHOT`、**`Backend API: Unknown`**、`Operating System: Linux (amd64) version 6.18.33.2-microsoft-standard-WSL2`。
- 时间线（`domain-stderr.log` 逐行）：`21:35:35` run 起 ⇒ `server ready` ⇒ `enable-status=false` ⇒ 拨 `127.0.0.1:25566`（读自 `run-4/server.properties`）⇒ **`21:36:07` 加入者崩**（起 JVM 后 32s）⇒ `Kin2 never arrived within 420s` ⇒ 具名下游 `THE_WORLD_STATUS_IS_NOT_PROBEABLE … 25570` ⇒ `Kin2 arrived but never became playable within 420s` ⇒ 会话 `{'outcome': 'HANDSHAKE_TIMEOUT', 'connection_state': None, 'snapshots_admitted': 0, 'entities_admitted': 0}` ⇒ `the case verdict is FAIL` ⇒ `21:44:02` `domain.sh rc=1`。
- 崩前那一行环境读数（`:6`）：`harness DISPLAY=:77 harness XDG_RUNTIME_DIR=<unset> harness XAUTHORITY=<unset> harness XDG_RUNTIME_DIR_ORIGIN=<unset> harness GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits) harness GL_PROBE_RC=0 harness WRAPPER=direct`。

**② 这一格切掉了什么、留下了什么**
- **排除**：H1q 的封存 argv（同轮打开态照样封出 `kind=dedicated` 且 `violations=[]`，§2.61 ④）、服务端判据层、状态端点盲区（`:25570` 那条是**下游**读数，崩在前、探不到在后）、「加入者用哪枚 profile」那几格（`minecraft` 版本与地址都读到了才起 JVM）。
- **留下**：同一容器同一次 run 里宿主支已起过一个 llvmpipe 客户端，加入者支再起一枚就死在 GLFW init；候选按便宜排序为 (甲) X 授权/`DISPLAY` 复用（`XAUTHORITY=<unset>`）；(乙) `XDG_RUNTIME_DIR` 未落到加入者 env（H1e 那格只管受控客户端的提供面）；(丙) 两枚 llvmpipe 上下文并发把 GL 初始化挤死；(丁) `--case` 支的启动次序竞态（joiner 起得比宿主 ready 早）。
- **判据口径**：§2.51 的三式 V5′（同卷、同专服形状、**不带 `--case`**）里加入者到场且被按名探到（`Kin` 72 / `Kin2` 66 行）。⇒ 差集在 `--case` 一侧。本卡第一格就是把这两式在**同一份 `domain.sh` 字节**上再做一次 A/B，把差集钉成读数而不是记忆。

**③ #66 卡面（`V1201-CAMPAIGN-JOINER-ARRIVAL-001`）**
- 允许面只有 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、新交付记录 `docs/validation/v1201-h66-campaign-joiner-arrival-2026-09-28.md` 与 lane 自己的 `.tmp/h66/**`；判到 `tools/`、`src/`、fixture、镜像、`run.sh`、判据口径就**停手回报**（`project-controller-reserved-decisions` 同族）。
- 验收：(1) A/B 两式（只动 `MINEKIN_DOMAIN_CASE`/`MINEKIN_DOMAIN_CASE_ON`）各自打印加入者 env 行、`Kin2 never arrived` 是否复现、崩溃报告是否再出现；(2) 若 `--case` 支才崩 ⇒ 定位到具名那一层，字节面与活体面各一条支撑；(3) 若两式都崩 ⇒ 结论改为「§2.51 那组读数在当前字节上不再成立」，并列出变了的字节（`domain.sh` 摘要 / 镜像 / 桥产物 / 卷），**同样是合格交付**；(4) 改行为必配能红的契约格 + 关闭态逐字节等值 + 每对冲突组合具名拒止（`project-knob-conflict-named-refusals`）；(5) 门名单取自 `ci.yml` 自有 `- run:` 行逐道读 rc，基线 `domain.sh 65947145…`/3276 行、契约 123 passed、全量 2711 passed 2 skipped、ruff format 374 files、151 registered、门载荷仍 `cfa0f118…63afd6`；(6) 私有卷新根 `minekin-h66-live`，Kin 根用 `cp -a` 整份复制（跨卷 `cp -al` 不可用，WAL 台账不能 `:ro` 开），**不得删改** `kin-v5p-*` 与 `server-runs/run-1..run-4`。
- 卡面落在 `C:/Users/darling/Documents/agent_work/minekin-wt-h66/.tmp/h66-brief.md`，材料与复现脚本副本在同目录 `.tmp/h66/`（9 份文件逐摘要见卡面 §6），M 主干树对该 lane 只读。

**④ 派工现场与 CI（脚本当场读，不凭记忆）**：lane 树 `HEAD=527b6a75adeba6fd0bc0c13e40e1ce6838fec74f`、`git status --porcelain` 0 行（只有 M 写进去的 `.tmp/h66/**`，未入库）、远端分支 ref 尚未创建 ⇒ 本格只申报「已派工、零正面信号」，不宣布交付。记录笔 `527b6a7` 的 CI 已在 push 后立即用 REST 读到：run **935 `36353653574`** `completed/success`，jobs 端点逐 job 逐步读结论后 `non_success=[]`、步数 `{python 18, protocol 10, bridge-static 9}`（原文 `.tmp/m-r68/ci-527b6a7.json`、`.tmp/m-r68/ci-527b6a7-jobs.json`）⇒ §2.58 ⑧ 那格口径（未读到绿之前不得写 CI 绿）在此闭合。

**⑤ 四态**：M 本轮（含补格）写入只有这两份主干文档 + 自己的 `.tmp/m-r68/**`（判官、普查、门日志、活体脚本与读数、取出的崩溃报告）；`../minekin` 未碰；lane 树只在它自己的 `.tmp/` 写过材料；规范卷未挂；未连用户远程服、未读 `.tmp/local-test-server.txt`；未翻 `mandatory`/registry/晋级；材料与失败材料未删；无 `--amend`/`--no-verify`。**LAN 第二客户端在受控专服形状下的规范卷真实封证仍 = 0。**
## §2.63 E7 案面四枚判据逐条量清：加入者到场的那一式里已有两枚实测成立，残余两枚都在口径侧——一枚是旋钮未设，一枚是台账根对不上（第六十九轮，2026-09-28 06:53 +0800，M 主控；仓库字节 + 三次只读容器核卷，零 JVM、零 gradle、零引擎活体、规范卷未挂、未读 `.tmp/local-test-server.txt`、lane 材料一字节未改）

**⓪ 落笔现场（脚本当场读，不凭记忆）**：远端 `main` = `6bf5546`（`git ls-remote` 现读），M 主干树 `git status --porcelain` 0 行；#66 lane 的收尾会话仍在飞。本轮 M 只读三类东西：仓库字节、自己私有卷 `minekin-m-v5p-live` 上 run-4 那两份 bundle、lane 私有卷 `minekin-h66-live` 上**已落盘**的 bundle / 读数 JSON 原文（`:ro` 挂载，未写一字节）。**读数不取信 lane 的报告文字，只读它落盘的字节。**

**① 已经成立的半张**：lane `case2` 那一次（`domain.sh` 摘要 `cbec5b85142d2168…`，bundle `2124da30fb3f3cb7…`，run `aa5524bc4e1d4b38…`，加入者文档 `actions_applied=2 / actions_refused=0 / connection_state=PLAYABLE / snapshots_admitted=1`）的封存 `failures` 只剩两枚——`move_input_was_leased:LEDGER_UNREADABLE` 与 `the_probed_player_is_this_run_s_kin:PROBE_ATTRIBUTION_NOT_RECORDED`（原文在 `.tmp/h66/out/case2/domain-stderr.log` 的 seal JSON 里，本轮直读）；`the_bridge_carried_the_input_out` 与 `the_server_saw_the_kin_move` **通过**。⇒ §2.62 里「战役路径四枚判据都不成立」那句**只描述我那次客户端崩溃的 run**（`9c46a963…`，四枚全红、`HANDSHAKE_TIMEOUT`），不描述加入者到场时的形状。E7 的阻塞面从「四枚」缩到「两枚」，而且这两枚都不是产品/编排判据。

**② 逐枚口径与出处（`tools/assert_case_evidence.py`，本轮零改动）**
- `the_bridge_carried_the_input_out`（`:1621–:1633`）只读被 seal 那份 run 文档的 `actions_applied` / `actions_refused` ⇒ 控制旋钮在场 + 客户端到场即成立，case2 已实证。旋钮面 = `MINEKIN_DOMAIN_JOIN_LOOK_YAW/PITCH/HOLD_FORWARD_SECONDS`（`domain.sh:664–:746` 把它们组进 `--look-yaw-degrees/--look-pitch-degrees/--hold-forward-seconds`；`hold_at` 默认 `playable`（`:449`），所以 `:700` 那条「按 join 相位问就拒」不触发）。
- `the_server_saw_the_kin_move`（`:1647–:1661`）= `probe_readings(server_log, 3)` 的首尾水平距离 ≥ `MINIMUM_STEP_BLOCKS = 2.0`（`:235`）。这枚判据**按构造不按名字过滤**：`_PROBE`（`:246`）只匹配 `has the following entity data: [...]`，谁的读数都收 ⇒ 单目标探测是唯一安全形状（[[project-probe-answer-line-pairs]]）；case2 用的正是 `MINEKIN_DOMAIN_PROBE=Kin2` 且 `PROBE_SECOND=<unset>`（`00-header.txt:15–:16` 现读）。
- `move_input_was_leased`（`:1602–:1618`）第一步是 `material.ledger_readable`；那个布尔只在 `:632–:644` 这一句里为真——`kin_directory(data_root, KinId(<加入者文档的 run.kin_id>))/kin.sqlite3` **是文件**。路径取自**文档里的 `kin_id`**，不取自 `overlay`。case2 的加入者文档是 `kin_id=kin-v5p-join` 而 `overlay=/data/kin/kin-h66-join/run/session/9f34ca0a…/generation-1`；只读核卷（④ 第二条命令）证明 `/data/kin/kin-v5p-join/` 只有 `run/evidence/{697eadaf…, 889828da…, aa5524bc…}`，**没有 `kin.sqlite3`**，卷内两份 store 在 `kin-h66-host` / `kin-h66-join` ⇒ 按构造 `LEDGER_UNREADABLE`。**这不是判据在拒绝一个坏 run，是判据没读到东西**——把它当成产品拒止会误判 E7。
- `the_probed_player_is_this_run_s_kin`（`:1664–:1689`）的 `PROBE_ATTRIBUTION_NOT_RECORDED` 来自 `probed_players is None`；`None` 由 `recorded_probed_players`（`:526–:540`）把空集读成 `None`，空集来自 `--probed-player` 缺席，缺席来自 **`MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS` 没有被设**——case2 头部「every other name handed to domain.sh」那段（`.tmp/h66/out/case2/00-header.txt:11–:26`）列了 `SEAL_JOINER_SERVER_LOG=1` 而没有它，M 自己 run-4 的 `run-live.sh` 也没有。旋钮本身早就在干上（`domain.sh:229` 读、`run.sh:147` 转发，H1i/H1o 交付）。⇒ **纯口径遗漏，不是缺陷。**
- 同一枚判据的另一半给出 E7 的硬约束：`len(recorded) > 1 ⇒ MORE_THAN_ONE_PLAYER_PROBED`，而 `seal_probed_player_args` 逐个取自 `probe_args`（`domain.sh:926–:953`），`probe_args` 的首位永远是 `${probe:-${player}}`（`:899`）。⇒ **E7 必须 `MINEKIN_DOMAIN_PROBE=Kin2` 且 `MINEKIN_DOMAIN_PROBE_SECOND` 留空**，封进去的名字集才恰为 `{Kin2}`，与 `subject_username="${join_username}"`（`:3078`，默认 `Kin2`）同名。

**③ 那枚 stale `kin_id` 的来源：申报为「有据推断」，不写「已证」**。能证的是上格那句——文档 `kin_id` 指向的根上没有 store，于是台账按构造读不到。推断是它的来路：`kin-h66-join` 根里同时躺着 M run-4 的 `run/evidence/889828dab7604e4c8812a5315641064e/client/crash-reports/crash-2026-09-27_21.36.07-client.txt`（本轮 `find` 现读）和它自己新 session 的同名副本 ⇒ 那枚根是从 M 的 `kin-v5p-join` 整树复制来的，复制体内部记录的 kin 身份仍是旧名，与 [[project-kin-01-stale-process-markers]]（复制 store 带旧身份/旧进程标记 ⇒ 真跑要用全新根）同族。**翻转条件（具名）**：E7 若在规范卷上用**新建**的 Kin 名（宿主名与 `MINEKIN_DOMAIN_JOIN` 都从未存在过）跑出的加入者文档里 `run.kin_id` 仍与 overlay 所在根不一致，则本推断作废，这一条升级为编排缺陷，M 开窄卡修加入者支的 kin 身份传递。

**④ 复算命令（三条，全部只读；Windows Git Bash 下必须先 `export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`）**
1. `grep -o '"failures": \[[^]]*\]' ../minekin-wt-h66/.tmp/h66/out/case2/domain-stderr.log` ⇒ 两枚残余，逐字 `move_input_was_leased:LEDGER_UNREADABLE`、`the_probed_player_is_this_run_s_kin:PROBE_ATTRIBUTION_NOT_RECORDED`。
2. `docker run --rm -v minekin-h66-live:/data:ro python:3.12-slim sh -c 'find /data/kin/kin-v5p-join -maxdepth 3; ls /data/kin/*/kin.sqlite3'` ⇒ 前者三个 evidence 目录、无 store；后者只有 `kin-h66-host` / `kin-h66-join` 两份 store。
3. `docker run --rm -v minekin-m-v5p-live:/data:ro python:3.12-slim sh -c 'c(){ grep -c "$2" "$1"; }; b=/data/kin/kin-v5p-join/run/evidence/889828dab7604e4c8812a5315641064e/server/server.log; c $b "No entity was found"; c $b "entity data"; c $b "joined the game"'` ⇒ 依次 `256 / 0 / 0`：那台专服从 `21:35:21` 到 `21:43:51` 没有任何客户端进过世界。这就是 run-4 四枚全红的**原因**（客户端 GLFW 崩溃的下游），不是判据缺陷。

**⑤ E7 的完整可跑配方（十四枚，逐枚有 ② 的出处）**：`MINEKIN_USERNAME=Kin`、`MINEKIN_KIN_ID=<新建宿主名>`、`MINEKIN_DOMAIN_JOIN=<新建加入者名>`、`MINEKIN_DOMAIN_JOIN_USERNAME=Kin2`、`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`、`MINEKIN_DOMAIN_PROBE=Kin2`、`MINEKIN_DOMAIN_PROBE_SECONDS=4`、`MINEKIN_DOMAIN_JOIN_LOOK_YAW=45`、`MINEKIN_DOMAIN_JOIN_LOOK_PITCH=-20`、`MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=2`、`MINEKIN_DOMAIN_CASE=v1201-lan-joiner-control-case-001`、`MINEKIN_DOMAIN_CASE_ON=joiner`、两枚封存旋钮 `MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=1` 与 `MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1`；**不带** `MINEKIN_DOMAIN_PROBE_SECOND`。冻结案面现读恰是这四枚判据（`tests/fixtures/cases/v1201-lan-joiner-control-case-001.json` 的 `assertions` 四项、`mandatory: false` ⇒ E7 不翻 `mandatory`，也不动 registry）。

**⑥ 次序随之改写**：#66 的卡面**不需要**证明「加入者能到场并受控」——case2 已经证了；它要收的仍是那一条确定性缺陷（下游读数探 `lan_port` 而非本 run 实际拨向的 `joiner_target_port`）＋相应文案与具名拒止。E7 的阻塞从「四枚判据不成立」改写为「一次配方正确的同 run 封证」，前置只剩 **#66 入干**（同一份 `domain.sh`，不并行）。M-G1（#50）仍排最后，`#58 (乙)` 待引擎窗。

**⑦ 四态**：真实封证仍 **0**；已合主干且 CI 绿 = `6bf5546`；仅在分支 = `codex/minekin-h66-campaign-joiner-arrival`（在飞）与 lane 的历史 refs（均不删）；未验证 = E7 全卡、M-G1 全卡、`#58 (乙)`、③ 那条 stale-kin 推断（翻转条件已具名）。本轮 M 写入只有这份文档与自己的 `.tmp/`；lane 树只读未改；容器只以 `:ro` 挂了 `minekin-h66-live` 与 `minekin-m-v5p-live` 做核卷，规范卷未挂；未连用户远程服、未读 `.tmp/local-test-server.txt`；未翻 `mandatory`/registry/晋级；材料与失败材料未删；无 `--amend`/`--no-verify`。**LAN 第二客户端在受控专服形状下的规范卷真实封证仍 = 0。**
## §2.64 `LEDGER_UNREADABLE` 的来路量到行级：复制 Kin 根只换目录名、不换账本里的身份行 ⇒ E7 的准备形状由字节定死（第七十轮，2026-09-28 07:10 +0800，M 主控；仓库字节 + 只读容器核卷（规范卷本论以 `:ro` 挂过两次）+ 账本副本只进内存 tmpfs，零 JVM、零 gradle、零引擎活体战役、未读 `.tmp/local-test-server.txt`、lane 材料一字节未改）

**⓪ 落笔现场（脚本当场读，不凭记忆）**：远端 `main` = `953dfeda46e1b15d0733b7ba1d8962c13de5781c`（`git ls-remote origin main` 现读），M 主干树 `git status --porcelain` **0 行**；#66 lane 树 HEAD 仍 `527b6a7`、`git status --porcelain` 两行（`test-orchestrator/runner/domain.sh` + `tests/contract/test_runner_scripts.py`）、`git ls-remote origin 'refs/heads/codex/minekin-h66*'` 空 ⇒ 仍判在飞，M 未代提交、未碰它一字节。CI 本轮 REST 读到：`af32e35` 的 run 937（`36356906385`）= `completed/success`；`953dfed` 的 run 938（`36357157810`）读时 `in_progress` ⇒ **不写绿**。

**① §2.63 ③ 那条「有据推断」升为已量，但来路换了一句。** 不一致的不是含糊的「复制体内部记录的 kin 身份」，而是**账本 `kin_identity` 表里的那一行**：
- 行级读数（⑤ 第 4 条命令，`SELECT kin_id, local_profile_id, username FROM kin_identity WHERE singleton = 1`）：`minekin-h66-live` 上 `kin-h66-join` 的账本给 `('kin-v5p-join', 'kin-v5p-join-r1', 'Kin2')`，`kin-h66-host` 给 `('kin-v5p-host', 'kin-v5p-host-r1', 'Kin')` ⇒ 两根的**目录名与身份行逐字符不同**，且两侧同形（不是加入者独有）。
- 卷级：同卷第三个根 `kin-v5p-join` **没有 `kin.sqlite3`**（`sqlite=0`），`kin-h66-host` / `kin-h66-join` 各有（`=1`）⇒ 判据拼出的 `/data/kin/kin-v5p-join/kin.sqlite3` 不存在。
- 正对照（规范卷，`:ro`）：16 个根**全部** `sqlite=1`；抽两行 `kin-01 → ('kin-01', 'kin-01-r1', 'Kin')`、`kin-e6-j020 → ('kin-e6-j020', 'kin-e6-j020-r1', 'Kin')` ⇒ 身份与目录同名是规范卷的现状，这一格失配只是那次驱动准备的形状。
- 零引擎旁证：M 自己 v5p 材料 `.tmp/v5p/out-host/{armed,control-off,ghost}` 里 9 份文档的 `kin_id` 与 `overlay` 的 Kin 段 **9/9 相同**（`.tmp/m-r70-kinid-pairing.py` → `paired 9 mismatched 0`，rc=0）。

**② 字节链（主干 `953dfed` 的工作树现读；引用前按 `git log --oneline -1 -- <file>` 重核。本轮量到的各文件最后触及笔：`session.py = 5c643c63`、`identity_store.py = 0ad3aab9`、`init.py = ac271f7d`、`assert_case_evidence.py = 4a5d353`、`domain.sh = 68a748a`）**
- 一份 session 文档里的两个字段来自两处：`src/minekin_core/cli/session.py:538` 用选择器定 `kin_id`，`:547` 再从**账本行**取 `identity = read_identity_root(connection)`；`:579` 的 `runs = run_root(root, kin_id)` 用**选择器**（overlay 落在新根），`:694` 的 `kin_id=str(identity.kin_id)` 用**账本行**（文档名字停在旧根）⇒ 一个复制体天然产出「overlay 在新根、`kin_id` 在旧根」的文档，两处各自都不是 bug。
- 那一行的来源：`src/minekin_core/adapters/sqlite/identity_store.py:18–:20` 的 `_SELECT` 就是 `kin_identity WHERE singleton = 1`，`:64–:69` 的 `read_identity_root` 只读不造（缺行即拒 `identity root is missing; only an explicit init may create one`）；只有 `src/minekin_core/cli/init.py:64–:91` 的 `initialise_identity` 会把 `--kin-id` 写进去（`:76` 的 `local_profile_id = f"{kin_id}-r{INITIAL_IDENTITY_REVISION}"` 与 ① 里两行都带 `-r1` 同形）。
- runner 侧的触发条件：`test-orchestrator/runner/domain.sh:1222–:1230` 的 init **只在 `/data/kin/${joiner}` 不存在时**执行，`:1229` 那句 `the joining Kin %s was created as %s` 也只在这一支里打印 ⇒ 驱动先把种子根复制成新名字，就等于让加入者沿用种子的身份行，而这一块**不会为此说任何一个字**（无提示、无拒止）。
- 判据侧为什么报「读不到」而不是「拒止」：`tools/assert_case_evidence.py:604` 取 `run.kin_id`；`:615–:620` 那格「按卷内唯一 store 猜」的回退**只在文档没说名字时**才走到 ⇒ 非空的过期名字永远走不到回退；`:632` 把路径拼成 `kin_directory(data_root, KinId(kin)) / kin.sqlite3`，`:644` 仅当它是文件且打开成功才 `readable = True`，`:698` 交给 `ledger_readable`，`:1610` 的 `move_input_was_leased` 第一句就返回 `LEDGER_UNREADABLE`。

**③ §2.63 ③ 的翻转条件按字面已经触发，但裁决不是「编排缺陷」**：case2 的目录名（`kin-h66-host` / `kin-h66-join`）本来就是全新名字，仍不一致 ⇒ 那句「用全新名仍不一致」的前提成立；但它写下的推论（升级编排缺陷、开窄卡）**不成立**，因为不一致的来路在驱动的种子复制，不在 runner 的名字传递。按字面执行「推断作废」的那半：§2.63 ③ 里「复制体带旧身份」这句现在有了行级出处，不再是需要翻转正理的推断。**不开新卡。** 新的具名回退条件：E7 若在规范卷用「该卷从未出现过的名字、由 `domain.sh:1222` 那一支自己 init 的加入者根」跑出 `run.kin_id ≠ 目录名`，则本裁决作废，升级为编排缺陷并由 M 开窄卡修加入者支的 kin 身份传递。

**④ E7 的准备形状（进卡面的硬前置，起跑前可自检）**：宿主与加入者两侧的 Kin 根都必须满足 **目录名 == 该根 `kin_identity` 里的 `kin_id`**。规范卷里最省的姿势是给 `MINEKIN_KIN_ID` / `MINEKIN_DOMAIN_JOIN` 两个**该卷从未出现过**的名字（⑤ 第 3 条列出的 16 个现名之外，例如带日期后缀的新名），让 `domain.sh:1222` 那一支自己 init 加入者根；宿主根同样不得是复制体。起跑前自检（任一行不等就**拒绝起跑**，不要等封存报 `LEDGER_UNREADABLE`）：把 ⑤ 第 4 条脚本里的 `CASES` 换成 E7 要用的两个根名再跑一次。

**⑤ 复算命令（五条，全部只读；Windows Git Bash 下先 `export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`；读数已落 `.tmp/m-r70-ledger-root-readings.log`）**
1. `grep -o '"failures": \[[^]]*\]' ../minekin-wt-h66/.tmp/h66/out/case2/domain-stderr.log | tail -1` ⇒ 两枚残余逐字 `move_input_was_leased:LEDGER_UNREADABLE`、`the_probed_player_is_this_run_s_kin:PROBE_ATTRIBUTION_NOT_RECORDED`。
2. `docker run --rm -v minekin-h66-live:/h66:ro python:3.12-slim sh -c 'ls -1 /h66/kin; for d in /h66/kin/*; do echo "$d sqlite=$(ls "$d/kin.sqlite3" 2>/dev/null | wc -l)"; done'` ⇒ 三根，`kin-v5p-join sqlite=0`，另两根 `=1`。
3. `docker run --rm -v minekin-runner-data:/data:ro python:3.12-slim sh -c 'for d in /data/kin/*; do echo "$d sqlite=$(ls "$d/kin.sqlite3" 2>/dev/null | wc -l)"; done'` ⇒ 16 行全部 `sqlite=1`。
4. `docker run --rm --tmpfs /work -v minekin-h66-live:/h66:ro -v minekin-runner-data:/data:ro -v "$PWD/.tmp:/drv:ro" python:3.12-slim python /drv/m-r70-identity-rows.py` ⇒ ① 那四行读数；账本副本只进内存 tmpfs，两个卷都只 `:ro`。
5. `python .tmp/m-r70-kinid-pairing.py .tmp/v5p/out-host` ⇒ `paired 9 mismatched 0`、rc=0（脚本 rc 的口径：有任何 mismatch 才非 0）。

**⑥ 口径面申报（这一条修正 §2.63 ⑦ 的「规范卷未挂」）**：第七十轮 M 以 `:ro` 挂过规范卷两次（列根、读身份行用的账本副本），**没有**以可写方式挂过、没有写过它任何一字节；`kin.sqlite3` 与它的 `-wal`/`-shm` 都留在原处。时点移动另起此句，§2.63 ⑦ 原文不改。

**⑦ 四态**：真实封证仍 **0**；已合主干且 CI 绿 = `af32e35`（run 937 本轮读到 `completed/success`），更正笔 `953dfed` 的 run 938 读时 `in_progress`；仅在分支 = `codex/minekin-h66-campaign-joiner-arrival`（在飞：HEAD `527b6a7` + 两文件脏 + 远端无 ref）与 lane 的历史 refs（均不删）；未验证 = E7 全卡、M-G1 全卡、`#58 (乙)`。本轮 M 写入只有这份文档、handoff 的一节与自己的 `.tmp/`；未连用户远程服、未读 `.tmp/local-test-server.txt`；未翻 `mandatory`/registry/晋级；材料与失败材料未删；无 `--amend`/`--no-verify`。**LAN 第二客户端在受控专服形状下的规范卷真实封证仍 = 0。**
## §2.65 #66 复审入干（合并 `82e199c`，parents `adc6a3f`+`a4dfef4`，真实 merge-base `527b6a7`，远端已核、CI 逐步读绿）：M 亲跑 19 道 POST 门 + 一枚植入变异对照把那张卡的核心验收变成 M 自己的读数；顺带量清 `ruff format --check` 的文件数**含 `.md`**，lane 表里的 374 与本轮的 375 因此都不是漂移（第七十一轮，2026-09-28 07:40 +0800，M 主控；宿主 bash + 只读容器 + 规范卷只 `:ro` 挂一次读门载荷，零 JVM、零 gradle、零引擎活体战役、未读 `.tmp/local-test-server.txt`、lane 材料一字节未改）

**⓪ 落笔现场（脚本当场读，不凭记忆）**：远端 `main` = `82e199c`（`git ls-remote origin refs/heads/main` 现读，与本地 HEAD 同值）；M 主干树 `git status --porcelain` 0 行。CI 三笔全部逐 job 逐步骤读过：合并笔 `82e199c` = run `36358872429`（本会话编号 941）`completed/success`，`bridge-static`/`python`/`protocol` 三个 job 的 `non_success_steps` 各为 `[]`；`953dfed` = run `36357157810`、`adc6a3f` = run `36357923755`，同样 `completed/success` 且三 job `non_success_steps=[]`。**取数姿势**（无 gh CLI）：`printf 'protocol=https\nhost=github.com\n\n' | git credential fill` 从**默认** helper 取 token（只指定 `credential.helper=wincred` 会取到空串并 401），token 只打印长度不打印值，再 `curl -H "Authorization: Bearer $TOKEN" https://api.github.com/repos/printlndarling/minekin/actions/runs?head_sha=<全 SHA>` —— `head_sha` 传短 SHA 会返回空列表而不报错，本轮就先撞了一次空集。

**① 合入了什么**：#66 `V1201-CAMPAIGN-JOINER-ARRIVAL-001`（分支 `codex/minekin-h66-campaign-joiner-arrival`，tip `a4dfef4`，起点 `859ab1d`）。它的修复面只有一处确定性缺陷：`classify_the_joiner_downstream_readings` 的下游读数探的是 `${lan_port}`，而专服形状下本 run 实际拨向的端口写在 `${joiner_target_port}`（由 `joiner-controlled-server-target` 那一支从**本 run 自己的** `server.properties` 读出来）⇒ 战役式下那句 verdict 回答的是另一个世界的端口。改后区域用 `# --- joiner-downstream-reading-target begin/end ---` 具名标记，契约按名提取、用真实 loopback listener 与 closed port 驱动判据、植入变异反证、并钉住默认关闭态逐字等值。合并树 `git show HEAD:test-orchestrator/runner/domain.sh | sha256sum` = `cbec5b85142d2168afcb46551d879dcd23159e62c89f21e422c7a69221ab8a82`／3292 行 —— 与 lane 活体读数所用摘要同值 ⇒ **字节出处闭合**（[[project-bundles-do-not-pin-orchestrator-bytes]] 说的是 bundle 不钉编排字节，这里闭合的是「M 复审的门与 lane 交付的字节是同一份」）。

**② M 亲跑的 POST 门（19 道，逐道读 rc，日志在 `.tmp/m-r71/gates-merge/`）**：`bash -n` 两道 rc=0；契约 **124 passed**（宿主 uv 28.20s、镜像 CPython 2.17s）；`uv sync --locked --dev` rc=0；`ruff check` All checks passed；`ruff format --check` **375 files already formatted**；`pyright` 0 errors；全量 **2712 passed, 2 skipped in 314.88s**；`check_boundaries` / `check_case_assertions`（**151 registered**）/ `verify_fixture_digests` / `check_workflow_pins` / `uv build --wheel` / `check_wheel_boundary` / `minekin --help` / `git diff --check` 全 rc=0；`-k downstream_reading` 单格在镜像内 1 passed。门载荷 `report_promotion --data-root /data`（规范卷 **`:ro`**）rc=1（构造性 blocked，非新failure），摘要 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece66761c47fe7d6b9f49863afd6` —— **第 14 次同值**，PRE==POST。可比量口径：契约 123→**124**（#66 新增那一格）、全量 2711→**2712**、`151 registered` 不动、载荷不动（载荷输入面不含 `docs/**`，也不含 `domain.sh`）。

**③ M 自己跑的植入变异对照（这张卡的核心验收格不再是「lane 说它绿」）**：先把出货字节备份并核摘要（`.tmp/m-r71/domain.sh.pre-plant` = `cbec5b85…`、172201 B、当时 `git status --porcelain` 0 行 ⇒ 恢复用的是 `git checkout --`，不是 stash），再用 `.tmp/m-r71-plant-m1.py` 把**具名区域内**的 `${joiner_target_port}` 全替换成 `${lan_port}`（区域内 4 处、区外 3 处未动）。镜像内 `-k downstream_reading` ⇒ **rc=1**，失败点是契约自己的那句 `tests/contract/test_runner_scripts.py:2593` `assert lan_shaped != region, "the planted mutation changed nothing; nothing was measured"`。这一红的意义要说准：它证明**该格读的是工作树里的出货字节**（变异一落盘，契约立刻把「区域已经是 lan 形状」当成未测量而拒判），不是只在自己内存里变异一遍就自证 ⇒ 契约对 shipped bytes 敏感（[[feedback-escape-class-predicates]] 的两侧对照里「植入缺陷必红」这一侧）。恢复后 `sha256sum` 逐字回 `cbec5b85…`、`cmp` 与备份 0 差、该格 rc=0、`git status --porcelain` 0 行。**这一侧红了、另一侧（修好的字节必绿）就是 ② 的 124/1 passed。**

**④ 顺手量清的一处口径：`ruff format --check .` 数的是工作树里被格式化的文件，含 `.md`**。#66 交付表写 POST `374 files`，本轮同一份工作树内容量到 **375**，差的那一格正是它自己那份 `docs/validation/v1201-h66-campaign-joiner-arrival-2026-09-28.md`（`.md` 被计入 ⇒ 落盘前后差 1）。这不是漂移也不是失败：**两棵树**（M 主干 `82e199c` 与 lane `../minekin-wt-h66@a4dfef4`）现在逐字都量到 375，且 ruff 逐文件清单 `diff` 为空。口径后果：**任何新增 `.md` 的卡都会把这道门的文件数 +1**，E7 的交付记录因此不能死抄 375，要按「+自己新增的文档数」申报（已写进 E7 简报）。

**⑤ E7（#49）已派工**：树 `../minekin-wt-e7`、分支 `codex/minekin-v1201-lan-joiner-control-seal`、起点 `82e199c`、该树 `domain.sh` 现读 `cbec5b85…`／3292 行、`git status` 0 行；简报 `.tmp/e7/brief.md` 本轮改写了四处（起点写实为 `82e199c`、门表改抄 M 的实测 POST、新增 `.md` 使 ruff 计数 +1 的口径、以及**撤回我自己那句没量过的断言**：原写「门载荷 PRE==POST，E7 不注册案 ⇒ 按构造不动它」，改为「封存前后各跑一次、贴两个摘要、说明差在哪个字段」——理由是 E7 一旦封成，规范卷上就多出一枚该案 bundle，载荷读的是卷面，M 从没量过这个方向）。E7 的配方与三条前置验收逐条见 §2.63 ⑤ 与 §2.64 ④；起跑前 `docker ps` 空清单已核（引擎串行）。

**⑥ 复算命令（四条，全部只读；Windows Git Bash 下 docker 前必须 `export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`）**
1. `bash .tmp/m-r71-h66-merge-gates.sh .tmp/m-r71/gates-merge` ⇒ 19 道逐行 rc，末行 `payload digest line:` 带 `cfa0f118…63afd6`。
2. `python .tmp/m-r71-plant-m1.py` ⇒ 打印 `region_occurrences 4 / outside_untouched 3`；容器内 `python -m pytest -q tests/contract/test_runner_scripts.py -k downstream_reading` ⇒ rc=1；`git checkout -- test-orchestrator/runner/domain.sh && sha256sum test-orchestrator/runner/domain.sh` ⇒ `cbec5b85…`。
3. `uv run --frozen --offline ruff format --check -v . 2>&1 | grep -oE 'path=.*' | sed 's#.*minekin-wt-integration.##' | sort`（在另一棵树把 sed 的目录名换掉再比）⇒ 两边各 375 行、`diff` 为空，其中含 `docs\validation\v1201-h66-campaign-joiner-arrival-2026-09-28.md`。
4. `git ls-remote origin refs/heads/main` ⇒ `82e199c…`；`git log --format='%H %P' -1` ⇒ `82e199c… adc6a3f… a4dfef4…`（两个 parent，真实 merge-base 用 `git merge-base adc6a3f a4dfef4` = `527b6a7`）。

**⑦ 四态**：真实封证仍 **0**（E7 在飞，其结果未读回）；已合主干且 CI 绿 = `82e199c`；仅在分支 = `codex/minekin-v1201-lan-joiner-control-seal`（E7，在飞）与 lane 的历史 refs（均不删）；未验证 = E7 的封证与它的门表、M-G1（#50）全卡、`#58 (乙)`。本轮 M 写入只有这份文档、handoff 与自己的 `.tmp/`；lane 树只读未改；容器只以 `:ro` 挂了 `minekin-runner-data` 一次读门载荷；未连用户远程服、未读 `.tmp/local-test-server.txt`；未翻 `mandatory`/registry/晋级；材料与失败材料未删；无 `--amend`/`--no-verify`。**LAN 第二客户端在受控专服形状下的规范卷真实封证仍 = 0。**
## §2.66 E7 封成入干（合并 `d01bc5e`，parents `cf6d2fc`+`a7c1f99`，真实 merge-base `82e199c`，远端已核）：**LAN 第二客户端在受控专服形状下的规范卷真实封证从 0 变 1** —— bundle `5086ee42…64f6`／run `a224f6c3…`，M 用出货 asserter 独立复判四枚判据全 `agrees/PASS`，门载荷第十五次同值而卷面普查恰 +1（第七十二轮，2026-09-28 08:40 +0800，M 主控；宿主 bash + 只读容器 + 规范卷只 `:ro`、lane 树只读未改、零 M 侧 JVM 战役、未读 `.tmp/local-test-server.txt`）

**⓪ 现场与交付面**。起点远端 `main` = `cf6d2fc`（§2.65 那笔）。E7 的执行体在 150 轮上限处中断，但它已把 campaign 跑完、封成、并把门表跑在盘上；M 按 [[只收尾不重设计]] 的姿势派续接体，简报 `.tmp/e7-resume-brief.md` 只列三件事（改一处读数标注、重跑受影响三道门、提交并只推自己分支）。交付恰一笔 `a7c1f99`：`git diff --name-status main...a7c1f99` = **`A docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md`（126 行，一枚文件）**，`git merge-base main a7c1f99` = `82e199c`（正是简报要求的起点），`ls-remote` 的分支 ref 与本地 `rev-parse HEAD` 逐字相等。**产品字节零改动**：分支上的 `test-orchestrator/runner/domain.sh` 提出来的 sha256 = `cbec5b85142d2168afcb46551d879dcd23159e62c89f21e422c7a69221ab8a82`／3292 行，与 M 第七十一轮在合并字节上量的 POST 值逐字相同 ⇒ 它的活体读数取自最终出货字节，不是中途草稿。三枚被引 fixture 摘要也在 M 树现量对上：`bundle-candidate-1.20.1.json` = `709a8899…ef185`、`controlled-offline-server-1.20.1.json` = `3864edda…3aa2`、`tests/fixtures/cases/v1201-lan-joiner-control-case-001.json` = `f4b94e03…d8ff`。

**① 封出来的是什么**。规范卷 `minekin-runner-data` 上 `/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf`：`case_id V1201-LAN-JOINER-CONTROL-CASE-001`、`case_version 1e31f0003b4e30e0…`、`attempt_sequence 1`、`result PASS`、`failures []`、`status sealed`、bundle `5086ee42659033a0db15c180f0b0e051961718b5d64bf3ac750ceda5f01464f6`、14 件 artifacts；`evidence verify` = `verified true / violations [] / 14 artifacts`。世界块 `kind = dedicated`、`seed_or_snapshot_id = minekin-p0-controlled`、`server_config_digest = 77a19c94c4467231e0431891939b09a94e3acd72c8e25edf3d28b24fb66f4df8`（与 `trusted/server-profile.json` 的 `revision` 同值）⇒ §2.59 裁决的「专服形状下由本 run 自己的 `--server-profile` 命名世界块」按预期兑现。同一 run 的阶段链在 `20-domain-stderr.log`：`server run directory /data/server-runs/run-186` → `the joining Kin kin-e7-join-0928 was created as Kin2` → `the world heard Kin2 arrive` → 首快照 → soak → `BRIDGE_LOST / PLAYABLE / snapshots_admitted 1 / entities_admitted 27`。全程只连容器 loopback `127.0.0.1:25566`。

**② M 的独立复判（不是读 lane 的日志，是 M 自己重跑）**。脚本 `.tmp/m-r71-e7-verify.py`（只读、规范卷 `:ro`），日志 `.tmp/m-r71/e7-verify.log`：按 run id 在卷上定位到 **恰 1 枚** bundle、重算 manifest sha256 = `5086ee42…` ⇒ `digest agrees with the seal JSON: True`；用**出货 asserter**（不克隆、不打补丁）`tools/rejudge_evidence.py` ⇒ `rc=0 status=agrees result=PASS criteria=4 disagreements=[] unimplemented=[]`，四枚判据逐名 `move_input_was_leased` / `the_bridge_carried_the_input_out` / `the_server_saw_the_kin_move` / `the_probed_player_is_this_run_s_kin`；`asserter-inputs.json` 的 `probed_players = ["Kin2"]`；`server.log` 172 行、`joined_the_game` 2、按名 `entity_data` 行 80、`no_entity_found` 28、`Kin2` 提及 85，离场链 `Kin2 lost connection 00:00:53` 早于 `Kin 00:00:57`。§2.63 的两枚残余（探针归属未记、台账根对不上）在这枚 bundle 里都**不存在**，且解法全在配方侧：`MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1` + 两枚全新自建 Kin 根（`kin-e7-host-0928`/`kin-e7-join-0928`，目录名 == 账本 `kin_identity.kin_id`，M 与 lane 各量一次）。**没动 `mandatory`、registry、判据、封存 schema。**

**③ M 本轮新量的一条：这枚封证属当前构建**。封存前后两份 `report_promotion` 报告按条目做集合差，新增恰 **1 枚 bundle + 1 枚 attempt**，且那枚 bundle 条目带 `from_repository_build: true`、`re_judged: "AGREES"`、`result PASS`、`verified true`、`violations []`、`bridge_digest e50d61c2…006f`、`launch_plan_digest 83299ad5e224959de8e30c72c5937a2434c4d7bba92c62f4d22cf8d89f5f6181` —— 与同报告 `repository_build.builds[minecraft=1.20.1].plan_sha256` **逐字相同**；`evidence.from_another_build` 前后都是 61（新 bundle 没进那个清单）。⇒ 它不是「旧构建引用」，将来若要入 registry 不需为重封而重跑。

**④ M 亲跑的 POST 门表（合并字节 `d01bc5e`，按 `ci.yml` 自有 `- run:` 步逐道单跑、先读 rc）**

| `bash -n domain.sh` | 0 | （空） |
| `bash -n run.sh` | 0 | （空） |
| `pytest contract/test_runner_scripts.py（host uv）` | 0 | 124 passed in 36.16s |
| `uv sync --locked --dev` | 0 | Checked 18 packages in 2ms |
| `ruff check .` | 0 | All checks passed! |
| `ruff format --check .` | 0 | 376 files already formatted |
| `pyright` | 0 | 0 errors, 0 warnings, 0 informations |
| `pytest -q（全量，host）` | 0 | 2712 passed, 2 skipped in 335.86s (0:05:35) |
| `check_boundaries.py` | 0 | Minekin package dependency boundaries: OK |
| `check_case_assertions.py` | 0 | Case assertion implementations: OK (151 registered) |
| `verify_fixture_digests.py` | 0 | W00 schema and fixture digests: OK |
| `check_workflow_pins.py` | 0 | Workflow pins: OK (every action is a commit, and each names its release) |
| `uv build --wheel` | 0 | Successfully built dist\minekin_core-0.0.0-py3-none-any.whl |
| `check_wheel_boundary.py dist/*.whl` | 0 | Wheel oracle boundary: OK (dist\minekin_core-0.0.0-py3-none-any.whl) |
| `minekin --help` | 0 |   -h, --help            show this help message and exit |
| `git diff --check` | 0 | （空） |
| `pytest contract（容器 CPython 3.12）` | 0 | 124 passed, 1 warning in 2.00s |
| `契约三枚具名单元（容器：sealed_probe_names / joiner_server_log_guard / joiner_control_driver）` | 0 | 15 passed, 109 deselected, 1 warning in 0.54s |
| `report_promotion.py --data-root /data（容器，规范卷 :ro）` | 1 | size=104680 |


三道具名契约单元（容器内）是这张卡的验收格本身：`sealed_probe_names`（记名交给封存）、`joiner_server_log_guard`（默认关闭 + 形状拒止）、`joiner_control_driver`（加入者控制限幅且只到一行）。`report_promotion` 的 `rc=1` 是构造性 blocked，不是失败。**`ruff format --check` 读到 376**（M 第七十一轮在同一主干上是 375）——这正是 §2.65 ④ 那条口径的第二次兑现：E7 新增的那一枚 `docs/validation/*.md` 让该门 +1，**是口径不是漂移**。注意位移只来自**新增文件**：本轮 M 的记录笔只往两份既有 `.md` 追加段落，该门现读仍是 376（`.tmp/m-r72/record-ruff-format.log`，`rc=0`）。

**⑤ 门载荷第十五次同值，但报告字节动了 —— M 撤掉自己那句没量过的断言之后由实测收口**。`gate_payload_sha256` 封前封后逐字都是 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（两枚 `gate-payload-{pre,post}.digest.txt` 由 appender 现读校验，不等即拒绝落盘）；被哈希的子集（`work_packages` + `overall`）逐字未变，动的是顶层 `evidence` 普查：`count 113 → 114`、`bundles 113 → 114`、`attempts 77 → 78`，`sealed_without_bundle / unsealed / unreadable / unverified` 前后皆 `0`，`status` 前后都是 `blocked`。报告体积：`bytes= 103920 → 104679`（`gate-payload-{pre,post}.digest.txt` 首行口径）／文件尺寸 `103921 → 104680`（`wc -c` 口径），两种取法增量都是 **+759**。⇒ §2.56 那条改判（只有 `REQUIRED_CASES` 点名的行入册才动载荷）在「封证」这一侧同样成立：**封一枚非 mandatory 案不点亮任何门**。

**⑥ 复审退回的一处标注，以提交前修正收口**。lane 首稿 §5 把 `wc -c` 的文件尺寸（103921/104680）当成 `bytes=` 这个键的值写进正文，而材料里 `bytes=` 实为 103920/104679。M 在派只收尾简报前就 `head -1` + `wc -c` 两侧各量一次、把两条命令原样写进简报要求「改完把取数命令贴回来，别凭记忆」；lane 的 `a7c1f99` 已把这两行改成「两个来源各自具名」，其余 §1–§4、§6–§8 未动（`git show --numstat` = `126 0` 一枚新文件，无整文件重写；CRLF 126 行保持）。**它同时如实点名了自己脚手架的两处崩**（`e7-drive.sh` 一处 bash 语法错、一处 `require_store_complete` 调用签名错报 `'dict' object has no attribute 'resolve'` 并打出 `E7-STOP` 却没 `exit`）——两处都发生在封存之后或只影响预检，证据面完整，且修正后的只读复核给出 `launchable=True / plan artifacts 3638 / verified 3638 / missing 0`。M 侧不替它重跑战役，也不把这两处当仓库缺陷；**驱动守卫「打了 STOP 却没停」这类形状，后续任何复用 `e7-drive.sh` 的卡都应先修成 `exit`**（记在未跟踪材料里，不入库）。

**⑦ 时点移动：§2.65 ⑦ 那句「真实封证仍 0」被本轮读数推翻**。那是 07:40 的现场（当时 E7 结果未读回），按 [[dated-findings]] 口径旧读数原样保留，本节只改现在时断言：**LAN 第二客户端在同一受控专服 run 里的规范卷封证 = 1**（`5086ee42…`）。另更正 M 自己第七十一轮的一次读数错误：`kin_id` 是 run-document 的**顶层键**（值 `kin-e7-join-0928` == 目录名），不在 `run` 对象里；我当时用 `doc["run"]["kin_id"]` 读出 `None` 并误以为 §2.64 的机制有变，实为键位取错，正读已落 `.tmp/m-r71/e7-rundoc-keys.log` 与 `.tmp/m-r71/e7-rundoc-topkey.log`。

**⑧ 落点与 CI**。合并笔 `d01bc5e34c39f28f480fc0df43c9098b5131b987`（parents `cf6d2fc5accc1b7bfbbf55c6d02d1e7ff3000002` + `a7c1f9958495c9283800f919e367c6a0f5bb0844`，真实 merge-base `82e199c`）已 push，`git ls-remote origin refs/heads/main` 读回同值；run `36363094622` 首读 `in_progress`、重读 `completed/success`，三 job 按 `ci.yml` 自有步骤逐条读为 `python` 18 步 / `bridge-static` 9 步 / `protocol` 10 步全 `success`、`non_success_jobs=[]`（原文 `.tmp/m-r72/ci-jobs-d01bc5e.json`）⇒ **「已合主干且 CI 绿」前进到 `d01bc5e`**。E7（#49）到此闭合；本轮 M 侧写入只有这两份主干文档 + 自己的 `.tmp/`，lane 树 `../minekin-wt-e7` 在 M 复审期间只读未改（M 只 `sha256sum`/`head`/`wc` 过它的材料）。

## §2.67 M-G1（#50）的「改后」半张跑完了：18 条 registry 引用逐条仍 `agrees/PASS`、`digest_mismatch=0`，而 **E7 的真封证对门报告是零位移** —— W40/W60/p0-core 的 `work_packages` 在封存前后**逐字节相同**，这枚证据的价值在证据面不在门（第七十二轮补格，2026-09-28 08:55 +0800，M 主控；全程只读，规范卷 `:ro`、源码树 `:ro`，唯一 rw 挂载是持有桥 jar 的 `../minekin-wt-v4`（跑后 `git status --porcelain` 仍 0 行、HEAD 仍 `8d9189e`），零 JVM 战役、未读 `.tmp/local-test-server.txt`、未做任何晋级）

**① 为什么现在能取**。§2.7 早就写明差分分两半、改前那一半只在 E7 写卷之前可取（`.tmp/m-r41-mg1-census-before.log`、`.tmp/m-r41-provenance-before.log`）；改后这半张脚本 `.tmp/m-r72-mg1-after.sh` 先核「跑审计的树与主干的 registry 字节相同」再跑，实测两侧 `tests/fixtures/registry/reviewed-tested-bundles.json` 都是 `06cac79867e879bc00b6fc1eb3f20691d8356492b7fe1d60e67d26434bd26107`（脚本那行 stdout 里的 `\06…` 是 bash `printf` 把开头 `0` 当八进制转义的显示假象，`sha256sum` 直读无此问题）。

**② 四道读数（日志 `.tmp/m-r72/mg1-after/`）**：
- **census（18 条既有引用逐条）** `rc=0`，末行 `census: cited=18 absent_bundles=0 digest_mismatch=0` ⇒ 与 §2.7 的改前那份**逐字同值**，没有任何一条引用需要修正。
- **provenance** `verify_tested_provenance.py --data-root /data` `rc=0`。
- **门载荷** `report_promotion` `rc=1`（构造性 blocked）＋ `gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（M 侧第十五次同值）。M 在合并字节上另跑一份（`.tmp/m-r72/gates-merge/payload-post.json`，`104680` B）与 E7 lane 的封后那份（`../minekin-wt-e7/.tmp/e7/out/gate-payload-post.json`，同 `104680` B、其脚本首行 `bytes=104679`）摘要逐字相同。注意口径：`bytes=` 那行只存在于 lane 那份 `trunk_digest.py` 的输出里，M 这份从 `gate_payload_sha256=` 起头 ⇒ 比对取「文件尺寸 + sha256」两格，别把 `bytes=` 当通用字段。
- **卷面**：evidence 目录 **101**，Kin 根 **18** 枚（清单里 `kin-e7-host-0928`、`kin-e7-join-0928` 在场，其余 16 枚与 §2.64 那次普查同名同数）。

**③ 卡面要的 W40/W60/p0-core 差分：答案是「零位移」，而且是按字节读出来的零**。把封存前后两份报告按字段比，`work_packages`（11 个门：`W00 W10 W20 W30 W40 W50 W60 W70 p0-core p0-nav-exp host-integrated`）**序列化后逐字节相同**；位移只在顶层 `evidence` 普查。逐格现读：`W40` `promotable=false`、`blocks=["REQUIRED_CASE_NOT_REGISTERED"]`、`requirement.absent` 5 条（`ADMIT-010/020/030/050/090`）、`non_mandatory` 6 条；`p0-core` 同形但 `absent` 9 条（多 `ADMIT-120 CORE-080 OFFLINE-060 OFFLINE-080`）；`W60` `promotable=true`、`blocking_cases=[]`、`blocks=[]`、`absent=[]`、`satisfied=true`。**关键一条**：`W60` 的 required 集由 `src/minekin_core/domain/cases.py:288` 那三枚定（`CORE-040`/`CORE-050`/`CORE-070`），**不含** `V1201-LAN-JOINER-CONTROL-CASE-001`（它是 `mandatory: false`，只带 `work_package: W60` 标签）⇒ W60 在 E7 写卷**之前**就已经是 `promotable=true`。所以这枚真封证不点亮、也不改变任何一格的可晋级性；它在报告里只以 2 处出现（普查的 bundle 行 + attempt 行），`5086ee42…` 这个 bundle 摘要本身根本不作为字段出现。

**④ 新 LAN 证据的范围（如实写）**：`V1201-LAN-JOINER-CONTROL-CASE-001`／`case_version 1e31f000…`／attempt 序列 1 的**一枚** bundle，形状是「同一 run：受控 1.20.1 专服 + 战役 `--case` + `case_on=joiner` + 限幅 look/move/release」，14 件 artifacts 内含 `server/server.log`、`asserter-inputs.json`（`probed_players=["Kin2"]`）、`run-document.json`、`trusted/server-profile.json`、`bridge-trace.jsonl`；`from_repository_build=true`、`re_judged=AGREES`。**不覆盖**：跨 bundle 链、用户远程服（V08 未获本轮授权）、HOST 侧封存、`OFFLINE-100` 的三件套（[[project-offline-100-triple-not-judgeable-by-construction]] 仍然成立）。

**⑤ 晋级这一格按卡面停在原地**。旧 `V1201-020` 引用仍全绿 ⇒ **维持不替换**；没有真实失败 ⇒ 不需要引用修正卡。任何 `mandatory`/registry/capabilities/gaps 或 tested 晋级都要「完整 required-case 策略 + 反例 + 独立提交」，本只读卡一律没顺手改：registry 字节在审计前后同值、门载荷同值、`report_promotion` 仍 `rc=1`。若要让这枚证据进门，路径是把它接进 `REQUIRED_CASES`（那会动门载荷，须 PRE/POST 配对并具名）——那是主控保留决策，不是本轮的活。

**⑥ 队列到此的形状**：H1h→V5′→M-C1→E7→M-G1 **全部闭合**；`docs/v1201-lan-control-next-2026-09-27.md` §1 的序走完，真实封证从 0 变 1。仍开着的存量只有 `#58 (乙)`（非 auto 形状 `ONLINE_MODE=true` × 新名的真跑产物读数，要引擎窗）与 §3 的两类独立工作（`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`、B2 尚无 fixture 的非 HOST case）。主干唯一的 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；本轮不新增 `NEXT`，也不因队列走空而把目标当完成——V08/远程服、HOST 侧、跨 bundle schema 仍在各自决策门后。

## §2.68 完成度审计把两格「已闭合」拆开重量：§2.16 第 4 条第一格被活体字节证否，而 E7 记录里引的加入者「末位姿」不是序列末（第七十三轮，2026-09-28 09:28 +0800，M 主控；只读私有卷材料 + 规范卷 `:ro`，零 JVM、零写卷、未连用户远程服）

**为什么还有这一节**：目标要求把「H1k 的 §2.22 四件」与 V5′/H1i/M-C1/E7/M-G1 逐格映射到证据（映射本身闭合，见 ⑤）。映射之外我做的是**按字节重读判据**，量出两处「记录里没报数」与「报了数但那值不是序列值」。两处都只读、都可复算，没有新增任何产品字节。

### ① §2.16 第 4 条第一格（同一 run 内主持有者读数首末不变）—— 三式按名首末，M 现量

载体：`.tmp/v5p/out-host/{armed,control-off,ghost}/server.log`（V5′ 私有卷材料，仍在盘上；三份摘要逐字等于 §2.51 表里那三枚 `c6052d38…`/`975ecd6d…`/`d7bfbcdc…`）。判据读的是**行内名**（`<name> has the following entity data: [`），成对形状按 `40 位姿 + 40 朝向` 计（§「成对读数」的旧教训）。

| 式 | 名 | 位姿行数 | 首（行号 / 值） | 末（行号 / 值） | 水平位移 | 末朝向 |
| --- | --- | --- | --- | --- | --- | --- |
| `armed` | `Kin`（宿主） | 42 | L112 `[-4.5d, -60.0d, -5.5d]` | L278 `[-1.6246148188670095d, -60.0d, -2.8268089999550146d]` | **3.926040** | L279 `[0.0f, 0.0f]` |
| `armed` | `Kin2`（加入者） | 41 | L114 `[10.5d, -60.0d, -9.5d]` | L274 `[4.399447156057091d, -60.0d, -3.399447156057091d]` | 8.627485 | L275 `[45.0f, -20.0f]` |
| `control-off` | `Kin` | 42 | L98 `[8.5d, -60.0d, 7.5d]` | L266 `[8.5d, -60.0d, 7.5d]` | **0.000000** | L267 `[0.0f, 0.0f]` |
| `control-off` | `Kin2` | 40 | L106 `[10.5d, -60.0d, -8.5d]` | L262 `[10.5d, -60.0d, -8.5d]` | **0.000000** | L263 `[0.0f, 0.0f]` |
| `ghost` | `Kin` | **0** | — | — | — | — |
| `ghost` | `Kin2` | 40 | L113 `[4.5d, -60.0d, -4.5d]` | L269 `[-1.6005528439429093d, -60.0d, 1.6005528439429093d]` | 8.627485 | L270 `[45.0f, -20.0f]` |

**量到的与 §2.41 的预言相反**：§2.41 那格写的是「第一名仍走默认 `${probe:-${player}}` = 宿主 `Kin`，同一 run 内它的**首末读数必须不变**」。`armed` 式里宿主名的首末**确实变了**（3.926040 格），`control-off` 式里两名都不动。⇒ **§2.16 第 4 条第一格的字面形状在专服形状下不成立**，而 §2.51 从没报过这一格的数（只报了 `Kin` 的答题行数 84）。行数不是判据、行内容才是——这条我自己在 §2.51 末写过，本轮被自己绊了一下。

**具名改口径（§2.16 开篇要求的申报，不静默替换）**：
- 改哪条：第 4 条第一格。旧口径「同一 run 内另一具名实体首末不变」；新口径「同一份 `server.log` 上按名取**加入者**的位姿/朝向序列做首末差，并要求 `control-off` 同形状对照里**两名**的首末位移都是 `0.000000`」。
- 为什么：`armed` 的宿主名位移是实测（3.926040），旧口径的「不变」被字节证否；把判别力放在「同名按行的控制关闭对照」上，判别面不缩小（仍能区分「驱动在动」与「世界在漂」）。
- 旧口径下哪些读数作废：**没有任何已登记判据以「宿主不变」为条件**，故无读数作废；受限的是一句**未登记**的说法——「三枚控制词只作用于加入者」。`armed` 里宿主名自己在动而 `control-off` 里不动，动因（宿主也吃到注入 / 世界内推力）本轮未辨 ⇒ 登记为待判问题 **#67**，可判形状具名：`MINEKIN_DOMAIN_PROBE=Kin` 单名 + 三枚 `MINEKIN_DOMAIN_JOIN_*` 控制词全开 ⇒ 宿主末朝向等于 `[45,-20]` 即注入到宿主，仍 `[0,0]` 而位移非零即环境。要引擎窗，与 `#58 (乙)` 同窗；**不开工是因为没有已登记判据等它**。

### ② E7 封证 bundle 内的按名序列读数（规范卷 `:ro`，M 自算）—— 更正一处引用值

同一枚 bundle：`/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf`，`server/server.log` 的 manifest 条目 `3c0318252314ee443b51d4c4a2d7ba251696d8e2190ad048f81ee64d85290aa8` / `18049` B；M 只读重算 sha256 与 size ⇒ **逐字一致**（`EQUAL`，非引用 lane 的打印）。

| 名 | 答题行数 | 位姿 / 朝向 | 首 | 末 | 水平位移 |
| --- | --- | --- | --- | --- | --- |
| `Kin`（宿主） | **0** | 0 / 0 | — | — | — |
| `Kin2`（加入者） | 80 | 40 / 40 | L81 `[4.5d, -60.0d, -6.5d]`（23:58:14） | L161 `[23.061931239375966d, -60.0d, 8.017035575966826d]`（00:00:50） | **23.564584** |

末朝向 L162 `[45.0f, -20.0f]`（逐字等于 `JOIN_LOOK_YAW=45`/`JOIN_LOOK_PITCH=-20`）。离场链 L164 `Kin2 left the game`（00:00:53）→ L168 `Kin left the game`（00:00:57）。

**更正**：交付记录 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:58` 写的是「`Kin2` 位姿从 `[4.5d,-60.0d,-6.5d]` 移到 `[-1.447917…d,-60.0d,-0.336223…d]`，位移 ≈ 8.6 格 ≥ 2.0」。那枚 `[-1.44791743550326d, -60.0d, -0.33622349608875957d]` 在日志里是**一段静止平台**（L85–L113，23:58:22 到 23:59:18 重复同一坐标，共 15 行）的中段值，不是序列末。⇒ 该句引用作废，以本节的 L81→L161 / **23.564584 格** 为准。**判据结论不动**：`the_server_saw_the_kin_move` 要的是「按加入者名、首末至少一分量不同、位移 ≥2.0」，真实首末位移比引用值更大，`agrees/PASS` 与 4/4 held 无需重跑；`move_input_was_leased`/`the_bridge_carried_the_input_out`/`the_probed_player_is_this_run_s_kin` 三条的载体本轮未重量（`rejudge` 的 `agrees` 已在 §2.66 ② 落盘，引用不重复主张）。

**为什么这一格反而更硬**：封证 run 的宿主名答题行是 **0**（单名探测形状：`MINEKIN_DOMAIN_PROBE=Kin2` 且未设 `…_PROBE_SECOND`），`asserter-inputs.json` 的 `probed_players` 恰 `["Kin2"]` ⇒ ① 里那句「宿主也在动」的混淆在这枚 bundle 里**没有可被误读的第二名字**，名字盲（把宿主位移记成加入者）在此形状按构造不可发生。

### ③ 复算式（两条都零 JVM；第二段跑在容器里，卷只 `:ro`）

```bash
# 私有卷材料：三式按名首末
sha256sum .tmp/v5p/out-host/*/server.log
for s in armed control-off ghost; do echo "## $s"; \
  for n in Kin Kin2; do \
    f=.tmp/v5p/out-host/$s/answer-lines-$n.txt; \
    [ -f "$f" ] || continue; \
    echo "-- $n lines=$(wc -l <"$f")"; \
    grep -oE 'entity data: \[[0-9.,eE+-]+d, [0-9.,eE+-]+d, [0-9.,eE+-]+d\]' "$f" | sed -n '1p;$p'; \
  done; done
```

```bash
# 规范卷里的封证 bundle：manifest 比对 + 按名序列（导出到 MSYS 路径需先关路径转换）
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
docker run --rm --entrypoint /bin/bash -v minekin-runner-data:/data:ro minekin-runner:local -lc 'python3 - <<PY
import json,hashlib,math,re
d="/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf"
m=json.load(open(d+"/manifest.json")); by={a["path"]:a for a in m["artifacts"]}
raw=open(d+"/server/server.log","rb").read(); p="server/server.log"
print("manifest", by[p]["sha256"], by[p]["size"])
print("measured", hashlib.sha256(raw).hexdigest(), len(raw))
txt=raw.decode("utf-8","replace").splitlines()
for n in ("Kin","Kin2"):
    pos=[(i,re.search(r"data: \[([0-9.,eE+-]+)d, ([0-9.,eE+-]+)d, ([0-9.,eE+-]+)d\]",l).groups())
         for i,l in enumerate(txt,1)
         if (" "+n+" has the following entity data: [") in l and "d," in l]
    print(n, "pose_lines", len(pos), pos[0] if pos else "-", pos[-1] if pos else "-")
PY'
```

**我本轮自己引入又当场改掉的一处读数错**：第一次核卷把上面那段写成了内联 `python3 -c`，比较摘要时用的是 `for` 循环**退出后的最后一个 `a`**（那是 `trusted/server-profile.json`），于是打印出 `MISMATCH` 而 manifest/measured 两行字节其实同为 `3c031825…aa8`。按 `by[p]` 取回条目重算即 `EQUAL`。⇒ ③ 里给的是改正后的形状；`MISMATCH` 那次输出是脚手架作用域漏了，不是卷或 bundle 的缺陷，材料 `.tmp/m-r73/` 未删。

### ④ M-G1 与 registry 侧本轮零位移（不重复主张，只补一句现读）

`git diff --name-only 82e199c..HEAD` 仍恰三份 `docs/`（交接、本文、E7 交付记录）⇒ E7 与 M-G1 两格没动产品字节；`tests/fixtures/cases/v1201-lan-joiner-control-case-001.json` 现读 `mandatory = False`、`work_package = W60`，`src/minekin_core/domain/cases.py:288` 的 W60 required 集仍不含该案 ⇒ 晋级那一格按 §2.67 ⑤ 停在主控保留，本轮没有任何动作碰它。

### ⑤ 审计映射（每格「lane 自己提交并推送 ⇒ M 按真实 merge-base 复审合入 ⇒ push 并核远端 SHA」的笔号证据）

现读姿势：`git rev-list --parents -n1 <merge>`、`git merge-base <trunk_parent> <lane_parent>`、`git branch -r --contains <lane_tip>`、`git merge-base --is-ancestor <lane_commit> HEAD`。

| 格 | 合并笔 | trunk 父 | lane 父（在哪个远端分支上） | 真实 merge-base |
| --- | --- | --- | --- | --- |
| H1k（§2.22 四件 → §2.33 第 7 条） | `a452e84` | `4df1b2f` | `84648c0` @ `origin/codex/minekin-v1201-joiner-on-controlled-server` | `29c5187` |
| H1l（转发） | `d95e59d` | `16e0df8` | `1ce9dc0`（其父 `c345c0f` 是字节笔）@ `origin/codex/minekin-h1l-forward-join-name` | `ac1d7fb` |
| H1m（第二具名目标） | `012f56b` | `fbfd9d0` | `dff4550` @ `origin/codex/minekin-h1m-second-probe-target` | `dc0067c` |
| V5′（活体读数） | 私有卷记录笔 `docs/validation/v1201-lan-joiner-local-control-readout-2026-09-28.md` 在主干在场 | — | — | — |
| H1i（两格交回） | `b243366` | `4776f26` | `9cd58aa` @ `origin/codex/minekin-h1i-probe-target-handover` | `b35bc37` |
| H1o（旋钮转发） | `77fd13d` | `6fb974b` | `f84d4c3` @ `origin/codex/minekin-h1o-forward-seal-knobs` | `b9b0d25` |
| H1n（字面 `\n`） | `c1f6518` | `7d97188` | `fdd9f88` @ `origin/codex/minekin-h1n-kick-grep-literal-n` | `9fe3eb4` |
| H1q（按形状交回 profile） | `f5b239e` | `483eb76` | `efd3169` @ `origin/codex/minekin-h1q-joiner-world-dedicated-profile` | `354f34e` |
| #66（加入者到达） | `82e199c` | `adc6a3f` | `a4dfef4` @ `origin/codex/minekin-h66-campaign-joiner-arrival` | `527b6a7` |
| M-C1（登记 + 注册） | `4a5d353` + `163e350`（M 独占实施，卡面即如此） | — | — | — |
| E7（规范卷封证） | `d01bc5e` | `cf6d2fc` | `a7c1f99` @ `origin/codex/minekin-v1201-lan-joiner-control-seal` | `82e199c` |
| M-G1（改后半张） | §2.67（只读审计，无产品笔） | — | — | — |

表里九枚 `--no-ff` 合并笔的第二个父都在自己的远端分支上（lane 自己 push 的），merge-base 一律早于 trunk 父 ⇒ 没有「M 代 lane 提交」的形状；H1k 工作树自 `a452e84` 入干后未再被 M 写过一字。远端 `main` 本轮 `git ls-remote origin main` = 本地 `HEAD`（值见 ⑦）。

### ⑥ 约束遵守（本轮逐条对号）

规范卷只 `:ro` 读、未写（卷上 evidence 目录数与 Kin 根数未变）；未连用户远程服，`.tmp/local-test-server.txt` 未打开、本文不出现任何远程 `IP:端口`（容器 loopback `127.0.0.1:25566` 是本 harness 自己的端点）；未改 `mandatory`/registry/判据/封存 schema/`domain.sh`；私有卷 `minekin-m-v5p-live` 三式 run 目录保留未清理，其读数仍按「不是 sealed bundle」计；lane 树（`../minekin-wt-e7`、`../minekin-wt-h1k`、`../minekin`）零改动、历史 refs 不删；本轮改动只有既有两份 `.md` 的追加。

### ⑦ 门表与门载荷（本轮现读，逐道单跑先读 rc）

门清单仍按 `.github/workflows/ci.yml` 自己的 `- run:` 步取（派生脚本 `.tmp/m-r73-audit-gates.sh`，日志逐道落 `.tmp/m-r73/gates/`）。**跑门时点**：本节与交接记录**追加之前**的主干字节（`88dc441`）——追加只往两份既有 `.md` 里写段落、不新增文件，故对 `ruff format --check` 的文件数无影响；落笔之后我把 markdown 敏感的三道门（`ruff check` / `ruff format --check` / `git diff --check`）在同一棵树上重跑，逐字 `rc=0` 且 `376 files already formatted` 不变。

| 步 | rc | 逐字尾行 |
| --- | --- | --- |
| `bash -n domain.sh` | 0 | （空） |
| `bash -n run.sh` | 0 | （空） |
| `pytest contract/test_runner_scripts.py`（host uv） | 0 | `124 passed in 55.10s` |
| `uv sync --locked --dev` | 0 | `Checked 18 packages in 9ms` |
| `ruff check .` | 0 | `All checks passed!` |
| `ruff format --check .` | 0 | `376 files already formatted` |
| `pyright` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest -q`（全量，host） | 0 | `2712 passed, 2 skipped in 476.11s (0:07:56)` |
| `check_boundaries.py` | 0 | `Minekin package dependency boundaries: OK` |
| `check_case_assertions.py` | 0 | `Case assertion implementations: OK (151 registered)` |
| `verify_fixture_digests.py` | 0 | `W00 schema and fixture digests: OK` |
| `check_workflow_pins.py` | 0 | `Workflow pins: OK (every action is a commit, and each names its release)` |
| `uv build --wheel` | 0 | `Successfully built dist\minekin_core-0.0.0-py3-none-any.whl` |
| `check_wheel_boundary.py dist/*.whl` | 0 | `Wheel oracle boundary: OK (dist\minekin_core-0.0.0-py3-none-any.whl)` |
| `minekin --help` | 0 | `-h, --help   show this help message and exit` |
| `git diff --check` | 0 | （空） |
| `pytest contract`（容器 CPython 3.12） | 0 | `124 passed, 1 warning in 3.85s` |
| 三枚具名单元 `-k "sealed_probe_names or joiner_server_log_guard or joiner_control_driver"`（容器） | 0 | `15 passed, 109 deselected, 1 warning in 0.64s` |
| `report_promotion.py --data-root /data`（容器，规范卷 `:ro`） | **1** | `size=104680`（预期阻塞形状） |

全量套件的**计数与基线逐字相同**（`2712 passed, 2 skipped`），只是耗时从 335.86s 变成 476.11s —— 这段窗内我自己另挂了两次只读容器核卷（② 与 ⑥ 的卷面普查），宿主争用属预期，不是套件变慢。

门载荷：`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，M 侧第 **16** 次同值；`rc=1` 的阻塞清单仍由 HOST/HOSTCOMMIT/HOSTCTL 一族点名 ⇒ 晋级那一格与本轮无接触。远端与本地的落点：`git ls-remote origin refs/heads/main` = 本地 `HEAD` = `88dc44116d8f356bd10e2ca6ba6acfe7abd526bb`（本节记录笔 push 后另读一次）。


### ⑧ 四态与队列

已合主干且 CI 绿 = `88dc441` 及其前；本轮记录笔 push 后要读 CI 才算绿（**不在读数之前宣称**）。仅在分支 = 无。真实封证 = **1**（`5086ee42…64f6` / run `a224f6c3…`，attempt 序列 1；② 只更正一处引用值，不改判据结论）。未验证/待判 = `#58 (乙)`、**#67（新登记）**、§3 两类独立工作（`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`、B2 尚无 fixture 的非 HOST case）、V08/远程服与 HOST 侧（各守主控决策门）。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；**队列走空、轮次充裕都不构成本目标的完成条件**，目标里点名要推进的五格与 H1k 都已落到笔号，晋级那一格按卡面停在主控保留。

## §2.69 补上 §2.68 预留的那两格读数：记录笔已 push 且远端 SHA 回读一致，该笔 CI 三 job 步骤级无红（第七十四轮，2026-09-28 09:49 +0800，M 主控；零 JVM、零写卷、未连用户远程服）

### ① 本节只补两格，不重开审计

§2.68 ⑦/⑧ 留了两条前瞻句：「远端 `main` = 本地 `HEAD` = `88dc441…`（本节记录笔 push 后另读一次）」和「本轮记录笔 push 后要读 CI 才算绿（未在读数前不宣称）」。本节把这两格按实际字节填上，并附一次 lane 工作树的现测。审计本身（八→九枚合并笔映射、发现一/发现二）已在 §2.68 闭合，不在本节范围。

### ② push 与远端 SHA 回读（具名操作顺序）

- 记录笔 `c43a6d31475330a1c1b63e9b33ac3daa72336a16`（§2.68 那 138 行 + handoff 第七十三轮那 11 行）落在 `main` 上，本地主树 `minekin-wt-integration` 工作树 `git status --porcelain | wc -l` = **0**。
- push 用显式 refspec，**不用 `HEAD:main`**：M 的默认目录 `Documents/agent_work/minekin` 当前检出的是另一条 lane 分支 `codex/core-state-transition`（`6a02ac6`），若在此目录 `push HEAD:main` 会把 lane 的历史推上主干。实际命令：
  `git -c credential.helper= -c credential.helper=wincred push origin main:main`（在 `minekin-wt-integration` 内）
  ⇒ 输出 `88dc441..c43a6d3  main -> main`，token 只经默认凭据助手取用、未回显。
- 回读：`git ls-remote origin refs/heads/main` = **`c43a6d31475330a1c1b63e9b33ac3daa72336a16`** = 本地 `main` ⇒ §2.68 ⑦ 那格从「push 前值 `88dc441`」更新为「push 后值 `c43a6d3`」，`88dc441` 作为其前驱读数原样留在 §2.68，不改写。

### ③ 该笔 CI 的逐步读数（先取数、后宣称）

复跑命令（同 §2.32 姿势，REST 不需 token 也能读 public 仓库的 workflow runs）：

```bash
python .tmp/ci_steps.py c43a6d3   # 日志：.tmp/m-r74-ci-c43a6d3.log
```

现读（run `36367171883`，`head_sha` 用全 40 位）：

| job | status | conclusion | 步数 | 步骤级 non_success |
| --- | --- | --- | --- | --- |
| `python` | completed | success | 18 | 无 |
| `bridge-static` | completed | success | 9 | 无 |
| `protocol` | completed | success | 10 | 无 |

三 job 的步骤清单里没有 `failure/cancelled/timed_out` 行 ⇒ 才写「`c43a6d3` CI 绿」。补充两格口径：① 首次轮询时 `python` 显示 **17 步**，是最后一步（Post-run/收尾）当时尚未生成，跑完才成 18 步，不是多插了一道门；② push 后约 3.5 分钟才 completed，中间那次「仍 in_progress」的读数也留在 `.tmp/m-r74/` 两份日志里（`m-r74-ci-final.log` 取到 completed 前一刻）。本节自身这笔记录（§2.69 落地笔）的 CI **不在本节宣称**，按同一规则由下一次读数补记。

### ④ lane 工作树现测（objective 点名的第一格，本轮再量一次）

- `minekin-wt-h1k` 检出分支 `codex/minekin-h1l-forward-join-name`，tip = **`1ce9dc0dfdd6a939e1b0e70c08959b30f5541bf7`**，与 `git ls-remote origin` 同名分支的远端值逐字相同 ⇒ lane 自己的提交已自己推上去，没有「M 代提交」的形状。
- `git status --porcelain` = **0 行**：§2.33 合入时该树里在途的未提交文件，现在已由 lane 自己落成 `1ce9dc0`（H1l 的读数/反证/全部门记录）并入干（合并笔 `d95e59d`）。这不代表 lane 停工——只代表此刻没有待复审的脏字节。
- 失败材料仍在案：该树 `.tmp/` 下 `h1k-*` 计 **47** 个文件未删；M 本轮在该树零写入，也未删任何 ref。

### ⑤ 约束逐条对号（本轮实际做的事只有 push + 只读）

零 JVM、零写规范卷（本轮没跑任何 run，只读 `.tmp/v5p/`、`.tmp/m-r73/gates/` 既有材料）；未连用户远程服、未打开 `.tmp/local-test-server.txt`；未改 `mandatory`/registry/判据/封存 schema（本轮 diff 只含两份既有 `docs/*.md` 的追加）；私有卷 `minekin-m-v5p-live` 的成功读数仍按「不是 sealed bundle」计；§2.68 的两处更正（发现一换判别承担者、发现二作废一句引用）不削弱那枚真封证（`5086ee42…64f6` / run `a224f6c3…`，4/4 held、`agrees/PASS`）；晋级那一格仍停在主控保留，`gate_payload_sha256` 不因本节位移。

### ⑥ 四态与队列（本节的净变化只有一格）

已合主干且 CI 绿 = **`c43a6d3`**（本节实测）及其前；真实封证 = **1**（`5086ee42…64f6`，未变）；仅在分支 = 无；未验证/待判 = `#58 (乙)`、`#67`（都要引擎窗）、§3 两类独立工作（`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`、B2 尚未做 fixture 的非 HOST case）、V08/远程服与 HOST 侧（各守主控决策门）。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`，本节不新增 `NEXT`；队列走空与轮次富余都不构成本目标的完成条件——点名要推进的 H1k + V5′/H1i/M-C1/E7/M-G1 五格已落到笔号且远端 SHA 与 CI 均有读数，剩余的待判格与保留决策仍开放。

## §2.70 #67 判完：控制词不作用于宿主（契约测试早已钉住，§2.68 那句「未登记」是错的），但量到了一格**未请求的自行位移**——它反过来收窄了 E7 那格的解释（第七十五轮，2026-09-28 10:12 +0800，M 主控；私有卷两次活体 + 规范卷 `:ro` 取一份日志副本）

**为什么还有这一节**：§2.68 把「三枚控制词是否也作用于宿主」登记成待判 #67，并命名了一个可判形状。本轮先读仓库字节，发现那一格**早就有登记的判据**（我上一轮说它「未登记」是错的）；随后在私有卷跑了两个新式做判别，量出了比 #67 更要紧的东西——受控客户端会在没有被请求的朝向上自己位移，而 E7 那枚真封证里就带着这种位移。三处都需要具名落账。

### ① #67 的「注入」半格：判**否**，由已登记的契约测试承担（并更正 §2.68）

- `tests/contract/test_runner_scripts.py:3162` `test_the_joiner_control_driver_keeps_its_bounds_and_reaches_one_line_only()` 里就有这三条：`text.count('"${joiner_control_args[@]}"') == 1`（失败信息正是「the bounded ask reaches somewhere other than the joining client's array」）、宿主启动片段 `assert '"$@"' in host_launch` + `assert "joiner" not in host_launch`（注释原话：Nothing at all on the way to the hosting session's line）、以及 `count("python -m minekin_core session start") == 1`。
- 仓库字节同向：三枚名字的唯一落点是 `test-orchestrator/runner/domain.sh:738/741/744` 组成 `joiner_control_args`，只在 `:759` 的 `build_joiner_session_argv` 里被拼接，而该数组只在 `:1771` 拉起加入者客户端；宿主那行是 `"$@"`（`:1754` 的注释就写着「the hosting session's line is the run's own arguments, and never sees it」）。`MINEKIN_DOMAIN_JOIN` 未设时该 ask 直接 `exit 2` 具名拒止（`:689-693`）。
- 这条测试就在本轮的门格里：三枚具名单元 `-k "sealed_probe_names or joiner_server_log_guard or joiner_control_driver"` 的 15 passed 含它；契约全量 124 passed 也含它。
- ⇒ **更正 §2.68 ① 末段那句**：「受限的是一句**未登记**的说法——三枚控制词只作用于加入者」。它不是未登记，它登记在契约测试里；受限的只是我没有去读那张网。

### ② §2.68 命名的可判形状作废：宿主名的朝向字段不承载注入

§2.68 写的是「宿主末朝向等于 `[45,-20]` 即注入到宿主，仍 `[0,0]` 而位移非零即环境」。现量：**宿主名 `Kin` 的朝向读数在 5 个式、163 次朝向行里全部是 `[0.0f, 0.0f]`**（`max_abs_rot = 0.0`），连它自己走了 11.926812 格的那一次也是零；同一段赋值 `[45.0f, -20.0f]` 在**加入者名**上能读到（`r67-join-look-only` 里加入者位移 0.000000 而末朝向恰等于赋值）。⇒ 朝向这一维只在加入者名上有承载，「宿主末朝向不等于赋值」既不能证真也不能证伪——**形状作废**，替换为：⑴ 契约测试钉住唯一 splice 点（①），⑵ 按名位移的三格设计（armed / look-only / control-off，见 ③）。旧句按 dated-findings 规矩原样留在 §2.68，不改写。

### ③ 私有卷两式新读数（材料 `.tmp/r67/out-host/`，`rc(live)=0` 两次）

| 式 | 名 | 位姿行数 | 首（时刻 / 值） | 末（时刻 / 值） | 水平位移 | 末朝向 | `max_abs_rot` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `r67-armed-repro`（与 v5p `armed` 同问） | `Kin`（宿主） | 40 | 01:59:43 `[10.5,-60,-7.5]` | 02:02:24 `[4.506797343146687,-60,2.811661233830395]` | **11.926812** | `[0.0f, 0.0f]` | 0.0 |
| `r67-armed-repro` | `Kin2`（加入者） | 41 | 01:59:39 `[8.5,-60,1.5]` | 02:02:20 `[-2.849720409939202,-60,18.306832584582356]` | 20.280182 | `[45.0f, -20.0f]` | 45.0 |
| `r67-join-look-only`（只开两枚 LOOK，`HOLD_FORWARD` 不设） | `Kin` | 39 | 02:03:27 `[-0.5,-60,5.5]` | 02:06:04 `[-0.5,-60,5.5]` | **0.000000** | `[0.0f, 0.0f]` | 0.0 |
| `r67-join-look-only` | `Kin2` | 40 | 02:03:27 `[-9.5,-60,2.5]` | 02:06:04 `[-9.5,-60,2.5]` | **0.000000** | `[45.0f, -20.0f]` | 45.0 |

线段分解（按名取「顺序去重后的相邻不同值」，三位小数下算，误差 1e-3）：

- `r67-armed-repro` 加入者**首段** 01:59:39→01:59:47 长 **8.628117**，方向 `yaw 45.00°`；v5p-armed 的同段是 **8.627485** ⇒ **被请求的那一次按住行走是跨 run 可复现的**（差 0.000632）。
- 同式加入者**按住窗之后** 01:59:47→02:01:18 又走 **11.923525**，方向 `yaw 26.12°`；宿主同期 01:59:43→02:01:06 走 **11.927003**，方向 `yaw 30.13°`。两名**等距（差 0.0035）而不同向（差 4.0°）** ⇒ 不是世界刚体平移，也不是同一次注入的两份拷贝：宿主那一名按 ① 接不到注入词。
- v5p-armed 的宿主只在最后一次读数出现 **3.925628 @ 312.91°**（且发生在 `16:13:02 Kin2 lost connection` 之后）。
- ⇒ 存在一格**未请求的自行位移**（两名都有，量级 4~26 格，方向与赋值的 45° 无关）。它正是 §2.68 用「位移非零即环境」一句话盖过去的那类东西，本轮把它量成了独立事实。

### ④ 这格事实反过来收窄 E7 那枚真封证的解释（判据结论不动，且更硬）

只读规范卷取回 `server/server.log` 副本（`.tmp/r67/e7-server.log`，sha256 `3c0318252314ee443b51d4c4a2d7ba251696d8e2190ad048f81ee64d85290aa8` / 18049 B，逐字等于 manifest 条目 ⇒ 副本可信）。按线段拆：

| 段 | 时刻 | 长度 | 方向 | 归因 |
| --- | --- | --- | --- | --- |
| 注入段 | 23:58:14→23:58:22（两小段 1.202306 @37.81° + 7.371403 @44.98°） | 合成 **8.566** | 贴住赋值 45° | 被请求的 2 秒按住 |
| 平台 | 23:58:22→23:59:22（60 s 不动） | 0.000 | — | 无输入 |
| 未请求段 | 23:59:22→23:59:50（8 段，每 4 s 约 3.97 格 ≈ 1 格/秒） | **25.896** | `yaw 288~289°` | 与赋值方向无关 |

- 三件判据结论都**不因此变**：末朝向逐字等于赋值（注入确实落到加入者）、`Kin` 0 行（单名探测）、4/4 held 与 `agrees/PASS`。
- 但 §2.68 ② 那句「位移 23.564584」要加一条口径：它是 **8.566（注入段）+ 25.896（未请求段）的合成**，方向不同 ⇒ 这个数**不能**当作注入的量。反过来它也给了一格更强的东西：**把未请求段整段剥掉，注入段自己就是 8.566 ≥ 2.0** ⇒ E7 的位移门不靠那 25.9 格也过。
- 门的弱点同时被量清：`tools/assert_case_evidence.py:1647 the_server_saw_the_kin_move` 只取 `probe_readings(..., 3)` 的首末水平差 ≥ `MINIMUM_STEP_BLOCKS = 2.0`（`:235`），**不看方向** ⇒ 一次注入完全失败的 run 只要带着 25.9 格自行位移也能满足这一格。现在承担非恒真的只有两处：同 run 的 `control-off` 双名零位移（本轮 `r67-join-look-only` 再次给出两名 0.000000 + 朝向承载分离）和单名探测。
- 登记为待判 **#68**：受控客户端存在未请求的自行位移 ⇒ 位移门需要按方向分段（只认与赋值同向的那一段）或把 `control-off` 纳入同 run 封存。两条都在判据/封存 schema 侧 ⇒ **主控保留**，M 只登记并保留材料，不改 `mandatory`/registry/判据。

### ⑤ 脚手架的具名收窄与本轮读数坑

- `.tmp/r67/run-shape.sh` 复用了未改动的 `.tmp/v5p/{prep,drive}.sh`（挂载为 `/drv:ro`），只换了外层。它把 v5p 的「`docker ps` 非空即拒」收窄成「容器名/镜像命中 `minekin|kin-|runner|minerun|java|minecraft` 才拒」，并加了 loopback `:25566` 空闲检查。原因具名：本窗内有两个别的项目的 redis-stack 容器（`statefix-audit`、`redis-tool-statefix-refactor__…`，Up 21 分钟），按原守卫会误拒；收窄后仍然打印完整 `docker ps`，两式实际起前读到的是「25566 空闲 + 无引擎命中」。
- 本轮自己踩的一次错并已改：第一次算线段时用了命名组的位置号（`m.group(1)` 其实是时间戳，名字是 `group(2)`），于是两张表都打印 `distinct 0`。改成具名取 `group('name')` 后读数如上。那次误印没有落进任何结论，`0` 也没被当成「没有位移」来用。
- 复算命令（可重跑）：`python .tmp/r67/read_seq.py '[[tag,relpath,name],…]'`（cwd 须为 `.tmp`）；`bash .tmp/r67/run-shape.sh` 需 `V5P_SHAPE=r67-armed-repro|r67-join-look-only`；整程日志 `.tmp/r67/campaign.log`。

### ⑥ 门与载荷（本轮无产品字节改动；逐道先读 rc）

- `ruff check .` **rc=0**（`All checks passed!`）、`ruff format --check .` **rc=0**（`376 files already formatted`，日志 `.tmp/m-r74/ruff-check.log` / `ruff-format.log`）——这两道在 §2.69 落盘后已跑过，本轮记录笔落盘后再各取一次。
- 门载荷第 **17** 次同值：`report_promotion.py --data-root /data`（容器、规范卷 `:ro`）**rc=1**（预期阻塞）、`size=104680`，`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（`.tmp/m-r75/payload.digest.txt`）⇒ 本轮的两式活体与文档追加都不动载荷。
- 规范卷卷面未变：`evidence_dirs=101`、`kin_roots=18`、`server_runs=186`。
- §2.69 预留的那格补上：记录笔 `050f371` 的 CI run `36367646103` = `completed/success`，三 job 步骤级 non_success 全空（`python` 18 步、`bridge-static` 9 步、`protocol` 10 步，日志 `.tmp/m-r75-ci-050f371.log`）。**本节自身这笔的 CI 仍不在本节宣称。**

### ⑦ 约束逐条对号

私有卷两次活体（`minekin-m-v5p-live`），规范卷只 `:ro` 且只取一份日志副本到 `.tmp/r67/`；零 JVM 于用户远程服（未连、`.tmp/local-test-server.txt` 未打开）；`mandatory`/registry/判据/封存 schema 一字未动（#68 只登记）；私有卷的成功读数按「不是 sealed bundle」计；真封证仍 = 1（`5086ee42…64f6` / run `a224f6c3…`，本轮只收窄其一格解释、不改判据结论）；lane 树零改动、无 ref 删除。

### ⑧ 四态与队列

#67 → **判完（否，不作用于宿主）**，并作废 §2.68 那个无判别力的形状；新登记 **#68**（未请求的自行位移 ⇒ 位移门的按方向分段/同 run 对照，属判据与 schema 侧，主控保留）。已合主干且 CI 绿 = `050f371` 及其前；真实封证 = 1；仅在分支 = 无；未验证/待判 = `#58 (乙)`、`#68`、§3 两类独立工作、V08/远程服与 HOST 侧。主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`，本轮不新增 `NEXT`；以上任何一格都不因队列走空或轮次富余而算目标完成。

## §2.71 (乙) 的真读数：`ONLINE_MODE=true` 的专服形状把具名失配落在**两份台账**，而编排层只知道超时（第七十六轮，M 主控；私有卷三式活体，规范卷一字未挂）

### ① 为什么补这一节

§2.26 撤回 §2.25 的「第八对缺口」之后，#58 只剩一格没读：`JOIN_ON_CONTROLLED_SERVER=1` 与 `ONLINE_MODE=true` 都被显式设、而 `case_id` **不是** ADMIT-040 时，产物是「具名失配」还是「加入者静默超时」。§2.25 还留了三个式名（A=该组合、B=正对照 `false`、C=默认关闭字节等价）。本轮把 A 跑出来，并各加一式做判别。

### ② 字节侧的三件前置事实（现字节；§2.25/§2.26 的历史行号按规矩原样保留不改写）

- guard 区间 `test-orchestrator/runner/domain.sh:511-540` 恰七条具名拒止（joiner 缺席 / `--server-profile` 缺席 / `open_lan` / `black_hole` / `no_server` / `not_whitelisted` / `refusal_asked`），**没有任何一条涉及 `MINEKIN_DOMAIN_ONLINE_MODE`** ⇒ 「非 auto 形状无门口拒止」在当前字节上成立，本轮的 A 式也确实没被拒止截住（它跑到了起服务端、起了两个客户端）。
- 强制 online-mode 的通路：`:96` 取值 → `:1076-1085` 铸 `--online-mode` / `--no-online-mode` → `:1100-1112` 拼进**同一条** `tools/run_controlled_server.py … --keep-running` 命令 ⇒ 一个服务端进程、一份 `server.properties`。
- 既有具名承担者的位置在现字节上漂了，本轮重取：`tests/unit/test_case_evidence_assertions.py:3715` → **:3721**；`tests/contract/test_runner_scripts.py:299` → **:360**；`domain.sh:1788` 的 ADMIT-040 判定分支 → **:1992**（形状前置 `:1996-1999`，台账谓词 SQL `:2004-2006`）。漂移来源是 H1h/H1i/H1k 先后往同两个文件加面，不是判据换过。

### ③ A 式 `r75e-online-join`（`ONLINE_MODE=true` × 专服加入者，`--case` 未设）

材料 `.tmp/r75e/out-host/r75e-online-join/`；容器 `rc(live)=0`，**`domain.sh rc=14`**（02:23:14Z→02:28:43Z）。

- 落盘的服务端设置：`/data/server-runs/run-7/server.properties` 第 34 行 `online-mode=true`，同档 `white-list=true` / `enforce-whitelist=true` / `server-port=25566` / `level-seed=minekin-p0-controlled`；`run_controlled_server.py` 自己的日志回读 `enable-status: asked for false, the settings written say false` ⇒ 本轮没有顺手打开 status 面。
- **失配不是加入者专属**：`server.log`（sha256 `c68e1a315a7a70ba5a54b8f7786d612c0464facc423be160cdee10aaccbce219` / 16379 B）里两名都被拒 —— `02:24:13 … GameProfile@5f22f747[id=<null>,name=Kin2 …] lost connection: Disconnected`、`02:24:14 … GameProfile@3dbdc3cb[id=<null>,name=Kin …] lost connection: Disconnected`。两个 `id=<null>` 逐字说明服务端没拿到可校验的身份：一个进程一份策略，宿主和加入者同受。
- **具名失配落在两份台账**（只取本 run 追加的行；baseline host=105 / joiner=120）：两名都走 `AuthPolicyFrozen{auth_mode:"offline", online_adapter_enabled:false}` → `…READY_MENU→CONNECTING→FAILED`，并在 `FAILED` 处落下同一条 `SessionInterrupted src=BRIDGE trust=BRIDGE_FILTERED payload={"phase":"FAILED","reason":"ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH"}`（host position 117 / joiner position 132），随后 `STOPPING→STOPPED` 与 `SessionInterrupted src=CORE payload={"outcome":"BRIDGE_LOST"}`。按 ADMIT-040 那条谓词逐台账问一次：**host 命中 1、joiner 命中 1**。两份的 `AuthPolicyFrozen` 各自指着不同 profile（宿主 `p0-controlled-offline-loopback-1201`、加入者 `p0-lan-host-fixture`），⇒ 该判定不依赖某一个 profile 文档，是形状属性。
- **编排层不知道这件事**：`domain: Kin2 never arrived within 150s` + `downstream reading — THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW …` + `domain: Kin2 arrived but never became playable within 150s`，宿主 run document 给 `connection_state=FAILED / outcome=BRIDGE_LOST / snapshots_admitted=0 / cognition_refusals{"MANAGEMENT_ONLY_DTO":50}`，退出码 **14**。⇒ (乙) 的答案是**两层分裂的同一 run**：ledger 判定层具名、编排层只报超时；既不是「只有静默超时」，也不是「run 被具名判成失配」。
- 加入者客户端 `domain-join-session.err` 是**空文件**（sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，size 0）⇒ 拒绝发生在服务端握手侧，客户端一句没说。
- 同一份 `server.log` 的三个计数把「谁拒的」钉住：`joined the game` **0 次**、`has the following entity data:` 应答行 **0 次**（没人进世界，探针按构造无话可说）、含 `whitelist` 的行 **0 次** ⇒ 拦下两人的是会话校验而不是白名单，尽管 `white-list=true` 且 `enforce-whitelist=true` 在场、两名也确实都在 `--allow-player` 名单里（`§2.13` 那条加入者名单在位）。这也把 §2.20 那类「两名是否因白名单被挡」的解释在本式排除。

### ④ 单 Kin 判别式 `r75e-online-hostonly`（同一开关，加入者面撤掉）

材料 `.tmp/r75e/out-host/r75e-online-hostonly/`；**`domain.sh rc=14`**（02:28:48Z→02:31:45Z）。这一式只为回答「失配是不是加入者专属」：

- 同一份开关落到同一份落盘：`/data/server-runs/run-8/server.properties` 第 34 行仍是 `online-mode=true`（`white-list=true`/`enforce-whitelist=true`/`25566`），`run-8` 而非 `run-7` ⇒ 每 run 一个新目录的规矩在私有卷上同样生效。
- 服务端日志（sha256 `087e16746e5c4b1925ae7818ffe4c79a450d6ec24ac36ec4d67cd9118a022ab3` / 12287 B）只有一条拒绝：`02:29:41 … GameProfile@428b13b1[id=<null>,name=Kin …] lost connection: Disconnected` —— **只有一个 Kin，也被同样拒掉**。
- 宿主台账在 baseline 120 之后追加的第 132 行就是那条具名失配（`SessionInterrupted src=BRIDGE trust=BRIDGE_FILTERED payload={"phase":"FAILED","reason":"ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH"}`，ADMIT-040 谓词命中 **1**），加入者台账一字未动（命中 **0**，且 `domain-join-profile.json` / `domain-join-session.json` / `domain-join-session.err` 三件全部 `WAS NOT WRITTEN`）。
- 编排侧同 A 式一样静默：只打印 run document（`connection_state=FAILED / outcome=BRIDGE_LOST / snapshots_admitted=0`）就退到 **rc=14**，没有「the session recorded the expected auth mismatch」那句 —— 那句属于 `case_id=ADMIT-040` 的等待分支（`:1992-2017`），本式没点 case ⇒ 具名行在台账里，而 harness 的判词只在点了该案时才说。

⇒ 「一次策略 / 一个进程」为**真**，且**失配不是加入者专属**：A 式里两名同被拒、本式里单 Kin 也被拒。加入者在不在场只改变「几行具名失配被记下」（A 式两份台账各 1 行；本式宿主 1 行、加入者 0 行），不改变被拒这件事本身。

### ⑤ B 式正对照 `r75e-online-false`（显式 `false`，其余与 A 式逐字同）

材料 `.tmp/r75e/out-host/r75e-online-false/`；`rc(live)=0`，**`domain.sh rc=14`**（02:32:01Z→02:33:19Z）。这一式只问一件事：A 式那两格命中是不是恒真构造。

- 落盘端只差了那一个开关：`/data/server-runs/run-9/server.properties` 第 34 行 **`online-mode=false`**，同档 `white-list=true` / `enforce-whitelist=true` / `server-port=25566` / `level-seed=minekin-p0-controlled` 与 A 式逐字同；`run_controlled_server.py` 自己的日志仍回读 `enable-status: asked for false, the settings written say false` ⇒ status 面没被顺手打开。服务端在 `server.log` 第 43 行自己警告 `The server will make no attempt to authenticate usernames. Beware.`
- **两名都进了世界**：`02:32:48 Kin joined the game`、`02:32:58 Kin2 joined the game`（sha256 `9833ae2cde889c30fe2cccc5819634ea95ac6d062ec833b62678df6b83688dfd` / 10799 B）。同一套计数与 A 式对撞：`joined the game` **2**、`id=<null>` **0**、探针应答行 `has the following entity data:` **6**（A 式对应 0 / 2 / 0）⇒ A 式那三个零计数是形状后果，不是读法 artefact。
- **具名失配消失，且是按同一条谓词消失的**：两份台账（baseline 都取在 135）各自走完 `CONNECTING→JOINED_UNVERIFIED→PLAYABLE`，各有一条 `SessionIdentityCompared`（宿主 `session_username:"Kin"`、加入者 `"Kin2"`，两条都 `matched:true / mismatches:[] / credential_values_exposed:false`）与一条 `PlayableEstablished`，全程没有 `ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH`；逐台账再问一次那条 ADMIT-040 谓词：**host 命中 0、joiner 命中 0**（A 式 1/1，④ 式 1/0）⇒ 该谓词有判别力，A 式的命中不是恒真。
- 编排层也第一次说到了事：`domain: the world heard Kin2 arrive`、`domain: Kin2 admitted its first snapshot of that world`，加入者收尾 `{'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 25}`，宿主 run document `connection_state=PLAYABLE / snapshots_admitted=1 / entities_admitted=16 / perceived_information_class=PLAYER_EQUIVALENT`。
- **`rc=14` 在本式同样出现 ⇒ 退出码在这一族里无判别力**：A（两名被拒）、④（单名被拒）、本式（两名 PLAYABLE 且服务端记到进世界）三式都退 14。它只说「会话没走到 harness 要的终局」，不说谁被拒、也不说有没有到达；本式也没打印「the session recorded the expected auth mismatch」那句判词，因为 `--case` 未点。**这一格比我上一轮写下的「编排层只知道超时」更硬**：不止编排层少说话，而是它给三种相反事实同一个码。判别只能落在台账与握手行上。
- 一处自伤的坑（具名登记以便复跑）：campaign 里 `==== R75E r75e-online-hostonly rc=2` 那格外层码不是产物停点 —— 真实原因是 **④ 式仍在执行时我改了同一份 `run-shape.sh`**（bash 按字节偏移惰性读脚本，改后偏移错位 → `.tmp/r75e/run-shape.sh: line 89: syntax error near unexpected token 'then'`）。它发生在 drive.sh 的读数全部打完之后 ⇒ ④ 的台账/日志/落盘三件数据完整，只丢了收尾那行 `rc(live)`；同一份新字节随后被 ⑤ 式干净读完（`bash -n` 现通过，`rc(live)=0`）。规矩：**式与式之间不写脚手架**。

### ⑥ 顺带核到的一格四态更正：`codex/parallel-execution-plan` 是陈旧副本，M 不合入

- 全分支普查（`git rev-list --count origin/main..<每支>`）里它是唯一 `ahead=2` 的分支（笔题 `21ffbac`「define isolated parallel Minekin development lanes」／`e472897`「add isolated 1.20.1 live-validation lane」，merge-base `6f0f562`）。
- 复审看的不是它缺什么，而是它相对主干**多什么**：`docs/parallel-execution-plan.md` 在主干是 blob `06c9204f…`、在该分支是 `7bb8446b…`，两 blob 互 diff = **+3/−26** —— 分支那份缺掉主干的「M 侧审查的写操作边界（第四轮补）」整段与整张「冲突表登记」，版本行也停在「2026-09-26」而没有主干那句「已与主干状态原子对齐」。
- 同笔笔题已在主干：`git log origin/main --grep=` 给 `13b84a8` 与 `432cc37` ⇒ `ahead=2` 是重写过的同名提交，不是未合的新工作。
- ⇒ **合入它会让主干计划文档倒退 26 行**（删掉既有写边界与登记表），M 拒绝合并；分支按协议保留不删。四态的「仅在分支」因此仍是**无待合产品工作**，但这一格从此具名：不可合的陈旧副本，而非空。
- 同时复量的 lane 面：`../minekin-wt-h1k` tip `1ce9dc0`、脏 0 行、`origin/main..HEAD = 0` ⇒ §2.22 的 ①②③④ 与该 lane 的在途工作已全部在主干，M 本轮对 lane 树零写入。

### ⑦ 约束逐条对号

三式活体都在 M 私有卷 `minekin-m-v5p-live`，规范卷 `minekin-runner-data` **一字未挂**（连 `:ro` 都没有）⇒ 本节的读数不是 sealed bundle，也不冒充；零连接用户远程服（`.tmp/local-test-server.txt` 未打开，端点只有容器 loopback `127.0.0.1:25566`）；`mandatory`/registry/判据/封存 schema 一字未动（本轮只把「既有具名承担者的位置」重取成新行号）；未给加入者开任何在线凭据路径、未放宽认证/地址/lease（A 式就是按硬禁的形状跑到它自己停的地方）。私有卷材料留在 `.tmp/r75e/out-host/`。

### ⑧ 四态与队列

- **已合主干且 CI 绿**：`c63b8dd`（= 远端 `refs/heads/main` 逐字同值）及其前；该笔自身 run `36369358628` = completed/success（python 18 步 / bridge-static 9 步 / protocol 10 步，步骤级无红）。**本节这笔提交自身的 CI 不在本节宣称**，留给下一笔补记。
- **真实封证**：仍 **1**（bundle `5086ee42…64f6` / run `a224f6c3…`）。本轮三式活体全在私有卷、规范卷一字未挂 ⇒ 零新封、零移动，§2.70 对那枚封证的 #68 收窄不变。
- **仅在分支**：**无待合产品工作**，但普查里两格「ahead≠0」本轮都具名成「不可合的陈旧副本」而非「未合的新工作」：
  - `codex/parallel-execution-plan` `ahead=2`（远端也在）⇒ ⑥ 已量：主干那份计划文档会被倒退 26 行，M 拒合、分支保留。
  - `worktree-plan-coverage-001` `ahead=1`（本地从未推远端）⇒ 它那一笔 `c864666`「feat(cases): make required coverage explicit」与主干 `6863be91` **patch-id 完全相同**（`8a492580…`），即同一改动已重写入干；且该笔所触 `src/minekin_core/domain/cases.py` 在主干已前进（branch `80f6a98d` → main `d1859a90`）⇒ 合它同样会倒退。普查里其余分支 `ahead=0`，含 `worktree-case-core-001`（tip `f1cbe63` 是主干祖先）。
  - lane 侧：`codex/minekin-lan-joiner-bounded-control` tip `1ce9dc0`、脏 0 行、`origin/main..HEAD = 0` ⇒ §2.22 与 H1k 的在途工作全部已在主干，M 本轮对 lane 树零写入、零代提交；主目录检出的 `codex/core-state-transition@6a02ac6` 亦 `ahead=0`。
- **未验证/待判**：`#58 (乙)` 本轮**判完**（三式：A 具名失配落两份台账 / ④ 单名同拒 / ⑤ 显式 `false` 两名 PLAYABLE 且谓词命中 0 ⇒ 两层层分裂 + 非恒真）；仍开放的是 **#68**（未请求自行位移可单独满足 `the_server_saw_the_kin_move`，属判据与封存 schema 侧 ⇒ 主控保留）、⑤ 新登记的「退出码 14 无判别力」是否要接成判据（同样主控保留，本轮不动判据）、§3 两类独立工作（只读 Gateway 契约设计、B2 非 HOST case 先设 oracle 后真跑）、V08/远程服与 HOST/PERSIST 侧。
- **队列**：主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；本节不新增 `NEXT`，也不以「三式跑完」或「暂无待合分支」作为 goal 完成条件。

## §2.72 第七十六轮欠的两格补记：`c3a3bf5` 自身的 CI 已读到步骤级，规范卷「卷面」这一格反而暴露出口径不成立（第七十七轮，M 主控）

### ① 为什么单独补一节

§2.71（判完 `#58 (乙)`）落盘并按规矩提交后，账上欠两格：那笔提交**自身的** CI（按纪律不在本节宣称，也不许引用上一笔的绿充数），和 §2.70 起沿用的规范卷「卷面」三元组。前者本轮读到了；后者本轮量出来发现**口径本身站不住**，所以两格一起补，并把其中一格改成具名空白。

### ② `c3a3bf5` 的 CI：三张 job、步骤级逐张取数

- 主干远端逐字同值：`git ls-remote origin refs/heads/main` = `c3a3bf5cec49c2dc9e74fab106aaa8e32f3db09f` = 本地 `HEAD`。
- 该 SHA 只有 **1** 条 workflow run：`36370970368`「CI」，本轮从 `in_progress` 第 5 次轮转 `completed / success`（轮询 `actions/runs/<id>`，具名等待而非事后追认）。
- 步骤级读数取自 `actions/runs/36370970368/jobs`：`python` job 全部步 `completed/success`（`ruff check`、`ruff format --check`、`pyright`、`pytest`、四道 `tools/check*` 与 `tools/verify*`、`uv build --wheel`、`minekin --help`），`bridge-static` 9 步全 `success`，`protocol` 10 步全 `success`；脚本按 `conclusion not in (success, skipped)` 汇总的红步清单 = **空列表**（`NON_SUCCESS_STEPS []`）。原始 JSON 留在 `.tmp/m-r76/{run,jobs}.json`。
- 本地侧同样逐道单跑并先读 rc 才写进 commit message：`ruff check` rc=0、`ruff format --check` rc=0（`376 files already formatted`）、staged `git diff --check` rc=0（日志 `.tmp/m-r76/gates/`）。

### ③ 门载荷复量与一处我自己写错的口径（具名更正）

- 安静窗（`docker ps` 只命中别项目的 `statefix-audit`，无 MC 引擎）、`minekin-runner-data:/data:ro` + `/src:ro`，按登记的配方（`.tmp/m-r12-payload.sh`）重跑：`report_rc=1`、**`gate_payload_sha256` 第 18 次同值 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`**、`overall_blocks` 仍只有 `REQUIRED_CASE_NOT_REGISTERED`、`W30.absent` 2（`OFFLINE-060/080`）/`non_mandatory` 11/`misattributed` 0，`p0-core.absent` 9/`non_mandatory` 24/`misattributed` 0。⇒ §2.71 那三式零新封、零登记，门不位移，这一点是被量出来的。
- **更正 §2.70 的 `size=104680`**：同一份报告，stdout 单流是 **104681** 字节，104680 是把 stderr 并进同一文件后的计数——两件东西，此前混写过一次。此后本节一律报单流数。

### ④ 规范卷「卷面」这一格：三元组无可指配方，本轮不复用旧数

- 本轮想复量 `101/18/186`，但在卷上只量到两件可对号的事实：`/data/kin` 目录条目 **18**，与三元组中项同值；全卷 `find /data -name manifest.json` = **114**（样例路径 `/data/kin/kin-02/run/evidence/35fa702d…/manifest.json`），它既不等于 101 也不等于 186。`/data/evidence` 在卷上不存在，`/data/runs` 为空。
- ⇒ 那个三元组**没有一条我能当场复现的计数配方**（全仓与本轮文档 grep 只找到引用它的句子，找不到产出它的命令）。按「读数必须当场取得」的规矩，本轮不把它当本轮读数引用，也不改写 §2.70 的历史记录；这一格改记为**具名空白**：卷面 bundles/kins/cases 的配方待从 `report_promotion` 的具名字段（`attempts`/`bundles`/`from_another_build` 那一组）取，取到之后再入册，届时会具名申报三元组各来自哪个字段。
- 顺带一条脚手架教训（不改产物）：我第一次用自写的 glob 猜 `bundles/*/*/manifest.json` 形状，在卷上命中 0；改用全卷 `find` 才拿到 114，但那一次扫描超过门内时限转后台。**先读代码里真实的字段名，再断言「缺载体」**——这条在 §2.71 是谓词命中数，在这一格是计数配方，同一个坑的两面。

### ⑤ 队列、约束与下一步

- 主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；本轮不新增 `NEXT`，也不以「§2.71/§2.72 都落了」作为 goal 完成条件。
- 待判/主控保留（本轮都不实施）：**#68** 未请求自行位移可单独满足位移门；⑤ 式那格「`rc=14` 对三种相反事实同码」是否接成判据；HOST/PERSIST 侧；V08/用户远程服。
- 约束逐条：本轮零封存、零 registry/mandatory 变更、零 `src/**`/`tools/**`/`test-orchestrator/**` 字节改动（只动两份文档）；规范卷只 `:ro`；未连接用户远程服，`.tmp/local-test-server.txt` 未打开；lane 树 `../minekin-wt-h1k` 未写入、未代提交（tip `1ce9dc0`、脏 0、`origin/main..HEAD = 0`）。
- 下一格可推进的独立工作按文档 §3 只有两类：只读 Gateway 契约设计（`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`，不接线上真实写接口），或非 HOST case 的「先设计 oracle/载体、后真跑」。**本轮尚未开工**，不是已完成——先写 owner/allowed_paths/验收再动笔。

## §2.73 卷面这一格补上具名配方：`evidence` 段的四个字段当场取到，`101/18/186` 就此作废为口径（第七十八轮，M 主控）

### ① 只补 §2.72 ④ 那一格

上一节把「规范卷卷面」记成具名空白，理由是那个三元组没有当场可复现的计数配方。本轮把配方找齐并取数——配方不在我的 glob 里，在 `report_promotion` 自己的输出里（`tools/report_promotion.py:678-712` 的 `evidence` 段，注释逐字段说明含义）。

### ② 当场读数（`minekin-runner-data:/data:ro` + `/src:ro`，`rc=1`、stdout 单流 104681 B）

- `evidence.count` = **114**、`evidence.bundles` 长度 = **114**
- `evidence.attempts` 长度 = **78**
- `evidence.from_another_build` = **61**、`evidence.repo_checks_not_from_the_controlled_interpreter` = **9**
- `evidence.sealed_without_bundle` / `unverified` / `unsealed` / `unreadable` 全 = **0**
- `reading_interpreter` = `controlled_check_interpreter` = `/opt/minekin/bin/python3`（即这份报告的读者就是受控解释器，该格不再是缺口）
- 卷侧独立对撞（不经过该工具）：全卷 `find /data -name manifest.json` = **114**（§2.72 ④ 已量），`/data/kin` 目录条目 = **18**。两条路同为 114 ⇒ 该计数不是工具自说。

### ③ 与主干既有句子的对账，以及为什么宣布旧三元组作废

- 主干既有记录里同一组字段出现过 `attempts 77 / bundles 113 / from_another_build 61 / repo_checks_not_from_the_controlled_interpreter 9`（M-C0 改前基线那一格）。本轮相对它：`attempts +1`、`bundles +1`，另两项一字不变 ⇒ 与「E7 之后新封了一枚同 run bundle」这一件**已发生且已登记**的事同向，没有额外的卷写入。
- `101/18/186` 那三个数不对应上面任何两个字段（`bundles` 现 114、`attempts` 现 78），我也不去附会。**该三元组自本节起作废为口径**，卷面一律以 `evidence` 段的具名字段报；历史记录（§2.70/§2.71/§2.72 与 handoff 里引用过它的句子）按规矩保留原文不改写，读者以本节为最新口径。
- 本轮**未**重取 `gate_payload_sha256` 子集摘要：命令与挂载未变，同一天已取到第 18 次同值 `cfa0f118…afd6`（§2.72 ③），本节只报本轮真量到的 `rc` 与字节数。

### ④ 约束与四态

- 本轮零封存、零 registry/mandatory/判据变更、零 `src/**`/`tools/**`/`test-orchestrator/**` 字节改动（只动两份文档，加一份 `.tmp` 材料）；规范卷只 `:ro`；未连接用户远程服；lane 树未写入、未代提交（tip `1ce9dc0`、脏 0、`origin/main..HEAD = 0`）。
- 主干 `main = 1c98773`（远端 `ls-remote` 逐字同值）；**该笔自身 CI 不在本节宣称**，按纪律留到下一格补记。真实封证仍 = 1。仅在分支 = 无待合产品工作。
- 待判/主控保留不变：**#68** 未请求自行位移可单独满足位移门、`rc=14` 对三种相反事实同码是否接成判据、HOST/PERSIST、V08/远程服。§3 两类可独立推进的工作（只读 Gateway 契约设计、非 HOST case 的 oracle 先行设计）**仍未开工**——本轮只补了卷面这一格。
- 主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；不新增 `NEXT`，也不以补记落轮次或把 goal 收口。


## §2.74 两笔欠账的 CI 读到步骤级，并把队列 §3 的甲类独立工作落成一张卡：只读 Gateway / Dashboard 契约冻结记录入册（第七十九轮，2026-09-28 11:23 +0800，M 主控；仓库字节 + GitHub Actions REST 只读，零 JVM、零 gradle、零规范卷挂载、未读 `.tmp/local-test-server.txt`、未连用户远程服、lane 材料一字节未改）

### ① 欠账：`1c98773` 与 `5c73f6a` 自身的 CI（步骤级）

- 取法：`GET /repos/<owner>/<repo>/actions/runs?head_sha=<40 位全 SHA>`，再逐 job 读 `steps[].conclusion`。**短 SHA 返回 0 条**（本轮按全 SHA 重取才拿到 run）；token 只从默认凭据助手取且从不回显。脚本 `.tmp/m-r79/ci_read.py`、日志 `.tmp/m-r79/ci-read.log`（未入版本控制，故命令写在上面）。
- `1c98773` = `1c9877335274af211790abbe6c3d78f2433ce61e` → run `36371327681`（name `CI`）`status=completed conclusion=success`；3 jobs 逐进步骤级 `NON_SUCCESS_STEPS []`：`python` 18 步、`protocol` 10 步、`bridge-static` 9 步；`JOB_CONCLUSION_BREAKS []`。
- `5c73f6a` = `5c73f6ac46e281f78e7e26e081decd65cf91e64f` → run `36371529203` 同形状：`python` 18 / `bridge-static` 9 / `protocol` 10 全 `completed/success`，`NON_SUCCESS_STEPS []`、`JOB_CONCLUSION_BREAKS []`。
- 口径：这两笔都是纯文档笔，CI 绿只说明「文档笔没打破仓库门」，不构成晋级、封证或 `tested` 依据。

### ② §3 甲类独立工作落地：`DASHBOARD-GATEWAY-READONLY-CONTRACT-001`

- 交付：新增 `docs/gateway-dashboard-readonly-contract-2026-09-28.md`（179 行 / 25,732 B / 纯 CRLF）；`docs/development-execution-plan.md` §4 末尾把该卡登记为 `DONE`（设计面）并登记两张下游卡 `GATEWAY-READONLY-PROJECTION-001`（G 候补 lane，独占新增 `gateway/**`）与 `DASHBOARD-GATEWAY-WIRING-001`（D lane，独占 `dashboard/**`），两张都是 `QUEUED`、都不是 `NEXT`；`docs/parallel-execution-plan.md` 的「另设候补 G」段追加了带日期的冻结时点。§2 激活表 D 行那个巨型单元格一字节未改写（降风险），「前置已满足」这件事由新小节引用它的原话来说明。
- 冻结面：三条只读 GET 与载荷形状、signal 信封的五值 `status` + 非 `known` 必填 `reason` + provenance 三件套、七种失败分类与 `401/403 → permission_denied`、`404 → contract_mismatch`、版本号 `kin-dashboard-readmodel/1.0.0`、身份面只以存在性或已归约字段出现、`alerts` 必须也走信封（新增具名构造缺陷 `ALERT_SOURCE_AMBIGUITY`：裸空数组会把「无告警源」读成「没有告警」）。
- 字段→载体普查（可复算命令 `grep -rni --include=*.py -w <名字> src tools test-orchestrator`；共 133 个 `.py`）：**0 命中** = `resolved_version`、`current_screen`、`guiOpen`、`last_sequence`、`alert`、`live_view`、`webrtc`、`mjpeg`、`hls`、`permission_denied`、`source_ref`/`sourceRef`、`paused`、`recovering`、`companion`；**有载体** = `world_context_id` 15（首处 `domain/world_activation.py:81`）、`epoch` 55（首处 `domain/hosted_world.py:9`）、`interval_ms` 10、`input_lease` 12、`bundle_digest` 42、`observed_at` 12；`standalone` 仅 1 处且是无关 docstring（`adapters/evidence/trace.py:4`）；`sealed_at` 不在 `src/**`、只在 `tools/seal_repo_case.py:207`。⇒ 按字段分档：今天能诚实 `known` 的是 6 组，必须具名 `not_wired` 的是 6 个外加整条 `alerts`。

### ③ 本轮自伤两处，都落在自己的判据上（已按实测改写）

- 「契约 v1 文本里 `POST|PUT|PATCH|DELETE` 出现次数 0」这句被本记录自己证否：初版中这四个词各出现 1 次，就在写下这句判据的那一行。现改成两条可直接复算的命令并按实测填数——端点表 3 行方法列全为 `GET`（非 GET 0 行）；`gatewayAdapter.ts` 里四个写动词命中 0，且该文件唯一的 `method:` 在 `:400` 且值为 `"GET"`。⇒ 判据判的是**端点方法与请求动词**，不是散文遣词；这条口径本身写进了记录 §5.2。
- 行号漂移三处更正：`dashboard/src/domain/adapter.ts` 的四方法接口是 `:48-53`（不是 `:52-57`）、`unreadableSnapshot` 是 `:59-79`；另外主干既有记录把 asserter 键集合登记在 `tools/assert_case_evidence.py:747-763`，现字节已被 H1i/M-C1 的增行推到 `:813-836`（键集合未变）——文档里具名申报这次漂移，而不是悄悄换号。

### ④ 门读数与四态

- 逐道单跑并先读 rc（日志 `.tmp/m-r79/gates/`）：`ruff check .` **rc=0**（`All checks passed!`）；`ruff format --check .` **rc=0**（`377 files already formatted`）——比上一格的 376 恰 +1，多的就是本卡新增那一份 `.md`（该门的文件数含 `.md`，见 §2.65），不是漂移；staged `git diff --check` **rc=0**（空输出）。
- **本轮未重取** `gate_payload_sha256`：本卡零 `src/**`/`tools/**`/判据/registry/`mandatory` 字节，纯文档按构造不动门载荷；同一天第 18 次同值读数仍是 `cfa0f118…afd6`（§2.72 ③），本轮全程未挂规范卷，所以不把它当本轮新读数引用。真实封证仍 = **1**（`5086ee42…64f6` / run `a224f6c3…`）。
- 主干 `main = 5c73f6a`（本轮起点，远端 `ls-remote` 逐字同值）；**本笔自身 CI 不在本节宣称**，留下一格补记。仅在分支 = 无待合产品工作（H1k tip `1ce9dc0` 等 lane 在途材料一字节未读未改，未代提交）。
- 未验证 / 主控保留不变：**#68** 未请求的自行位移、`rc=14` 同码是否接成判据、`world.worldContext`/`epoch` 的值可否对用户展示、哪些 run document 拒止算「告警」、HOST/PERSIST、V08/远程服。G 的实现卡与 D 的接线卡本轮都不代做。
- 主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；§3 第二类独立工作（乙：非 HOST case 的 oracle/载体先行设计）仍未开工；不新增 `NEXT`，不因轮次富余或暂无待合分支把 goal 收口。

## §2.75 OFFLINE-080 的 oracle/载体先行设计与 `efe8c66` 的自身 CI（第八十轮，2026-09-28 11:45 +0800，M 回写）

### ① 上一轮具名预留的欠账结清：`efe8c66` 自身 CI（步骤级）

主干 `efe8c66e0760004e3747b613a5c4e5324a32dc5c` 的 Actions 读数：**run `36373649061`**，`name=CI`、`status=completed`、`conclusion=success`，共 3 个 job 且全部 `completed/success` —— `python` 18 步、`bridge-static` 9 步、`protocol` 10 步，三者 `NON_SUCCESS_STEPS []`，run 级 `JOB_CONCLUSION_BREAKS []`。取数方式：REST `/repos/.../actions/runs?head_sha=<40位全SHA>`（短 SHA 会返回 0 条），token 只从默认凭据助手读且不回显。脚本与日志：`.tmp/m-r79/ci_read_push.py`、`.tmp/m-r79/ci-read-r79push.log` —— **两者都未入版本控制**，读者需自备同形请求，本仓库不携带可复算路径。

### ② 新卡 `P0-OFFLINE-080-CASE-SPEC-001`（§3 第二类独立工作「乙」的第一张）

交付 [`docs/p0-offline-080-case-spec-2026-09-28.md`](p0-offline-080-case-spec-2026-09-28.md)：doc-only、全程未挂任何卷（连 `:ro` 都不需要）、不写断言函数、不加 fixture、不动 `manifest.sha256` / registry / `mandatory` / 任何门。契约行 `docs/p0-offline-session-compatibility-contract.md:154` 是**三格场景 × 两格判据**，本卡按六格逐格给 oracle / 载体 / 反例 / 阳性对照，不拿一格的绿替另一格。

本轮亲量的关键读数（base 字节；脚本 `.tmp/m-r80/carrier_census.py`，仓库内等价命令写在该卡 §6）：

- **封禁那格既缺词也缺分支**：`classifyDisconnect` = `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:426-449`，六个分支依次为 blank / 白名单 / 重名 / 认证 / 版本 / 资源包，末尾回落 `UNEXPECTED_DISCONNECT`（`:448`）；函数体与整份文件的 `ban` 词族命中 **0**，1.20.1 孪生面 `bridge-1201/…:441-464` 同样为 0。枚举块 `proto/minekin/v1/observation.proto:24-49` 共 17 成员（`UNSPECIFIED=0` + 16 具名，末位 `CONNECTION_REFUSED = 16`），**无 ban 名**。
- **「不循环换身份」只对认证场景存在读法**：`the_refusal_left_the_run_on_one_policy_and_one_process:2725-2755` 的锚点硬编码 `AUTH_MODE_MISMATCH`（`:2739`），交给白名单 run 会返回具名 `NO_AUTH_MODE_REFUSAL_TO_ORDER_AGAINST`（`:2742`）而不是绿；其 docstring `:2728-2731` 明说「进程数单独只证明没重启」。而「拒止后又起过一个不同身份」这一项，字节全在（`PROCESS_STARTED:102`、`AUTH_POLICY_FROZEN:196`、`SESSION_IDENTITY_COMPARED` import `:56`、`identity_candidate_id` `:3184/:3379/:3421/:3472`）却**没有一条断言这样读**。
- **代码侧没有换身份回路，但不因此省判据**：`candidate_by_id` 对未知 id 抛错（`src/minekin_core/adapters/launcher/offline_session.py:104-110`）、候选集封闭两条（`:67-87`）、CLI `choices` 取自同集（`cli/parser.py:238`），两处 `for candidate` 是选择/校验而非重试（`offline_session.py:106`、`cli/session.py:334`）⇒ 判据问的是「这次 run 记下了什么」，结构上不可能 ≠ 材料里没记。
- **底数**：`tests/fixtures/cases/` 共 **53** 份、`offline-*` 11 份，**无 `offline-080.json`**（同族 070/090/100 都在）；`OFFLINE-080` 已在 `cases.py:353`（`RUNTIME_REQUIRED` / `"W30"`，块 `:341-356`）⇒ 缺的是 fixture 与判据，不是 registry 行。

### ③ 本卡申报的两笔代价与一处旧口径更正

- 把 `:2725` 的锚点 reason 参数化会改**已注册函数字节** ⇒ `ADMIT-040` 当前构建 `case_version daeb4ed5150734e7…2be61545`（`docs/p0-admit-five-run-2026-09-26.md:102`）漂移、那份 bundle 掉回「别的构建」，要重封才补得上。替代形状是**新写一条只服务 080 的读法**（零摘要漂移；先例是 `the_auth_mode_mismatch…` docstring `:2705-2708` 里那句「白名单那条不能顶替它」）。两条都摆出来，选哪条属主控。
- 一个 case id 装三格互斥场景 ⇒ promotion 的 any-satisfying-bundle 语义下「跑了一个场景也算过」。仓库已两次承认这一族（`cases.py:336-339` 的 `OFFLINE-030` 父子拆、`docs/p0-validation-evidence-contract.md:189` 第 7 条对 `CORE-060` 的按进程边界拆）。三条登记路线写在本卡 §3.5，**本卡不选**；第 (2) 路线要动 `cases.py`，出本卡面。
- 更正旧口径（dated 原文照引不改）：`docs/p0-evidence-inventory-2026-09-26.md:170` 把分类器写成 `:426-447`，现字节为 `:426-449`；同句「16 个具名分类（另加 `UNSPECIFIED`）」本轮按字节成立。

### ④ 门读数与四态

本轮五道门单跑、先读 rc（日志 `.tmp/m-r80/gates/`）：`ruff check .` **rc=0**（`All checks passed!`）；`ruff format --check .` **rc=0**（`378 files already formatted`，较上一轮 377 **+1 = 本卡新那份 `.md` 自身**，按已知口径不是漂移）；`git diff --check` **rc=0**，stdout 空、stderr 一枚归一化提示 （`in the working copy of 'docs/qoder-execution-handoff.md', LF will be replaced by CRLF the next time Git touches it` —— 该文件工作树字节本就是 LF，与 `core.autocrlf=true` 相遇所致，不是空白错误）；`tools/check_case_assertions.py` **rc=0**（`OK (151 registered)`，与上一轮同值 ⇒ 本轮零登记）；`tools/verify_fixture_digests.py` **rc=0**（`W00 schema and fixture digests: OK` ⇒ 无 fixture 摘要漂移，也就没有已封 bundle 被本轮判失效）。**未跑**：`pyright`、`pytest`、`check_boundaries`、`check_workflow_pins`、`uv build --wheel` + `check_wheel_boundary`、`minekin --help`、protocol 的 buf 三条、bridge 两条 —— 改动虽全在 `docs/**`，这些门本轮就是**未量**，不写成通过。门载荷本轮**未取卷复量**（未挂卷），维持上一轮具名值 `cfa0f118…63afd6` 不变的说法属**预期**而非本轮读数。

四态：已合主干 = 本卡与两处登记（本轮笔次待 push 后回读）；仅在分支 = 无新增；真实封证 = 仍 1 份（`5086ee42…64f6` / run `a224f6c3…`，出处 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:6-7`）；未验证/待判 = `OFFLINE-080` 全部运行时判法、封禁格的服务端文案与摆法、`identity_candidate_id` 在真实拒止 run 里是否总有值、§3.5 三条路线的载荷代价。

不宣称完成：主干唯一 `current_next` 仍是 `PARALLEL-INTEGRATION-GATE-001`；§3 第二类独立工作的其余非 HOST 行（`ADMIT-010/020/030/050/090/120`、`CORE-080`、`OFFLINE-060`、`NAV-EXP-010`）尚未逐张排卡；HOST/PERSIST、V08/远程服、`#68` 与 `rc=14` 判据仍在主控保留格。

## §2.76 ADMIT-030 / ADMIT-050 的 oracle 与载体设计入干（第八十一轮，2026-09-28 12:05 +0800，M 回写）

### 1. 上一轮的欠账结清：`2b8e0e1` 自身 CI 的步骤级读数

远端 `main = 2b8e0e17e2861b911fb1d819a83de118951554b0` 的 CI：run `36374994652`，`status=completed`、`conclusion=success`。逐 job 读步骤（不是只看 job 结论）：

| job | steps | NON_SUCCESS_STEPS |
|---|---|---|
| python | 18 | `[]` |
| bridge-static | 9 | `[]` |
| protocol | 10 | `[]` |

`JOB_CONCLUSION_BREAKS []`。读数脚本与日志：`.tmp/m-r81/read_ci_steps.py`、`.tmp/m-r81/ci-steps-2b8e0e1.log`（`.tmp/**` 未入版本控制；复现需 GitHub 凭据，走默认凭据助手且不回显）。

### 2. 新卡：`P0-ADMIT-030-050-CASE-SPEC-001`（§3 第二类独立工作的第二张）

交付 `docs/p0-admit-030-050-case-spec-2026-09-28.md`。两条形制相同（一个 case id 装三个互斥场景）故共用一张卡，但**逐格分开判**。全程 doc-only：不写断言、不加 fixture、不动 `manifest.sha256`/registry/`mandatory`/任何门、不改 `src/**`、`bridge*/**`、`schemas/**`、`test-orchestrator/**`、**未挂任何卷**、未连远端、未 dial 非 loopback 地址。

本轮量出来的三条新事实（都改变下一步的形状，不只是补全）：

1. **`ADMIT-030` 的「无 DNS」那一格不是缺断言、也不是缺分类词，而是场景不可达**：分类词汇与代码分支全在（`observation.proto:27` 的 `DNS_FAILED=2`、`ConnectFailure.java:33-34`、`ConnectFailureMixin.java:44-56`、Java 单测 `ConnectFailureTest.java:29-31`），但 profile 层根本不允许携带可解析名字——`src/minekin_core/adapters/launcher/server_profile.py:287-289` 的具名拒止逐字写着「server profile host must be an explicit IP literal, not a resolvable name」，v1 schema 更只允许两枚 loopback 字面量（`schemas/server-profile.schema.json:11`）。schema 的 v2 pattern（`:11` `^[0-9a-fA-F:.]+$`）看似能漏进一个「全是十六进制字母的假名字」，但同一函数 `:286` 的 `ipaddress.ip_address()` 先拒 ⇒ 该漏洞不成立（字面读码判定，未跑）。
2. **「无无限重试」有正载体、没有负载体**：Bridge 两面（`bridge/`、`bridge-1201/`）的 `src/main/java` 里 `reconnect|retry|retries` **0 命中**；Core 侧 `reconnect` 5 处全是注释/守卫（唯一可执行的一条是 `domain/connection.py:164-165`「未关闭当前 generation 就不许再 begin」），唯一的 `max_attempts` 回路属工件下载（`adapters/launcher/fetch.py:33/:143-155/:239`），与连接路径无关。可判的一面是具名有界：`cli/session.py:191` 的 30 秒 ⇒ `:1223-1266` 发 `CancelConnection(TIMEOUT)`、关 generation、把 `"TIMEOUT"` 记进 run 文档字段 `connection_cancelled`（`:1618-1622`）；再加 dial 行计数（判官侧 `tools/assert_case_evidence.py:1379` 已按 `generation` 分组）。⇒ 卡里把这一句写成「计数 ≤ 具名 N 且本 run 有终态」两条同时成立，并声明 N 由谁定属主控。
3. **一处我上一轮的口径过头了**：主干 `tools/assert_case_evidence.py` 的 `OFFLINE-070` 段注释写「The server's sentence is not available to a re-judge at all」。本轮读到 `LoginDisconnectMixin.java:38-39`、`:43-46` 与 `CommonDisconnectMixin.java:35` 把服务端原话就地写进客户端日志，而那份日志正是 `CLIENT_STREAM_ARTIFACTS`（`tools/assert_case_evidence.py:755`）封存、`:659-664` 装配为 `material.client_log` 的字节。正确的说法是：**原话不进产品事件，但复审者读得到**。这条更正见 §3。

### 3. 注释级更正（一笔独立提交，不动判定行为）

`tools/assert_case_evidence.py:4003-4010` 的 `DUPLICATE_LOGIN_PHASE` 上方注释改写：保留「分类是唯一能传到这一层的东西」与兄弟判据出处，删去「原话对复审者完全不可得」，补上「Bridge 就地记日志、客户端流里读得到，需要原话的条款读 `material.client_log`」。

不触发重封的证明：bundle 里的 `case_version` 取的是 **case 定义摘要**（`tools/seal_run_evidence.py:518` `case_version=definition.digest`），与 asserter 自身字节无关；本轮也未改任何 fixture、`src/**`、`bridge*/**`、`proto/**`。

副作用（申报，不掩饰）：这一处更正使 `ADMIT-050` 的「保留原因」从「只有 ledger 一个载体」变成「ledger 分类 + 客户端流原话两个载体」，卡里据此把该格写成两条必须分别成立（§3.3⑧）；`OFFLINE-070` 的 `CONFLICT_CATEGORY_HAS_NO_RENAME_ENTRY` 仍然成立——那条拒的是**产品事件里的具名分类**缺一个改名/大小写值，本轮更正没有为它制造新分类。

### 4. 门读数与四态

本轮五道仓库内门逐道单跑、先读 rc 再写进提交信息（`ruff check .`、`ruff format --check .`、`git diff --check`、`tools/check_case_assertions.py`、`tools/verify_fixture_digests.py`）；本轮新增 1 份 `.md` ⇒ `ruff format --check` 的计数按既有口径从 378 → 379。未跑并在卡里具名列出的其余门：pyright、pytest、check_boundaries、check_workflow_pins、`uv build --wheel` + check_wheel_boundary、`minekin --help`、buf 三条、bridge 两条。

四态：**未合并 main / 仅在主干 `2b8e0e1` 之后的 M 提交里 / 无真封存证据新增（本轮 0 次挂卷）/ 断言运行读法尚未量。** 真实封证底数不变：1 份（bundle `5086ee42…64f6` / run `a224f6c3…`，出处 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:6-7`）；门载荷本轮**未取卷复量**（无位移预期，也未测）。030/050 卷上 bundle 仍为 0 份（本轮未复量卷面）。
## §2.77 ADMIT-010 / ADMIT-020 的 oracle 与载体设计入干，并结清 `5d31951` 的 CI 步骤级读数（第八十二轮，2026-09-28 12:20 +0800，M 回写）

### 1. 上一轮欠账的 CI 读数（步骤级，只读 GitHub Actions REST）

- `5d31951a1aedf05cf7d2be85d2481e9c28c4a783`：push run `36376247455` completed / success；python 18 步、bridge-static 9 步、protocol 10 步，各 job `NON_SUCCESS_STEPS []`，`JOB_CONCLUSION_BREAKS []`。
- `595591af15c43d86e0a475404340c02e8a970e56`：`/actions/runs?head_sha=…&event=push` 返回 **0 条 run**。口径写清：这不是失败，是**没有 run**——该 SHA 是 `2b8e0e1..5d31951` 那一次 push 的非 tip 父提交，GitHub 只为 ref 目标起 workflow，它的字节只被 tip run 覆盖。

### 2. 新卡 `P0-ADMIT-010-020-CASE-SPEC-001`（该族第三张 doc-only 设计卡）

交付 `docs/p0-admit-010-020-case-spec-2026-09-28.md`（133 行 LF）：两案逐格的 oracle / 载体 / 反例 / 阳性对照 + 12 行载体底数表 + 四条交主控决定 + 复现命令 A–L + 四态 + 六条未测。本轮新读出的三条结论：

1. `ADMIT-010` 的「LAN 地址」格今天**双重不可达**：v1 在加载期具名拒（`server_profile.py:190-195`，消息含 `no LAN scan or DNS name`），v2 允许把 LAN 字面量存进 profile（`_literal_host:283-297` 只要求 IP 字面量）却把会话目标关回 loopback（`:424-428`，消息自己点名「remote joining needs its own authorization card」），Java 命令门禁另只认两枚 loopback 字面量（`AdmissionCommandGate.java:23`、`:64-66`）。⇒ 该格今天只能判「拒」那一侧，建议具名缺口 `LAN_TARGET_SCENARIO_NOT_REACHABLE_IN_P0`。
2. `ADMIT-020` 的「实际 endpoint」格在**加入路径无载体**：Bridge 的拨号日志行打在 `ConnectScreen.connect` 之前，内容是由命令 `original_host:port` 构造的 `ServerAddress`（`ClientAdmissionController.java:606-622` 对 `:630`），vanilla 解析之后 Bridge 读回的唯一东西是资源包策略（`:610-613`）。⇒ 真实重定向下「被要求的地址」与「实际 socket 端点」在封存材料里字节不可区分；建议具名缺口 `RESOLVED_ENDPOINT_HAS_NO_CARRIER_ON_JOIN_PATH`。
3. 「重定向仍过策略」今天只有**探针域级**那条判得动（`server_probe.py:290-299` 在 transport 之前重决策；`tests/unit/test_server_probe.py:89-104` 已用 `10.0.0.5` 的 `as-saved` 与 `via_srv` 两形都判 `POLICY_REFUSAL` 且 `transport.calls == []`），而 resolver 是测试注入的 `FakeResolver`（`:42-46`）——按 `ADMIT-070` 已落地的同一口径，不得当作一次真实 SRV 重定向被拦住。真 SRV 场景另被 profile 层堵死（域名在加载期即拒，`admission.py:134-137` 的 `NOT_A_LITERAL` 与 `server_profile.py:283-297`）。

另两处附带读数：`_DIALLED` 的两处既有使用者（`assert_case_evidence.py:1353-1358`、`:1401-1402`）**都没有**把拨出的 `host:port` 与封存 profile 比过 ⇒ 「只连已保存 profile」的拨号等式是一格真空缺；断言摘要取的是「该具名函数自己的源码文本」（`check_case_assertions.py:94-124`，含 docstring、LF 归一），故改模块级常量（如 `:1379` 的 `_DIALLED`）会静默改变判法而**不移任何 case_version**——本轮只登记这条门禁审计面事实，不实施检查。

### 3. 门读数与四态

本轮五道门逐道先读 rc，全 rc=0：`ruff check .`（All checks passed）、`ruff format --check .`（**380** files already formatted，比上一轮 +1 = 本卡新增的 `.md`，按 `project-ruff-format-counts-md` 口径归一）、`git diff --check`（stdout 空）、`tools/check_case_assertions.py`（`OK (151 registered)`，未新增注册项）、`tools/verify_fixture_digests.py`（`W00 schema and fixture digests: OK`）。未跑并具名列出：pyright、pytest、`check_boundaries`、`check_workflow_pins`、`uv build --wheel` + wheel 边界、`minekin --help`、buf 三条、bridge 两条。

**四态：设计卡已入干 / 登记与真跑未开工 / 无 sealed bundle 新增（本轮 0 次挂卷）/ 无强制用例集位移。** 真实封证底数不变：1 份（bundle `5086ee42…64f6` / run `a224f6c3…`，出处 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:6-7`）；门载荷本轮**未取卷复量**（无位移预期，也未测）；`ADMIT-010` / `ADMIT-020` 的卷上 bundle 仍为 0 份（本轮未复量卷面）。
## §2.78 ADMIT-090 / ADMIT-120 的 oracle 与载体设计入干（第八十三轮，2026-09-28 12:35 +0800，M 回写）

1. **新卡**：`docs/p0-admit-090-120-case-spec-2026-09-28.md`（101 行纯 LF，卡片 `P0-ADMIT-090-120-CASE-SPEC-001`；base `b3e753de19533c3da9034f8b47139904db2fa623`，**本轮零代码改动**）。这是 §3 第二类独立工作的第四张 doc-only 设计卡。
2. **三条结论**：① `ADMIT-090` 的「人格不重建」从旧清单（`docs/p0-evidence-inventory-2026-09-26.md:165`）的「乙：无载体」**改正为「有载体、无跨 run 判据」**——产品自己写 `SessionIdentityCompared`（`src/minekin_core/adapters/sqlite/session_log.py:75`、闭合集 `:92`，落点 `src/minekin_core/cli/session.py:1556-1566`，观测字段清单 `tools/assert_case_evidence.py:3183-3191`），而上一条 run 的该行随 `previous-run-trace.jsonl` 一起封在 bundle 里（`tools/seal_run_evidence.py:811`；trace 列含 `payload_json`，`assert_case_evidence.py:259-264`）⇒ 跨 run 的人格等式**不需要产品新增事实**就能判。判不出的那半也具名：`local_profile_id`/`identity_revision`/`uuid_algorithm` 只在身份存储里（`src/minekin_core/adapters/sqlite/identity_store.py:19`、`:49`），不进载荷。② 「重连同一服」的**强读法场景不可达**：`test-orchestrator/runner/domain.sh:1038-1042` 每 run 铸一份全新的 `run-<n>` 服务端目录、且工具拒绝非空目录 ⇒ 契约 `docs/p0-validation-evidence-contract.md:208` 那两连跑证的是「同 Kin、新 run、新 world」，不是同一存档世界也不是同一服务端进程；缺口具名 `SAME_WORLD_RECONNECT_NOT_REACHABLE_IN_P0`。③ `ADMIT-120` 的仓库/构建侧**已有四道门**（canary 摘要钉住 `tools/verify_fixture_digests.py:19`；`tests/fixtures/runtime-input` 的 marker 扫描且该目录 6 份非空文件 `tests/contract/test_fixture_boundaries.py:90-97`；`tools/check_wheel_boundary.py:11`/`:22-32`/`:38-58` 的**值级**扫描；case manifest 的 `oracle_inputs` 边界 `:120-141`），运行期那半缺的**第一样是生产者不是判据**（`domain.sh` 全文 `canary` 0 命中）⇒ 具名 `ORACLE_CANARY_HAS_NO_PLACEMENT_MECHANISM`；并且一旦有放置，扫描域必须排除 oracle 自己的载体，否则必然假阳。
3. **附带读数（四条）**：`the_restart_runs_as_a_new_session`（`assert_case_evidence.py:2143-2165`）比的是 `(session_id, generation)` **一对**且拒止文本只打 session ⇒ 「generation 仍从 1 数起、session 换了」是过的，而改这条会移 `CORE-090` 的摘要 `1b248b13…`（`tests/fixtures/cases/core-090.json:14`）；`the_kin_id_continues_from_the_previous_run`（`:3909-3940`）已在册并登记给 `tests/fixtures/cases/offline-100.json`；`ADMIT-090` 在 `src/minekin_core/domain/cases.py:324`（W40 块 `:312-327`）、`ADMIT-120` 在 `:328`（W50），`admit-*` fixture 仍只有 7 份、无 090/120；registry 两份 entry 的 evidence 行合计 18 条且**没有 `W00-CONTRACT-001`** ⇒ 仓库侧那条 oracle 断言连「被封过一次」都不是。
4. **门读数（最终字节，逐道先读 rc）**：`ruff check .` 0 / `ruff format --check .` 0（**381 files**，+1 为本卡 `.md`）/ `git diff --check` 0（stdout 0 字节，stderr 只有 CRLF 归一化警告）/ `check_case_assertions.py` 0（`OK (151 registered)`）/ `verify_fixture_digests.py` 0。未跑并具名列出：pyright、pytest、`check_boundaries`、`check_workflow_pins`、`uv build --wheel` + wheel 边界、`minekin --help`、buf 三条、bridge 两条。**门载荷未取卷复量**（无位移预期，也未测）。四态：设计卡已入干 / 登记与真跑未开工 / 无 sealed bundle 新增（0 次挂卷）/ 无强制用例集位移。
## §2.79 `b3e753d` 自身的 CI 步骤级读数（第八十三轮同轮补记，M 亲跑）

第八十二轮把「新晋 main 的 CI 读数」明写为欠账留下一轮；本轮落盘 `d18a199` 之后按 `ci.yml` 自身清单取回该笔读数，一次 REST 读，不轮询：

- run `36377489950`（head_sha `b3e753de19533c3da9034f8b47139904db2fa623`，push 触发，`runs=1`）⇒ **`completed` / `success`**。
- `bridge-static` 9 步、`python` 18 步、`protocol` 10 步，三个 job 各自 `NON_SUCCESS_STEPS=[]`，`JOB_CONCLUSION_BREAKS=[]` ⇒ 该笔主干字节在 CI 上是全绿，不存在「job 绿而步骤红」的遮蔽。
- 口径：这是**步骤级**结论（免浏览器可得）；日志正文仍不可得，所以本条不写任何「CI 说了什么话」的结论。`d18a199` 自身的 run 此刻尚未取（push 后 4 秒起跑），留下一轮。
- 本轮不变量照旧：真实封证 **1**、`mandatory`/registry/判据零位移、门载荷未复量、规范卷 0 次挂载、未连用户远程服。
## §2.80 `CORE-080` / `OFFLINE-060` 的 oracle 与载体设计入干（第八十四轮，M 主控，doc-only）

1. **新卡**：`docs/p0-core-080-offline-060-case-spec-2026-09-28.md`（112 行纯 LF，卡片 `P0-CORE-080-OFFLINE-060-CASE-SPEC-001`）——§3 第二类独立工作该族第五张（前四张见 §2.76–§2.79 与更早）。base `d5680489208c852272a9405d757de8f2fcb2ef1e`，本轮零代码改动。
2. **三条结论**：① `CORE-080` 由旧清单的「运行期那半无断言亦无材料」重新定性为**门禁与载体都在、缺放置端**——`domain/information_class.py:55-61,81-87` 有三类与五键表（无一条 `TEST_ORACLE`），`cli/session_runtime.py:511-514` 在处理任何载荷前问这道门并按原因计数，`:177-178` 与 `:756-757` 把 `cognition_refusals`/`perceived_information_class` 写进 run document，`tests/contract/test_session_runtime.py:773-774,:857-858` 精确断言过这一对；② 放置有两种互斥形状——走线的新 DTO 会**按构造**让 `tests/unit/test_information_class.py:139`（钉「今天无此类」）变红，具名 `TEST_ORACLE_PLACEMENT_BREAKS_THE_TOTALITY_PIN`；世界侧事实则根本不经过这道门，判定只能落回载体扫描；③ `OFFLINE-060` 的两候选**三重锁启不来**——`cli/parser.py:236-242` 的 argparse `choices` 让未知串在解析期即拒且不产生任何 run，`offline_session.py:56-62` 禁空 `user_type_argv`，`:115`+`:197-199` 只允许 `clientid`/`auth_xuid` 为空。
3. **附带读数四条**：`candidate_by_id:104-110` 的具名拒止**从 CLI 不可达**（被 `choices` 先挡）；验收侧已有 `CANDIDATE_NOT_REVIEWED:{candidate}`（`tools/assert_case_evidence.py:3345-3346`）⇒ 判据在而载体不可能出现，具名 `OFF_N_HAS_JUDGE_BUT_NO_RUN`；`cases.py:340-355` 把本条登记为 `RUNTIME_REQUIRED`，而 `OFF-N` 今天只可能以仓库级断言成立，两侧形状错位；`--identity-candidate` 在整个 `test-orchestrator/` 里 0 命中（本轮亲 grep，无输出）⇒ 战役路径连这个旋钮本身都不转发。另登记一处误读风险：`tests/unit/test_case_registry.py:1012` 的 `absent == (...)` 判的是该测试自造的合成 registry（见 `:1004-1008`），不是真 registry 行数。
4. **门读数（最终字节，逐道先读 rc）** 与四态：见本轮 handoff 第八十四轮第 5 条与卡 §5–§6。本轮 0 次挂卷、未连用户远程服、`mandatory`/registry/判据零位移、主干仍只有一个 integration `NEXT`。真实封证仍为 **1**。
## §2.81 `NAV-EXP-010` 的 oracle 与载体设计入干，并结清三笔 CI 欠账（第八十五轮，M 主控，doc-only）

1. **新卡**：`docs/p0-nav-exp-010-case-spec-2026-09-28.md`（92 行纯 LF，卡片 `P0-NAV-EXP-010-CASE-SPEC-001`）——§3 第二类独立工作该族**第六张、收尾一张**：§3 列出的非 HOST 行（`ADMIT-010/020/030/050/090/120`、`CORE-080`、`OFFLINE-060`、`NAV-EXP-010`，见本文 `:1840`）至此每张都有一张设计卡。base `535e033132576f4d5edf2087c06608d205f50e8c`，本轮零代码改动。
2. **三条结论**：① 本条的三档分级 `candidate/tested/quarantine` 里**只有 `tested` 一档有载体**——`cases.py:89-107` 的 `PromotionBlock` 文档句即「为什么还不能被称作 tested」，而仓库里的 `quarantine` 字节全在另一条轴上（`adapters/launcher/artifacts.py:133-134,:169-170` 的产物隔离目录、`domain/version_resolution.py:44,:765-778` 的 `BundleStatus.QUARANTINED`）⇒ 本卡把这格命名为 `NAV_TRI_GRADE_HAS_ONLY_TESTED`，指出它是**分级轴缺失**而不是判据缺失；② 契约 `:195` 的「只在 core tested 后运行」今天**没有任何承载者**——代码刻意让 `p0-nav-exp` 独立分级（`cases.py:39-46,:197-199`，`W80` 因此被排除在 `REQUIRED_GATES:200-212` 之外），后果可判：先于 core tested 封出的 NAV bundle 对 `p0-nav-exp` 单独复算照样可能 `promotable=true`；本卡列出三种可选承载点而不选；③ 四个检查项的载体厚度不均——`Baritone mixin` 在 `src/`、`tools/`、`tests/`、`test-orchestrator/` 内 **0 命中**（只有 4 份文档提到），`隐藏真值越界` 却已经有最厚的结构化观测面（`domain/perception.py:40,50,60,114,120,144` 的 `EntityReason`/`SnapshotReason`/`IntegrityViolation`/`EntityRejection`/`VisibleWorld`/`SnapshotAdmission`），`取消尾部` 无具名事件（`events.py` 与 `input_control.py` 按三串 grep 均 0 命中）。
3. **CI 三笔（本轮亲跑 REST，逐笔先读状态再作结论）**：`d568048…` → run `36378797135` `completed`/`success`，`protocol` 10 / `bridge-static` 9 / `python` 18 步，`NON_SUCCESS_STEPS` 与 `JOB_CONCLUSION_BREAKS` 全空；`d18a199…` → run `36378464126` `completed`/`success`，步骤 9/18/10，两清单全空 ⇒ §2.79 之后仍欠的那笔至此闭合；`535e033…`（第八十四轮落盘笔）→ run `36379470293` 本轮取到的是 **`in_progress`**（`conclusion=None`）⇒ 不作绿声明，留下一轮复取。日志在 `.tmp/m-r84/ci-d568048.log`、`.tmp/m-r84/ci-d18a199.log`、`.tmp/m-r84/ci-535e033.log`。步骤级口径照旧：日志正文不可得，本节不写任何「CI 说了什么话」。
4. **门读数与四态**：见本轮 handoff 第八十五轮第 5 条。不变量照旧——真实封证 **1**、`mandatory`/registry/判据零位移、门载荷未复量、规范卷 0 次挂载、未连用户远程服、lane 字节一字节未读未改、主干仍只有一个 integration `NEXT`。
## §2.82 整条 CI 欠账闭合与 objective 前半的现场复量（第八十六轮，M 主控，doc-only，本轮无新卡）

1. **两笔 CI 亲取，欠账清零**：`535e033…`（第八十四轮落盘笔）的 push run `36379470293` 复取为 **`completed`/`success`**，`protocol` 10 / `bridge-static` 9 / `python` 18 步，三 job `NON_SUCCESS_STEPS=[]`、`JOB_CONCLUSION_BREAKS=[]`（日志 `.tmp/m-r86/ci-535e033.log`）⇒ §2.81 第 3 条那句「本轮取到的是 `in_progress`，留下一轮复取」在下一轮就兑现了；`0d080c0…`（第八十五轮落盘笔）自身的 run `36379827665` = `completed`/`success`，步骤 9/18/10，两清单同样全空（日志 `.tmp/m-r86/ci-0d080c0.log`）。**链条口径**：自 `b3e753d` 起的五笔 doc-only 提交（`b3e753d`、`d18a199`、`d568048`、`535e033`、`0d080c0`）现在各自都有一笔步骤级绿读数，其中前三笔分别记在 §2.79、§2.81 第 3 条（两笔）；日志正文依旧不可得，故本节仍不写任何「CI 说了什么话」。
2. **objective 前半复量（全部只读）**：`git ls-remote origin refs/heads/main` = `0d080c0b37b3242ef8967d2bf317532418335243` = 本地 HEAD；`../minekin-wt-h1k` 的 `git status --porcelain` 为 **0 行**、其分支 `codex/minekin-h1l-forward-join-name` 停在 `1ce9dc0` 且 `git rev-list --count origin/main..该分支` = **0** ⇒ H1k 已按当前字节提交并推送、并经 M 的 merge-base 复审合入主干，「lane 在途工作」这一格今天没有待收的未提交文件。另核三条历史 lane 分支（`codex/core-state-transition` @ `6a02ac6`、`codex/minekin-local-control-next` @ `0552e10`、`codex/minekin-lan-joiner-bounded-control` @ `99a18ef`）相对 `origin/main` 均 **ahead=0** ⇒ 无未合分支可复审。
3. **§2.22 四项在当前 main 字节上逐条对回载体**（本轮亲 grep，行号按 `0d080c0` 树重测）：① 第七条具名拒止在 guard 区间内——`test-orchestrator/runner/domain.sh:511` 的 `if [ "${join_on_controlled_server_asked}" -eq 1 ]` 包住整段、`:537` 逐字写出「name two destinations for one wait; the chain answers the snapshot refusal before any joining client is sent」，置位读法 `:176`/`:179`；契约侧承担者在 `tests/contract/test_runner_scripts.py:4022`、`:4049`（同两名 ⇒ `rc=2` 且不落 `/tmp/domain-join-profile.json` 的字面断言另见 `:3049`、`:4100`）。② §2/§3/§4 读数集在新字节上整体重跑：`docs/validation/v1201-joiner-on-controlled-server-2026-09-27.md:447`（§10.2）与 `:564`（§11.1，M 侧会话独立复跑同一镜像）。③ 活体在 lane 自己的私有卷 `minekin-h1k-live` 上补的两轮：`:469`（§10.3，`:488` 记 `[12:56:50] Kin2 joined the game`）与 `:597`（§11.2，live-e/live-f 两轮）。④ 门载荷前后一对：`:522`（§10.4）与 `:639`（§11.3），PRE/POST 均 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、`rc(report_promotion)=1`。**口径不变**：③ 是 lane 私有卷上的活体读数，不是封证；`## 附：live-c 补记位`（`:370`）与 §9（`:377`）的原文按日期留在盘上，本轮不改写。
4. **工作树全量普查（52 棵，只数不读）**：`git worktree list` 逐棵数 `git status --porcelain` 行数，结果——M 的树 `minekin-wt-integration`、E 的树 `minekin`、以及全部 `minekin-wt-*` lane 树皆 **0 行**；非零的只有 7 棵：`.claude/worktrees/` 下 6 棵（`case-core-001` 4、`core-030-host-binding` 9、`core-060-fault-injection` 18、`launcher-liveness-fix` 5、`promotion-fail-closed` 8、`replay-evidence` 5）与 M 自己第四十五轮的复审树 `minekin-wt-m-r45` **2 行**（`domain.sh` 已 staged、`tests/contract/test_runner_scripts.py` 未 staged；该树 `domain.sh` 盘上 sha256 前缀 `e1d8dbb9…` 是 §2.22 时期的 lane 候选字节，当前 main 同文件为 `cbec5b85…`，两者不同 ⇒ 这棵树是复审材料，不是待合物；分支 `m-r45-h1k-review` @ `ceb079f` 相对 main ahead=0）。**这 7 棵一字节未读、未改、未 revert**（memory 口径：脏文件禁 `checkout --`/`restore`/`reset --hard`/`stash`）。
5. **本轮不开新卡**：§3 第二类独立工作该族六张已排完（`ADMIT-010/020/030/050`、`ADMIT-090/120`、`CORE-080/OFFLINE-060`、`NAV-EXP-010` 各一），主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`，`current_next` 一字未动；剩下的格（`#7`、`#68`、HOST 整族、V08 与用户远程服、契约 §8 的决策格、各卡的 §4 交主控格子）都在主控保留侧 ⇒ 按纪律**只申报为缺口，不发明成范围**，也不伪造新的 `NEXT`。
6. **不变量与四态**：真实封证仍为 **1**（bundle `5086ee42…64f6` / run `a224f6c3…`）；`mandatory`、registry、判据集合本轮**零位移**，门载荷未取卷复量（无位移预期，也未测）；规范卷 `minekin-runner-data` 本轮 **0 次挂载**；未连接用户远程服；GitHub token 只经默认凭据助手取用且未回显。四态：CI 欠账闭合 / 设计卡零新增 / 无 sealed bundle 新增 / 无强制用例集位移。

## §2.83 `#68` 在唯一真实封证 bundle 上的只读量化取证：授权窗内的位移按构造不可归因（第八十七轮，M 主控，doc-only + 派生切片材料，判据零位移）

1. **材料身份与挂载**：取证对象是卷内**迄今唯一一枚**真实封证 bundle —— `/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf`（bundle `5086ee42…64f6` / run `a224f6c3…`，case `V1201-LAN-JOINER-CONTROL-CASE-001`，`verdict PASS` 四条）。`minekin-runner-data` 全程以 `:ro` 挂载进 `minekin-runner:local`，工作树同样 `:ro`，可写面只有容器 `--tmpfs /work`；驱动 `.tmp/m-r87/run-inspect.sh`，四份读数日志 `.tmp/m-r87/{inspect,series,payloads,slices}.log`。**这些都是只读取证与派生材料，不是新的 sealed bundle。**
2. **账本时间线（bundle 内 `bridge-trace.jsonl`，23 事件，每行带 `payload_json` ⇒ 归属在只读 bundle 内即可量出）**：`seq=16 InputLeaseGranted 23:58:17.982650Z capability=control.move.v1`，`seq=17 InputLeaseGranted 23:58:18.005321Z capability=control.look.v1`，两条同一 `lease_id fb3688d5…`、同一 `action_id 2bd1024a…`、同一 `deadline_monotonic_ns 43790861504556` ⇒ **授权控制窗 = 1.9966 s**（不是 2 s 的名义值，按单调时钟差算出）。`seq=18 InputReleased 23:58:19.983252Z {generation:1, had_lease:true, reason:TIMEOUT}`；`seq=19 InputReleased 00:00:53.046672Z {generation:1, had_lease:false, reason:EXPLICIT}` —— 后一条**不是 lease 的结束**（`had_lease=false`），而是收尾时的具名释放，客户端日志同一秒逐字写着 `bridge released 0 input(s) after CORE_REQUEST (EXPLICIT)`。`seq=17` 之后再无 `InputLeaseGranted` ⇒ **23:58:19.98 之后本 run 没有任何授权控制窗**。
3. **判据侧的代码事实（在主干当前字节上现读，不是推断）**：`tools/assert_case_evidence.py:235 MINIMUM_STEP_BLOCKS = 2.0`；用它的三处位移判定 —— `the_server_saw_the_kin_move:1647`、`the_server_saw_the_kin_stop_after_the_move:1736`、`the_server_saw_the_kin_arrive_and_never_move:2510` —— 一律只把 `probe_readings(material.server_log, 3)`（`:266`）的首末两条代入 `_horizontal`（`:1636`，刻意忽略 Y），**没有一处解析读数时刻、也没有一处读 lease**。⇒「把位移限制在授权窗内」这句话在今天的判据里不存在；`#68` 关心的正是这条缺口。
4. **用判据自己的函数在派生时间切片上跑**（`.tmp/m-r87/rejudge_slices.py`；切片按服务端自己的 `[HH:MM:SS]` 逐行筛，写进容器 tmpfs，bundle 未被写过）。四式读数：
   - **as-sealed**（40 条读数）`first=(4.5, -60.0, -6.5)` → `last=(23.0619, -60.0, 8.0170)`，`horizontal=23.565` ⇒ 返回 `None` = **PASS**（与 bundle 内 `orchestrator-trace.json` 的 verdict 同向，这是正对照）。
   - **窗内及之前**（≤ 23:58:19，2 条读数）⇒ `MOVED_LESS_THAN_A_STEP:1.20` = **FAIL**。
   - **严格窗内**（[23:58:17, 23:58:19]，**恰 1 条读数**）⇒ `NO_SERVER_READINGS` = **FAIL**。
   - **窗后**（≥ 23:58:22，38 条读数）`horizontal=25.894` ⇒ **PASS**。
   ⇒ 同一枚函数、同一份 bundle 的两端配对非恒真：**只留授权窗内的材料连「两条读数」都不成立；剔掉窗内及之前的两条读数，剩下的未授权时段独自越门。** 根因是采样密度：探测节拍 4 s，授权窗 1.9966 s ⇒ 窗内至多一条读数，**授权窗内的位移在这份封存材料里按构造不可测**，而 PASS 所依据的 23.565 全部落在 release 之后。
5. **对本案 verdict 的影响（如实，不夸大也不缩小）**：bundle 的 `verdict` 四条仍是 PASS，`run-document.json` 记 `actions_applied=2 / actions_refused=0`（正好 move+look），`asserter-inputs.json` 记 `probed_players=["Kin2"]` 单名 ⇒ `the_probed_player_is_this_run_s_kin` 与 `move_input_was_leased`、`the_bridge_carried_the_input_out` 三条不受本轮读数影响。被削弱的是**第四条的归因力**：`#68` 由此从「私有卷活体上的推断」升为「唯一真实封证上的具名量化缺口」。
6. **世界内未请求位移的来源（旁证，按构造不做因果声称）**：`client/latest.log` 记 `[00:00:29] Kin was slain by Slime` ⇒ 受控专服的世界里存在能把玩家推开/回生的原生实体。本轮那次死亡发生在**所有位移之后**（23:59:50 起读数已冻结到 run 结束），所以它**不是**这 23.565 的成因，也不得写成成因；它只证明「读数期间玩家可被世界移动」不是假想而是同一 run 里的实况。
7. **载体侧的新结论（推翻本轮之前的一个假设）**：修法**不需要扩封存 schema**。lease 的起止时刻已在 `bridge-trace.jsonl` 里（带 `observed_at_utc` 与 `monotonic_ns`），读数的秒级时刻已在 `server/server.log` 的行首 —— 两格载体都已在位，缺的是判据把它们对上。**未证的一条**（要留给窄卡的第一个验收）：trace 是 UTC 微秒、日志是服务端本地秒，本轮只观察到 `JoinObserved 23:58:14.915` 与首条读数 `[23:58:14]` 同秒这一枚旁证，**两侧时钟同源未经量清**，秒级对齐误差直接决定「窗内该有几条读数」这种判法能不能立。
8. **窄卡入册（`QUEUED`，非 `NEXT`，不动主干唯一 integration `NEXT`）**：`V1201-MOVE-WINDOW-ATTRIBUTION-001`，owner=M，allowed_paths = `tools/assert_case_evidence.py`、`tests/fixtures/cases/v1201-lan-joiner-control-case-001.json`、`tests/**`、`docs/validation/**`。验收顺序：① 在只读 bundle 上量 trace 时刻与日志行首时刻的同源性（给出偏移与不确定度，不许假定 0）；② 判据要求「lease 授予→释放」窗内服务端至少给出**两条例数**并只以窗内首末位移作判定，配三枚具名反证（把窗内读数全删 ⇒ 必 `NO_SERVER_READINGS`；只在窗后造 ≥2.0 位移 ⇒ 必 `MOVED_LESS_THAN_A_STEP`；把窗内两条读数保留、窗后全删 ⇒ 若窗内确有位移则仍 PASS）；③ 申报 `case_version` 与四枚 `assertion_digests` 的位移面 —— 本案 `mandatory:false` ⇒ 预期不动 `gate_payload_sha256`，但必须实测 PRE/POST 配对，且**旧 bundle 的复判结果会变**这条要写清（封存字节不可动，判据变则历史 verdict 不可复现，属重封而非改卷）。④ 采样密度缺口（4 s 节拍 vs 2 s 窗）属 runner 侧，若要一并修需另开一张 `domain.sh` 独占面的卡，不与本卡混面。
9. **不变量与四态**：真实封证仍 **1**（同一枚 bundle，本轮只读）；`mandatory`、registry、判据集合、`case_version` 本轮**零位移**，门载荷未取卷复量（无位移预期，也未测）；未连接用户远程服；GitHub token 只经默认凭据助手取用且未回显。四态：`#68` 取证闭合 / 窄卡入册 QUEUED / 无新封证 / 无强制用例集位移。

## §2.84 `V1201-MOVE-WINDOW-ATTRIBUTION-001` 验收① 的只读量移：trace 与日志同源到秒、授权窗内恒一枚读数、承载 PASS 的末读数来自尸体（第八十八轮，2026-09-28 13:40 +0800，M 主控，doc-only + 派生测量脚本，判据零位移）

1. **材料与挂载（仍是同一枚唯一真实封证，未新增封证）**：`/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf`（bundle `5086ee42…64f6`、run `a224f6c3…`、case `V1201-LAN-JOINER-CONTROL-CASE-001`、`mandatory:false`）。读数方式与 §2.83 同：只读容器 `minekin-runner:local`，工作树与 `minekin-runner-data` 卷双双 `-v …:ro`，`--tmpfs /work`，`LD_LIBRARY_PATH=/opt/sqlite/lib`、`PYTHONPATH=/src/src`；脚本 `.tmp/m-r87/clock_alignment.py` → 日志 `.tmp/m-r87/clock.log`（52 行，rc=0）。复现命令（逐字）：`cd C:/Users/darling/Documents/agent_work/minekin-wt-integration && export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" && SCRIPT=.tmp/m-r87/clock_alignment.py bash .tmp/m-r87/run-inspect.sh > .tmp/m-r87/clock.log 2>&1`。bundle 全程未被写过；派生脚本与日志只落 M 自己的工作树，`.tmp/` 由 `.gitignore:10` 排除在 git 之外（`git check-ignore -v` 可复现），且 `uv run ruff check .` / `ruff format --check .` 在当前字节上分别为 `All checks passed!` / `383 files already formatted`（同一份脚本显式点名给 ruff 时会报 21 处，反证门的路径枚举确实没有走进 `.tmp/`）⇒ 门载荷按构造不动。
2. **探针行的发言者已经具名（收窄 §2.68 的一条担忧）**：`server/server.log` 里 40 枚位置行**全部**由 `Kin2` 发言（前缀清一色 `[Server thread/INFO]: `），本 bundle 不存在宿主自己的 `has the following entity data:` 行 ⇒ 判据虽然名字盲（`_PROBE` 不解析发言者，`tools/assert_case_evidence.py:245`），**在这一枚封证里没有发生「把宿主位移记成加入者」的污染**；§2.68 被引用过的 `23.564584` 整段都是加入者自身的轨迹。这不改变「名字盲是判据缺陷」的一般结论，只说明本案读数未被它污染。
3. **节拍是常量，不是运气**：40 枚位置读数的相邻间隔直方图 = `{4: 39}`（无一枚例外），首 `23:58:14`、末 `00:00:50`（服务端行首秒）⇒ 采样时刻钉在 `14 + 4k` 秒，与 lease 窗的相对位置在整个 run 内不漂移。
4. **窗内计数 = 1，且对平移稳健**：授权窗 `[23:58:17.982650, 23:58:19.983252]`（`deadline_monotonic_ns 43790861504556`，1.9966 s）内恰 **1** 枚读数（`23:58:18`）；把窗整体平移 `−1 s / 0 / +1 s` 后窗内读数枚数仍是 `1 / 1 / 1`（发言者分布 `[('Kin2', 1)]`）⇒ **窗内枚数不依赖窗边界的取整方向**，「窗内至少两枚读数」在 4 s 节拍 × 1.9966 s 窗之下按构造不可达。
5. **唯一那枚窗内读数连位移都构不成**：单枚读数无 first→last；窗首之前的一条（`23:58:14`）早于授予 **3.982650 s** ⇒ §2.83 量到的 `idx0→idx1 = 1.202` 混入了授予之前的运动，不能当作「窗内位移」。
6. **验收①（时钟同源性）的读数与诚实限制**：两条独立锚点——`JoinObserved 2026-09-27T23:58:14.915608Z` vs `Kin2 joined the game [23:58:14]`；`SessionInterrupted 2026-09-28T00:00:53.792924Z` 与 `InputReleased{reason:EXPLICIT} 00:00:53.046672Z` vs `Kin2 lost connection [00:00:53]`。两侧同时跨 `09-27→09-28` 的午夜且 time-of-day 逐秒相等 ⇒ **排除任何整点时区偏移**（若日志走 +08:00 就应读到 `07:58`）；残差与日志行首的 1 s 分辨率同阶（界内 `<1 s`，两锚点相隔 158.9 s 且无反漂）。**未证到的部分具名**：trace 的 payload 只有 `{"phase":"JOIN_SEEN"}`、`{"phase":"PLAYABLE"}`、`{"outcome":"BRIDGE_LOST"}`，**不具名** ⇒ 配对是按时刻相邻建立的，不是身份锚定；另有一条看似矛盾实则不是的读数——`SessionProcessStarted 23:57:45.980891Z` 比日志首行 `[23:57:27] Environment: authHost=…` 晚 18.019 s，因为前者记的是受控**客户端**会话进程、后者是服务端 JVM，两个进程。**结论**：窗内判定不必扩封存 schema，trace 的 UTC 微秒可以直接与日志行首秒比较，但判据口径必须把 `±1 s` 写成固有不确定度，不许假定 0。
7. **承载 PASS 的末读数来自尸体**：日志 `[23:59:47] Kin2 was slain by Slime`。死亡后再无位移——死亡后 16 枚读数（占材料 `16/40 = 40%`）位置恒为 `(23.0619, -60.0, 8.017)`，其首末水平位移 `0.0000`；死亡前最后一枚（`23:59:46`）是 `(21.187, -60.0, 7.3589)`，与冻结位的水平差 `1.987`（对两枚已印出读数的算术，脚本不作因果解释；击杀击退只是候选说明）。从死亡到 run 末读数 `63 s`。⇒ 现有 `the_server_saw_the_kin_move` 的 `last` 正是这枚死亡位置：**判据把「死亡后冻结 63 s」当作轨迹末端**，本案它没有改变 PASS 与否（窗后 38 枚读数已独自越门），但它是 §2.83「未请求位移」之外第二条独立的非归因来源。
8. **验收② 的口径按本轮读数修订（本条取代 §2.83 第 8 条的 ②，①③④ 原文照旧）**：不得把判据写成「窗内至少两枚读数」——第 4 条已证明该前置在现有封证材料上按构造不可达，写进去等于把门做成永远红。可判形状改为**边界配对**：取「授予前最后一枚」与「释放后第一枚」为窗内首末，并在读数里**显式申报该跨度的时长与其中授予前的秒数**（本案 `23:58:14 → 23:58:22`，跨 8 s，其中授予前 3.982650 s）。三枚反证随之改为：删掉边界两枚 ⇒ 必 `NO_SERVER_READINGS`；只在释放后第二枚之后造 `≥2.0` 位移 ⇒ 必 `MOVED_LESS_THAN_A_STEP`；保留边界两枚、删掉其后全部 ⇒ 若确有授权方向位移则仍 PASS。**并写明该修订的代价**：边界配对把未请求位移与授权位移混在同一 8 s 跨度里（第 5 条的 `1.202` 就是实例），所以修订后的判据**只有与同 run 的 `control-off` 双名零位移形状同时成立时才非恒真**；要真正去掉这个混合，必须先有第 9 条的采样密度卡。
9. **另开一张 runner 侧窄卡，不与本卡混面（`QUEUED`，非 `NEXT`）**：`V1201-PROBE-SAMPLE-CADENCE-001`，owner=H lane（`domain.sh` 独占面，沿 H 系列既有卡的 allowed_paths，落笔前先核不越面），allowed_paths = `tools/controlled-run/orchestrator/domain.sh` + 其 `tests/**`；验收：① 在活体 run 里让 lease 窗内的服务端位置读数达到 **≥2 枚**（窗内即时探测，或把节拍压到 `≤1 s`），② 正对照=封出一份窗内读数 ≥2 且**仅窗内首末位移 ≥2.0** 的新 bundle，③ 反证=同 run 的 `control-off` 段窗内首末位移 `<2.0`。该卡不落地前，第 8 条的修订口径是唯一可判形状。
10. **不变量与四态**：真实封证仍为 **1**（`5086ee42…`/run `a224f6c3…`）；判据、`mandatory`、registry、`case_version` 零位移；门载荷仍 `cfa0f118…63afd6`——本轮在最终字节上容器内实量（`.tmp/m-r88/payload-after-doc.log`：`report_rc=1`、`gate_payload_sha256 cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`、`overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']`、`W30/p0-core` 仍 `promotable False`），不是引用旧记录；`ruff format --check` 仍 383 files；`check_case_assertions` 仍 151 registered；主干唯一 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`，`V1201-MOVE-WINDOW-ATTRIBUTION-001` 与 `V1201-PROBE-SAMPLE-CADENCE-001` 均为 `QUEUED`。`b37f20c`（第八十七轮）自身 CI 步骤级已转绿：run `36381795859` `status=completed conclusion=success`，`protocol` 10 步 / `python` 18 步 / `bridge-static` 9 步，三道 `NON_SUCCESS_STEPS=[]`、`JOB_CONCLUSION_BREAKS=[]`（日志 `.tmp/m-r87/ci-b37f20c.log`）。四态：本轮结 #76 的**验收①（已测）**与**② 的口径修订（已定）**，③ 的门载荷配对与判据实施**未做**；晋级门、V08/真实用户服、HOST 侧封存与实施仍停主控保留。本轮不宣称 goal 完成。

## §2.85 判据改动对「唯一真实封证」的作用点已量到行：`rejudge_evidence.py:130` 会直接拒判旧 bundle，而不是复判出一个新结果（第八十八轮同轮补记，2026-09-28 13:50 +0800，M 亲跑，只读，判据零位移）

1. **为什么要量这一格**：§2.83 第 8 条的 ③ 与 §2.84 第 10 条都写着「旧 bundle 的复判结果会变」。这句话的力度不够 ⇒ 本轮把它换成行级读数，因为判据改动是不是可落地，取决于旧封证是「变绿/变红」还是「根本不再可复判」。
2. **`case_version` 覆盖判据函数自身的源码文本**（现读 `tools/check_case_assertions.py:22`：「what makes `case_version` cover the criteria rather than only their names」；同一口径在 `tools/assert_case_evidence.py:3528` 的注释里重复过一次：「editing it to share two lines would move its `case_version`」）⇒ 改 `the_server_saw_the_kin_move` 的字节必然移动本案 `case_version`。
3. **封证字节确实钉死了这个摘要**：唯一真实封证的 `manifest.json` 顶层键含 `case_id = V1201-LAN-JOINER-CONTROL-CASE-001`、`case_version = 1e31f0003b4e30e06506e086616335db73ec975b406874d219033f151b3f812a`、`result = PASS`、`schema = minekin.p0.evidence.v1`、`assertions.expected == observed == 四枚判据名`（`failures []`）、`attempt.sequence = 1`、`identity.server_observed_name_uuid = Kin2/20d2112d-ecc9-3e0b-a7f4-5b830b9e6451`、`artifacts = 14` 条；`asserter-inputs.json`（191 B）/`orchestrator-trace.json`（1036 B）/`run-document.json`（1861 B）三份里都**不含** `case_version` 字样 ⇒ 钉子只在 manifest 一处。复现：`.tmp/m-r88/case_version_pins.py` → `.tmp/m-r88/pins.log`、`.tmp/m-r88/pins_manifest.py` → `.tmp/m-r88/pins2.log`（同一支只读容器驱动 `.tmp/m-r87/run-inspect.sh`，两个卷与 `domain.sh` 全程 `:ro`）。
4. **作用点（本轮的核心读数）**：`tools/rejudge_evidence.py:130` 是 `if definition.digest != manifest.case_version:`，其 :132 的文案是「this bundle was sealed against case version {manifest.case_version} and …」⇒ 判据一改，对旧 bundle 的复判**在第一步就拒判**，根本走不到四枚判据。⇒ 正确口径是：**「旧封证不再可复判」而不是「旧封证的复判会变」**；`report_promotion.py:436` 也只会照原样转录 manifest 里那枚旧 `case_version`（`seal_run_evidence.py:518`/`seal_repo_case.py:145` 写、`:837`/`:262` 读），所以卷面读数会一直显示旧摘要，与新字节无法对表。
5. **对 ③ 的可执行含义（卡面口径据此收窄，不扩范围）**：判据实施**不可能**用现有封件自证；能自证的只有仓库侧材料——单元/契约测试 + §2.84/§2.83 已经量到的两份派生切片读数（同一份 `server.log` 的整行时间切片，写面只在 `--tmpfs /work`）。要在**封证面**确认新判据，必须先落地判据、再重跑一次 E7 式规范卷封证，产出一枚钉在新 `case_version` 上的 bundle；那会令真实封证从 1 变 2，并把 `5086ee42…` 变成「历史时点、按新字节不可复判」的一枚。这一步要引擎窗与独占规范卷 run，且**不与 ④ 的采样密度卡合并**（否则新 bundle 仍只有窗内 1 枚读数，白跑一轮）。⇒ 顺序判读：**④（采样密度）应先于「重封自证」**，否则重封出来的仍是不可归因的形状。
6. **本轮不动判据、不动 fixture、不动 registry**：真实封证仍 **1**，`case_version` 仍 `1e31f000…812a`，门载荷仍 §2.84 第 10 条实量的 `cfa0f118…63afd6`；「先落地判据再重封」这一步在做出之前是一个待决的产品/证据面决定，本轮把它量清并具名，不替用户消费引擎窗。

## §2.86 ③ 不必移动证据基线：`case_version` 的摘要按**单个判据函数的源码段**计算，新判据可以先落地再接管（第八十八轮第三次补记，2026-09-28 14:01 +0800，M 亲读仓库字节，判据/fixture/registry 零位移）
1. **为什么要量这一格**：§2.85 第 4 条把作用点钉在 `tools/rejudge_evidence.py:130` 之后，③ 看起来只剩「改判据 ⇒ 唯一真实封证不可复判」一条路。本轮按实现层复核这个推论的**边界**，因为「落地一段新判据」与「让已登记的那枚判据改口」不是同一件事，而 ③ 的卡面只要求前者能自证。
2. **摘要的粒度是符号级，不是文件级**（现读 `tools/check_case_assertions.py`）：`:46` `DIGESTS_FIELD = "assertion_digests"`（每枚判据把自己的实现摘要记在 manifest 里），`:94 _function_source` 取的是**一个顶层函数的源码段**——从它的第一枚装饰器行到 `node.end_lineno`（注释在 `:106-107` 写明参数化算被覆盖的一部分），`:113 implementation_digest` 对这枚函数体 `:124` 做 `sha256(source.replace("\r\n", "\n"))`。⇒ 往 `tools/assert_case_evidence.py` 里**新增**符号、且不触碰本案那四枚被覆盖符号的字节，按构造不动 `case_version`，旧封证继续可复判。这一格在实施前后都要用读数收口（见第 4 条的 POST 口径），本轮只量到「机制是符号级」这一半。
3. **边界配对要的载体今天已经在 asserter 的输入面里**（现读 `tools/assert_case_evidence.py:355` 的 `RunMaterial`）：`:376 ledger_events` 就是本 run 的账本事件序列——`:1034` 处它由 `_sealed_events(directory, LEDGER_TIMELINE_ARTIFACT)` 填出来（常量从 `minekin_core.adapters.evidence.trace` 导入，`:46`），每枚事件带 `observed_at_utc` 与 `monotonic_ns`（§2.84 第 3、9 条已在真实封证上量过），`:386 server_log` 是服务端自己的日志文本（读数按名成对、行首带服务端自己的秒戳）。⇒ §2.84 第 9 条那句「不需要扩封存 schema」在字段层成立：新判据要同时拿到**授权窗**与**带戳读数**，两处今天都拿得到，不必新造采集。
4. **卡面口径据此分裂成两笔（M 的裁决，不扩范围）**：
   - **(A) 非接管式落地**：新增具名判据（边界配对：授予前末枚 + 释放后首枚，申报跨度与授予前秒数）+ 单元/契约测试 + §2.84 第 8 条已改写的三枚具名反证；不动被覆盖符号、不动 fixture 的 `assertions`/`assertion_digests`、不动 registry。POST 必须量到：本案 `case_version` 仍 `1e31f0003b4e30e0…812a`、`check_case_assertions.py` 仍 `151 registered` 且 rc=0、真实封证仍**可复判**（对旧 bundle 跑一次 `rejudge` 的具名读数）、门载荷仍 `cfa0f118…63afd6`。
   - **(B) 接管（另行一笔，且要用户点头）**：把本案的位移判据换成归因形状、重记 `assertion_digests` ⇒ `case_version` 移动 ⇒ 按 §2.85 第 4 条 `5086ee42…` 成为按新字节不可复判的历史时点，要在封证面重新自证就得重跑一次 E7 式规范卷封证（真实封证 1→2，需引擎窗）。⇒ **顺序仍按 §2.85 第 5 条：④（采样密度）先于 (B)**，否则新封证仍是窗内 1 枚读数的形状。
5. **本轮不落地判据字节**：(A) 的实施排到下一轮，并要先在主干当前字节上量一份 PRE（`case_version`/`assertion_digests`/门载荷/rejudge 对旧 bundle 的具名读数），否则 POST 的「逐字相同」没有对照。真实封证仍 **1**；门载荷对纯 `docs/**` 追加按构造不动（`tools/report_promotion.py:147` 的仓库侧输入只有 `tests/fixtures/cases`），其值仍 §2.84 第 10 条实量值。
