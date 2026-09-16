# 玩家式客户端动作契约：从木头到战斗、建造

证据核对：2026-09-15；第一轮实验版本拟为 Java `1.21.4` / Yarn `1.21.4+build.8`，不是已运行的 Kin。下面列出的客户端交互方法来自 [Fabric Yarn 的 `ClientPlayerInteractionManager`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)、[`MinecraftClient`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html) 和 [`ScreenHandler`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/ScreenHandler.html)。它们说明**存在可实现的正常客户端交互面**，不是“调用一次就一定成功”，具体版本仍需构建和登录实测。Fabric 的[按键映射](https://docs.fabricmc.net/develop/key-mappings)目前默认展示新版 API，方法理念可借鉴，具体调用签名对所选旧版重新检查。

## 通用动作契约

高层只输出可取消的 `intent`（如“准备基础工具”“打一场仗或逃跑”“施工这个设计”），不发送实体精确坐标或逐帧输入。任务层提交 `action_request`：目标来源、最后观察时间、动作期限、可触及范围、前置材料、所需本地技能和安全约束；本地单一输入仲裁器决定谁能操作客户端。反射优先于战斗，战斗优先于一般施工；GUI 开启时普通行走/攻击暂停，危险抢占需要先取消或关闭 GUI 并核查状态。外部资料、玩家聊天和过期计划没有本地输入权限。

结果分为 `started`、`confirmed`、`failed`、`interrupted`、`unknown`。**只有服务器同步后的背包/方块/屏幕变化才可确认**；客户端预测值、方法调用返回或窗口被打开，不能直接记成取得物品或建成建筑。每次动作记录决策时的玩家等价观察、客户端输入、服务器确认、实际消耗、超时与失败原因；未知结果不得自动重复可能有副作用的点击。

### 1. 寻树、砍木、拾取

1. 寻树：先从视锥和遮挡允许的观察或亲历地点产生候选；可转视角主动寻找，不把已加载世界内所有木头坐标送给 Kin。导航只对经观察允许的目标发请求；寻路可用 Baritone API 候选，但需单独审计其路径缓存、拆/放方块和扫描策略。
2. 砍木：正常移到距离与角度允许的方块，检查目前 `crosshairTarget` 命中该目标，开始破坏并逐 tick 持续；候选客户端接口有 `attackBlock`、`updateBlockBreakingProgress` 与 `cancelBlockBreaking`，**该 Javadoc 同时存在 `breakBlock` 方法，单凭方法名不能证明它是瞬挖或合法操作路径**，需检查 1.21.4 实际客户端源码/游戏行为。不得通过其他快捷路径跳过正常挖掘时长。目标遮挡、工具不对、别人挡路或危险中断即停止；实际木块改变与掉落需二次核对。
3. 拾取：仅从已看见或近处合理听/触的掉落物产生目标，靠正常移动接近并观察背包同步后的数量增加；**没有“给自己加物品”动作**。掉落物被玩家拿走、烧毁或过期，均返回失败或未知。

### 2. 背包、工作台、炉与箱

当前屏幕必须先由真实的对方可达工作台、炉、箱等交互打开。`ClientPlayerInteractionManager` 暴露 `interactBlock`、`clickRecipe`、`clickSlot`、`clickButton`；[`ScreenHandler.syncId`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/ScreenHandler.html)用于匹配当前玩家打开的界面，不能从旧 GUI 留一个 `syncId` 后盲点下一个容器。客户端有 [`CraftingScreenHandler`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/CraftingScreenHandler.html)和[`AbstractFurnaceScreenHandler`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/screen/AbstractFurnaceScreenHandler.html)，这也是后续专业化 GUI adapter 的来源。

- GUI adapter 先检查处理器类型、当前 `syncId`、焦点、槽位实际映射、游标暂存物品和自身背包材料；配方助手只消费对该角色公开可学、适用本游戏版本的合成规则。该版 `clickRecipe` 需**当前可用的 `NetworkRecipeId`**，不是知识树里一段配方文字；也可在已打开界面内执行合法槽位点击，**不可用 `clickCreativeStack` 或伪造直接添加物品**。等待每步状态同步，再拿成品、确认材料减少与成品增加；掉线或窗口意外关闭须返回 `unknown`/`failed`。关窗可能把游标物品送回背包或掉落，危险抢占先保命，记录材料去向，不能假定不会丢失；具体[接口核查](gui-combat-interface-audit.md)。
- 炉：打开炉 GUI，放实际输入与燃料，读取该界面呈现的进度/结果、选择等待或离开做自己的事；取成品时再次确认同步背包。房子、炉、床、箱的操作先验证放置、权属约定、位置记忆和重新到达，容器内容仅在 Kin 自己正常打开时可读，不得扫描未打开私箱。
- 服务器可能改变原版配方、拒绝交互或网络延迟；不重复套用上一次 `slotId`、`syncId` 和旧材料列表。首版合成目标限制为工作台、木板/木棍/镐、基础炉与床等已验证流程；不能因为旧版 AltoClef 会获取 400+ 物品就宣称这些动作现成。

### 3. 玩家式战斗而非杀戮光环

高层可以决定争执、躲避、援助或追击，但本地闭环需由**当前视野内且无遮挡**的对手、受击/声音线索及最近一次观察组成信念。非目视线索可以促使转身查验，不赋予穿墙坐标；目标离开视野后记住最后位置和不确定性，不能每 tick 继续按实体列表实时追踪。客户端 [`MinecraftClient.crosshairTarget`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html)与 `targetedEntity` 是常规交互的候选核验；Yarn 有 `attackEntity`，**必须在当前瞄准/距离/遮挡/攻速/安全检查之后**才能调用，不能遍历所有实体直接轮流攻击。

本地 combat adapter 提供 `face_visible_target`、`move_or_retreat`、`attack_when_ready`、`hold_or_release_shield`、`break_contact`；每次朝向按可测最大角速度变化，不瞬时转 180°，盾牌由手上装备、使用状态和服务器反馈核验。训练经历影响能否及时发现、瞄准、挡或逃；也允许因为手忙脚乱失败，不能用角色能力标签制造秒杀。连续 PvP 场景要测移动目标、墙后再出现、意外误伤、旧信念过期、低血量抢占和对方停战；关系判断与一击反射分开。

### 4. 施工、红石与审美

“擅长建造”须拆为**知道方案**、**提出方案**、**把方案转成放置意图**、**客户端准确执行并检查结果**。高层可给出场景目标、风格与需求，再由规划器产生带版本来源的材料表与局部体素草图；先局部采光、可站位置、邻近权属和地形限制评估，而非读取全球地图。设计草图是候选，不等于建好，Kin 可以自行改变主意或邀朋友讨论。对已知可施工目标逐个导航到能正常看见并点击的工作位置，用真实手持方块、朝向/面、`interactBlock` 和客户端 `crosshairTarget` 检查后放置；验方块类型、朝向、形状、材料消耗，遇到失配修订或停工。Baritone USAGE 的 [`build`](https://github.com/cabaletta/baritone/blob/1.21.4/USAGE.md)能为方案执行提供候选思路，但既不保证漂亮，也不证明 Kin 可用未知地形直接生成完美建筑。

红石工程须额外检查输入/输出的真实功能和版本机制，在世界里搭一个可复现小电路再扩大；“对红石知识深”不能代替排错和施工技能。美感可来自 Kin 的偏好、公开范例、本人可见的局部几何与亲历反馈；外部 VLM 默认关闭，仅在预算/隐私授权下按需选配，且不负责逐块控制。详见[逐块施工/朝向契约](building-placement-contract.md)。是否符合风格需人类和角色的审美评估，而非一个几何打分就称“完美”。对无效设计/无法完成的楼层允许撤回、妥协或重设计。

## 进入开发后的必要小实验

| 实验 | 预期可以确认的结论 | 不能偷换成什么 |
| --- | --- | --- |
| 空手→已见树→木头→背包/工作台→木镐→石材 | 正常客户端输入、GUI 与库存同步的闭环及失败原因 | 高层决策会自动通关 |
| 打开/关闭工作台、炉、私箱 | `syncId`/槽位换屏不会误点；燃料、加工、所有权与库存核验 | “读到客户端缓存”即“亲眼知道私箱里有什么” |
| 移动 PvE/PvP 对手与障碍物 | 视野、角度、盾牌、攻速、误伤和反射抢占的表现 | 360°、穿墙跟踪、KillAura 可用 |
| 建造小屋/红石小线路 | 材料草图、逐块 placement、方块朝向与功能测试 | 一个 prompt 必然产出漂亮完整的大建筑 |

指标需报实际 TPS/FPS、网络 RTT、动作开始到首次输入 tick、服务器确认延迟、GUI 错点和中断恢复次数；模型关闭时本地操作仍应能安全停/自救。设计路径有源码/接口依据，但这些实验**都未实际完成**。关联[研究台账](research-tracker.md)的 R06–R09 和[首登动作闭环](vanilla-survival-loop.md)。
