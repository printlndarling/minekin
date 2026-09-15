# Baritone 1.21.4 源码读数审计：`legitMine` 不等于玩家等价

核查时间：2026-09-16；固定源码 `cabaletta/baritone@78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8`。这只是**静态源码审计**，没有把 API 构件装进 Kin、构建或登入私人服。审计对象为普通模式的采矿目标与路径方块数据，而不是证明 Baritone 必定实际透视挖到矿。

| 代码证据（同一源码 commit） | 能得出的结论 | 不能据此宣称 |
| --- | --- | --- |
| [`MineProcess.searchWorld`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/process/MineProcess.java) 通过 `getCachedWorld().getLocationsOf` 查询特定方块的已缓存位置，再用 `getWorldScanner().scanChunkRadius` 搜索已加载区域 | **非 `legitMine` 的目标发现可能借已缓存/已加载区块获得超出 Kin 可见域的矿点**；是否被当前服反矿透机制遮掩取决于实际服务端 | 有权限查询服务器未发到客户端的世界真值；缓存数据实时准确 |
| 同文件 `rescan` 在 `legitMine=true` 时提早返回，但 `addNearby` 遍历脚下 ±10 方块立方体，先用 `BlockStateInterface.get0` 判断是否是目标矿，再判断 `reachable`，另有默认关闭的 `legitMineIncludeDiagonals` 分支 | `legitMine` 可关闭这一条全局重扫路径，但**不能把读取候选方块状态当作眼睛已经看见**；可达判断不等于当前镜头、亮度、无遮挡像素可辨识 | `legitMine` 绝对不会利用隐藏数据；其实际挖矿必然违背规则；关闭 diagonals 就够公平 |
| [`BlockStateInterface.get0`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/utils/BlockStateInterface.java) 先查当前已加载 chunk，否则会查 Baritone 已存 `CachedRegion`；[`ChunkPacker.pack`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/main/java/baritone/cache/ChunkPacker.java) 遍历 chunk 内块状态并索引特殊方块；[`Settings`](https://github.com/cabaletta/baritone/blob/78d3613e8c2e4c2f4bb56a6d84fe2844bd6d22e8/src/api/java/baritone/api/Settings.java) 设 `chunkCaching=true`、`legitMine=false`、`allowOnlyExposedOres=false`、`exploreForBlocks=true` 为默认值 | 无自定义约束直接使用默认参数不符合 Kin 的普通玩家感知目标；单独关磁盘缓存仍允许读已加载 chunk 的未暴露方块 | 设置 `chunkCaching=false` 或 `allowOnlyExposedOres=true` 就已证明所有导航/采矿符合玩家等价 |

## 决策与最小验证

普通模式**不得把原版 `mine`/默认扫描作为自动采矿的发现层**。Kin 的目标发现由经过截图/视锥/遮挡/亮度测试的 `PlayerObservation` 提供，并带 `observed_target_id`；本地导航的障碍查询只能使用已经申明的短半径/短 TTL 碰撞辅助，不得回流人物信念，过去缓存不能直接给下一次新矿物目标。这是我们的目标接口约束，**目前并未证明可以对未修改的 Baritone 全路径算法实施此权限隔离**。

首个原型若试 Baritone API：首先基线固定 `chunkCaching` 等设置并记录实际值（默认值不可接受）；审读完整导航/建造/采集调用图，记录每次 `get0`、cache、scanner 和 path target 的坐标、来源、消费者、半径和时间，特别测试墙后矿、被遮蔽树、过去缓存矿、非玩家视野内区块、跨世界/重启与 `legitMine` 开关；对照测试截图，分别统计**隐藏读数、隐藏读数影响目标/路线、权限越界**。若 API 层不能严守隔离，则不把它用于普通模式，转为自写受限局部寻路/合法客户端输入或评估经许可的可隔离适配器；不能仅过滤 LLM 输出而保留底层隐形全局扫描。允许的落地水短时碰撞例外与明确按服务器规则启用的矿透模式分别审计，不混为一谈。

这个失败回退将增加研发工作量，但不意味真实客户端自治玩家不可实现。具体全路径耗时、动作成功、许可合规和服端反作弊效果均是下一阶段必须实测或进一步源码核查的事项；此文不能用作“已完成玩家等价”的验收报告。
