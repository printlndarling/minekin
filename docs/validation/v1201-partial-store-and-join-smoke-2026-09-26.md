# V1201-PARTIAL-STORE-AND-JOIN-SMOKE-001 — 1.20.1 部分装机复验与当前 build 本地入服观察

- Lane：V（1.20.1 游戏内调试），分支 `codex/minekin-v1201-validation`，工作树 `minekin-wt-v1201-validation`。
- 被验 build：分支基线 `e6f3e7a`（"Merge origin/main (lane_next activation) into E's B2 checkpoint"）；`origin/main` = `300ed07`。产品源码全程**只读**挂载（`/src:ro`），未改 `src/**`、`test-orchestrator/**`、`tools/**`、case/registry。
- 资源隔离（本 lane 私有）：Docker 数据卷 `minekin-v1201-smoke-v1`、Kin `kin-v1smoke`、日志/中间件目录宿主 `.tmp/v1201-validation`；服务器为**本 lane 直接启动**的 offline 1.20.1（`127.0.0.1:25566`，`online-mode=false`，vanilla 默认 `enable-status=true`）。
- 未触碰：默认规范卷 `minekin-runner-data`、B2 文件、case/registry、用户远程服（V08 仍 `BLOCKED_DECISION`，本卡不连）。
- 复现脚本（本目录）：`scripts/partial_store_repro.py`、`scripts/join_smoke.sh`。

结论摘要：
- **A 部分装机复验：通过。** 下载被真实硬中断后，已提交 blob 能被逐件复验并按内容地址复用；被切断的 `.staging` 残件从不被当作可用内容；同时暴露两条可复现缺陷（孤儿 `.staging` 不回收、已损坏 blob 无法自愈）。
- **B 入服 smoke：status 与 auto-select 在真实服务器上不阻塞；同 run 的完整 JOIN/PLAYABLE/退出为 `BLOCKED_HARNESS`。** 已按真实失败材料记录，不搬旧 PASS、不手改判官、不冒充 V08 远程入服。

---

## A. 部分装机：下载中断后已存 blob 的逐件复验（补 A2 F4 未测项）

方法：驱动**产品自带**的 launcher 代码（`build_launch_plan`→`plan_fetch_set`→`ArtifactFetcher`/`ArtifactStore`），对 reviewed 1.20.1 recipe `bundle-candidate-1.20.1.json`（离线可解析，`plan_sha256=83299ad5…`，全集 **3639 件 / 738,432,269 字节**）取前 40 件真实联网抓取，用看门狗 `os._exit` 在 6s 硬杀，模拟真实下载中断；再在同一持久卷上复跑 resume。每步都是新容器、同卷。

### A.1 中断现场（interrupt 40 / 6s）
```
committed_blobs = 9                 # blobs/sha1 下已完成并通过 sha1+size 校验的件
staging_leftovers = {               # .staging/<uuid>/payload.part 半成品
  "a64adc...": 6291456,             # 6.0 MiB，写到一半被杀
  "9ae33b...": 6291456,             # 6.0 MiB
  "7cfbdc...": 0                    # 0 B，尚未开始写
}
quarantine = []                     # 无：不是摘要不符，是进程被硬杀
first_n_verified_present = 9 ; first_n_missing = 31
```
观察：被硬杀留下的半截 payload 只在 `.staging/<uuid>/payload.part`，**没有**进入 `blobs/sha1`，因此 `ArtifactStore.verify`（只读 `blobs/`）看不到它们，也就无从被误用。

### A.2 续跑复验（resume 40）
```
complete = true
reused   = 9                        # 之前已提交且校验通过的件，逐件复验命中→复用，不再下载
installed= 31                       # 之前缺失/被中断的件（含 3 个 .staging 残件对应的件）重新抓取
failures = []
pre_fetch_map = {verified: 9, missing: 31, present-but-failed: 0}
reuse_invariant_holds = true        # “已验证集合 ⊆ 复用集合，且与重装集合不相交”
committed_after = 40
```
判定：**逐件复验成立。** 恢复只重新抓取真正缺失者，对已完成件走 `verify` 命中即 `reused=True`（`fetch.py:209-228`），不重复抓取、不把 `.staging` 残件当内容——这正是 A2 F4 未测问题的答案。

### A.3 缺陷一（可复现）：中断残留 `.staging` 不被回收
`resume` 后 `staging_after` 仍列出**同样三个**孤儿目录（合计约 12 MiB）。原因：`ArtifactStore.install` 的 `finally` 只清理**本次自己创建**的事务目录（`artifacts.py:180-182`），历史被硬杀留下的 `.staging/<uuid>` 无人认领。反复中断会累积孤儿半成品。影响：磁盘增长/装机体积失真；不影响正确性。**交 H**：runner/装机清理策略是否负责回收孤儿 `.staging`。

### A.4 缺陷二（可复现，负向反证）：present-but-corrupt blob 无法自愈
对已提交件 `com.ibm.icu:icu4j:71.1` 截断 512 字节后：
```
verify_after_corrupt = REJECTED ("stored artifact failed size or digest verification")
false_reuse          = false          # 好：损坏件绝不被当作有效复用
present_but_corrupt_self_heals = false # 抓取器无法自愈
  outcome_with_blob_present = { complete: false, installed: 0, reused: 0,
     failures:[{category: SUPPLY_CHAIN, reason:"stored artifact failed size or digest verification"}] }
# 删除损坏件后：
recovers_once_removed = true           # installed:1 reused:0 complete:true
third_pass_reuses     = true           # 再跑一次命中复用，幂等
```
根因：`ArtifactStore.install` 在 `target.exists()` 时**提前返回 `self.verify(artifact)`**（`artifacts.py:153-154`），而损坏件仍在原位，于是 `verify` 再次抛错→`_attempt` 直接把该错当失败返回，不会重下。即：一个“存在但已损坏”的 blob 会让整批 `provision_bundle` 判为 `incomplete`（`auto_session.py:217-224` 直接 `PROVISION_*` 拒启），需人工删件才能恢复。**交 H/E**：下载器应在 `verify` 失败时对既有目标做“删除后重取”，而非仅信任 `target.exists()`。

---

## B. 当前 build 本地 smoke：status → 自动选择 → JOIN/PLAYABLE → 安全退出

单容器内：本 lane 直接启动 offline 1.20.1 服务器（绕过 `run_controlled_server.py`，因其硬写 `enable-status=false`=G2；vanilla 默认为 true），然后按产品 CLI 逐段驱动。

### B.1 STATUS（真实观测，当前 build，无阻塞）
`python -m minekin_core server probe --server-profile controlled-offline-server-1.20.1.json`：
```
{"command":"server probe","endpoint":"127.0.0.1:25566","outcome":"OBSERVED",
 "profile_id":"p0-controlled-offline-loopback-1201","protocol":763,"version_text":"1.20.1",
 "received_bytes":112,"refusal_reasons":[],
 "resolution_chain":["saved:127.0.0.1:25566","as-saved:127.0.0.1:25566","payload:112"]}
```
服务器 `Done (27.181s)` 首启；probe 5s 内 OBSERVED。**这同时证明 G2 不是固有限制**，而是 harness 写入 `enable-status=false` 所致——只要以本 lane 自有、状态可读的受控服务器，status 步骤即可成立。

### B.2 自动选择 + 摘要门（真实，通过）
`python -m minekin_core session start --auto-bundle reviewed-tested-bundles.json --server-profile <1.20.1> `（**不给 `--max-bytes`**）：
```
{"category":"SUPPLY_CHAIN","component":"cli.auto_session",
 "message":"3599 of 3639 artifacts are missing and would cost 660392160 bytes;
            pass --max-bytes deliberately rather than let a session start download them
            by accident [BUDGET_UNDECLARED]",
 "operation":"session start --auto-bundle"}   rc=11
```
读法：该命令在 `_provision` **之前**必须依次通过 `probe→resolve（自动选择）→require_reviewed_plan（tested 状态 + recipe/plan/bridge 三摘要）→require_agreeing_facts（观测 1.20.1/763 与 entry/recipe 相符）`。它确实到达并给出了 `3599/3639、660,392,160 字节` 的取件集读数，与 `bundle install --bundle-id 1.20.1-linux-x86_64-offline-java21 --dry-run` 完全一致：
```
{"artifacts":3639,"missing":3599,"missing_bytes":660392160,
 "plan_sha256":"83299ad5…","store":"/data/kin/kin-v1smoke/run/artifact-store","status":"planned"}
```
（`missing=3599` 恰为全集 3639 减去 A 段已提交的 40 件。）→ **status→自动选择→摘要门在真实当前 build + 真实服务器上成立**，并按预算安全属性拒绝“无意下载 660 MB”。

### B.3 完整 JOIN/PLAYABLE/安全退出 = `BLOCKED_HARNESS`
纯 V-lane 无法在同 run 内完成并封证，三条各自独立的可复现阻断：
1. **bridge 不可联网获取（关键）**：1.20.1 recipe 的 `minekin-bridge` 记录 `source="workspace:bridge-1201"`，`fetched_mod_artifact(bridge) → None`（fabric-api 为 https 可取，bridge 不是）。故 `provision_bundle` 的取件集**不含 bridge**，装机后 store 内无 bridge，客户端 `launch` 会因缺 bridge 拒启。bridge 需由构建产物安装（gradle / jdk-21），属 H/E/产品面，V 只读不改。
2. **G1（封证入口）**：`domain.sh` 仅扫 `--profile`/`--server-profile`，不识别 `--auto-bundle`，无法对自动路径同 run 封证（见 memory「Sealing an --auto-bundle run」）。
3. **G2（探测失明）**：harness 的 `run_controlled_server.py` 硬写 `enable-status=false`，其自动探测路径看不到自建服务器状态；本卡靠直接起 jar 绕过以证明 status 可行，但**harness 通道内**仍盲。

因此本轮**不**伪造 JOIN/PLAYABLE、不搬 A1 旧 bundle、不称其为 V08 远程入服。

### B.4 四读（verify / re-judge / replay×2 / report_promotion）
**未执行**——因为不存在可封的当前 build 同 run bundle（B.3-2 G1）。四读需要一个 sealed run-id 作输入；本轮该 run 从未到达 launch/退出、也无 `evidence/<run-id>`，故四读按“无对象可读”如实记 `N/A / 未测`。若 H 解掉 G1（让 `domain.sh`/手动 `seal_run_evidence.py` 能吃 `--auto-bundle`）并由 E 安装 bridge-1201，则同 run 的四读应在其产物上执行，不在本 lane 造。

---

## 记录：run / attempt / build / 失败分类 / 未测 / 交办

- build：`e6f3e7a`（分支基线，产品码只读）。
- run/attempt：无 registry 级 run-id、无 attempt 序号——本 lane 不写 registry、且自动路径未封证（G1）。容器级证据为 `.tmp/v1201-validation` 与卷 `minekin-v1201-smoke-v1:/data/v1-*`（服务器日志、probe 输出、partial_store 状态）。
- 失败分类（均为真跑所得，非断言）：
  - `SUPPLY_CHAIN/BUDGET_UNDECLARED`（B.2，预期安全拒绝）。
  - `SUPPLY_CHAIN/digest verification` 于“存在但损坏”的 blob（A.4，缺陷二）。
  - `BLOCKED_HARNESS`（B.3：bridge 不可取 + G1 封证 + G2 探测）。
- 未测（本 lane 明确不覆盖）：真实 JOIN→PLAYABLE→安全退出端到端；四读；同 run 封证；1.20.1 全量 3639 件装机（仅需 40 件即足以复验，全量为 660 MB/约 25 min 的联网抓取，本卡不需要）。
- 交 H（runner/launcher）：
  - H-1 让自动路径同 run 可探测+可封证（解 G1）；
  - H-2 让 bridge 成为可安装产物或提供安装步骤（B.3-1）；
  - H-3 下载器对既有但校验失败的 blob 应“删后重取”（A.4）；
  - H-4 回收孤儿 `.staging` 半成品（A.3）；
  - H-5 `run_controlled_server.py` 的 `enable-status=false` 与自动探测冲突的取舍（G2）。
- 交 E/M（规范卷/取证）：bridge-1201 的构建与 provenance；本卡观察是否值得进规范卷引用由 E/M 独立复核决定，V 不自评、不搬旧 PASS。

## 复现命令（本 lane，只读产品码，私有卷）

部分装机：
```bash
docker run --rm -v <worktree>:/src:ro -v <scratch>:/scratch \
  -v minekin-v1201-smoke-v1:/data -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  --entrypoint python minekin-runner:local /src/docs/validation/scripts/partial_store_repro.py \
  interrupt 40 6
# 依次：snapshot 40 → resume 40 → corrupt-coord 5
```
入服 smoke：
```bash
docker run --rm -v <worktree>:/src:ro -v <mc-1.20.1-server.jar>:/server/server.jar:ro \
  -v minekin-v1201-smoke-v1:/data -e MINEKIN_KIN_ID=kin-v1smoke -e STAGE=gate \
  -e JAR=/server/server.jar --entrypoint bash minekin-runner:local \
  /src/docs/validation/scripts/join_smoke.sh
```
