# 公开版本配方知识

`adapters/public_recipe_archive.py` 从已有本地版本 JAR 的公开资源读取知识，不连接服务器、不读取运行中服务器的私有注册表，不执行或解压 JAR。支持直接资源 JAR 与内嵌版本 JAR 的 server bundler；目前实测版本是 **1.20.1**，不宣称已完成其他版本适配。

查询入口：

```powershell
uv run --frozen python -m tools.inspect_recipe_knowledge <本地版本JAR路径> --version 1.20.1 --product minecraft:stone_pickaxe
```

可追加 `--sha256 <可信下载记录中的SHA256>`。不提供摘要时仍记录实际字节摘要，但**不保证文件来自可信发行者**；版本声明也不是发行者签名。该命令没有联网下载或游戏控制权限。

- 普通 shaped/shapeless 配方按资源字节导入，保留结果数量、形状、空格、item/tag 原料以及 OR 替代项；同一成品的多个配方全部返回，不偷偷选一个。
- tag 是公开知识中的符号，不是“背包里已有材料”。暂不展开标签、不猜测玩家库存，也不手工维护全量配方配置。
- 熔炼、特殊动态合成、锻造等类型单独计数为暂不支持，不伪造普通网格配方。错误版本、错误摘要、重复条目/JSON key、坏形状和超限源具名拒绝，不提供部分坏数据。
- 输出明确标记 `player_recipe_unlocked=unknown`、`current_server_compatibility=unknown`、`current_materials=not_observed`，所有记录均不是 live-confirmed。

2026-10-04 本地实测：已有 `.tmp/mc-1.20.1-server.jar` 的 SHA256 为 `3af73a9dc5a102e38147946360dd27d4d70bae7055bf91cf2151cd5d121b79e0`；1174 条资源中导入 822 条普通合成、其余 352 条按类型报告。查询石镐读出 3×3 布局、`minecraft:stone_tool_materials` 标签和木棍槽位，未添加物品专用动作代码。这是公开知识读取验证，不是游戏合成成功证据。

## 尚未完成的运行接线

当前 `PlayerMind` / `recipe_catalog` 仍使用四条过渡记录；此工具不改变其覆盖范围，输出 `runtime_planner_connected=false`。下一环需要把版本绑定的知识作为依赖送入通用规划接口，结合公开标签与真实库存解析 alternatives，并保持玩家配方书/当前 GUI 准入与游戏后验确认；模型可以提出目标或配方假设，但知识不能直接签发按键。优先替换过渡目录，不逐物品追加动作链。
