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

1. **合成没有世界侧确认**：`craft` 仍是 `UNKNOWN / NO_CONFIRMING_OBSERVATION`，归因 `INSUFFICIENT_INFORMATION`；区分「客户端 tick 停住」与「Core 拒了每一帧」要扩 run 文档/封存 schema，那是主控保留的决定。
2. **结果槽产物无人取走**：Core 还没有「从结果槽点击取物」的技能与契约。这一步会改桥字节 ⇒ 又是一轮续封，故排在本次入库之后。
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
