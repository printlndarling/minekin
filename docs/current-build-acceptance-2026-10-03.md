# 1.20.1 当前构建登记（2026-10-03）

当前 Linux/offline/Java21 构建可经默认 auto-bundle 入口入服、行走、停止。登记仅承认下列两个新运行的六项断言；用户远程服、Windows 身体、崩溃/watchdog/租约过期及更长生存不因此通过。1.21.4 登记与历史封存字节未改。

| 案例 | run_id | 结果 | 新封存摘要 |
| --- | --- | --- | --- |
| V1201-020 入服/快照/离开 | abfbcca66d79459aa400d705b0fb6c92 | PASS，摘要核验与独立重判一致 | b8dc206c7862314edf99f638c78486e6ae778fcd09a21aa98a3fb395135879cb |
| V1201-080 持键期间停止 | 1d4eb07a2bec47cabf46bad93363dafd | PASS，摘要核验与独立重判一致 | ea47c6d82d7e4264ba8f7fccfe244ffa6cd52a39f1f759839b0c17813b63c775 |

实际 Bridge jar：`0c8adfb7bcaa5700cdb74e316ba9ab4fa5cb5acb995cc705d27f9ef09736972e`（1444472字节）；source：`fc0e4850719b7c812aeecf720e54f473c59ed2ab8855c01786a9a7ba84e43071`。启动计划：`8b577b622e046e836f2ac599441d2314f71b9459ffe08ab77bd5684d988d224a`；recipe审查摘要：`b82d5e356b2221d89b2ddd878afb2825d5eb5a5e8a0e966aaf2ad74e71e9b95f`。当前1.20.1条目的provenance读数无findings、verified=true；该核对限此条目，不宣称全历史数据根齐备。

封存目录在 Docker volume `minekin-local-demo2` 的 `/data/kin/kin-3x3-fresh-20261002/run/evidence/<run_id>/`。`tools/rejudge_evidence.py` 只读核对两份资料均返回 agrees，无disagreements。旧资料不迁移、不改写；当前登记替换旧构建引用后，将旧构建才证明过的额外能力标为 CURRENT_BUILD_UNSEALED gaps，完整历史可从Git与原封存目录追溯。

停止首轮 `519523189b224c5cb38e1a84a0f5cc05` 如实封为 FAIL（摘要 `dcdce300fa323ab0d1e4a9a7861648aac1fce06e12186063d2b07e9284fad615`）：demo先等待行走结束再停，所以 HELD_NOTHING_WHEN_THE_SESSION_WAS_STOPPED。第二轮用原 run.sh domain 入口，120秒持键、无行走完成等待，在playable后的常规停止窗口发请求；判据未改。新PASS的attempt=2，失败记录保留。

默认自动入口普通复验 `a7313ff99b3c49998181289a5618ec6e`（会话dcf7bc6159a140d89248c19b5ff0cc55）：未指定候选profile，registry选包，实际PLAYABLE，服务端观察行走并停止，STOPPED_ON_REQUEST、input_release_failed=false。这是普通运行记录，不是第三份sealed evidence。

116项版本解析/fixture/provenance/安装/自动入口回归通过。真实模型复验工具默认亦使用自动registry；`--bundle-profile`仅作新候选明确覆盖，两个入口及目标传参有定向测试。完整项目仍在推进：不同模型目标、异常恢复、后台启动和生存待验证/开发。

后续不同目标运行 `2cf80ab6afa1446b8a0e2f178316e5a5`（8块木板、run-64、本地和平模式）暴露数量不足即结束的缺陷：8次真实模型调用后 stop_reason=GOAL_HELD_IN_HAND，但 goal_met=false，不能计成功。已修正结束条件为库存总量满足且任一匹配堆栈已选中；数量不足时不提供为结束而选择部分产物的动作。三个回归涵盖数量不足、跨堆栈选中及动作选择，相关122项测试通过。基线d527116全量3630项通过、2项平台跳过。修正后的真跑run-65在启动阶段被 OLD_CLIENT_UNPROVEN 拒绝，尚未验证游戏结果；下一步查明旧客户端归属记录，不接管不明进程。

史莱姆死亡发生在本机Docker的run-56（Minecraft 1.20.1，difficulty=normal，server-ip=127.0.0.1，port=25566）；服务端日志记载 Kin was slain by Slime。后续和平模式合成运行不属于生存验收，未连接用户远程服务器。

run-65启动误拒绝已定位：auto-bundle把底层已经判为命令行不匹配的left_alone PID也列入未解决客户端。入口现在只以unresolved拒绝，之后仍重新查询客户端身份；外来进程不接管、不发信号，历史marker不删不改。新的回归先红后绿；相关73项通过、1项平台跳过，全仓pyright通过。run-66（89fec0bf9d674a4cb54feeced5f5ac0f）经同卷默认入口实际PLAYABLE、正常停止且松键确认，证明启动恢复；最终goal_met=false，另一个局部合成请求满足被误标为整个GOAL_ACHIEVED的问题仍待修复，因此不计目标成功。
