# 本地 1.20.1 Demo：启动说明与已知限制

这条入口给用户的是三件事：**一个能看的后台**（只读投影 + Dashboard 面板）、**一套可执行的基础资源技能**（从眼前看到的资源取木、拾取掉落物、按真实背包界面合成）、**一条自己决定下一步的游玩闭环**（没有人写下动作序列，做什么由世界读数决定）。

入口只有一个文件：`test-orchestrator/runner/demo.sh`。它不是第二套测试框架，而是 `run.sh` 的组合——里面每一步都走产品自己的代码路径。

## 一、这台机器需要准备什么

| 东西 | 怎么确认 | 怎么补 |
| --- | --- | --- |
| Docker，以及受控运行镜像 `minekin-runner:local` | `bash test-orchestrator/runner/run.sh doctor` | `docker build -f test-orchestrator/runner/Dockerfile -t minekin-runner:local .` |
| 一份 1.20.1 官方服务端 jar（离线模式专用） | 环境变量 `MINEKIN_SERVER_JAR` 指到的文件存在 | `uv run python tools/verify_supply_chain.py --version 1.20.1 --save-server .tmp/mc-1.20.1-server.jar --max-bytes 60000000` |
| 客户端 bundle（1.20.1 的 Fabric + 桥 + 版本库） | 入口会自己装进卷里 | 无需手工准备；首次冷装约 740 MB，15–25 分钟 |
| Node + pnpm（**只有 `--browse` 需要**） | `pnpm --version` | Dashboard 的依赖装在 `dashboard/` 下，`pnpm install` |

服务端 jar 是宿主机上的文件，路径用 `MINEKIN_SERVER_JAR` 给；`.tmp/` 只是本机缓存，不属于仓库。

## 二、四个入口

```bash
# 0) 只核对运行环境，不动卷
bash test-orchestrator/runner/run.sh doctor

# 1) 脚本化底座演示：加入、按住前进键走、向右转视角、交还按键
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar bash test-orchestrator/runner/demo.sh
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar bash test-orchestrator/runner/demo.sh --again  # 同卷同 Kin 根，跳过冷装

# 2) 基础资源技能：按 examples/skill-plan-gather-and-craft.json 取木 -> 拾取 -> 合成
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar bash test-orchestrator/runner/demo.sh --skills

# 3) 自主闭环：没有人命名步骤，PlayerMind 每一步看完读数再决定下一个技能
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_AUTONOMOUS_STEPS=8 \
  bash test-orchestrator/runner/demo.sh --autonomous

# 4) 看完这次会话：一条命令起只读投影、等它真的应答、再把面板对上它
bash test-orchestrator/runner/demo.sh --browse
```

`--autonomous` 与 `--skills` 的差别只有一处：前者交给会话的是 `--autonomous`，后者是 `--skill-plan`。因此**这条命令无法提前告诉你 Kin 会试哪几个技能**——序列是这次运行的结果，不是它的输入。`MINEKIN_DEMO_AUTONOMOUS_STEPS` 给一个步数上界（默认 12），因为每一步都是真实世界里的真实动作，走错一步要花掉它的超时。

固定种子的平坦世界不长树，所以 `--skills` 与 `--autonomous` 都会自己向 harness 要一段可破坏的资源（入口在内部设 `MINEKIN_DOMAIN_RESOURCE_TRUNK=1`，把橡木原木堆在 Kin 正前方）；没有可看的东西，选择器就无从选择。操作者**不需要也不应该**再手工设它：`demo.sh` 已经设了，而它和 `MINEKIN_DOMAIN_USE_TARGET`/`MINEKIN_DOMAIN_PROBE_SECOND` 同设会被 `domain.sh` 具名拒止。

## 三、跑完之后在哪里读结果

1. **终端里的 run 文档**。会话退出前，`domain.sh` 会把 Core 的 run 文档原样打印一行。`--autonomous` 那次要读的是 `run.autonomous`：`direction`（这次的目标）、`steps[]`（每一步的 `intent.skill / intent.reason / result / reason / attribution / result_observation_ref`）、`stop_reason`、以及 mind 自己的账（`decision_source`、`model_enabled`、`model_refusal`、`model_calls`、`model_spent_micro`）。
2. **面板**。`demo.sh --browse` 之后打开 `http://127.0.0.1:5175/?adapter=gateway&gateway=/gateway`。技能步那一组显示的是**最后一条已收口的步骤**：目标、当前动作、实际结果、失败原因、决策来源、模型拒止码。Ctrl-C 会把面板和只读投影一起带走。
3. **判定与证据**（可选）。这条命令的卷名必须和 demo 一致：demo 写在自己的 `minekin-local-demo`，而 `run.sh --shell` 默认挂的是规范卷 `minekin-runner-data`，不带卷名去查就是查错了地方。
   `MINEKIN_RUNNER_DATA=minekin-local-demo bash test-orchestrator/runner/run.sh --shell "python -m minekin_core evidence verify <run_id>"`。

步与证据里 `result` 的读法必须记住一条：CONFIRMED/FAILED/UNKNOWN 只由**后来的世界读数**判定，桥自己报的 SUCCEEDED 不算数；UNKNOWN 不会被自动重试。

## 四、把大模型接进来（可选，默认不接）

PlayerMind 读这几个变量，全部由宿主机传给容器，**仓库里不出现任何一个值**：

```bash
export MINEKIN_MODEL_PROVIDER=<提供方>
export MINEKIN_MODEL_BASE_URL=<服务地址>
export MINEKIN_MODEL=<模型名>
export MINEKIN_MODEL_API_KEY_ENV=<存放密钥的那个变量名>   # 注意：这里放的是变量名，不是密钥
export MINEKIN_MODEL_TIMEOUT_MS=8000
export MINEKIN_MODEL_RUN_COST_CAP=200000
export MINEKIN_PERSONA_SEED=<人格种子>          # 不设就是一个不同的 Kin
export MINEKIN_RUNNER_FORWARD_ENV=<存放密钥的那个变量名>  # 逗号分隔的“变量名”列表
```

`MINEKIN_RUNNER_FORWARD_ENV` 只接受变量**名**（字母/数字/下划线，不能以数字开头），名字不合法就直接拒（退出码 2），不会被拼进 docker 的参数里。密钥的值自始至终不进仓库、不进日志、不进任何提交物。

一个都没设的时候，这次运行仍然完整跑通，只是每一步的来源是 `local_reflection`，并且 run 文档与面板都会写出 `MODEL_NOT_CONFIGURED`——**这是明说的降级，不是假装问过模型**。

## 五、已知限制（具名，不用测试数量掩盖）

1. **合成这一步现在拿不到确认。** 本次真实运行里 `break_seen_block`（取木）和 `collect_dropped`（拾取）都是 CONFIRMED，而 `craft` 是 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，归因 `INSUFFICIENT_INFORMATION`。已经量到的边界是：配方点击确实发出去了，客户端进程和服务端连接在整段 5 秒判据窗口里都还活着（服务端日志里能看到加入与 15 秒后的断开），但那一步窗口内**没有任何新的被采纳读数到达** Core。到底是客户端 tick 停住，还是 Core 把每一帧都拒了，当前只读面区分不了——要区分就得扩 run 文档 / 封存 schema，那是主控保留的决定，本次没做。因此**"通过真实背包/GUI 制作基础工具"这一项目标只完成到"点击已发出并被桥接受"，没有完成到"世界确认合成成功"**。
2. **合成产物落在结果槽之后无人取走。** Core 没有"从结果槽点击取物"这个技能，契约里也没有。上面的限制 1 修好之后，这一条仍然单独存在。
3. **面板上的技能行不带模型的配置与花费。** `model_enabled`、provider、`model_calls`、`model_spent_micro`、`model_cap_refusals` 只记在 run 文档的 mind 段里；台账的技能行不携带，只读投影不解析 bundle 的 run 文档。面板对这两格会直接写明 `not_wired` 的理由，而不是留空白。
4. **本次演示里"目标"不是大模型选的。** 这台机器上没有可用的模型凭据，所以四次意图全部来自 `local_reflection`（`MODEL_NOT_CONFIGURED`）。"由大模型自主选定目标"这件事**尚未在真实游戏里验证过**；已经验证的是：没有人类逐步指令、没有预设动作序列，Kin 依然按读数一步步试下来，并在失败后调整（合成 UNKNOWN 之后转为 `turn_to` 继续找里程碑需要的东西）。
5. **桥字节与已封证据不一致这件事已经闭合（2026-09-30）。** 起因是本轮修了两处桥缺陷（界面其实没打开；观察者采集器在界面真打开后会让客户端崩一次），bundle 摘要变了，而 `tests/fixtures/registry/reviewed-tested-bundles.json` 那条 1.20.1 行还指着旧的 recipe/bridge 摘要。当时不是推测：2026-09-29 在本机用默认（registry）路径跑了一次 demo，安装在取 bundle 前就具名拒止并以 rc=11 退出，逐字读数：
   `{"category": "SUPPLY_CHAIN", "component": "launcher.provision", "operation": "fetch", "retryability": "OPERATOR_ACTION", "message": "recipe tests/fixtures/runtime-input/bundle-candidate-1.20.1.json digests to bd6afaee…, not the reviewed 8ce43e26…"}`。
   那两天里本说明的 2)、3) 因此带上 `MINEKIN_DEMO_BUNDLE_PROFILE`——这个旋钮是为"字节已经动了、封证还没续"准备的**证据中立的读法**，不是绕过。V1201 六案在新桥字节下续封、registry 行 renew 之后（读数见 `docs/validation/v1201-autonomous-loop-and-registry-renewal-2026-09-30.md`），默认路径已实测恢复：2026-09-30 本机 `demo.sh --again` 不带任何 profile 旋钮跑通，run `f19caae6a1be42608b0f833fe79dfbdb` 的 `auto_bundle` 段是 `{"bundle_id": "1.20.1-linux-x86_64-offline-java21", "recipe_path": "/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json", "launch_plan_digest": "924931e574de…6cc0", "registry_revision": "c2aace9aed0b…", "status": "ready", "reused": 3639, "installed": 0}`，随后 `the session is playable`，前进与停止都被服务端看到，退出码 14 是 harness 到点停问（正常收尾），rc=11 的供应链拒止没有再出现。2)、3) 的命令因此回到默认路径；`MINEKIN_DEMO_BUNDLE_PROFILE` 仍然可用，用途是下一次"字节动了、封证未续"的窗口。旧封证与上面那条 rc=11 读数作为历史读数保留，不改写。
6. **会话是被停下来的，不是自己收尾的。** 本次 run 文档：`stop_reason: CONTROL_CHANNEL_LOST`、`outcome: BRIDGE_LOST`、`input_release_failed: true`（停止指令里那把租约 `unconfirmed: [290]`）。也就是说"交还按键"这一步在自主收尾路径上还没有确认闭环。
7. **只在 loopback 上跑。** 不连接、不修改任何远程测试服；无 HOST/PERSIST、无在线认证、无公网访问。Dashboard 的通用写控制端点未开放，唯一已授权的写面是身份改名。
8. **`--gateway`/`--browse` 需要宿主机能起容器端口**，且 `--browse` 会在本机监听 8787 与 5175；脚本只会关掉自己起的那个容器，已经在跑的容器原样保留并报告。

9. **拾取现在会追着掉落物迈步，并且写明自己追了几步、判读到哪一帧。** `collect_dropped` 过去只按动作计划里的 `walk_seconds` 走一步，然后原地把整个判据窗口听完：2026-09-30 的 run `974a2d19a0a741ad9514437bbee7fc14` 就是这样在木头还看得见的时候结束成 `UNKNOWN / NO_CONFIRMING_OBSERVATION`（同一技能在 2026-09-29 的 run `0c10d0774f704f47a909728cf745135e` 里是 CONFIRMED，所以这一步不是恒败，是那一步没走到跟前）。现在它每读到一帧就重新朝掉落物当时的位置迈步——第一步仍是计划给的长度，之后每步 0.5 秒——并且只在剩余窗口还容得下"一步路 + 一帧可判读"时继续迈；否则停在最后一步留下的位置，把剩下的窗口用来听。无论成败，`details` 都带 `steps`（发出过几次迈步）和 `newest_checked_tick`（判读到的最新一帧的 tick）：`newest_checked_tick == pre_tick` 说的是通道安静（一帧都没到 Core），大于 `pre_tick` 说的是帧到了而东西没进包。这两种解释要改的东西不同，而只看 `post_tick: null` 分不出来——这也是这次改动的主要目的。同步的两格（`cognition_refusals`、`snapshot_rejections`）如果非空，还能进一步指出是感知门在拒帧还是客户端没再报。**这条只动 Python 字节，没动 bridge-1201，因此不触发 V1201 六案的重封；它的活体读数本轮还没取到（受控 runner 的容器引擎此刻对 `docker version` 返回 500，跑不了真跑），下一次 `demo.sh --skills` 的 run 文档可以直接判读。**
10. **拾取之后的两格仍未闭合。** `craft` 的世界侧确认（上面第 1 条）和"从结果槽取走合成产物"的技能（第 2 条）都还在原处；本轮没有为了让它们变绿而改动契约或证据 schema。

## 六、本次演示的读数（2026-09-29，run `0c10d0774f704f47a909728cf745135e`）

`--autonomous`，`MINEKIN_DEMO_AUTONOMOUS_STEPS=8`，热卷（同卷同 Kin 根），上界 2700 秒而实际约 1 分钟结束。

| 步 | 意图（`intent.reason`） | 结果 | 失败原因 / 归因 | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- | --- |
| 1 | break the block in view for minecraft:oak_log | CONFIRMED | — | tick=1441 → tick=1513 |
| 2 | collect the minecraft:oak_log in view | CONFIRMED | — | 1513 → 1535 |
| 3 | craft minecraft:oak_planks for hold_a_wooden_pickaxe | UNKNOWN | NO_CONFIRMING_OBSERVATION / INSUFFICIENT_INFORMATION | 1535 → 1634 |
| 4 | look for the next thing the milestone needs | STARTED | AIM_IN_PROGRESS / ACTION_NOT_EFFECTIVE | 1634 → 1645 |

同一次运行还读到：`perceived_information_class: PLAYER_EQUIVALENT`，`cognition_refusals: {MANAGEMENT_ONLY_DTO: 4}`（管理侧 DTO 被感知门挡在心的世界模型之外——这是门在起作用），`entities_admitted: 20`，`snapshots_admitted: 1`，`confirmed: 2`，`goal_met: false`，`direction: hold_a_wooden_pickaxe`，`model_enabled: false / model_calls: 0`。

只读投影在同一份台账上的读数（`build_snapshot(/data, kin-local-demo)`）：`skillSteps` 状态 `known`，`stepIndex=4 / stepCount=4`、`goal=hold_a_wooden_pickaxe`、`skill=turn_to`、`result=STARTED`、`reason=AIM_IN_PROGRESS`、`attribution=ACTION_NOT_EFFECTIVE`、`decisionSource=local_reflection`、`modelRefusal=MODEL_NOT_CONFIGURED`，`modelConfig` 与 `modelCost` 两组为 `not_wired` 并写明理由。

这一档只声明"本地 1.20.1 的这条 demo 跑通了"，不声明 Minekin 整体完工。
