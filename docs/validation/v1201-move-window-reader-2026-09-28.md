# P1 项 5/6：`tools/read_move_window.py` 把授权窗读数固化成正式工具，并配 18 例正式测试（2026-09-28，M 主控）

日期：2026-09-28。工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-integration`（`main`）。
卡面：`#82 P1 项 5 —— 新判据字节下的真跑重封 + 反对照`，本次收口的是它的**读数侧**（正式工具 + 正式测试），
真跑与正/反对照的封存读数取自同日那次加入者控制战役跑。

**边界**：规范卷 `minekin-runner-data` 全程只以 `-v ...:/data:ro` 只读挂载出现；活体材料在 lane 私有卷
`minekin-m82-campaign`。未连接、未修改任何远程测试服；未改距离门槛（`MINIMUM_STEP_BLOCKS = 2.0`）与授权
窗长度；未翻 `mandatory`、未动 registry、未晋级产品门禁。本文不出现服务器地址。

## 1. 新增的业务能力与正式落点

| 文件 | 状态 | 含义 |
| --- | --- | --- |
| `tools/read_move_window.py` | 新增 | 读一个 run「被授权了什么、服务端在授权期间答了什么、哪两枚读数被当作窗口的首末记进了判定」，并逐条打印五枚对照会判成什么 |
| `tests/unit/test_read_move_window.py` | 新增（18 例） | 上述读数的正式测试；三件套 bundle 由测试自己搭（`asserter-inputs.json` + `server/server.log` + `bridge-trace.jsonl`），grant/release 用真跑的那两个瞬间 |
| `test-orchestrator/runner/demo-lan.sh` | 新增 | 双客户端（宿主 + 加入者）可靠控制 Demo 的可重复入口；`--auto-bundle` 的加入者拒止条件写在脚本头 |

工具**不做任何判定**：verdict 取自 `the_server_saw_the_kin_move`，归因取自 `move_window_attribution`，位移取自
`_horizontal`（`tools/assert_case_evidence.py` 的同一枚度量）。一个窗口只有一个读法，工具侧不可能悄悄和判定官分家。

## 2. 接口

```bash
# 已封存的 bundle
uv run python tools/read_move_window.py --bundle DIR --all-controls

# 只在卷上的活 run（在 runner 容器里）
MINEKIN_RUNNER_DATA=VOLUME bash test-orchestrator/runner/run.sh --shell \
    "python tools/read_move_window.py --data-root /data --kin KIN --username Kin2 \
        --server-directory /data/server-runs/run-1"

# 只要一枚对照，可重复给；--json 额外把读数打成一行 JSON
uv run python tools/read_move_window.py --bundle DIR --control drop-window-readings --json
```

`--bundle` 与 `--data-root` 必须二选一，否则 argparse 具名拒止（退出码 2）；台账载体读不到时也走 2 并说明
「这份 run 的台账读不出，所以没有窗口可归因」，而不是交回一个看起来像空窗口的读数。

五枚对照：`whole-log-pair`、`drop-window-readings`、`first-window-reading-only`、`death-before-tail`、
`departure-before-tail`。每枚只改**服务端日志**（台账与授权窗保持本 run 自己的字节），并自己说明改了什么；
对照永不写卷，也永不是证据。

## 3. 真实封证上的读数（逐字段）

材料：`bundle_digest a8690e61d96507bfe01287b9ce3f1f4fdea875842610dc9db7dae6a0763382fb`、
`case_version 397cefbdee685bc298243b76ad040e27d5fc415c2a3806c6085093812d13357d`、
`run_id 1025f9d5852c4e97b0da03de9bae56f8`、Kin `kin-m82-join-0928`、账号 `Kin2`。原始逐行读数在
`.tmp/m82/window-reading-0928-final.txt`，战役日志与失败材料在 `.tmp/m82/run2.log`。

```text
grant        : 2026-09-28T13:10:37.008321Z
release      : 2026-09-28T13:10:39.008287Z
window       : 2.000 s
readings     : 11 stamped answer(s) in the server's log
inside       : 2 answer(s)
start        : [13:10:37] (-3.50, -60.00, -3.40)
endpoint     : [13:10:39] (-9.51, -60.00, 2.72)
credited     : ... = 8.58 blocks
after release: [13:10:40] (-9.60, -60.00, 2.82)
verdict      : the window carries a step
comparison   : [13:10:33] -> [13:10:43] = 8.78 blocks, which clears the 2.0-block step
```

## 4. 五枚对照在这份真跑上的读数，以及它们各自证明了什么

| 对照 | 会判成 | 记进判定的首末 |
| --- | --- | --- |
| `whole-log-pair` | 通过（无派生，本 run 自己的字节） | 按整份日志首末量：8.78 格 |
| `drop-window-readings` | `NO_READING_INSIDE_WINDOW` | 什么都不记；删完之后整份日志首末仍量出 8.78 格 ≥ 2.0，因此这格拒的是**读数落在哪里**而不是距离 |
| `first-window-reading-only` | 通过 | `[13:10:37] → [13:10:38] = 4.57 格`（终点被换掉，判词不变） |
| `death-before-tail` | 通过 | `4.57 格`；**不按名字归因**的话会记 `8.58 格` |
| `departure-before-tail` | 通过 | `4.57 格`；**不按名字归因**的话会记 `8.58 格` |

**诚实口径（不掩盖的三点）**：

1. 这份真跑在松键前已经走了 4.57 格 ≥ 2.0，所以 `first-window-reading-only`、`death-before-tail`、
   `departure-before-tail` 在这里是**归因对照**而不是翻判对照——只有 `drop-window-readings` 翻成具名拒止。
   会把判词从通过翻成 `MOVED_LESS_THAN_A_STEP_IN_WINDOW:0.00` 的死亡/离场形状，由 §5 的正式测试
   （「停住后再远处」日志）证明，而不是由这份真跑证明。
2. 因此**目前还没有一次带真实死亡语句的 1.20.1 活体跑**。「死亡后冻结位置不能当有效终点」这条今天靠
   正式单测 + 上面 ungated 行（同一批字节，不具名就会把 `[13:10:39]` 那枚当作终点）成立；活体那一发是缺口，
   不是已完成。
3. 本卡的 run 有 `BRIDGE_LOST`、会话提前结束、`soak-samples.txt` 未产出（soak 没采到样本）。这些留在
   `.tmp/m82/run2.log`，不因为判据那格通过而抹掉。

旧 bundle `5086ee42…` 保留为历史证据；本次没有做摘要搬迁式的登记更新（registry/晋级属主控保留）。

## 5. 正式测试证明什么（`tests/unit/test_read_move_window.py`）

- 工具的 verdict 与 `the_server_saw_the_kin_move` 同源；带戳位置读数计数按位置答案算，不把朝向答案算进去。
- 窗口起点取「授予前最后一答」，且 `window.before is window.start`（这条关系是写死的，不是巧合）。
- 每枚对照都被证明**改变了它声称改变的东西**：删窗内答案 ⇒ 具名拒止且时钟集合可见地少了两枚；只留首答 ⇒
  终点从 `[13:10:39]` 变 `[13:10:38]`、记账距离从 6.00 变 3.00；补一句死亡/离场 ⇒ 派生句紧邻在那一答之后、
  时钟集合不变（证明它被当作一句话读，而不是被当作一个位置答案），判词翻成 `MOVED_LESS_THAN_A_STEP_IN_WINDOW:0.00`，
  而不具名归因仍会把远处那枚记成终点（16.00 格）。离场那格还先剥掉本 run 自己那句 `left the game`，
  使派生句在日志里**只有一句**。
- 没有任何一枚对照能动台账、用户名、run 标识、授予/释放瞬间或门槛（逐控制断言五个瞬间与 `2.0` 全等）。
- 三枚「无从派生」的守卫各自**报出自己为什么不动手**，且返回的是同一个对象；未知控制名在碰材料之前 `ValueError`。
- CLI：干净 bundle 退出码 0 且 `--json` 最后一行可解析；`--all-controls` 打印全部五枚；有输入但无台账载体 ⇒
  退出码 2 并具名说明；非 bundle 目录 ⇒ 退出码 2；材料参数必须二选一；活 run 那侧把五个关键字段原样交给
  `read_run_material`（用替身测，不造假 run）。

## 6. 一次量出来的判据字节代价（先测后改，别按构造猜）

把 `_horizontal` 改成公开名（让兄弟工具可以「正当地」跨模块用）在这棵树上是**有代价的**：
`tools/check_case_assertions.py` 记录的摘要取自**执行该判据的函数自己的源码**，而被改的名字出现在三个被引用函数的
函数体里，于是 8 行登记的 `assertion_digest` 当场漂走，实测点名：
`CORE-040`、`CORE-050`、`CORE-060`、`CORE-090`、`V1201-040`、`V1201-060`、`V1201-080`、
`V1201-LAN-JOINER-CONTROL-CASE-001` —— 一次纯改名会叫一整卷封证需要重封。

因此本卡**不**改判据字节：按仓库既有先例（`tools/verify_tested_provenance.py:61` 用
`# pyright: ignore[reportPrivateUsage]` 跨模块读同一枚私有度量）在工具侧读取同一枚 `_horizontal`，
判据文件回到 HEAD 字节。落地后 `check_case_assertions` 读数：`Case assertion implementations: OK (151 registered)`，
`case_version` 未漂，§3 那枚封证继续是当前构建的证据。

⇒ 记下来的规则：**要公开化判据内部符号，先跑 `check_case_assertions` 量漂移面**，并把重封当一次独立决策，
不要塞进实现提交。

## 7. 门读数（最终字节上跑，逐条退出码）

```bash
cd C:/Users/darling/Documents/agent_work/minekin-wt-integration
uv run ruff format tools/read_move_window.py tests/unit/test_read_move_window.py   # rc=0
uv run ruff check tools tests/unit/test_read_move_window.py                          # rc=0, All checks passed
uv run pyright tools/read_move_window.py tests/unit/test_read_move_window.py         # rc=0, 0 errors
uv run python tools/check_case_assertions.py                                         # rc=0, 151 registered
uv run python -m pytest tests/unit/test_read_move_window.py -q                       # 18 passed
uv run python -m pytest tests/unit tests/contract -q                                 # 见 .tmp/m82/final-gates-0928.log
bash -n test-orchestrator/runner/demo-lan.sh                                         # rc=0
```

`tests/unit` 全量在最终字节上的通过数以 `.tmp/m82/final-gates-0928.log` 末行为准（同一次跑还含 `tests/contract`）。

## 8. 仍未支持 / 未闭合（具名）

- 带真实死亡语句的 1.20.1 活体跑还没有；`demo-lan.sh` 自身的端到端一发也还没有（它这次只是入口固化 + 语法门）。
- 「两次 run 是不是同一份编排字节」按构造读不出（bundle 不钉编排层字节），属主控保留。
- 门禁晋级、V08/远程测试服、HOST/PERSIST、Dashboard 写端点仍在主控手里，本卡未触碰。

## 9. 下一步（一张卡）

`#84 V1201-LAN-JOINER-DEMO-ENTRY-RUN-001`：用 `test-orchestrator/runner/demo-lan.sh` 在私有卷跑一次干净加入者
控制演示（含松键后停止），拿 `tools/read_move_window.py` 的读数与 `evidence verify` 的复判各一份；其中要包含
**会话内真死一次**的形状（让世界里的僵尸在授权窗内打死加入者），把 §4 第 2 点那条缺口从「单测证明」升级成
「活体证明」。规范卷只读，不动登记。
