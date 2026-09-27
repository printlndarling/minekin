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

1. **单 bundle 双载体不需要扩 schema**：封存入口本就有 `--server-directory` 与 `--world-run-document` 两个参数（`tools/seal_run_evidence.py:869/898` 一带，分别封成 `server/server.log` 与 `host-run-document.json`）。卷内 6 份 `CORE-030` 加入者 bundle 之所以只有后者、没有前者，是因为当时那次封存没传 `--server-directory`——**缺的是参数，不是实现**。⇒ E7 仍是「一个 bundle、同一次 run」封证，不触主控保留的跨 bundle 链上载体。
2. **但服务端位置读数是无名的，加入者的移动今天不能自证归属**。实测三件事：
   - `tools/run_controlled_server.py:489/507` 把探针发成 `data get entity <player> Pos|Rotation`，目标名只出现在**命令**里；
   - 卷内真 `server/server.log` 里只有答案行 `has the following entity data: [...]`，`data get entity <name>` 形式的命令行 **0 次出现**（抽样 CORE-060 ×3、CORE-020 ×1，答案行 0~6 条）；
   - 判据侧 `tools/assert_case_evidence.py:246,266-280` 的 `_PROBE`/`probe_readings` 与 `the_server_saw_the_kin_move`(`:1599`) 取的是**全日志所有答案行的首尾两次读数**，只按分量数区分位置/朝向，不按名字区分；
   - 卷内 100 份 `orchestrator-trace.json` 里**没有一份提到 probe** ⇒ 探针目标今天没有被封进任何产物。
   单客户端时这不成问题（一次 run 只问一个名字，且 `domain.sh:482` 的 `--probe-player "${probe:-${player}}"` 只有一个目标）；两客户端时，若两个名字都被问过，轨迹就会被错配。
3. **裁决（写死 M-C1 的边界）**：M-C1 的**第一份提交**必须先补「探针目标归属」这一格载体——把本次 run 被问过的玩家名记进**已有**封存产物 `asserter-inputs.json`（`seal_run_evidence.py:795` 的 `ASSERTER_INPUTS`），并在 case 判据里要求「被问过的名字恰为加入者用户名，且仅此一个」。这是 `tools/**` 面内的新增字段/新增 artifact 名，沿用既有名字常量纪律，**不是** `minekin.p0.evidence.v1` 的 schema 扩展。
4. **反证要求**：M-C1 必须现场演示——把同一份日志的归属换成主客户端名字、或塞进第二个被探针的名字，判据要**具名失败**（`the_server_saw_the_kin_move` 不得在归属不成立时仍返回 None）。做不到这一条，M-C1 不得登记 case，E7 不得排封证窗口。
5. **不因此改动现有 case 的判据**：既有单客户端案的「一个目标」前提不变，H1h/V5 之前也不依赖本节。
