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

`--skills` 读的是那份 JSON，操作者可以用 `MINEKIN_DEMO_SKILL_PLAN` 换成自己写的；它按原样传给容器里的会话，而工作树是以 `/src` 只读挂进去的，所以那个值必须是 `/src/...` 下的路径（把计划文件放在仓库里再指它）。其中 `craft` 一条可写 `"craft_all": true` 或 `false` 来点名要哪一笔点击：默认 `true` 是把成品放进背包的那一笔，`false` 是配方书的单点、成品停在光标上；写非布尔值会在解析期具名拒止（`skills[i] (craft) needs craft_all to be true or false`），而 run 文档的 `details.craft_all` 会写明那一次实际发出的是哪一笔。第五节第 10 条是这件事的判据依据。

固定种子的平坦世界不长树，所以 `--skills` 与 `--autonomous` 都会自己向 harness 要一段可破坏的资源（入口在内部设 `MINEKIN_DOMAIN_RESOURCE_TRUNK=1`，把橡木原木堆在 Kin 正前方）；没有可看的东西，选择器就无从选择。操作者**不需要也不应该**再手工设它：`demo.sh` 已经设了，而它和 `MINEKIN_DOMAIN_USE_TARGET`/`MINEKIN_DOMAIN_PROBE_SECOND` 同设会被 `domain.sh` 具名拒止。

想吃东西的场景另有夹具：`MINEKIN_DOMAIN_HUNGRY_KIN=1`（直接设在 demo 命令的环境里，`run.sh` 按名转发）会在 Kin 入服时给它三只苹果，再用一发短促高浓度饥饿效果把饥饿条清空——食用技能的前提是"饥饿条有空间"，而平坦受控世界不会在任何有用时限内自己把条耗下来。它与 `MINEKIN_DOMAIN_USE_TARGET` 同设会被具名拒止：使用键会先打中准星上的方块，那会让每一次进食都成拒绝。仓库里的确定性探针计划是 `examples/skill-plan-eat.json`（先转向空处让准星落空，再吃苹果）：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DOMAIN_HUNGRY_KIN=1 \
MINEKIN_DEMO_SKILL_PLAN=/src/examples/skill-plan-eat.json \
  bash test-orchestrator/runner/demo.sh --skills --again
```

自主入口同理，把目标留空就是"没有常驻目标的 Kin"（选择器自己决定先吃）：`MINEKIN_DOMAIN_HUNGRY_KIN=1 MINEKIN_DEMO_GOAL_PRODUCT= bash test-orchestrator/runner/demo.sh --autonomous --again`。两发都还没跑过活体（2026-10-03 首发被本机后台内存守卫中断），读数落地后按第五节编号补登。

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

1. **合成这一步在 2026-09-29 那次运行里拿不到确认。** 那次真实运行的读数是：`break_seen_block`（取木）和 `collect_dropped`（拾取）都是 CONFIRMED，而 `craft` 是 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，归因 `INSUFFICIENT_INFORMATION`。当时量到的边界是：配方点击确实发出去了，客户端进程和服务端连接在整段 5 秒判据窗口里都还活着（服务端日志里能看到加入与 15 秒后的断开），但那一步窗口内**没有任何新的被采纳读数到达** Core。**当时记下的那句"要区分就得扩 run 文档 / 封存 schema，那是主控保留的决定"已经按新读数作废**：run 文档本来就带 `details` 这个自由字段，现在它把三种收尾分开说（`newest_checked_tick` 等于 `pre_tick` ⇒ 通道安静；大于 ⇒ 帧到了而背包同步号没动；`gui_open=false` ⇒ 界面根本没被看见打开），schema 一格没扩。**"通过真实背包/GUI 制作基础工具"这一项目前的完成度**：点击已发出并被桥接受、判据窗口会说明它为什么没确认、默认点击已换成会把成品放进背包的那一笔（下面第 10 条），而"世界确认合成成功"那一格仍待活体读数。**那一格在 2026-09-30 由第 11 条的技能补上并量到了**（run `e1e981553a0d4ea69468f6bc07a88fb5`：木板与木棍两步 CONFIRMED，服务端存档背包 4 根木棍 + 2 块木板），而 `craft` 这一条本身按第 12 条停在 `UNKNOWN`。
2. **合成产物落在结果槽之后无人取走——这一格已经在 2026-09-30 关掉。** 原先的说法（Core 没有"从结果槽点击取物"这个技能、契约里也没有）**按读数作废**：1.20.1 的桥在**已封的字节上**就吃槽位点击（`docs/validation/v1201-autonomous-loop-and-registry-renewal-2026-09-30.md` 第八节有 file:line），而 Core 侧现在有了 `craft_take_result`（第 11 条）。它读到的确认不靠桥自报：run `e1e98155…` 的 `details` 写明两笔点击、revision 1699→1732→1754，服务端存档背包 4 根木棍 + 2 块木板。仍然在的是第 11 条末尾那一格——光标存放的第三笔在活字节上还没被需要过，也就还没被活字节验证过。
3. **面板上的技能行不带模型的配置与花费。** `model_enabled`、provider、`model_calls`、`model_spent_micro`、`model_cap_refusals` 只记在 run 文档的 mind 段里；台账的技能行不携带，这两格对只读投影恒为 `not_wired`（措辞与 `mockFixtures.ts` 逐字镜像，防两侧漂移）。**行为参数是这次唯一从 bundle 的 run 文档解析出来的一格**：`behaviorParameters` 读的是 `run.autonomous.steps[].intent.arguments`（脚本运行没有自主段时退回 `mind.executing_arguments`），所以只有**已封且 `verify_addressed_bundle` 校验通过、bundle 里带 run document** 的 run 才有读数，未封的活 run 与不满足任一条的 bundle 一律写成具名缺口而不是空串。投影仍然不改写历史封证，只在读取侧解析已被摘要钉过字节的那份 run document。
4. **本次演示里"里程碑/目标"不是大模型选的。** 这里要分清两件不同的事，别把它们混成一句。其一，**答的是哪一步技能**：这台机器先前确实没有可用的模型凭据，所以那一阶段的意图全部来自 `local_reflection`（`MODEL_NOT_CONFIGURED`）；自 §四 那条 OpenAI-compatible 配置接上之后，这一句作为"当前事实"已经不再成立——真实端点已在游戏内逐步作答，run `151e7dc1a64e4d94a66061904f7ce937` 每步的 `decision_source` 都是 `model`、`model_refusal` 为空（见六之十二），`local_reflection` 的读数原样保留为历史。其二，**目标里程碑本身**（要哪件产物、几件、朝哪个方向，即 `hold_stick` 那一条）：它自始至终由操作者用 `MINEKIN_GOAL_*` 递进去，Core 不读任何默认物品，大模型选的是"当前 attempt 哪个技能"而不是"要什么里程碑"。所以"由大模型自主选定里程碑/目标"这件事**仍未在真实游戏里验证过**；已经验证的是：没有人类逐步指令、没有预设动作序列，Kin 依然按读数一步步试下来，并在失败后调整。2026-09-30 的那次自主运行把"调整"量到了名字这一层：七步里前四步 CONFIRMED，随后 `turn_to` 连撞三次 `AIM_STALLED`，mind 段于是写下 `excluded_skills: ["turn_to"]`、`retry_budget: 2` 并以 `NO_FEASIBLE_SKILL` 具名收尾（见六之二）——这是改线，不是重试同一笔。
5. **桥字节与已封证据不一致这件事已经闭合（2026-09-30）。** 起因是本轮修了两处桥缺陷（界面其实没打开；观察者采集器在界面真打开后会让客户端崩一次），bundle 摘要变了，而 `tests/fixtures/registry/reviewed-tested-bundles.json` 那条 1.20.1 行还指着旧的 recipe/bridge 摘要。当时不是推测：2026-09-29 在本机用默认（registry）路径跑了一次 demo，安装在取 bundle 前就具名拒止并以 rc=11 退出，逐字读数：
   `{"category": "SUPPLY_CHAIN", "component": "launcher.provision", "operation": "fetch", "retryability": "OPERATOR_ACTION", "message": "recipe tests/fixtures/runtime-input/bundle-candidate-1.20.1.json digests to bd6afaee…, not the reviewed 8ce43e26…"}`。
   那两天里本说明的 2)、3) 因此带上 `MINEKIN_DEMO_BUNDLE_PROFILE`——这个旋钮是为"字节已经动了、封证还没续"准备的**证据中立的读法**，不是绕过。V1201 六案在新桥字节下续封、registry 行 renew 之后（读数见 `docs/validation/v1201-autonomous-loop-and-registry-renewal-2026-09-30.md`），默认路径已实测恢复：2026-09-30 本机 `demo.sh --again` 不带任何 profile 旋钮跑通，run `f19caae6a1be42608b0f833fe79dfbdb` 的 `auto_bundle` 段是 `{"bundle_id": "1.20.1-linux-x86_64-offline-java21", "recipe_path": "/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json", "launch_plan_digest": "924931e574de…6cc0", "registry_revision": "c2aace9aed0b…", "status": "ready", "reused": 3639, "installed": 0}`，随后 `the session is playable`，前进与停止都被服务端看到，退出码 14 是 harness 到点停问（正常收尾），rc=11 的供应链拒止没有再出现。2)、3) 的命令因此回到默认路径；`MINEKIN_DEMO_BUNDLE_PROFILE` 仍然可用，用途是下一次"字节动了、封证未续"的窗口。旧封证与上面那条 rc=11 读数作为历史读数保留，不改写。
6. **会话是被停下来的，不是自己收尾的。** 本次 run 文档：`stop_reason: CONTROL_CHANNEL_LOST`、`outcome: BRIDGE_LOST`、`input_release_failed: true`（停止指令里那把租约 `unconfirmed: [290]`）。也就是说"交还按键"这一步在自主收尾路径上还没有确认闭环。**这一格在 2026-09-30 的自主运行里量到了闭环**：run `1d681c16750d4805a7603973f7175f99` 是 `input_release_failed: false`、`session_state: STOPPED`、`connection_state: PLAYABLE`，停止指令逐字为 `{"asked": [385], "released": [385], "unconfirmed": [], "nothing_held": [], "left_alone": [], "terminated": [385], "unresolved": []}`，而它的收尾原因是 `autonomous.stop_reason: NO_FEASIBLE_SKILL`（心的改线自己停下来的），不是控制器丢通道。历史上那次 `unconfirmed: [290]` 的读数原样保留，不改写。
7. **只在 loopback 上跑。** 不连接、不修改任何远程测试服；无 HOST/PERSIST、无在线认证、无公网访问。Dashboard 的通用写控制端点未开放，唯一已授权的写面是身份改名。
8. **`--gateway`/`--browse` 需要宿主机能起容器端口**，且 `--browse` 会在本机监听 8787 与 5175；脚本只会关掉自己起的那个容器，已经在跑的容器原样保留并报告。

9. **拾取现在会追着掉落物迈步，并且写明自己追了几步、判读到哪一帧。** `collect_dropped` 过去只按动作计划里的 `walk_seconds` 走一步，然后原地把整个判据窗口听完：2026-09-30 的 run `974a2d19a0a741ad9514437bbee7fc14` 就是这样在木头还看得见的时候结束成 `UNKNOWN / NO_CONFIRMING_OBSERVATION`（同一技能在 2026-09-29 的 run `0c10d0774f704f47a909728cf745135e` 里是 CONFIRMED，所以这一步不是恒败，是那一步没走到跟前）。现在它每读到一帧就重新朝掉落物当时的位置迈步——第一步仍是计划给的长度，之后每步 0.5 秒——并且只在剩余窗口还容得下"一步路 + 一帧可判读"时继续迈；否则停在最后一步留下的位置，把剩下的窗口用来听。无论成败，`details` 都带 `steps`（发出过几次迈步）和 `newest_checked_tick`（判读到的最新一帧的 tick）：`newest_checked_tick == pre_tick` 说的是通道安静（一帧都没到 Core），大于 `pre_tick` 说的是帧到了而东西没进包。这两种解释要改的东西不同，而只看 `post_tick: null` 分不出来——这也是这次改动的主要目的。同步的两格（`cognition_refusals`、`snapshot_rejections`）如果非空，还能进一步指出是感知门在拒帧还是客户端没再报。**这条只动 Python 字节，没动 bridge-1201，因此不触发 V1201 六案的重封；它的活体读数本轮还没取到（受控 runner 的容器引擎此刻对 `docker version` 返回 500，跑不了真跑），下一次 `demo.sh --skills` 的 run 文档可以直接判读。** 引擎恢复后读数取到了：`collect_dropped` 在 run `615eb862eb754aebb6a555904709821d`（`steps=1`、`newest_checked_tick=19068`）与 run `e1e981553a0d4ea69468f6bc07a88fb5`（`steps=1`、`newest_checked_tick=1699`）都是 CONFIRMED，`details` 那两格按设计把"追了几步、判读到哪一帧"写进了 run 文档；同一天也量到一次 `FAILED / NO_SEEN_DROP`，见第 14 条。
10. **合成的默认点击换成了那一笔会把成品放进背包的交易。** 依据是量出来的两件事：配方书的单点（`clickRecipe` 的非 craftAll）把成品留在**光标**上，而 Core 读得到的 `inventory` 与 `GuiScreenValue` 都不报光标那一格（`src/minekin_core/domain/perception.py`），于是 §4 那条「材料减少与产物增加同时出现在同步后的 revision 上」的判据在那一笔点击之后不可能满足——这正是历次 demo 把 `craft` 收尾成 `UNKNOWN / NO_CONFIRMING_OBSERVATION` 的形状。现在 `craft` 默认发 `craft_all=true`；技能计划可以逐条写 `"craft_all": false` 要回单点，非布尔值会在解析期具名拒止（`skills[i] (craft) needs craft_all to be true or false`），而 run 文档的 `details.craft_all` 写明那一次实际发出的是哪一笔。**这批只动 Python 字节**：`craft_all` 早就存在于 proto 与 bridge-1201 的**已封字节**里（`proto/minekin/v1/control.proto` 的 `GuiRecipeClick`、`BridgeIpcWorker` 的 `clickRecipe(..., craftAll)`），所以 V1201 六案的封证不受影响，证据 schema 也没动。**活体读数仍未取到**：`craft` 是否真的转成 CONFIRMED 要看下一次 `demo.sh --skills` / `--autonomous` 的 run 文档——2026-09-30 复量时受控 runner 的容器引擎仍对 `docker version` 返回 500（客户端 29.5.3 / API 1.54 那半有答复，Linux 引擎那半没有），跑不了真跑。**这一格后来量到了，答案是否定的**：引擎恢复后冷卷 run `615eb862eb754aebb6a555904709821d` 的 `craft` 仍是 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，`details` 说 `craft_all=true`、`gui_open=true`、revision 19068→19167（帧到了而背包没给出确认）。默认点击不是收口，收口在第 11 条。
11. **仍欠的一格是「取走结果槽/光标那一笔」的显式技能——这一格已经在 2026-09-30 补上。** `craft_take_result` 按既有 GUI/输入契约发三笔：先 `GuiRecipeClick(craft_all=false)` 让配方书把材料铺进网格，再对结果槽 0 发 `GuiSlotClick(button=1, mode=QUICK_MOVE)`，只有在读数说材料已减而产物始终没进包时才补第三笔 `mode=PICK` 的存放点击，且只放进**最新一帧读数报为空**的那一格（放不进去就具名停在 `CRAFT_NO_EMPTY_SLOT`，因为"光标上那件东西无处可放"和"根本没合成"在读数上长得一样）。槽位坐标是换算的：读数报的是 PlayerInventory 的格子号（0–8 快捷栏、9–35 主包、空的不报），而界面点击吃的是当前容器的格子号（玩家 2×2 界面：结果 0、网格 1–4、主包 5–31、快捷栏 32–40）。**活体读数已取到**（run `e1e981553a0d4ea69468f6bc07a88fb5`，热卷，同一卷的上一次运行是 `615eb862eb754aebb6a555904709821d`）：`oak_planks` 与 `stick` 两步都是 CONFIRMED，`details` 为 `clicks=recipe_fill+result_quick_move`、`craft_all=false`、`gui_open=true`，第二笔之后 revision 1699→1732→1754 就满足了 §4 的判据，因此第三笔存放点击没有被需要。**服务端自己存下来的 player.dat 是独立的一格证据**：那次运行结束时背包里是 `minecraft:stick ×4`（槽 7）与 `minecraft:oak_planks ×2`（槽 8），没有 `Carried`——成品确实进了背包，而不是桥自报成功。
12. **craft_all 这一笔在活字节上仍不足，这一次是有名字的。** 冷卷 run `615eb862…` 的三件证据把范围收到一处：客户端日志里 `bridge clicked recipe minecraft:oak_planks (craftAll=true)` 说点击确实发出并被接受；`advancements/…/oak_planks` 的 `done: true`（`has_logs` 在点击前两秒达成）和存档 `recipeBook` 里的 4 条配方说明配方书侧是开着的，"配方书不认识这笔点击"那条猜测被排除；而同一份 player.dat 里 `Inventory` 是 **0 格**、没有 `Carried`。合起来的读数只支持一种说法：材料离开了 PlayerInventory（进了 2×2 网格），到存盘那一刻没有任何东西回到背包。于是第 10 条那句"默认点击已换成会把成品放进背包的那一笔"在活字节上并不成立，`craft` 保留原样而收口改用第 11 条的技能。
13. **木镐这一步卡在 2×2 网格，不在技能上。** `craft_take_result` 已经在 2×2 里连过两配方（木板、木棍），但 `minecraft:wooden_pickaxe` 需要 3×3 工作台的网格；玩家自带界面装不下它，而本项目还没有"放下一个工作台"的技能（`SKILL_OFFER` 里没有放置这一步）。也就是说"最终取得木镐"这一目标欠的是**放置技能 + 木板数量**（一次采木 = 4 板，镐要 3 板 + 2 棍，还要先摆台），不是合成判据。这一条留给主控决定要不要把 S2 的收口范围扩到放置。**2026-09-30 起这一格多了一层：Core 不再把 3×3 的配方发给只开 2×2 的技能。** 配方现在按产物从 `src/minekin_core/domain/recipe_catalog.py` 解析，装不下的形状具名返回 `CRAFT_GRID_TOO_SMALL`（归因 `SKILL_NOT_IMPLEMENTED`），心因此永远不会为木镐发出那一笔点击——见第 16 条与六之四。**2026-10-01 更正首句并追加活体读数：** 上面那句“还没有‘放下一个工作台’的技能（`SKILL_OFFER` 里没有放置这一步）”按现字节作废——`use_target`（第 16 条）已进 `SKILL_OFFER`，act 路径的 `build_plan` 会为净欠的 3×3 形状按 `Recipe.opens_grid_side` 预留 `crafting_table` 这一步，合成技能再按打开界面的有效边长（`crafting_grid_side`）取配方，所以工作台是被通用计划排出来的一步、也是能在开好的 3×3 窗口里点的配方，不是产物专用链。真机 run `f016077a47f54596ae53acf15d1c2a36`（demo2 就绪卷、缓存命中，真实模型 `model_enabled=true`、12 次调用）把这条链走通到了“选中要放的台”：break oak_log → collect oak_log → craft oak_planks → close_screen → craft `minecraft:crafting_table` → close_screen → `select_hotbar slot=8 expected=crafting_table`，这七步逐笔 CONFIRMED，没有一步是产物专用链。它停在下一手：`use_target_refusal` 只在准星报出 BLOCK/ENTITY 时才接受放置，而 Kin 站在原木被砸的位置向前扫视、准星迟迟没落到地面方块，于是 `use_target` 从未进入可行集；模型连发 `turn_to`（pitch −18、yaw 135/180/225）找落点，三次 `AIM_STALLED` 耗尽 `retry_budget=2` 后按名排除 `turn_to`，收尾 `stop_reason=NO_FEASIBLE_SKILL`、`goal_met=false`。所以“最终取得木镐”这一目标此刻仍记为未完成，欠的是**放置之前取到一个可放置朝向这一步的健壮性**（turn_to 在该俯角反复把已达成的转向判成停），而不是合成判据、也不是缺放置技能。排在下一轮：修正该俯角一带的转向停顿判定，或在心侧给“手持可放置方块却无准星目标”补一个朝脚下地面取朝向的通用手。
14. **`collect_dropped` 现在会追掉落物，但它要求的"看得见"并不恒成立。** 三次运行里两次 CONFIRMED（`615eb862…` 的 `steps=1, newest_checked_tick=19068`；`e1e98155…` 的 `steps=1, newest_checked_tick=1699`），一次 `FAILED / NO_SEEN_DROP`（run `8b8412ca182c4bb7b3764df5a5304d76`：`break_seen_block` 在 tick 1640 就 CONFIRMED，紧接着的 `collect_dropped` 在同一个 tick 的一帧里没读到掉落物）。所以这一步不是恒败，但也不是恒过——它把"那一帧里看得见"当成了前提，而木头从被破坏的那一格掉到地上时可能正好在视野锥之外。这一步的健壮性还欠一次改动（要么允许多帧重试，要么在破坏后重新瞄准掉落点）。
15. ~~面板说不出"心自己按名字停的线"~~ **已收口（2026-09-30，活体）**：台账加了 `AutonomousRunHalted` 一行，`goal / stop_reason / error / steps / confirmed / excluded_skills` 六个具名成员按 allowlist 投影进时间线，`action_id`、`lease_id` 与异常文本都不外泄（契约 §10、六之三）。面板那一格现在是 `decision AutonomousRunHalted | goal=hold_a_wooden_pickaxe, stop_reason=CONTROL_CHANNEL_LOST, error=ConnectionResetError, steps=4, confirmed=4`。仍然没收到的答案是"那个客户端 JVM 为什么走"——`error` 说的是哪一侧断的手（`ConnectionResetError` ⇒ 客户端那一侧重置了套接字），不是它离开的原因。

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

## 六之二、自主闭环的那一份读数（2026-09-30，run `1d681c16750d4805a7603973f7175f99`）

`--autonomous`，热卷（同卷同 Kin 根，上一次是 `615eb862…`），`auto_bundle` 走默认 registry 路径（`status: ready`、`reused: 3639`、`installed: 0`、`registry_revision: c2aace9aed0b…`）。这一档和上一档的区别是**它跑的是第 11 条的技能**：心问的是 `craft_take_result`，不是 `craft`。

| 步 | 意图（`intent.reason`） | 结果 | 失败原因 / 归因 | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- | --- |
| 1 | break the block in view for minecraft:oak_log | CONFIRMED | — | tick=1885 → tick=1960 |
| 2 | collect the minecraft:oak_log in view | CONFIRMED | — | 1960 → 1982 |
| 3 | craft minecraft:oak_planks for hold_a_wooden_pickaxe | CONFIRMED | — | 1982 → 2015 |
| 4 | craft minecraft:stick for hold_a_wooden_pickaxe | CONFIRMED | — | 2015 → 2037 |
| 5 | look for the next thing the milestone needs | FAILED | AIM_STALLED / ACTION_NOT_EFFECTIVE | 2037 → 2059 |
| 6 | look for the next thing the milestone needs | FAILED | AIM_STALLED / ACTION_NOT_EFFECTIVE | 2059 → 2081 |
| 7 | look for the next thing the milestone needs | FAILED | AIM_STALLED / ACTION_NOT_EFFECTIVE | 2081 → 2103 |

于是"取木→拾取→合成→成品进入背包"这一条链**在自主路径上也是靠读数确认的**（`autonomous.confirmed: 4`），不再只在技能计划那档里成立。

停止是心自己收的线，不是通道丢的：三次 `turn_to` 撞同一堵（`AIM_STALLED`）之后，mind 段是 `excluded_skills: ["turn_to"]`、`retry_budget: 2`、`current_intent: {kind: BLOCKED, reason: NO_FEASIBLE_SKILL, observation_ref: "tick=2103;generation=1"}`，`autonomous.stop_reason: NO_FEASIBLE_SKILL`；会话侧 `session_state: STOPPED`、`input_release_failed: false`，停止指令逐字 `release: {"asked": [385], "released": [385], "unconfirmed": []}`（第 6 条那一格因此闭环）。`outcome: BRIDGE_LOST` 仍是 harness 到点停问的收尾，退出码 14。

其余读数：`direction: hold_a_wooden_pickaxe`、`goal_met: false`、`intent_generation: 7`、`model_enabled: false / model_calls: 0 / model_refusal: MODEL_NOT_CONFIGURED`、四次意图全来自 `local_reflection`、`perceived_information_class: PLAYER_EQUIVALENT`、`cognition_refusals: {MANAGEMENT_ONLY_DTO: 4}`、`entities_admitted: 19`、`snapshots_admitted: 1`、`actions_applied: 6 / actions_refused: 13`。

同一份台账上的只读投影（`build_snapshot(/data, kin-local-demo)` 与 `build_timeline`，2026-09-30 本机对同一卷取的读数）与上面**逐行一致**：本次会话 33 行，`SkillStepRecorded` 七行按 `step_index=1..7` 排开，前四行 `result=CONFIRMED`（第 3、4 行的 `skill` 就是 `craft_take_result`）、后三行 `turn_to / FAILED / AIM_STALLED / ACTION_NOT_EFFECTIVE`，七行都带 `goal=hold_a_wooden_pickaxe, decision_source=local_reflection, model_refusal=MODEL_NOT_CONFIGURED`；快照的 `skillSteps` 取最后一行，因此面板那格是 `stepIndex=7 / stepCount=7`。输入释放也有行：六条 `InputLeaseGranted`（`control.{gui,aim,hotbar,move,mine,screen}.v1`）之后一条 `InputReleased | reason=EXPLICIT, had_lease=True`，再接 `FAILED→STOPPING→STOPPED`。`modelConfig`/`modelCost` 两格仍是 `not_wired` 并写明理由（第 3 条）。

**这一档量到一处 S3 要修的解释缺口**：心的收尾名没有落到台账上。run 文档里 `autonomous.stop_reason: NO_FEASIBLE_SKILL`、`excluded_skills: ["turn_to"]`、`current_intent.kind: BLOCKED` 都在，而台账那 33 行里**没有任何一行写这个名**——面板最新一行的解释是第 7 步的 `AIM_STALLED`，会话侧则是 `SessionInterrupted | outcome=BRIDGE_LOST`。只看面板的人会读成"通道被掐了"，而真实读数说"心自己按名字停的线，通道只是随后被 harness 停掉"。这一格排在 S3-C：把自主收尾的名字落进台账，让面板不靠 run 文档也能说出停在哪。

`goal_met: false` 与第 13 条一致：木镐要 3×3 工作台，而 `SKILL_OFFER` 里没有放置这一步。**这一档不声明木镐已取得**，它声明的是：S2 这条链在自主路径上按读数收口了（取木→拾取→合成→成品进包，四步全靠后来的读数确认），心在撞墙之后按读数把 `turn_to` 排除掉并具名停下，而面板对同一次 run 的七行解释与 run 文档逐行一致——除上面点名的那格收尾解释。

这一档只声明"本地 1.20.1 的这条自主链按读数收口了"，不声明 Minekin 整体完工。

## 六之三、收尾名落进台账的那一份读数（2026-09-30，run `a1d749937d864203ac50de8f98884882`）

`--autonomous`，同一枚热卷（server run 目录 `run-5`），`MINEKIN_DEMO_AUTONOMOUS_STEPS=8`。这一档是六之二末点名那一格（S3-C）的活体依据：**心的收尾名字第一次作为台账行存在**。

| 步 | 意图（`intent.reason`） | 结果 | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- |
| 1 | break the block in view for minecraft:oak_log | CONFIRMED | tick=1602 → 1659 |
| 2 | collect the minecraft:oak_log in view | CONFIRMED | 1659 → 1680 |
| 3 | craft minecraft:oak_planks for hold_a_wooden_pickaxe | CONFIRMED | 1680 → 1713 |
| 4 | craft minecraft:stick for hold_a_wooden_pickaxe | CONFIRMED | 1713 → 1735 |

四条 `SkillStepRecorded` 之后是那一行新字节（台账位置 146，只读投影逐字一致）：

```text
26 decision AutonomousRunHalted | goal=hold_a_wooden_pickaxe, stop_reason=CONTROL_CHANNEL_LOST, steps=4, confirmed=4 | applied
```

它与六之二那一档的区别正是这一行要回答的：那一次是心把 `turn_to` 排除后具名停下（`NO_FEASIBLE_SKILL`），这一次是频道真的没了（`CONTROL_CHANNEL_LOST`）。`excluded_skills` 这次为空 ⇒ 按投影规整格省略，不渲染成 `[]`。本次会话投影 30 行，`action_id` 与 `lease_id` 零出现。

**这次量到的失败读数：`input_release_failed: true`。** 它不是"键被按在世界里没松"，而是"Core 没能道别"，两条要分开。时间线（都是同一卷上的字节）：第 4 步落在 10:12:13.933 → 桥的最后一条日志 10:12:13.972（`bridge refused mine 17e651ef274640338c65980f8b08b048: GUI_CONFLICT`）→ 台账 5.0 秒空档 → Core 的收尾从 10:12:18.960 开始（halt 行、`PLAYABLE→FAILED→STOPPING→STOPPED`、19.041 `SessionInterrupted`）→ 受控服务器 10:12:18 `Kin lost connection: Disconnected`、10:12:19 `Kin left the game`。`crash-reports/` 为空、`stderr.log` 为空、没有 `ClientExited` 行，而 `domain.sh` 的等待环以 `kill -0 ${session_pid}` 为条件、"stopping the session" 打印在 CLI 已退出之后 —— 所以次序是**客户端先没了，Core 的第 5 次发送撞上空频道**（`run_autonomous_loop` 把 `OSError/RuntimeError` 折成 `CONTROL_CHANNEL_LOST`），harness 随后的 `session stop` 对着一具空频道发释放，只能记 `true`。
键没有留在世界上：桥的日志里每次 `pressed` 都配了对应的 `released`，最后一次是 `applied 54aa5727…: holding []`（10:12:11），第 5 步的 mine 是被**拒**的（根本没按下）；停在世界里的只有开着的物品栏界面。§12 那层"桥在自己频道断掉时松手"的看门狗此时没有键可松。

两处具名缺口由此登记：
1. 客户端 JVM 为什么在 10:12:14~18 之间消失，现有工件答不出——而循环把异常对象吞了，只剩一个笼统的 `CONTROL_CHANNEL_LOST`。已按 TDD 补上名字：`AutonomousRun.stop_detail` 记**异常类名**（不含 message，理由见契约 §10），同名写进 run 文档 `autonomous.stop_detail`，并以 `error` 成员落进那一行台账。同一条命令再跑一次的 run `78be6675c11d4661bb9f2bc86f6fb283`（server run 目录 `run-6`，台账位置 176）就是这个名字的第一条真实字节：`stop_reason=CONTROL_CHANNEL_LOST, error=ConnectionResetError, steps=4, confirmed=4`，四条 `SkillStepRecorded` 与上一档同形（`break_seen_block → collect_dropped → craft_take_result×2` 全 CONFIRMED），释放读数仍是失败的那一条（`release: {"asked": [387], "nothing_held": [], "released": [], "unconfirmed": [387]}`、`input_release_failed: true`、退出码 14）。⇒ **`ConnectionResetError` 说明是客户端那一侧把套接字重置的，不是 Core 关掉自己的监听**，而这已是当前工件能答到的边界；至于那个 JVM 为什么走，要的是桥/客户端侧的下一次观测，不是这里再猜。
2. 第 5 步的 `GUI_CONFLICT` 暴露的是改线缺口：连续两次 `craft_take_result` 之后物品栏仍开着，心的下一个 `break_seen_block` 因此被桥按契约拒掉（`actions_refused: 8`），而它没有"先关界面"这一步可试——`SKILL_OFFER` 里没有 `close_screen`。这属 S3 的改线范围，与第 13 条的放置技能各是一格，都不在本档声明之内。

16. **合成现在是"按产物表达意图、按目录解析配方"，不再是写死的动作序列（2026-09-30，活体）。** 技能层早就参数化了（`craft` / `craft_take_result` 收 recipe id 与材料表，本身不认识"木"），写死的其实是**配方知识**：它此前只存在于 `player_mind.py` 的 `CRAFT_CHAIN` 表和技能计划里逐条手抄的 `recipe_id` + `materials` + `product_id`。现在配方知识有一处数据定义——`src/minekin_core/domain/recipe_catalog.py`（它就是 `docs/recipe-knowledge-gui-contract.md` 三分对象里的第一类：公开知识；不是账号配方书，也不是任何确认）——计划条目可以只写 `{"skill": "craft_take_result", "product": "minecraft:oak_planks"}`，`skill_plan.py` 从目录取回那三件再交给同一个技能；旧写法照旧解析（已提交的计划本身就是证据，不为新写法重写历史）。三种不可能各自有一个名字，不靠空结果让调用方猜：`CRAFT_RECIPE_UNAVAILABLE`（目录里没有这个产物）、`CRAFT_GRID_TOO_SMALL`（要开的网格装不下这个形状，检查在背包之前——对着装不下的形状多采木头是错的反应）、`CRAFT_MATERIALS_MISSING`（配方已知也放得下，这只包付不起）。前两个在解析期就具名拒止，模型编不出配方：它自造的 recipe id 到客户端只会是 `REFUSED_GUI_RECIPE_UNKNOWN`，它自造的材料表会花掉错的物品。`CRAFT_CHAIN` 同时降格为**演示夹具**——它的用途只剩"给 demo 一条走得完的顺序"，不再是产品的配方知识，真正的目标选择接替它时不需要新配方代码。**活体复用已量到**（六之四，run `461bbbf77d884b12a6d1cb814e8901db`）：只写产物的木板那一步 CONFIRMED（同步 revision 986→1019，§4 判据），而客户端日志里出现了 `bridge clicked recipe minecraft:crafting_table (craftAll=false)`——工作台这一产物不出现在任何夹具或旧计划里，它的 id 与材料表只可能来自目录这一处。**这一条不声明工作台已合成**：那一笔点击之后的判定停在第 17 条那一格。

17. **GUI 点击之后观测流会整段安静，这是历次 `craft UNKNOWN` 现在最像的真实成因（2026-09-30，两次运行同一形状）。** 六之四那两发都不是配方问题也不是材料问题：run `d7fafc30…` 的木板步在 `recipe_fill` 点击之后拿不到比 tick 1064 更新的一帧；run `461bbbf7…` 更干净——第 4 步 CONFIRMED 收在 1019，第 5 步（工作台）从 `pre` 到放弃都是 1019，`newest_checked_tick == pre_tick` 按第 9 条的读法就是**一帧都没到 Core**，而客户端自己的日志在同一时刻还在往前写（12:04:24 槽位点击、12:04:25 配方点击），`crash-reports/` 空、`stderr.log` 空 ⇒ 渲染线程活着，报帧的那条路没活着。同一格还有第二处证据：这两发的停止读数都是 `input_release_failed: true`（逐字 `unconfirmed: [246]` / `unconfirmed: [242]`，harness 只能把 JVM `terminated`），因为释放要走的就是这条已经安静的频道——键没有留在世界上（桥日志里每次 `pressed` 都配了 `released`），悬着的只有那个还开着的物品栏界面。**答不出的部分照原样登记**：界面开着时观测为什么不再报，要到桥/客户端侧的下一次观测才答得出，而 bridge-1201 是已封字节，本档不猜也不动。**这一条的成因在下一格被换了名字**（第 18 条，run `514bb121…`）：新增的读数计数排除了"帧到了却被按 replay 丢掉"这一支，而那一发的客户端日志**没有**继续往前写——所以本节上一句"渲染线程活着"只对 `461bbbf7…` 成立，不是两发的共同事实。

`goal_met: false`、`model_enabled: false / model_calls: 0`、`perceived_information_class: PLAYER_EQUIVALENT`、`cognition_refusals: {MANAGEMENT_ONLY_DTO: 4}`、`entities_admitted: 13`、`snapshots_admitted: 1`、`actions_applied: 6`。这一档声明的是：收尾名已经能从台账读出来，且一次频道丢失被诚实记成 `CONTROL_CHANNEL_LOST` 加一条失败的释放读数，而不是被折成成功。

18. **观测流为什么安静，现在有了名字：客户端在那一刻离开了世界，而 JVM 还活着（2026-09-30，run `514bb121303d493394101126c07858e3`，读数见六之五）。** 第 17 条留的那一问有两个候选，Core 一侧先各补了一个计数再跑：`WorldObservationStore` 把"到了但不比手上那帧新"从静默 `return False` 变成 `stale_tick_dropped` + `newest_stale_tick`，`SessionRun` 文档长出 `world_observations`（store 自己的台账）与 `world_observations_unheld`（帧到了却没人接）。那一发读回的是 `{"admitted": 16, "refused": 0, "refusal_reasons": {}, "stale_tick_dropped": 0, "newest_stale_tick": null, "newest_admitted_tick": 1108}`——**没有一帧被按 replay 丢掉，也没有一帧被完整性规则拒掉；1108 之后 store 什么都没收到**。"桥持续报同一 tick、store 静默丢帧"这一支由此排除，剩下的是客户端不再报帧。客户端日志给了同一时刻的另一半：最后一行是 `12:36:57.047`（`Loaded 16 advancements`，logger `net.minecraft.class_163`）在它上一条点击 `bridge clicked slot 0 … QUICK_MOVE`（`12:36:57.026`）之后 21 ms，而受控服务器同一秒写 `Kin lost connection: Disconnected` + `Kin left the game`；Core 的第二笔 `recipe_fill` 是 `12:36:57.5+` 才发的，客户端日志里**没有对应的 `bridge clicked recipe` 行** ⇒ 那一笔根本没被应用，第 5 步的 `NO_CONFIRMING_OBSERVATION` 是后果不是成因。进程并没有走：`session stop` 的 `terminated: [251]` 按 `adapters/launcher/orphans.py` 的规矩只列**探针说还活着**的 pid（已经没了的会被跳过、两个列表都不进），`left_alone: [357]` 是那台不归本会话管的受控服务器。于是这三份字节合起来说的是：进程活着、世界已经离开、渲染线程不再产出任何一行日志——报帧的 `END_CLIENT_TICK`、应用 GUI 点击的线程、桥那句"这次断线要分类"的日志（`bridge observed a disconnect…` / `bridge classified the disconnect as…`，一条都没出现）要走的全是同一条线程。**还答不出的**：客户端为什么恰在第一次取结果之后 21 ms 离开世界。`crash-reports/` 空、`/data` 下无 `hs_err*` 也无 `.hprof`、`stderr.log` 零字节、`logs/telemetry/` 空——现有工件里没有那次离开的理由，而要拿到它得在桥的网络线程上多看一眼，那是已封字节。本档到此为止把它记成"客户端侧的一次离开"，不再记成"Core 的观测通道丢了帧"。**这一条里"进程并没有走"那半句在下一格被更正**（第 19、20 条，run `4543d50a…` 的整张进程表）。

19. **关界面这一步在活体上站住了，而"第二次合成才出事"这个假设被时间线否证（2026-09-30，同一冷卷 `minekin-local-demo2` 上七发 run，逐字读数见六之六）。** 三件事各自有了字节。其一，`close_screen` 三次由**更晚的一帧**确认：run `354415bb…` 22724→22735、`8beea122…` 1394→1404、`2b88fc02…` 1080→1091，三发的 details 都是 `pre_sync_id "0"` → `newest_sync_id ""`、`screen_open "false"`（客户端给自己的合成界面报的是**空** `screen_id` 配 `sync_id 0`，所以这一对字段才进 details）；同一批字节也划掉了"关屏把通道弄安静了"这一支——关屏之后 store 仍在收帧（`354415bb…` 里重开界面和那笔配方点击都是在这之后被应用的）。其二，**UNKNOWN 与第几步无关**：`e23da02e…` 停在第 4 步（木板）的第一笔 `recipe_fill`，`4543d50a…` 同样停在第 4 步，`8beea122…` 与 `2b88fc02…` 停在第 6 步的 `SCREEN_NOT_CONFIRMED`（`clicks ""`、`gui_open false`，即重开界面的那一下没人接），`a44fcbd7…` 停在走路里的 `CONTROL_CHANNEL_LOST`，`47f72e29…` 停在 `collect_dropped` 的 `NO_SEEN_DROP`。把七发对在一起的是服务器那三行：每发都是 `joined the game` 之后 **5–14 秒**写 `Kin lost connection: Disconnected` + `left the game`（run-1…run-7 分别 11/10/5/14/11/10/10 秒），而那一刻在跑哪一步七发各不相同 ⇒ 成因的形状是"**客户端在进入世界之后一小段时间就不在了**"，不是"按产物合成这条路本身走不通"，也不是工作台或木棍这两个产物里的任何一个。其三，按"同步检查输入释放"的要求把七发的释放读数都留下：六发 `input_release_failed: true` 且 `release.unconfirmed: [pid]`，唯一一发 `false` 的是 `47f72e29…`（`{"asked": [248], "released": [248], "unconfirmed": []}`，客户端日志 `bridge released 0 input(s) after CORE_REQUEST (EXPLICIT)`）——它是提前停在 `NO_SEEN_DROP` 那一发，也就是唯一一发 Core 还来得及道别的。**这一发要说清安全边界**：`a44fcbd7…` 的桥日志里最后一次 `bridge pressed move.forward` **没有**配对的 `released` 行，也就是说"每次 pressed 都配了 released"只对之前那几发成立；那一发的键是随那个已经不在世界里的客户端一起没的，Core 只能记 `unconfirmed: [249]`。**不声明**：木镐没有取得（`goal_met: false`，七发都是），第 6 步的工作台/木棍没有一发拿到 CONFIRMED，且"客户端为什么离开世界"仍未答出。

20. **"进程并没有走"这半句现在由 Core 自己回答，而它给的是相反的答案（2026-09-30，run `8203e46e8fa947ffb82281678a39e768`，逐字读数见六之七）。** 技能步的等待不再只问世界：`application/world_skills.py` 的 `_wait_until` 把"还有没有子进程"和"有没有更晚的一帧"放在同一次等待里跑（`_outlive_client`，每 `CLIENT_EXIT_POLL_S = 0.25` 秒问一次 launcher 自己的 `supervisor.poll`），客户端一没，这一步立刻按名字停下——`reason: CLIENT_EXITED`、`details.exit_code`，不再烧完那 150 秒；发令之前子进程就已经没了也同样具名停下（那一笔还是发出去，只是不等人）。计划层 `skill_plan.perform_skill` 把这种离开收成 `UNKNOWN` 而不是 `FAILED`：命令已经出门，世界在那台 JVM 倒下之前可能已经变过，这是这一发读不出来的事实。自主循环 `autonomous_play` 据此把整次运行按同一个名字停住（`stop_reason: CLIENT_EXITED`，`stop_detail` 带退出码）。**于是第 18 条那两个候选第一次被分开**：那一发的第 5 步在几秒之内拿到 `{"skill":"close_screen","result":"UNKNOWN","reason":"CLIENT_EXITED","details":{"exit_code":"143"},"action_id":""}`、`skill_stop: close_screen`，而同一发的 `session stop` 说 `terminated: [253]`——同一个 pid，一份读数说它已经退了，另一份说还活着并且由它把它停掉。**这两份不能同时是事实，本档不选边，只登记为什么选不出来**：`adapters/launcher/orphans.py` 的止路在发信号之前只比命令行的摘要（`prove_process_identity` 读 `/proc/<pid>/cmdline`），marker 里记了 `started_at` 却不比对，所以"名字对得上"和"还是那一个进程"是两回事；这也是 `left_alone: [438, 335]` 那两行能出现的同一个机制（前几发的 pid 号在这台新容器里被 reuse，摘要不配 ⇒ 不动手，这是设计在生效）。**这一条同时把 18/19 两条的时间形状更正一次**：这一发不是"进入世界之后一小段时间就没了"——`started_at 15:03:39`（JVM）、服务器 `15:03:58 Kin joined the game`、`15:04:08 Kin lost connection: Disconnected`，而客户端日志的**最后一行**就是 `15:04:08 bridge applied screen … (SCREEN_CONTROL_CLOSE)`，Core 读到的退出码 143 是 JVM 收到 SIGTERM 之后自己 `exit(143)` 的那一个形状（不是 137，`memory.events` 那几发的 `oom_kill` 都是 0）。**新的前沿因此换了名字**：这一发 `outcome: BRIDGE_LOST` 在 `cli/session_runtime.py:506` 只有一个来源——观测 reader 抛了 `IpcProtocolError`——而 CLI 的退出码 14 就是 `bootstrap.py` 给的 `ExitCode.IPC_PROTOCOL`。所以结束的形状是"控制频道上先有一次契约破坏，然后会话收尾，然后那台客户端不在了"，而不是"客户端自己走掉把频道弄安静"。**答不出的那半句也有了具体的形状**：`IpcProtocolError` 在 `adapters/bridge/ipc.py` 有九处抛出点、每一处都带自己那句消息，可这句消息不进 run 文档，于是下一次活体还是只能靠三份日志对齐。**下一格因此不碰已封字节**：把那次契约破坏的理由名记进 run 文档（Core 侧、可单测），跑一发就知道是哪一条规矩被破。另外两处 Core 侧的诚实缺口一并登记：其一，`perform_skill` 的 `CLIENT_EXITED` 行带 `action_id: ""`，而那笔关屏的 id 是 Core 自己造的、已经发出去并被应用了（`81132da822274377b09b9cdb23e32892`）——行里丢了一个本可知道的事实；其二，`BridgeIpcWorker.applyScreen` 的顺序是先 `view.closeScreen()` 再 `publishResult(ACCEPTED)` 最后打那行日志，所以那行日志证明 `client.setScreen(null)` **返回了**，而 Core 仍只能判 `UNKNOWN`（这是规则在生效，不是缺陷）。**输入释放这一发是干净的那一种**：客户端日志里 `mine.attack` 与 `move.forward` 各 pressed 1 / released 1，`unconfirmed: [253]` 只是确认回不来，没有键悬在世界上。**采样账**：`.tmp/census-v13.log` 那份宿主机 `/proc/stat` 采样按构造就读不出被探的那个 pid（它不打印 pid，只数全机进程 churn，且从 pass 7 起容器已经不在了，六行之后全是 `No such container`），所以 v13 不再补，改由 Core 自己的 poll 作答。**不声明**：木镐仍未取得（第 13 条那一格没动），run-9 那一发（会话 `fee8b3c8…`）没有留下 run 文档，本档按"不是成一次运行"记、不当证据。

21. **第 20 条登记的两处具名诚实缺口各自有了一发读数，而合起来它们改写了"频道先坏、客户端后走"那句次序（2026-09-30，run `ec5330b5a7c74258a2bd20476e99ea0d`（server run 目录 `run-11`）与 run `dbc65e316e534364add732307926c020`（`run-12`，逐字读数见六之八）。** 其一，run 文档现在带 `bridge_lost_reason`——那句理由名是 Core 自己写的（`adapters/bridge/ipc.py` 九个抛出点各自一句固定的话，不含对端文本），两发读回的都是**同一句** `"IPC channel closed before a complete frame header"`。这一句把第 20 条末段那个推断更正了：那一支是**在帧边界上读到套接字关闭**时抛的，也就是说这几发里的"契约破坏"就是那台客户端离开的那一刻，不是它的前因——`BRIDGE_LOST` 与 `CLIENT_EXITED` 在这两发里是同一件事的两个名字，而不是链条上的两段。第 20 条那句"新的前沿因此换了名字"到此答完；仍然答不出的那句换了回去：**那个 JVM 为什么会收到 SIGTERM**（143 = 128+15），而它不在 Core 现有字节能答的范围里——要它得看 bridge-1201 的网络线程侧，那是已封字节，是主控的决定（B 分支），不是本卡继续猜的理由。其二，`CLIENT_EXITED` 那一行现在带上在飞的那笔 id：run-12 的第 5 步是 `{"skill":"close_screen","result":"UNKNOWN","reason":"CLIENT_EXITED","action_id":"bcb5aafb3f9241c99d1a1d354f4de909","details":{"exit_code":"143"}}`，而这个 id 在**客户端自己的日志里出现 0 次**（同一份日志的最后一行是 `16:04:34` 的 `Loaded 16 advancements`，它的上一条就是第 4 步那笔 `63aab7c5…` 的配方与槽位点击）⇒ 那一笔关屏**从 Core 发出去了、客户端没有应用它**。在把 id 带出来之前，那一行是空的，这一个问题根本问不出来——这就是这一格的全部用途。发令之前子进程就已经没了的那一支仍写空 id（`skill_plan.perform_skill` 的 pre-send 路径），两种形状各由一条单测钉住（`tests/unit/test_world_skills.py::test_the_exit_names_the_ask_that_was_in_flight_when_the_client_went`、`tests/unit/test_skill_plan.py` 那一对）。**输入释放这一发是"没有键悬着"的那一种**：`move.forward` pressed 2 / released 2、`mine.attack` pressed 1 / released 1，日志里最后一条 applied 是 `holding []`，`unconfirmed: [243]` 只说明确认回不来；悬在世界上的只有那个还开着的物品栏界面。**同一处矛盾第四次复现**：`supervisor.poll` 给 143（步内），同一发的 `session stop` 说 `terminated: [243]`（还活着且由它把它停掉），成因仍是第 20 条那一格——`orphans.py` 的止路在发信号之前只比命令行摘要，marker 里的 `started_at` 从不比对。这一发还顺带量到那机制的另一半：`left_alone: [438, 263, 248, 249, 253]`——前三发留在卷上的 marker 让每一次停止都多探四个 pid，而它们在新容器里命令行摘要不配 ⇒ 不动手（设计在生效，但"marker 会一发的接一发的留在卷上、每次停止都多探几个 pid"这一格本档登记出来，不改写）。**不声明**：木镐仍未取得（第 13 条那一格没动），`close_screen` 仍不在 `player_mind.SKILL_OFFER` 里（第 19 条那格仍归 S3），B 分支仍归主控。

22. **里程碑那一串合成不再是"谁手敲的一张表"，而是配方表算出来的顺序，活体读回的就是那一串（2026-09-30，run `78a12962a7b142aabe68718cf99474ef`，server run 目录 `run-13`，逐字读数见六之九）。** 这一格换掉的是 mind 自己：`CRAFT_CHAIN` 与 `CraftStage` 从产品路径上退下来（那串手写顺序本来就是 Demo 夹具，真正在跑的那份顺序一直住在 `examples/skill-plan-*.json` 里、从没被 mind 读过），`player_mind.GOAL_BUILD_PLAN` 改由 `domain/recipe_catalog.py` 的 `build_plan` 按配方推出来 ⇒ "想要一个产物"从此是一个 product id 加一个数量，不是一张有人抄过的表。**那条算术被当场量到**：木镐要 5 块木板而不是旧夹具写的 3，因为那把镐自己吃的木棍那一批还要再花两块木板（`3 planks + 2 sticks` 与 `2 planks → 4 sticks` 两行乘出来的），而这种错在世界上没有任何东西会发现。**活体上的切换**：第 3 步的参数是 `minecraft:oak_planks`（CONFIRMED，tick 1010→1044）、第 4 步换成了 `minecraft:stick`（`UNKNOWN`/`CLIENT_EXITED`，结果帧 1055）——两笔都不是计划文件写死的，是 mind 从当时那一帧背包算出来再交给 `craft_take_result` 的。第 3→4 那一换本身就是 netting 的读数：一批木板（yield 4）之后需求就清了 ⇒ 这一发进这一格时背包并不空（harness 自己那句 `the Kin root kin-local-demo already has a store on minekin-local-demo2 -- running on that filled store` 说的是同一件事），若在空背包上 5>4 会再要一批木板——那一支目前只有单测钉住（`tests/unit/test_autonomous_play.py::test_the_loop_walks_the_plan_as_far_as_the_grid_it_can_open`），**活体还没读到**。取木→拾取那一段在同一条新路径上又各确认了一次（`break_seen_block` 911→988、`collect_dropped` 988→1010）。**决策来源记清**：`decision_source: local_reflection`、`model_enabled: false`、`model_refusal: MODEL_NOT_CONFIGURED`、`model_calls: 0` ⇒ 这一发没有联系任何付费端点，走的正是无凭据那一条路。**第 21 条那两种形状在这一发上分开**：在飞的那笔 id `0843e155a7624d3ea97cc1250420d7b5` 在客户端日志里出现 **2 次**（`bridge clicked recipe minecraft:stick in …` 与 `bridge clicked slot 0 … QUICK_MOVE` 各一次），而 run-12 那笔关屏出现 0 次 ⇒ "发出去了"与"客户端应用了"从此是可分辨的两个事实，这一发是**发了且应用了、只是那一帧之后那台 JVM 不在了**。**输入释放是配对的那一种**：`move.forward` pressed 1 / released 1、`mine.attack` pressed 1 / released 1，最后一条 applied 写 `holding []`，`unconfirmed: [240]` 只说明确认回不来。**同一处矛盾第五次复现**：`session stop` 说 `terminated: [240]` 而步内读的是 143，本档按第 20 条原样登记、不选边；`left_alone: [438, 341, 243, 249, 253]` 是那四个（这次多了一个 `341`）早期 marker 再各探一遍。**不声明**：5 块木板这一需求未在活体上读到（这一发停在第 4 步），木镐仍未取得（第 13 条那一格没动），3×3 摆格与 B 分支仍归主控，`close_screen` 仍不在 `player_mind.SKILL_OFFER` 里。

23. **改线那一格现在按"更晚的一帧能不能把它说反"分道，而收尾行把那个名字带到面板上（2026-09-30，run `ced217a0d068418385a439084e3a47ca`，server run 目录 `run-14`，逐字读数见六之十）。** 三个具名前提在 `player_mind.record_result` 里不再走同一条路：`CRAFT_MATERIALS_MISSING` 是**能更线的**（背包空不空由世界说，往后一帧完全可能把它讲反），于是不烧任何重试额度（`attempts` 保持空），下一次直接问"有没有掉在地上的东西可捡"，而合成这一步本身留在候选里等下一批材料；`CRAFT_GRID_TOO_SMALL` 与 `CRAFT_RECIPE_UNAVAILABLE` 是**死路**（没有任何一帧能让 2×2 装下 3×3、也没有任何一帧能让目录里不存在的配方存在出来），第一句就把它排除。顺带补上归因的一处洞：`CRAFT_RECIPE_UNAVAILABLE` 原先不在 `_NOT_IMPLEMENTED_REASONS` 里，会被折成 `ACTION_NOT_EFFECTIVE`，读起来像"试过了没成"而不是"这张表里没有这个东西"。那个名字同名穿过四张面：`mind.last_precondition` → mind 段（run 文档）→ 台账 `AutonomousRunHalted` 的第七个具名成员 → gateway 的 allowlist（契约 §11），空串按 §10 既有的规矩整格省略；确认一步把它清空。**活体读到的那一格是省略那一格**：这一发的收尾行 raw payload 七个成员全在，`last_precondition` 为 `""`、`excluded_skills` 为 `[]`，面板字节因此是 `goal=hold_a_wooden_pickaxe, stop_reason=CLIENT_EXITED, error=143, steps=5, confirmed=4`，两格都没有渲染成 `=` 或 `[]`。**这一格因此只判成"更线路径的代码与契约完成"，不判成活体完成**：更线路径上的具名失败（`CRAFT_MATERIALS_MISSING` 从世界上回来）在这一发以及此前任何一发里都没有读到过——历发活体上的失败名字一直是 `CLIENT_EXITED`。另两处按实登记、不改写：其一，`error` 那一格代码路子上是 `halted.stop_detail` 原样投影，所以它在 `CONTROL_CHANNEL_LOST` 上是异常类名（六之三那个 `ConnectionResetError`）、在 `CLIENT_EXITED` 上是那台 JVM 的终止信号（这一发的 `143`），§10 那句"其余收尾为空串"说的是"没有 detail 的收尾"，本条按字节更正；其二，输入释放这一发又回到 `input_release_failed: true` 那一形状（`{"asked": [237], "released": [], "unconfirmed": [237]}`，而 `terminated: [237]` 是第 20 条那处矛盾的第六次复现），第 6 条那句"这一格已经量到闭环"只对 `NO_FEASIBLE_SKILL` 那种自己停下来的收尾成立，客户端先没的那一发确认永远回不来。**不声明**：木镐仍未取得（`goal_met: false`，第 13 条那一格没动），3×3 摆格、B 分支与 `close_screen` 进 `SKILL_OFFER` 仍归主控。

24. **固定木镐那一串目标从产品路径上换了下来，而"模型提出 skill + arguments"那一格在活体上读到了（2026-10-01，run `785936d2ffca4461ae11ea444c5d6643`，server run 目录 `run-17`，逐字读数见六之十一）。** 两面新的面把职责分开了：`domain/skill_parameters.py` 把"每个行为吃哪些参数"写成数据（种类、必带与否、上下界，加上 `MODEL_ARGUMENTS_UNKNOWN / MODEL_ARGUMENTS_MISSING / MODEL_ARGUMENTS_INVALID` 三个拒止名），`domain/goal_spec.py` 把里程碑写成一个 product id 加一个数量加一个来源物加一个朝向，从 `MINEKIN_GOAL_PRODUCT / QUANTITY / SOURCE_ITEM / DIRECTION` 读——**Core 不再持有任一默认产物**：环境不给就是"没有常驻目标的 Kin"（这是支持的形状，不是坏掉的），给了而拼错按 `GOAL_NOT_CONFIGURED` 拒在配置阶段。请求侧带上这次读数的真实摘要（`inventory` 计数、`craft_options`、`dropped_items`、`selected_slot`、瞄准的方块、生命与食物，以及里程碑那一格）和只就可行集声明的 `skill_parameters`；答复侧带 `arguments`。`PlayerMind._call_for` 是询问词汇变成计划词汇的那唯一一处，校验不过就按那个名字退回本地反思并把 `model_refusal` 记进文档，绝不换一个本地产物顶上。**木镐那一串现在只住在两处夹具里**：`demo.sh` 的四个 `MINEKIN_DEMO_GOAL_*` 旋钮（用的是 `${VAR-default}` 而不是带冒号那一种，所以 `MINEKIN_DEMO_GOAL_PRODUCT=` 空是一句真问——"给我一个无常驻目标的 Kin"；这一格不再只是注释：`tests/contract/test_runner_scripts.py` 把 `demo.sh` 那四行逐字抽出来在 bash 里驱动，unset 得到夹具默认、命名得到所报的 `minecraft:stick`/`16`、命名而空得到空串，而冒号形状在最后那一格会打印出木镐，因此这一断言不是空的），以及单测的 fixture。`application/player_mind.py`、`domain/goal_spec.py`、`domain/skill_parameters.py`、`adapters/model/openai_compatible.py` 四个文件里 `oak_planks / oak_log / stick / wooden_pickaxe / crafting_table` 五个名字一次都不出现，`src/` 全树除 `domain/recipe_catalog.py` 那四行配方表外只剩两处注释文字提到 item id（`model_access.py:509`、`perception.py:351`）；`tests/unit/test_goal_spec.py` 与 `tests/unit/test_skill_parameters.py` 各带一枚源码扫描钉住这一句，配方表一格未加。**复用**在两层都量到：同一枚循环对 `minecraft:stick` 里程碑与对"无里程碑"各走一遍（`tests/unit/test_autonomous_play.py` 的新格，其中 `test_the_loop_walks_the_plan_as_far_as_the_grid_it_can_open` 现在按 `CRAFT_GRID_TOO_SMALL` 那一个名字停下而不是耗到步数上限），活的那一发则把 `{"target_item": "minecraft:oak_planks", "quantity": 1}`（CONFIRMED 910→943）与 `{"target_item": "minecraft:stick", "quantity": 1}` 两笔从 socket 那头收进来，四步全部 `decision_source: model`。**本课先量的那一格要记下来**：前一发 run `31c3a430e5ad46ee8ce4689e72c3b2fe`（`run-16`）每一步都是 `model_refusal: PROVIDER_STATUS`、`model_calls: 5`，成因是本机脚本把 base URL 写成 `http://127.0.0.1:8818/v1`，而 provider 自己拼 `/chat/completions`（`openai_compatible.py:360`），harness 端点只对这一个路径答话、其余一律 404 ⇒ 拒止名老实记下了这次错配，也说明"接线通没通"这一问在活体上必须先去掉 `/v1` 再问；这一句已写进 `tools/run_fake_model_endpoint.py` 的模块说明。**不声明**：`goal_met: false`，第 4 步那笔在飞的 `craft minecraft:stick` 停在 `UNKNOWN / CLIENT_EXITED`（`stop_detail: "143"`、`outcome: BRIDGE_LOST`、`bridge_lost_reason: "IPC channel closed before a complete frame header"`），而客户端日志里那笔的 id 出现 **2 次**（`bridge clicked recipe minecraft:stick in ed3ef888…`、`bridge clicked slot 0 in ed3ef888…`）⇒ 那是"发了且应用了、只是那一帧之后没有确认读数回来"，第 20/21 条那面墙的第八次复现，判据与已封字节都不在本卡范围内；`input_release_failed: true` 同旧形状（`{"asked": [238], "unconfirmed": [238]}`）。按主控方向，**不再因"木镐尚未取得"追加专用业务步骤**。另具名登记一处可答而未答：模型的 `arguments` 进了 run 文档的 `steps[i].intent.arguments` 与 mind 段的 `executing_arguments`，但没有进台账 `SkillStepRecorded` / `AutonomousRunHalted` 那一行（那一行的八个成员逐字见六之十一）——面板因此说不出"模型当时要的是哪个产物、要几个"，而加那一名是证据格式决定，归主控。

## 六之四、按产物合成读到的那两发（2026-09-30，runs `d7fafc30bbec4231ba1b52a30b7be6a8` 与 `461bbbf77d884b12a6d1cb814e8901db`）
同一枚热卷（同卷同 Kin 根 `kin-local-demo`，第二发是 server run 目录 `run-7` 之后的下一次会话），计划换成第 16 条那份只写产物的：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_SKILL_PLAN=/src/examples/skill-plan-craft-by-product.json \
  bash test-orchestrator/runner/demo.sh --skills --again
```

计划五条：`turn_to` → `break_seen_block` → `collect_dropped` → `{"skill":"craft_take_result","product":"minecraft:oak_planks"}` → `{"skill":"craft_take_result","product":"minecraft:crafting_table"}`。两条合成条目**没有** `recipe_id`、也没有 `materials`——它们由目录解析出来，run 文档 `skill_plan` 那一格仍是 `["turn_to","break_seen_block","collect_dropped","craft_take_result","craft_take_result"]`，技能层看不出意图换了写法。

第一发 `d7fafc30…`（11:59:55 起，12:00:29 收）：

| 步 | 技能 | 结果 | `details` | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- | --- |
| 1 | turn_to | CONFIRMED | — | tick=911 → 922 |
| 2 | break_seen_block | CONFIRMED | — | 922 → 987 |
| 3 | collect_dropped | CONFIRMED | `steps=4` | 987 → 1053 |
| 4 | craft_take_result（木板） | UNKNOWN / `NO_CONFIRMING_OBSERVATION` | `clicks=recipe_fill`、`craft_all=false`、`gui_open=true`、revision 1053→1064 | 1053 → **`post_tick: null`** |

`actions_applied: 10`、`actions_refused: 7`、`input_release_failed: true`（逐字 `{"asked": [246], "unconfirmed": [246], "terminated": [246], "left_alone": []}`）、`outcome: BRIDGE_LOST`、退出码 14。

第二发 `461bbbf7…`（12:03:57 起，12:04:30 收）在同一枚卷上把木板那一步走成了 CONFIRMED，并走到了第二配方：

| 步 | 技能 | 结果 | `details` | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- | --- |
| 1 | turn_to | CONFIRMED | — | tick=871 → 888 |
| 2 | break_seen_block | CONFIRMED | — | 888 → 953 |
| 3 | collect_dropped | CONFIRMED | `steps=1` | 953 → 986 |
| 4 | craft_take_result（**按产物**的木板） | CONFIRMED | `clicks=recipe_fill+result_quick_move`、`craft_all=false`、`gui_open=true`、revision 986→1019 | 986 → 1019 |
| 5 | craft_take_result（**按产物**的工作台） | UNKNOWN / `NO_CONFIRMING_OBSERVATION` | `clicks=recipe_fill`、`craft_all=false`、`gui_open=true`、`pre_inventory_revision = newest_inventory_revision = 1019` | 1019 → **`post_tick: null`** |

`actions_applied: 4`、`actions_refused: 6`、`input_release_failed: true`（逐字 `{"asked": [242], "unconfirmed": [242], "terminated": [242], "left_alone": [246]}`）、`outcome: BRIDGE_LOST`、退出码 14。

客户端自己那一侧的日志（只读卷上 `…/logs/latest.log` 末行，第二发）逐字是：

```text
[12:04:23] bridge tapped screen.inventory
[12:04:23] bridge applied screen bfa60c96… (SCREEN_CONTROL_OPEN_INVENTORY)
[12:04:23] bridge clicked recipe minecraft:oak_planks (craftAll=false)
[12:04:24] bridge clicked slot 0 (button 1, SLOT_CLICK_MODE_QUICK_MOVE)
[12:04:24] Loaded 16 advancements
[12:04:25] bridge clicked recipe minecraft:crafting_table (craftAll=false)
```

这两发合起来能声明的与不能声明的：**能声明**的是第 16 条那半——只写产物的意图经目录解析成真实点击，木板那一步由同步 revision 986→1019 事后读数确认（不是桥自报），而 `minecraft:crafting_table` 这个在任何夹具里都没出现过的 recipe id 被客户端接受并点击（配方书侧没有具名拒止它）。**不能声明**的是工作台已经合成：第 5 步从依据帧到放弃一帧未更新（`newest_checked_tick == pre_tick == 1019`），按第 9 条的读法是通道安静而非"帧到了没确认"，所以这一笔的判定停在第 17 条登记的那一格，`goal_met: false`，本档不把它读成成功。第一发的木板同形：它在 `recipe_fill` 之后也再没等到新帧，同一技能在第二发是 CONFIRMED ⇒ 这一格不是恒败，也不是恒过。

## 六之五、那份新计数第一次改变结论的那一发（2026-09-30，run `514bb121303d493394101126c07858e3`）

同一枚热卷、同一份只写产物的计划（server run 目录 `run-9`，会话 `058d3f4d89b84567ab6d755d4c743b91`，12:36:27 起、12:37:02 收）。这一档要回答的是第 17 条留下的那一问：**GUI 点击之后那一整段安静，是"帧到了 Core 却被丢掉"，还是"根本没有帧"**。为此 Core 先各补了一个计数（第 18 条），再用同一条命令跑回来。

| 步 | 技能 | 结果 | `details` | 依据的读数 → 核对的读数 |
| --- | --- | --- | --- | --- |
| 1 | turn_to | CONFIRMED | — | tick=965 → 976 |
| 2 | break_seen_block | CONFIRMED | — | 976 → 1042 |
| 3 | collect_dropped | CONFIRMED | `steps=1` | 1042 → 1075 |
| 4 | craft_take_result（**按产物**的木板） | CONFIRMED | `clicks=recipe_fill+result_quick_move`、`craft_all=false`、`gui_open=true`、revision 1075→1108 | 1075 → 1108 |
| 5 | craft_take_result（**按产物**的工作台） | UNKNOWN / `NO_CONFIRMING_OBSERVATION` | `clicks=recipe_fill`、`gui_open=true`、`pre_inventory_revision = newest_inventory_revision = 1108` | 1108 → **`post_tick: null`** |

run 文档里那一格新字节，逐字：

```text
"world_observations": {"admitted": 16, "newest_admitted_tick": 1108, "newest_stale_tick": null,
                       "refusal_reasons": {}, "refused": 0, "stale_tick_dropped": 0},
"world_observations_unheld": 0
```

`stale_tick_dropped: 0` 与 `refused: 0` 一起把"桥持续报同一 tick、store 按 replay 静默丢掉"那一支划掉了：1108 之后 store 什么都没收到。`world_observations_unheld: 0` 说明接线是通的（`events_ignored: 0` 同向）。其余计数：`actions_applied: 4`、`actions_refused: 5`、`snapshots_admitted: 1`、`entities_admitted: 1`、`entities_rejected: 1`、`cognition_refusals: {MANAGEMENT_ONLY_DTO: 2}`、`perceived_information_class: PLAYER_EQUIVALENT`、`input_release_failed: true`、`outcome: BRIDGE_LOST`、退出码 14。

三份字节把时刻对到了一起（都是同一卷上的字节）：

```text
客户端 logs/latest.log 末两行
[12:36:57] bridge clicked slot 0 (button 1, SLOT_CLICK_MODE_QUICK_MOVE)
[12:36:57] Loaded 16 advancements            ← logger=net.minecraft.class_163, 1790771817047

受控服务器 /data/server-runs/run-9/logs/latest.log
[12:36:57] Kin lost connection: Disconnected
[12:36:57] Kin left the game
[12:36:58…12:37:03] No entity was found       ← 服务器还在跑，世界里已经没有人

台账（本会话）
12:36:57.523877 SkillStepRecorded  第4步 CONFIRMED
12:37:02.552048 SkillStepRecorded  第5步 UNKNOWN / NO_CONFIRMING_OBSERVATION
12:37:02.566549 SessionStateTransitioned PLAYABLE→FAILED
12:37:02.607889 SessionInterrupted {"outcome":"BRIDGE_LOST"}
```

客户端最后一行的毫秒是 `12:36:57.047`，在它前一条点击（`1790771817026`）之后 21 ms；Core 的第 5 步是在 `12:36:57.52` 记下 CONFIRMED 之后才发出那笔 `recipe_fill` 的。客户端日志里**没有** `bridge clicked recipe minecraft:crafting_table` 这一行——那一笔点击没有被应用。合起来：第 5 步的 UNKNOWN 不是"点击生效了但没有读数"，而是**发出点击的那一侧已经没有人接了**。

进程仍然活着：`session stop` 逐字 `{"terminated": [251], "left_alone": [357], "release": {"asked": [251], "nothing_held": [], "released": [], "unconfirmed": [251]}}`，而 `adapters/launcher/orphans.py` 的规格里 `terminated` 只列探针说还活着的 pid（已经没了的那个不进任何列表），`left_alone: [357]` 是那台不归本会话管的受控服务器。⇒ 那一刻是**进程活着、世界已离开、渲染线程不再产出任何一行日志**。报帧的 `END_CLIENT_TICK`、应用 GUI 点击的循环、桥自己那句"这次断线要分类"的日志（`bridge observed a disconnect…` / `bridge classified the disconnect as…`，整卷一条都没出现）要走的都是这条线程，这与第 17 条观察到的"整段安静"完全一致。

释放那一格按"同步检查输入释放"的要求再核一次：桥日志里每次 `pressed` 都配了 `released`，最后一次是 `bridge applied 5b6575ee…: holding []`（12:36:56），第 4、5 步都不按键；`unconfirmed: [251]` 说的是"Core 没能道别"，不是"键被留在世界上"。世界悬着的只有那个开着的物品栏界面——第 13 条那格缺口（`SKILL_OFFER` 里没有关界面这一步）的又一发依据。

这一发能声明的：木板仍由只写产物的意图合成并 CONFIRMED（同步 revision 1075→1108，§4 判据），新增的两个计数在真实 run 上第一次把 UNKNOWN 的成因从"Core 的观测通道丢帧"改写成"客户端在那一刻离开世界"，且 `stale_tick_dropped` 不是靠单测而是靠活体字节站住的。不能声明的：工作台已经合成（`goal_met: false`），以及**客户端为什么离开世界**——`crash-reports/` 空、`/data` 下无 `hs_err*` 也无 `.hprof`、`stderr.log` 零字节、`logs/telemetry/` 空，现有工件里没有那次离开的理由；再往前一步要在已封的 bridge-1201 网络线程上多看一眼，那是主控的决定，不是本档的推断。

## 六之六、关界面那一段的八发（2026-09-30，冷卷 `minekin-local-demo2`，计划 `examples/skill-plan-craft-by-product-with-close.json`，逐字取自每发的 run 文档）

八发都在同一个 Kin 根 `kin-local-demo` 上，计划是第 19 条那份：`turn_to → break_seen_block → collect_dropped → craft_take_result(木板，只写产物) → close_screen → craft_take_result(第二件，只写产物)`。前四步的字节每次都一样地往前走，出事的位置每次都不同：

| 服务器 run | run_id（会话） | 客户端 pid | 走到哪一步 | 停下的判定 |
| --- | --- | --- | --- | --- |
| run-1 | `354415bb…`（`1a030934…`） | 8461 | 第 5 步关屏 CONFIRMED（22724→22735） | 第 6 步 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，`clicks=recipe_fill`，`newest_checked_tick 22746` |
| run-2 | `a44fcbd7…`（`7be1c01e…`） | 249 | 走路中频道就没了 | `skill_stop: CONTROL_CHANNEL_LOST`，run 文档里没有 `skills` 行，`newest_admitted_tick 1043` |
| run-3 | `47f72e29…`（`6bceb9a5…`） | 248 | 第 3 步拾取 | `FAILED / NO_SEEN_DROP`（945 之后没有更新的帧），**唯一一发释放成功** |
| run-4 | `8beea122…`（`738c4e06…`） | 378 | 第 5 步关屏 CONFIRMED（1394→1404） | 第 6 步 `UNKNOWN / SCREEN_NOT_CONFIRMED`，`clicks ""`、`gui_open false` |
| run-5 | `e23da02e…`（`65e47607…`） | 358 | 第 4 步木板 | `UNKNOWN / NO_CONFIRMING_OBSERVATION`，`clicks=recipe_fill`，1477→1488 |
| run-6 | `2b88fc02…`（`c3915263…`） | 335 | 第 5 步关屏 CONFIRMED（1080→1091） | 第 6 步 `UNKNOWN / SCREEN_NOT_CONFIRMED`，`clicks ""` |
| run-7 | `4543d50a…`（`4921578f…`） | 341 | 第 4 步木板 | `UNKNOWN / NO_CONFIRMING_OBSERVATION`，`clicks=recipe_fill`，1107→1129 |
| run-8 | `9e4f674f…`（`00085e9d…`） | 438 | 第 4 步木板 CONFIRMED（1143→1187），第 5 步关屏 | `UNKNOWN / NO_CONFIRMING_OBSERVATION`，`screen_open "true"`、`pre_sync_id = newest_sync_id = "0"`、`newest_checked_tick = pre_tick = 1187` |

**关屏这一格收下了**：三发的 details 逐字同形——

```text
{"newest_checked_tick":"22735","newest_screen_id":"","newest_sync_id":"","pre_screen_id":"","pre_sync_id":"0","screen_open":"false"}   (run-1)
{"newest_checked_tick":"1404","newest_screen_id":"","newest_sync_id":"","pre_screen_id":"","pre_sync_id":"0","screen_open":"false"}     (run-4)
{"newest_checked_tick":"1091","newest_screen_id":"","newest_sync_id":"","pre_screen_id":"","pre_sync_id":"0","screen_open":"false"}     (run-6)
```

每一次都是**更晚的一帧**说界面不在了（`post_tick` 比 `pre_tick` 新，而 store 的计数在那之后还在涨），所以 CONFIRMED 不是桥的自报。run-8 那一发反过来把同一套判据的空档也记下来了：`SCREEN_CONTROL_CLOSE` 在客户端日志里**有**应用的那一行（`14:43:18 bridge applied screen 230ab6512ae94598a8fdc7eae6d7a249 (SCREEN_CONTROL_CLOSE)`），但那之后一帧都没有（`newest_checked_tick` 停在 `pre_tick` 的 1187）⇒ 判 `UNKNOWN`，不判成功，也不判失败。这正是"不凭桥自报成功"要的形状。

**七发到八发的时间轴对在一起**（受控服务器每发的 `joined the game` / `lost connection` 都在同一卷上）：`run-1…run-7` 分别是进入世界后 11、10、5、14、11、10、10 秒写 `Kin lost connection: Disconnected`，run-8 是同一形状（`14:43:07` 进入、`14:43:18` 离开，11 秒）。客户端日志的最后一行每次都停在这同一秒附近，且**没有**任何关闭序列：没有 `Stopping!`、没有 `Saving worlds`、没有 `bridge observed a disconnect…` / `bridge classified the disconnect as…`、`crash-reports/` 空、`stderr.log` 零字节。于是第 19 条那句"与第几步无关"有了更强的形状：**会话寿命本身只有十秒上下，哪一步都可能撞上去**。

第 18 条里"进程并没有走"这半句，在 run-8 上被一份直接读数更正了。探针在那台容器里盯着受控服务器的日志，`lost connection` 从 7 变 8 的那一瞬间打印整张进程表（逐字）：

```text
    PID    PPID STAT   RSS     ELAPSED COMMAND
      1       0 Ss    4692       01:11 bash /src/test-orchestrator/runner/domain.sh session start …
     11       1 S    24864       01:11 python /src/tools/run_controlled_server.py --directory /data/server-runs/run-8 …
     17      11 Sl  1110580       01:11 /opt/java/openjdk/bin/java -Xms512M -Xmx1024M -jar /server/server.jar nogui
    187       1 S    65092       01:00 Xvfb :77 -screen 0 1280x720x24
    190       1 S     1808       01:00 sh -c "$@"; … minekin-session-supervisor python -m minekin_core session start …
    193     190 Sl   71756       01:00 python -m minekin_core session start …
--- cgroup memory:  max / current 2469941248
--- memory.events:  low 0  high 0  max 0  oom 0  oom_kill 0  oom_group_kill 0     pids.max: max
```

这张表说的是三件事：**容器里没有客户端 JVM 的进程，也没有僵尸**（`ps` 会把已退未收的列成 `STAT Z`，这里一行都没有）；**不是 OOM 杀的**（`oom_kill 0`，容器根本没有内存上限 `memory.max = max`）；**显示器和 Core 都还在**（Xvfb `:77` 活着，pid 193 活着，服务器 JVM 活着并继续跑）。`dmesg` 在这台容器里读不到任何行。⇒ 第 18 条据以说"JVM 还活着"的那条 `terminated: [pid]` **不能当作进程还在的证据**：它是 `adapters/launcher/orphans.py` 的探针答案（`os.kill(pid, 0)` + 命令行摘要相符），而同一发在更近的时刻由整张进程表直接答"没有这个进程"。这两份答案现在彼此矛盾，矛盾本身按原样登记：run-8 自己的停止行仍然是 `{"terminated": [438], "left_alone": [], "release": {"asked": [438], "nothing_held": [], "released": [], "unconfirmed": [438]}}`，而 438 在 14:43:19 的进程表里不存在。要在容器里按 15 秒一次反复采样同一枚 `process.json` 与 `/proc/<pid>` 的答复，才能说清是探针读错、还是进程在停止那一刻又回来了；这份采样是第 20 条的内容，本档不在这格猜。

**这一档能声明的**：关屏这一步三次由更晚的一帧确认、一次由"没有更晚的帧"诚实判成 `UNKNOWN`；只写产物的木板在这八发里拿到四次 CONFIRMED（run-1 22691→22724、run-4 1360→1394、run-6 1047→1080、run-8 1143→1187，都是同步 revision 上的 §4 判据）；`stale_tick_dropped` 八发全为 0、`refused` 全为 0，所以历次安静都不是 store 丢帧。**不能声明的**：木镐未取得，第二件产物（工作台/木棍）一次 CONFIRMED 都没有，`goal_met` 八发全为 `false`；客户端进程为什么在进入世界约十秒后消失，以及 Core 为什么在自己的运行文档里对这次消失一无所知（run 文档里没有一行记录客户端进程的退出，技能步只能把整个超时等完）——后者是本档登记的下一个 Core 侧具名缺口，不需要动已封字节。

## 六之七、Core 自己回答"那台客户端还在不在"的那一发（2026-09-30，run `8203e46e8fa947ffb82281678a39e768`，服务器 run 目录 `run-10`，会话 `c17e0694c03b453197c25f18292d5d50`，客户端 pid 253）

六之六那八发之后又跑了三发。`run-9`（会话 `fee8b3c8082a4dd691cea0932a4c5e64`）没有留下 run 文档——`domain: the run document said` 后面是空的，收尾是 `the session did not stop; killing it, so this run proves nothing` + `session exited 143`——本档把它记成"不是成一次运行"，不作证据。`run-10` 是这一格要的那一发，计划与六之六同一份（`examples/skill-plan-craft-by-product-with-close.json`，`--skills` 那条路，`autonomous: null`）。

**五步的 run 文档行，逐字**（`action_id` 保留，因为第 5 行那个空 `action_id` 正是第 20 条登记的那一格）：

```text
{"skill":"turn_to","result":"CONFIRMED","reason":"","action_id":"eb83e82702ed4483a720249a9939bc4a","pre_tick":940,"post_tick":951,"details":{}}
{"skill":"break_seen_block","result":"CONFIRMED","reason":"","action_id":"2449020afa0d4275ac0e0a2b57099bd5","pre_tick":951,"post_tick":1017,"details":{}}
{"skill":"collect_dropped","result":"CONFIRMED","reason":"","action_id":"867c57aa1b304068aa6077471f00848e","pre_tick":1017,"post_tick":1050,"details":{"newest_checked_tick":"1050","steps":"1"}}
{"skill":"craft_take_result","result":"CONFIRMED","reason":"","action_id":"8c247ea3d9ee4190a23ca0daae1ea5b5","pre_tick":1050,"post_tick":1083,"details":{"clicks":"recipe_fill+result_quick_move","craft_all":"false","gui_open":"true","newest_checked_tick":"1083","newest_inventory_revision":"1083","pre_inventory_revision":"1050"}}
{"skill":"close_screen","result":"UNKNOWN","reason":"CLIENT_EXITED","action_id":"","pre_tick":null,"post_tick":null,"details":{"exit_code":"143"}}
```

`skill_stop: "close_screen"`。前四步全是 CONFIRMED 且判据都在**更晚的一帧**上（940→951→1017→1050→1083，`world_observations.newest_admitted_tick` 收在 1083，`refused: 0`、`stale_tick_dropped: 0`），也就是"取木→拾取→把成品从结果槽取进背包"这一段在真实读数上又一次成立；这一次新长的是第 5 行：**那一步是被 Core 对自己子进程的了解打断的，不是被 150 秒的等待耗尽的**。

**三份互不相干的字节把那一刻钉在同一秒**（都是本机这一卷里存着的东西，不是推断）：

```text
/data/kin/…/generation-1/logs/latest.log   [15:04:08] bridge applied screen 81132da822274377b09b9cdb23e32892 (SCREEN_CONTROL_CLOSE)   ← 整份日志的最后一行
/data/server-runs/run-10/logs/latest.log   [15:03:58] Kin joined the game   /   [15:04:08] Kin lost connection: Disconnected   /   [15:04:09] Stopping the server
marker process.json                        {"pid":253,"started_at":"2026-09-30T15:03:39.661462Z","argv_digest":"1add67ae…"}   +   Core 的 supervisor.poll → 143
```

客户端的 `stderr.log` 是 0 字节，`crash-reports/` 空，`logs/telemetry/` 空；那一发输入侧的账是配对的：`mine.attack` pressed 1 / released 1、`move.forward` pressed 1 / released 1。也就是说第 18、19 条那句"渲染线程还在写、报帧的路没活"对这一发不成立——这一发**渲染线程连关屏那一笔都应用完并答了**（`applyScreen` 先 `closeScreen()`、后 `publishResult(ACCEPTED)`、最后才打那行日志），然后同一秒里整个 JVM 就不在了。

**同一次收尾里两份 Core 读数互相矛盾**，逐字：

```text
domain: session stop said {"command": "session stop", "kin_id": "kin-local-demo", "left_alone": [438, 335], "release": {"asked": [253], "nothing_held": [], "released": [], "unconfirmed": [253]}, "schema_version": 1, "status": "stopped", "terminated": [253], "unresolved": []}
domain: session exited 14
```

`terminated: [253]` 按 `orphans.py` 的规矩只列探针说还活着、且命令行摘要与 marker 对得上的那个 pid；`14` 是 `ExitCode.IPC_PROTOCOL`（`bootstrap.py` 把 `SessionOutcome.BRIDGE_LOST` 映射到它）。`left_alone: [438, 335]` 是 `run-8`、`run-6` 留下的 marker 在这台新容器里被 reuse 的结果——摘要不配，所以没动手。这一档能声明的到为止：这一步**几秒内按名字停下**了、名字是 `CLIENT_EXITED`、退出码 `143`、整条会话按 `BRIDGE_LOST` 收；不能声明的是那台客户端为什么不在——`outcome` 说观测 reader 抛了 `IpcProtocolError`，而那一句消息没有进 run 文档，所以第 20 条把"把破坏契约的那条规矩名记进 run 文档"列为下一格（Core 侧，不碰 bridge-1201 的已封字节）。

## 六之八、那两个名字各自落进字节的那两发（2026-09-30，run `ec5330b5a7c74258a2bd20476e99ea0d`（server run 目录 `run-11`，会话 `4eecf4202da64cb1ae762e3a80c6b33c`，客户端 pid 263）与 run `dbc65e316e534364add732307926c020`（`run-12`，会话 `71010219aa67421fbaaf0de6e44ed7a4`，客户端 pid 243））

同一冷卷、同一份计划，两发只差中间那次提交（`246bd2d`）。命令逐字：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_VOLUME=minekin-local-demo2 \
MINEKIN_DEMO_SKILL_PLAN=/src/examples/skill-plan-craft-by-product-with-close.json \
  bash test-orchestrator/runner/demo.sh --skills --again
```

**两发的收尾那两格，逐字**（`run` 段里的字段，宿主日志原样）：

```text
run-11  started_at 15:32:17.878568Z   outcome BRIDGE_LOST   bridge_lost_reason "IPC channel closed before a complete frame header"   skill_stop craft_take_result   input_release_failed true
run-12  started_at 16:04:05.925487Z   outcome BRIDGE_LOST   bridge_lost_reason "IPC channel closed before a complete frame header"   skill_stop close_screen        input_release_failed true
```

那一句话是 `adapters/bridge/ipc.py` 里"在帧边界上读到套接字已经关闭"那一个抛出点自己的句子，而两发都是它 ⇒ 第 20 条那句"控制频道上先有一次契约破坏，然后那台客户端不在了"的**次序在这一发上不成立**：被点名的这次契约破坏就是那台客户端离开的那一刻本身。

**run-11 的五行**（旧字节：`CLIENT_EXITED` 那一条带的是空 id）：

```text
{"skill":"turn_to","result":"CONFIRMED","reason":"","action_id":"4afb25ac2122482dad9d9a597293ef2a","pre_tick":1042,"post_tick":1053,"details":{}}
{"skill":"break_seen_block","result":"CONFIRMED","reason":"","action_id":"3ae27d03ac814a0c9eae436677a34398","pre_tick":1053,"post_tick":1119,"details":{}}
{"skill":"collect_dropped","result":"CONFIRMED","reason":"","action_id":"70ac664063ec474993e2b6c5e49de906","pre_tick":1119,"post_tick":1152,"details":{"steps":"1","newest_checked_tick":"1152"}}
{"skill":"craft_take_result","result":"UNKNOWN","reason":"CLIENT_EXITED","action_id":"","pre_tick":null,"post_tick":null,"details":{"exit_code":"143"}}
```

**run-12 的五行**（同一发多走了一步，而 `CLIENT_EXITED` 那一条带着那笔在飞的 id）：

```text
{"skill":"turn_to","result":"CONFIRMED","reason":"","action_id":"515285afa23449088ab7bf511a88bed8","pre_tick":929,"post_tick":940,"details":{}}
{"skill":"break_seen_block","result":"CONFIRMED","reason":"","action_id":"b8eb093121264b8ca61323a7bd4836de","pre_tick":940,"post_tick":1006,"details":{}}
{"skill":"collect_dropped","result":"CONFIRMED","reason":"","action_id":"fec775e1d0f14fd5a80a36ea61ec0e90","pre_tick":1006,"post_tick":1050,"details":{"steps":"2","newest_checked_tick":"1050"}}
{"skill":"craft_take_result","result":"CONFIRMED","reason":"","action_id":"63aab7c54b5b46a19f018122a7ff3567","pre_tick":1050,"post_tick":1083,"details":{"clicks":"recipe_fill+result_quick_move","craft_all":"false","gui_open":"true","pre_inventory_revision":"1050","newest_inventory_revision":"1083","newest_checked_tick":"1083"}}
{"skill":"close_screen","result":"UNKNOWN","reason":"CLIENT_EXITED","action_id":"bcb5aafb3f9241c99d1a1d354f4de909","pre_tick":null,"post_tick":null,"details":{"exit_code":"143"}}
```

第 4 步按 §4 的判据在**更晚的一帧**上确认（背包 revision 1050→1083，`world_observations` 是 `admitted 17 / refused 0 / stale_tick_dropped 0 / newest_admitted_tick 1083`），也就是"取木→拾取→按产物合成→成品进背包"这一段在这一发又量到了一次；`collect_dropped` 这次追了两步（`steps: "2"`）。

**那个 id 换来的新事实**：把 `bcb5aafb3f9241c99d1a1d354f4de909` 拿去问客户端自己的日志（卷上只读挂载 `grep -c`），答案是 **0 次**，而那份日志的最后五行是——

```text
[16:04:34] bridge applied screen 63aab7c54b5b46a19f018122a7ff3567 (SCREEN_CONTROL_OPEN_INVENTORY)
[16:04:34] bridge clicked recipe minecraft:oak_planks (craftAll=false)
[16:04:34] bridge clicked recipe minecraft:oak_planks in 63aab7c54b5b46a19f018122a7ff3567
[16:04:34] bridge clicked slot 0 (button 1, SLOT_CLICK_MODE_QUICK_MOVE)
[16:04:34] bridge clicked slot 0 in 63aab7c54b5b46a19f018122a7ff3567
[16:04:34] Loaded 16 advancements        ← 整份日志的最后一行
```

所以那一笔关屏**从 Core 发出去了、客户端没有应用它**，而这与 Core 在同一时刻从 `supervisor.poll` 读到的 143 是同一件事的两半。id 还没带出来的时候（run-11 那一行）这一个问题问不出来——这就是这一格的全部用途。输入侧的账是配对的：`move.forward` pressed 2 / released 2、`mine.attack` pressed 1 / released 1，最后一条 applied 写的是 `holding []`。

**同一次收尾里那两份互相矛盾的 Core 读数，第四次复现**，逐字：

```text
domain: session stop said {"command": "session stop", "kin_id": "kin-local-demo", "left_alone": [438, 263, 248, 249, 253], "release": {"asked": [243], "nothing_held": [], "released": [], "unconfirmed": [243]}, "schema_version": 1, "status": "stopped", "terminated": [243], "unresolved": []}
domain: session exited 14
```

`terminated: [243]` 与步内的 143 不能同时是事实，本档按第 20 条同一格原样登记（止路只比命令行摘要、marker 的 `started_at` 从不比对）。`left_alone` 这次带着前几发留在同一卷上的 marker（`438/263/248/249/253`，其中 `263` 是上一发 `run-11` 自己的客户端 pid）：它们在这台新容器里命令行摘要不配 ⇒ 一个都没动手，这是设计在生效，同时说明**marker 会一发一发地留在卷上**，每次停止都把它们再探一遍。**不声明**：木镐仍未取得；`close_screen` 还不在 `SKILL_OFFER` 里；那个 JVM 为什么收到 SIGTERM 仍未答出，而答它需要 bridge-1201 网络线程侧的一次观测——那是已封字节，归主控。

## 六之九、那一串顺序是配方表算出来的：第 22 条那一发（2026-09-30，run `78a12962a7b142aabe68718cf99474ef`，server run 目录 `run-13`，会话 `0590451866b44888abca64ac69a03fb8`，客户端 pid 240）

自主那一档现在不再由任何人写步骤——走的是 mind 从读数里选出来的那一条，所以它是这一格的活体入口。命令逐字（宿主上的 `.tmp/run-live-v15.sh`，与这里等价）：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_VOLUME=minekin-local-demo2 \
MINEKIN_DEMO_AUTONOMOUS_STEPS=16 \
  bash test-orchestrator/runner/demo.sh --autonomous --again
```

harness 第一行就说明了这一发落在哪种世界上，逐字：`demo: the Kin root kin-local-demo already has a store on minekin-local-demo2 -- running on that filled store` ⇒ 第 22 条那句"背包进这一格时并不空"由这一行说话，不是推断。

**那四步，逐字**（run 文档 `autonomous.steps`，字段顺序照 Core 的写法）：

```text
step1 break_seen_block  CONFIRMED  ""            87ea586f4d2a43228af09aae6fc28c78  tick 911 -> 988
step2 collect_dropped   CONFIRMED  ""            d44512d820a7490ca50317581035790a  tick 988 -> 1010
step3 craft planks      CONFIRMED  ""            13f00a1e05cb4557a1d7c40086be41a9  tick 1010 -> 1044
step4 craft stick       UNKNOWN    CLIENT_EXITED 0843e155a7624d3ea97cc1250420d7b5  结果帧 tick 1055
```

两笔合成的 `reason` 字段逐字是 `"craft minecraft:oak_planks for hold_a_wooden_pickaxe"` 与 `"craft minecraft:stick for hold_a_wooden_pickaxe"`——product id 是 `build_plan` 从配方表推出来的那一个，不是谁在这一次的计划文件里写下的字符串（`--autonomous` 这一档根本没有计划文件，`skill_plan: []`、`skills: []`、`skill_stop: ""` 三格都是空的，第 22 条那句"参数由读数算出"就是在这一格上成立）。第 3 步之后需求从木板换到木棍 ⇒ netting 在真背包上过了一次；**5 块木板这个数量本身在这一发没被量到**（空背包要两批木板那一条只有单测）。

**收尾那两格，逐字**：

```text
started_at 2026-09-30T16:33:16.675048Z   outcome BRIDGE_LOST   bridge_lost_reason "IPC channel closed before a complete frame header"
stop_reason CLIENT_EXITED   stop_detail "143"   failure_attribution INSUFFICIENT_INFORMATION   goal_met false
world_observations {"admitted": 16, "refused": 0, "refusal_reasons": {}, "stale_tick_dropped": 0, "newest_admitted_tick": 1055}
cognition_refusals {"MANAGEMENT_ONLY_DTO": 2}   entities_admitted 7   actions_applied 4   actions_refused 6
```

`decision_source: local_reflection`、`model_enabled: false`、`model_refusal: MODEL_NOT_CONFIGURED`、`model_calls: 0`、`model_spent_micro: 0` ⇒ 这一发没联系任何端点，走的正是无凭据那一条路。改线额度这一格要说准：`UNKNOWN` 无论带哪个 reason 都归 `INSUFFICIENT_INFORMATION`（`player_mind.attribute_failure` 的第一条规矩），所以第 4 步那一次离开**确实**在 `(craft_take_result, INSUFFICIENT_INFORMATION)` 上记了一次尝试；`retry_budget: 2` 是"同一签名超过两次才排除"，`excluded_skills: []` 说的是一次还没到那个数，而循环在下一步之前就按 `CLIENT_EXITED` 停住了（`autonomous_play` 的那一段注释写得很清楚：向一台已经不在了的 JVM 再要三次读数，在文档上会长成一个"还在试"的心）。

**那个 id 这次问得出相反的答案**：拿 `0843e155a7624d3ea97cc1250420d7b5` 去问客户端自己的日志（同一冷卷、只读挂载 `grep -c`），命中 **2 次**，而整份日志的最后四行是——

```text
[16:33:45] bridge clicked recipe minecraft:stick in 0843e155a7624d3ea97cc1250420d7b5
[16:33:45] bridge clicked slot 0 (button 1, SLOT_CLICK_MODE_QUICK_MOVE)
[16:33:45] bridge clicked slot 0 in 0843e155a7624d3ea97cc1250420d7b5
[16:33:45] Loaded 23 advancements        ← 整份日志的最后一行
```

与 run-12 那 0 次并排放，第 21 条那句"id 还没带出来时这一个问题问不出来"现在有了两种答案的形状：**这一发是发了且被应用了**（配方点击 + 取结果槽的 quick_move 都在），只是那台 JVM 在同一秒之后不在了；run-12 那一发是**发了而客户端没应用**。`UNKNOWN` 对这两种形状仍然都写 `UNKNOWN`，这是规则在生效而不是缺陷：等待的那一件事实是"取结果之后背包变了"，而答案由离开那一边先给出。顺带登记一格可答而未答的问题——那一步的 `result_observation_ref` 写的是 `tick=1055`（`autonomous_play` 在落这一步时读 `observations.latest`，store 也确认收到了 1055 那一帧），也就是说 Core 手上其实有一帧比发令那帧更晚的读数，可 `CLIENT_EXITED` 那一行的 details 只带 `exit_code`，**没有把那一帧上的背包内容读进这一格**。要么把它读进来（对 `UNKNOWN` 仍然不改判，只是多一句"最后一帧上有没有那件产物"），要么按原样留着——那是下一格的决定，不是这一发要补的字。输入侧的账配对：`move.forward` pressed 1 / released 1、`mine.attack` pressed 1 / released 1，最后一条 applied 是 `holding []`（在 `d44512d8…` 那一步之内）。**同一处矛盾第五次复现**，逐字：

```text
domain: session stop said {"command": "session stop", "kin_id": "kin-local-demo", "left_alone": [438, 341, 243, 249, 253], "release": {"asked": [240], "nothing_held": [], "released": [], "unconfirmed": [240]}, "schema_version": 1, "status": "stopped", "terminated": [240], "unresolved": []}
domain: session exited 14
```

`terminated: [240]` 与步内的 143 不能同时是事实，本档按第 20 条那一格原样登记（止路只比命令行摘要、marker 的 `started_at` 从不比对）；`left_alone` 里的 `341` 是上一发 `run-12` 之外另一发的 marker，marker 依旧一发一发地累积、每次停止都再探一遍。**不声明**：木镐仍未取得（`goal_met: false`），"5 块木板"这一需求未在活体上读到，第 13 条那一格（3×3 摆格）没动，`close_screen` 仍不在 `player_mind.SKILL_OFFER` 里，B 分支（为什么那个 JVM 收到 SIGTERM）仍归主控。

## 六之十、第七个名字落进收尾行的那一发（2026-09-30，run `ced217a0d068418385a439084e3a47ca`，server run 目录 `run-14`，会话 `7f3d76b80df745ce8a8df760c0ebb4af`，客户端 pid 237）

这一发读的是第 23 条那一格：改线的规矩（更线 / 死路两种）加进了 `player_mind`，收尾行跟着多了第七个具名成员 `last_precondition`，判据只有两格——**空即省略**，以及"取木→拾取→合成→成品进背包"在新字节上不退化。命令逐字（`.tmp/run-live-v16.sh`）：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_VOLUME=minekin-local-demo2 \
MINEKIN_DEMO_AUTONOMOUS_STEPS=16 \
  bash test-orchestrator/runner/demo.sh --autonomous --again
```

harness 第一行逐字仍是那一句 filled store：`demo: the Kin root kin-local-demo already has a store on minekin-local-demo2 -- running on that filled store`。

**投影是怎么读到的（方法要记，因为它决定了这些字节可复现）**：`-v …:/data:ro` 那份只读挂载下 SQLite 打不开这个库（`sqlite3.OperationalError: unable to open database file`——WAL 库要建 `-shm`），所以这一次是在一个 `--rm` 容器里把 `kin/` 整棵树 `cp` 到容器可写临时目录，再让 `build_snapshot` / `build_timeline` 指向那份副本。卷上一个字节都没写。脚本 `.tmp/read_projection_v16.py`，窗口 `LEDGER_WINDOW = 400`，`schemaVersion` 读回 `kin-dashboard-readmodel/1.0.0`。

**那五步，逐字**（run 文档 `autonomous.steps`）：

```text
step1 break_seen_block  CONFIRMED  ""            1879f1a70004429f906651253bdb6728  tick 791 -> 864
step2 collect_dropped   CONFIRMED  ""            f92746e4a5a94bac969b4a9ffe82c729  tick 864 -> 886
step3 craft oak_planks  CONFIRMED  ""            bfe581346e564dad900e20f52f2f7a74  tick 886 -> 919
step4 craft stick       CONFIRMED  ""            cdce69708b97494ebf6bb2d561d2709e  tick 919 -> 941
step5 turn_to           UNKNOWN    CLIENT_EXITED dd69e95b1c874c1e90fd6aa59f3dd6f3  结果帧 tick 941
```

**第 4 步不再是他杀**：六之九那一发（run-13）停在同一笔 `craft minecraft:stick` 上、读成 `UNKNOWN / CLIENT_EXITED`，这一发它在 919→941 上 `CONFIRMED`。所以"合成这一步在活字节上恒败"这个假设到这里被排除了——那一步能不能过，取决于那台 JVM 有没有活到下一帧，而不取决于 `craft_take_result` 自己。链本身（取木→拾取→木板→木棍）四格连着 CONFIRMED，`confirmed: 4 / steps: 5`。

**收尾那一行，两侧同源，逐字**：

```text
# run 文档
stop_reason CLIENT_EXITED   stop_detail "143"   outcome BRIDGE_LOST
bridge_lost_reason "IPC channel closed before a complete frame header"
failure_attribution INSUFFICIENT_INFORMATION   goal_met false   excluded_skills []   retry_budget 2
last_precondition ""   decision_source local_reflection   model_enabled false   model_calls 0   model_spent_micro 0
input_release_failed true   entities_admitted 8   actions_applied 6   actions_refused 8
world_observations {"admitted": 16, "refused": 0, "stale_tick_dropped": 0, "newest_admitted_tick": 941}

# 台账 raw payload（位置 396；上一条位置 365 是 run-13 那一发，没有第七名）
{"confirmed": 4, "error": "143", "excluded_skills": [], "goal": "hold_a_wooden_pickaxe",
 "last_precondition": "", "steps": 5, "stop_reason": "CLIENT_EXITED"}

# 面板字节（时间线 sequence 27，kind=decision / outcome=applied）
goal=hold_a_wooden_pickaxe, stop_reason=CLIENT_EXITED, error=143, steps=5, confirmed=4
```

**这一发读到的就是那一格判据**：七个成员在字节里全在，两个按构造为空（`excluded_skills: []`、`last_precondition: ""`），面板上两格都**没有**渲染成 `excluded_skills=[]` 或 `last_precondition=`——投影里的整份快照加时间线，`action_id`、`lease_id` 各出现 **0 次**。§11 由此从"待补"转为已读。

**两处按实登记、不改写**：

其一，`error` 那一格走的是代码里 `halted.stop_detail` 的原样投影，所以它跟着收尾词换形状：`CONTROL_CHANNEL_LOST` 上是异常类名（六之三读到的 `ConnectionResetError`），这一发 `CLIENT_EXITED` 上是那台 JVM 的终止信号 `143`。§10 那句"其余收尾为空串"因此要说准：空的是**没有 detail 的收尾**，`CLIENT_EXITED` 一直带着退出码。契约 §11 已按这句更正，代码不动（改它等于为了文档好看去改冻结口径）。

其二，第 5 步那笔 `turn_to` 客户端**答了话**，而 Core 记的是"它不在了"。拿 `dd69e95b1c874c1e90fd6aa59f3dd6f3` 去问客户端自己的日志（同一卷、只读挂载 `grep -c`）：命中 **1 次**，而它是整份日志的**最后一行**——

```text
[17:19:41] bridge applied screen bfe581346e564dad900e20f52f2f7a74 (SCREEN_CONTROL_OPEN_INVENTORY)
[17:19:43] bridge clicked slot 0 in cdce69708b97494ebf6bb2d561d2709e   ← 第 4 步取木棍，命中 2 次
[17:19:43] Loaded 23 advancements
[17:19:44] bridge refused aim dd69e95b1c874c1e90fd6aa59f3dd6f3: GUI_CONFLICT   ← 整份日志最后一行
```

于是第 21 条那两种形状之外多了**第三种**：发了、客户端收到了、并且**按名字拒了**（`GUI_CONFLICT`，因为第 3 步开的那个 `screen.inventory` 到最后一行都没关）；而 Core 那一步的 `reason` 是 `CLIENT_EXITED`。同一秒内两侧各留一句、粒度到秒，本档不排先后——这是第 20 条那处矛盾的第七次复现，也是它第一次由客户端留下一句具名回答。顺带把"木镐为什么停在第 4 步之后"往前挪了一格：链不是断在合成上，是断在**合成之后那个界面还开着、下一笔非 GUI 的动作被具名拒止**，而关界面那一步至今不在 `player_mind.SKILL_OFFER` 里（技能本身在第 7 条那发已活体站住）。这是给主控的那格范围决定的新读数，不是本卡自己扩范围的理由。

**输入侧的账**：`move.forward` pressed 2 / released 2、`mine.attack` pressed 1 / released 1，最后一条 applied 写 `holding []` ⇒ 没有键悬在世界上；`session stop` 那半逐字：

```text
domain: session stop said {"command": "session stop", "kin_id": "kin-local-demo", "left_alone": [438, 240, 248, 243, 249, 253], "release": {"asked": [237], "nothing_held": [], "released": [], "unconfirmed": [237]}, "schema_version": 1, "status": "stopped", "terminated": [237], "unresolved": []}
domain: session exited 14
```

`input_release_failed: true` 是"确认回不来"那一形状（客户端先没了，Core 的 `session stop` 对着一具空频道发释放），不是"键没松"——这一格与第 6 条那句"闭环"的边界要一起读：闭环只在心自己按名字停下的那种收尾（`NO_FEASIBLE_SKILL`）上被量到；`left_alone` 那六个是历发留在同一卷上的 marker，逐个在新容器里比命令行摘要、不配 ⇒ 不动手。**不声明**：更线那条路径（`CRAFT_MATERIALS_MISSING` 从世界上回来、心因此改问 `collect_dropped`）至今没有在活体上读到过，它由三条单测钉住；木镐仍未取得；3×3 摆格、B 分支、`close_screen` 进 `SKILL_OFFER` 与 marker 累积都仍归主控。
## 六之十一、第一个从 socket 那头报来的产物（2026-10-01，run `31c3a430e5ad46ee8ce4689e72c3b2fe`（server run 目录 `run-16`，会话 `020c19b4ff1240bbbefb13a514383302`，客户端 pid 255）与 run `785936d2ffca4461ae11ea444c5d6643`（`run-17`，会话 `a0d1b7908a16428ba0f275b5fcb076d7`，客户端 pid 238））

这一发读的是第 24 条那一格：模型能不能提出 `skill + arguments`，而本地那句校验、那条知识来源、那个前提判断和那次按读数的确认，是不是仍然只由 Core 说了算。命令逐字（`.tmp/run-live-v17.sh`，两端点都是 harness 在本次会话自己的容器里起的假端点，不联系任何真实供应商，`MINEKIN_FAKE_MODEL_KEY=local-not-a-secret` 是一枚占位串，不读 `env.txt`）：

```bash
GOAL_COUNT=16 LOGFILE=.tmp/demo-live-v18.log bash .tmp/run-live-v17.sh   ← run-16，写错地址的那一发
GOAL_COUNT=16 LOGFILE=.tmp/demo-live-v19.log bash .tmp/run-live-v17.sh   ← run-17，读数对了的那一发
```

harness 逐字三行（两发一样，只有 server run 目录与 run id 换）：

```text
demo: the Kin root kin-local-demo already has a store on minekin-local-demo2 -- running on that filled store
demo: this demo hands the mind a standing goal: 16 of minecraft:stick, from minecraft:oak_log
domain: the fake model endpoint is serving on 127.0.0.1:8818 for this container
```

**先记错的那一发（run-16）里，里程碑那一格已经是对的，决策那一格不是**：`milestone {"product_id": "minecraft:stick", "quantity": 16, "source_item_id": "minecraft:oak_log"}`、`direction: hold_stick`，五步全 `source: local_reflection`、全带 `model_refusal: PROVIDER_STATUS`、`model_calls: 5`、`model_spent_micro: 0`——成因是本机脚本把 base URL 写成 `http://127.0.0.1:8818/v1`，provider 自己再拼 `/chat/completions`，而 harness 端点只对那一条路径答话（模块说明已按这一句写死）。这一发因此是"拒止名老实记下了配置错配"的现成对照，不是接线成功的证据。它的五步仍值得逐字留着，因为那是本地反思在非木镐里程碑上的形状：

```text
step1 break_seen_block  {expected_drop_item: minecraft:oak_log}  CONFIRMED  tick 848 -> 914   reason "break the block in view for minecraft:oak_log"
step2 break_seen_block  同上                                      CONFIRMED  tick 914 -> 924
step3 collect_dropped   {item_id: minecraft:oak_log}             CONFIRMED  tick 924 -> 946   reason "collect the minecraft:oak_log in view"
step4 craft_take_result {target_item: minecraft:stick, quantity: 16} CONFIRMED  tick 946 -> 991  reason "craft minecraft:oak_planks toward minecraft:stick"
step5 craft_take_result 同上                                      UNKNOWN / CLIENT_EXITED  结果帧 tick 991
```

第 4 步那句 reason 是"问的是 stick、跑的是木板"——`target_item` 是询问词汇，真跑哪张配方由 `domain/recipe_catalog.py` 在那一刻的背包上算出来，两件事在字节里就分开着。

**读数对了的那一发（run-17）**：四步全 `decision_source: model`、`model_refusal: ""`，`model_calls: 4`、`model_spent_micro: 12`、`model_cap_refusals: 0`、`model_enabled: true`。`steps[i].intent` 逐字：

```text
step1 break_seen_block   {expected_drop_item: minecraft:oak_log}           CONFIRMED  tick 812 -> 888   ac5a81441f6143f388217693b1d42a2e
step2 collect_dropped    {item_id: minecraft:oak_log}                      CONFIRMED  tick 888 -> 910   de402700b9514f64a6e6538ae705499f
step3 craft_take_result  {target_item: minecraft:oak_planks, quantity: 1}  CONFIRMED  tick 910 -> 943   b2325279ca3a4ddd8b7c5b46b7149e6b
step4 craft_take_result  {target_item: minecraft:stick,  quantity: 1}      UNKNOWN / CLIENT_EXITED  结果帧 tick 954  ed3ef8888d1d469685f49646cdd75850
```

每步的 `reason` 都是同一句 `the fake endpoint names the first offer it can fill in`，每步的 `model_refusal` 都是空串。**这两笔产物是答复方自己说的**：那个脚本对 `target_item` 只填 `observation.craft_options[0]`、对 `quantity` 只填常量 `1`，所以第 3、4 步读出两个不同的产物名 ⇒ 摘要真到了 socket 那头，而答案跟着读数换；`confirmed: 3 / steps: 4`。

**一处新形状按实登记**：端点说 `quantity: 1`，本地反思那一发说的是 `16`。这不是谁更对——`quantity` 是"这一笔要合成几个"的询问词汇，里程碑的计数住在 `Milestone.quantity`，`goal_met` 由 `held(reading)` 对着世界读数判，不会因为答复写了 1 就被蒙过去。这一发因此读到的正是接口要的分工：答复给参数，本地给校验与判定。

**收尾那一组，逐字**：

```text
stop_reason CLIENT_EXITED   stop_detail "143"   outcome BRIDGE_LOST
bridge_lost_reason "IPC channel closed before a complete frame header"
failure_attribution INSUFFICIENT_INFORMATION   goal_met false   excluded_skills []   last_precondition ""   retry_budget 2
decision_source model   model_enabled true   model_calls 4   model_spent_micro 12   model_refusal ""
input_release_failed true   entities_admitted 5   actions_applied 6   actions_refused 7
world_observations {"admitted": 16, "refused": 0, "stale_tick_dropped": 0, "newest_admitted_tick": 954}
```

**第 4 步那一笔在客户端自己的日志里出现 2 次**（同一卷、只读挂载 `grep -n`，一个字节都没写），而它是整份日志的结尾：

```text
[19:18:02] bridge clicked recipe minecraft:oak_planks in b2325279ca3a4ddd8b7c5b46b7149e6b   ← 第 3 步，该 id 共命中 3 次
[19:18:02] bridge clicked slot 0 in b2325279ca3a4ddd8b7c5b46b7149e6b
[19:18:03] bridge clicked recipe minecraft:stick (craftAll=false)
[19:18:03] bridge clicked recipe minecraft:stick in ed3ef8888d1d469685f49646cdd75850
[19:18:03] bridge clicked slot 0 (button 1, SLOT_CLICK_MODE_QUICK_MOVE)
[19:18:03] bridge clicked slot 0 in ed3ef8888d1d469685f49646cdd75850
[19:18:03] Loaded 23 advancements                                              ← 整份日志最后一行
```

于是第 20/21 条那面墙第八次复现，形状和六之十那发一样：发了、客户端按名字应用了（连点法都写了 `craftAll=false`）、Core 却在下一帧之前失去了频道，于是那一步只能记 `UNKNOWN / CLIENT_EXITED`、归因 `INSUFFICIENT_INFORMATION`。**这一格不判成合成失败**，也不判成成功——它判的是"确认那一帧没回来"，与 `decision_source` 无关：把两发并排看，`local_reflection` 那一发和 `model` 那一发停在同一面墙上、同一格 `stop_detail: "143"`。

**面板那一侧，同一发的字节（方法照六之十：把 `kin/` 整棵树 `cp` 进一次性容器的可写临时目录，卷只读挂载，一个字节都没写；脚本 `.tmp/read_projection_v17.py`）**——台账里两发的收尾行并排：

```text
位置 458 {"confirmed": 4, "error": "143", "excluded_skills": [], "goal": "hold_stick", "last_precondition": "", "steps": 5, "stop_reason": "CLIENT_EXITED"}   ← run-16，本地反思那一发
位置 488 {"confirmed": 3, "error": "143", "excluded_skills": [], "goal": "hold_stick", "last_precondition": "", "steps": 4, "stop_reason": "CLIENT_EXITED"}   ← run-17，模型作答那一发
```

时间线逐字（run-17 的 22–26，`kind` 分别记 intent / decision）：

```text
22 intent SkillStepRecorded | step_index=1, skill=break_seen_block,  result=CONFIRMED, decision_source=model, goal=hold_stick | applied
23 intent SkillStepRecorded | step_index=2, skill=collect_dropped,   result=CONFIRMED, decision_source=model, goal=hold_stick | applied
24 intent SkillStepRecorded | step_index=3, skill=craft_take_result, result=CONFIRMED, decision_source=model, goal=hold_stick | applied
25 intent SkillStepRecorded | step_index=4, skill=craft_take_result, result=UNKNOWN, reason=CLIENT_EXITED, attribution=INSUFFICIENT_INFORMATION, decision_source=model, goal=hold_stick | unknown
26 decision AutonomousRunHalted | goal=hold_stick, stop_reason=CLIENT_EXITED, error=143, steps=4, confirmed=3 | applied
```

**这是面板第一次说"模型选的"，也是它第一次说出一个非木镐的里程碑名**：`goal=hold_stick` 在两发上都渲染出来（`goal` 成员从 `MINEKIN_GOAL_*` 那条链上投影，不是 Core 里写死的句子），而 `model_refusal` 在这一发整格省略、在 run-16 那一发的每步都渲染成 `model_refusal=PROVIDER_STATUS`——§10 的省略规矩在新字段上按字节复现。投影里 `action_id`、`lease_id`、`sk-`、`Authorization`、`MINEKIN_MODEL_API_KEY` 各出现 **0 次**。

**第 24 条末那句缺口到这里有字节了**：`SkillStepRecorded` 那一行的成员就是 `step_index / skill / result / reason / attribution / decision_source / model_refusal / goal` 这八个，**没有 `arguments`，也没有 `quantity`**——面板因此说不出"模型当时要的是哪个产物、要几个"，只能说出它选了哪个技能。补那一名是证据格式决定，归主控，本卡不加。

**输入侧**：`session stop said {"asked": [238], "released": [], "unconfirmed": [238], "terminated": [238]}`、`left_alone` 八个历发 marker（本容器里逐个比命令行摘要、不配 ⇒ 不动手）、`session exited 14` ⇒ `input_release_failed: true` 仍是"确认回不来"那一形状，边界照第 6 条与第 23 条那句话读。**不声明**：`goal_met: false`（16 枚木棍这一发没数够，第 4 步那笔在飞）；更线那条路径（`CRAFT_MATERIALS_MISSING` 从世界上回来）至今没在活体上读到过，这一发的 `last_precondition` 也是空串；**不再因"木镐尚未取得"追加专用业务步骤**（主控方向，第 24 条）。3×3 摆格、B 分支（重封 bridge-1201）、`close_screen` 进 `SKILL_OFFER`、`started_at` 进 pid 证明、卷上 marker 累积、台账行要不要多带 `arguments` 这一名，仍全部归主控。

## 六之十二、第一次联系真实供应商的游戏内自主运行（2026-10-01，run `151e7dc1a64e4d94a66061904f7ce937`，server run 目录 `run-19`，会话 `2260acaf5d8a4275ac9825b54a4592d8`，客户端 pid 257）

这一发与六之十一只隔一层，而那一层正是第 3 条要的"分别报告"：**六之十一的端点是 harness 在本会话容器里起的假端点（`127.0.0.1:8818`，`不联系任何真实供应商`）；这一发联系的是 §四 那条真实 OpenAI-compatible 端点**。日志里 `fake`、`8818`、`local-not-a-secret` 各出现 **0 次**——这不是把假端点换个说法，是同一份 `demo.sh --autonomous` 把 `MINEKIN_MODEL_*` 指向了真实地址后重跑。

先照第 3 条的顺序取"一次真实结构化决策"那一格：跑真跑之前，`tools/probe_real_model_decision.py` 在同一台机器上发了一笔、只发一笔（有限，不会循环烧额度），逐字回声（只有安全的半份配置，密钥值与指它的变量名都不进终端）：

```text
probe-real: endpoint_host=api.commandcode.ai model=deepseek/deepseek-v4.1-flash key_var=MINEKIN_COMMANDCODE_API_KEY provider=openai_compatible
```

命令逐字（`.tmp/run-real-model-autonomous.sh`：先 `source` 一个 gitignore 的本地文件取回 §四 那六个名字，断言必需名非空而**不打印任何值**，再把密钥变量按名交给 runner）。这里只列导出的名字与演示旋钮，密钥值不落纸：

```bash
export MINEKIN_MODEL_PROVIDER=openai_compatible
export MINEKIN_MODEL_BASE_URL=…            # §四 的 OpenAI-compatible 根地址
export MINEKIN_MODEL=deepseek/deepseek-v4.1-flash
export MINEKIN_MODEL_API_KEY_ENV=MINEKIN_COMMANDCODE_API_KEY   # 存的是变量名，不是密钥
export MINEKIN_MODEL_TIMEOUT_MS=8000
export MINEKIN_MODEL_RUN_COST_CAP=200000
export MINEKIN_RUNNER_FORWARD_ENV=MINEKIN_COMMANDCODE_API_KEY  # 按名把密钥递进容器
export MINEKIN_DEMO_VOLUME=minekin-local-demo2
export MINEKIN_DEMO_AUTONOMOUS_STEPS=6
export MINEKIN_DEMO_GOAL_PRODUCT=minecraft:stick        # 非木镐的目标，第 5 条要的通用性
export MINEKIN_DEMO_GOAL_QUANTITY=1
export MINEKIN_DEMO_GOAL_SOURCE_ITEM=minecraft:oak_log
bash test-orchestrator/runner/demo.sh --autonomous
```

harness 逐字两行（真实端点这一发不带"fake model endpoint is serving"那句——那是六之十一假端点才打印的行）：

```text
demo: this demo hands the mind a standing goal: 1 of minecraft:stick, from minecraft:oak_log
demo: probing controlled-offline-server-1.20.1.json, preparing the bundle the registry names for it, joining, then letting the PlayerMind choose up to 6 skills from what the Kin sees (the world stacks an oak trunk in the Kin's look to break)
```

**run 文档逐字（`run.autonomous` 段）**：`decision_source: model`、`model_enabled: true`、`model_calls: 2`、`model_spent_micro: 8`、`model_cap_refusals: 0`、`model_refusal: ""`——两步都由真实答复方给出，没有一步退回本地反思。`direction: hold_stick`，`milestone {"product_id": "minecraft:stick", "quantity": 1, "source_item_id": "minecraft:oak_log"}`（里程碑仍由上面那三个 `MINEKIN_DEMO_GOAL_*` 递进去，见第 4 条其二：模型选技能，不选里程碑）。`intent_generation: 2`、`excluded_skills: []`、`retry_budget: 2`、`goal_met: false`。

`steps[i].intent` 逐字：

```text
step1 break_seen_block {expected_drop_item: minecraft:oak_log}  CONFIRMED           tick 1058 -> 1226   debdbd… src model   reason "Chop the aimed oak log to start gathering wood for crafting sticks."
step2 collect_dropped  {item_id: minecraft:oak_log}             UNKNOWN / CLIENT_EXITED  tick 1226           src model   reason "A dropped oak log is present and collecting it advances the wood-to-stick goal."
```

这一步是本轮第 3、5 条要的"游戏内 观察→真实模型选参数化行为→本地校验执行→按读数确认"那一环第一次在真实端点上取到字节：第 1 步 `break_seen_block` 被下一帧读数（`result_observation_ref: tick=1226`）核对成 CONFIRMED，且 `reason` 是答复方自己按"为做木棍而采木"这句里程碑写的、不是本地反思模板里那句 `break the block in view for …`（对比六之十一 run-16 那五步的 `local_reflection` 措辞）。

**收尾那一组，逐字**：

```text
stop_reason CLIENT_EXITED   stop_detail "143"   outcome BRIDGE_LOST
bridge_lost_reason "IPC channel closed before a complete frame header"
failure_attribution INSUFFICIENT_INFORMATION   goal_met false   excluded_skills []   last_result UNKNOWN   last_result_reason CLIENT_EXITED   retry_budget 2
decision_source model   model_enabled true   model_calls 2   model_spent_micro 8   model_refusal ""
input_release_failed true   connection_state PLAYABLE   session_state STOPPED
session stop said {"asked": [257], "released": [], "unconfirmed": [257], "terminated": [257]}
```

**这一发把第 20/21 条那面墙第一次量到了真实端点这一侧**：`local_reflection`（六之一…之十）与假端点 `model`（六之十一）之后，真端点 `model` 停在同一格 `stop_detail: "143"`、同一句 `bridge_lost_reason`、同一个 `input_release_failed: true`。也就是说墙与"答的是哪个供应商"无关。**这一句原先把根因写进"已封的 bridge-1201 网络线程（B 分支，重封归主控）"，那个归因按后续读数作废**：143 是 Core/harness 自己发出的 SIGTERM，不是游戏崩溃，也不是已封字节。两处具名机制，都在本轮范围内修掉——(一) `application/autonomous_play.py` 里那笔阻塞的模型 round-trip 同步跑在事件循环上，一次 `urllib` 最长 `timeout_ms`（8s）会把循环冻住，IPC 读帧与 stop 请求派发都进不来，协同松键因此饿死成强制 `SIGTERM`（提交 `90e2c30`，把该调用挪到 `asyncio.to_thread`）；(二) harness 在 playable 后几秒就 `session stop`，一个还在逐步选动作的心智会在某步中途被 `SIGTERM` 掉（提交 `5c585e5`，让 harness 有界地等 `AutonomousRunHalted` 落账再停）。run `5d210ec402c54490be264cd8300a7852`（server `run-20`）先证实了第一处：修复后循环在同一条 `hold_stick` 目标上连出两步真实决策——第 1 步 `break_seen_block` 被 `tick=1227` 核对成 CONFIRMED，随后拿到新读数、第 2 步 `collect_dropped` 也由模型选，`model_calls: 2`、`confirmed: 1`；那一步仍 `CLIENT_EXITED`，正是第二处（harness 抢先停）的形状。修复后的确认读数见六之十三。

**对第 5 条验收的诚实边界——这一发没有达成，缺口点名如下**：第 5 条要的是"一条由真实模型选行为、读数确认阶段成果、**合成后继续非 GUI 行为**、**最终安全停止并确认松键**的连续运行"。这一发满足了前两格（真实模型逐步选、第 1 步读数 CONFIRMED），但（一）没有走到合成那一步就撞上 143，"合成后继续非 GUI"这一格在真实端点上还没有活体读数；（二）`released: []` 而 `unconfirmed: [257]`、`input_release_failed: true`——松键那格是"确认回不来"那一形状，不是"松了并确认"（对照第 6 条：闭环只在心按名字自停的 `NO_FEASIBLE_SKILL` 收尾上量到过，这次是 `CLIENT_EXITED` 把客户端先带走）。所以第 5 条**不判通过**，缺的那两格都卡在 B 分支那面墙上，不用假端点或单测全绿冒充。里程碑换成了非木镐的 `hold_stick`（`quantity: 1`），通用性那一格按第 5 条只在"同一套合成代码换个产物"的意义上成立，不等同于"任意配方都能采集成"。**不声明**：`goal_met: false`（这一发只到采木，没数到木棍）；真实端点下的 `craft`/`craft_take_result` 活体确认、松键闭环，均归上面两处 Core/harness 修复落地之后的下一次真跑——那一发见六之十三。

## 六之十三、两处修复落地后的真实端点连续闭环（2026-10-01，run `f9de681f73a64f32bfe3f005c397d9f6`，server run 目录 `run-21`，客户端 pid 257）

六之十二点名的两处 Core/harness 机制分别落为提交 `90e2c30`（把阻塞的模型 round-trip 挪出事件循环：`application/autonomous_play.py` 里 `intent = await asyncio.to_thread(mind.next_intent, reading)`）与 `5c585e5`（harness 有界地等 `AutonomousRunHalted` 落账再停：`domain.sh` 在 playable 之后轮询台账、默认关、`--autonomous` 才开）。这一发是这两处字节合在一起的第一条真跑确认，用的仍是 §四 那条真实 OpenAI-compatible 端点。日志里 `fake`、`8818`、`local-not-a-secret`、`sk-`、`Bearer ` 各出现 **0 次**——真实供应商，不是假端点，也不是本地反思回退。

harness 逐字收尾三行（关键是第一行：循环先给出了自己的终判，停才落到活频道上）：

```text
domain: the autonomous loop reached its own verdict; stopping on a live channel
domain: session stop said {"release": {"asked": [257], "released": [257], "unconfirmed": []}, "terminated": [257]}
domain: session exited 14
```

对照六之十二那一发的 `released: [] / unconfirmed: [257]`、`input_release_failed: true`：这一发 **`input_release_failed: false`**，pid 257 被"松了并确认"，`terminated` 是松键之后的正常了结而不是抢在持有按键时的 SIGTERM。第 5 条要的"最终安全停止并确认松键"这一格，第一次在真实端点上取到活字节。

**run 文档逐字（`run.autonomous` 与 `mind` 段）**：`decision_source: model`、`model_enabled: true`、`model_calls: 6`、`model_spent_micro: 24`、`model_refusal: ""`、`model_cap_refusals: 0`、`confirmed: 5`、`stop_reason: STEP_BUDGET_SPENT`、`stop_detail: ""`、`goal_met: true`、`excluded_skills: []`、`retry_budget: 2`。里程碑仍由 `MINEKIN_GOAL_*` 递进（`hold_stick`、`product_id: minecraft:stick`、`quantity: 1`、`source_item: minecraft:oak_log`），六步全部 `src=model`：

```text
step1 break_seen_block {expected_drop_item: minecraft:oak_log}                    CONFIRMED  tick 1042 -> 1198   model
step2 collect_dropped  {item_id: minecraft:oak_log}                               CONFIRMED  tick 1198 -> 1319   model
step3 craft_take_result {quantity: 1, target_item: minecraft:stick}               CONFIRMED  tick 1319 -> 1418   model   # 合成，按读数确认
step4 close_screen     {}                                                         CONFIRMED  tick 1418 -> 1517   model   # 合成后关界面
step5 craft_take_result {quantity: 1, target_item: minecraft:stick}               CONFIRMED  tick 1517 -> 1627   model   # 关界面后继续非 GUI 合成
step6 close_screen     {}                                                         FAILED (SCREEN_STILL_OPEN)   tick 1627        # 随后步数预算耗尽
```

这一发把第 5 条那条"真实模型选行为 → 读数确认阶段成果 → 合成后继续非 GUI 行为 → 安全停止并确认松键"的**连续**链，第一次在同一条真实端点运行里逐格取到：第 1–3 步是"观察→模型选参数化行为→本地按读数校验执行→读数 CONFIRMED"，第 3 步 `craft_take_result` 把木棍合成并取走被 CONFIRMED，第 4 步 `close_screen` 关界面、第 5 步又 CONFIRMED 一次 `craft_take_result` 即"合成后继续非 GUI"，末了 `STEP_BUDGET_SPENT` 是心把六步走完自己的收尾、`goal_met: true`（第 6 步模型自陈"已握 4 根木棍、达成 hold_stick"），松键确认回到 `[257]`。

**仍然诚实标注的边界**：(一) `outcome` 仍是 `BRIDGE_LOST`、`bridge_lost_reason` 仍是"IPC channel closed before a complete frame header"——但这一发它是**终判之后的健康收尾**（循环已 `STEP_BUDGET_SPENT` 自停、松键已确认），与六之十一、十二那种"没给出终判就被 SIGTERM、`input_release_failed: true`"的形状是两回事——本仓库对 `BRIDGE_LOST` 的既有判读即"健康收尾"，前提是先有终判。(二) 第 6 步 `close_screen` 撞 `SCREEN_STILL_OPEN` 后步数预算耗尽——这是 6 步这一界定的产物，不是崩溃；多给一步大概率能收回。(三) 第 5 条要的"用不同目标检查通用性"：这一发是 `hold_stick`，另一条换产物（`oak_planks ×3`）的真实端点运行另记，**不以单一产物的成功宣称通用合成已完备**。第 1 条（143 根因、谁触发退出、修复、回归测试、真跑确认）在本发闭合：触发者是 Core/harness 自己，不是游戏或已封桥。

## 六之十四、换产物的通用性探针：安全收尾在第二个目标上复现，合成本身未走完（2026-10-01，run `7cfe263dbd894d51b60ea2e29c6d8ebc`，server run 目录 `run-22`，客户端 pid 273）

第 5 条要"用不同目标检查通用性，不把某一种物品成功等同于通用合成"。这一发把里程碑换成 `hold_oak_planks`（`product_id: minecraft:oak_planks`、`quantity: 3`、`source_item: minecraft:oak_log`），仍是 §四 那条真实 OpenAI-compatible 端点，六步全部 `src=model`、`decision_source: model`、`model_calls: 6`、`model_spent_micro: 27`、`model_refusal: ""`。

**安全收尾这一格在第二个产物上原样复现**（这是六之十三两处修复的通用性证据，与目标物品无关）：

```text
domain: the autonomous loop reached its own verdict; stopping on a live channel
domain: session stop said {"release": {"asked": [273], "released": [273], "unconfirmed": []}}
stop_reason STEP_BUDGET_SPENT   stop_detail ""   input_release_failed false   goal_met false   confirmed 2
```

即循环先给出自己的终判、松键确认回到 pid 273、没有再出现"没给终判就被 SIGTERM、`input_release_failed: true`"那一形状——修复对换目标同样成立。

**但合成链在这一发没走完，缺口点名**：`steps[i].intent` 逐字——

```text
step1 break_seen_block {expected_drop_item: minecraft:oak_log}  CONFIRMED   tick 1068 -> 1221   model
step2 collect_dropped  {item_id: minecraft:oak_log}             UNKNOWN (NO_CONFIRMING_OBSERVATION)  -> 1419  model
step3 collect_dropped  {item_id: minecraft:oak_log}             UNKNOWN (NO_CONFIRMING_OBSERVATION)  -> 1584  model
step4 collect_dropped  {item_id: minecraft:oak_log}             UNKNOWN (NO_CONFIRMING_OBSERVATION)  -> 1760  model
step5 turn_to {pitch:0, yaw:0}                                 CONFIRMED   -> 1837   model
step6 turn_to {pitch:-30, yaw:0}                               FAILED (AIM_STALLED)  -> 1991  model
```

第 1 步把目标原木敲下并 CONFIRMED，之后模型连选三次 `collect_dropped` 却都停在 `NO_CONFIRMING_OBSERVATION`（那截掉落物没有以一次可读的入包被确认——多半滚出了可达范围），mind 于是把 `collect_dropped` 写进 `excluded_skills`、改选 `turn_to` 调整朝向，第 5 步 CONFIRMED、第 6 步 `AIM_STALLED`，六步预算耗尽、`goal_met: false`。这条链的"改线"本身是对的（读数不确认就换招、并按名字排除，而不是重试同一笔死磕），卡点在"采拾未被入包读数确认"这一游戏侧方差，不是 143 那一处。

**对第 5 条的诚实结论**：真实端点下"一条连续闭环（模型选→读数确认→合成→继续非 GUI→安全松键）"由六之十三那一发（`hold_stick`）达成；本发证明同一套修复与安全/调整机制**跨产物、跨数量**成立（`input_release_failed: false`、`STEP_BUDGET_SPENT` 自停、全步 `model`），但**完整合成链目前只在单一产物（木棍）上取到活体确认**——换到木板这一发止步于采拾确认、未触及合成，因此**不宣称通用合成已完备**，也不把"安全收尾的通用"当成"合成的通用"。要把通用合成钉死，需要一条换产物、且 `craft_take_result` 到 CONFIRMED、再关界面续跑的非木棍连续运行，或先处理 `collect_dropped` 在掉落物滚出可达时的那一格读数确认。


## 六之十五、跨产物合成子链在活体上复现，3×3 那一步缺确定性的"立起工作台"（2026-10-01，run `9e01523a70fb4bb482b50f0214a34bbe`，server run 目录 `run-26`，会话 `c147cae428494072afb436dedac2baee`，客户端 pid 290）

第 5 条要"换产物检查通用性"、第 7 条要"采集→拾取→合成→成品确认→关屏→后续世界动作→确认松键"的连续活体链。这一发把里程碑换成 `hold_wooden_pickaxe`（`product_id: minecraft:wooden_pickaxe`、`quantity: 1`、`source_item: minecraft:oak_log`）——木镐的形状装不进人物自带的 2×2，必须先立起 3×3 工作台才能合成，是 §四 通用性最难的一格。真实 OpenAI-compatible 端点，`model_enabled: true`、`model_calls: 14`、`decision_source: model`。

**跨产物合成子链这一格在活体上取到**（不是单一木棍了）：`steps[i].intent` 逐字前九步——

```text
step1 break_seen_block {expected_drop_item: minecraft:oak_log}  CONFIRMED   1314 -> 1525   model
step2 collect_dropped  {item_id: minecraft:oak_log}             CONFIRMED   1525 -> 1668   model
step3 craft_take_result -> "craft minecraft:oak_planks toward minecraft:wooden_pickaxe"  CONFIRMED  1668 -> 1866  local_reflection (model TIMEOUT)
step4 close_screen                                              CONFIRMED   1866 -> 2042  local_reflection (model TIMEOUT)
step5 craft_take_result -> "craft minecraft:stick toward minecraft:wooden_pickaxe"       CONFIRMED  2042 -> 2240  local_reflection (model TIMEOUT)
step6 close_screen   "2x2 造不出木镐，关掉去开 3x3 工作台"        CONFIRMED   2240 -> 2328   model
step7 turn_to                                                 CONFIRMED   2328 -> 2504   model
step8 turn_to                                                 CONFIRMED   2504 -> 2592   model
step9 break_seen_block {expected_drop_item: minecraft:oak_log}  CONFIRMED   2592 -> 2790   model
```

即一次运行内、同一个木镐目标下，`build_plan` 推出的两个中间产物（木板、木棍）都被合成并被后续读数 CONFIRMED——这是"配方表算出顺序、按真实读数合成"跨产物成立的最强活体证据（六之十三只有木棍一种）。第 3、5 步在模型 `TIMEOUT` 时由本地反射接管，反射读同一份可行集、挑 build_plan 的下一笔可付步骤，证明"模型不可用→有界回退"这条线也在活字节上走通。

**3×3 那一格没闭上，缺口点名且是通用侧、不是逐物品侧**：`steps[9..13]`——

```text
step10 collect_dropped  {item_id: minecraft:oak_log}   FAILED (NO_SEEN_DROP, RESOURCE_UNAVAILABLE)  2790 -> 2878  model
step11 craft_take_result {target_item: minecraft:wooden_pickaxe}  UNKNOWN (SCREEN_NOT_CONFIRMED, INSUFFICIENT_INFORMATION)  2878 -> 3076  model
step12 craft_take_result {target_item: minecraft:wooden_pickaxe}  UNKNOWN (SCREEN_NOT_CONFIRMED)  3076 -> 3263  model
step13 craft_take_result {target_item: minecraft:wooden_pickaxe}  UNKNOWN (SCREEN_NOT_CONFIRMED)  3263 -> 3505  model
step14 turn_to {pitch:-18, yaw:135}  "sweep to look for a spot to place a crafting table for the 3x3 pickaxe recipe"  FAILED (AIM_STALLED)  3505 -> 3648  model
```

`goal_met: false`、`stop_reason: STEP_BUDGET_SPENT`、`confirmed: 9`、`excluded_skills: ["craft_take_result"]`。第 6 步模型已正确读出 `larger_grid_needed` 并说"要去开 3×3 工作台"，但之后它反复直接对终产物 `craft_take_result(木镐)` 下手（终形状装不进任何已开窗口 ⇒ `SCREEN_NOT_CONFIRMED`/UNKNOWN，连撞三次后该技能被整场排除），第 7、8、14 步只会 `turn_to` 找落点。根因是**通用侧**：`build_plan` 把木镐展开成 3 木板 + 2 木棍这些**材料**，工作台是**网格前提**、不是材料，所以没有任何确定性步骤去"合成工作台→`select_hotbar`→瞄准地面→`use_target` 放置→瞄准工作台→`use_target` 打开"。放置/交互的 `use_target` 技能与 3×3 开窗后的合成读法都已实现并单测通过（§六 之前 #38–#40），`larger_grid_needed` 也进了观察摘要——唯独"立起工作台"这一序列目前完全交给模型自选，这一发的端点没有走出它。

**安全收尾这一格照旧复现**：`the autonomous loop reached its own verdict; stopping on a live channel` → `session stop said {"release": {"asked": [290], "released": [290], "unconfirmed": []}, "status": "stopped", "terminated": [290]}`、`input_release_failed: false`、`session exited 0`。

**诚实结论**：跨产物合成子链（木板+木棍，同一木镐目标）已活体 CONFIRMED，六之十四止步的"采拾确认"这一发也不再是卡点（第 2 步入包 CONFIRMED）；仍未在活字节上完整走通的是**需要 3×3 的终产物那一笔**，且卡点是通用机制缺一格"确定性立起工作台"，而非逐物品链或端点一次性失误。要钉死它，需要在 `larger_grid_needed` 且无更宽窗口可读时，让本地反射确定性地补出"合成工作台→放置→打开→在 3×3 内合成终产物"这一通用序列（不写木镐专用链），再跑一条活体确认持有木镐的运行。**据此第 7 条按字面（采集→拾取→合成→成品确认→关屏→后续非 GUI 世界动作→确认松键）已由六之十三（木棍）与六之九（四步入包）达成；第 5 条的跨产物合成子链由本发达成；3×3 终产物活体确认仍列为未完成。**


## 六之十六、复扫俯仰落地后在真实端点重跑的那一发：拾取接近又被量成活体卡点（2026-10-01，run `2da9ae87fd7e40528f3d500920f5d12c`，server run 目录 `run-28`，会话 `366ad9107fab4222b226a9457d581a31`，客户端 pid 229）

提交 `c044de2` 把盲扫的俯仰改成复扫（`SCAN_PITCH_CYCLE_DEGREES = (-18, 55, -55)`）之后，用 §四 那条真实端点（`api.commandcode.ai`、deepseek-v4.1-flash）跑常驻目标 `hold 1×minecraft:oak_planks from minecraft:oak_log`，步数上限 10。逐字取自 run 文档 `run.autonomous.steps`：

1. `break_seen_block{expected_drop_item:oak_log}` → CONFIRMED（`source: model`，tick 852→994）。木头砍下、读数核对到位。
2. 第 2–4 步 `collect_dropped{oak_log}` 三连 `UNKNOWN / COLLECT_APPROACH_STALLED`（归因 `INSUFFICIENT_INFORMATION`）：掉落物滚到跟前但接近没收窄，背包始终没有 oak_log。
3. 第 5 步 `turn_to{-18,45}` CONFIRMED、第 6 步 `turn_to{pitch:90,yaw:0}` CONFIRMED——模型自己说「低头看掉落的 oak_log 好把它捡起来」，俯角这一动作是到位的。
4. 第 7–9 步模型连续 `TIMEOUT`，本地反射接管 `break_seen_block` 三连 `UNKNOWN / NO_CONFIRMING_OBSERVATION`（材料没进包，砍的又是不存在的目标）。
5. 第 10 步本地反射 `turn_to{-55,135}`（新复扫里的那一档）`FAILED / AIM_STALLED`，`excluded_skills:[break_seen_block,collect_dropped]`，`stop_reason: STEP_BUDGET_SPENT`，`goal_met: false`。

**这一发既没走到合成，也没走到放置**：卡在「把已掉落的 oak_log 收进背包」这一格。六之十四（第 756 行）早已把 `collect_dropped 在掉落物滚出可达时` 点名为候选卡点，本发把它重新量成真实端点下的活体卡点，且与目标产物无关。据此对六之十五「采拾确认不再是卡点」那句作一处诚实修正：那句只在 `run 9e01523a` 那一发运气下成立，同一份代码换一发世界布局就会回到接近 stall。

**复扫俯仰本身不足以解锁放置**：`c044de2` 的 `pitch:-55` 确实在第 10 步出现，却落在 `AIM_STALLED`（gap 不再收窄）。换俯仰角读到的是更多朝向，不等于稳定拿到 `BLOCK` 瞄准；放置前的瞄准获取是与复扫独立的一格问题。

**安全与有界这一格在真实端点上复现**：`input_release_failed: false`、`release{asked:[229],released:[229],unconfirmed:[]}`、`terminated:[229]`、`unresolved:[]`；`world_observations admitted:173 / refused:0 / stale_tick_dropped:0`；同类签名两次预算耗尽即排除、随后按步数上限自停，没有无限重试。

**具名的下一步（先诊断，不盲改）**：`collect_dropped` 的停滞判据在 `world_skills.py:749` 拿 `_drop_distance`（三维含竖直分量）与 `COLLECT_CLOSE_APPROACH_METERS` 比收窄。掉落物停在一到两格之下时，水平走动无法削减竖直分量 ⇒ 三维距离看着不收窄 ⇒ 误判 `COLLECT_APPROACH_STALLED`。这一假设需要一发带 `relative_x/y/z` 读数的活体确认，不在 run 文档里 ⇒ 不在本轮盲改判据。取 `current_next`＝「在真实读数上确认 collect 接近距离该按水平距离判还是按三维距离判，再按确认结果改 `world_skills.py` 的停滞判据并补单测」。

**不声明**：放置 `use_target` 的真实游戏确认仍未取得，保持 `UNKNOWN`；第 7 条按字面仍由六之十三（木棍连续闭环+确认松键）与六之九达成，本发不削减它，也不给 `goal_met` 或任何 `tested/CONFIRMED` 追加冒充。


## 六之十七、把接近判据改量水平距离后在同一真实端点重跑的那一发：砍→拾取→合成→关屏→选物→确认松键全链 CONFIRMED（2026-10-01，run `bfdc6011e4a84c6ab8c05e2a814d989d`，server run 目录 `run-29`，会话 `98b3c63fbe744c30a0566564cbd16d6a`，客户端 pid 338）

在 `3215c86`（`_drop_approach_distance` 取步行真正能收窄的那一维 `hypot(relative_x, relative_z)`，把停滞判据对齐到水平面）之后，用 §四 同一条真实端点（`api.commandcode.ai`、deepseek-v4.1-flash）跑常驻目标 `hold 1×minecraft:oak_planks from minecraft:oak_log`，步数上限 10。逐字取自 run 文档 `run.autonomous.steps`：

1. `break_seen_block{expected_drop_item:oak_log}` → CONFIRMED（`source: model`，tick 1572→1736）。木头砍下、读数核对到位。
2. `collect_dropped{item_id:oak_log}` → **CONFIRMED**（`source: model`，tick 1736→1857）——这正是六之十六同一目标下三连 `COLLECT_APPROACH_STALLED` 的那一格，改判这一发一步入包。
3. `craft_take_result{target_item:oak_planks, quantity:1}` → CONFIRMED（tick 1857→1945）。
4. `close_screen{}` → CONFIRMED（tick 1945→2110），模型读「已持有 4 块木板、超过所需的 1，关掉开着的合成窗」。
5. `select_hotbar{expected_item_id:oak_planks, slot:8}` → CONFIRMED（tick 2110→2220），把它选进手上。

`goal_met: true`、`stop_reason: GOAL_HELD_IN_HAND`、`autonomous.confirmed: 5`、`decision_source: model`、`model_calls: 5`、`model_enabled: true`、`model_spent_micro: 25`、`excluded_skills: []`。

**这一发把第 7 条按字面在活字节上从头走到尾、且每步由真实模型决策**：采集（砍）→拾取（入包 CONFIRMED）→合成（产物进背包）→成品确认（读数为据的 4 块木板）→关屏→后续非 GUI 世界动作（`select_hotbar` 选入手上）→确认松键。松键逐字为 `release{asked:[338], released:[338], unconfirmed:[]}`、`terminated:[338]`、`unresolved:[]`、`input_release_failed: false`、`outcome: STOPPED_ON_REQUEST`、`session exited 0`。

**对六之十六那句诚实修正的收口**：六之十六说「同一份代码换一发世界布局就会回到接近 stall」——那是三维判据下的旧字节。`3215c86` 之后，同一目标、同一端点这一发不再出现虚假 stall。要说清的边界：这一发证明的是**因竖直分量而误判的接近停滞**被消除了；掉落物真正滚出可达视野仍应走 `DROP_OUT_OF_VIEW`/有界自停，那条与水平还是三维判据无关，本发未触发，也不据此声称已活体确认它。

**仍不声明**：`use_target` 放置与 3×3 终产物（木镐）那一笔的真实游戏确认仍未取得，保持 `UNKNOWN`（见六之十五）。本发是单目标 `oak_planks` 闭环，不替代第 5 条「多个不同目标」的完整覆盖；第 5 条目前由本发（oak_planks 全链由 model 逐步决策）加六之十五（同一木镐目标下木板+木棍跨产物子链）共同支撑，3×3 终产物活体确认仍列为未完成。

**下一格 `current_next`**：把「立起工作台」做成本地反射的确定性通用序列（`larger_grid_needed` 且无更宽窗口可读时，补出「合成工作台→`select_hotbar`→`turn_to`/`use_target` 放置→打开→在 3×3 内合成终产物」，不写木镐专用链），再以真实端点跑一发确认持有木镐——这同时补上第 5 条的跨目标覆盖与 `use_target` 放置的真实游戏确认。

## 六之十八、把 3×3 那一笔交给真实模型自选、在同一真实端点上跑木镐的那一发：立起工作台序列逐步 CONFIRMED，唯独「放置」按契约诚实停在 UNKNOWN（2026-10-01，run `ab200996459e4564b9172ed4c52cba3e`，会话 `b951295ace30476ebbe066e1631c5eb5`，客户端 pid 335；另有并发的一发 `32470aba6334443c870014829ca3c85e` 因与上一发共用同一 demo2 数据根而 `CLIENT_EXITED`，见末段）

在 `28e1775` 之后，用 §四 同一条真实端点（`api.commandcode.ai`、deepseek-v4.1-flash）跑常驻目标 `hold 1×minecraft:wooden_pickaxe from minecraft:oak_log`，步数上限 16，不预设动作。逐字取自 run 文档 `run.autonomous.steps`：

1. `break_seen_block{oak_log}` → CONFIRMED（`source: model`，tick 1525→1703）。
2. `collect_dropped{oak_log}` → CONFIRMED（model，tick 1703→1833）。
3. `craft_take_result{oak_planks×4}` → CONFIRMED（model，tick 1833→2009）。
4. `close_screen{}` → CONFIRMED（这一帧模型 `TIMEOUT`，`source: local_reflection` 收尾，tick 2009→2185）。
5. `craft_take_result{crafting_table×1}` → CONFIRMED（model，tick 2185→2350）——模型自己判定「2×2 装不下木镐，先合成工作台」。
6. `close_screen{}` → CONFIRMED（model，tick 2350→2449）。
7. `select_hotbar{crafting_table, slot:8}` → CONFIRMED（model，tick 2449→2570）——把工作台拿在手上。
8. `turn_to{pitch:-18, yaw:45}` → CONFIRMED（model，tick 2570→2680）。
9. `turn_to{pitch:90, yaw:0}` → CONFIRMED（model，tick 2680→2878）——模型选择低头对准地面好把工作台放下。
10–12. `use_target{}` 三连 → **UNKNOWN**（`source: model`，归因 `INSUFFICIENT_INFORMATION`，tick 2878→3120）。
13. `break_seen_block` → UNKNOWN（`NO_CONFIRMING_OBSERVATION`）。
14. `turn_to{-55, 135}` → FAILED `AIM_STALLED`。
15. `break_seen_block` → UNKNOWN。
16. `turn_to{0, 90}` → FAILED `AIM_STALLED`；`stop_reason: STEP_BUDGET_SPENT`、`goal_met: false`、`excluded_skills:[use_target]`。安全收尾：`input_release_failed: false`、`outcome: STOPPED_ON_REQUEST`、`session exited 0`。

**这一发把「立起工作台」从纸面推到活体，且每一步由真实模型自选参数**：模型没有等本地反射，而是自发走完了「砍→拾→合成木板→关屏→合成工作台→关屏→选入手上→转身→低头」这条通用序列，前九步读数全 CONFIRMED。据此更正总规划里「缺确定性立起工作台、完全交给模型自选」那句：`38–41` 号卡已把该序列（`crafting_grid_side` 从开窗读有效边长、`owed_steps` 把工作台预留成自有步、`step_to_run` 把装不下的合成重路由到能付的更宽步、`use_target` 放置→打开）实现并单测通过；本发进一步显示连模型自发路线也能一路走到放置前。

**卡点精确落在「放置」这一格，且系统按契约诚实停在 UNKNOWN**：`verify_use_effect`（`domain/world_actions.py:403`）只认两种确认——（a）后置读数里新开出一个前置没有的窗口，或（b）手上物品在两帧已同步读数里总量减少（放下一个就少一个）。第 9 步模型把视角转到 `pitch:90` 直对脚下，而工作台放不下玩家自身占据的那一格 ⇒ 既无减量也无开窗 ⇒ 三连 UNKNOWN。`_inventory_synced` 要 revision 先移动才肯认这是服务器的变化而非一厢情愿，所以判 UNKNOWN 是对的：第 7 条明令「UNKNOWN 不得转述为 CONFIRMED」，本发守住了这条地板。

**因此仍不声明**：`use_target` 放置与 3×3 终产物（木镐）的真实游戏确认仍未取得，保持 `UNKNOWN`；第 5 条「多个不同目标」里需要 3×3 的那一笔仍未活体 CONFIRMED。要说清的是**卡点性质已变**：不再是「缺机制」，而是「模型自发路线把放置瞄到了自己身上」——这是真实模型的瞄准/覆盖选择问题，不是逐物品接口的缺失。方向是让放置那一下落在**空的相邻面**（不把准星压进脚下占位格），放置按减量 CONFIRM 后再以一次 `use_target` 打开 3×3 并在其中合成 `wooden_pickaxe`，全程复用同一套通用技能，不新增产物专用链。

**并发撞库这一发不产品记账**：同一时刻我误起了第二发（`32470aba…`，客户端 pid 346、会话 `82cd0f5b…`），两发共用单卷 demo2 的同一 Kin 数据根，第二发的客户端 JVM 在第一首发收尾时被带走，记为 `stop_reason: CLIENT_EXITED / BRIDGE_LOST`、`input_release_failed: true`、`session exited 14`。这是编排/操作层面的自伤（单卷同一时间只能独占跑一发），不是产品缺陷，也不拿它当 `use_target` 的第二个证据；保留此记录以如实记撞库事实，不据此改动产品结论。

**下一格 `current_next`**：单次、独占 demo2 数据根地重跑木镐一发，让 `use_target` 放置落在空的相邻面（俯角不把准星压进自己脚下占位格）；放置若按减量 CONFIRM，则紧接第二次 `use_target` 打开 3×3 并合成 `wooden_pickaxe`，全链由真实模型决策并逐字入账。通过则记第 5 条跨目标 + 第 7 条 3×3 收尾 CONFIRMED，未通过则继续记 UNKNOWN，不美化。

## 六之十九、第二个不同终产物（木棍）在同一真实端点由通用行为逐步确认的那一发：砍→拾取→合成→合成→关屏→选物入手→确认松键 全链 CONFIRMED（2026-10-01，run `da6b72d7f2794e29bfff9e387bfe1cfc`，会话 `48baf6686b38405a943bf16a951e4ff6`，客户端 pid 310，server run 目录 `run-32`，boot_mode `cache_hit`）

目标 `hold 1×minecraft:stick from minecraft:oak_log`，步数上限 10，同一条真实端点（`api.commandcode.ai`、deepseek-v4.1-flash），复用已填充的 demo2 卷。逐字取自 `run.autonomous.steps`——六步全部 `result: CONFIRMED`、全部 `source: model`：

1. `break_seen_block{expected_drop_item:oak_log}` CONFIRMED（tick 1337→1502）。
2. `collect_dropped{item_id:oak_log}` CONFIRMED（tick 1502→1590）——水平接近判据（`3215c86`）下这一步一步入包。
3. `craft_take_result{target_item:stick, quantity:1}` CONFIRMED（tick 1590→1722）。
4. `craft_take_result{target_item:stick, quantity:1}` 再一次 CONFIRMED（tick 1722→1810）——模型自陈「木棍可由已在背包的木板合成」，因单次合成只出 2 根而再合成一笔；这是同一通用技能按读数自适配，非木棍专用链。
5. `close_screen{}` CONFIRMED（tick 1810→1909），模型读「已持有 4 根木棍、超出所需 1，关掉开着的合成窗」。
6. `select_hotbar{expected_item_id:stick, slot:7}` CONFIRMED（tick 1909→2019），把它选进手上。

`goal_met: true`、`stop_reason: GOAL_HELD_IN_HAND`、`decision_source: model`、`model_enabled: true`、`model_calls: 6`、`autonomous.confirmed: 6`、`excluded_skills: []`、`model_spent_micro: 26`。安全与有界：`input_release_failed: false`、`release{asked:[310]}`、`terminated:[310]`、`unresolved:[]`、`outcome: STOPPED_ON_REQUEST`、`connection_state: PLAYABLE → session_state: STOPPED、status: ended`；`world_observations admitted:73 / refused:0 / stale_tick_dropped:0`。

**这一发把 #5「多个不同目标」补成两枚不同终产物、均由同一套通用参数化行为承接并逐步真实读数确认**：`oak_planks`（六之十七 run `bfdc6011…`）与本发的 `stick`，同一 Core、无按物品专用模块；`#7` 的连续链「采集→拾取→合成→成品确认→关屏→后续非 GUI 世界动作（选物入手）→确认松键」在第二枚产物上原样复现。

**边界不越**：本发刻意取 2×2 玩家格可合成的终产物，不涉及 `use_target` 放置与 3×3 开窗。需 3×3 的终产物（木镐）那一笔的真实游戏确认仍未取得、保持 `UNKNOWN`（见六之十八：机制已实现+单测通过、模型已自选到放置那一步，但把方块瞄准进自己脚下），本发不替代、不削减它，也不据此给 `use_target` 追加任何 CONFIRMED。

## 六之二十、用全新 Kin 根在冷启动 bundle 上再跑木镐那一发：放置三连 UNKNOWN，以及由它引出并已落地的"同靶不重放"通用护栏（2026-10-02，run `37368eba6634471cbbd2f5ad07b64596`，会话 `ddc4bfd73c7a42e1ae9278c3960baaa5`，客户端 pid 1297，server run 目录 `run-34`，Kin 根 `kin-3x3-fresh-20261002`，boot_mode `cold`）

这一发用 §四 那条真实 OpenAI-compatible 端点，在一枚**全新初始化的 Kin 根**上冷启动跑，为的是把「放置」这一格在干净、独占的条件下再取一次读数，并顺带验证收尾松键的实测形状。

1. **独占单 Kin 根下的干净复跑**：Kin 根 `kin-3x3-fresh-20261002` 是这一发新建的（不是复用 kin-01/kin-local-demo 那种带死进程标记的旧根），所以同一 demo2 卷上不撞 `OLD_CLIENT_UNPROVEN`；`recovery.status: reconciled`、`invalidated: []`、`waiting: []`。收尾行按第 4 条要的实测读数入账：session stop 的 `release` 写了 `asked [1297] / released [1297] / unconfirmed [] / nothing_held []`，另有 `terminated [1297]`、`unresolved []`——松键的 `released` 是一格实打实的读数，不是只凭 `asked`/`terminated` 判成，`unconfirmed` 空着也如实读出。
2. **材料子链与转身 CONFIRMED**：第 1–6 步 `break→collect→木板→工作台→关屏→break` 连着 CONFIRMED；第 7 步 `collect` `FAILED / NO_SEEN_DROP`（归因 `RESOURCE_UNAVAILABLE`）；第 8 步本地反射 `select_hotbar{crafting_table, slot 8}` CONFIRMED；第 9–11 步 CONFIRMED；第 12–13 步 `turn_to` 转身、低头 CONFIRMED。`confirmed: 12`。
3. **卡点仍精确落在放置三连**：第 14/15/16 步 `use_target{}` 连续 UNKNOWN（`source: model`，归因 `INSUFFICIENT_INFORMATION`，observation_ref 依次 9398→9497→9574→9673）。三下 `use_target` 之间没有插入任何会改变准星的 `turn_to` 步——也就是模型对着同一瞄准结果连按了三下，正是目标明令禁止的"不停重跑赌模型选对角度"。跑满 16 步额度收尾：`goal_met false`、`stop_reason STEP_BUDGET_SPENT`、`excluded_skills ["use_target"]`、`input_release_failed false`、`outcome STOPPED_ON_REQUEST`、`session exited 0`。
4. **一处必须说清、以免把第 9/10 步误读成 `verify_craft` 假阳性**：那两步的 INTENT 写着 `craft_take_result{target_item: minecraft:wooden_pickaxe}`，模型以为自己在直接出木镐，但 `verify_craft` 只认"材料全降 + 产物上升 + revision 已移动"。这一发 `goal_met` 恒 false ⇒ 背包里 `minecraft:wooden_pickaxe` 总量始终 0 ⇒ 那两步 CONFIRM 的**不可能是木镐本身**，而是 `step_to_run` 在当时 2×2 网格里挑出的、装得下的那道欠料；`arguments.target_item` 只是模型的诉求，真正点下的配方是首个能付的欠步。所以这两格 CONFIRMED 合法，把它读成假阳性反而是错的。
5. **由这一发引出并落地的 `#48` 通用护栏**：`domain/world_actions.py` 新增 `use_target_signature(obs)`，把准星读成可比较的签名（方块 =(kind,x,y,z,face)、实体 =(kind,observation_id)、MISS/未读到=None）；`application/player_mind.py` 记住上一次**真正发出**的 `use_target` 所瞄签名 `last_use_aim`，当准星仍指向同一目标且候选技能不止一个时，把 `use_target` 从可行集剔除、转去 `turn_to`/`break` 这类能改变世界读数的动作；任一 CONFIRMED 步清空该记忆，所以准星一旦挪到新方块仍照常尊重。它不新增木镐专用步、也不靠改断言让三连变绿，只是不再允许对同一靶点空按。domain 与 mind 各补单测（同靶第二下不再 use_target、挪靶后重新尊重、CONFIRMED 清空记忆、签名对坐标/面/实体 id 的判别与 MISS→None）。`153` 项目标单测通过，`ruff check`/`ruff format` 干净，落在主干 `main@704eae2`。

**仍不声明**：这一发没取得 `use_target` 放置的真实游戏 CONFIRM，也没让 3×3 终产物（木镐）入包——`#48` 消除的是"同靶空按三连"这种浪费，把模型从重复点击推向先改变瞄准，但放置落在空相邻面→开窗→在 3×3 内合成终产物这一笔的活体确认仍未取得、保持 `UNKNOWN`。护栏本身目前只有单测覆盖，尚未在一发真实端点运行里观察到它把某一步从"重复 use_target"改判为别的技能——那要在下一次独占复跑里逐字入账。

**下一格 `current_next`**：单次、独占 demo2 数据根地再跑一发木镐，观察 `#48` 护栏是否在第 N 次同靶 UNKNOWN 后把 `use_target` 换成 `turn_to`/`break`，从而让准星落到空的相邻面；放置若按减量 CONFIRM，则紧接第二次 `use_target` 打开 3×3 并合成 `wooden_pickaxe`，全程复用通用技能、逐字入账。通过则记跨目标 + 3×3 收尾 CONFIRMED，未通过继续记 UNKNOWN、不美化。

## 六之二十一、护栏 `#48` 落地后在独占新 Kin 根上再跑木镐那一发：本轮根本没有 `use_target` 可挡，卡点上移到"上一级欠步先把 enabler 的材料吃光"（2026-10-02，run `ad147dd4987a40a9bf5d42ccca3b21c0`，会话 `0a2de209f92d48989288fefc2d7058d8`，客户端 pid 1198，server run 目录 `run-35`，Kin 根 `kin-3x3-guard-20261001-195907`，boot_mode `cold`）

这一发仍走 §四 那枚真实 OpenAI-compatible 端点，在一枚新建、独占的 Kin 根上冷启动跑木镐，本意是观察 `#48` 是否会在同靶 `use_target` 连吃 UNKNOWN 后把该技能换掉。实读之下，这一发暴露的是一个更靠前、且与 `#48`/`#44` 都不同的卡点，逐字入账如下。

1. **`#48` 本轮没有触发面，也就谈不上验证**：整条 `steps` 里一次 `use_target` 都没有出现（14 步全是 `break→collect→木板→关屏→木棍→关屏→转身×8`），所以既没被护栏挡住、也没漏放——这一发不能算作对 `#48` 的正例或反例，只能说明失败发生在"能不能走到放置"之前。护栏目前仍只有单测覆盖。
2. **松键实测读数（第 4 条要求）再次到手**：收尾 `session stop` 的 `release` 写了 `asked [1198] / released [1198] / unconfirmed [] / nothing_held []`，另有 `terminated [1198]`、`unresolved []`、`input_release_failed false`、`outcome STOPPED_ON_REQUEST`、`session exited 0`。`released` 是实打实的一格，不是凭 `asked`/`terminated` 判成，`unconfirmed` 空着也如实读出。
3. **卡点精确定位在 enabler 预算被吃光**：第 3 步 1 原木→4 木板 CONFIRMED，第 5 步 `step_to_run` 按欠序先出了木棍（2 木板→4 木棍），背包遂只剩 2 木板、4 木棍、0 原木、0 工作台。对着 `feasible_skill_ids` 在 2×2 下逐项读：`craft_take_result` 不再可行——工作台要 4 木板（只剩 2）、木镐要 3×3（无窗）、木板要原木（已空），`craft_options` 空；`use_target` 不可行（准星已不在方块上，且手里根本没有可放置的 enabler）；`select_hotbar` 不可行（终产物与已持 enabler 都不在包）；`break/collect` 在转身扫视后无块无落物 ⇒ 只剩 `turn_to`。于是第 12–14 步 `turn_to` 连吃 `AIM_STALLED`、`turn_to` 被排除，`stop_reason NO_FEASIBLE_SKILL`、`goal_met false`、`confirmed 11`。
4. **与六之二十（`37368eba…`）的对照说明这是通用规划问题，不是模型运气**：同一份代码、同一目标，那一发在背包仍有 4 木板时先合成并选中了工作台，从而走到了放置（停在 UNKNOWN）；这一发模型先把木板花在了木棍上，使工作台再也付不起，整条 3×3 路在放置之前就断死。差别不在接口缺失，而在 build 顺序/可行性允许一道低阶欠步（木棍）把高阶 enabler（工作台）仍需的共享材料（木板）提前吃光。

**仍不声明**：这一发未取得任何放置或 3×3 木镐的真实游戏 CONFIRM，目标保持 UNKNOWN/未达（不是 FAILED——`verify_craft` 下限本就是 UNKNOWN）；`#48` 既未被证实也未证伪。

**下一格 `current_next`**：先读 `domain/recipe_catalog.py` 的 `build_plan` 与 enabler 预留次序，判明"被预留的 3×3 enabler（工作台）这一道欠步，排在共享材料（木板）的低阶欠步（木棍）之前还是之后"，以及可行性是否应先把 enabler 的料价预留出来；只有据这份读法，才谈得上"通用放置目标选择与前提校验"更靠前那一环的通用修法——不重跑赌模型、不加木镐专用步、不改断言凑绿。

## 六之二十二、复用已填 Kin 根跑 `--again` 那一发：把「应用重启/复用」「正常 stop」「任务恢复」三件事在活体上分开入账（2026-10-02，run `8c6197a32d4d46cb9ad53612c0e2fe33`，会话 `3a115705e9ec4e648606208ba413d24c`，客户端 pid 295，server run 目录 `run-36`，Kin 根 `kin-3x3-guard-20261001-195907`（复用六之二十一那一发刚填满 store 的同一根），boot_mode `cache_hit`）

这一发对应完成度审计的第 3 条：正常 session stop ≠ 异常断连测试，重启读回配置 ≠ 任务恢复。做法是用无模型 `--again` 在上一发（六之二十一）刚填满 store 的同一 Kin 根上重跑脚本走，专门取「重启/复用」相对「正常 stop」「任务恢复」的活体区分读数，全程不耗模型预算。

1. **store 复用读数**：`boot_mode cache_hit`、`fetch_set 3639 / reused 3639 / installed 0`——bundle 未再下载即直接进入世界，`auto_bundle.status ready`。这正是与冷启动（六之二十一 `boot_mode cold`）相对的那一侧。
2. **会话机与收尾实读（正常取消/stop 再次活体确认）**：`connection_state PLAYABLE → session_state STOPPED`、`outcome STOPPED_ON_REQUEST`、`input_release_failed false`、`session exited 0`；domain 逐行「the session is playable」「the server saw the Kin walk and stop」「stopping the session」。松键按第 4 条要的实读入账：`release asked[295] / released[295] / unconfirmed [] / nothing_held []`，另有 `terminated[295]`、`unresolved []`、`left_alone []`——`released` 是实读非推断。
3. **「重启/复用」与「任务恢复」的活体区分（核心）**：`recovery.status reconciled`、`invalidated []`、`waiting []`，且 `autonomous null`（这一发是脚本走，没有把上一发的木镐目标接过来自动重跑）。⇒ 编排层对着已持久化的 store/会话重启时，做的是核对/收尾既有会话，既非静默重连（`reconciled` 而非 reconnect），亦非静默重放目标动作（`autonomous null`、无 goal 续跑）。这就是「重启读回配置 ≠ 任务恢复」在活体上的样子。
4. **两处诚实保留，不能拿这一发冒充已全验**：
   - 显式恢复的非空失效子情形（对一枚因非正常收尾而死掉的进程标记做 `invalidated`/`waiting` 回收）本轮是 `invalidated []/waiting []`，因为上一发是 `exited 0` 的干净收尾；非空失效只在 wrapper 被杀 / PID 复用留死标记时自然出现，而那会撞 `OLD_CLIENT_UNPROVEN` 拒起新 run，不在这一发能按需复现——不伪造。
   - 异常断连（传输掉线 / `BRIDGE_LOST`，与 `STOPPED_ON_REQUEST` 相区分）这一发没有触发；harness 把双开同存档判为 artifact、无干净的按需掉线旋钮，该路径目前只有代码 + 单测层的区分（#8 已闭合），活体逐字读数仍缺。

**仍不声明**：不据此判 #46 全绿。这一发（`8c6197a3…`）自身只取到「正常取消/stop」与「应用重启/复用＝核对非重放」两路读数，未触发后两路。就全局账目而言：「异常断连」早有一枚活体分类读数（第五节第 6 条那一发：`stop_reason CONTROL_CHANNEL_LOST`、`outcome BRIDGE_LOST`、`input_release_failed true`、`unconfirmed [290]`，与正常 stop 的 `unconfirmed []` 成对照），只是由 harness 拆通道触发、非游戏内自发掉线，触发保真度列为保留项；「非空失效的显式恢复」仍只有设计面（重启断言刻意不要求 `invalidated` 为空）与 `invalidated []` 的读数，真正非空的活体读数仍缺。

**下一格 `current_next`**：要么在受控条件下取一次非空失效恢复读数（先接受一次非正常收尾并据其死标记做 reconcile，且不删旧失败材料），要么给异常断连找一个产品级、非 artifact 的按需触发面后再逐字入账；两者都不与 #50/#47/#4 的保留设计决定混做。

## 六之二十三、用户选定的 Option 1：确定性 `--skills` 计划活体一发，如实停在第二次采集、3×3 终端合成仍保持未达（2026-10-02，run `87d078cf5da2478b85a49ffd211641ef`，会话 `6a4646fbffe44d929adaca2e6c4c1508`，客户端 pid 340，server run 目录 `run-37`，Kin 根 `kin-3x3-fresh-20261002`，boot_mode `cache_hit`，计划文件 `examples/skill-plan-table-and-pickaxe.json`）

这一发对应#50 的通用修法方向：用户明确选了 Option 1——不改契约、只用运营者手写的通用技能确定性计划（`turn_to/break_seen_block/collect_dropped/craft_take_result/close_screen/select_hotbar/use_target`，无木镐专用步）在活体上试一次 3×3 木镐终端。做法是先离线解析该计划（`uv run python`，21 步全部可解析、能力集合不越其点名范围），再在已填 store 的同一 Kin 根上 `--skills` 跑一发，不靠反复重跑赌模型选对角度。

1. **计划落盘与离线可解析**：`examples/skill-plan-table-and-pickaxe.json` 是这份可复现组合的持久载体；`tests/unit/test_skill_plan.py` 的能力上界断言新增 `USE_CAPABILITY`（105-111 注册表本就含 `control.use.v1`，这是第一枚使用 `use_target` 的已提交示例，属刻意且正确的设计对齐，非改断言凑绿）。36 项单测通过，`ruff format --check` 与 `ruff check` 干净。
2. **活体逐技能实读（`skill_plan` 首非 CONFIRMED 即停，§4 无重试）**：`skills` 记到 5 步——`turn_to CONFIRMED`(1382→1392)、`break_seen_block CONFIRMED`(1392→1462，第一根橡木)、`collect_dropped CONFIRMED`(1462→1494，steps=1)、`turn_to CONFIRMED`(1494→1505)、第二次 `break_seen_block` **FAILED / `MINE_TARGET_NOT_AIMED`**(1505→null)。`skill_stop: break_seen_block`。⇒ 计划连采集阶段第二根都没走完，合成/放置/开窗/3×3 一步都未触及。
3. **这根停在采集而非放置，说明的是通用问题定位，不是模型运气**：固定射线只破它正下方那一格；第一根倒树后，脚前方残柱的行进/拾取已改变了十字准星下的目标，第二次 `break_seen_block` 对着未对准的角即按 §4 停。这正是#50 已把缺口定位到的「再采集/对准」通用边界——修它要么对准随目标自动重取，要么在采集里带上让目标重新进入射线的步长；不是加木镐专用步、也不是反复重跑赌角度。这一发只跑一次即如实入账。
4. **松键与收尾实读（第 4 条审计要的实际读数）**：`session exited 0`、`outcome STOPPED_ON_REQUEST`、`input_release_failed false`；`release asked[340] / released[340] / unconfirmed []`——每路被按住的输入都在客户端下一 tick 得到释放确认，非只凭 `asked`。`recovery.status reconciled`、`invalidated []`、`autonomous null`。

**仍不声明**：这一发未取得任何放置或 3×3 木镐的真实游戏 CONFIRM；`#50` 的 3×3 终端保持 UNKNOWN/未达，`use_target` 的放置CONFIRM 路径此前也只在 `verify_use_effect` 下限=UNKNOWN 的意义上存在。不据此判 #50/#48 通过，也不把 UNKNOWN 转述为 CONFIRMED。

**下一格 `current_next`**：#50 的通用修法方向已用一枚活体读数钉死在「多目标采集时十字准星未随残柱自动重取」这一环。下一步读 `domain/recipe_catalog.py` 的 `build_plan` 与 enabler 预留次序之外，改把焦点放在 `collect_dropped`/`break_seen_block` 之间的对准交接：判明采集走完后目标射线是否应自动重新对准（而非要求下一条 `turn_to` 用固定角再赌一次），据此才谈得上通用放置目标选择与前提校验更靠前那一环；仍不重跑赌模型、不加木镐专用步、不改断言凑绿。


## 当前接管验证（2026-10-03，main@d87ce87）

本地规则复验 run `ebe69cbe59ee48f0aa728865ac4f0b7f`，会话 `40ec626749dc4f8985bc4e5cbce3225d`，demo2 卷同一 Kin 根，server `run-44`。24 步中 21 步 CONFIRMED：前 15 步完成两轮采集、木板/木棍/工作台并选中工作台；第 17–19 步拾取返回 `NO_SEEN_DROP`，随后到 `STEP_BUDGET_SPENT`，未完成 3×3。`model_calls=0`、来源 `local_reflection`；收尾 `STOPPED_ON_REQUEST`，不是真实模型成功，也不是 sealed evidence。第一次 `run-43` 在 CLI 因 32 超过 24 步上限被拒，未入服，不计入能力验证。

定向回归复现：仅看到泥土掉落物时，PlayerMind 的拾取 offer 可行，却无条件填写 milestone 的橡木资源，必然 `NO_SEEN_DROP`；新测试先红。修复按同一可见观察选物品：目标资源可见时优先它，否则选择最近的可见掉落物。该修复是确定性参数缺陷，不声称已证明 run-44 三次拒止的物品种类（该 run 未记录逐步观察内容）。下一步核对放置前的通用目标选择，再按当前字节复验；不重复跑旧字节赌成功。


修复后第二次本地规则复验 run `44026f957f784438bd6cd7290bae5e86`，会话 `cb67650994224f2cbc2f5961cf9aadd1`，server `run-45`：17 步 CONFIRMED，含第 16 步 `use_target` 和随后关屏；最后 `NO_FRESH_OBSERVATION`，`goal_met=false`。观察计数 `admitted=52 / refused=16`，拒收全部 `YAW_OUT_OF_RANGE`，收尾 released `[317]`、unconfirmed `[]`、`STOPPED_ON_REQUEST`。Bridge 原样发送 Minecraft 的累计 yaw；跨 ±180 后角度合法但线格式不合法。`LookAngles.of` 现在将有限 yaw 归一为 (-180,180]，拒绝非有限值，pitch 保持原读数；角度回归先红后绿，完整 Bridge test/build 与产物权限边界检查通过。

新候选 jar/source 摘要已同步 recipe 和 Launcher pin；旧 registry 的 sealed 引用保持不变。当前默认 auto-bundle 会因旧证据摘要与当前构建不符而拒止，验证使用显式候选入口：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar \
MINEKIN_DEMO_VOLUME=minekin-local-demo2 \
MINEKIN_DEMO_KIN=kin-3x3-fresh-20261002 \
MINEKIN_DEMO_BUNDLE_PROFILE=/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json \
MINEKIN_DEMO_AUTONOMOUS_STEPS=24 \
MINEKIN_DEMO_AUTONOMOUS_WAIT_SECONDS=420 \
  bash test-orchestrator/runner/demo.sh --autonomous
```

首次候选 `run-46` 因 Launcher pin 尚未同步，在入服前供应链拒止（exit 11）；现已同步并通过 36 项 recipe/Bridge 契约回归。该拒止不是游戏能力失败，不计入成功验证。交互技能还补了“新帧先到、效果稍后到”的有界等待：一次点击后继续观察至确认或原截止，不追加点击；203 项 Core 回归通过。


当前候选新 Bridge 的两次复验：`28677cd3a3784060b87f34218d9b6158`（server `run-47`，24 步）接纳 84 帧、拒收 0，21 步 CONFIRMED，含放置/交互；拾取三次 `COLLECT_APPROACH_STALLED`，最后预算耗尽。`b41b87c69c994c4c95f5879ff0629d84`（server `run-48`，显式 48 步）接纳 164 帧、拒收 0，35 步 CONFIRMED，重新锁定资源未成，随后 `AIM_STALLED` 与关屏失败，按 `NO_FEASIBLE_SKILL` 正常停止。两发 `goal_met=false`、模型调用 0；不能声称 3×3 成功。yaw 拒收在当前候选字节下消失，更多预算仍不替代目标恢复。

后续修复将有界资源回看补到 ±85°，覆盖靠近树干的头顶方向；只有新的客户端准星命中才恢复挖掘，不推断隐藏邻格。陡角回归在旧扫视上失败、新扫视上通过，相关心智/自主循环 108 项通过。显式自主步数现在 1–64，默认 24；循环预算4/48均准确截止。下一条可执行任务仍是当前候选通用 3×3 复验与真实观察下的拾取/放置恢复；真实模型与异常恢复随后继续。


陡角修复后 run `ab02dd30a7a54d72bd9347ed96cd80b1`（会话 `3c0419a66be5410092e4eb8166a552d9`，server `run-49`）接纳203帧、拒收0，45步CONFIRMED。第三次采集在第25–26步CONFIRMED，随后三次木板合成UNKNOWN，最后48步预算截止；正常停止，未完成3×3，模型调用0。客户端日志明确三次都发送 `recipe minecraft:oak_planks` 与 slot0 quick-move。按真实调用缝隙复现并修了两项：拾取先等待已观测的行走朝向再前进；结果槽先等待同一handler内同步材料移入网格，忽略先到的无变化帧，换窗/关窗则停止。不重发配方点击。自主步骤文档现保留执行器原有details，以便后续直接读取库存revision、点击阶段和最新tick。227项相关回归通过；下次真跑使用本次字节，不能以旧run替代。


最新时序修复后 run `acbdd60afe574bebaa21cdbcf9f08ee3`（会话 `c7e8a1c936734b6bb6c3db456b4ce3ff`，server `run-50`）：204帧接纳、0拒收，47步CONFIRMED；四次2×2合成均CONFIRMED，details显示 `recipe_fill+result_quick_move` 与库存revision前进。拾取一次 `COLLECT_AIM_NOT_CONFIRMED` 后库存自然拾入，计划继续；工作台交互sync1已确认，但第三根资源未重新获得，48步截止，goal仍false、model_calls=0。据此修正上一轮过早设置网格的排序：仅当剩余材料已支付、catalog blocker为 `CRAFT_GRID_TOO_SMALL` 时优先use；材料仍欠缺则继续通用采集/回看。新回归在过早设置的代码上红、修复后绿。`tools/summarize_demo_run.py <log>` 可直接输出每步来源/结果/details；不输出配置或模型理由，缺完成文档时退出2。


材料先行复验 run `d5a611ddeec04e13b8d10d37474abef5`（会话 `57a84455299a42488ca19e6ca69e185b`，server `run-51`）：三次采集后的五次2×2合成CONFIRMED，第20步use开窗sync1 CONFIRMED；第21步本地规则立即关窗，随后试做重复工作台而非终产物，三次停在 `clicks=recipe_fill`，48步截止。205帧接纳、0拒收，goalfalse、model_calls0、正常松键停止。根因在 `_reflect` 的关窗优先级：有宽网格可支付当前目标时仍先关窗。真实交接回归“持enabler→use→更晚3×3读数→终产物合成→关窗”在旧代码红；修复优先复用该宽网格的当前目标步骤，完成后仍关窗。另外自然拾入背包的后续同步读数现在可确认拾取，即使转向未完成；换成另一handler时不点击它的slot0。230项相关回归通过，终产物的当前字节真跑仍待执行。


通用3×3首条实际成功（当前代码 `f5b7d52`）：run `55a59985a6f642f79ec9771ba25ee75b`，会话 `48e49512f9a8439181a9834cd9c8f6bd`，server `run-52`。21步全部CONFIRMED，三次采集、五次2×2中间合成、工作台use开窗sync1，以及第21步3×3终产物合成（库存revision1387→1409）均由后续读数确认；`goal_met=true / GOAL_HELD_IN_HAND`，66帧接纳、0拒收、`STOPPED_ON_REQUEST`，释放实读无unconfirmed，退出0。来源为local_reflection、model_calls0，不是LLM成功或sealed evidence。此发成品进入已选槽位使循环在GUI尚开时提前成功，因此补关窗收尾：目标在手且GUI打开时只允许close_screen，循环要在关窗确认后才成功；对应真实循环回归先红后绿。231项相关回归与静态检查通过；下一步为同字节真实模型与GUI收尾复验。


真实模型当前字节复验（main@b13eaba）：run `94b6cc2d7d9a4040b856e023bc7a1bd5`、会话 `3d9e4c6f929a4670a2c04f723ecaeda5`、server run-53。40次真实调用、35步CONFIRMED、489帧接纳/0观察拒收，但goal_met=false、NO_FEASIBLE_SKILL；含local_reflection回退，不是纯模型成功。工作台交互后模型选择挖掘被GUI_CONFLICT拒绝，三次关窗客户端报DEADLINE_EXCEEDED：授权原按48×5秒计算，漏了模型调用等待。新增回归复现240秒不足，修为每步“动作等待+已配置模型超时”；off路径不扩展授权。62项定向测试、ruff/pyright通过；修后真跑尚待。正常STOPPED_ON_REQUEST、input_release_failed=false，无sealed登记。

真实模型复验入口已跟踪，读取.env字面赋值而不执行shell，只把模型配置及所引用密钥传给子进程；本次启用仅对子进程生效。示例：

```powershell
uv run python tools/run_real_model_demo.py --log .tmp/model-demo.log --bash D:/env/Git/bin/bash.exe --steps 48 --cost-cap-micro 10000
```

账本单位与估算费率来自model_access契约，不能将上限直接宣称为供应商实际账单金额。此入口不改配置文件、不打印密钥，普通日志与sealed证据分开。

模型等待期间的观察变化也有独立回归：请求turn_to后GUI在模型返回前打开，旧循环仍执行世界动作；新循环按最新可行集将该步记为INTERRUPTED/DECISION_PRECONDITION_CHANGED并重新规划，不发送已不适用动作、不消耗技能失败重试。仅tick前进不拒绝，物品/位置参数仍由技能实际前提核对。181项心智、闭环、CLI与技能回归通过；授权修复与观察重验待合并后的本地模型复验。

全量回归首次在Windows误用System32/WSL bash，产生116失败，已用Git Bash路径重跑。期间发现候选recipe变更遗漏manifest摘要，现同步且W00与8项fixture边界通过。旧reviewed registry与当前Bridge摘要不一致仍是已知的默认自动入口/历史provenance拒止，未篡改历史记录。摘要工具新增actions_applied/refused、松键结果、模型账本和来源计数，避免把“观察拒收0”误当作“动作拒绝0”；--compact仅显示末5步，省略模型理由与配置。

授权与重验修复后run `dbe851f882104d1f98deae08a6ee6d0f`（会话e35bb68fb262422fa05de0269283741e、server run-54）48次真实调用、47步CONFIRMED、397帧接纳/0拒收，正常松键停止；47步来源model、1步local_reflection，goal_met=false/STEP_BUDGET_SPENT。后半程反复打开、关闭工作台（末次sync17），3×3关窗已CONFIRMED，未完成终产物。针对停滞补模型观察：当前绝对yaw/pitch、GUI状态、显式curated_catalog材料计划和最近6个实际结果；空材料容器的同靶重开在库存内容不变时撤出可行集，材料或靶变化可恢复。两条回归先红后绿，183项相关测试通过；不是新物品脚本，当前目录边界不扩大。新模型路径待真跑。

本机代理造成模型假端点两项失败（原应是断连/超时却报502）：模型适配器现对真实回环地址直连，远端端点保持原代理路径。回环判断改为解析IP，127.example.com等外部域名不再获明文HTTP例外；两条安全回归先红后绿，全部102项模型配置/端点测试通过。静态检查通过，密钥仍不记录、不随重定向转发。

Windows后台脚本测试的两项失败来自Git Bash包装器把自带curl插到PATH最前，导致测试触及真实网络而非curl替身。测试入口现在在shell初始化后重置替身优先级，并优先真实bash解释器以覆盖子脚本；产品脚本不改。4项启动/错误/清理/浏览入口测试通过，ruff/format通过。历史registry与当前候选的构建差异仍单列，未用测试变通隐藏。

模型run-55 `3090f05f8d3545c796dfd691a26738d7`（会话f8c49a33973f402999c0f515f72a2609）48调用、42步CONFIRMED、675帧接纳、正常松键，goal未成；空容器反复开关已停止，但第三原料后的三次oak_planks填充UNKNOWN。检查本地Yarn Minecraft字节码：HandledScreen.removed仅onClosed，正常close另调用ClientPlayerEntity.closeHandledScreen并重置处理器/通知服务端；Bridge原setScreen(null)跳过后者。现按currentScreen.close正常路径关闭1.20.1窗口。Java21 test/build及源/工件边界通过；新jar 0c8adfb7…、source fc0e4850…，candidate与Launcher pin及fixture manifest同步，51项契约/配方测试通过。1.21.4未改，旧sealed/registry不改；新字节游戏复验待做。

后台技能步现在把INTERRUPTED显示为“已中断”，把观察变化、拾取朝向未确认、等待截止、GUI占用等原因加上简洁说明并保留原token；字段称“结果原因”，避免把重新规划当动作失败。5项组件回归及生产构建通过；此前完整232项前端测试、160项恢复/松键/模型回归通过。启动/暂停/恢复仍未交付，本项不代替后台完整交付。

新关闭路径模型复验run `81ccd77af0df4b8ba330f33cb67fdcd8`（会话f0e60c2a22d844cbba9bd8ffe871bdd6、server run-56）20模型调用、17步CONFIRMED，正常停止，goal未成；不是容器修复失败的直接证据：服务端18:03:35明确“Kin was slain by Slime”，随后死亡画面sync0不可关闭，心智错误重试close三次。现死亡观察立即PLAYER_DEAD停止、无模型调用或GUI动作，等待期间死亡也撤出全部可行行为；148项相关回归、静态检查通过。自动复活/避敌仍属于未交付生存范围。

基础合成夹具新增显式难度参数：run_controlled_server --difficulty（默认normal）、runner MINEKIN_DOMAIN_DIFFICULTY、模型复验工具 --difficulty。peaceful仅用于隔离GUI/材料机制，不宣称生存通过；原survival模式、离线loopback、默认normal与权限不变。41项工具/配置与12项runner路由测试、ruff/pyright与bash -n通过；随后用--difficulty peaceful复验当前Bridge。

和平难度本机Docker run-57（非用户远程服，server.properties已核difficulty=peaceful），run `0e18b5d79437461e93fcd56847b5d647`、会话79b6c2debf054092bd21cb57c34f46c8：48真实调用、41步model/7步local_reflection、47步CONFIRMED、673帧/0观察拒收，动作13应用/175拒绝，松键正常，goal=false/STEP_BUDGET_SPENT。模型长时间仅pitch0扫描；第34步本地抬头55°才找到下一块木头，不能把转向确认视为目标进展。现模型summary补可见过的crosshair cell方向与通用俯仰候选（明确当前位置目标未确认，无隐藏读取），仍由模型选择；recent_actions保留目标参数并另报实际执行产物与后续库存。实际产物回归先红后绿，搜索方向和缺坐标回归通过；新模型字节仍待游戏验证。

后台任务预览同步现有工作台能力：原goal_read仍把所有3×3目标拒为CRAFT_GRID_TOO_SMALL，现从同一catalog计入可达网格前提与成本，并把工作台排在更大网格产物之前。木镐预算含9木板及1工作台，未知配方/无可达网格仍具名拒止；不新增配方、不宣称实时完成。回归先红后绿，9项API目标测试、27项任务/配置/身份/停止组件测试及生产构建、ruff/pyright通过。常用页面说明改为用户操作说明，去除授权轮次/内部接线散文。启动/暂停/恢复仍未交付。

目标预览改动后的完整前端回归：232项通过。首轮另有1条适配器断言仍期待旧3×3拒止，现按完整计划/工作台顺序/9木板预算更新后复跑全绿。

方向记忆模型复验run-58 `cdca3cf0185d48629ca2a9157a35b7f9`（会话1d6a9ddb9d8f47c89266a1156c02717d、本机Docker和平，基线4a4fc6f）48真实调用、32步model/16步local_reflection、45CONFIRMED、726帧/0观察拒收，23动作应用/177拒绝，松键正常，goal=false/STEP_BUDGET_SPENT。3次挖掘；第2/3步拾取COLLECT_APPROACH_STALLED、第7步COLLECT_AIM_NOT_CONFIRMED后collect整会话排除，后来新挖落物也无法尝试。现新可见实体ID可恢复拾取预算；同实体移动/重新出现不刷新，generation计入身份，仍有步骤上限。回归先红后绿，另补追踪目标物品最近掉落的水平/垂直距离读数，避免UNKNOWN缺少定位信息；新字节游戏复验待做。

run-59 `93ebaa4b01554a43882da2c0e0fc2a04`（会话3fa51cab34ea4970a4e458e5b1d00a62、本机Docker和平、行为基线751613e/Bridge0c8adfb7）真实模型目标成功：17次调用、14步model/3步local_reflection、17步CONFIRMED、221帧/0观察拒收，GOAL_HELD_IN_HAND，goal=true，正常松键。末段15 use_target打开sync1、16木镐3×3库存2897→2919、17关窗2974 screen=false，后续目标持有检查通过。这是受控场景普通运行记录，不是sealed、不代表全生存或多目标通过。旧run动作字段13/21沿旧口径保留；检查实际IPC发现非ACCEPTED全算refused（包含STARTED/SUCCEEDED），现按全部状态独立计数、refused只算FAILED，摘要工具标注历史口径。IPC真实消息回归先红后绿，27项运行契约、ruff/pyright通过。

受跟踪的真实模型复验工具支持--goal-product/--goal-quantity/--goal-source，沿用原demo参数化目标与同一技能，不增物品动作链；验证命名空间ID及1..64数量，13项工具回归及静态检查通过。用于随后8木板等不同目标验证；当前夹具仅提供oak_log，不宣称可验证任意资源环境。

当前Bridge入服与持键停止新封证、登记、默认自动入口恢复见[current-build-acceptance-2026-10-03.md](current-build-acceptance-2026-10-03.md)。116项相关回归通过，历史封存及1.21.4未变；模型复验工具默认auto-bundle，可显式--bundle-profile覆盖新候选，15项工具测试与静态检查通过。

## 六之二十四、后台受管启动的浏览器活体两发：容器白名单一度为空被拒，按既有工具修复后两发连续入服并 `STOPPED_ON_REQUEST`（2026-10-03，job `ce7c970bf30d461eaa96862488bca0e9`（会话 `31e0de496ec442a98b34fead584383bd`）与 job `87d2fac07c4047478f327502f9106732`（会话 `bad2954f5b784a29815faad57295ae90`），容器 `minekin-server-config-20261003`，卷 `minekin-local-demo2`，server run 目录 `run-71`）

这一发对应执行计划 `C-SERVER-CONFIG-AND-SAFE-START-008` 的后半：后台受管启动（`gateway/session_jobs.py` 持有的一次受监督启动）在浏览器→Vite 代理→Docker Gateway→容器内受控 1.20.1 的链路上收口。环境：受控服务器按既有工具重启——`MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar MINEKIN_RUNNER_DATA=minekin-local-demo2 MINEKIN_RUNNER_PUBLISH=8789 MINEKIN_RUNNER_DETACH=1 MINEKIN_RUNNER_NAME=minekin-server-config-20261003 bash test-orchestrator/runner/run.sh server --version 1.20.1 --accept-eula --keep-running --enable-status --difficulty peaceful --allow-player Kin`；Gateway 起在同一容器内 8789（`xvfb-run -a python -m gateway.server --data-root /data --kin kin-3x3-fresh-20261002 --host 0.0.0.0 --port 8789`），宿主只发布 `127.0.0.1:8789`；e2e 入口在 dashboard 目录先 `pnpm build`，再 `MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8789 E2E_SESSION_START_LIVE=1 pnpm exec playwright test e2e/session-start-live.spec.ts`。

1. **两发都是真实入服读数**：e2e 先在直连读数上等到 `runtimeState=running`、`world.joined=true`、`serverLink=connected`，并等页面自己显示「已入服/会话进入可玩」后才截图（`dashboard/test-results/session-start-local.png`），再从会话面板显式确认停止。服务端 `server.log`（run-71）逐字：`[08:27:13] Kin joined the game` / `[08:27:15] Kin lost connection: Disconnected` 与 `[08:34:27] Kin joined the game` / `[08:34:35] Kin lost connection: Disconnected`。
2. **收尾读数**：两份作业记录（`/data/kin/kin-3x3-fresh-20261002/run/dashboard-jobs/<jobId>.json` 与只读端点 `GET /api/v1/dashboard/session/job`）均为 `phase=ended · reason="" · outcome=STOPPED_ON_REQUEST · inputReleaseFailed=false · bridgeLostReason="" · installed=0 · total=3639`（store 全复用、无下载）；两发的 stop receipt 都是 `release=NOTHING_HELD`（`stop-requests/<session>-generation-1-pid-299/844.receipt.json`）——观察模式从未持键，这是一条真读数而不是「已确认松键」的替代：持键场景的 `released/unconfirmed` 仍以第六节各发为准。
3. **首提失败如实保留，修复不是放宽判据**：第一发（同一个 e2e）在 run-70 上被服务器拒止——`run-70/server.log:54-55` 逐字 `Disconnecting …name=Kin… You are not white-listed on this server!`，因为该容器起服务器时没带 `--allow-player Kin`（`run-70/whitelist.json` 为 `[]`）。修法是用既有工具重启服务器并显式 `--allow-player Kin`（`run-71/whitelist.json` 含 `Kin`/`8f40376b-c23f-3ef1-b553-5564eea75639`），e2e 字节随后两发连续通过；判据、1.20.1 登记、封存字节一字节未动。
4. **边界**：两发都是观察模式（`autonomousSteps=0`，不调用模型、不持输入）、单 Kin、loopback、普通运行记录（不是 sealed evidence）。受管路径的取消（preparing/supervising）、时限到期、客户端崩溃/被杀的收尾映射目前只有单测覆盖（`tests/unit/test_gateway_session_jobs.py`、`tests/unit/test_session_supervision.py`），活体读数仍缺，列为下一卡 `C-MANAGED-START-CANCEL-TIMEOUT-RECOVERY-009`；暂停/恢复仍为具名边界。门：全量 `3675 passed, 2 skipped`、ruff check/format 0、全仓 pyright 0、四仓库检查与 `git diff --check` 0、前端 240 项与生产构建通过。

## 受管会话生命周期复验

跟踪工具仅接受显式本地夹具，需已有空闲 Gateway、已保存 127.0.0.1:25566、匹配客户端缓存及允许 Kin 的受控服务器。运行：

```powershell
uv run python tools/verify_managed_session_lifecycle.py --container minekin-server-config-20261003 --kin kin-3x3-fresh-20261002 --restart-gateway --output .tmp/managed-lifecycle.json
```

工具顺序验证准备取消、真实入服后的时限收尾、该会话客户端被杀，以及可选的精确 Gateway 进程丢失。`--restart-gateway --only-restart` 可单独复验恢复；它只读观察中断作业，不自动重放，必要时显式停止后有界等待空闲。结果写普通 JSON；观察模式不持租约，不证明持键释放。崩溃注入使用 Linux pidfd 与该会话身份复核，不适用于用户远程服务器或任意进程。

同一工具加 `--only-held-stop`（不与重启选项组合）可单独验证 CLI 通用移动控制在取得非空租约后由后台停止。它核对单一新 run、停止前无释放、回执 released/无 unconfirmed、账本 had_lease=true 与 STOPPED_ON_REQUEST、进程退出和后台 idle。此形态不调用模型，不代替后台自主受管启动或断连恢复验收。

后台自主恢复的受控复验（只接受本地空闲且没有持久 operator-config 的该夹具，不替换用户设置）：

```powershell
uv run python -m tools.verify_managed_autonomous_recovery --container minekin-server-config-20261003 --kin kin-3x3-fresh-20261002 --output .tmp/managed-autonomous-recovery.json
```

它使用无密钥的回环测试端点调用 turn_to，分别验证后台取消非空租约、该会话客户端丢失、空闲收尾，然后恢复原 Gateway 环境配置。写入阶段报告，读取不重放；端点仅测试控制路径，不是真实模型能力证据。SIGKILL 后释放发送未报错不等于 Bridge 确认，仍存活客户端 watchdog 另验。

2026-10-04 HUD 观察实现：当前Core对已接纳的玩家视角观察每100游戏tick记录 PlayerStateObserved（health/max_health/food、tick、generation）；后台输出当前运行 health/food 与事件时间，10秒过期，不回显额外payload。旧运行、已收尾或无法确认存活的客户端不当成当前身体；无输入的观察模式亦能记录，proto/Bridge未改。129项定向回归与类型/静态检查通过；当前实现的真实游戏显示待复验。食用 run-72 中 apple减少而food下降不能过确认；先同步夹具饥饿效果结束与动作开始，再复验，完整生存未交付。

2026-10-04 饥饿夹具准备：受控服务器改为先给 Hunger 并查询 foodLevel，读到 food≤6 后显式清除；只在收到该玩家 Hunger 清除回执后给三个苹果，收到给物回执才原子写入该 server run 的 meal-ready.json。整个准备共享60秒期限；和平难度具名拒绝，避免自然恢复混入食用确认。标记是测试准备状态，不进入模型观察、不代表 consume 成功。动作启动与该标记及新鲜玩家观察的同步仍待接入；run-72 的 UNKNOWN 保留，当前未新增真实进食成功证据。

2026-10-04 准备屏障接线：HUNGRY_KIN 入口先运行 tools/prepare_hungry_kin.py，无输入观察会话沿原来的入服与 Bridge 观察路径取得准备完成之后的新鲜 health>0/food≤6 读数，再停止该自有客户端；正式动作会话另起，日志基线刷新。仅接受新的编号 server run、匹配的回环离线设置，拒绝未知启动参数、旧标记和并发客户端；清理验证 Linux 子进程归属，收尾核对无 InputLeaseGranted、STOPPED_ON_REQUEST 和空闲。准备标记不交给模型，库存/瞄准前提仍由正式 consume 行为检查。

本地 run-73 实际准备成功：观察 run f08ba76a953d4e5290a4a35ab3f1ced6，玩家读数 health=20、food=20/tick840→food=5/tick942；该玩家 Hunger 清除和三个苹果给物回执后写入标记，新读数晚于标记。停止 nothing_held=[168]、unconfirmed=[]、Core退出0、账本 STOPPED_ON_REQUEST，无输入租约事件。随后正式动作 run e664c909951f4bfe9fa3c1087e246125 仅记录启动，因宿主可用内存降至约660MB停止容器，未取得进食结果，harness退出143；不算当前进食或死亡恢复通过，不算模型验证或封存证据。读回材料为 .tmp/hunger-ready-evidence-20261004.json；原始准备记录仍在持久卷 server-runs/run-73。

资源停止后的环境：旧测试容器带 --rm，停止后自动移除，minekin-local-demo2 持久卷保留。已重建同名 minekin-server-config-20261003 为 created 状态，保持原镜像/卷/和平模式及仅127.0.0.1:8789端口，未重新启动JVM或后台。内存恢复后可 docker start minekin-server-config-20261003，确认服务器 ready 后再启动一次后台：docker exec -d minekin-server-config-20261003 xvfb-run -a python -m gateway.server --data-root /data --kin kin-3x3-fresh-20261002 --host 0.0.0.0 --port 8789。当前入口暂不可访问，正式进食复验仍待资源允许。

2026-10-04 生存中断收口：自主循环在模型返回后复核当前身体安全需求、连接代际与观察可用性；安全需求升档时丢弃旧决定并以最新读数重规划，普通推进或改善不无端作废。死亡优先于目标完成/步数预算，记录步骤期间新增的死亡也会中断运行；已死亡时库存不算目标持有，死亡不占技能失败重试额度。通用技能死亡中断/取消会尝试对应持键停止，发送失败保留死亡原因和 release_send_failed，不能视为 Bridge 确认。PlayerStateObserved 对死亡及恢复存活立即采样，常态保持100tick节流。单测使用可控模型 provider 和经观察门的消息，尚无当前字节的真实模型/死亡恢复游戏证明；自动复活和死亡后继续生存仍未接入。观察门另保留已准入 live→dead 转变计数及最近死亡 tick（不保存帧队列，不计拒绝/重复帧）；自主决定及 perform_skill 执行范围比较起始计数，死亡后更新的存活帧不能掩盖中断，ContextVar 执行范围退出后恢复。既往死亡不阻止从当前存活状态开始的新动作，恢复存活帧不是自动重生已实现的证据。相关观察完整性/心智/自主循环/HUD/配方运行时/会话监督/后台读模型/通用技能回归424项通过，owned代码ruff和pyright通过；光标存入测试改用随点击的读数回执，避免独立定时器跳过中间观察，保留三次点击断言。


2026-10-04 重生观察前提：1.20.1 的 InitialObservation/WorldObservation 新增可选 SelfState.respawn_available。只读取当前 DeathScreen 中启用、可见且翻译键为 deathScreen.respawn 的按钮；disabled、隐藏、旁观、退出、字面标签及存活身体均不会给出可用。旧 Bridge 未读该字段时 Core 保留 None，不当 False 或 True；存活且可用的矛盾帧经完整性门拒绝。未接入重生输入、模型选择重生或死亡后继续，按钮可用读数不是重生成功。

共享 schema 已重新构建两根 Bridge，candidate recipe/Launcher jar pin/fixture manifest 更新；1.21.4 不读取新字段，保持未知。历史 reviewed-tested-bundles.json 和封存材料未改，新候选不能由旧 run 晋级：自动 tested 入口会拒绝构建身份不匹配，当前新构建须走显式 candidate profile；恢复 automatic tested 路径需要新构建实际运行/封存及独立复判后登记。467项相关 Python 回归、两根 Gradle build/test 与工件边界通过；重生按钮两项 Java 用例使用实际 DeathScreen/ButtonWidget，但不是真实客户端运行。Linux交叉构建与新游戏验收仍待完成。下一步接入独立协商的重生动作，复核当前按钮前提，只以后续同代际存活观察确认结果，未知不重发。


自主循环的终止回答也重验身体：HOLD/BLOCKED 等非动作回答在模型等待后重新 observe，期间死亡（含已恢复存活）优先落 PLAYER_DEAD，观察丢失落 NO_LATEST_OBSERVATION，世界代际变化落 DECISION_PRECONDITION_CHANGED/WORLD_GENERATION_CHANGED；没有发送动作或虚构步骤。当前观察缺失时 goal_met 不沿用旧库存结论。四项回归先红后绿，相关心智/自主循环/公开配方运行时175项通过；这是单测验证，重生动作与新构建活体验收仍待完成。


2026-10-04 重生动作与候选引脚续期：`respawn` 成为独立协商的通用技能——proto 新增 `RespawnInput`（action_id/lease_id/generation/deadline 四边界），能力名 `control.respawn.v1`；Bridge 侧发第一条命令前复核当前 DeathScreen 上启用、可见且翻译键为 `deathScreen.respawn` 的原版按钮并只调用其回调一次（disabled/隐藏/旁观/字面标签/存活身体都具名拒止）。心侧：死亡且按钮可用时可行集收窄为 `("respawn",)` 且选择器优先；技能只认「同代际且存活」的更晚帧为 CONFIRMED，UNKNOWN 不重发；自主循环在按钮被原版短暂禁用时按观察等待（≤2s）等新帧，重生未确认即具名停跑（`RESPAWN_NOT_CONFIRMED`），确认后以新生命继续；死亡中断/取消出口沿用同一具名松键。两根 Bridge 为输入消息二次重建（Windows JDK 21.0.12.1+1-LTS-4，每根连续两次同字节 `--rerun-tasks`）：1.21.4 `cf89f3ad…`/1,413,072B、1.20.1 `ea5d07b8…`/1,453,863B（按 buf canonical 的 proto 拼写重拼一次，拼写同批修正）；candidate recipe、Launcher jar pin、fixture manifest、CORE-001 输入钉与 Hello proof 常量随之前移。历史 reviewed-tested-bundles.json 与封存材料一字未动，新候选仍须实际运行、封存、独立复判后才能登记。
同批修复主干上的 CI 红（`4418e84`）：根因是上一轮候选引脚前移后 CORE-001 输入钉滞留，以及约 18 项组合测试仍把「candidate fixture == reviewed registry」当同一物；修复为输入钉随 fixture 前移、证明常量随计划前移，组合测试改经 `tests/launcher_support.py` 从当前 fixture 派生「凭证当下字节」的合成注册表（明示非证据、不回写历史），历史注册表拒收移动后候选的读数保留在 provenance 测试（`test_historical_tested_entry_cannot_promote_a_new_candidate_build`）。
门：本机全量 `3982 passed, 2 skipped`、不带参数的 `uv run pyright` 全仓 0 errors、ruff 0/0、boundaries/case-assertions(151)/fixture-digests/workflow-pins 全绿、两个 Gradle 根 `check --rerun-tasks` 与工件边界绿、`git diff --check` 干净。**未证按实**：死亡→重生→继续的活体读数未取（本机内存守卫与放行窗口未到）；Linux 交叉构建与本构建的游戏验收未跑；重生按钮/输入两格是单测与合成帧，不是真实客户端运行。
