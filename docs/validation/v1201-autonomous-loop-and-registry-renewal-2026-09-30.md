# V1201-AUTONOMOUS-LOOP-AND-REGISTRY-RENEWAL-001：1.20.1 自主闭环入库那批桥字节下的 registry 续封与门读数（2026-09-30，M 主控）

> **一句话结论**：本轮把「可用后台＋基础资源技能＋第一条自主游玩闭环」那批产品字节（含两处桥缺陷修复）一次性入库，并把 `tests/fixtures/registry/reviewed-tested-bundles.json` 的 1.20.1 行**续到这批字节自己产出的六枚 sealed bundle 上**——续完之后 `tools/verify_tested_provenance.py --data-root /data` 对该行的独立复读是 `verified: true`（桥 jar 按字节量，不抄钉值）。本轮**不晋级任何门禁、不动 `capabilities`/`gaps`、不动 mandatory 清单、不扩证据 schema**。

## 一、承载字节（先核摘要，再谈读数）

| 项 | 值 |
| --- | --- |
| 主干基线 | `e97c4e8`（本卡提交前远端 `main`） |
| `bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar` | sha256 `ff2540824ee354149cdc7230d40f9d1eacbbed267ef9cf9936f6f64778672519`，1,442,677 B（2026-09-30 本机现量；未跟踪产物） |
| registry 1.20.1 行 | `bridge_digest ff2540824ee3…2519` / `launch_plan_digest 924931e574de…6cc0` / `recipe_digest bd6afaeee9dd…2c78` |
| `tests/fixtures/registry/reviewed-tested-bundles.json` | `f1c5d2bc19f63667193d…`（blob/LF 口径；改前 `6dd2f4218388781b05c1…`） |
| `tests/fixtures/manifest.sha256` | `91af98e7ad1a79130ad5…`，其中第 89 行自钉 `6dd2f421…` → `f1c5d2bc…` |
| `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json` | `bd6afaeee9dd51e14417…`（= registry 行 `recipe_digest`，逐字相同） |
| `src/minekin_core/adapters/launcher/recipe.py` | `67cb349e9ba204e01db3…`（`BRIDGE_1201_JAR_SHA256` 钉到新 jar） |
| `tests/unit/test_version_resolution.py` | `74fea63dcfd789898f10…`（`BRIDGE_1201`/`PLAN_1201` 两常量） |
| `docs/version-license-matrix.md` | `863c7193130e61d5624f…`（第 30 行现势值） |
| 产品侧代表文件 | `application/autonomous_play.py 94f795b0b516d30be36c…`、`application/player_mind.py 3f27b04f68c1bcbae716…`、`application/world_skills.py 26075f9ca15d5543a333…`、`gateway/readmodel.py 10a563afbb0e148be067…`、`test-orchestrator/runner/demo.sh 1a913655459521998260…` |
| 远程服 | 未连接；`.tmp/local-test-server.txt` 未读；服务端由 run 自起且只听 loopback |

摘要口径与既有约定一致：`manifest.sha256` 与本表都记 **CRLF→LF 归一后的 sha256**（registry 在本检出是 CRLF 文件，270 对 CRLF；直接对原始字节取 sha256 会得到另一个值）。

## 二、这批字节给了用户什么

1. **后台能读到的自主状态**（`gateway/readmodel.py` + Dashboard）：技能逐步行（意图 → 结果 → 失败原因/归因 → 依据读数与核对读数）、心智段的目标与降级标记、`MODEL_NOT_CONFIGURED` 会原样写到面板而不是留白。
2. **基础资源技能可执行**：`break_seen_block`（从视野里的资源取木）与 `collect_dropped`（拾取）在真实 1.20.1 世界里都是 CONFIRMED；`craft` 只到「配方点击已发出并被桥接受」，世界侧确认仍缺（见第六节）。
3. **第一条自主闭环**：`demo.sh --autonomous` 不给动作序列、不逐步指挥，Kin 自己选目标、发一个技能、读下一帧判断世界是否同意，失败后调整。启动说明与已知限制在 `docs/local-demo-runbook.md`。
4. **本轮修复的两处桥缺陷属于这条路径的地基**：界面其实没打开；观察者采集器在界面真打开后会让客户端崩一次。二者都会改变桥字节，因此才有下面的续封。

## 三、续封引用的六枚 run（全部读自规范卷 `minekin-runner-data` 的 sealed bundle 本身）

六枚都记 `bridge_digest ff2540824ee3…2519` + `launch_plan_digest 924931e574de…6cc0`，与 M 离线用 `build_launch_plan(bundle-candidate-1.20.1.json)` 独立推导的那对逐字相同（正对照成立）：

| case | run_id | bundle_digest | attempt（旧→新） |
| --- | --- | --- | --- |
| V1201-010 | `9dd6cfd4c4f243e98a134ef000857ed1` | `eac79134c76c…378eb` | 3 → 5 |
| V1201-020 | `b96cd43a91644272991fd435d44daf9b` | `d02e844c5c5f…0cfdc` | 2 → 6 |
| V1201-040 | `5ff5210fee9544acaa9d14ac4b133640` | `eeb154fb886e…c6e19` | 2 → 6 |
| V1201-060 | `186ecd0ea129415c9d9f723f01f660be` | `ed0a7dd0fb34…2027e` | 1 → 3 |
| V1201-070 | `fc96c6bad6c84fb2bc55f0f4970878af` | `1b7b6f4f0c29…5810a4` | 2 → 4 |
| V1201-080 | `2c25e6a35d924fddbf4f3644e98dadf8` | `f435bcdc5ee4…c1e0e` | 3 → 5 |

`attempt` 取各 bundle `manifest.json` 的 `attempt.sequence`（对着三枚既有引用行验过这个对应关系）。旧行引用的那些 run 是桥字节改动前的构建，作为历史读数保留在旧文档里，不改写。

## 四、编辑集：为什么只有这四处

一条链：桥源码改动 ⇒ 新 jar ⇒ `recipe.py` 的 `BRIDGE_1201_JAR_SHA256` ⇒ bundle candidate 的 `source_digest` ⇒ `manifest.sha256` ⇒ registry 行的 `recipe_digest` ⇒ `adapters/launcher/provision.py` 的供应链拒止 ⇒ 全量里 17 枚红。

因此落地的最小集是：

1. `tests/fixtures/registry/reviewed-tested-bundles.json`（三枚摘要 + 六枚证据行）；
2. `tests/fixtures/manifest.sha256:89`（registry 自钉，必须同笔）；
3. `tests/unit/test_version_resolution.py:35-36`（`BRIDGE_1201`/`PLAN_1201` 两个常量；1.21.4 的两枚不动）；
4. `docs/version-license-matrix.md:30`（现势 jar 摘要与字节）。

`capabilities`（19 枚断言 token）与 `gaps`（8 项）不动，因为被引的这六案的断言 token 没有变化；v1201 的 case fixture 只按路径引用输入、不按摘要，所以 case 侧无需手改。

续封写入工具 `.tmp/m120-renew-apply.py` 的三条自测（本机实测）：恒等输入 ⇒ 渲染字节与原文件逐字相同（14,148 B、CRLF 保留、证据行键序固定），`manifest:89` 不变；只改一枚 `run_id` ⇒ 该行必须动（`6dd2f421…` → `b1c2de02…`），证明摘要由内容决定；只给 5/6 枚 ⇒ 具名拒止 `no supplied run for cited cases: ['V1201-080']`。

## 五、门读数（本机，逐条量，未量的不写）

| 门 | 命令 | 读数 |
| --- | --- | --- |
| 受影响的四案文件 | `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/unit/test_{auto_session,bundle_install,tested_provenance,version_resolution}.py -q` | `108 passed in 38.56s`，rc=0（续封前同一批是 17 failed） |
| 全量（无并发负载） | `PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q` | `3231 passed, 2 skipped in 751.86s`，rc=0；两枚 skip 是 `test_orphans.py:686`（本平台答不出这个问题）与 `test_silent_listener.py:123`（Windows 的 terminate 不是信号），均为既有平台性跳过。续封前同机全量是 `17 failed, 3214 passed, 2 skipped in 443.67s` |
| 全量（与 demo 容器并发） | 同上 | `1 failed, 3230 passed, 2 skipped in 802.22s`——红的那枚是 `tests/unit/test_gateway_identity_write.py::test_renaming_a_read_route_is_a_405_not_a_rename`；单独重跑该文件 `34 passed in 4.85s` rc=0，随后无负载全量转绿。**是负载下摘掉监听套接字导致的时限敏感 flake，不是本批字节的回归**，具名留此 |
| fixture 摘要 | `.venv/Scripts/python.exe tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK`，rc=0 |
| 断言登记 | `.venv/Scripts/python.exe tools/check_case_assertions.py` | `Case assertion implementations: OK (151 registered)`，rc=0 |
| 依赖边界 | `.venv/Scripts/python.exe tools/check_boundaries.py` | `Minekin package dependency boundaries: OK`，rc=0 |
| workflow 钉值 | `.venv/Scripts/python.exe tools/check_workflow_pins.py` | `Workflow pins: OK (every action is a commit, and each names its release)`，rc=0 |
| ruff | `.venv/Scripts/python.exe -m ruff check .` / `-m ruff format --check .` | `All checks passed!` / `433 files already formatted`，各 rc=0 |
| wheel | `uv build --wheel` + `python tools/check_wheel_boundary.py dist/*.whl` | `Wheel oracle boundary: OK (dist\minekin_core-0.0.0-py3-none-any.whl)`，各 rc=0 |
| CLI | `.venv/Scripts/minekin.exe --help` | 打印 usage，rc=0 |
| 面板类型 | `dashboard`：`pnpm run typecheck` | rc=0（CI 里没有 vitest/tsc 作业，这一格只有本机证据） |
| 面板测试 | `dashboard`：`pnpm run test -- --run` | `Test Files 13 passed (13) / Tests 137 passed (137)`，rc=0 |
| 桥静态五门 | `python tools/check_bridge_scaffold.py`、`check_bridge_host_boundary.py`（默认 + `--sources bridge-1201/src/main/java`）、`check_bridge_protocol.py`、`check_bridge_proto_java.py` | `Bridge scaffold pins: OK (2 root(s))` / `Bridge host boundary: OK (no server state outside the lifecycle adapter)` ×2 / `protocol kernel of bridge-1201: OK (Java 17 compatibility subset)` / `protobuf adapter: OK (verified Maven artifacts, Java 17 subset)`，各 rc=0 |
| 空白 | `git diff --check` | rc=0（只有 CRLF 转换 warning） |
| 独立供应链复读 | `docker run --rm -w /src -e PYTHONPATH=/src/src -v "$(pwd)":/src:ro -v minekin-runner-data:/data:ro minekin-runner:local python tools/verify_tested_provenance.py --data-root /data` | 1.20.1 行 `verified: true`（`jar_sha256 ff2540824ee3…`、`jar_size 1442677`，六枚引用 `sealed/consistent/result=PASS`）；整体 rc=1 只由 1.21.4 行的一枚 `BRIDGE_JAR_DIGEST_MISMATCH` 造成，见下 |

两处**如实说明**，不掩盖：

- **1.21.4 行那枚 `BRIDGE_JAR_DIGEST_MISMATCH` 是本机产物的差，不是钉值的差**：容器读的是宿主机工作树里未跟踪的 `bridge/build/libs/minekin-bridge-0.0.0.jar`（本机 2026-09-30 构建，1,405,180 B，`d9132f252b12…`），而该行钉的是 Linux 密封那枚 `0ee2070b97ba…`；同一份 1.21.4 **源树**摘要在报告里仍是 `recipe_source_digest a4a53cac…` = 行内值，即 1.21.4 源码一字未动，本轮也没碰。该行的十二枚引用 bundle 全部 `sealed/consistent/PASS`。
- **`pyright` 本机报 16 error、0 阻塞判定**：全部是同一类 `reportUnknownMemberType`——`pytest.approx(...)` 的 `expected: Unknown`，落在 `tests/unit/test_case_evidence_assertions.py`、`test_read_move_window.py`、`test_report_soak.py` 三份文件里。这三份都是 `git ls-files` 里的**已跟踪且本轮未改**的文件（`git diff --name-only` 对它们为空）。判别读数：把 `git archive HEAD` 导出的原始树（`.tmp/pyright-baseline`，含同样这三份文件）用同一个 venv 解释器再跑一次 pyright ⇒ `277 files analyzed, 0 errors`；同一份 `test_report_soak.py` 在工作树里单跑 ⇒ 3 errors。**同样的字节，换一棵树就不同结论**，所以这 16 枚是本机类型解析环境的属性，不是本卡字节引入的回归。本机 `.venv` 里 `pytest 9.1.1`（与 `uv.lock` 一致）且 `numpy` 未安装、也不在锁里；`pyright` 在受控镜像里没装，无法用镜像复现。**CI 自己的读数是绿的**：本卡提交 `589c765` 推 `codex/m120-preflight` 触发的 run `36657525247`，`python` 作业逐步 `success`（步骤 4 `uv sync --locked --dev`、5 `ruff check`、6 `ruff format --check`、**7 `uv run pyright`**、8 `uv run pytest`、9–15 各工具门与 `minekin --help`），`protocol` 与 `bridge-static` 两个作业的每一步也 `success`，整体 `conclusion=success`。所以那 16 枚是本机类型解析环境的属性，本批字节在 CI 的解释器与依赖集下没有类型回归。

## 六、仍然存在的缺口（具名）

1. **合成没有世界侧确认**：`craft` 仍是 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，归因 `INSUFFICIENT_INFORMATION`。这条缺口当初记的是「区分『客户端 tick 停住』与『Core 拒了每一帧』要扩 run 文档/封存 schema，那是主控保留的决定」——**那个前提已经不成立**：run 文档本来就带 `details` 这个自由字段，第八节把它填上了，三种收尾（帧没到 / 帧到了但背包同步号没动 / 界面没被看见打开）现在可以从同一份 run 文档判读，没有动任何 schema。剩下的缺口因此收窄为「合成确实没被世界确认」这一件，而不是「读不出来为什么」。
2. **结果槽产物无人取走**：Core 还没有「从结果槽/光标把成品放回背包」的技能与契约。**这一条原先记的『这一步会改桥字节 ⇒ 又是一轮续封』按新读数不成立**（第八节）：1.20.1 的桥在**已封的字节上**就吃槽位点击，缺的只是 Core 侧的技能与判据。
3. **1.20.1 行的 Java 口径未变**：`java_major 21` 是密封实际用的运行时，recipe 自己声明 17，`RUNNER_JDK_17_UNSEALED` 仍在 `gaps` 里；Linux Temurin-21 交叉复现也没在本轮重做。
4. **默认 registry 路径已实测恢复**：见第七节的活体读数。`docs/local-demo-runbook.md` 的 `--skills`/`--autonomous` 命令因此回到默认路径，2026-09-29 那条 rc=11 具名拒止作为历史读数保留。
5. **本次只声明这一批能力入库并把证据续到它自己的字节上**，不声明 1.20.1 线整体完成，也不移动任何门禁。

## 七、默认 registry 路径的活体读数（2026-09-30，run `f19caae6a1be42608b0f833fe79dfbdb`）

续封之前，这条路上写死的是拒止：2026-09-29 同机同路径跑 demo 时，安装在取 bundle 前具名拒止并以 rc=11 退出（`recipe … digests to bd6afaee…, not the reviewed 8ce43e26…`）。续封之后跑的是**不带任何 profile 旋钮**的默认命令：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar MINEKIN_DEMO_SECONDS=600 \
  bash test-orchestrator/runner/demo.sh --again
```

读数（同一次 run 的 stdout，私有演示卷 `minekin-local-demo` / `kin-local-demo`）：

| 格 | 值 |
| --- | --- |
| registry 侧决策 | `auto_bundle.kind=auto-bundle-decision`、`bundle_id=1.20.1-linux-x86_64-offline-java21`、`registry_revision c2aace9aed0b…`（与第五节独立复读报告里的 `registry_revision` 同一枚） |
| 引用件 | `recipe_path=/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json`、`launch_plan_digest 924931e574de…6cc0`、`protocol 763`、`version_text 1.20.1` |
| 供应链 | `status=ready`、`fetch_set 3639`、`reused 3639`、`installed 0`（热卷复用，未发生取件）；**rc=11 的 `SUPPLY_CHAIN` 拒止没有再出现** |
| 世界 | `domain: the session is playable`、`connection_state=PLAYABLE`、`perceived_information_class=PLAYER_EQUIVALENT`、服务端看到前进与停止 |
| 收尾 | `input_release_failed=false`、release `asked=[516] released=[516] unconfirmed=[]`、`outcome=BRIDGE_LOST`、退出码 14（harness 到点停问，正常收尾） |

这条读数的用途限于一件事：**证明默认（registry）路径在这批字节上重新可用**，因此 `docs/local-demo-runbook.md` 的 `--skills`/`--autonomous` 不再需要 `MINEKIN_DEMO_BUNDLE_PROFILE`。它不是脚本化底座那一步之外的技能判据读数，也不改变任何 case 的封存状态。

## 八、拾取会追、收尾会说的这批字节（2026-09-30，`9cef84a` → `67ec7fd` → `a5fe378`）

第七节之后又推了三枚提交，改动面只有三份文件（判别读数：`git diff --name-only f2c6351 a5fe378` 逐字返回 `docs/local-demo-runbook.md`、`src/minekin_core/application/world_skills.py`、`tests/unit/test_world_skills.py` 三行；对 `bridge/`、`bridge-1201/`、`proto/`、`tests/fixtures/registry/`、`tests/fixtures/manifest.sha256` 的过滤命中 **0** 枚）。桥字节与协议字节一根没动，所以**本节不移动任何 case 的封存状态**：第五节那六枚 V1201 引用和第七节的 `f19caae6…` 读数继续对它们自己的字节有效。

三枚给用户的是两件事：

| 提交 | 用户现在多出来的能力 |
| --- | --- |
| `9cef84a` | `collect_dropped` 不再「走一步就站着听」。它在窗口内每读到一帧更新的观测就朝掉落物重新转向，再迈 0.5 秒修正步——只有当剩余窗口还容得下「一次迈步 + 一帧能拿去判据的读数」时才迈，其余时间继续听。重复的仍然只有转向与移动；§4 那条「有副作用的点击绝不自动重试」原样保留。这修的是 run `974a2d19a0a741ad9514437bbee7fc14` 那种收尾：走到木头前面差一步，然后站着等到窗口关闭。 |
| `67ec7fd` | `docs/local-demo-runbook.md` 第 9/10 条把这一步的读法写成入口：操作者不改代码就能分开「通道静音」与「帧到了但东西还在地上」。 |
| `a5fe378` | `craft` 的每种收尾都带它究竟看过什么：最后拿去校验的 tick、窗口前后的背包同步号、脚下那帧有没有报出打开的界面。 |

`details` 是 run 文档本来就带着的自由字段（`SkillOutcome.details` ⇒ 封存文档里的 `"details": {}`），这三枚只是把它填上，**没有扩任何 schema**，所以第六节 1) 里「要区分得先扩 schema」那条前提被按新读数收窄。现在三种合成收尾可以从同一份 run 文档判读：

| `reason` | `details` 的形状 | 结论 |
| --- | --- | --- |
| `NO_CONFIRMING_OBSERVATION` 且 `newest_checked_tick == pre_tick` | 帧没到 | 窗口内 Core 一帧新读数都没收到——是客户端/通道那边停了 |
| `NO_CONFIRMING_OBSERVATION` 且 `newest_checked_tick > pre_tick`，两枚背包同步号相等 | 帧到了、背包没重同步 | Core 收得到 tick，但配方点击没让**同步背包**变化（这一枚以前完全读不出来） |
| `SCREEN_NOT_CONFIRMED` 且 `gui_open=false` | 界面没被看见打开 | 打开指令发出去了，脚下那帧仍不报 GUI；该臂不发出 `GuiClickInput`，单测按「没发点击」钉住 |

**顺带量到的一件，改写了第六节 2) 的口径**：1.20.1 桥在已封字节上就支持槽位点击——`bridge-1201/src/main/java/org/minekin/bridge/runtime/BridgeIpcWorker.java:726-735` 的 `case SLOT -> view.clickSlot(...)`，`action/WorldActionController.java:129-137` 把它接到 `clickSlot(currentScreenHandler.syncId, slotId, button, toSlotAction(mode), player)`，`runtime/BridgeIpcWorker.java:1663-1671` 对「没指名模式的槽位点击」具名拒止。协议侧 `GuiSlotClick`/`SlotClickMode`（PICK/QUICK_MOVE/SWAP/THROW）也早已进 `proto/minekin/v1/control.proto:248-252` 与生成的 `control_pb2`。所以「取成品」这一步**不需要动桥字节、不需要新一轮续封**；它是 Core 侧欠的一个技能和一条判据。判据的形状也量清了：观察面 `GuiScreenValue`（`src/minekin_core/domain/perception.py:369-375`）只带 `screen_id` 与 `sync_id`，**看不到结果槽或光标**，因此取物后的确认只能落在同步背包上——这与 `verify_craft` 要求「成品在同一枚同步 revision 上上涨」是同一件事，也解释了为什么配方点击发出去了而合成拿不到 CONFIRMED。本节只记录这条读数，取物技能排在它自己的提交里，未与这三枚混批。

本地门读数（`cd` 到本工作树、`export PYTHONPATH="$(pwd)/src"`）：

| 门 | 命令 | 读数 |
| --- | --- | --- |
| ruff check | `.venv/Scripts/ruff.exe check .` | `All checks passed!`，rc=0 |
| ruff format | `.venv/Scripts/ruff.exe format --check .` | rc=0，`433 files already formatted` |
| 技能单测 | `.venv/Scripts/python.exe -m pytest tests/unit/test_world_skills.py -q` | `19 passed in 4.38s`（本批前 16 枚） |
| 全量单测 | `.venv/Scripts/python.exe -m pytest -q` | rc=0，`3237 passed, 2 skipped in 652.55s (0:10:52)`，跑的就是 `a5fe378` 这批字节（本机全量比 CI 慢，但结论一致：CI 第 8 步 `uv run pytest` 三枚 SHA 都 `success`） |
| pyright（本机，按文件） | `.venv/Scripts/pyright.exe src/minekin_core/application/world_skills.py` | `0 errors, 1 warning`（那条 warning 是 `google.protobuf.message` 无源码，与本轮无关）。整树那 16 枚 `approx` 噪声仍落在本轮未改的三份测试文件里，判别方法见第五节的 `git archive` 对照 |

CI 自己的步骤级读数：三枚推送 SHA 各触发一枚 run，`9cef84a`→`36663998358`、`67ec7fd`→`36664241107`、`a5fe378`→`36665047666`，三枚都 `status=completed / conclusion=success`。**逐作业逐步**：`python` 作业 15 步（第 4 步 `uv sync --locked --dev`、5 `ruff check`、6 `ruff format --check`、**7 `uv run pyright`**、8 `uv run pytest`、9–12 四份工具门、13 `uv build --wheel`、14 `check_wheel_boundary.py`、15 `minekin --help`）三枚全 `success`；`protocol`（buf build/lint/format + 校验仓库内 protobuf）与 `bridge-static` 每一步也 `success`。取法（token 只进 shell 变量、不打印）：

```bash
TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | sed -n 's/^password=//p')
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/printlndarling/minekin/actions/runs?head_sha=$(git rev-parse HEAD)"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/printlndarling/minekin/actions/runs/<run_id>/jobs"
```

**本节没有取的读数（具名）**：新的迈步逻辑在真实 1.20.1 上的活体重跑——即 `collect_dropped` 是否因此转 CONFIRMED，或仍 UNKNOWN 时 `details` 点名哪一臂——还没拿到。受控 runner 起不来：2026-09-30T03:47Z 复量 `docker version`，客户端半边正常（Docker 29.5.3 / API 1.54 / desktop-linux），服务端半边逐字回

```
request returned 500 Internal Server Error for API route and version http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.54/version, check if the server supports the requested API version
```

所以本节能声明的止于「判据与读法已经进产品、过了 CI 与本机的门」，**不声明拾取已在真实游戏里被重验**，也不声明合成能拿到世界确认。同一句限制在 `docs/local-demo-runbook.md` 第 9 条里也写着，等引擎恢复就补跑一次 `demo.sh --skills` 并把读数续到那批字节上。

保留边界本轮同样一处未动：不接远程测试服、不解冻 HOST/PERSIST 与在线认证、不扩证据 schema（`details` 是既有字段）、不移动任何门禁；Dashboard 的通用写控制端点继续关闭，唯一的已授权写面仍是停止态改名。

## 九、合成那一笔换成会落进背包的点击（2026-09-30，`5000106` + `b757282`）

**这批字节改的是「合成发哪一种点击」，不动桥、不动协议、不动 registry。** 第八节量到的形状是：配方书的普通点击（`craftAll=false`）把成品留在**光标**上，而 `GuiScreenValue`（`src/minekin_core/domain/perception.py:369-375`）只报 `screen_id` 与 `sync_id`、`inventory` 也不报光标那一格——所以 `verify_craft` 可以在材料下降的那一帧之后一直等不到成品上涨，demo 反复报的 `NO_CONFIRMING_OBSERVATION` 就是这个形状。craft-all 才是把成品放进同步背包的那一笔事务。

### 1. 落地的能力

| 面 | 变化 | 用户现在能做什么 |
| --- | --- | --- |
| 技能 | `world_skills.craft(..., craft_all: bool = True)`；线上传 `control_pb2.GuiRecipeClick(recipe_id=..., craft_all=...)` | 调用合成默认拿到的就是「成品进背包」那一笔 |
| 判定 | `_craft_details(...)` 现在多一个键 `craft_all`，随 `SkillOutcome.details` 投影进 run 文档与面板 | 面板/日志能读出这一笔发的是哪种点击，不用再猜 |
| 计划 | `skill_plan.py` 的 `_DEFAULTED["craft"] = ("craft_all",)`，`_flag` 只接受真正的布尔；`craft_all: "true"` 这种字符串会**具名拒止**（`skills[i] (craft) needs craft_all to be true or false`） | JSON 计划可以自己点名要哪一种事务，写错形状会被拒绝而不是被猜 |
| 心智 | `player_mind.py` 的 `CRAFT_CHAIN` 不传该参 ⇒ 继承默认 True | 自主链条每一步的合成都落在可读回的地方 |
| 文档 | s2 契约 §3 的 `GuiClickInput` 行、§4 craft 行、§5「技能做五件事」；启动说明第五节 10–11 条与 `MINEKIN_DEMO_SKILL_PLAN`；总规划 S2/S3 行 | 启动说明里那条「合成拿不到世界确认」的口径按新字节重写 |

`examples/skill-plan-gather-and-craft.json` 故意**不加** `craft_all`：默认值就是能收尾的那一笔，示例计划不该重复它。

### 2. 为什么这一批不需要续封

`git diff --name-only 146de05 HEAD` 只列出这 8 个文件（3 份文档 + 2 份产品源 + 3 份测试），对 `^(bridge/|bridge-1201/|proto/|tests/fixtures/registry/|tests/fixtures/manifest\.sha256)` 的命中数是 **0**（`grep -Ec` 现量并打印 `grep rc=1`）。桥字节、协议字节、registry 行与 manifest 自钉都没动 ⇒ 第八节引用的六枚 sealed bundle 仍引用当前桥字节，无需新一轮续封。`details` 是既有自由字段，填一个键**不是**证据 schema 扩展。

### 3. 本机门读数（逐条量，未量的不写）

| 门 | 命令 | 读数 |
| --- | --- | --- |
| ruff check | `.venv/Scripts/ruff.exe check .` | `All checks passed!`，rc=0 |
| ruff format | `.venv/Scripts/ruff.exe format --check .` | rc=0，`433 files already formatted` |
| pyright（按改动文件） | `.venv/Scripts/pyright.exe src/.../world_skills.py src/.../skill_plan.py tests/unit/{test_world_skills,test_skill_plan,test_autonomous_play}.py` | `0 errors, 4 warnings`，4 条都是既有的 `google.protobuf.message` 无源码告警 |
| 全量单测 | `.venv/Scripts/python.exe -m pytest -q -p no:randomly` | rc=0，`3241 passed, 2 skipped in 416.95s (0:06:56)` |

全量这一枚是确定性顺序重跑，日志留在 `.tmp/pytest-craft-all2.txt`。第一次跑（`.tmp/pytest-craft-all.txt`）是 **7 failed / 3234 passed**，如实记在这里：其中 6 枚是 `TypeError: TapeSkills.craft() got an unexpected keyword argument 'craft_all'`，落在 `tests/unit/test_autonomous_play.py` 的假技能上（`skill_plan.py` 派发处新增关键字），修法是让那枚 tape 收下并记录 `craft_all`；第 7 枚 `test_renaming_a_read_route_is_a_405_not_a_rename` 抛 `ConnectionAbortedError: [WinError 10053]`，单独跑那两份文件是绿的，判定为本机 socket 在负载下的抖动，确定性重跑里也没有再出现。第一次跑还有一处读数事故值得记：命令写成 `pytest … ; echo rc=$? ; tail -3 …`，后台任务返回的是复合命令的退出码 0，而 pytest 自己是红的——第二枚跑把 pytest 当唯一命令，退出码才是判据。

### 4. CI 自己读到的字节

远端 `main` 逐字读回 `b75728273f225ec14d6d8b4f6612f1fbeba021a4`（`git ls-remote origin refs/heads/main`）。该 SHA 触发自己的 run `36670641061`（`https://github.com/printlndarling/minekin/actions/runs/36670641061`），三枚作业都在 2026-09-30T05:32Z 复量时 `status=completed / conclusion=success`，**逐作业逐步**：

| 作业 | 步 | 读数 |
| --- | --- | --- |
| `python` | 4 `uv sync --locked --dev`、5 `uv run ruff check .`、6 `uv run ruff format --check .`、**7 `uv run pyright`**、**8 `uv run pytest`**、9–12 四份工具门（`check_boundaries` / `check_case_assertions` / `verify_fixture_digests` / `check_workflow_pins`）、13 `uv build --wheel`、14 `check_wheel_boundary.py`、15 `minekin --help` | 15 步（含 Set up/checkout/setup-uv）全部 `success` |
| `protocol` | 4 `buf build`、5 `buf lint`、6 `buf format --diff --exit-code`、7 校验仓库内生成的 protobuf | 全 `success` |
| `bridge-static` | 4 无下载校验钉住的桥脚手架、5 拒止桥宿主适配器之外的服务端状态、6 无依赖的桥协议与适配器检查 | 全 `success` |

第 8 步这一步单独值得点出：CI 的 `uv run pytest` 跑的就是这批 Python 字节，它绿 ⇒ 「本机全量绿」不是只有我这台机器能读到。取法（token 只进 shell 变量、不打印）沿用第八节那两条 `curl`，把 `head_sha` 换成上面这枚即可。

### 5. 本节没有取的读数（具名）

新的默认点击在真实 1.20.1 上的活体重跑还没拿到：`craft` 是否因此转 CONFIRMED、`collect_dropped` 在追物那批字节下的活体结论，都要等受控 runner 起得来。2026-09-30T04:51Z 与 05:33Z 两次复量 `docker version`，客户端半边都正常（Context: desktop-linux），服务端半边逐字回

```
request returned 500 Internal Server Error for API route and version http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.54/version, check if the server supports the requested API version
```

`tasklist` 里 Docker Desktop 与 `com.docker.backend.exe` 都在，所以是 Linux 引擎不健康而不是没装；操作者已认领「重启 Docker Desktop 后由我补跑」这一格。因此本节只声明「判据与点击形状已经进产品、过了本机与 CI 的门」，**不声明合成已在真实游戏里拿到世界确认**。同一句限制写在 `docs/local-demo-runbook.md` 第五节第 10 条。引擎恢复后要跑的是同一条入口：

```bash
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar bash test-orchestrator/runner/demo.sh --skills
```

读数落在 run 文档的技能逐步行里，判法就是第八节那张 `reason` × `details` 形状表；这一批之后它多了一列可读的键。若仍回 `NO_CONFIRMING_OBSERVATION` 且 `newest_checked_tick > pre_tick`、两枚背包同步号相等，而 `details.craft_all == "true"`，那才说明 craft-all 也没让同步背包动，缺口就落在结果槽/光标取物那一格（启动说明第 11 条）。

保留边界本轮同样一处未动：不接远程测试服、不解冻 HOST/PERSIST 与在线认证、不扩证据 schema、不移动任何门禁；Dashboard 的通用写控制端点继续关闭，唯一的已授权写面仍是停止态改名。
