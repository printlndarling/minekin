# V1201-CONTROLLED-SERVER-STATUS-KNOB-001 — 受控服务器启动器把 status 变成可具名选择的开关（H lane）

日期：2026-09-27。执行 lane：H（test Harness）。
基线：`origin/main` @ `be4e79b98baafea85f1230de587fc5b7b8b15a89`（`git rev-parse origin/main` 实读一致）。
分支：`codex/minekin-controlled-server-status`，worktree `../minekin-wt-status`。
改动面：仅 `tools/run_controlled_server.py` 与其契约测试 `tests/contract/test_controlled_server_runner.py`。
未动：`test-orchestrator/**`（含 `domain.sh`）、产品 `src/**`、case fixture、registry、`mandatory`、
任何门禁、任何历史日期记录。规范卷 `minekin-runner-data` **全程未挂载**（连只读都没有）；
容器切片只用本 lane 自建卷 `minekin-h-status-20260927` 与 `/src` 只读挂载。
本卡不产生任何封存证据。

## 缺陷与红线复测（先量红）

`tools/run_controlled_server.py` 原来在第 247 行无条件写死 `"enable-status": "false"`：
调用方既没有具名要求 `true` 的入口，工具也不回读自己究竟写了什么。于是由本 harness
启动的服务器，其 status 通道按构造必然沉默 —— 任何需要服务器侧读数的验证会静默失去
该通道（G2 当时只能靠 `domain.sh` 的 `--probe-player` 默认化绕开）。

复现命令（受控镜像 `minekin-runner:local`，image id `b67a4d917306`；真起 1.21.4 JVM；
逐字驱动脚本 `.tmp/status-driver.sh`，原始记录 `.tmp/knob-red4.log`）：

```text
bash /src/.tmp/status-driver.sh red4-default
```

红读数（改动前的工具，`git show HEAD:tools/run_controlled_server.py` 原样放回施工位）：

- 写入的 settings 实录：`server.properties:14:enable-status=false`。
- 该服务器确实在跑：ready 后 3 秒裸 TCP `connect: accepted`。
- 产品自己的只读探针 `python -m minekin_core server probe --server-profile <loopback profile>`
  回 `"outcome": "NO_RESPONSE", "detail": "the endpoint closed before any frame"`，
  `received_bytes: 0`，rc=17。**probe-blind 由此从推断变成量到。**
- 改动前根本不存在该开关：`--enable-status` → `error: unrecognized arguments: --enable-status`，
  rc=2（`.tmp/knob-red2.log`）。

诚实记录一次测错：最早两轮（`.tmp/knob-red.log`、`.tmp/knob-red2.log`）探针也回 NO_RESPONSE，
但那是因为驱动脚本漏了 `--keep-running` —— 该工具本就在服务器报 ready 后立刻把它停掉
（`.tmp/knob-diag.log` 量到 `Controlled server: OK (ready, then stopped; ...)`），
那次测的是"没有服务器在听"（`connect: refused`），与 status 开关无关。该两轮不作为红读数，
仅保留为过程材料；`red4` 才是有效读数。另测一次确认驱动形状与 `domain.sh` 等价：
后台启动 + 默认 stdin + `--keep-running` 时服务器仍然活着（`.tmp/knob-diag-nofifo.log`
`connect: accepted`），所以不存在"后台任务 stdin 导致服务器自停"的额外 hazard。

## 改绿：默认不动，选择变具名

新增模块级具名默认 `DEFAULT_ENABLE_STATUS = False` 与命令行 `--enable-status`（`store_true`，
与 `--accept-eula`/`--resource-pack`/`--use-target` 同风格）。工具随后：

1. **报告它真正写了什么**：写完 settings 后打印
   `enable-status: asked for <true|false>, the settings written say <值>`；
2. **回读而非自证**：打印的值来自 `read_back_enable_status(directory)`，它从磁盘上的
   `server.properties` 取该行（取最后一行，与 `domain.sh` 的 `sed ... | tail -1` 同一读法），
   缺行/缺文件时报 `unreadable` —— 与 `domain.sh` 已有的那一个词对齐，不新造第三种说法；
3. **写之前具名拒止**：`status_switch_refusal(profile, online_mode=…, enable_status=…)` 在任何
   字节落盘前判定。它不发明新政策，只复用本文件自己声明的受控通道两条规则：
   `profile.is_loopback`（即 loader 那句 "P0 admits only a saved loopback profile … no LAN scan
   or DNS name"）与 `_online_mode_text(...)`（与写进文件的 `online-mode` 同一处推导）。
   只在 `--enable-status` 被要求时生效；默认路径一条判定都不多走。

容器内同一驱动脚本的改后读数（`.tmp/knob-green4.log`）：

- 不带开关（默认未动的对照）：`server.properties:14:enable-status=false`，
  工具打印 `asked for false, the settings written say false`，探针仍 `NO_RESPONSE` /
  `the endpoint closed before any frame` / rc=17 —— 与红读数逐字相同。
- 带 `--enable-status`：打印 `asked for true, the settings written say true`，
  `server.properties:14:enable-status=true`，探针回 `"outcome": "OBSERVED"`、
  `protocol: 769`、`version_text: "1.21.4"`、`received_bytes: 163`，**rc=0**。
  同一条命令、同一个镜像、同一个 profile，只差那个具名开关。
- 具名拒止（`--enable-status --online-mode`）：rc=2，stderr 具名
  `--enable-status asks the controlled server to answer a status ping, and this run forces the
  server to require session verification; …（AUTH_MODE_MISMATCH）…`，且
  `run directory exists? no` —— 什么都没写。
- 反证（`--online-mode` 单独给，不给 `--enable-status`）不触发该拒止：默认路径照旧。

## 契约测试与反向证明

新增 6 个测试于既有文件 `tests/contract/test_controlled_server_runner.py`；改后该文件
`uv run --frozen pytest -q tests/contract/test_controlled_server_runner.py` → **24 passed**
（原有 18 + 新 6），rc=0。

反向①：把缺陷在位的旧工具原样放回施工位
（`.tmp/run_controlled_server-before.py` = `git show HEAD:tools/run_controlled_server.py`），
新测试全部指名失败（`.tmp/knob-reversal-before.log`，`6 failed, 18 passed`，rc=1）：

| 测试 | 指名的断言行 |
| --- | --- |
| `test_the_reviewed_default_leaves_the_server_answering_no_status` | `assert RUNNER.DEFAULT_ENABLE_STATUS is False` → AttributeError |
| `test_an_opt_in_run_answers_status_and_changes_nothing_else` | `opened = RUNNER.properties_for(profile, level_seed="fixed-seed", enable_status=True)` → TypeError: unexpected keyword |
| `test_the_status_reading_reported_is_the_file_s_own_and_not_the_request` | `assert "asked for false" in reported` → 输出里只有 started 行 |
| `test_the_reader_names_an_absent_line_as_unreadable` | `assert RUNNER.read_back_enable_status(directory) == "unreadable"` → AttributeError |
| `test_opening_the_status_port_on_a_verifying_server_is_refused_before_writing` | `run_the_launcher(..., "--enable-status", "--online-mode")` → `SystemExit: 2`（argparse 不认该旗标） |
| `test_the_status_switch_is_gated_only_on_the_channel_it_would_widen` | `assert RUNNER.status_switch_refusal(loopback, …) is None` → AttributeError |

反向②（默认值非空转的关键证明）：只把 `DEFAULT_ENABLE_STATUS` 翻成 `True`（其余一字不动），
`.tmp/knob-reversal-flip.log` → `2 failed, 22 passed`，rc=1，指名行是

```text
>       assert RUNNER.DEFAULT_ENABLE_STATUS is False
E       assert True is False
>       assert {key for key in closed if closed[key] != opened[key]} == {"enable-status"}
E       AssertionError: assert set() == {'enable-status'}
```

即：翻默认会立刻被具名抓住，而 `false` 与 `true` 之间只差那一个具名开关这一事实也被
"两次调用恰好只差这一行"钉住（`test_an_opt_in_run_answers_status_and_changes_nothing_else`）。

回读路径的反向证明不依赖旧文件：测试把 `write_configuration` 换成一个故意写
`enable-status=true` 的替身、而请求是 `false`，断言工具打印
`asked for false` + `the settings written say true` —— 若打印取自自身变量则该断言必红。
另测缺行与缺文件各自回 `unreadable`，以及文件里出现两行时报最后一行（服务器实际读到的那行）。

## 门禁（本 worktree，`uv sync --locked --dev` 后全部 `uv run --frozen`）

| 门 | 命令 | rc |
| --- | --- | --- |
| lint | `uv run --frozen ruff check .` | 0（All checks passed!） |
| format | `uv run --frozen ruff format --check .` | 0（341 files already formatted） |
| 类型 | `uv run --frozen pyright` | 0（0 errors, 0 warnings, 0 informations） |
| 边界 | `uv run --frozen python tools/check_boundaries.py` | 0 |
| 判据 | `uv run --frozen python tools/check_case_assertions.py` | 0 |
| fixture 摘要 | `uv run --frozen python tools/verify_fixture_digests.py` | 0 |
| 工作流钉 | `uv run --frozen python tools/check_workflow_pins.py` | 0 |
| 空白 | `git diff --check` | 0 |
| 针对测试 | `uv run --frozen pytest -q tests/contract/test_controlled_server_runner.py` | 0（24 passed） |
| 全量 | `uv run --frozen pytest -q` | 0（**2534 passed, 3 skipped in 475.68s**） |
| 容器语法 | `bash -n`（本卡未改任何 shell 脚本） | — |

三个 skip 是主干上既有的平台跳过，与本卡无关、未新增：`tests/unit/test_orphans.py:686`
（本平台答不出那个问题）、`tests/unit/test_silent_listener.py:123`（Windows 的 terminate
不是信号）、`tests/unit/test_tested_provenance.py:354`（`bridge-1201` 的 Bridge jar 未在本机
构建）。全量跑是单独跑的：第一次与反向测量重叠（反向要把旧工具临时放回施工位），那次结果
作废未采信，重跑取上述读数。

## 停在何处（诚实边界）

- **具名开关可用，但 `domain.sh` 不传它**：按边界本卡不得改 `test-orchestrator/runner/**`。
  所以 auto 路径现在仍是红的，只是红得可诊断 —— `domain.sh` 读到 `enable-status=false`
  后具名早停（G1/G2 已合入的那段）。要让 auto run 真跑起来，需要另卡把
  `--enable-status` 接进 `domain.sh` 的服务器调用面（属 H 独占面，但不在本卡范围）。
- **不做任何 seal**：封证需规范卷与独占窗口，都不在本卡允许面。
- **不改默认**：`Rejected` 里具名记了翻默认这条路。
- 全程未连接、未探测任何远端服务器；未读取宿主 `.tmp/local-test-server.txt`；
  文中不出现任何外部地址。测试用的非 loopback 目标是仓库既有的匿名文档位 fixture
  `tests/fixtures/launcher/managed-remote-target-example.json`，且断言了拒止文本不回显该地址。
- 本卡未测：`--enable-status` 与 1.20.1 recipe 的组合（容器只真跑了默认 1.21.4 recipe）；
  `--enable-status` 与 `--resource-pack` 同时开启的容器读数（单元层已证明二者互不影响那三行）。

## 四态声明

status 具名开关与其读数/回读/具名拒止：**仅在分支**（`codex/minekin-controlled-server-status`，
未合入 main，等待主控双审）。红/绿读数与两组反向证明：**真实测量**（受控镜像、真 JVM、
本 lane 自建卷、逐字驱动脚本）。**真实封证：无** —— 本卡不产生任何 sealed evidence，
规范卷一次都没挂载。端到端 auto-bundle 真跑：**尚未验证**（还差 `domain.sh` 传该旗标的另卡）。
本记录不宣称 Minekin 完成，不宣称任何门禁点亮。
