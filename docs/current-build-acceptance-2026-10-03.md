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

局部请求与最终目标已分开：已有数量/中间产物只记REQUEST_ALREADY_SATISFIED，目标未满足时按观测允许的动作做有界本地改线；模型超时后的反思也逐个排除无法支付的候选，保留原TIMEOUT及材料前提。run-67/68分别停在材料不足和超时后的不可支付回退，失败保留，未重复不改代码赌结果。修正后的run-69（3c34378d079a4168a224d57529b288b8，会话4e336e7491a446e2ada82927011a427a，本地和平模式）完成8木板、选中目标且关窗：GOAL_HELD_IN_HAND、goal_met=true，11真实模型调用，7模型动作/4本地回退，10确认/1前提变化中断，172观测/0拒止，input_release_failed=false。估算73 micro不等于供应商账单。127项心智/自主循环回归通过；这是普通真模型运行记录，不是sealed evidence，不支持长期生存或纯模型逐步控制的主张。

后台模型测试：配置页显式POST，共享回环/同源/CSRF校验，拒绝并发重复调用；返回状态、具名原因、耗时、调用记录与估算成本，不执行模型决策。实际模型函数调用一次connected（2906ms、timeout8000ms、估算3 micro）；真实浏览器经Vite代理调用实际Gateway，在独立model-test-browser根保存off后得到MODEL_NOT_CONFIGURED/零调用，390px无横向溢出。两者分别证明真实供应商调用与实际浏览器/HTTP链路，不宣称该浏览器路径联系了供应商。113项相关配置/HTTP/模型测试、236项前端全量、全仓pyright、构建通过；详细复验入口见[Dashboard说明](../dashboard/README.md)。历史只读审批文案从用户页头移除。

后台服务器设置与探测：SQLite修订比较写入，冲突保留原配置；显式探测以内容摘要固定目标快照，远程地址需独立许可，禁止草稿探测。实际浏览器→Vite→Docker Gateway→容器本地Minecraft链路通过：run-70为1.20.1和平模式，127.0.0.1:25566；保存后刷新保留端口，探测OBSERVED/763/1.20.1，linux-x86_64匹配RESOLVED。390px无横向溢出，截图已查看；此探测没有启动客户端，不属于入服/生存验收。76项后端配置/权限/版本探测测试、239项前端全量、全仓pyright和构建通过。Windows未登记匹配身体构建时仍具名拒绝支持，不以Linux结果代替。受管启动已完成并活体收口（见下段）；暂停/恢复仍未接入。

后台受管启动（2026-10-03，同一受控 Docker 形态）：Gateway 现持有一个有界受管启动任务（显式确认；绑定已保存服务器修订与版本探测，未登记版本具名拒绝；时限/步数/下载预算；作业记录落盘，读取不重启任务；取消经文件+事件双通道，先释放后终止）。受控服务器以 `--allow-player Kin` 重启（server run 目录 run-71，和平、loopback）后，浏览器 e2e `session-start-live.spec.ts` 两发连续 PASS（47.3s/48.8s）：job `ce7c970bf30d461eaa96862488bca0e9`（会话 `31e0de496ec442a98b34fead584383bd`）与 job `87d2fac07c4047478f327502f9106732`（会话 `bad2954f5b784a29815faad57295ae90`）均实际入服，服务端日志逐字 `Kin joined the game` / `Kin lost connection: Disconnected`；面板停止后两份作业记录均为 `phase=ended · outcome=STOPPED_ON_REQUEST · inputReleaseFailed=false · bridgeLostReason="" · installed=0/total=3639`，stop receipt 为 `release=NOTHING_HELD`（观察模式不持输入租约；不替代持键场景的 released/unconfirmed 读数）。首提失败如实保留：白名单为空的 run-70 曾拒止 `Kin`（`You are not white-listed on this server!`），修复是按既有工具重启服务器并显式 `--allow-player Kin`，判据未放宽。这两发是普通运行记录，不是 sealed evidence；取消（准备/监督中）、时限到期、客户端崩溃/被杀的收尾映射目前只有单测覆盖，活体读数列为下一卡。全量 `3675 passed, 2 skipped`、ruff/pyright 0、前端 240 项与生产构建通过。

受管生命周期 C009（2026-10-03，普通记录、非封存）：同一 run-71 本地和平服务器、观察模式、0 自主步骤/0 模型调用。当前作业准备取消 `90f46ff6ccd8474e9e30bfba402e081c` 为 START_CANCELLED、无 outcome；时限 `11ce72b9bfa246379bd5bf4c58f0c9cf` 为 STOPPED_ON_REQUEST/RUN_DURATION_EXPIRED；客户端被杀 `9a44d916daf844489e32553341ed3377` 为 failed、退出码 -9。Gateway 丢失案例 `37314233c05d40dfbe360107cdc05de4` 实际入服后监督进程被定点终止，新 Gateway 读到 interrupted/SUPERVISOR_NOT_RUNNING；三次读取前后作业摘要与 overlay 数不变，没有自动重连或重放。显式停止回执 release.unconfirmed，随后有界轮询确认空闲；不能算确认松键。前两次恢复工具失败分别为已空闲时重复停止、停止返回后立即要求空闲，历史作业未删除；工具现处理这两个实际时序。最新恢复报告 `.tmp/managed-gateway-restart-20261003.json`，重复使用入口是跟踪工具 `tools/verify_managed_session_lifecycle.py`。53 项相关后端测试/类型检查、19 项前端定向测试/构建已通过，新增文件共享冲突三项后作业测试 14 项通过。非空租约、断连与持键状态读数继续验收，不用 NOTHING_HELD 或 unconfirmed 替代。

非空输入的后台停止（C010 部分验收）：CLI 通用移动控制、非自主/无模型调用，run `7a79f73f87a94dd38a9a226a4ba44208`、session `1d31eeda5b3a4c1ab75070c7aacdc93c`。后台停止前同一 run 有 control.move.v1 租约且无 InputReleased；停止回执 released=[6720]、unconfirmed=[]、unresolved=[]，随后账本 InputReleased(had_lease=true, reason=EXPLICIT)、ClientProcessExited(STOPPED_ON_REQUEST)，CLI exit=0、后台 idle。工具 `--only-held-stop` 把这些前后读数写 `.tmp/gateway-held-stop-20261003.json`。首轮门禁拒绝多版本 profile，随后按后台已探测的 1.20.1 绑定单版本；一次报告整理失败为空 stdout，改从同 run 账本验证实际收尾后定向复验 PASS。该结果不是后台自主启动的持键取消或断连释放验收，C010 尚未完整收口；和平夹具不证明生存。

后台自主非空租约恢复（C010 有界覆盖）：跟踪工具 `tools/verify_managed_autonomous_recovery.py` 启动容器回环决策测试端点，明确标 control_path_test_double；没有真实 LLM 调用或密钥，测试动作是参数化 turn_to，不宣称方向控制等同持续按键。job `ba52cbedadd043219dcc940c1a92d28e` / run `c28eff422cdc41ef8b346f9472b96ad5` 入服并调用测试端点后，在 InputReleased 尚不存在、七项能力共享非空租约时后台取消，ended/START_CANCELLED/STOPPED_ON_REQUEST、InputReleased(had_lease=true, EXPLICIT)、idle。job `185577173c51451cac1a39a8e1e48221` / run `5545c4f2dc6540279eea3455227bea04` 同样先持非空租约，再定点 SIGKILL 该会话客户端；failed/BRIDGE_LOST/-9、idle，无残留活客户端。此例 inputReleaseFailed=false 仅是 Core 发送释放未报错，不是已退出 Bridge 的确认；面板已显示释放确认不可用。报告 `.tmp/managed-autonomous-recovery-20261003.json` passed=true、originalGatewayConfigurationRestored=true；结束后只读复核 idle，端点停止。15 项定向后端、3 项面板测试、前端生产构建及自有工具 Ruff/Pyright 通过。尚未证明仍存活客户端断连/watchdog 松键或死亡后继续生存；不替代普通难度生存验收。下一项玩家可见生命/饥饿观察与通用食用。
