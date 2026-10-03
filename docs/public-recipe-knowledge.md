# 公开版本配方知识

`adapters/public_recipe_archive.py` 从已有本地版本 JAR 的公开资源读取知识，不连接服务器、不读取运行中服务器的私有注册表，不执行或解压 JAR。支持直接资源 JAR 与内嵌版本 JAR 的 server bundler；目前实测版本是 **1.20.1**，不宣称已完成其他版本适配。

查询入口：

```powershell
uv run --frozen python -m tools.inspect_recipe_knowledge <本地版本JAR路径> --version 1.20.1 --product minecraft:stone_pickaxe
```

可追加 `--sha256 <可信下载记录中的SHA256>`。不提供摘要时仍记录实际字节摘要，但**不保证文件来自可信发行者**；版本声明也不是发行者签名。该命令没有联网下载或游戏控制权限。

- 普通 shaped/shapeless 配方按资源字节导入，保留结果数量、形状、空格、item/tag 原料以及 OR 替代项；同一成品的多个配方全部返回，不偷偷选一个。
- tag 是公开知识中的符号，不是“背包里已有材料”。导入器从同一份版本资源递归展开公开 item tag；缺少必需引用、循环引用或超限具名拒绝。它不猜测玩家库存，也不手工维护全量配方配置。
- 熔炼、特殊动态合成、锻造等类型单独计数为暂不支持，不伪造普通网格配方。错误版本、错误摘要、重复条目/JSON key、坏形状和超限源具名拒绝，不提供部分坏数据。
- 输出明确标记 `player_recipe_unlocked=unknown`、`current_server_compatibility=unknown`、`current_materials=not_observed`，所有记录均不是 live-confirmed。

2026-10-04 本地实测：已有 `.tmp/mc-1.20.1-server.jar` 的 SHA256 为 `3af73a9dc5a102e38147946360dd27d4d70bae7055bf91cf2151cd5d121b79e0`；1174 条资源中导入 822 条普通合成、其余 352 条按类型报告。查询石镐读出 3×3 布局、`minecraft:stone_tool_materials` 标签和木棍槽位，未添加物品专用动作代码。这是公开知识读取验证，不是游戏合成成功证据。

## 运行接线与尚未完成部分

`RecipeKnowledge.materials_for(recipe_id, inventory)` 已能根据调用方传入的物品数量为一批配方匹配原料，保留空格；OR 替代项共享库存容量，不能重复花同一件物品。使用容量约束匹配，避免贪心先占稀缺原料导致假缺料；未知 tag、未知配方或数量非法返回不可解析。结果只是知识侧计划，仍不是当前服务器准入。

`PlayerMind` 已接可选 `CraftKnowledge` 依赖。配置公开源后，模型的可合成目标与通用 `craft_take_result` 材料由该源和当前库存推导；打开 GUI 后还必须出现在当前 GUI 的可合成集合中。旧四条目录不能绕过这个检查；库存变动时自主循环按同一知识源重算 offer。成品是否进入背包仍由原有游戏反馈判断，知识与模型选择都不等于 CONFIRMED。

运行前在 Core 进程配置：

```powershell
$env:MINEKIN_RECIPE_ARCHIVE='<本地版本JAR绝对路径>'
$env:MINEKIN_RECIPE_ARCHIVE_SHA256='<可信下载记录中的SHA256>'
```

composition root 按**实际启动 profile 的版本**绑定源，版本/摘要不符具名拒绝。没有配置时保持过渡目录路径；不自动扫描 `.tmp`，不偷偷联网。查询工具本身仍无游戏控制，所以工具输出 `runtime_planner_connected=false` 不代表配置过的 Core 未接线。

2026-10-04 起接通的是**逐层欠序的第一步**：`PublicCraftKnowledge.step_toward` 用同一份公开配方把目标递归展开（依赖先序、每层按各自 `result.count` 折算批次、tag 替代项按容量共享先扣当前库存、自食配方按名字拒止），返回"这一帧真能跑的最前欠步"——目标产品的中间层（如合成石镐前的木棍）因此会被解成可执行的 `craft_take_result`，而不是把缺料一律报成 `CRAFT_MATERIALS_MISSING`；拒止词与优先级不变（先网格、再背包、最后开着的界面的配方书，`GUI_RECIPE_UNKNOWN`）。模型摘要相应给出 `craft_plan_source=public_version_stepwise`、`multi_stage_plan_available=true` 与当前那一步（不是完整路线），`as_document.multi_stage_planner` 为 `stepwise`。

仍然未完成：**缺料时选择采集路线**（原始料见底时只报 `CRAFT_MATERIALS_MISSING`，采集由心侧改线）、**公开知识下的宽网格 enabler**（档案不携带 `opens_grid_side`，3×3 仍走既有策展路径或真实开窗读数）、**完整 GUI 收尾**与真实游戏验收。运行代码测试以脚本 provider 验证不同成品走同一个行为，不是实际 LLM 或游戏结果证明。
