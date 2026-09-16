# 单 Kin 原版建造与红石：从设计意图到真实放置

静态核对日期：2026-09-16，Minecraft Java 1.21.4 / Yarn `1.21.4+build.8`；**尚无 Kin 的体素规划、实际放置、小屋美感或红石实验**。外部多模态视觉默认关闭；普通施工基于玩家可观察的方块/地形、本人资源、本地几何规则与放置反馈，不需每一块调用模型。人物是否愿意盖家、风格与工期由其目标/人格判断；系统仅提供有界的施工技能，而不是统一的“一键完美房屋”模板。

## 已确认可试的原版客户端接口

[`BlockHitResult`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/util/hit/BlockHitResult.html)携带命中方块位置、表面方向及射线接触点；[`ClientPlayerInteractionManager.interactBlock`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/network/ClientPlayerInteractionManager.html)使用真实本人、手与命中结果返回 `ActionResult`。[`ItemPlacementContext`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/item/ItemPlacementContext.html)列 `getBlockPos/getPlacementDirections/getPlayerLookDirection/canPlace`；[`Block.getPlacementState`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/block/Block.html)及[`FacingBlock.FACING`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/block/FacingBlock.html)说明方块姿态可能依赖点击面/玩家视角/上下文。签名证明可研究*逐块合法交互*，**不证明任意构造 `BlockHitResult` 就是鼠标实际可碰到的位置、动作能被服务器接受、方块朝向满足蓝图**。放置候选需从当前玩家准星或自己实际可见、可达到的表面导出，检查距离、遮挡和视角控制；严禁走“目标坐标→伪造命中/远距交互/直接写世界方块”的捷径。

## 工程契约（技能提供能力，Kin 决定是否执行）

`BuildIntent` 记录 Kin 自己提出的用途、风格偏好、位置偏好/领地约定、允许材料/工期和可放弃条件。设计层把已观察施工范围映射成**局部** `BuildPlan`：层高、门/通行/储物意图、局部格子、每格材料与预期朝向、若地形未看清标为 `unknown`。知识丰富能提出更多备选和自己想试的结构，知识欠缺时可用基本规则、询问朋友或查公开机制；实际造得好与否按施工成功、功能和反馈评定，不凭知识档案虚称技术高超。

局部 `PlacementTask` 只使用 Kin 已知范围、当前可见支撑面与当前库存，先选择安全可站位置，再正常移动→逐步转头→核当前 `crosshairTarget` 的方块和面→正常手持材料交互→等待客户端实际可观察更新与库存/界面反馈→核位置、**方向属性是否符合设计**。自然客户端交互 `ActionResult` 非服务端最终成功凭据；同一格已被别人改动、物品缺少或玩家被击退时先停、重新观察、修订计划。有限碰撞例外仅用于即时安全，不灌入隐藏地图/未观察建筑。拆错块必须另行核权属，自己的工地也可允许放弃、修补或歪着继续，保留 Kin 风格与犯错。

真正的建造难点不仅“在哪里放”：依赖搭脚手架/材料补充、部分方块需支撑、门窗/床/楼梯/炉及红石元件朝向不同、可能会打开容器而非放置、多人环境有误拆/领地风险。不能统一假定“视角角度→FACING”对所有物品有效；按**具体方块/版本**建立可复核放置规则，无法预测时做单格受控实验，优先观测放置结果再修正。当前不承诺建筑美观、复杂红石正确或超人逐块精度。

红石分开两件事：机制知识（版本世界书/公开资料与个人知识树）和实际电路操作（功能规格→局部线路→逐个元件放置/朝向→用玩家实际可观察输入/输出做测试→故障定位/返工）。模型会画线路不等于 Kin 可以到位施工；若电路中间的细节不可从本人可见输入/输出证明，就只能记 `hypothesis`，不读未允许的底层红石真值或在未测试时自称“红石高手”。本地可用版本配方/元件定义，必要时按[资料查询契约](research-skill-contract.md)查**公开**攻略，资料不能修改人物或主机权限。

第一轮阶段 0 私人服回放：`2×3` 临时木墙→`5×5` 小屋（门/工作台/箱）、定向楼梯/炉/漏斗样例、按钮→红石粉→灯的微型电路；包含支撑面被遮挡、交互距离之外、错误面、库存不足、他人修改/权属拒绝、GUI 打开、突然受击、模型断网。记录每格“玩家真能看到的面/准星→动作→实际结果与库存”、放错朝向/缺块/返工、用时/材料/打断恢复、视觉模型调用次数（默认零），对施工后**人的审美评估**另报。成功率和角度/重试上限须在实验后定，不可预填“完美建筑”或上游 `build` 命令已解决 Kin 的创作。
