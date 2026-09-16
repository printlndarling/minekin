# 真实 Fabric 客户端输入：单一控制权与松手保证

查证：2026-09-16；Java 1.21.4 / Yarn `1.21.4+build.8`，静态接口研究，无运行中的 Kin。对应的同版 Fabric API 源码 [`ClientTickEvents`](https://github.com/FabricMC/fabric-api/blob/7347d6186858dcfcf7fccf747e8029067caaece5/fabric-lifecycle-events-v1/src/client/java/net/fabricmc/fabric/api/client/event/lifecycle/v1/ClientTickEvents.java)列客户端 tick 的 START/END；[Yarn `GameOptions`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/option/GameOptions.html)列 `forwardKey/leftKey/jumpKey/sneakKey/attackKey/useKey` 等绑定，[`KeyBinding`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/option/KeyBinding.html)列 `isPressed/wasPressed/setPressed`，[`ClientPlayerEntity`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerEntity.html)列当前 `input`，[`Entity`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/entity/Entity.html)列 `getYaw/getPitch/setYaw/setPitch`。这些接口能提出**本地玩家输入候选**，但并未证明按键模拟能与所有图形窗口、实体/GUI交互、服务器校正及其他模组共存。

## 在同一客户端里只允许一个写者

反射、局部寻路、战斗、GUI 和高层意图必须走 `InputArbiter`：每次授予 `input_lease(owner, intent_generation, priority, acquired_tick, expires_tick, held_keys, rotation_bound)`，唯一执行线程在客户端 tick 上对批准动作赋值；模型、网页、聊天、数据库线程不能直接写 `KeyBinding` 或角色视角。世界外强制停机和目标服禁止能力先于反射，反射可抢占导航/施工，GUI 会话与移动/普通攻击互斥。若同时集成 Baritone，**它也是争夺真实客户端输入的控制者**；[固定源码输入审计](baritone-input-audit.md)显示它在控制路径时会切换 `ClientPlayerEntity.input` 为自带的 `PlayerMovementInput`，强制移动状态独立于 Kin 的 `KeyBinding`，且正常 `cancelEverything()` 在不可取消片段可能返回 false。因此 Kin 只能仲裁自己的命令，不能凭单写者声明即时覆盖 Baritone；首轮在危险地形先禁 Baritone 自动路径，实验核验上游强制键、路径状态、输入对象、停挖及实际服务端效果，不可安全隔离则用自写受限局部技能。

正常移动可候选从选项的绑定键维持按住/松开状态，视角以当前自身 `yaw/pitch` 在每次本地更新最多变化经配置的角度而非瞬转；紧急水桶、剑/盾的攻用也须走当前客户端准星、所持物、GUI 与服务器动作限制。**`setYaw/setPitch` 是本地角度接口而不是人类视觉技能保证；禁止 `setPos/teleport` 一类修改人物位置**。`KeyBinding.setPressed(true)` 未必等同产生一次 `wasPressed` 脉冲或真实鼠标事件；要分别验证“持续按住走路/举盾”和“一次点击攻击/GUI/切槽”的正常游戏输入路径，不靠重复 setPressed 伪造点击。GUI 槽位仍按当前服务器同步后的 handler 使用现有[动作契约](action-contracts.md)，不凭按键模拟绕过校验。

每次取消、被反射抢占、GUI 打开、断线、死亡、切换 A/B 模式或进程正常退出，都必须把 arbiter **曾按住的键松开**、拒绝旧 `intent_generation`、停止继续更新视角；恢复前确认当前画面/所持物/窗口/服务器同步并取得新 lease。若原生玩家键盘同时输入，可首期明确专用无人手控客户端，检测到真实键鼠输入时让渡或暂停 Kin；接管/交还时不能误松掉玩家正按住的键，此情形需原型中分别测键值所有权和输入优先级，不可仅靠软件缓存假定已识别物理输入。窗口失焦/聊天输入框/ESC 菜单不应让旧 lease 持续移动或把自动按键打进聊天。

阶段 0 的最小同服回放：空手转头、按住前进后在崖边松开、在聊天与工作台之间切屏、按键冲突/窗口失焦、tick 重入/帧率低、模型迟到、Baritone 接管与反射抢占、击杀/死亡/离线 A 模式退出；记录 lease、每帧/每 tick 首次输入、真实按键状态、视角变化、服务器可观察结果和释放延迟。对目标服只能依正常账号与私服准入，且需按最初[版本矩阵](version-license-matrix.md)实际组合构建；本文件只把必验输入时序与失败回退写明确，**不能凭 `setPressed` API 宣称已经控制一个能独立玩原版的玩家**。对应研究台账 R02、R06、R08、R11、R18。
