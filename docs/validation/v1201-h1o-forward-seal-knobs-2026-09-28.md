# H1o `V1201-FORWARD-SEAL-KNOBS-001` — `run.sh` 转发两枚封存交接旋钮：读数与反证

日期：2026-09-28。基线：`b9b0d25bba9a9d9bb6e50d5666b53d2fa52bd6f8`（= 主干 H1i 复审合入后）。
分支：`codex/minekin-h1o-forward-seal-knobs`。工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-h1o`。
规范卷 `minekin-runner-data` 全程只出现在门载荷复算一条 `-v ...:/data:ro` **只读**挂载里，未建 attempt、
未建 bundle、未封存任何证据；活体一律走本 lane 私有卷 `minekin-h1o-live`。本文档无任何 IP:port，
未连接任何外部或用户的远程服务器。

## 0. 开工三检（动手前实测）

```text
git rev-parse HEAD                                = b9b0d25bba9a9d9bb6e50d5666b53d2fa52bd6f8   ✓
sha256sum test-orchestrator/runner/run.sh         = 323f521a3141fa3c613d02b93500612aa1ec943a2467a4da1d4a5080f1669126 ✓
sha256sum tests/contract/test_runner_scripts.py   = daecfa01a5827534fd6db6eb8c70e3a09659804748cbfe88dfd2b9f4af7da471 ✓
```

`grep -c "MINEKIN_DOMAIN_SEAL" test-orchestrator/runner/run.sh` = **0**（缺口登记与卡面一致）。

## 1. 改了什么（允许面核对）

`git diff --stat b9b0d25`：全仓只有 `test-orchestrator/runner/run.sh` **+15/−1**、
`tests/contract/test_runner_scripts.py` **+30/−29**，加上本记录。
`domain.sh` 盘上字节 = `git show HEAD:...` 的同一 sha256
（`df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2`，**0 行改动**）；
`tools/**`、`src/**`（含 `config.FORWARDED_VARIABLES`）、fixtures、registry、schemas、`.github/**` 全部 0 行。

- `run.sh`：`domain` 分支 `EXTRA_ARGS` 名单末尾（原闭合括号所在行拆开重闭）加入
  `-e MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG` 与 `-e MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS`，
  写法与 H1j/H1l/H1m 的既有条目逐字同形——**裸 `-e NAME`**：宿主设了 docker 才把值带进容器，
  宿主没设则该名在容器里保持 unset。未铸任何默认值，未触碰命令行构造。注释按既有口径写明三件事：
  wrapper 参与止于这条 pass-through（取值校验与三枚/两枚具名拒止都在 `domain.sh`）；不转发 ⇒ 名字
  到容器为空 ⇒ 「not asked for」支 ⇒ run 完成、封存、却是另一个形状的证据（H1j/H1l 闭过的同一缺陷）；
  默认关闭面不因转发而移动（未设 ⇒ 加入者侧封存命令与主干逐字节相等）。
- 契约 `test_every_knob_the_harness_reads_is_one_the_wrapper_hands_it`：把 H1i 登记的精确缺口
  **转成已交付形状**（删登记、不删断言，与 H1j/H1l 对 joiner-control 的翻转同格同法）：
  - `SEAL_HANDOVER_KNOBS` 常量本体两名保留，注释由现在式缺口登记改写为过去式闭合记录；
  - 每名仍逐一断言 `in read`（domain.sh 不再读它 ⇒ 红）；
  - **新增**每名逐一断言 `in delivered`（缺席即红，消息点名那枚被停发的名字并写明
    「arrives empty ⇒ 'not asked for' ⇒ 封的是另一个形状」失败模式）；
  - `assert read - delivered == SEAL_HANDOVER_KNOBS` 改为 `assert read - delivered == set()`
    （第三个 read-未-delivered 名即红）；`assert delivered - read == set()` 原样保留；
  - `:211` 族的产品外溢断言原样保留（两枚名不得出现在 `src/minekin_core/config.py`）；
  - 测试 docstring 末段补一句本笔闭合的过去式记录，全文不再有任何现在式声称「未转发」。

字节表（盘上 sha256；`*.py` 本检出 `core.autocrlf=true`，库内 blob 摘要以 `git show <sha>:<path> | sha256sum` 为准）：

| 文件 | 改前（= 基线） | 改后（交付字节） |
| --- | --- | --- |
| `test-orchestrator/runner/run.sh` | `323f521a3141fa3c613d02b93500612aa1ec943a2467a4da1d4a5080f1669126` | `93642dd3005ecdb745d780ca85937ff53da614374fa6a757584840273e54734f`（207 行） |
| `tests/contract/test_runner_scripts.py` | `daecfa01a5827534fd6db6eb8c70e3a09659804748cbfe88dfd2b9f4af7da471`（盘上） | `2d3503913cedae0c5d7615a67a3bdd90df2805f27bbf82651f6724cf6d2b8543`（盘上） |
| `test-orchestrator/runner/domain.sh` | `df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2` | 同一值（0 行） |

## 2. CE-a 正对照：交付字节下契约绿

```text
uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q --tb=line
rc=0    118 passed in 17.45s
```

（主干基线 118；本笔只翻转/新增断言于既有测试函数体内，未增删测试函数 ⇒ 数字不变。）
材料：`.tmp/h1o/ce-a-contract-green.log`。

## 3. CE-b 非恒真：摘掉一行 `-e` 必须红、装回必须绿

种桩前 `cp test-orchestrator/runner/run.sh .tmp/h1o/run.sh.delivery`（sha256 `93642dd3…` = 交付字节）。
全程无 `git checkout --`/`restore`/`reset`/`stash`；复原用 `cp` 回拷并以 sha256 核对。

1. `sed -i '/-e MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG$/d'` 删掉其中一行 ⇒ `grep -c` 该名字 = 0；
   变异体上 `bash -n` 仍 rc=0（红的是语义不是语法）。契约：

```text
uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q --tb=line
rc=1    1 failed, 117 passed in 16.67s
E   AssertionError: domain.sh arms the seal handover on MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG and run.sh stopped delivering it: the name arrives empty, domain.sh takes its 'not asked for' branch, the run completes and seals — evidence for a different shape than the one the operator asked for
tests/contract/test_runner_scripts.py:192: AssertionError
```

   红消息逐字点名被摘的那枚名字。材料：`.tmp/h1o/ce-b-mutant-red.log`。
2. `cp .tmp/h1o/run.sh.delivery` 复原 ⇒ 复原前后各量一次：

```text
before: 93642dd3005ecdb745d780ca85937ff53da614374fa6a757584840273e54734f  (sha256sum, 删行前)
after:  93642dd3005ecdb745d780ca85937ff53da614374fa6a757584840273e54734f  (sha256sum, 复原后)  IDENTICAL
契约复跑 rc=0    118 passed in 19.33s
```

   材料：`.tmp/h1o/ce-b-before-restore-sha.txt`、`.tmp/h1o/ce-b-after-restore-sha.txt`、
   `.tmp/h1o/ce-b-restored-green.log`。这次改动只发生在本工作树，且已复原。

## 4. CE-c 活体：值确实跨过 docker 边界（一发正例 + 负对照）

镜像 `minekin-runner:local`（docker server 29.5.3，`docker ps` 起 run 前空列表核验）。
`MINEKIN_RUNNER_DATA=minekin-h1o-live`（本 lane 新建私有卷；规范卷不出现在这两条命令里）。
两发都在**任何落盘之前**被具名拒止回答（选择与封存旋钮无关的第二具名拒止把负对照也钉在写盘前；
正例则要求封存句**抢先**回答，以证明值已到）。

- **正例（带坏值）**：

```text
MINEKIN_RUNNER_DATA=minekin-h1o-live MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=maybe \
  MINEKIN_DOMAIN_PROBE=kin-h1odup MINEKIN_DOMAIN_PROBE_SECOND=kin-h1odup \
  bash test-orchestrator/runner/run.sh domain session start --profile /src/tests/fixtures/launcher/1.20.1.json
rc=2
domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG must be 1/true or 0/false, got maybe
```

  该句只可能由容器内 `domain.sh:219` 的取值 case 打印，且它压过了同命令里更晚的
  `MINEKIN_DOMAIN_PROBE_SECOND` 重复名守卫（`domain.sh:877`）⇒ 值真的经 `run.sh` 的
  `-e MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG` 跨过了 `docker run` 边界。
  材料：`.tmp/h1o/live-positive.err` / `live-positive-out.txt`。
- **负对照（同形状、不设旋钮）**：

```text
MINEKIN_RUNNER_DATA=minekin-h1o-live MINEKIN_DOMAIN_PROBE=kin-h1odup MINEKIN_DOMAIN_PROBE_SECOND=kin-h1odup \
  bash test-orchestrator/runner/run.sh domain session start --profile /src/tests/fixtures/launcher/1.20.1.json
rc=2
domain: MINEKIN_DOMAIN_PROBE_SECOND names kin-h1odup, ... -- refused here, before anything is written
grep -c "MINEKIN_DOMAIN_SEAL" stderr = 0（rc=1）
```

  不设 ⇒ 封存句不出现，run 继续走到它自己的下一个守卫。材料：`.tmp/h1o/live-negative.err`。
- **早于任何落盘**：两发前后对私有卷做只读清单
  `docker run --rm -v minekin-h1o-live:/data alpine sh -c 'find /data -maxdepth 3 | sort'`：
  改前 `.tmp/h1o/volume-before-live.txt`、改后 `.tmp/h1o/volume-after-live.txt`，diff 为空
  ⇒ `VOLUME_UNCHANGED`。未建 attempt/bundle、未调用 `--record`、未动 registry、未新增封存。

## 5. CE-d 外溢面

```text
grep -n "MINEKIN_DOMAIN_SEAL" src/minekin_core/config.py    rc=1（空输出）
```

材料：`.tmp/h1o/ce-d-config-grep.txt`。契约里的 `product_roster` 外溢断言（`:211` 族）保留且在绿。

## 6. 门禁表（每道单跑、先读到 rc 才写进本表与 commit message）

| 门 | 命令 | 末行读数 | rc |
| --- | --- | --- | --- |
| shell 语法 | `bash -n test-orchestrator/runner/run.sh` | 无输出 | **0** |
| shell 语法 | `bash -n test-orchestrator/runner/domain.sh` | 无输出 | **0** |
| 契约 | `uv run --frozen --offline python -m pytest tests/contract/test_runner_scripts.py -q --tb=line` | `118 passed in 17.45s`（交付字节，见 §2/§3 两次复跑同值） | **0** |
| 判据 | `uv run --frozen --offline python tools/check_case_assertions.py` | `Case assertion implementations: OK (150 registered)` | **0** |
| 边界 | `uv run --frozen --offline python tools/check_boundaries.py` | `Minekin package dependency boundaries: OK` | **0** |
| fixture 摘要 | `uv run --frozen --offline python tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK` | **0** |
| workflow pins | `uv run --frozen --offline python tools/check_workflow_pins.py` | `Workflow pins: OK (every action is a commit, and each names its release)` | **0** |
| ruff check | `uv run --frozen --offline ruff check .` | `All checks passed!` | **0** |
| ruff format | `uv run --frozen --offline ruff format --check .` | `371 files already formatted` | **0** |
| pyright | `uv run --frozen --offline pyright` | `0 errors, 0 warnings, 0 informations` | **0** |
| 全量 pytest | `uv run --frozen --offline python -m pytest -q` | `2699 passed, 3 skipped in 281.93s`（见 §6.1） | **0** |
| 空白 | `git diff --check` | 无输出 | **0** |

各门完整输出存 `.tmp/h1o/gate-*.log`。

## 6.1 全量 pytest 与基线 2700/2 的差一格（如实具名）

收集总数不变：2699+3 = 2702 = 基线 2700+2 ⇒ 本笔没有增删任何测试函数（契约文件单独跑仍
`118 passed`，§2）。多出的那一个 skip 全部落在本卡允许面之外、且是**平台/材料条件**的：

```text
SKIPPED tests\unit/test_orphans.py:686          this platform cannot answer the question
SKIPPED tests\unit/test_silent_listener.py:123  @pytest.mark.skipif(sys.platform == "win32")
SKIPPED tests\unit/test_tested_provenance.py:354 bridge-1201 jar is not built on this host
```

后两格在本 Windows 检出上是条件跳过（win32 平台标记 / 本机未建 Bridge jar 的 `pytest.skip`），
读本机字节即得，与本卡 `run.sh`/契约改动无因果（两者均不读这两个文件所测对象的环境）。
主干基线的 2700/2 应是这两格中有一格在其度量环境可跑。本卡不修环境、不追这个数字，如实报。

## 7. 门载荷（唯一一条规范卷 `:ro` 只读复算）

```text
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker run --rm --entrypoint /bin/bash \
  -v C:/Users/darling/Documents/agent_work/minekin-wt-h1o:/src:ro \
  -v minekin-runner-data:/data:ro \
  -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  minekin-runner:local -lc 'python /src/tools/report_promotion.py --data-root /data'
```

（挂载前 `docker ps` 空列表核验、`docker version` rc=0/server 29.5.3；`trunk_digest.py` 只读复用自
`../minekin-wt-integration/.tmp/`，未写入该树。）实测：

```text
rc(report_promotion)=1              ← 按构造 blocked（本卡不注册 case、不翻 mandatory）
文档 103921 字节
gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
```

与主干钉住的基线**逐字节相同** ⇒ 门载荷在本卡字节上一字未移。材料：
`.tmp/h1o/gate-payload-doc.json` / `gate-payload.err` / `gate-payload-digest.txt`。

## 8. 四态封顶

- **仅在分支、待 M 复审**：本卡全部验收（转发、删登记翻转、非恒真反证、活体跨界读数、门表、门载荷）
  都在 `codex/minekin-h1o-forward-seal-knobs` 的字节上量得。
- 真实封证：**0**。未写规范卷、未建 attempt/bundle、未注册 case、未动 registry/`mandatory`/判据。
- `domain.sh`、`tools/**`、`src/**`、fixtures、registry、schemas、`.github/**` 全程 0 行。
- 未做/未验证（如实标注）：未做 H1j 式的 stub-argv 默认关闭 dump（§1 的 unset 语义按该先例既有读数
  与 §4 负对照句缺席陈述）；两枚旋钮各自的**真值活体封证**（`=1` 走完封存）不在本卡面内，未做。
