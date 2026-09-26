# 镜像内自检重封一轮（E-CO）：OFFLINE-001 / OFFLINE-040 / OFFLINE-050 / ADMIT-080

日期：2026-09-26（封存文件时间 2026-09-26 15:45，取自规范卷内新 bundle 文件的 mtime；bundle 字节本身不记录时钟）。
分支 `codex/minekin-evidence`，起点 `f632665`，`git fetch origin` 后确认 `refs/heads/main` = `ea5423e9711f944d27b4bdd9257d28c7da35d67e`，`git merge --ff-only origin/main` 干净快进（含 H1a 的 pytest 钉住镜像层）。工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-evidence`。

## 1. 目的

第五刀（`docs/p0-repo-four-case-run-2026-09-26.md`）的形状是「镜像外跑、镜像内封」：四条 repo 检查在宿主 `.venv`（pytest 9.1.1）里跑，只有 `seal_repo_case.py` 进了受控镜像。H1a 已把钉住版本的 pytest 装进 runner 镜像（`ee0a439`），本卡把剩下半步补上——**同一个受控镜像里跑、同一个镜像里封**，使 bundle 的 `environment` 段与实际执行检查的环境一致。依赖只有 H1a，本卡不要求真实 Minecraft/JVM。

## 2. 边界

- 只跑不改：`src/**`、`tools/**`、`test-orchestrator/**`、`tests/fixtures/**` 判据、registry 的 `status`/`gaps`/`mandatory` 一律未碰；无新 case id、无新断言、无 mandatory 提升。repo 侧无改动证明：`git status --porcelain -- src tools tests test-orchestrator schemas bridge` 输出 0 行；整工作树在提交本文档前干净（`.tmp/` 被 gitignore）。
- 唯一写入目标是规范卷 `minekin-runner-data`：一次 run+seal（脚本 `.tmp/e6-02-run-seal.sh`，卷挂载可写），新 attempt 一律 `sequence +1`（四条都是从 seq 1 到 seq 2），既有 attempt 行与既有 bundle 字节零改写——用前后逐目录指纹证明（§6）。所有读数与反证在 `/data:ro` 下的只读挂载 + 容器 `/tmp` 副本里做。
- 不接触用户远程服务器，不探测任何外网地址；本文档不含任何基础设施地址（只出现本地路径、卷名与镜像名）。
- 镜像：新 `minekin-runner:local`（`b67a4d917306`，H1a 后构建）；修前参照 `minekin-runner-before:local`（`3f0938809910`）仅用于一条独立反证（§7.4）。

## 3. 复现命令与读数

宿主侧统一配方（`LD_LIBRARY_PATH` 是 `/opt/sqlite/lib`；卡面上 `/opt/sqlnet/lib` 为笔误，卡内已自注）。写卷的那一步：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/e6-02-run-seal.sh' > .tmp/e6-02-run-seal.log 2>&1
```

其余步骤（基线 / 读数 / 反证 / 二读 / 修前镜像）都是同配方换 `/data:ro` 与脚本名：

```bash
for s in e6-01-baseline e6-03-readout e6-04-reversals e6-05-rerun; do
  docker run --rm --entrypoint /bin/bash -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
    -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src minekin-runner:local -lc "bash /src/.tmp/${s}.sh" > ".tmp/${s}.log" 2>&1
done
docker run --rm --entrypoint /bin/bash -v "${REPO}:/src:ro" \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  -w /src minekin-runner-before:local -lc 'bash /src/.tmp/e6-06-before-probe.sh' > .tmp/e6-06-before-probe.log 2>&1
```

`e6-02` 内核对每个 case 做的（四条只差 case 名）：

```bash
python3 tools/run_repo_case.py --case tests/fixtures/cases/<c>.json \
  --output-directory /tmp/e6-out/<c> > /tmp/e6-verdict-<c>.json
python3 tools/seal_repo_case.py --data-root /data \
  --case tests/fixtures/cases/<c>.json \
  --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json \
  --verdict /tmp/e6-verdict-<c>.json --output-directory /tmp/e6-out/<c>
```

镜像内解释器读数（e6-02 首行、e6-05 同）：`/opt/minekin/bin/python3 pytest 9.1.1`。
运行读数（e6-02 log）：四条 `run_rc=0`；verdict 分别 5/5、3/3、3/3、6/6 held、`failures=[]`、`result=PASS`。
封存读数（e6-02 log）：四次 `seal_rc=0`，`"status": "sealed"`，`attempt_sequence: 2`，`supersedes_run_id` 均指向 seq-1 旧 run。

一个如实记录的副作用：镜像内 pytest 试图写 `/src/.pytest_cache`（`/src` 只读）产生
`PytestCacheWarning: cache could not be written`，检查仍 `1 passed`、exit 0；该告警被原样封进
`checks/*.log`（这正是新 log 632 字节与旧 102 字节差异的一部分，见 §5）。

## 4. 新封的四个 bundle（本卡真实封证）

| case | 新 run_id | bundle_digest | 产物数 | held | seq 1 旧 run（被 supersedes） |
|---|---|---|---|---|---|
| OFFLINE-001 | `46f88ff633094d79a1a2ec456049f13e` | `d59283f46d3ce04236b2f3d5b8cbd08a5c89568954d006216ae657e50cd72baf` | 9 | 5/5 | `935c034a99f04fa9a121e7ef739a3f5d` |
| OFFLINE-040 | `e9ee19ab127246c590ec22e25e0d8978` | `62db1336bb4ef53c0b567e955d6b8e3c7cfe1a28f483f6bc97815c826edd2894` | 7 | 3/3 | `4f324c20830f4e95a62e497e5b3d7a3b` |
| OFFLINE-050 | `8af1ad702167465ba194530fe69a0182` | `29fe5a5f8972170a92836a554fab52152d8f7f20c4a668cddb89299ef025dacf` | 7 | 3/3 | `f42030333c904d489e2042fb95bccf22` |
| ADMIT-080 | `8ffed6f1a7394d31a1e90776714429e6` | `e06ee8e7d6c36c6ae7f2e442806f200e29ab3b7b1052f8ad0c1dbe71b3d31084` | 10 | 6/6 | `66c51fc7a2384c9d8b09ddf96ac129f2` |

四条 `case_version` 与 seq 1 完全相同（`6b0241fc…` / `a3beb905…` / `b4beb8a6…` / `35081d5f…`）——判据未动；`launch_plan_digest` 均为 `bcc0c10d46ab5c0b46d0c86f7e0de9d0d57b635bc17f9dcffdf7631eba8125e2`。

## 5. 四读（每 case 四个独立读数）

以 OFFLINE-001 为例列出原始形态，其余三条同形状（run id / digest / 产物数按 §4 表替换）；全部原文在 `.tmp/e6-02…05-*.log`。

1. **封存判据**（e6-02 stdout JSON）：`"result": "PASS", "failures": [], "attempt_sequence": 2, "status": "sealed"`。
2. **`evidence verify`**（e6-03，只读挂载）：`verify_rc=0`，`{"verified": true, "sealed": true, "status": "verified", "result": "PASS", "artifacts": 9, "violations": []}`。四条全部 `rc=0 / verified true / violations []`，产物数 9/7/7/10。
3. **`report_promotion` 行**（e6-03，`report_rc=1` 为整体 blocked 的正常码）：四条 seq-2 行均 `verified true, sealed true, from_repository_build true, result PASS, violations []`；`re_judged` 为 `UNJUDGED`，reason 是 repo bundle 的既定口径：`does not record the inputs its judgement was made with (asserter-inputs.json)`。
4. **`rejudge_evidence.py`**（e6-03）：四条均 `rc=2` + 上述同一 reason 原文（与读数 3 的 reason 逐字一致，即两个通道互相印证而非孤证）。因该通道对 repo bundle 结构上不可判（不记 asserter 输入），**第二读改用镜像内重跑**（e6-05）：四条新 run id `8df61f4012724856a1fc10ea3d7a15de`（5/5）、`57bbf229c3dc49f2b44afd55af41637c`（3/3）、`1e1c9bbfacce4549b00713c359e6c8fd`（3/3）、`0faa9f207e124e1f8c47c081147438d4`（6/6），全 PASS、`rc=0`、未封进卷（只是重读）。

## 6. environment 段对比（本卡的诚实核心）

**新旧四个 bundle 的 `environment` 段逐字节相同。** 四对（e6-03 log §environment comparison，`environment_equal: True` ×4）：

- `os_kernel`: `Linux 6.18.33.2-microsoft-standard-WSL2`
- `java_runtime`: `openjdk version "21.0.12.1" 2026-08-18 LTS / OpenJDK Runtime Environment Temurin-21.0.12.1+1 (build 21.0.12.1+1-LTS)`
- `cpu_memory`: `20 vCPU / 7.6 GiB`
- `renderer_display`: `unmeasured`

原因：`environment.host_facts()` 记录的是**封存进程**的环境，而第五刀的封存进程本来就已在同一容器里（该口径在第五刀 §5 已判为「②-b 按封存进程解释，不重封」）。所以按卡面要求如实报告：**本卡没有改变 environment 段本身的口径读数**。

口径上真正的改进在别处，且可用字节验证——**bundle 声明的环境现在与检查实际执行环境一致**：

1. `orchestrator-trace.json` 里检查命令的解释器：旧 `C:\Users\darling\Documents\agent_work\minekin-wt-evidence\.venv\Scripts\python.exe` → 新 `/opt/minekin/bin/python3`（四对均如此，e6-03 原文 `old/new trace.interpreters`）。
2. 封存的检查日志大小 102 → 632 字节（每条 check 皆然，e6-03 逐文件表）：新 log 含镜像内 pytest 的真实输出与只读 `/src` 缓存告警，旧 log 只有宿主跑的两行摘要。

即：旧 bundle 的 environment 说「容器」，但检查实际跑在 Windows venv——两个证据面（trace、日志）当时就不自洽；本卡后两边一致。

## 7. 反证与正对照（全部在容器 `/tmp` 或卷外宿主 `.tmp/` 副本里做，规范卷全程 `:ro`；各反证脚本首行的可写性哨兵均输出 `/data writable False`）

**7.1 P 正对照**（e6-04）：把 `/data/repo-evidence` + 台账整目录原样复制到 `/tmp` 副本再读——13 个 bundle、69 attempt 行、`unverified []`、`unsealed []`；四条新行全 `verified true/sealed true/PASS/violations []`。证明后续反证看到的一切失败都不是读取姿势造成的。

**7.2 R-A 单字节篡改**（e6-04）：副本里给 OFFLINE-001 新 bundle 的一条 `checks/*.log` 追加 1 字节（632→633）：
- `evidence verify` 翻为 `rc=12`、`"status": "invalid", "verified": false`，violation 点名 `ARTIFACT_DIGEST_MISMATCH:checks/test_an_unknown_placeholder_is_rejected_rather_than_emptied.log`；
- `rejudge_evidence.py` 翻为 `rc=2` 且 reason 从「不记输入」换成「`the bundle does not hold up, so there is nothing to re-judge: ARTIFACT_DIGEST_MISMATCH:…`」；
- 副本 `report_promotion` 的 `unverified` 恰好点名 `46f88ff6…`；
- 把那一字节还原（633→632）后 `verify` 回到 `rc=0 / verified true`。
非空转性：同一命令在 P 里全绿，只改一字节即红，且还原即复绿。

**7.3 R-E 材料缺失**（e6-04）：另一副本删掉四个新 bundle 目录（台账不动）——`report_promotion` 的 `sealed_without_bundle`（main `759125f` 起的字段）精确点名这 4 条 SEALED seq-2 行（`ADMIT-080 8ffed6f1… / OFFLINE-001 46f88ff6… / OFFLINE-040 e9ee19ab… / OFFLINE-050 8af1ad70…`），证明新行是「账上有封、卷里有字节」的活记录。附注如实：该切片里 overall blocks 出现 `CASE_VERSION_MISMATCH`，是切片缺 `kin/` 卷树的读数伪影；完整卷读数（e6-01/e6-03）里从未出现，完整卷上剩余阻断只有 `REQUIRED_CASE_NOT_REGISTERED`（overall）与 W30 的 `NO_MANDATORY_CASES`。

**7.4 修前镜像反证**（e6-06，`minekin-runner-before:local`，完全不挂卷）：同一 run 命令 `run_rc=1`、`result FAIL`，五条 check 全 `exit 1`，detail 逐条 `/opt/minekin/bin/python3: No module named pytest`；该镜像 `/opt/minekin` site-packages 里 pytest spec 为 `None`。独立复现了 H1a 修前/修后断言，也说明本卡新 bundle 的 PASS 依赖钉住层而非镜像名。

## 8. 卷计数前后（基线 e6-01 vs 封存后读数 e6-03/e6-04，均只读）

| 量 | 前 | 后 |
|---|---|---|
| attempt 台账行 | 65 | 69（+4，全为四 case 的 seq 2 SEALED；65 条旧行原样在位，逐 case 行对见 e6-03 log） |
| `repo-evidence/` 目录 | 9 | 13（+4 个新 bundle） |
| `report_promotion` bundle count | 101 | 105 |
| `from_another_build` | 61 | 61（未变） |
| `sealed_without_bundle`（完整卷） | `[]` | `[]` |
| `unverified` / `unsealed` / `unreadable` | `[]` | `[]` |
| 9 个旧 bundle 目录指纹（path+逐文件 sha256 的目录级 digest 与总字节） | — | 逐条与基线完全相同（e6-01 vs e6-03 指纹表，9 对 digest+size 全等） |
| gate payload sha256（`work_packages`+`overall`，sort_keys） | `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da` | 同一字符串，逐字符相同 |
| 四 case 的 mandatory 状态 | false（report 的 `non_mandatory` 名单） | false（不变，未提升） |

## 9. 未测与阻断

- 本卡不触碰、也不验证：`kin/` 13 个 run bundle 家族（卷内 ~19 GB，只按指纹证明未动）；宿主面/集成面 case；真实 Minecraft/JVM 启动。
- 阻断不变且本卡不改变：W30 `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED`（OFFLINE-060…100 未注册）、W40 `REQUIRED_CASE_NOT_REGISTERED`（ADMIT-010/020/030/050/090 未注册）；`overall.promotable false`。四 case 判据材料中登记的 registry 缺口属主控另卡范围，本卡只引用不修复。
- `renderer_display` 仍为 `unmeasured`（本卡无 GUI 探针职责）。
- bundle 内不存时钟字段：先后秩序由台账 `sequence + supersedes_run_id`（append-only）与文件 mtime 佐证，非 bundle 内生证据。

## 10. 本卡不声称

不声称 Minekin 已完成；不声称任何门禁点亮（W30/W40/overall 的 promotable 前后都为 false，gate 摘要逐字符未变）；不声称修改过任何判据、registry 或产品代码；不声称旧 seq-1 bundle 是错的——它们的字节原封，只是台账上被 seq-2 行接续（supersedes）。本卡声称的只有：这四个 case 的检查与封存发生在同一个受控镜像内，四读一致，反证非空转，规范卷其余字节前后全等。
