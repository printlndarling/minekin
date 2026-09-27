# H1i 独立复审的 PRE 基线（主干字节 `b35bc37`，2026-09-28 00:36 +0800，M 主控）

**为什么单独留这一份**：H1i（卡 #52）交付后，M 要按真实 merge-base 独立复审。复审的判别量是「门载荷是否仍为同一值」与「加入者侧封存命令面是否逐字节不变」，两者都必须有一枚**在 lane 字节之前**的读数才谈得上「不变」。本文件就是那枚 PRE。全程只读仓库字节 + 规范卷 `:ro` 挂载，零 JVM、零活体客户端。

## 一、字节与挂载

- 树：`C:/Users/darling/Documents/agent_work/minekin-wt-integration`，`HEAD = b35bc370982f222d0774bc1a8568c7671b63f61d`（远端 `refs/heads/main` 同值）。
- `sha256sum`（工作树字节）：`test-orchestrator/runner/domain.sh = e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954`、`tools/seal_run_evidence.py = 4970381c72ea4816b1ab59bf0c058576ed94e156e32c09878fe20d32b8f34242`、`tools/assert_case_evidence.py = d89bf64b11a47f6144862ff1ff5dd2ea90c41633dd4c151a213e4b4995f664f0`。
- 门载荷读数用 `-v minekin-runner-data:/data:ro`（只读），`PYTHONPATH=/src/src`、`LD_LIBRARY_PATH=/opt/sqlite/lib`。

## 二、逐条门读数（每步单独跑、先取退出码）

| 门 | rc | 末行 |
| --- | --- | --- |
| `bash -n domain.sh` | 0 | — |
| `bash -n run.sh` | 0 | — |
| `pytest tests/contract/test_runner_scripts.py -q` | 0 | 94 passed in 18.81s |
| `check_case_assertions.py` | 0 | OK (150 registered) |
| `check_boundaries.py` | 0 | boundaries: OK |
| `verify_fixture_digests.py` | 0 | W00 schema and fixture digests: OK |
| `ruff check .` | 0 | All checks passed! |
| `ruff format --check .` | 0 | 369 files already formatted |
| `pyright` | 0 | 0 errors, 0 warnings, 0 informations |
| 容器内 `report_promotion.py --data-root /data` | 1（预期非零：`blocking_cases` 在位） | 见下行摘要 |

`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`（第五次同值；载荷体积 103921 字节）。

复算式：`cd /c/Users/darling/Documents/agent_work/minekin-wt-integration && bash .tmp/m-r57-h1i-pre-gates.sh; cat .tmp/m-r57-h1i-pre-gates.log`

## 三、H1i 两格今日的「不变量」侧证据（即 lane 必须打破、又必须只在默认关闭时不破的东西）

- `grep -n "world_args=()" test-orchestrator/runner/domain.sh` ⇒ 两处：`:2869`（专服形状分支的初始化）、`:2934`（加入者侧**故意清空**）。第①格只允许在加入者那一支按旋钮交回 `--server-directory`，`--server-profile`/`--server-jar` 仍不得出现。
- `grep -c "probed-player" test-orchestrator/runner/domain.sh` ⇒ **0**（该文件里根本没有这个名字；`tools/seal_run_evidence.py:929` 收参数、`tools/assert_case_evidence.py:712/:1051` 读回，承担者早已在 tools 侧等着）。⇒ 第②格判据 (b)「不设旋钮 ⇒ 名字不出现在 bundle」今天在**任何形状**下都成立，因为无人递它；这一格的正对照只能来自 lane 的改后字节。

## 四、CI 与远端

`b35bc37` 的 CI 运行号 911 = `completed success`；906–910 亦全 success（`fbfd9d0`/`dff4550`/`012f56b`/`edfd8c5`/`0ce94f1`）。**真实封证仍为 0**：本节只是复审基线，不构成任何 case 的 sealed bundle，也不改 registry/mandatory。

## 五、补测：把 H1i 反证 (a)(b) 的 tools 侧一半先量掉（同轮 00:46 +0800，M 主控，零容器、零 JVM）

**为什么补这一格**：§2.50 要求 lane 交四枚反证，其中 (a)「开旋钮 ⇒ 加入者 bundle 多出 `server/server.log` 且含按名答题行」与 (b)「不设旋钮 ⇒ 该 artifact 不出现」同时依赖 runner 与 sealer 两侧。sealer 侧今天就能单独量；量完 ⇒ 复审时**不必取信于 lane**：改后若仍不出 artifact，责任只在 `domain.sh` 有没有把目录递过去。

**形状**：直接调 `tools/seal_run_evidence.py:194 collect_artifacts`，输入 = V5′ `armed` 式落盘的私有材料目录，其余入参按「这次 run 没有」给空（`overlay=None`、`run_document=b"{}"`、`fault_injection=b""`、`soak_samples/soak_summary=b""`、`orchestrator={}`）。脚本与读数各留一份：`.tmp/m-r58-carrier-control.py` → `.tmp/m-r58-carrier-control.log`（复算式即 `PYTHONPATH=src:. .venv/Scripts/python.exe .tmp/m-r58-carrier-control.py`）。

| 调用 | 收到的 artifact 名 |
| --- | --- |
| `server_directory=<armed 目录>` | `orchestrator-trace.json`、`run-document.json`、**`server/server.log`**、**`server/server.properties`** |
| `server_directory=None`（= 今日加入者侧的实际形状） | 只有 `orchestrator-trace.json`、`run-document.json` |

差集逐字 = `['server/server.log', 'server/server.properties']`。被封进去的 `server.log` = 27,569 字节，按名答题行随之读得出：`Kin has the following entity data` **84** 行、`Kin2 has the following entity data` **82** 行。这与 §2.52 表里的「三元组 83（`Kin` 42 / `Kin2` 41）」**不矛盾**，本轮当场拆开量清：一次探测打**两**行——位置行是三元组、朝向行是二元组，故 `Kin` = 42+42 = 84、`Kin2` = 41+41 = 82，全文 `has the following entity data` 共 **166** 行。⇒ 顺带把 §2.52 那句「朝向那格今天没有任何检查读它」钉实：`probe_readings(..., 3)` 只收三元组，166 行里 83 行位置被读、83 行朝向被丢弃。`server/usercache.json` **未**出现不是缺陷，而是 `:180–:192 _artifact` 的「在才收」口径（那份私有目录里本来就没有该文件）；复审 (a) 时按同一条读，不得要求它必在。

⇒ 钉两条结论：① **H1i 第①格只需要 `--server-directory`**——给了目录就多出两件服务端 artifact、按名答题行随之可读，不给则该格恒假。本枚测量**没有**放宽「只交目录、不带回 `--server-profile`/`--server-jar`」的口径。② 反证 (b) 的负对照在 tools 侧**天然成立**（`server_directory=None` 时键集就只有两个），所以 (b) 的全部判别力都落在 runner 侧：默认关闭时 `domain.sh` 必须仍然把 `world_args` 清空。

**一次真实失败（不掩饰）**：第一次用 `importlib` 装载该模块时抛 `AttributeError: 'NoneType' object has no attribute '__dict__'`，起因是 `@dataclass(frozen=True, slots=True)` 要从 `sys.modules` 取回自身模块，而 `exec_module` 之前未注册 ⇒ 脚本里 `sys.modules["sealer"] = module` 是必需行，已在文件内注明并复跑通过。
