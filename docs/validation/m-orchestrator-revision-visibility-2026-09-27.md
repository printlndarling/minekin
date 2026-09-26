# M 卡施工记录：编排脚本版本可见性缺口 —— 在报告面上具名（2026-09-27）

- 分支：`codex/minekin-orchestrator-revision-visibility`，base = 远端 `main` = `796316ad68724584178add0e34f8370dd22a5098`（`git ls-remote` 实读，与预期一致；worktree `minekin-wt-revvis`，merge-base 即该 SHA）。
- 改面：`tools/report_promotion.py`、`tests/unit/test_report_promotion.py`、本文件。不碰 schema、不碰 seal、不碰判据/registry/fixtures、不重封卷。

## 前提（全部来自本 worktree 字节实读，行号为 base 796316a 上的）

1. **打印文档的组装点**：`tools/report_promotion.py` 的 `_report_with_inventory()`（`:612-749`）组装并返回整个文档字典；顶层键 `"work_packages": packages` 在 `:717`、`"overall": overall` 在 `:718`、`"gated"` `:719`、`"status"` `:720`。`main()` 在 `:742-767`，打印行是 `:766` 的 `print(json.dumps(document, sort_keys=True))`；退出码由 `:767`（`EXIT_PROMOTABLE if document["status"] == "promotable"`）决定。
2. **门载荷摘要算在哪个子结构上**：对 stdout 文档里 `work_packages` 与 `overall` 两个顶层键的所选子集取 `sha256(json.dumps({"work_packages": …, "overall": …}, sort_keys=True))`。仓库代码内没有任何函数计算这枚摘要（全库 grep `fb0152c` / 对该子结构的 sha256 无命中）——它是校验记录里定下的读法，仓库内的执行证据行是 `docs/p0-repo-internal-image-reseal-2026-09-26.md:125`（"gate payload sha256（`work_packages`+`overall`，sort_keys）"，规范卷现值 `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`）与 `docs/p0-repo-four-case-run-2026-09-26.md:25,185`。因此：**新键只要与 `work_packages`/`overall` 平级、不嵌进二者内部，该摘要按构造不变**；本卡的载荷不变证明（见下）在合成数据上把这句话量了出来。
3. **不可见性本身（seal 侧证据）**：`tools/seal_run_evidence.py` 的 `orchestrator_trace()`（`:535-556`）在 `:550` 写死 `"orchestrator": "test-orchestrator/runner/domain.sh"` —— 一个路径字符串，没有任何版本或摘要字段。工件集合由 `collect_artifacts()`（`:195` 起）逐条按具名常量收（`"orchestrator-trace.json"` 在 `:215` 初始化，其后 `:219-258` 逐条判有），唯一的 glob 是 `:252-254` 的 `crash-reports`。bundle 里没有任何工件承载编排脚本的字节 ⇒「两次 run 用的是不是同一份 `test-orchestrator/runner/domain.sh`」按构造读不出来。
4. **为什么不改 seal schema**：往 `minekin.p0.evidence.v1` 加字段 = 重封整卷（卷上现 `attempts 71 / bundles 107`，其中 `from_another_build 61`）。那是用户/主控保留决策，本卡不做。本卡只把缺口在报告面上具名，让读者不再靠推断。

## 改面

`tools/report_promotion.py`：
- 新增常量 `ORCHESTRATOR_REVISION_GAP`（id `ORCHESTRATOR_REVISION_NOT_PINNED`，带 `artifact: orchestrator-trace.json`、`field: orchestrator`、陈述文本、`gates_promotion: False`）与 `VISIBILITY_GAPS` 清单。
- `_report_with_inventory()` 的返回字典在 `"overall"` 之后新增顶层键 `"visibility_gaps": [dict(gap) for gap in VISIBILITY_GAPS]` —— 与 `work_packages`/`overall` 平级。它不进入 `overall.blocks`、任何 work package 的 `blocks`/`blocking_cases`/`promotable` 判定、退出码，也不进入载荷子结构（红测试把这四条都钉住了）。

`tests/unit/test_report_promotion.py`：新增 `test_the_report_names_the_orchestrator_revision_visibility_gap`（红先行）+ 段落注释。

## 红 → 绿（原始输出）

红（实现前，`uv run --frozen pytest tests/unit/test_report_promotion.py -q`）：

```text
tmp_path = WindowsPath('D:/Temp/pytest-of-darling/pytest-2620/test_the_report_names_the_orch0')

    def test_the_report_names_the_orchestrator_revision_visibility_gap(tmp_path: Path) -> None:
        """The gap is a named sibling of `work_packages`/`overall`, not a blocker."""

        seal(tmp_path, RUN_ID, launch_plan_digest=plan_of("1.21.4"))

        document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

>       gaps = cast(list[dict[str, Any]], document["visibility_gaps"])
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'visibility_gaps'

tests\unit\test_report_promotion.py:1198: KeyError
=========================== short test summary info ===========================
FAILED tests/unit/test_report_promotion.py::test_the_report_names_the_orchestrator_revision_visibility_gap
1 failed, 54 passed in 40.62s
```

绿（实现后，同一命令）：

```text
.......................................................                  [100%]
55 passed in 47.62s
```

## 载荷不变证明（承重证明，真跑真记）

测量方式：`git show 796316a:tools/report_promotion.py` 导出为 `tools/_report_promotion_base.py`（base 字节，测后删除，**未进提交、未用 git checkout**）；对新旧两版各跑一次 CLI，对 stdout 的 `{"work_packages","overall"}` 子结构取 sha256。**数据 root 全部在系统 temp 下合成（`tempfile.mkdtemp(prefix="minekin-revvis-payload-")`，kin-01 证据根内 `write_bundle` 合成 bundle）；从未挂载、读取或写入 `minekin-runner-data`。**

| 读数 | 载荷 sha256 |
| --- | --- |
| base 代码，1 个 PASS bundle（不限定 gate） | `39ab4cdbde8e93c5644ede0ea4c41af95a25ae922c4a5be1dec37b90eef14ceb` |
| 新代码，同一数据 root（不限定 gate） | `39ab4cdbde8e93c5644ede0ea4c41af95a25ae922c4a5be1dec37b90eef14ceb` |
| base / 新代码，`--work-package W40` 两次 | 均 `39ab4cdbde8e93c5644ede0ea4c41af95a25ae922c4a5be1dec37b90eef14ceb` |
| **正对照**：同一 root 再补 1 个 FAIL bundle 后（base == 新代码） | `04f07e7ac3e62648fef42d23878f900dc1c9558dc5dafbb344f606ae02f5dce8` |

前两枚**逐字节相同**；正对照那枚与它们**不同**（且 base 与新代码在对照数据上仍彼此相同）——断言不是恒真。脚本尾部输出：`OK payload unchanged by the new key; a data change does move it`。新版 stdout 顶层含 `visibility_gaps`、base 版不含；`gates_promotion: false` 随条目本身进入文档。

**真实规范卷上的门载荷复量：本卡未做（Docker Desktop 未运行，任何挂卷测量均未尝试）；卷上现值 `fb0152c8…d178da` 未被本地复现，本记录不宣称与其相等。**

## 门禁复跑（全部本地，worktree）

| 门禁 | 结果 |
| --- | --- |
| `uv run --frozen pytest tests/unit/test_report_promotion.py -q` | `55 passed`（见上） |
| `uv run --frozen pytest -q`（全量） | `2538 passed, 3 skipped in 313.74s (0:05:13)` —— 主干基线 `796316a` 为 `2537 passed, 3 skipped`，+1 即本卡新测；两条 skip 为 `test_silent_listener.py:123`（Windows terminate 非信号）与 `test_tested_provenance.py:354`（本机未构建 bridge-1201 jar），与基线同 |
| `uv run --frozen ruff check .` | `All checks passed!` |
| `uv run --frozen ruff format --check .` | `346 files already formatted` |
| `uv run --frozen pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv run --frozen python tools/check_boundaries.py` | `Minekin package dependency boundaries: OK` |
| `uv run --frozen python tools/check_case_assertions.py` | `Case assertion implementations: OK (140 registered)` |
| `uv run --frozen python tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK` |
| `git diff --check` | 干净（无输出） |

## 四态声明

- 已合入 main：**否**（未合并、未碰 main）。
- 仅在分支：**是** —— 本卡交付态即 `codex/minekin-orchestrator-revision-visibility` 上的一个提交 + push。
- 真实封证：**无** —— 没有任何新测量挂真实卷/容器；本卡不产生也不改动封证。
- 尚未验证：真实规范卷上的载荷复量（需容器引擎，M 侧保留）；seal schema 加字段/重封（用户/主控保留决策，本卡未做亦不会做）。

## 没做到的部分

- 未在真实卷上复量 `fb0152c8…`：引擎不可用，且卡面明确禁止尝试挂载。
- 未给「重封后 bundle 直接钉住脚本字节」的出路做任何准备——那是保留决策，本卡只让不可见性可读。
- 门禁点亮：不宣称。本报告只说明各本地门禁在 worktree 内的实测输出。
