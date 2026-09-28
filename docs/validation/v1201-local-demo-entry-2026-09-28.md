# V1201-LOCAL-DEMO-ENTRY-001：可重复执行的 1.20.1 本地端到端 Demo 入口，以及干净/重复两次真跑（2026-09-28，M 主控）

> **一句话结论**：`test-orchestrator/runner/demo.sh` 现在是用户可直接跑的端到端入口（探测版本 → 由 registry 选定并准备客户端 → 入服 → 转向/前进/释放 → 停止），**干净启动与重复启动各真跑过一次且都进到 `PLAYABLE`**；卡在这条路上的最后一个缺陷是产品侧固定的 30 秒握手窗，已升格为 CLI 开关 `session start --handshake-timeout-seconds`，默认不变。本轮**不封存证据、不登记 case、不动 mandatory/registry、不晋级任何门禁**。

## 承载字节（先核摘要，再谈读数）

| 项 | 值 |
| --- | --- |
| 主干基线 | `1ee6507`（本卡提交前远端 `main`） |
| `test-orchestrator/runner/demo.sh` | `bfa5add8af764904ccf7ab59937a9a25be487b224f76a67828f00c82ca0974e5`（本卡首次入库） |
| `src/minekin_core/cli/parser.py` | `8b9c25f58d1e15ba10e88b1607639f7f153c29ea047bcf50bc964e1a67c22708` |
| `src/minekin_core/bootstrap.py` | `7359eb134acc6ebb2530a18f5cfd9154ee7c47143a35dfe36a009d0915f3dfd5` |
| `tests/unit/test_auto_session.py` | `17fb09d780e3e1e258b506c80bda11da2f2c5399462b0e345232375e53917438` |
| `test-orchestrator/runner/README.md` | `2092e35d8b35c65828abee4f61409ab57383c72d6992ea206f8b07c4410c7bb4` |
| 服务端 jar | `.tmp/mc-1.20.1-server.jar`（未跟踪，经 `tools/verify_supply_chain.py` 取得） |
| 卷 | 干净启动跑在新卷 `minekin-local-demo` 的新 Kin 根 `kin-local-demo`；重复启动跑在 `minekin-m-demo-live2` 的 `kin-demo-0928b`（上一轮已装满 store） |
| 远程服 | 未连接；`.tmp/local-test-server.txt` 未读；服务端由本 run 自起（`/data/server-runs/run-1..2`，只监听 loopback） |

改动文件全集＝上表五份（`git diff --stat` 只列这五份 + 首次入库的 `demo.sh`），**不含任何 case 定义、registry、mandatory 清单**。

## 落地的业务能力

1. **`session start --handshake-timeout-seconds SECONDS`**（`parser.py`）→ 两个入服调用点都接上（`bootstrap.py` 的 `--auto-bundle` 支与显式 `--profile` 支），不传时仍取 Core 已审的 `DEFAULT_HANDSHAKE_TIMEOUT_S = 30.0`。
2. **`demo.sh`**：一条命令的组合入口，默认 1.20.1 受控离线形状但版本由 Server Profile 决定（脚本里没有硬编码版本号）；三种模式 `clean`（默认）/ `--again` / `--gateway`，前置缺件时以 rc=2 打印补齐命令；默认给客户端 90 秒握手窗（`MINEKIN_DEMO_HANDSHAKE_SECONDS` 可覆盖）。
3. **README**：入口用法、旋钮清单（含新握手旋钮）与「读数看 run 文档而不是退出码」的说明。

## 判别读数：同一行客户端日志对三个窗口的关系

判据取客户端 `logs/latest.log` 的 `Setting user` 行相对 `process.json` 的 `started_at` 的秒差——历史 7 枚 1.20.1 bundle 就是按这一格分成功/失败的（成功 3 枚 +17.0 / +17.4 / +21.8 秒；失败 4 枚 ≥+30.7 秒，且都在该行 1 秒后报 `BRIDGE_FAULT`）。

| 形状 | 握手窗 | 会话启动 → `Setting user` | 结果 |
| --- | --- | --- | --- |
| `kin-demo-0928b` 旧字节（无开关，30 秒） | 30.0 | **≥ 34.4 秒**（上一轮同一形状失败） | `HANDSHAKE_TIMEOUT`，`connection_state: null`，`entities_admitted 0` |
| 干净冷装 `kin-local-demo` | 90 | **52 秒**（`10:09:57.965993Z` → `[10:10:50]`；日志另显 `[10:10:36] Fabric is preparing JARs on first launch`） | `PLAYABLE` |
| 重复 warm `kin-demo-0928b` 新字节 | 90 | **约 17 秒**（`09:49:43.529925Z` → `[09:50:00]`） | `PLAYABLE` |

⇒ 30 秒窗足以跑通**热 store 的重复启动**，跑不通**冷装的干净启动**；把窗交给调用方（默认不变）就是这条路的最小正确修法。

## 两次真跑的 run 文档读数（逐字段，非退出码）

| 字段 | 干净启动 `322972450e114cc98f58f1a9d9bdc0c4` | 重复启动 `7ac542ce30c5440b92169a47816a4d78` |
| --- | --- | --- |
| `auto_bundle` | `installed 3639 / reused 0 / status ready` | `installed 0 / reused 3639 / status ready` |
| `bundle_id` / `protocol` / `fetch_set` | `1.20.1-linux-x86_64-offline-java21` / `763` / `3639` | 同左 |
| `launch_plan_digest` | `83299ad5e224959de8e30c72c5937a2434c4d7bba92c62f4d22cf8d89f5f6181` | 同左 |
| `connection_state` | `PLAYABLE` | `PLAYABLE` |
| `entities_admitted / rejected` | `11 / 0` | `14 / 0` |
| `snapshots_admitted` | `1` | `1` |
| `events_applied / ignored` | `5 / 0` | `5 / 0` |
| `actions_applied / refused` | `2 / 0` | `2 / 0` |
| `input_release_failed` | `false` | `false` |
| `session stop` 释放 | `{"asked": [2738], "released": [2738], "terminated": [2738]}`，`status: stopped` | `{"asked": [368], "released": [368], "terminated": [368]}`，`status: stopped` |
| `outcome` / `session_state` | `BRIDGE_LOST` / `STOPPED` | `BRIDGE_LOST` / `STOPPED` |
| 编排层 rc | `14` | `14` |
| 服务端观察 | `domain: the server saw the Kin walk and stop; its height moved through 0.00 blocks` | 同形状，另一世界 |

`BRIDGE_LOST` + rc=14 是这条入口的正常收尾：**harness 停掉了它自己起的客户端**，所以判别量取 run 文档（见 `test-orchestrator/runner/README.md`）。

## 测试侧对照（`tests/unit/test_auto_session.py`）

- 正对照：`--handshake-timeout-seconds 90` ⇒ **两个**入服入口都把手 `90.0` 交到 supervisor（`handed == [90.0, 90.0]`）。
- 负对照：不传该旋钮 ⇒ 两处都仍是 `DEFAULT_HANDSHAKE_TIMEOUT_S`，并断言 `DEFAULT_HANDSHAKE_TIMEOUT_S == 30.0`（默认窗口没被本卡挪走）。
- 反证：删掉 `bootstrap.py` 的传参 ⇒ 上面两个测试同时以 `KeyError` 变红（判据非恒真）。

## 门读数（`ci.yml` 自身列出的 Python 作业步骤，逐步骤退出码）

`uv sync --locked --dev` 0 / `ruff check .` 0 / `ruff format --check .` 0（390 files already formatted）/ `pytest` 0（**2778 passed, 2 skipped**，682.16 秒）/ `check_boundaries.py` 0 / `check_case_assertions.py` 0 / `verify_fixture_digests.py` 0 / `check_workflow_pins.py` 0 / `uv build --wheel` 0 / `check_wheel_boundary.py` 0 / `minekin --help` 0。`uv run pyright` 单独跑过：**0 errors**。

门载荷（`gate_payload_sha256`）本卡**未重取读数**：本卡改动文件面不含 case/registry/mandatory，且我在 `tools/` 与 `src/` 的当前字节里没找到产出该字段的读取路径（`grep -rn "gate_payload" tools/*.py src/` 回空）——取法与 #82 那笔判据变更的载荷读数一并补，不在此处引用旧值当本轮读数。

## 仍未支持的范围（具名，不求绿掩盖）

1. **本 Demo 不封存证据**：`MINEKIN_DEMO_CASE` 默认未设 ⇒ 不产 sealed bundle，这两次真跑是活体读数，不进 `mandatory`、不支撑任何 `tested` 晋级。
2. **`--gateway` 当时只在容器内起 Gateway**：`run.sh --shell` 那条 `docker run` 不发布端口，所以宿主浏览器打不开 Dashboard。⇒ 同日由 `V1201-DEMO-GATEWAY-BROWSABLE-001` 闭合：`MINEKIN_RUNNER_PUBLISH` 只接受单个端口号、绑定固定在 `127.0.0.1`，面板经 dev-server 的 `/gateway` 反代读取。活体读数见文末新增小节。
3. **Bridge 侧的拒连误判未修**：握手超时后 IPC 监听被关，Bridge 的 `connect()` 被拒，而 `reasonFor()` 只把 `IpcLost`/`SocketTimeoutException` 记成 `IPC_LOST`，其余归 `BRIDGE_FAULT`，且 `run()` 的 catch 从不打印异常本身。改 `bridge-1201` 会动 registry 钉住的 jar 摘要 ⇒ 全卷重封，属主控保留决策。
4. **Dashboard 仍只有只读面**：写操作（启动/停止/控制）不在现有契约授权内，未自行扩权。

## 复算式

```bash
cd C:/Users/darling/Documents/agent_work/minekin-wt-integration
sha256sum test-orchestrator/runner/demo.sh src/minekin_core/cli/parser.py \
  src/minekin_core/bootstrap.py tests/unit/test_auto_session.py

# 干净启动（新卷 + 新 Kin 根；冷装约 740 MB / 15–25 分钟）
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar bash test-orchestrator/runner/demo.sh
# 重复启动（同卷同 Kin 根，热 store）
MINEKIN_SERVER_JAR=.tmp/mc-1.20.1-server.jar MINEKIN_DEMO_VOLUME=minekin-local-demo \
  MINEKIN_DEMO_KIN=kin-local-demo bash test-orchestrator/runner/demo.sh --again

# 判据那一格（客户端日志对会话启动）
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
docker run --rm -v minekin-local-demo:/data:ro alpine sh -c \
  'd=$(ls -d /data/kin/kin-local-demo/run/session/*/generation-1); \
   grep -m1 started_at $d/process.json; grep -m1 "Setting user" $d/logs/latest.log'

# 定向测试
uv run pytest -q tests/unit/test_auto_session.py -k handshake
```

原始材料保留、未删：`.tmp/demo/clean-0928.out`（缺件的 rc=2 早退）、`.tmp/demo/clean-0928b.out`（旧字节 `HANDSHAKE_TIMEOUT` 失败材料）、`.tmp/demo/repeat-0928c.out`（新字节重复启动成功）、`.tmp/demo/clean-0928d.out`（新字节干净启动成功）。卷 `minekin-local-demo`、`minekin-m-demo-live2` 未清理。

## V1201-DEMO-GATEWAY-BROWSABLE-001 的活体读数（同日）

新增的业务能力：`demo.sh --gateway` 起的只读模型现在真能在宿主浏览器里读到这次 Demo 会话。

改动落在正式路径：`test-orchestrator/runner/run.sh`（`MINEKIN_RUNNER_PUBLISH` 端口发布）、
`test-orchestrator/runner/demo.sh`（`--gateway` 接线与回显）、`dashboard/vite.config.ts`
（dev-server 的 `/gateway` 反代）、`tests/contract/test_runner_scripts.py`（驱动 `run.sh` 的契约测试）。

真跑读数（卷 `minekin-local-demo`、Kin `kin-local-demo`）：

```text
docker ps            -> 127.0.0.1:8787->8787/tcp
GET  :8787/api/v1/dashboard/snapshot   200 3664 B
GET  :8787/api/v1/dashboard/timeline   200 11731 B  （40 行）
GET  :8787/api/v1/dashboard/alerts     200 254 B
GET  :5175/gateway/.../snapshot        200 3664 B   （与直连逐字段相等，仅 kinId/runtimeState 的
                                                      observedAt 因两次请求而不同）
GET  :5175/gateway/.../timeline        200 11731 B  （40 行 eventId 与直连全等）
POST :5175/gateway/.../{snapshot,timeline,alerts}   405 405 405
GET  :5175/gateway/api/v1/dashboard/nope            404
```

面板 `http://127.0.0.1:5175/?adapter=gateway&gateway=/gateway` 的可访问树读到的是这次会话本身，
不是 fixture：Kin ID `kin-local-demo`（`core://status/kin-local-demo/kin_id`，新鲜度「5 秒前」）、
runtime_state 空闲、Bridge/服务器链路「已失联·陈旧·1 小时前」、
会话 `d58a052b29054607be991d2cd2ee8399` · gen 1 · pid 378 · 覆盖层
`/data/kin/kin-local-demo/run/session/d58a052b…/generation-1`、世界上下文 profile
`p0-controlled-offline-loopback-1201`、页头 `kin-dashboard-readmodel/1.0.0`。
契约没实现的面一律是「未接入/不可用」并带原因（版本五件套要已封 bundle、相干性快照不落盘、
告警源属产品决定、无媒体中继），面板没有编造值的路径。

拒止（反照）：`MINEKIN_RUNNER_PUBLISH` 对 `0`、`878700000`、`5175:8787`、`0.0.0.0:8787`、
`127.0.0.1:8787:8787`、`8p` 六个形状各 rc=2 并指名该变量，且 `docker` 从未被调用（契约测试用 PATH
上的 `docker` 桩记录 argv，未置该名时 argv 里没有 `-p`）。

暴露口径：绑定写死 `127.0.0.1:<port>:<port>`，旋钮只能给一个端口号、结构上点不出网卡；
容器里的 `--host 0.0.0.0` 只是 Docker 转发的目标地址，宿主侧绑定才是暴露面。公网访问未扩大。

门禁：`uv run pytest -q` 2779 passed / 2 skipped（428 s）、`pyright` 0 errors、
`ruff check` 通过、`ruff format --check` 391 files already formatted、
`pnpm --dir dashboard typecheck` 0、`pnpm --dir dashboard test` 75 passed。
`uv run pytest tests/contract/test_runner_scripts.py -q` 128 passed。

仍未支持：写面（启动/停止/简单控制）不在冻结契约授权内，未自行扩权 ⇒ 单列决策卡
`V1201-DASHBOARD-WRITE-SURFACE-DECISION`；Live View、事件游标增量流、版本五件套读数仍按契约显示
「未接入」。收尾时 `docker stop` 了本次 Gateway 容器并结束 vite dev 进程，`8787/5175` 复归无监听。

复算：

```bash
cd C:/Users/darling/Documents/agent_work/minekin-wt-integration
MINEKIN_DEMO_VOLUME=minekin-local-demo MINEKIN_DEMO_KIN=kin-local-demo \
  bash test-orchestrator/runner/demo.sh --gateway        # 后台起
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' \
  http://127.0.0.1:8787/api/v1/dashboard/snapshot
pnpm --dir dashboard dev                                  # 另开一个终端
uv run pytest -q tests/contract/test_runner_scripts.py -k publish
```

## 同一条入口在 1 秒采样节奏下的第三次真跑（同日 20:08，`9884ef1f60f849409cd27da9d8b9461e`）

- **承载字节**：这次跑的是当前主干字节——`c168320`（`test-orchestrator/runner/domain.sh` 的 1 秒服务端探测节奏 + `tools/assert_case_evidence.py` 的授权窗归因）与 `6530427`（上一节的只读模型发布）都已在干上，不是历史脚本的复刻。
- **run 文档逐字段**（与上表「重复启动」那一列同形状）：`auto_bundle installed 0 / reused 3639 / status ready`、`connection_state PLAYABLE`、`entities_admitted 20 / rejected 0`、`snapshots_admitted 1`、`events_applied 5 / ignored 0`、`actions_applied 2 / refused 0`、`input_release_failed false`、`session stop` 释放 `{"asked": [276], "released": [276], "terminated": [276], "unconfirmed": []}`、`outcome BRIDGE_LOST` / `session_state STOPPED`、编排层 rc=14。
- **本卡的增量含义**：`domain: the server saw the Kin walk and stop` 那一格现在背后有可判的窗口归因——同一份服务端日志在 7.996514 秒的授权窗内给出 **8 枚**带戳位置读数、窗内水平位移 **32.6308 格**；反对照与逐字段读数见 `docs/v1201-lan-control-next-2026-09-27.md` §2.89。
- **原始材料**：`.tmp/r90-demo-again.log`、卷 `minekin-local-demo` 的 `/data/server-runs/run-3`（未清理、未封存，`MINEKIN_DEMO_CASE` 未设，故不产 sealed bundle）。
