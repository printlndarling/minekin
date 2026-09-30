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
13. **木镐这一步卡在 2×2 网格，不在技能上。** `craft_take_result` 已经在 2×2 里连过两配方（木板、木棍），但 `minecraft:wooden_pickaxe` 需要 3×3 工作台的网格；玩家自带界面装不下它，而本项目还没有"放下一个工作台"的技能（`SKILL_OFFER` 里没有放置这一步）。也就是说"最终取得木镐"这一目标欠的是**放置技能 + 木板数量**（一次采木 = 4 板，镐要 3 板 + 2 棍，还要先摆台），不是合成判据。这一条留给主控决定要不要把 S2 的收口范围扩到放置。**2026-09-30 起这一格多了一层：Core 不再把 3×3 的配方发给只开 2×2 的技能。** 配方现在按产物从 `src/minekin_core/domain/recipe_catalog.py` 解析，装不下的形状具名返回 `CRAFT_GRID_TOO_SMALL`（归因 `SKILL_NOT_IMPLEMENTED`），心因此永远不会为木镐发出那一笔点击——见第 16 条与六之四。
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
