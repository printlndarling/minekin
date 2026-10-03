# S2 世界观察与玩家等价动作契约

本文件把 `docs/action-contracts.md` 的第 1、2 节落到具体字节上：Bridge 报什么、Core 能命令什么、结果怎样才算被确认。它是实现与验收的共同口径，不是新产品决定的入口——与 `action-contracts.md` 冲突时以那一节为准，与真实客户端读数冲突时以读数为准。

对应线格式：`proto/minekin/v1/control.proto`、`proto/minekin/v1/observation.proto`。生成物 `src/minekin_core/generated/**` 只能由 `tools/generate_protos.py` 产生。

## 1. 能力协商

新增能力串按既有 `control.<skill>.v1` / `observe.<name>.v1` 拼写，逐个协商、逐个把关：

| 能力串 | 允许的消息 | 为什么单独一格 |
| --- | --- | --- |
| `control.aim.v1` | `AimInput` | 会转视角的客户端不一定允许破坏方块 |
| `control.mine.v1` | `MineInput` | 挖掘有副作用（改变世界），必须能与移动分开关 |
| `control.hotbar.v1` | `HotbarSelectInput` | 换手只影响自己，风险面不同于挖方块 |
| `control.screen.v1` | `ScreenInput` | 开关界面会暂停普通输入反射，是独立权限 |
| `control.gui.v1` | `GuiClickInput` | GUI 点击直接动物品，是唯一能改变物品分布的写面 |
| `observe.world.v1` | `WorldObservation` | 观察是只读的，可以和五个动作面完全不同开关 |

未协商的能力对应的消息必须在 Bridge 侧被拒（`CAPABILITY_NOT_GRANTED`），并且 Core 的发送侧也不能把它塞进 `_CONTROL_TYPES` 的允许集合后就当没事发生——门禁两处都要有名字。

## 2. 观察面

### `WorldObservation`

固定 tick 间隔发布（`bridge-1201` 与 `bridge` 各自一个常量，当前 10 tick），只在客户端 PLAYABLE 且 Core 会话持有 `observe.world.v1` 时发。间隔是构建常量而不是请求频率：一个会话的成本不取决于对方问得多急。

字段口径：

- `self`：客户端自己玩家的位置、朝向、手持。缺的字段就是不填（proto3 `optional`），**零不是"没读到"**。`main_hand_item_id` 缺失表示手上确实空着，`selected_slot` 缺失表示这次没读热键栏。
- `aim`：`MinecraftClient.crosshairTarget` 的一次读取。`AIM_TARGET_KIND_MISS` 是"看了，什么都没有"，与整个 `aim` 缺席（没看）是两件事。只填 `kind` 选中的分支；`targeted_block_id` 只说命中那格在渲染什么方块（原版 F3 也给任何玩家这一行），不是对邻格或墙后的授权，也不带方块属性列表。
- `inventory`：与 `InitialObservation` 同一份 `InventorySummary` 形状，`revision` 仍是读取时的 game tick。动作后的物品核对只认这里的增量。
- `visible_entities`：沿用 `ClientSnapshot` 的半径与遮挡规则，位置只有相对观察者自己的 `relative_*`。实体不带世界坐标：那是把渲染器持有的每个实体（包括没人看的）都摆到服务端真值上，`tests/unit/test_observation_boundary.py` 按构造拒收。要回到某处，用 `self` 自己的坐标加相对偏移。`item_id`/`item_count` 只填客户端渲染成掉落物的实体，别的实体一律不填（实体自己的背包不是"看见"的东西）。
- `mining`：客户端自己的破坏动画进度，0..1。它是玩家看得见的那条进度，不是剩余 tick 的推算。
- `gui`：当前屏幕的类名标签与 `sync_id`。没有开屏幕时 `sync_id` 缺席，因为 0 是合法 handler id（玩家自带背包），不能兼职当"无"。

### 信息类别

`minekin.v1.WorldObservation` 在 `domain/information_class.py` 里是 `PLAYER_EQUIVALENT`：它是同一个客户端在同一条读取路径上的再读，不是第二个真值来源。Bridge 仍然不报方块实体内容、不报未命中射线的方块、不报任何服务端侧信息。

## 3. 动作面

五个新入站消息都带 `action_id`、`lease_id`、`generation`、`deadline_monotonic_ns`，与 `MoveInput`/`UseInput` 走同一套租约与看门狗；撤销租约的释放路径是唯一的，不给每个新键各造一次"松手"。

- **`AimInput`**：绝对 yaw/pitch。Bridge 每条命令最多转 `MAX_AIM_DEGREES_PER_COMMAND`（构建常量，20°），没到位就回 `STARTED` + `AIM_IN_PROGRESS`，到位回 `SUCCEEDED`。契约要求朝向是"可测最大角速度下的逐步变化"，所以限制放在客户端，而不是让 Core 自己算增量。
- **`MineInput`**：攻击键按住/松开，形状照 `UseInput`。`mining=true` 时 `target` 必须与客户端当前 `crosshairTarget` 的方块与面一致，否则具名拒绝 `MINE_TARGET_NOT_AIMED`；在范围内则 `attackBlock`，之后由 tick 钩子按客户端自己的节奏继续 `updateBlockBreakingProgress`，松手或租约到期即 `cancelBlockBreaking`。**没有** `breakBlock`、没有瞬挖、没有跳过时长的快捷路径。
- **`HotbarSelectInput`**：只接受 0..8，越界拒 `HOTBAR_SLOT_OUT_OF_RANGE`。它等价于玩家按数字键，不改物品分布。
- **`ScreenInput`**：`OPEN_INVENTORY` 走客户端自己的 `inventoryKey` 按键路径（和人手按 E 是同一条），`CLOSE` 是关屏。这里刻意没有"打开面前的方块"这一格：那已经是 `UseInput` 的能力，多开一扇门就多一处漏掉检查的地方。
- **`GuiClickInput`**：`sync_id` 必须等于客户端此刻报告的 handler，否则拒 `GUI_SYNC_ID_MISMATCH`（契约禁止带着旧 syncId 点下一个容器）。`slot` 分支映射到 `clickSlot`，`recipe` 分支映射到 `clickRecipe` 并要求 `recipe_id` 是本游戏版本存在的规则 id。客户端解析 id 失败即拒 `GUI_RECIPE_UNKNOWN`。`recipe` 分支还带 `craft_all`：Core 默认发 `true`，因为普通选择（配方书的单点）把成品留在**光标**上，而光标不在 `inventory` 报出的同步内容里，下面那张表的核对条件在那一帧之后仍然读不出来；运行文档的 `details.craft_all` 写明这一次发出去的是哪一笔。`clickCreativeStack` 在这套线格式里**不存在**，不是"运行时拒绝"。

## 4. 结果核对

`ActionResult` 的 `SUCCEEDED` 只代表客户端把手上的动作做完了，不代表世界变了。技能层的结论必须由动作之后到达的 `WorldObservation` 得出：

| 动作 | confirmed 需要的读数 | failed / interrupted 的读数 |
| --- | --- | --- |
| 挖掉一格木头 | `aim.targeted_block_id` 不再是该方块，或 `visible_entities` 出现对应掉落物 | `mining.progress` 长时间不动、租约到期、目标丢失 |
| 拾取掉落物 | `inventory` 同名 item 的总数在同步后的 revision 上增加，且掉落物减少或消失 | 掉落物被别人拿走/烧毁/过期 ⇒ `failed` 或 `unknown` |
| 合成 | 材料减少与产物增加**同时**出现在同步后的 `inventory` 里 | 只发了包、只开了窗、只点了格子都不算；停在光标上的成品也不算，因为 `inventory` 与 `GuiScreenValue` 都不报光标那一格 |
| 换手 | 后续 `self.selected_slot` / `main_hand_item_id` 与请求一致 | 读数仍指回原槽 ⇒ `unknown` |

`unknown` 不自动重试有副作用的点击（GUI/挖掘）；无副作用的读数类动作可以重试。每一次动作记录：决策时的观察（tick + aim + 相关 revision）、实际发出的输入、服务端确认后的读数、结论与具名原因。

## 5. 首版技能面

技能做五件事，且都以"已见"为前提：`turn_to`（绝对朝向，受角速度限制）、`break_seen_block`（目标是 `aim` 报出的那一格）、`collect_dropped`（走向已见的掉落物，靠背包增量确认）、`craft`（先用已有材料验前提，再走真实 GUI）、`select_hotbar`（按数字键换手，由下一帧 `self` 说明手里是什么）。

不做的：读墙后、扫描已加载区块找木头、给自己加物品、`clickCreativeStack`、无限堆叠、跳过挖掘时长。首版合成面限制在 2x2 网格内可完成的木板/木棍/木镐（工作台配方留给 GUI 打开后的同一套点击）。

## 6. 验收口径

- 两个 Bridge 根（`bridge/` 1.21.4 回归基线、`bridge-1201/` 1.20.1 产品线）都要实现同一套消息，各自的 `./gradlew check` 绿。
- `tools/check_bridge_protocol.py`、`check_bridge_proto_java.py`、`check_bridge_host_boundary.py`、`check_bridge_artifacts.py` 绿；新增的 Minecraft 调用需要在 `check_bridge_proto_java.py` 的 stub 集合里有对应签名（stub 的签名从已编译客户端读，不靠猜）。
- Python 侧 `information_class` 全覆盖测试要把新事件类型逐个点名；`tests/contract/test_bridge_java_constants.py` 绑定两侧常量。
- 活体读数只在本地受控会话里取，不连接用户的远程测试服。

## 7. 追加修订（2026-10-03）：通用食用 `consume_item`

食用**不是新线格式**：线上没有 eat 消息，一个玩家吃东西就是手里拿着食物、准星落在空处时按住使用键，直到客户端自己的进食时长走完。所以这一格复用两件已有消息——`HotbarSelectInput`（把食物换到手上）与 `UseInput` 的按住/松开（`use=true` … `use=false`）——`proto/` 与两个 Bridge 根一字未动；新增的是 Core 技能面、前提词与结果行。

- **前提**（全部由最新一帧判定，任一不成立即具名拒绝、不进线）：目标物在背包（`CONSUME_ITEM_MISSING`）、在 `domain/food_catalog.py` 的过渡策展表内（`CONSUME_ITEM_NOT_KNOWN_FOOD`——该词说的是"本构建没有这一行"，不是"游戏认为不能吃"）、饥饿条有空间（`CONSUME_NOT_HUNGRY`；满格是唯一"吃了也读不出变化"的状态，确认读的就是那条，故按此拒绝）、可被 0..8 的快捷键带到手上（`CONSUME_ITEM_NOT_IN_HOTBAR`；把物品从背包挪进快捷栏是容器点击，本版不做）、准星是正面的 `MISS`（`CONSUME_AIM_NOT_CLEAR`；使用键会先打中准星上的东西——门、活板门、箱子、弓的拉弦都是真实副作用，本版不用"先试试看"去赌它）。
- **执行形状**：未在手上 → 先发 `HotbarSelectInput`，由**更晚的一帧** `self` 确认槽位与手持物（`verify_hotbar_change`）；随后 `use=true`，**按住直到某帧读数报出这次进食**（条升 + 物减同帧，与本步结论同一判据），`CONSUME_HOLD_SECONDS = 2.5 s` 只是没有任何确认帧时的上限——原版一次进食 32 客户端 tick = 1.6 s（零食类如干海带为 16 tick），客户端在按下后下一 tick 起算、按住会立即续吃下一口，因此"读到确认帧即松键"把第二口取消在上限之内：除无确认回帧的通道外，一次调用确认一件。选槽等待、按住与确认等待共用**同一个 `timeout_ns` 窗口**，总时长不超过计划按 `timeout + STEP_LEASE_HEADROOM_S` 为单次等待预留的租约余量。松开必发生在其后的等待之前，频道不再作答也以松键收尾。
- **§4 结果核对新增一行**：确认 = **同一帧同步修订上，饥饿条上升且该物在背包里的总数下降**。两臂缺一不确认（只有条升 = 别的原因；只有数降 = 去向别处）。`UNKNOWN` 是地板，不判 `FAILED`；`UNKNOWN` 不买第二次按键。
- 步骤 `details` 记 `item_id / food_before / food_after / health_before / health_after / item_before / item_after / newest_checked_tick`：健康/饥饿这两格玩家可见观察由此在 run 文档里留下作出判断的那两帧。
- **心智侧**：`consume_item` 进入 `SKILL_OFFER`；可行性 = 存在可及候选（表内食物且 0..8 或已在手）且上述前提整组通过；本地反思在 `safety ≥ 3`（饥饿 ≤ 6 或生命 < 90%）时先吃再做别的；五条拒绝词全部按**改线**处理（不烧重试额度、不整场排除技能——被拒的是一个候选，下一帧可以换一个）。模型点名不成立的食物时沿同一条改线把原名记进 `model_refusal`，技能留在可行集里由本地层按本次读数重新选择——`safety ≥ 3` 时就是读数的候选本身，否则先去做别的事。`observation_summary` 新增 `consumable_items`（表 ∩ 快捷栏可及），与 `craft_options` 同类：把本构建能行动的边界明说给答复方，列出的每一项都是技能真能跑的名字。
- **边界（照实登记）**：`food_catalog` 是过渡策展子集，明确声称不做全量；会返还容器的饮品/炖菜与以效果为主的满格情形（如金苹果在满格时）不在本版；扩展路线是让 Bridge 在 `InventorySummary` 每摞上报客户端注册表的 `isFood()`（版本精确），届时本表退役。当前线上没有这个字段，不得声称知识来自世界。
