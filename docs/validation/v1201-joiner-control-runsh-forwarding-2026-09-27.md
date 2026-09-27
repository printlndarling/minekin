# H1j `V1201-JOINER-CONTROL-RUNSH-FORWARDING-001` — 加入者控制四名的 `run.sh` 转发：读数与反证

日期：2026-09-27。基线：`dcd914a`（= 当时远端 main，H1h 合入后）。分支：`codex/minekin-runsh-joiner-forwarding`。
规范卷：全程不挂载；唯一例外是门载荷复算一条按卡面允许以 `-v minekin-runner-data:/data:ro` **只读**挂载，未建 attempt/bundle。
允许面核对：本卡改动只有 `test-orchestrator/runner/run.sh`、`tests/contract/test_runner_scripts.py` 与本记录。
`domain.sh`、`src/**`（含 `config.FORWARDED_VARIABLES`）、`tools/**`、`tests/fixtures/**` 在
`git diff --stat dcd914a` 里均为 0 行。

## 0. 改了什么

- `run.sh` 的 `domain` 分支转发名单（`EXTRA_ARGS`）末尾加入既有四名，写法与名单里每个既有条目相同——
  裸 `-e NAME`：宿主设了 docker 才把值带进容器，宿主没设就不带（`run.sh:86-87` 的既有注释就是这个语义）。
  未新增名字、未给默认值、未触碰任何命令行构造。
- `tests/contract/test_runner_scripts.py::test_every_knob_the_harness_reads_is_one_the_wrapper_hands_it`
  里的精确集合断言被**有意翻转**（本卡唯一被允许改写的既有断言，提交信息点名）：
  - 改前：`assert read - delivered == JOINER_CONTROL_KNOBS` —— 要求四名**不得**出现在 `run.sh`。
  - 改后：每名逐一要求已转发（`JOINER_CONTROL_KNOBS - delivered` 必须为空）；
    `assert read - delivered == set()`（第五个被 `domain.sh` 读而未转发的名变红）；
    保留 `assert delivered - read == set()`（转发而无人读变红）；
    新增：四名仍**不得**出现在 `src/minekin_core/config.py`（产品转发名单，runner 的旋钮进它就是放宽产品入口）。
  - `JOINER_CONTROL_KNOBS` 常量本体与 `domain.sh` 的驱动区、`drive_joiner_control` harness 均未动。

## 1. 验收一：默认关闭等值（四层读数，全部字面）

harness：`PATH` 上一个不执行任何事物的 `docker` 桩（`.tmp/h1j/stub/docker`），打印
①`docker argv`（逐字一行一词）与 ②`container environment`（按 docker 对裸 `-e NAME` 的既定语义解析：
宿主设了才落 `env NAME=value`，没设就不进容器，桩里记作 `unset-not-passed`，不计入环境段）。
调用（基线与新字节各 dump 一次；基线字节从 `git show dcd914a:...` 取到 `.tmp/h1j/base-run.sh`，
它与工作树 `run.sh` 距仓库根同为两级，故 `REPOSITORY_ROOT`、jar 挂载行逐字可比）：

```text
bash .tmp/h1j/dump.sh <run.sh> <out>     # 见 .tmp/h1j/dump.sh：清空四名的环境 + 桩 docker + 假 jar
```

完整 dump 的 sha256（含两段）：

```text
ed9a05c79a1a505f8b02ea7e0b6e5d764f3ef147e9914a85997c998bb812ae0b *.tmp/h1j/dump-base-none.txt
2eb6a02624e39bba05309d972ddd2f08a658d0020472a9851ee9acd51c3037f7 *.tmp/h1j/dump-tip-none.txt
```

**docker argv 层面的字面 diff（如实报告：不逐字相同，差的恰是四名声明）**：

```text
63a64,71
> -e
> MINEKIN_DOMAIN_JOIN_LOOK_YAW
> -e
> MINEKIN_DOMAIN_JOIN_LOOK_PITCH
> -e
> MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS
> -e
> MINEKIN_DOMAIN_JOIN_CONTROL_PRINT
115a124,127
> unset-not-passed MINEKIN_DOMAIN_JOIN_LOOK_YAW
> unset-not-passed MINEKIN_DOMAIN_JOIN_LOOK_PITCH
> unset-not-passed MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS
> unset-not-passed MINEKIN_DOMAIN_JOIN_CONTROL_PRINT
```

这不是"宿主把值带进去了"：那 4 对 `-e NAME` 与名单里既有条目（如 `-e MINEKIN_DOMAIN_JOIN`）一样是
**声明**，docker 见裸名宿主未设即不进容器。因此「逐字相同」这条读数按卡面退到它能成立的那一层——
**容器实际收到的环境**（决定驱动是否被武装的层），两次 dump 的环境段（剔除 `unset-not-passed` 记号线后，
该记号线只存在于桩的打印格式、docker 里本无对应物）：

```text
8e9c580249507cbe672c699283333881b1c95791e6a62b112e03e4417a273be7 *.tmp/h1j/env-base-none.txt
8e9c580249507cbe672c699283333881b1c95791e6a62b112e03e4417a273be7 *.tmp/h1j/env-tip-none.txt
--- effective env diff ---
ENV_IDENTICAL
```

即：四名一个都没设时，基线容器与新字节容器收到的环境变量集合逐字节相同、命令行逐字节相同，
驱动的默认关闭等值成立。

## 2. 验收二：逐个点亮（四组字面读数）

同一 harness，只设其中一名（`.tmp/h1j/dump-tip-one-<NAME>.txt`）。环境段里 `MINEKIN_DOMAIN_JOIN_*` 的全部行：

```text
== only MINEKIN_DOMAIN_JOIN_LOOK_YAW set to 22.5 ==
env MINEKIN_DOMAIN_JOIN_LOOK_YAW=22.5
   3 of the four still unset-not-passed
== only MINEKIN_DOMAIN_JOIN_LOOK_PITCH set to -10 ==
env MINEKIN_DOMAIN_JOIN_LOOK_PITCH=-10
   3 of the four still unset-not-passed
== only MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS set to 1.5 ==
env MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=1.5
   3 of the four still unset-not-passed
== only MINEKIN_DOMAIN_JOIN_CONTROL_PRINT set to 1 ==
env MINEKIN_DOMAIN_JOIN_CONTROL_PRINT=1
   3 of the four still unset-not-passed
```

每组：被设的那一名以宿主给的值进入容器环境，其余三名停在 `unset-not-passed`，不进容器。

## 3. 验收三：断言翻转的两个方向都量了

- 旧断言对新字节变红（证明翻转是必须的、不是装饰），容器内对 shipped 字节的只读求值：

```text
OLD assertion (read - delivered == JOINER_CONTROL_KNOBS) on the new bytes: False -> measured read-delivered = []
NEW assertion read - delivered == set() with a fifth read-but-unforwarded name: False -> measured = ['MINEKIN_DOMAIN_JOIN_FIFTH_UNFORWARDED']
```

- 容器内整文件契约测试：`64 passed`。基线该文件为 64 passed，差值为 0——本卡只**翻转**既有断言，
  未新增测试函数，`drive_joiner_control` 族（H1h 的 33 个用例）一测未动。
  首跑曾 `1 failed`（本卡新增的 config.py 读取把仓库根上溯了一级：`RUNNER.parents[2]`→应为 `[1]`，
  `FileNotFoundError`），修正后全绿；该失败是本卡新行自身的缺陷，不是既有断言被改坏。

## 4. 反证两则（真实失败输出，均已还原）

(a) **无条件 `-e NAME=`**：把四名改成 `-e NAME="${NAME:-}"`（宿主没设也给容器塞一个空值）——在一次性
副本 `.tmp/h1j/mutant-a-run.sh` 上做，`bash -n` 通过后同 harness dump：

```text
--- mutant A effective env shas vs base ---
8e9c580249507cbe672c699283333881b1c95791e6a62b112e03e4417a273be7 *.tmp/h1j/env-base-none.txt
7cb2307f1c6327539a90be17496cd55b6fa826f9396cd32b26de9f4332789499 *.tmp/h1j/env-mutantA-none.txt
--- diff (acceptance 1 must go RED on this mutant) ---
0a1,4
> env MINEKIN_DOMAIN_JOIN_LOOK_YAW=
> env MINEKIN_DOMAIN_JOIN_LOOK_PITCH=
> env MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=
> env MINEKIN_DOMAIN_JOIN_CONTROL_PRINT=
diff_rc=1
```

验收 1 变红：容器收到的环境多了四个空值名，等值不再成立。（这四个空名恰好就是 H1h 文档里说的
「一个跑过但什么都没被要求」的形状——seal 照常发生，判读却读不出宿主是否设过。）

(b) **名单加第五名**：向 live `run.sh` 临时插入 `-e MINEKIN_DOMAIN_JOIN_FIFTH_DEMO`（先 `cp` 快照，
跑完还原并以 `sha256sum -c` 核对一致），容器内跑翻转后的契约测试：

```text
E       AssertionError: run.sh delivers these and nothing reads them: ['MINEKIN_DOMAIN_JOIN_FIFTH_DEMO']
E       assert {'MINEKIN_DOM...N_FIFTH_DEMO'} == set()
tests/contract/test_runner_scripts.py:145: AssertionError
1 failed, 2 warnings in 1.86s
```

验收 3 方向变红，随后 `sha256sum -c .tmp/h1j/tip-run.sha` ⇒ `test-orchestrator/runner/run.sh: OK`，
diff 回到本卡的 +11/-1。

## 5. 本地门禁（原始输出位置与读数）

- `bash -n test-orchestrator/runner/run.sh` ⇒ 通过（`BASH_N_OK`）。
- 容器契约（镜像 `minekin-runner:local`，`/src:ro`，`-e PYTHONPATH -e MINEKIN_HOME -e LD_LIBRARY_PATH`）：
  整文件 `64 passed`（见 §3）。
- 宿主 `uv run ruff check` ⇒ `All checks passed!`。
- 宿主 `uv run ruff format --check` ⇒ `1 file would be reformatted, 360 files already formatted`。
  **申报**：该不合规是本文件在基线就有的 4 处（全部位于 H1h 区段，宿主 ruff 0.16.8 与 H1h 当时所用
  formatter 版本漂移所致）；把 tip 与 base 的 `ruff format --diff` 输出逐行比对 ⇒
  `IDENTICAL_PREEXISTING_NONCOMPLIANCE`（16 行建议改动完全相同），本卡新增行零不合规。
  中途一次 `uv run ruff format <file>` 曾顺手重排这 4 处 H1h 既有行——已逐处还原为基线字节，
  最终 diff 只含 §0 所列改动（这是本卡执行中的越界与纠正，如实记）。
- `git diff --check dcd914a HEAD` ⇒ 干净（`DIFF_CHECK_OK`）。
- 门载荷复算（只读挂 `/data:ro`，仅此一条）：容器内
  `python tools/report_promotion.py --data-root /data` 后对 `{"work_packages","overall"}` 子集做
  `json.dumps(sort_keys=True)` 取 sha256 ⇒
  `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，`status: blocked`——
  与 §2.3 钉住的基线逐字节相同；本卡不注册 case，门未动。

## 6. 没做到 / 未验证（四态口径）

本卡交付的是**仅在分支**；不是真实封证，封证相关一律**未验证**。具体：

- 没有真跑过 `docker run`（桩只证 argv 与环境的递交形状）；没有真实第二客户端经 `run.sh` 转过或走过。
- `domain.sh` 一字节未动、也未为其复测（H1h 的 64 测在本卡字节下全绿即其形状未移）。
- V5 的活体读数未做（本卡不武装任何真跑）；`config.py`、registry、fixture、`tools/**` 未触碰。
- 完整单测套件未在容器内跑（卡门只要求契约文件；H1h 的 asserter 单测读数未在本卡复量）。

## 7. 复现命令（Git Bash）

```text
# 验收 1/2 与反证 (a)
bash .tmp/h1j/dump.sh test-orchestrator/runner/run.sh out.txt      # 环境清空四名的调用在 dump.sh 内
# 容器契约
export MSYS_NO_PATHCONV=1
docker run --rm --entrypoint /bin/bash -v "$(cygpath -m "$PWD"):/src:ro" \
  -e PYTHONPATH=/src/src -e MINEKIN_HOME=/data -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  minekin-runner:local -lc 'cd /src && python -m pytest -q tests/contract/test_runner_scripts.py'
```

（`.tmp/` 内全部探针/桩/变异副本保持未跟踪，不进仓。）
