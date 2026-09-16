# Baritone 固定版输入接管与紧急抢占：静态源码核查

核对：2026-09-16，Minecraft Java 1.21.4 Baritone commit `78d3613`；仅静态读取上游源码，**未构建 Kin/Baritone 同版组合、未测实际 tick、动作或服务端收效**。本契约与[Kin 输入仲裁](input-arbitration-contract.md)及[感知源码审计](baritone-perception-audit.md)分别管真实输入和地图读数，两者均需闭环，不能以其中一项通过代表另一项通过。

| 上游源码/可观察事实 | 对 Kin 的约束（推论，非实测） |
| --- | --- |
| [`InputOverrideHandler`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/utils/InputOverrideHandler.java) 持有强制按下状态，在 tick 中将玩家 `input` 切换为 `PlayerMovementInput`，不控制时恢复 `KeyboardInput`；[后者源码](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/utils/PlayerMovementInput.java)从 Baritone 自己的 force-state 生成行走/跳跃/潜行等动作 | Kin 操作 GameOptions/KeyBinding 的按住状态**不一定在 Baritone 控制移动时生效**；不能把游戏按键列为全客户端唯一写者的充分证明。客户端 `input` 对象与 Baritone 强制状态须一起纳入控制权诊断。 |
| [`IInputOverrideHandler`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/api/java/baritone/api/utils/IInputOverrideHandler.java)公开 `isInputForcedDown/setInputForceState/clearAllKeys`；实现的 `clearAllKeys` 清除 force map，但 `BlockBreakHelper/BlockPlaceHelper` 仍有自身 tick 及停挖状态 | 应区分“移除强制键”、“停止连续挖/放”、“结束当前路径”、“恢复正常玩家输入”，不能只调用 `clearAllKeys` 就声明已停止。关键操作用实际反馈和状态核验。 |
| [`IPathingBehavior.cancelEverything()`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/api/java/baritone/api/behavior/IPathingBehavior.java)声明返回取消是否成功；过程会被取消，当前路径可能在不可取消的跑酷跳跃里继续。[实际实现](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/behavior/PathingBehavior.java)只有 `isSafeToCancel` 才立即移除片段；`forceCancel` 接口警告不要调用 | 紧急抢占不是必定一个 tick 成功：先请求有返回值的正常取消、撤销 Kin 的旧 lease/新导航意图，**未确认路径终止前不给 Kin 另一路不受约束的移动输入**；危险场景另测独立存活控制器的救援动作是否可在此状态安全介入。不得以 `forceCancel` 暴力停机作为已证明安全的捷径。 |
| [`PathingControlManager`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/utils/PathingControlManager.java)在 cancel 后清空控制过程，但为临时过程保留特例，流程还区分 tick 前后的命令与路径执行；[Minecraft Mixin](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/launch/java/baritone/launch/mixins/MixinMinecraft.java)对当前路径及画面有输入事件重定向 | Fabric `ClientTickEvents.START/END` 与 Baritone mixin 在同一实例的**真实相对时序未知**；GUI、ESC、聊天、失焦和真人键鼠让渡不能凭简单 Fabric 事件回调判安全。临时过程也需枚举其在紧急状态是否保持控制。 |

## 首版策略与回退

普通模式首轮只允许**已观察目标的导航试验**（矿点扫描另见[采矿审计](baritone-perception-audit.md)）；Baritone 所有路径请求都经 Kin 仲裁器带 generation 与失效期限，使用上游公开的正常取消/按键清除候选接口，同时由 Kin 检查输入对象、强制键、pathing/过程状态、GUI、本人位置与服务端动作。因上游不是 Kin 仲裁器的子进程，**当前只能把它当独立写者，需要实际单实例集成和时序测量**，不宣称现有 API 已实现单写者。

对高处、熔岩、跑酷等紧急救援易与自动导航冲突的区域，初期可选择：**不让 Baritone 执行高风险移动片段**，由自写受限局部运动/救援技能候选处理；正常环境沿已观察目标试 Baritone，进入危险域之前移交。运行时突然发生危险仍须研究“取消未成功时本地救援/停挖与旧路径共存”的回放，不保证必救成功。若组合实验表明上游仍抢写移动或安全取消太迟，则 Kin 首版撤下 Baritone 运行依赖，保留研究/算法思想，自写玩家等价局部寻路/普通客户端交互；此回退是候选工程方案，不是已经完成的替代底座。

最小同服原型矩阵：正常移动→停机；持续挖掘→放手；常规路径→反射取消；跳跃/崖边当前片段→`cancelEverything=false` 分支；GUI/ESC/聊天切屏；真人键盘输入让渡；A 模式离线/断线；低 TPS/FPS 与网络抖动。逐 tick 记录 Kin lease owner、上游 `isPathing/hasPath`、取消返回、公开强制键状态、当前输入类、连续挖状态、首次有效输入和服务端位置/物品反馈；测试 `forceCancel` 不作为通过条件。测失败次数和 P95/P99 首次有效抢占/恢复时间，分开报“已请求停”和“角色确实停”。没有实际组合试验前，本文件**不能为 Baritone 的即时抢占、人类化救援、真客户端兼容作保证**。
