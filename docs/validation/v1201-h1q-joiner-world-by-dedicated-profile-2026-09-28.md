# V1201-JOINER-WORLD-BY-DEDICATED-PROFILE-001（#65 H1q）交付记录

分支 `codex/minekin-h1q-joiner-world-dedicated-profile`，起点 `354f34e`（= 该卡派工时的远端 `main`）。
本卡实施主控 §2.59 的裁决：专服形状下把加入者侧封存的世界块交成 `--server-profile` +
`--server-directory` 两件、并弃掉那次注定被 `tools/seal_run_evidence.py:434` 拒掉的
`--world-run-document` 递件；关闭态与起点逐字节等价；新增「两者同时在场 ⇒ `exit 2`」的具名拒止。

## 0. 现场读数（接手时现读，落盘前）

- `git rev-parse --short HEAD` = `354f34e`
- `git status --porcelain | wc -l` = `0`
- `sha256sum test-orchestrator/runner/domain.sh` = `16124b5bf3a18b2985d14ca27bf2514d3f630fe4db60827abb4b274e35988401`（3252 行，LF；`.gitattributes` 对 `test-orchestrator/runner/*.sh` 强制 `eol=lf`，故工作树摘要 = git blob 摘要 = 卡面值）
- 起点两份待改文件的 `sha256` 已备份到 `.tmp/h1q/backup-origin354f34e/`（`domain.sh` = `16124b5b…`；`test_runner_scripts.py` 工作树 = `8f3a08fc…`，对应 git blob = `136696c4…`，差在 `.py` 受 `* text=auto` 归一，提交后为 LF）。

## 1. 缺陷与裁决出处

- **缺陷（加入者侧封存支在专服形状下按构造封不出 bundle）**：
  - `domain.sh:3074` 无条件把 `--world-run-document /tmp/domain-session.json` 递出去。H1k 形状的服务端由 `domain.sh` 直接起、核心从不播种（`src/minekin_core/cli/session.py:644–:657`），宿主文档 `run.world_snapshot` 恒空 ⇒ `tools/seal_run_evidence.py:426–:434` 在 `:434` 抛 `Unsealable("the run that hosted this world did not record a world of its own")`。
  - 只补 `--server-directory`（H1i 第①格现状）：路线 3 需 `target`（profile）非空才走 `kind: dedicated`；只交目录时 `kind: none` 与目录算出的名字不成一侧，撞 `src/minekin_core/domain/evidence.py:189–:193` 的 `WORLD_RECORD_INCONSISTENT`（`bundle.py:113` 抛出）。
- **裁决出处**：卡面 `.tmp/h1q/brief.md` §1/§3/§7 引用主干文档 §2.59（M 于第六十七轮 `23fa81c` 自行裁决采纳「按形状分裂」）。**本卡分支基线 `354f34e` 早于 `23fa81c`，故 §2.59 不在本树文档里**（该文件在本树止于 §2.58）；实质技术判定在已存在的 §2.54（`:977` 起）。执行体已 `git -c credential.helper= -c credential.helper=wincred fetch origin main`（只动 ref、不动工作树）取 `23fa81c` 只读核对 §2.59 全文与其「今日字节锚点」，逐处与本树 `354f34e` 字节对照后实施。`354f34e..23fa81c` 仅差两笔文档笔、`domain.sh`/`tests/contract/` 零改动 ⇒ §2.59 的锚点对本树成立。
- **裁决要动的两处（同一具名区域内）**：加入者封存支 `:3074` 的无条件递件条件化、与 `:3091–:3094` 的 `world_args`；契约只按名提取 `joiner-server-log-seal-forge` 区域 ⇒ 两处落在同一区域内，「两格同时在场即拒」在契约面上才读得到。LAN 形状（`--server-profile` 缺席）不改；`--server-jar` 仍不交（`:3034–:3041` 宿主支是对照，未动）；三枚既有拒止 `:547`（`case_on`）/ `:552`（profile 缺席）/ `:556`（black hole）保留原句。

## 2. 最终 SHA 与提交列表（按路径配对的字节）

- 起点：`354f34e`
- commit #1（契约先红）：`00e89cf` —— 只改 `tests/contract/test_runner_scripts.py`，`domain.sh` 保持 `16124b5b…`。
- commit #2（GREEN 交付字节）：`68a748a` —— 改 `test-orchestrator/runner/domain.sh`（+46/−22）与契约里首次落盘扫描的锚点（把散文式 `/tmp/domain-seal.err` 收窄为重定向写 `>/tmp/domain-seal.err`；这一格只在 `domain.sh` 转绿后才走到，属绿阶段实现细节，非新增红格）。**交付代码字节 = `68a748a`**。
- commit #3（本记录笔）：`docs/validation/v1201-h1q-joiner-world-by-dedicated-profile-2026-09-28.md` 落盘之上的独立文档笔（记录不含自身 SHA）。

## 3. 门表（`.tmp/h1q/run-gates.sh` 步骤取自 `.github/workflows/ci.yml`，逐道读 rc、先落盘再抄末行）

PRE = `.tmp/h1q/gates-pre/summary.log`；POST = `.tmp/h1q/gates-post/summary.log`。每道的完整输出落在同名 `<name>.log`。

| 道（log 文件名） | PRE rc | PRE 末行 | POST rc | POST 末行 |
| --- | --- | --- | --- | --- |
| `bash-n-domain.log` | 0 | （空） | 0 | （空） |
| `bash-n-run.log` | 0 | （空） | 0 | （空） |
| `contract.log` | 0 | `119 passed in 17.50s` | 0 | `123 passed in 13.87s` |
| `uv-sync.log` | 0 | `Checked 18 packages` | 0 | `Checked 18 packages` |
| `ruff-check.log` | 0 | `All checks passed!` | 0 | `All checks passed!` |
| `ruff-format.log` | 0 | `373 files already formatted` | 0 | `373 files already formatted` |
| `pyright.log` | 0 | `0 errors, 0 warnings, 0 informations` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest-full.log` | 0 | `2706 passed, 3 skipped` | 0 | `2710 passed, 3 skipped` |
| `boundaries.log` | 0 | `boundaries: OK` | 0 | `boundaries: OK` |
| `case-assertions.log` | 0 | `OK (151 registered)` | 0 | `OK (151 registered)` |
| `fixture-digests.log` | 0 | `W00 schema and fixture digests: OK` | 0 | `W00 schema and fixture digests: OK` |
| `workflow-pins.log` | 0 | `Workflow pins: OK` | 0 | `Workflow pins: OK` |
| `wheel.log` | 0 | `Successfully built …whl` | 0 | `Successfully built …whl` |
| `wheel-boundary.log` | 0 | `Wheel oracle boundary: OK` | 0 | `Wheel oracle boundary: OK` |
| `cli-help.log` | 0 | `-h, --help …` | 0 | `-h, --help …` |
| `diff-check.log` | 0 | （空） | 0 | （空） |

起点读数与主干一致：契约全绿、`OK (151 registered)`、`ruff format --check` 373 files、全量可比量 `passed + skipped = 2709`。
POST 全量 `2710 passed, 3 skipped` ⇒ 可比量 `2713 = 2709 + 4`，**+4 恰是本卡新增的契约案净数**（替换旧 1 枚、新增 5 枚）。
PRE 全量 `2706 passed / 3 skipped` 与主干 `2707 passed / 2 skipped` 的 passed/skipped 各差一格，是 `test_tested_provenance.py:354` 的桥产物条件 skip（本机无 1.20.1 桥产物），可比总量 2709 相同——与主干 §2.58 门表口径一致。
`ruff format --check` 在 gates-post 跑时本记录尚未落盘（373 files）；本记录 md 落盘后 `ruff` 计入 **374 files**（§2.56/§2.58 既有口径：ruff 0.16.8 把 md 计入文件数，记录本身即那一格增量），落盘后单跑 `ruff check` 与 `ruff format --check` 见 §5。

## 4. 谓词 / 断言形状复现（`tests/contract/test_runner_scripts.py`）

沿用本族既有写法：区域按名提取（`handover_region`）、区域字节经 `run_shelled` 真过 bash 驱动、临时文件落 `tmp_path`。

- **(1) 关闭态等值** `test_the_joiner_forge_close_state_is_byte_equal_to_the_starting_handoff`：从真文件提取 `joiner-server-log-seal-forge`，`asked=0` 驱动，`seal_two_arrays` 读回 `world_args == []`、`world_run_args == ["--world-run-document", "/tmp/domain-session.json"]`。起点旧区域不赋 `world_run_args`（那行在 `:3074` 区域外）⇒ `set -u` 下读回未定义即报错 ⇒ 先红。
- **(2) 打开态形状** `test_the_joiner_forge_open_state_hands_profile_and_directory_and_no_jar`：`asked=1` 驱动，`world_args == ["--server-profile", …, "--server-directory", …]` 恰两件、`world_run_args == []`、且 `--server-jar` 不在区域里。
- **(3) 冲突拒止在场 + 删桩变异转红 + 早于落盘** `test_the_joiner_forge_refuses_world_document_and_profile_together`：先断言区域里同时出现 `--world-run-document` 与 `--server-profile`（守卫在场）；把「弃件行」删掉得到「两格同时在场」的禁区形状 ⇒ 驱动 `exit 2` 且 stderr 具名两件；再把守卫的 `exit 2` 删掉（变异，落 `tmp_path`、随 `tmp_path` 自清）⇒ rc 落回非 2，证明拒止非恒真。行号/字节偏移证明：守卫 `exit 2` 在区域 begin/end 之间，区域 end 早于首次落盘三点（`: > /tmp/domain-seal.json`、`>/tmp/domain-seal.err`、`python /src/tools/seal_run_evidence.py`）。扫描锚定重定向写形，避免命中区域注释里的散文名。
- **(4) 真文件成对断言** `test_the_joiner_only_directory_world_shape_is_named_and_the_shipped_file_has_none`：谓词 `_numbered_matches` 用纯子串 `world_args=(--server-directory "`（无反斜杠+字母，无转义陷阱）。缺陷样本（旧「只交目录」区域）落 `tmp_path` ⇒ 命中具名行号（`[3]`，正对照，判据不空转）；修好的真文件 ⇒ 命中 0（打开态改以 `--server-profile` 打头，多行式 `--server-directory` 不再带 `world_args=(` 前缀）。两侧都跑。
- **(5) 注释与字节不相反** `test_the_joiner_server_log_knob_comment_no_longer_claims_only_the_directory`：断言区域打开态含 `--server-profile`（交两件）且全文件不再出现 `Only the directory`（钉住 §1 注释改写）。

### 最终谓词区域字节（`test-orchestrator/runner/domain.sh`，`joiner-server-log-seal-forge`）

```bash
world_run_args=(--world-run-document /tmp/domain-session.json)
world_args=()
if [ "${seal_joiner_server_log_asked}" -eq 1 ]; then
    world_args=(--server-profile "${server_profile}"
        --server-directory "${server_directory}")
    world_run_args=()
fi
has_world_document=0
has_server_profile=0
case " ${world_run_args[*]} " in *" --world-run-document "*) has_world_document=1 ;; esac
case " ${world_args[*]} " in *" --server-profile "*) has_server_profile=1 ;; esac
if [ "${has_world_document}" -eq 1 ] && [ "${has_server_profile}" -eq 1 ]; then
    printf 'domain: the joining run'"'"'s seal was handed both --world-run-document and --server-profile; ...refused here, before the sealer runs and writes anything\n' >&2
    exit 2
fi
```

（完整带注释的区域见 `git show 68a748a -- test-orchestrator/runner/domain.sh`；旋钮注释 `:206–:216` 亦同步改写。）

## 5. 门载荷 PRE/POST 配对（`.tmp/h1q/trunk_digest.py` 对 `{work_packages, overall}` 子集取 sha256）

| | 文件 | report_promotion rc | json 字节 | gate_payload_sha256 |
| --- | --- | --- | --- | --- |
| PRE | `.tmp/h1q/gate-payload-pre.json`（err：`.tmp/h1q/gate-payload-pre.err`） | 1（按构造 blocked） | 103,921 | `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` |
| POST | `.tmp/h1q/gate-payload-post.json`（err：`.tmp/h1q/gate-payload-post.err`） | 1（按构造 blocked） | 103,921 | `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` |

两份 json 逐字节相同（`cmp -s` = IDENTICAL，文件 sha256 同为 `b09cc196…cb41`）。基线 `cfa0f118…63afd6` 未移——本卡不注册案、不动判据 ⇒ PRE==POST 同值。`report_promotion` 的 `rc=1` 属按构造 blocked（无 mandatory 可晋级），非失败。两次均以规范卷 `minekin-runner-data:/data:ro` 只读运行，零 JVM、零容器写入。

落盘本记录后（记录 md 使 ruff 文件数 +1），单跑确认：`uv run --frozen --offline ruff check .` = `All checks passed!`；`uv run --frozen --offline ruff format --check .` = `374 files already formatted`（373 + 本记录，见 §3 末注）。

## 6. 活体一读（回退条件判别格）

**结论：未量到（环境不具备 1.20.1 受控专服活体资产）。**

- 本卡要跑的形状 = 「专服形状 + `case_on=joiner` + 旋钮开」的真 `domain.sh session`，经 `run.sh domain` 在 runner 容器里起一台 1.20.1 受控专服、放两个客户端真加入、真封出 bundle，并打印 `manifest` 的 `world_kind / seed_or_snapshot_id / server_config_digest` 与 `violations()`，回答「1.20.1 受控专服 run 目录 `level-seed` 落定后 `name` 是 `minekin-…` 还是 `unrecorded`」。
- 现读证据（`docker` 可用，引擎 `linux/amd64`、Server 29.5.3，镜像 `minekin-runner:local` 在，规范卷 `minekin-runner-data` 在）：
  - 镜像内 `/opt` 仅 `{java, minekin, sqlite}`；`find / -iname '*.jar' | grep -iE 'bridge|client|fabric|quilt|1\.20'` 为空；无 `/server` 预挂载；无 1.20.x 资产。
  - 宿主仅有 `../server-26.3.jar`（版本 26.3，非 joiner 案 `v1201-lan-joiner-control-case-001` 所钉 `controlled-offline-server-1.20.1` 那一版）。桥（`bridge/`）是未构建源码，需 gradle + 联网取 Mojang 依赖（主干 §2.46 已量「集成树没有 1.20.1 桥产物」）。
  - 与本环境自洽的旁证：PRE 全量 `2706 passed / 3 skipped` 比主干多出的那一格 skip，正是 `test_tested_provenance.py:354` 的 1.20.1 桥产物条件 skip ⇒ 本机确实无桥产物。
- 因此**无法真跑该活体、无法真封 bundle**。按卡面 §7「引擎/卷不可用不是失败，如实写未量到，不要用私有卷 dev-seal 产物冒充 sealed bundle」，本格记「未量到」，且**未挂载规范卷做活体**（规范卷只用于 §5 的只读 `report_promotion`）。
- **回退条件未被触发**：回退（§2.59 ②(b) 被证否 ⇒ 停手）要求「量到『只交目录』在某形状下能干净封出 bundle」。本环境**未量到任何 bundle**，不构成对 (b) 的证否，故不停手、不改口径；(b) 的经验判定仍按 M 的量测（`ce_ab2/50-switch-off.err` 命中 `WORLD_RECORD_INCONSISTENT`）成立，交付记录如实标注「本卡未复量该经验格」。
- **无失败材料被改名保留**：活体未跑起，无 `-FE<n>` 产物；本卡也无其它跑挂材料需保留（各门与契约在交付字节上全绿）。

## 7. 纪律核对

未连用户远程服、未读 `.tmp/local-test-server.txt`、committed 文档不含 IP:port；未放宽认证/地址/lease/判据；未删旧材料与失败材料；改动前对两份文件备份并记 `sha256`（§0），全程未对脏文件用 `git checkout --`/`git restore`/`git reset --hard`/`git stash`；未 `--amend`、未 `--no-verify`；纯子串判据不含「反斜杠+字母」（§4 第 4 格），故无转义陷阱；只 push 本分支、不合主干。
