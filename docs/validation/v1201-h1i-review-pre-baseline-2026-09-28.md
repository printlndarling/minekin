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
