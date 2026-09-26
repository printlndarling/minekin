# Minekin Dashboard（D1：只读外壳）

卡片：`DASHBOARD-READONLY-SHELL-001`（并行计划 D lane）。独占路径 `dashboard/**`；本目录之外的文件不属于本卡。

依据文档：`docs/standalone-runtime-dashboard.md`、`docs/technical-stack-selection.md`。冲突时以那两份文档与真实 P0 证据为准。

## 本卡是什么

一个**只读**的 Kin 观测外壳：总览（运行状态 / 会话与版本 / 证据来源）、时间线、告警、Live View 占位、Mind 与成本占位。所有数值都来自一个可替换的 read adapter，当前唯一真实数据源是**明确标注的模拟数据**。

边界（并用测试固定，不只是写在文档里）：

- 不启动、不暂停、不急停、不注入游戏输入，不提供任何写操作入口；
- 不连 Bridge、不连数据库、不持有凭据（页面上不出现 token/密钥字段）；
- 不伪造 Live View：没有真帧源时该面板只显示"未接入"和前置条件清单，不渲染 `<video>/<canvas>/<img>`；
- 不改动 P0 Core：Core 侧不新增 Node 依赖，本目录构建产物是静态文件，未来由 Gateway 或反向代理托管。

## 已验证内容（真实读数）

同一条链路（typecheck → Vitest → build → Playwright）在 Node 24.13.0 与 Node 22.22.3 上各完整跑过一遍，pnpm 11.21.0，结果一致：

| 命令 | 结果 |
| --- | --- |
| `node ./node_modules/typescript/bin/tsc --noEmit` | 无输出（通过） |
| `node ./node_modules/vitest/vitest.mjs run` | 5 文件 / 35 用例全绿 |
| `node ./node_modules/vite/bin/vite.js build` | 102 modules，`dist/assets/index-*.js` 293.75 kB（gzip 92.96 kB），1.89s |
| `node ./node_modules/@playwright/test/cli.js test` | 10 用例全绿（`vite preview` 真浏览器关键流程） |

Playwright 浏览器下载在默认 CDN 上出现 `ECONNRESET`，改用镜像可完成：

```bash
PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright pnpm run e2e:install
```

## 命令

```bash
pnpm install            # 装依赖（见下方供应链说明）
pnpm dev                # 127.0.0.1:5175 开发服务器
pnpm build              # tsc --noEmit + vite build
pnpm test               # Vitest（jsdom）
pnpm run e2e            # Playwright，自动起 vite preview（127.0.0.1:5176）
```

## 目录

```text
src/domain/     Signal 读模型、快照/时间线/告警类型、adapter 接口、中文标签
src/fixtures/   六个模拟场景（唯一的"数据源"）
src/adapters/   mockAdapter（脚本化）、gatewayAdapter（真实 fetch + fail-closed 解码）、config（URL/env 切换）
src/hooks/      useNow 时钟、TanStack Query 读数封装
src/components/ Pill / Panel / SignalValue / DataSourceBanner
src/panels/     总览、时间线、告警、Live View 占位、未接入占位
e2e/            真浏览器关键流程
```

## 读模型：为什么"没有值"是一等公民

每个字段都是 `Signal<T>`：要么 `known`（带 `value` + 观测时间 + 新鲜度预算），要么 `gap`（带 `status` ∈ `unknown/unavailable/not_wired/permission_denied`、非空 `reason`、以及 `source`/`sourceRef`/`observedAt` 溯源）。渲染层只有一个 `SignalValue`，因此不存在"某个面板偷偷把缺失值当 0 或默认值显示"的路径。

新鲜度（实时 / 陈旧 / 无观测时间）由共享时钟按 `staleAfterMs` 计算，不靠文案猜测。`schemaVersion` 为 `kin-dashboard-readmodel/0.1.0-proposal`，**是提案不是契约**：G lane 尚未冻结只读 API，页头会一直显示它是 proposal。

## 切换数据源

优先级：URL 查询参数 > 构建期环境变量 > 默认值。

| 参数 | 环境变量 | 取值 |
| --- | --- | --- |
| `?adapter=` | `VITE_DASHBOARD_ADAPTER` | `mock`（默认）/ `gateway` |
| `?scenario=` | `VITE_MOCK_SCENARIO` | `healthy_run_07` `stale_observations` `bridge_disconnected` `fields_unknown` `permission_restricted` `read_failed` |
| `?gateway=` | `VITE_GATEWAY_BASE_URL` | Gateway 基址；缺省时所有读取返回 `not_configured` |
| `?latency=` | `VITE_MOCK_LATENCY_MS` | 模拟延迟 |

`?adapter=gateway` 且未给基址时，面板不会发起任何 `/api/` 请求（e2e 用例断言请求列表为空），并整屏显示未配置/未知。`GatewayReadAdapter` 已经写出真实 `fetch`、超时/取消和契约解码，解码器对枚举、溯源字段和 `schemaVersion` 严格拒绝，因此**任何未被 G lane 实现的字段都只能显示为未知，不可能被前端编造出来**。

## 工具链与供应链注记

- 冻结栈：React 19 + Vite 7 + TypeScript 5.9（`strict` 且开 `noUncheckedIndexedAccess`、`exactOptionalPropertyTypes`、`verbatimModuleSyntax`、`noUnusedLocals/Parameters`）、TanStack Query 5、Vitest 3 + Testing Library、Playwright 1.63、CSS Modules + token（无重型设计系统，无 SSR/Next）。
- `engines.node >=22.12`，`.nvmrc` 记 24。实测 Node 24.13.0 与 22.22.3 都能装依赖与跑测试。
- 本仓库启用了 pnpm 的 `minimumReleaseAge`（24 小时）供应链策略：当天新发布的 `@tanstack/react-query@5.104.0` 被拒绝，因此把 `@tanstack/react-query`/`query-core` 精确锁定在 `5.103.2`（`pnpm-workspace.yaml` 的 `overrides`）。等 5.104.0 满足窗口期后可解绑。
- pnpm 11 忽略 `package.json` 里的 `pnpm.*` 字段，`onlyBuiltDependencies: [esbuild]`、`verifyDepsBeforeRun: false` 必须写在 `pnpm-workspace.yaml`。
- 仓库中不放机器相关的 registry 配置：镜像与 `PLAYWRIGHT_DOWNLOAD_HOST` 属于本地环境，通过环境变量传入。

## 真实接口接入还缺什么

按阻塞顺序，D2 之后要接上真数据需要：

1. **G lane 冻结只读契约**（最大阻塞项）。当前端点 `/api/v1/dashboard/{snapshot,timeline,alerts}` 与 `.../0.1.0-proposal` 的字段名都是前端提案。需要 Core/Gateway 侧给出：稳定 `schemaVersion`、每个字段的 `source`/`sourceRef`/`observedAt`/`staleAfterMs` 语义、缺失时的 `status` 枚举。没有它，接入只能停在"解码即拒绝"。
2. **鉴权与来源策略**。默认只监听 127.0.0.1；远程需要 TLS 反代、独立管理员认证、短时配对/撤销、CSRF/origin 校验。Dashboard 绝不能拿到 Bridge token，也不能把凭据写进前端——这部分依赖 Gateway 实现，前端只预留 header 注入点。
3. **事件游标与增量流**。时间线现在是整页拉取 + 5 秒轮询；契约缺 `cursor`/`generation` 语义和 WSS 增量通道（状态快照、事件、日志尾部、告警）。WebSocket 序列化格式、最大频率、背压与断线重放窗口仍是文档里列出的"待原型决定"项。
4. **证据/封存读数端点**。`panel-evidence` 需要能引用 Core 已封存的 run evidence（hash + 元数据 + 可核验链接），才能做到"面板只引用已封装配额，不据此宣称 tested 或在线"。
5. **媒体通道**。Live View 需要真实帧源（Linux：Xvfb + FFmpeg `x11grab`；Windows 等价物）、独立媒体中继（可选 MediaMTX/WebRTC），以及"媒体断流不阻塞反射"的断流提示。前端已刻意不放任何 `<video>`，等帧源和端到端延迟测量一起做。
6. **脱敏后的 Server Profile / World Context 视图**。host/port、身份档案、服规、感知与能力开关需要按"人类可读但可审计"的粒度呈现，且不得回流到 Kin 感知；这依赖 Core 的 profile 读取接口。
7. **权限分层**。观测/配置/急停/人工接管是不同级别；现在整个面板只有观测，写操作入口需要 Gateway 的 actor/审计模型先落地。
8. **OpenAPI 客户端生成**。契约稳定后用生成器替换手写解码器，并接入 schema diff 检查，避免前端与 Gateway 各自漂移。

在这些之前，本外壳的价值是：把"缺失即未知"的表达、溯源展示与只读边界固定下来，让 G/Core 侧一冻结契约就能直接对着解码器验收。
