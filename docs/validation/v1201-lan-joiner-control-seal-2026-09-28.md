# E7 `V1201-LAN-JOINER-CONTROL-SEAL-001` — 1.20.1 加入者控制真跑封证（规范卷）

- **卡片**：card #49 `V1201-LAN-JOINER-CONTROL-SEAL-001`（E7）；允许面 / 验收逐字取 `docs/v1201-lan-control-next-2026-09-27.md` §2.63（判据字节来源）与 §2.64（两条硬前置）。
- **Lane / 分支**：`codex/minekin-v1201-lan-joiner-control-seal`（E 证据 lane），基线 `82e199c`（起跑即干净，未改任何产品码）。
- **本卡状态**：**DELIVERED — 四条判据在同一次「加入者控制 + 专服形状」真跑里全部出 `failures`，封在规范卷 `minekin-runner-data` 上的一枚 bundle**。
  run `a224f6c3fa0f45f2ae4c922277220fcf`、bundle `5086ee42659033a0db15c180f0b0e051961718b5d64bf3ac750ceda5f01464f6`、
  `evidence_directory` `/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf`、attempt 序列 **1**（`case_id V1201-LAN-JOINER-CONTROL-CASE-001`、`case_version 1e31f0003b4e30e0…`）、
  判据 **4/4 held**（seal `result: PASS`、`failures: []`）；四读齐（`evidence verify` `verified: true` / `violations: []` / 14 artifacts、`report_promotion rc=1` 属预期阻塞形状）。
- **零改动门**：`V1201-LAN-JOINER-CONTROL-CASE-001` 是 `mandatory: false` 的已登记 case；封前后 trunk 载荷 sha256 逐字相同（`cfa0f118…`），动的只是 `evidence` 普查计数（见 §5）。registry / 判据 / case 文件 / 封存 schema / `domain.sh` 一字未改。

---

## 1. 目标与配方（同 run：加入者控制 case + 专服形状）

同一容器、同一 run：campaign 路径（`MINEKIN_DOMAIN_CASE=v1201-lan-joiner-control-case-001` + `MINEKIN_DOMAIN_CASE_ON=joiner`）叠加专服形状（本次起跑自己的受控 1.20.1 服务端，带 `--server-profile`）。四条判据（`the_bridge_carried_the_input_out`、`the_server_saw_the_kin_move`、`move_input_was_leased`、`the_probed_player_is_this_run_s_kin`）在同一枚 seal JSON 的 `failures` 里一起清零。

十四枚配方旋钮逐字按 brief 给：`MINEKIN_USERNAME=Kin`、`MINEKIN_KIN_ID=kin-e7-host-0928`、`MINEKIN_DOMAIN_JOIN=kin-e7-join-0928`、`MINEKIN_DOMAIN_JOIN_USERNAME=Kin2`、`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`、`MINEKIN_DOMAIN_PROBE=Kin2`、`MINEKIN_DOMAIN_PROBE_SECONDS=4`、`MINEKIN_DOMAIN_JOIN_LOOK_YAW=45`、`MINEKIN_DOMAIN_JOIN_LOOK_PITCH=-20`、`MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=2`、`MINEKIN_DOMAIN_CASE=v1201-lan-joiner-control-case-001`、`MINEKIN_DOMAIN_CASE_ON=joiner`、`MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=1`、`MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1`。运行时长（非判据旋钮）沿用 case2 已验形状：`MINEKIN_DOMAIN_SECONDS=420`、`SOAK_SECONDS=150`、`SOAK_INTERVAL=20`。

禁用面（容器自核，逐字在 `/out/campaign/00-header.txt` 与 `00-inspect-env.json`）：`MINEKIN_DOMAIN_PROBE_SECOND` 完全未设（探针名恰一个 `Kin2`）；`MINEKIN_DOMAIN_OPEN_LAN`、`BLACK_HOLE`、`NO_SERVER`、`NOT_WHITELISTED`、`REFUSE_FIRST_SNAPSHOT` 一次都不出现。

## 2. 与 h66 参照的强制差异（逐条兑现）

1. **卷**：`-v minekin-runner-data:/data`（读写），h66 的 `minekin-h66-live` 不出现。本窗口是该规范卷唯一写者；所有写都是**追加**（一枚新 Kin 根、一个新 server-run、一枚新 bundle），既有内容一律不动。收工差值见 §5。
2. **删种子卷**：h66 的 `-v minekin-v4-join:/ro:ro` 与任何 `cp -a` 种子 **Kin 根** 全部删除。两枚 Kin 根都是本卷从未见过的名字（起跑普查 16 枚里没有 `kin-e7-host-0928`/`kin-e7-join-0928`），host 根由 `minekin_core init` 自建、joiner 根由 `domain.sh:1222` 那一支自建。仅 host 根的 `run/artifact-store` 从既有 `kin-04` 的**内容寻址 store** 只读复制一份，好让 `domain.sh:1241-1248` 的 joiner store `cp -a` 有源；这不复制任何身份、不动 `kin-04` 一字。
3. **加 `MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1`**：历史上 campaign 形状的每一支都缺它，正是判据 (a) `PROBE_ATTRIBUTION_NOT_RECORDED` 的根因。
4. **探针面**：`--profile` / `--server-profile` 两枚参数照 brief；禁用旋钮如上，一律不出现。
5. **桥 jar**：campaign 需 `bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`。先查各 lane 树，取到 sha256 与 pin `e50d61c2…006f` 逐字相等、`1310604` 字节的一件，复制进本工作树（`.gitignore` 覆盖 `build/`），**未跑 gradle**；只读挂进 `/src` 后容器内复量同值。
6. **头部打印**：`domain.sh`（挂进 `/src`）的 sha256、桥 jar、服务端 jar、两枚 case 侧 fixture、容器 `docker inspect` 全量 env（含 `MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1`）、起跑前 `/data/kin` 根清单、两枚新根 `kin.sqlite3` 与身份行自检——全部落到 `/out/campaign/{00-header.txt,10-preflight.txt}`。

## 3. 三条起跑前验收（量出来的，不是说的小）

**验收①：两枚新根是本卷从未见过的名字。** 起跑前只读普查 `/data/kin` 共 16 枚（`kin-01 kin-02 kin-04 kin-auto-inst-*×2 kin-e6-ctr kin-e6-j020 kin-e-aba kin-e-rr-*×5 kin-v07-*×3`），`kin-e7-host-0928`/`kin-e7-join-0928` 均缺席；容器头两行逐字 `E7: host root present at start? no` / `E7: joiner root present at start? no`（`/out/campaign/00-header.txt`）。

**验收②：新 host 根的 store 满足 1.20.1 计划。** `minekin_core init` 建 host 根后，从 `kin-04` 的既有 store 复制 `run/artifact-store`（复量 7565 blob）。以现行 `require_store_complete` 直接量：`launchable = True`、`plan artifacts = 3638`、`verified = 3638`、`missing = 0`，`REQUIRE_STORE_COMPLETE: PASS`（规范卷只读复核）。产品侧同 run 的 host `session start` 过了这道门（客户端真起、run 记录在场），互为印证。

**验收③：两枚最终根的目录名 == `kin_identity.kin_id`（§2.64 硬前置）。** 把 `kin.sqlite3`（连同 `-wal`/`-shm`）复制进 `/tmp` tmpfs 再查 `kin_identity WHERE singleton = 1`（WAL 账本不能 `:ro` 打开，故先拷）：

- host：`dir_name=kin-e7-host-0928` rows=`[('kin-e7-host-0928', 'kin-e7-host-0928-r1', 'Kin')]`
- join：`dir_name=kin-e7-join-0928` rows=`[('kin-e7-join-0928', 'kin-e7-join-0928-r1', 'Kin2')]`

两枚都 `kin_id == 目录名`；joiner 根由 `domain.sh:1222` 自建、身份行由 `init.py` 按 `f"{kin_id}-r1"` 写就，故 `LEDGER_UNREADABLE`（case2 私卷旧身份残留的那条残余）在此形状天然不出现。任一行不等即 §2.64 ③ 的具名 fallback（编排缺陷，非本卡职责），会当场 STOP 并报 M——实测无此情形。

## 4. 真跑读数与封存面

### 4.1 同 run 阶段（逐字在 `/out/campaign/20-domain-stderr.log`）

`server run directory /data/server-runs/run-186` → `server ready`；`the controlled server reports enable-status=false`；`the joining Kin kin-e7-join-0928 was created as Kin2`；`the joining client dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-186/server.properties`；`the world heard Kin2 arrive`；`Kin2 admitted its first snapshot of that world`；`bridge reporting CONNECTION_PHASE_JOIN_SEEN for generation 1`；`bridge knows of 27 entity candidate(s) 1 tick(s) after joining`；`this run is 285bbb91d0c444d08e50fb930a677d9c`（host run id）；soak 150s/20s；`the joining client ended with {'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 27}`。全程只连本次受控 runner 在容器 loopback 起的 `127.0.0.1:25566`；`.tmp/local-test-server.txt` 未被打开/读取/打印，本文不出现任何远程 IP:端口。

### 4.2 seal JSON（逐字）

`{"artifacts": [...14 项...], "attempt_sequence": 1, "bundle_digest": "5086ee42659033a0db15c180f0b0e051961718b5d64bf3ac750ceda5f01464f6", "case_id": "V1201-LAN-JOINER-CONTROL-CASE-001", "case_version": "1e31f0003b4e30e06506e086616335db73ec975b406874d219033f151b3f812a", "command": "seal run evidence", "evidence_directory": "/data/kin/kin-e7-join-0928/run/evidence/a224f6c3fa0f45f2ae4c922277220fcf", "failures": [], "result": "PASS", "run_id": "a224f6c3fa0f45f2ae4c922277220fcf", "schema_version": 1, "status": "sealed"}`

判据逐条（`failures: []` ⇒ 四条一起出清）：

| 判据 | 本次量到的字节 | 结论 |
|---|---|
| `the_probed_player_is_this_run_s_kin` | `asserter-inputs.json` 的 `probed_players` == `["Kin2"]`（单名，正是本 run 的加入者 Kin） | **held**（SEAL_PROBED_PLAYERS=1 消解 `PROBE_ATTRIBUTION_NOT_RECORDED`） |
| `the_server_saw_the_kin_move` | 服务端日志 `Kin2` 位姿从 `[4.5d,-60.0d,-6.5d]` 移到 `[-1.447917…d,-60.0d,-0.336223…d]`，位移 ≈ 8.6 格 ≥ 2.0 | **held** |
| `move_input_was_leased` | 新根 `kin-e7-join-0928` 账本可直读，`kin_id` 由 `MINEKIN_KIN_ID` 选定（`domain.sh:1931-1941`） | **held**（无 `LEDGER_UNREADABLE`） |
| `the_bridge_carried_the_input_out` | run 文档 `run.actions_applied` / `actions_refused` 在场，Bridge 把入站输入带出去 | **held** |

### 4.3 `evidence verify`（逐字）

`{"artifacts": 14, "bundle_digest": "5086ee42…64f6", "command": "evidence verify", "evidence_directory": "/data/kin/kin-e7-join-0928/run/evidence/a224f6c3…", "result": "PASS", "run_id": "a224f6c3fa0f45f2ae4c922277220fcf", "schema_version": 1, "sealed": true, "status": "verified", "verified": true, "violations": []}`

### 4.4 bundle 面（只读复取；全量在 `/out/campaign/33-bundle-faces.txt`）

- **`manifest.json` world 三格**：`kind = dedicated`、`seed_or_snapshot_id = minekin-p0-controlled`、`server_config_digest = 77a19c94c4467231e0431891939b09a94e3acd72c8e25edf3d28b24fb66f4df8`。
- **`manifest.json` artifacts（键为 `path`）**：`asserter-inputs.json`（191）、`bridge-trace.jsonl`（16832）、`client/latest.log`（162）、`client/server-resource-packs.json`（102）、`client/stderr.log`（0）、`client/stdout.log`（35719）、`orchestrator-trace.json`（1036）、`run-document.json`（1861）、`server/server.log`（18049）、`server/server.properties`（1383）、`server/usercache.json`（204）、`soak-samples.txt`（348）、`soak-summary.json`（171）、`trusted/server-profile.json`（647）。
- **`server/server.log` 加入者相关行**：`78: Kin joined the game`；`79: Kin2[/127.0.0.1:44472] logged in with entity id 2 at (4.5, -60.0, -6.5)`；`80: Kin2 joined the game`；`81: Kin2 has the following entity data: [4.5d, -60.0d, -6.5d]`；后续 `[0.0f, 0.0f]`、`[45.0f, -20.0f]`（朝向）与逐 4 秒的位姿行（`[3.762…, -60.0d, -5.550…]`、`[-1.447…, -60.0d, -0.336…]`）。
- **`trusted/server-profile.json`**：`auth_mode offline`、`host 127.0.0.1`、`port 25566`、`profile_id p0-controlled-offline-loopback-1201`、`resource_pack_policy deny`、`revision 77a19c94…`（与 world 的 `server_config_digest` 同值）、`schema_version 2`、`allowed_versions ["1.20.1"]`（`explicit_allowlist`）、`target_authorization.basis` 具名「仅本 harness 自己的 127.0.0.1 端点，不点名/不承认任何远程地址」。
- **`asserter-inputs.json` `probed_players`**：`["Kin2"]`。

## 5. 门表与 gate 载荷（按 `ci.yml` 自身 `- run:` 步逐条，rc 现读现引）

本卡不改产品码，故门表逐字等 M 的 POST 基线；唯一位移是 `ruff format --check` 的文件数 **375 → 376**（本记录新增一枚 `docs/validation/*.md`，ruff format 会数 `.md`）。宿主半用 `uv`（host uv 0.11.21，锁定 `.venv` 带 dev extras），容器半用 `minekin-runner:local` 的 CPython 3.12。

| 步（ci.yml 名） | rc | 逐字尾行 |
|---|---|---|
| `bash -n domain.sh` | 0 | （空） |
| `bash -n run.sh` | 0 | （空） |
| `uv sync --locked --dev` | 0 | `Checked 18 packages` 系 |
| `pytest contract/test_runner_scripts.py`（host） | 0 | `124 passed in 26.15s` |
| `ruff check .` | 0 | `All checks passed!` |
| `ruff format --check .` | 0 | `376 files already formatted`（基线 375，+本 `.md`） |
| `pyright` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest -q`（全量，host） | 0 | `2712 passed, 2 skipped in 297.87s` |
| `check_boundaries.py` | 0 | `Minekin package dependency boundaries: OK` |
| `check_case_assertions.py` | 0 | `Case assertion implementations: OK (151 registered)` |
| `verify_fixture_digests.py` | 0 | `W00 schema and fixture digests: OK` |
| `check_workflow_pins.py` | 0 | `Workflow pins: OK` |
| `uv build --wheel` | 0 | `Successfully built dist\minekin_core-0.0.0-py3-none-any.whl` |
| `check_wheel_boundary.py` | 0 | `Wheel oracle boundary: OK` |
| `minekin --help` | 0 | `-h, --help show this help message and exit` |
| `git diff --check`（host git） | 0 | （空） |
| `pytest contract`（容器，CPython 3.12） | 0 | `124 passed in 1.55s` |
| 契约单元 `test_the_joiner_control_driver_keeps_its_bounds_and_reaches_one_line_only`（容器） | 0 | `1 passed in 0.29s` |
| `report_promotion.py --data-root /data`（容器，规范卷 `:ro`） | 1 | 封前 `size=103921` / 封后 `size=104680`（`rc=1` 属预期阻塞形状） |

**gate 载荷两次跑（跑在封存前 / 后，规范卷只读）**：

- 封前：`gate_payload_sha256 = cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`，`bytes=103920`（`.tmp/e7/out/gate-payload-pre.digest.txt` 首行）/ 报告文件 `103921` B（`wc -c`）。
- 封后：**同值 `cfa0f118…63afd6`**，`bytes=104679`（`.tmp/e7/out/gate-payload-post.digest.txt` 首行）/ 报告文件 `104680` B（`wc -c`）—— 增量 **+759**（`bytes=` 与 `wc -c` 两种取法都得 +759）。

**哪个字段动了（不假设「恒静」）**：trunk 载荷（`work_packages` + `overall`）逐字未变，故 sha256 不变；动的仅是顶层 `evidence` 普查计数——`bundles 113 → 114`、`attempts 77 → 78`、`count 113 → 114`，新增叶子恰是本次的 `case_id V1201-LAN-JOINER-CONTROL-CASE-001`、`case_version 1e31f000…`、`run_id a224f6c3…`。`sealed_without_bundle/unsealed/unreadable/unverified` 前后皆 `0`。原因是 `V1201-LAN-JOINER-CONTROL-CASE-001` 是 `mandatory: false`、不入 promotable/required trunk，本封只往普查里追加一枚 bundle，**不点亮任何门**。

**卷写足迹（追加，一字未删）**：`server-runs 185 → 186`（+`run-186`）、规范卷 evidence 目录 `100 → 101`（+本 bundle）、Kin 根 `16 → 18`（+`kin-e7-host-0928`、+`kin-e7-join-0928`，均自建新名）；既有 bundle / 旧 attempt / 旧 FAIL 一律原样在场，未被改动、删除或重封。

## 6. 四态声明

**DELIVERED。** 目标 case `V1201-LAN-JOINER-CONTROL-CASE-001` 的四条判据在同一次「加入者控制 + 专服形状」真跑里一起从 `failures` 出清（`result: PASS`、`failures: []`、`evidence verify verified: true / violations: []`），封在规范卷 `minekin-runner-data` 上、由 `kin-e7-join-0928`（本 run 自建的 joiner 根）持有，bundle `5086ee42…64f6`、run `a224f6c3…`、attempt 序列 1。三条起跑前验收（新名缺席、store 满足 1.20.1 计划 3638/3638、两最终根目录名==`kin_id`）皆为量出来的实测。本卡不改产品码、不动 registry / 判据 / 封存 schema；门表逐字等 M 的 POST 基线，唯 `ruff format --check` 因本记录一枚 `.md` 由 375 变 376。

## 7. 被驱动字节 / 输入落位（可复核）

- 起跑 SHA `82e199ce94dfed45054c607dba53983fe37c9080`；远端 `main`（`git ls-remote origin`）`cf6d2fc5accc1b7bfbbf55c6d02d1e7ff3000002`。
- `test-orchestrator/runner/domain.sh` sha256 `cbec5b85142d2168afcb46551d879dcd23159e62c89f21e422c7a69221ab8a82`（3292 行；起跑前后逐字同值，见 `00-header.txt`）。
- 桥 jar `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f` / `1310604` 字节（sha256 逐字等于 pin `e50d61c2…006f`；未跑 gradle）。
- 服务端 jar sha256 `3af73a9dc5a102e38147946360dd27d4d70bae7055bf91cf2151cd5d121b79e0`、sha1 `84194a2f286ef7c14ed7ce0090dba59902951553` / `47791053` 字节（`run_controlled_server.py` 的 1.20.1 具名 pin；只读挂 `/server/server.jar:ro`）。
- case 侧 fixture：`bundle-candidate-1.20.1.json` sha256 `709a889977b10857ae623d83aca640321493224ba54e594ad1d09bd22aaef185`；`controlled-offline-server-1.20.1.json` sha256 `3864eddae899c77a1f2c522fd02c3618b6601efd97f9e2fe8c4aff2354303aa2`；case 文件 `v1201-lan-joiner-control-case-001.json` sha256 `f4b94e03dc48cab4c6a2759281e887679856ba31c7ed500b54a4444cb282d8ff`。
- 驱动脚本（`.tmp/e7/`，gitignore，不入库）：`e7-run.sh`（宿主启动器）、`e7-drive.sh`（容器驱动）、`gate-payload.sh` + `trunk_digest.py`（gate 载荷只读跑）。

## 8. 我没能做到的（不含糊）

1. **驱动脚本 readouts 阶段曾在容器内崩了一次**（`e7-drive.sh` 旧版第 223 行附近一处 bash 语法错，`syntax error near unexpected token '('`）——**发生在 `domain.sh` 已完成并封存之后**，故 seal/verify 落盘未受影响；`/tmp/domain-seal.json` 随容器消失，但 seal JSON 与 `evidence verify` 已由 `domain.sh` 原样回打到 `20-domain-stderr.log`，bundle 也已封在规范卷，我据此**只读复取**全部面（§4.4，`33-bundle-faces.txt`）。脚本该处已在盘上修正（当前 `bash -n` 通过）。
2. **`e7-drive.sh` 内的 `require_store_complete` 预检曾误报**（旧版把 `dict`/`str` 传给了 `build_launch_plan`/`ArtifactStore`，报 `'dict' object has no attribute 'resolve'`）——**这是我脚手架调用签名不对，不是卷/store 缺陷**；`exit 4` 落在 `| tee` 子 shell 里没截断长跑，真 run 的 host `session start` 过了这道门并一路封成。正确读数以 §3 验收② 的只读复核（3638/3638、`REQUIRE_STORE_COMPLETE: PASS`）为准；脚本调用签名亦已修正。
3. 本次**未重跑整 campaign**（第 1、2 点都发生在封存之后或与我方脚手架调用有关，证据已完整且已封在规范卷，重跑会白占约 9–10 分钟引擎并追加无谓的卷足迹）。若 M 认为需要一份「readouts 阶段自身打印、不含脚手架崩」的洁净长跑，可择一安静窗口用已修正的 `e7-drive.sh` 以另一对全新根名重跑。
