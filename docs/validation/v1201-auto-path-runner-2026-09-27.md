# V1201-AUTO-PATH-RUNNER-001 — 自动路径与服务器侧读数在同一受控通道内同时成立（H lane，G1+G2）

日期：2026-09-26/27（容器实测跨夜）。执行 lane：H（test Harness）。
基线：main @ `ea5423e9711f944d27b4bdd9257d28c7da35d67e`（`git ls-remote origin refs/heads/main` 实读一致）。
分支：`codex/minekin-auto-path-runner`，提交 `efb8630`（G1）与本记录的 G2 提交。
改动面：仅 `test-orchestrator/**` 与 `tests/contract/test_runner_scripts.py`。
`tools/seal_run_evidence.py` 只按其 argparse 实际必填字段读取接口，未改；`src/**`、案例
fixture、registry、`docs/p0-*` 证据记录未动。规范卷 `minekin-runner-data` 全程未挂载
（E lane 唯一写者）；所有容器切片用 `minekin-h1b-20260926` 卷或 `/src` 只读挂载。
没有任何 seal 发生：封证独占窗口不在本卡权限内（见"停在何处"）。

## 缺陷与红线复测（先量红）

### G1 — `domain.sh` 看不见 `--auto-bundle`，封证恒传空 `--profile`

复现命令（受控容器内，`minekin-runner:local`，镜像 id `b67a4d917306`；逐字 awk 抽取
真脚本参数扫描区与封证展开，不手抄）：

```text
DOMAIN_SH=/src/.tmp/domain-before.sh bash /src/.tmp/g12-red-driver.sh
```

红读数（改动前 domain.sh，sha1 `9021ea916ea4417b72f578f403172b29bc8e5ff2`）：

- 扫描区对 `session start --auto-bundle <registry> --server-profile <1.20.1 profile>`
  的展开：`profile=[] launched_version=[] version_args_count=0`，且不存在
  `auto_bundle` 变量（扫描只匹配 `--profile/--server-profile/
  --connection-timeout-seconds/--hold-at`）。
- 按封证分支的真实展开调用 sealer（`--profile ""` + `--server-profile` +
  `--run-id g12-no-such-run`）：rc=2，stderr
  `"…controlled-offline-server-1.20.1.json is not a Server Profile the product
  accepts: the launcher profile is not readable UTF-8 JSON"`。
- 正对照 1（具名正确 recipe）：同一条 sealer 命令把 `--profile` 换成
  `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json` 后通过 profile 读取
  阶段，抵达下一个诚实前沿：`"no Kin is named for run g12-no-such-run: … the data
  root holds 0 Kins rather than one"`（rc=2）。
- 正对照 2（版本不符 recipe）：具名拒绝 `"the session launches Minecraft 1.21.4,
  the target allows 1.20.1"`。

### G2 — `enable-status=false` 的状态盲区与探针缺省

复现命令（同一镜像，真起 1.21.4 服务器 JVM 三轮，全部落在本 lane 卷
`/data/server-runs/`，规范卷未挂载）：

```text
bash /src/.tmp/g2-server-driver.sh   # 原始记录 .tmp/g2-red.log
```

红读数：

- R1（完全按 domain.sh 现在的样子调用 `tools/run_controlled_server.py`）：
  `server.properties` 实录 `enable-status=false`；产品自己的
  `python -m minekin_core server probe --server-profile <loopback profile>` 回
  `"outcome": "NO_RESPONSE", "detail": "the endpoint closed before any frame"`，
  rc=17。
- R2（正对照：同一份 settings 只翻 `enable-status=true`，直接
  `java -jar server.jar nogui` 起服）：probe 回 `"outcome": "OBSERVED"`，
  protocol 769、version_text "1.21.4"，rc=0。
- 控制台探针默认能力：R1（不给探针旋钮）server.log 中探针应答
  （`No entity was found` / `has the following entity data`）共 **0** 行；
  R3b（`--probe-player Kin --probe-every-seconds 3`）**10** 行 — 非空转对照成立。
  （R3 首轮因 R2 的 JVM 仍占端口报 `FAILED TO BIND TO PORT`，单独重跑为 R3b，
  该失败本身也记录在 `.tmp/g2-red.log`。）

## 改绿（同一命令改后的具名读数）

容器内重放（`.tmp/g12-green.log`、`.tmp/g2-green.log`，改动后 domain.sh
sha1 `0eb3f55dfa10d686553ff1da8f514e5f5266f198`）：

- 扫描+版本推导：auto argv → `auto_bundle=[…reviewed-tested-bundles.json]
  launched_version=[1.20.1] version_args=[--version 1.20.1]`（schema 2 单一
  allowed 版本）；对 schema 1 pinned profile → `1.21.4`。
- 反证（改动后全部具名拒绝、rc=2；改动前全部静默通过）：双版本 allow-list →
  `"an auto-bundle run has to start the server its Server Profile allows, and …
  names no single version to start"`；同时给 `--profile` 与 `--auto-bundle` →
  `"this run names both --profile and --auto-bundle; the session admits exactly
  one bundle source"`；auto + joiner → `"an auto-bundle run cannot also ask for a
  joining second client…"`。
- 封证命名：run document 的 `auto_bundle.recipe_path`（形状按产品
  `bootstrap.py::_emit` / `auto_session.py::AutoBundleDecision.as_document` 构造，
  **replay 专用，未跑真客户端**）→
  `"the seal names the recipe the run resolved to: …/bundle-candidate-1.20.1.json"`，
  `blocked=0 args=[--profile …/bundle-candidate-1.20.1.json]`；sealer 用该参数到达
  与红阶段正对照同一前沿（`no Kin is named for run g12-no-such-run`）。文档无
  decision 段 → `blocked=1`，stderr 具名
  `"names no readable recipe it resolved to; … no seal was attempted"`，sealer
  不被调用。手动 run 展开不变（`--profile <given>`）。改动前同一重放：
  `seal_blocked: unbound variable`、抽取区 0 行（区块不存在）。
- 状态读数（对红阶段留下的**真实** run 目录重放抽取的 ready 区块）：
  R1 目录 → `domain: the controlled server reports enable-status=false`；
  R2 目录（正对照）→ `enable-status=true`；settings 无此行（反证）→
  `enable-status=unreadable`。auto run 对 false/unreadable → rc=2 具名停止
  `"the auto path needs this server to answer status … stops before the client
  starts"`；auto run 对 true → 通过不停止。改动前：任何情况都无读数行。
- 探针默认（抽取 `probe_args` 构造区）：无旋钮 →
  `[--probe-player Kin --probe-every-seconds 5]`；给旋钮 → 形状不变；
  `use-target` 无旋钮旧形状（会被工具拒）现随默认一并成立。改动前无旋钮 → `[]`。
- 判据未动：读这些行的等待/判断仍以 `MINEKIN_DOMAIN_PROBE` 具名门控
  （`[[ -n "${probe}" && "${hold_requested}" -eq 1 …` 原样保留），新契约测试把这条
  门控也钉住。

## 契约测试

`tests/contract/test_runner_scripts.py` 新增
`test_an_auto_bundle_run_is_captured_named_and_otherwise_refused` 与
`test_the_console_probe_is_a_default_and_the_status_switch_is_read`。
两者对 `.tmp/domain-before.sh`（缺陷在位）量红（各 1 failed，断言即上列读数行），
G2 测试另对"G1 已改、G2 未改"的中间态量红一次，改后全文件 19 passed。
`bash -n` 两脚本均通过。

## 基线门禁（worktree，`uv sync --locked --dev` 后全部 `uv run --frozen`）

- `ruff check .`：All checks passed。`ruff format --check .`：339 files already
  formatted。
- `pyright`：0 errors, 0 warnings, 0 informations。
- `pytest -q` 全量：2520 passed, 3 skipped in 361.62s（三个 skip 为主干上既有的
  Windows 平台跳过：test_orphans:686、test_silent_listener:123、
  test_tested_provenance:354，与本卡无关，未新增）。
- `check_boundaries`：OK。`check_case_assertions`：OK（140 registered）。
  `verify_fixture_digests`：OK。`check_workflow_pins`：OK。
- `git diff --check`：干净。`bash -n` 两脚本：通过。

## 停在何处（诚实边界与 N/A）

- **未做任何 seal**：封证需要规范卷与独占窗口，两者都不在本卡允许面 — 按边界停在
  该前置并登记，不抢卷。
- **端到端 auto-bundle 真跑+封证 N/A**：需要真实受管客户端 JVM、1.20.1 bridge 可
  安装（H-2，registry 桥接物取不到 → store 缺料 → 客户端拒启），以及下面的状态翻
  转。不以旧 PASS 顶替。
- **需主控另卡（本卡允许面之外，只登记不修改）**：
  1. `tools/run_controlled_server.py` 第 247 行硬编码 `enable-status=false`，auto
     路径的目标解析与状态观察过不去。domain.sh 已改为：读数打印 + auto run 具名
     早停；真正的翻转在该工具（V1 报告 H-5 的落点），需主控另卡。
  2. V1 移交的 H-3/H-4 属产品下载器（`src/**`），非本卡内容，维持 V1 登记。
  3. 本卡未新建卷：沿用 `minekin-h1b-20260926`（H1b 遗留），若主控要求独立
     `minekin-g1g2-*` 卷可在复审时重放。
- 文档中不出现任何外部地址；测试服一律匿名描述。

## 四态声明

G1/G2 的 harness 修复：**仅在分支**（`codex/minekin-auto-path-runner`，未合入
main，等待主控双审）。红/绿读数与对照：**真实测量**（受控容器、真 JVM、lane 卷）。
端到端 auto-bundle 封证：**尚未验证**（如上 N/A 与阻断）。本记录不宣称 Minekin
完成，不宣称任何门禁点亮。
