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
3. **面板上的技能行不带模型的配置与花费。** `model_enabled`、provider、`model_calls`、`model_spent_micro`、`model_cap_refusals` 只记在 run 文档的 mind 段里；台账的技能行不携带，只读投影不解析 bundle 的 run 文档。面板对这两格会直接写明 `not_wired` 的理由，而不是留空白。
4. **本次演示里"目标"不是大模型选的。** 这台机器上没有可用的模型凭据，所以意图全部来自 `local_reflection`（`MODEL_NOT_CONFIGURED`）。"由大模型自主选定目标"这件事**尚未在真实游戏里验证过**；已经验证的是：没有人类逐步指令、没有预设动作序列，Kin 依然按读数一步步试下来，并在失败后调整。2026-09-30 的那次自主运行把"调整"量到了名字这一层：七步里前四步 CONFIRMED，随后 `turn_to` 连撞三次 `AIM_STALLED`，mind 段于是写下 `excluded_skills: ["turn_to"]`、`retry_budget: 2` 并以 `NO_FEASIBLE_SKILL` 具名收尾（见六之二）——这是改线，不是重试同一笔。
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
13. **木镐这一步卡在 2×2 网格，不在技能上。** `craft_take_result` 已经在 2×2 里连过两配方（木板、木棍），但 `minecraft:wooden_pickaxe` 需要 3×3 工作台的网格；玩家自带界面装不下它，而本项目还没有"放下一个工作台"的技能（`SKILL_OFFER` 里没有放置这一步）。也就是说"最终取得木镐"这一目标欠的是**放置技能 + 木板数量**（一次采木 = 4 板，镐要 3 板 + 2 棍，还要先摆台），不是合成判据。这一条留给主控决定要不要把 S2 的收口范围扩到放置。
14. **`collect_dropped` 现在会追掉落物，但它要求的"看得见"并不恒成立。** 三次运行里两次 CONFIRMED（`615eb862…` 的 `steps=1, newest_checked_tick=19068`；`e1e98155…` 的 `steps=1, newest_checked_tick=1699`），一次 `FAILED / NO_SEEN_DROP`（run `8b8412ca182c4bb7b3764df5a5304d76`：`break_seen_block` 在 tick 1640 就 CONFIRMED，紧接着的 `collect_dropped` 在同一个 tick 的一帧里没读到掉落物）。所以这一步不是恒败，但也不是恒过——它把"那一帧里看得见"当成了前提，而木头从被破坏的那一格掉到地上时可能正好在视野锥之外。这一步的健壮性还欠一次改动（要么允许多帧重试，要么在破坏后重新瞄准掉落点）。
15. **面板说不出"心自己按名字停的线"。** 自主收尾的名字（`autonomous.stop_reason`、`excluded_skills`、`current_intent.kind: BLOCKED`）只活在 run 文档里，台账没有对应的一行；只看面板会读到 `SessionInterrupted | outcome=BRIDGE_LOST`。逐行读数见六之二末尾。这一格是 S3-C 要动的地方：把名字落进台账，而不是把 run 文档塞进投影。

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
