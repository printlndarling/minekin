# 1.20.1 负向矩阵复判记录（V1201-LOCAL-NEGATIVE-MATRIX-001）

> 只读复判记录，2026-09-26，baseline `11538c4ba65390548fc78e637868556a49e0042c`（in-image python 3.12.3）。
> 范围：[版本契约 §跨卡必须保留的负向矩阵](version-auto-to-server-control-plan.md) 的九行，按执行计划 A2 卡面
> 收敛成六族，逐族量出**当前 build 可重跑的拒绝类别 + 原因码**，以及需要真跑的部分的 sealed 证据读数。
> 本记录**不改**产品代码、case 判据、registry 字节或任何已封存证据；它只做四件事：给出读数、区分"可重跑拒止"
> 与"真实 run 封证"、把每族未覆盖的组合登记成有边界的后续卡、明确本卡不声称什么。
> 全程在受控 runner 与 loopback / 容器自身接口上完成：**未连接任何远程服务器**，未使用私有目标地址。
> 所有地址都由脚本在容器内现取（`hostname -I`），文档不落任何基础设施地址。

## 0. 复现入口

统一模板（Windows 侧必须先 `export MSYS_NO_PATHCONV=1`，`docker exec` 同理）：

```bash
MSYS_NO_PATHCONV=1 docker run --rm --entrypoint /bin/bash \
  -v "$(cygpath -m "$PWD"):/src:ro" -v minekin-runner-data:/dataref:ro -v <本卡新建卷>:/data \
  -e MINEKIN_HOME=/data -w /src minekin-runner:local \
  -lc 'bash /src/.tmp/<脚本>'
```

八个 `.tmp/` 未跟踪脚本各自独立可重跑；卷是本次读数的原始材料存放处，**失败材料未被覆盖**：

| 脚本 | 卷（时间戳） | 量了什么 |
| --- | --- | --- |
| `v1201-negative-matrix.sh` | `minekin-v1201neg2` / `20260926T062430Z` | 真 1.20.1 服 + 自动入口 B1–B11 |
| `v1201-negative-status.sh` | `minekin-v1201neg5` / `20260926T062903Z` | 真实 socket 状态探测 18 行 + B12/B13 |
| `v1201-admission-rerun.sh` | `minekin-v1201neg4` | 显式 `--profile` 路径的准入五拒 + Bridge 钉住 |
| `v1201-negative-control.sh` | `minekin-v1201neg6` / `20260926T063050Z` | 干净空 store 的未改动作正对照 |
| `v1201-negative-reversal.sh` | `minekin-v1201neg7` / `20260926T063445Z` | B12/B13 的非空转反转对（R1/R2/R3） |
| `v1201-address-gate.sh` | `minekin-v1201neg8` / `20260926T063814Z` | 地址禁区/字面量门 A1–A6 |
| `v1201-boundary-address.sh` | `minekin-v1201neg10` / `20260926T064156Z` | 可达非 loopback 目标 X1/X2 |
| `v1201-boundary-stored.sh` | `minekin-v1201neg11` / `20260926T064554Z` | 满 store 下的门序 Y1/Y2 |

假状态端点：`.tmp/a2-hostile-status.py`（18 个具名帧形状，逐个 bind 连续 loopback 端口，并把每个端口的
`listening` 表与每次接受的连接（含发送字节 sha256）写进自己的 JSONL）和 `.tmp/a2-open-status.py`
（bind `0.0.0.0` 的单一良构 1.20.1 应答，记录接受的 peer）。传输层是产品自己的
`SocketStatusTransport`（`src/minekin_core/adapters/launcher/server_probe.py:151-199`），所以这些帧是**真 socket 读数**，
不是 monkeypatch。

## 1. 六族结论

| 族（契约行） | 当前 build 的实际读数 | 结论 |
| --- | --- | --- |
| F1 歧义协议 / 版本文本与协议号冲突（契约 :129,:130） | 18 行真实 socket 探测里 `neither_protocol_nor_name`→`MALFORMED`、`multi_version_proxy`→`AMBIGUOUS + MULTI_VERSION_PROXY`；自动入口对同两端点分别 `exit=17 / ADMISSION / NEEDS_PIN`，且 `forged_display_contradicts` 把原始观测写进消息（`'1.21.4' on protocol 763`）——见 §2、§3 | **成立**：既有机器读数，又有可重跑拒止和反转对 |
| F2 错误版本 / 错误身份 / Bridge 不匹配（契约 :130,:133） | 显式路径：allowlist 说 `1.21.4` 而启动 `1.20.1` → `ADMISSION "the session launches Minecraft 1.20.1, the target allows 1.21.4"`（1 秒，store 不变）；Bridge 钉错 → `SUPPLY_CHAIN "candidate Bridge jar pin is not the reviewed build of the 1.20.1 root"`（`bundle verify` 与 `launch-plan --dry-run` 各一次，均 exit 11）；正对照未改动 recipe `bundle verify` → `launchable: true`、`plan_sha256 83299ad5…`。generation 侧真跑：`V1201-070` bundle `eb054c0a…`（14 工件）本 build 重读 `verified / PASS` + rejudge `agrees` | **成立（显式路径）**；**自动路径不成立**——见 §3 的 B1/B2 |
| F3 恶意 status / SRV / 命中禁区（契约 :131） | 恶意 status：§2 全 18 行。禁区地址：`0.0.0.0`/`169.254.169.254`/`224.0.0.1` 在 **profile 装载阶段** 拒（`ADMISSION … (UNSPECIFIED / LINK_LOCAL / MULTICAST)`），且假端点自己的接受日志计数 `0→0`（拒在发出任何字节之前）；主机名拒 `must be an explicit IP literal, not a resolvable name` ⇒ **没有 DNS/SRV 解析路径**，"SRV 把目标改到禁区"今天无法作为真实行为产生。非 loopback 但可达的字面量：`192.0.2.1` 不被策略拒（`TIMEOUT / connect timed out`），容器自身可路由地址被探测并接受（`OBSERVED`） | **部分成立**：无解析器 = 该行的风险面被"只接受字面 IP"挡住；join 授权仍在，但位置不对（§3 Y2） |
| F4 工件损坏 / 下载中断 / 磁盘满（契约 :132） | recipe 字节被改 → `SUPPLY_CHAIN "recipe … digests to 8ce43e26…, not the reviewed 0000…"`（2 秒，store 0）；预算 1 字节 → `SUPPLY_CHAIN "needs 543405728 bytes, over the 1 byte budget"`；半包不能启动 → `session start --profile` 报 `3352 of 3638 artifacts are not in the store yet`（`SUPPLY_CHAIN`）；真实中断：A1 attempt 2 的单资产 `SUPPLY_CHAIN` 拒启动（已有记录，未产生 run document）；本卡两次装机被人为中止后 store 分别停在 31 文件（`.staging` 残留 3）与 18 文件（`.staging` 残留 2），第三次中止点在 388 文件 | **部分成立**：hash/中断/半包有可重跑拒止；**"磁盘不足"整行无实现**（§4 N3） |
| F5 断连后键未松（契约 :136） | 真跑封证重读：`V1201-060` bundle `90d490ce…`（13 工件）本 build `evidence verify → verified / PASS`，`rejudge_evidence.py → agrees`。该 case 断言 `runtime_controller_sigkill_was_confirmed`、`the_bridge_released_the_input_when_the_ipc_was_lost`、`the_server_saw_the_kin_stop_after_the_move`。相邻的停止阶段一行由 `V1201-080` bundle `22fb57f3…`（13 工件）覆盖，同读 `PASS / agrees`，断言 `the_bridge_released_the_input_when_the_session_was_stopped` | **成立（Bridge 侧 IPC 丢失释放 + 会话停止释放，各有独立 sealed run）**；registry 其余 `gaps` 名单是 A3 的只读复核对象，本卡不翻 |
| F6 旧 generation 回调 / 旧 JVM 未停（契约 :135） | 真跑封证重读：`V1201-070` bundle `eb054c0a…`（14 工件）本 build `verified / PASS` + `agrees`，断言含 `the_refused_generation_was_closed_and_never_reopened`、`a_refused_first_snapshot_became_no_lease_and_no_playable`、`this_run_joined_a_world_it_was_never_told_it_could_play` | **成立（拒绝型 generation 关闭后不重开）**；"切服中旧 JVM 未停"是 V07 线的读数，本卡不重复封证 |

## 2. 真实 socket 状态探测：18 行（`table rows: 20 FAIL=0`，store 全程 0）

端口 25700–25717 连续 bind 于 loopback，每行判"探测得到的 `outcome` 是否等于该字节形状该得到的"。
正对照 `control_1201` 必须 `OBSERVED`，否则整表无意义。

| 场景 | outcome | exit | 备注（产品给出的 detail/reasons） |
| --- | --- | --- | --- |
| `control_1201` | `OBSERVED` | 0 | 正对照：良构 1.20.1 应答被相信 |
| `not_json` | `MALFORMED` | 17 | `the status payload is not UTF-8 JSON` |
| `no_version_object` | `MALFORMED` | 17 | `the status payload carries no version object` |
| `version_object_wrong_shape` | `MALFORMED` | 17 | 同上（`version` 为字符串时按"无版本对象"处理） |
| `neither_protocol_nor_name` | `MALFORMED` | 17 | `the version object carries neither protocol nor display text` |
| `display_over_cap` | `MALFORMED` | 17 | `MAX_DISPLAY_TEXT_CHARS = 64` 生效（`domain/version_probe.py:19`） |
| `forged_display_contradicts` | `OBSERVED` | 0 | **探测层只报告所见**，矛盾判定发生在解析层（§3 B12/R1） |
| `multi_version_proxy` | `AMBIGUOUS` | 17 | reasons=`MULTI_VERSION_PROXY`，原始值保留给 pin 决策 |
| `wrong_packet_id` | `MALFORMED` | 17 | `the status response packet id is not 0x00` |
| `truncated_string` | `MALFORMED` | 17 | 声明长度大于字符串实际字节 |
| `short_frame` | `MALFORMED` | 17 | 帧在声明长度前结束 |
| `oversize_declared` | `OVERSIZE` | 17 | 声明长度超 `MAX_STATUS_PAYLOAD_BYTES` |
| `delivered_over_cap` | `OVERSIZE` | 17 | 实际交付超上限 |
| `negative_length` | `OVERSIZE` | 17 | **见 §4 末行死代码观察**：`FF FF FF FF 0F` 走的是超上限分支，`length < 0` 分支（`server_probe.py:191-192`）在真 socket 上不可达 |
| `varint_over_five_bytes` | `MALFORMED` | 17 | `varint longer than five bytes`（`server_probe.py:99-112`） |
| `large_positive_length` | `OVERSIZE` | 17 | 五字节正数长度同样先撞 `OVERSIZE` |
| `close_immediately` | `NO_RESPONSE` | 17 | 端点在给出任何帧前关闭 |
| `silence` | `TIMEOUT` | 17 | 帧中途停住 |

B12/B13（同端点走自动入口）：`exit=17 / ADMISSION / cli.auto_session`，
`NEEDS_PIN … reasons=DISPLAY_TEXT_CONTRADICTS candidates=1.20.1-linux-x86_64-offline-java21`（1 秒）与
`NEEDS_PIN … reasons=MULTI_VERSION_PROXY candidates=none`（2 秒），结束 store 仍 0 文件。

## 3. 自动入口的门序：本卡最重要的新读数

同一份 registry、同一个全新 Kin（store 起始实测 0 文件）、只差 host 字面量：

| 行 | 输入 | 读数 |
| --- | --- | --- |
| B1 | profile allowlist 只写 `1.21.4`，真服答 `1.20.1` | `exit=124`（60 秒界）且已 `fetching 100/3639` —— **没有任何准入拒绝先发生** |
| B2 | profile allowlist 写 `1.20.1,1.21.4` | `exit=124`（66 秒界）`fetching 200/3639` —— 同上 |
| B5 | profile host 改为文档段地址 | `ADMISSION STALE_PROBE … reasons=PROBE_NOT_OBSERVED`（6 秒）—— 它**先尝试连出去**，只因目标不可达而停 |
| X1 | 可达的非 loopback 假端点，显式 `--profile` | `exit=17 ADMISSION launcher.profile "a managed session may only join a loopback target; remote joining needs its own authorization card"`，<2 秒，store 0 |
| X2 | 同上字节，自动 `--auto-bundle`，store 空 | `exit=124`（120 秒界），store 已到 **388 文件**，`fetching` 3 行 —— 装机先于任何 join 授权 |
| Y1 | 满 store（3639/3639，从 A1 卷 `cp -a`），host `127.0.0.1` + 假端点 | 走完 `fetching 3639/3639`，150 秒界内**未被拒** |
| Y2 | 同上，只把 host 换成容器自身可路由地址 | `fetching 3639/3639` **之后**才 `exit=17 ADMISSION … loopback target …`，`java=0` |

结论（分开说，不混）：

1. **join 授权没有被绕过**——非 loopback 目标最终被拒，且没起 JVM（Y2）。契约 :131 的"禁止向新目标发送游戏会话"未被违反。
2. **但自动入口把 738 MB 的装机放在了授权判定之前**：X2 在没有 store 时就开始下载；Y2 在有满 store 时先把 3639 项全过一遍才说"不许 join"。同一份 profile 在显式路径 2 秒内就被拒（X1、§1 F2）。这是**门序缺陷**，不是授权缺失 ⇒ 登记 N1。
3. **版本 allowlist 在自动路径上不再生效**：B1/B2 都进了装机，而显式路径对同两形状分别给出 `the session launches Minecraft 1.20.1, the target allows 1.21.4` 与 `must allow exactly one version`（§1 F2，均 1–2 秒）⇒ 自动解析用的是**目标自己应答的版本**，profile 的 allowlist 没有参与准入。这与第 2 点是同一个 N1 卡的两半（先准入、后装机），不另开卡。

## 4. 本卡量出的缺口：登记，不顺手修

按 §1.2「范围外登记单独修复卡」，以下都不在 A2 的允许改动内，本卡一行代码未改。

| ID | 状态 / 依赖 | 缺口与判据来源 |
| --- | --- | --- |
| **N1** `V1201-AUTO-ENTRY-GATE-ORDER-001` | `QUEUED`，不依赖 A3 | 自动入口应先做与显式路径等强的准入（地址禁区、join 授权、profile allowlist 与解析结果一致），再决定要不要装机。判据：§3 的 X1 vs X2/Y2（装机先于授权）与 B1/B2（allowlist 不参与自动准入）。修完要能重跑本记录 §3 全部行并让"先拒后装"成为读数，而不是改本记录的期望。 |
| **N2** `V1201-MAX-BYTES-VALIDATION-001` | `QUEUED`，不依赖 A3 | `--max-bytes 0` 与 `-1` 今天得到 `exit=70 / INTERNAL_INVARIANT / unexpected internal failure (ValueError)`（各 13–16 秒），而 `--max-bytes 1` 得到正确的 `SUPPLY_CHAIN` 具名拒止；`--max-bytes` 与 `--profile` 同时给出时被接受且被忽略（B10 报的是缺工件，不是预算）。期望是"非正预算 ⇒ 具名拒止；与自动 bundle 无关的预算 ⇒ 具名用法错误"，两句都属产品行为 ⇒ 单独卡，不在证据卡里改代码。 |
| **N3** `V1201-DISK-PREFLIGHT-001` | `BLOCKED_DECISION`（等主控冻结断言） | 契约 :132 的"磁盘满"一行在 `src/minekin_core` 里没有任何实现（无空间预检、无 ENOSPC 具名类别），因此本卡无法用真实读数回答该行的两半（"无可启动半包"另见 F4，已有读数）。是否引入装机前预检、失败类别叫什么，属未冻结契约 ⇒ 不自造断言。 |
| **N4** `V1201-SRV-RESOLVER-001` | `BLOCKED_DECISION` | 唯一解析实现是 `SavedAddressResolver`（`server_probe.py:69`），profile host 必须是字面 IP（A4）。"SRV/DNS 目标改变"要成为可测行为，先得决定产品是否支持 SRV；当前"只接受字面 IP + 装载期禁区拒"是实际边界，本记录按实际写。 |
| 死代码观察（不建卡） | 记录 | `server_probe.py:191-192` 的 `if length < 0` 分支在真实 socket 上不可达：`_read_varint` 从不返回负数，`negative_length` 实测 `OVERSIZE`。属可清理代码，不是契约缺口，留给实现卡顺手看。 |

未测量并保留的：F4 后半句"旧 blob 仍可验"在今天没有针对**部分装机后**的 store 级复验读数（`bundle verify` 判的是 recipe 可启动性，不是整店重验）；本卡不猜结论，A3 若要引用必须另测。

## 5. 非空转与正对照配对

每条新断出来的拒止都配一行"同样字节形状下不该拒的情况"，否则矩阵可以靠"什么都拒"变绿：

| 拒止 | 配对读数 | 结果 |
| --- | --- | --- |
| R1 `DISPLAY_TEXT_CONTRADICTS`、R2 `MULTI_VERSION_PROXY` | R3：同一端点组、同一自动入口、同一空 store，只把应答换成一致的 1.20.1 | R3 通过解析并进入装机（store `0→8`，`.staging` 2 文件），故两条拒止归因于它们自己的字节，而不是"自动入口不信任何假端点" |
| 状态探测 18 行 | `control_1201` | `OBSERVED / exit 0`，否则整表作废（§2） |
| 禁区地址 A1（`0.0.0.0`，端口与 A6 同一个） | A6 `127.0.0.1` 同一端口 | A1 拒且假端点接受数 `0→0`；A6 `OBSERVED` 且接受数 `0→1` ⇒ 计数本身有效，"拒在发字节之前"不是空话 |
| Y2 非 loopback 被拒 | Y1 loopback 同 store 同入口 | Y1 未被拒 ⇒ 决定因素是 host 字面量 |
| 显式准入五拒 | 未改动的提交版 profile 直调 `load_session_server_profile(..., minecraft_version="1.20.1")` | `accepted`（`127.0.0.1:25566`/`offline`），且 `bundle verify` 正对照 `launchable: true` |
| 干净空 store 装机 | 未改动自动入口真跑（part 4） | 服务器 13 秒就绪，store `0→8` 运行中、结束 31 文件，判定 `CONTROL PASSED` |

## 6. 本卡不声称

- 不是 V08 晋级，也不是对任何远程目标的许可；全程 loopback 与容器自身接口。
- 18 行状态探测与 B/X/Y 系列是**可重跑拒止读数**，不是 sealed `tested` 证据；只有 §1 F5/F6 与 A1 的 `fc12d7d1…` 属于 sealed 真跑，且本卡只**重读**（`verified / PASS` + `agrees`），未重封、未翻 registry。
- 不代表 1.21.4，不代表 HOST/PERSIST/在线认证，不代表 `p0-core` 整体 `tested`。
- `attempt` 类结论保留原始材料：`minekin-v1201neg9`（part 7 第一次尝试）因假端点自身帧构造错误而 `NO_RESPONSE`，该行判定为**不确定**（脚本重跑后才有 OBSERVED），失败卷未清理、结论未采用。
