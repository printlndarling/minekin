# Minekin Dashboard

当前控制台提供状态与日志、模型与目标配置、模型连接测试、身份改名、停止会话，以及受管启动（显式确认、有界监督，见下文）。服务器设置已接入；暂停/恢复仍待实现；完整产品进度见[总规划](../docs/full-project-development-plan.md)。

早期只读契约和身份写面文档保留为历史依据；现行范围以用户完整项目目标与当前实现为准。

## 这一层是什么

角色状态、任务、时间线、告警、身份、配置与配方边界来自可替换的 adapter，默认连接本地 Gateway。模拟数据仅在显式 `?adapter=mock` 时使用，并在横幅标注；模拟模式不能验证真实模型连接。

顶部常驻的**上下文条**用一屏回答操作者真正要问的四件事：它是谁（身份读数 + revision + 离线 UUID）、在哪个世界（profile / epoch / 是否入服）、正在干什么（运行态、链路、租约、台账里最远阶段）、为什么没运行或没完成（连续未落地的读取、会话收尾行、输入被拒原因、无告警源、活动告警）。左侧导航的每一项带该页读路的实时状态（在读 / 读取中 / 连续 N 次未落 / 失败 · 具名原因），页面由地址片段选择，可直接深链 `#timeline`、`#alerts`、`#identity`、`#data`。

**没有占位页。** 观战画面、心智/目标/成本、事件游标这些还没有权威数据源的能力，只在「数据源与缺口」页按具名原因列为 `未接入`；Dashboard 的通用写控制端点是产品阶段有意保留的边界，单独标为 `暂不开放`，两者不混同、也不渲染任何编造内容。

边界（并用测试固定，不只是写在文档里）：

- 当前可保存配置、修改停止状态下的身份、测试模型、启动受管会话及停止会话；暂停/恢复未接入；
- 不连 Bridge、不连数据库、不持有凭据（页面上不出现 token/密钥字段）；
- 不伪造 Live View：没有真帧源时不渲染 `<video>/<canvas>/<img>`，只显示具名缺口与前置条件；
- 所有写请求复用同源、回环和 CSRF 校验；身份修改按修订号检查，连接测试拒绝并发重复调用；
- 不改动 P0 Core：Core 侧不新增 Node 依赖，本目录构建产物是静态文件，由 Gateway 或反向代理托管。

## 已验证内容（真实读数）

2026-10-03：模型连接测试由配置页发起 `POST /api/v1/dashboard/model/test`，使用已保存配置与 Gateway 进程环境（环境优先）。请求尝试一次结构化模型决策，连接超时配置上限20秒，返回具名原因、耗时、调用记录与估算成本；不会执行决策、回显模型原文或密钥，也不自动重试。未保存草稿时禁用测试，编辑配置会清除旧结果。真实模型函数调用一次返回 connected（2906ms、估算3 micro），与真实浏览器→Vite代理→Gateway 的 off/零调用验证分开记录；不把假端点或模拟面板当成真实模型结果。

可复现浏览器测试：先在独立 `MINEKIN_HOME` 初始化一个 Kin，用 `MINEKIN_ENV_FILE` 指向空配置文件并清除该测试进程的 `MINEKIN_MODEL_*` 覆盖；启动 `uv run python -m gateway.server --data-root <测试根> --kin <测试Kin> --port 8789`。在另一终端设置 `MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8789`、`E2E_MODEL_TEST_LIVE=1`，运行 `pnpm build` 与 `pnpm exec playwright test e2e/model-test-live.spec.ts`。此用例保存 off，仅验证实际HTTP链路，无付费调用；390px窄屏布局也检查无横向溢出。单元/API 的本地假端点仅用作格式和错误边界测试。

2026-09-29 外壳重做后，同一条链路（typecheck → Vitest → build → Playwright）在 Node 24.18.0 + pnpm 11.21.0 上的读数：

| 命令 | 结果 |
| --- | --- |
| `node ./node_modules/typescript/bin/tsc --noEmit` | 无输出（通过，含 `e2e/`） |
| `node ./node_modules/vitest/vitest.mjs run` | 12 文件 / 127 用例全绿 |
| `node ./node_modules/vite/bin/vite.js build` | 114 modules，`dist/assets/index-*.js` 330.20 kB（gzip 104.66 kB），2.27s |
| `node ./node_modules/@playwright/test/cli.js test e2e/readonly-shell.spec.ts` | 12 用例全绿（`vite preview` 真浏览器关键流程，含上下文条、片段深链、缺口页与只读边界） |

D1 时期的同一链路读数（Node 24.13.0 与 Node 22.22.3 各一遍，结果一致）保留如下，作为当时的记录：5 测试文件 / 35 用例、102 modules / 293.75 kB（gzip 92.96 kB）、Playwright 10 用例。

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

读真实 Gateway 时不要从面板直连它的端口：契约只答三条 GET、自己不回应跨域预检，浏览器会在请求到达 Gateway 之前拒掉 `127.0.0.1:5175 → 127.0.0.1:8787`。开发服务器因此把 `/gateway/*` 反代到 Gateway（`vite.config.ts` 的 `server.proxy`，目标由 `MINEKIN_GATEWAY_TARGET` 覆盖，默认 `http://127.0.0.1:8787`），出浏览器的路径是 `/gateway/api/v1/dashboard/snapshot`，到达的是契约自己的 `/api/v1/dashboard/snapshot`。Gateway 的起法见 `test-orchestrator/runner/README.md` 的「Reading it from a browser」：`bash test-orchestrator/runner/demo.sh --gateway` 把 Demo 卷的只读模型发布在 `127.0.0.1:8787`，随后 `pnpm dev` 打开 `http://127.0.0.1:5175/?adapter=gateway&gateway=/gateway`。

## 服务器配置与版本探测（2026-10-03）

打开 `#server`，填写 IP 字面量和端口并保存，再点击「探测服务器版本」。设置保存在 Gateway 数据根的 `dashboard-settings.sqlite3`；修订冲突拒绝覆盖，草稿保留。探测使用保存配置的固定快照，远程目标还需勾选该地址的显式许可；页面不会自动探测或自动加入世界。支持状态来自当前登记和实际 Gateway 所在平台，未支持的版本/平台具名返回。模拟适配器拒绝真实探测。

实际浏览器复验需要受控 Docker Gateway（仅宿主127.0.0.1:8789发布）与容器内127.0.0.1:25566的Minecraft 1.20.1服务：先构建Dashboard，再设置 `MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8789`、`E2E_SERVER_CONFIG_LIVE=1`，运行 `pnpm e2e e2e/server-config-live.spec.ts`。用例保存配置、刷新验证持久化、检查OBSERVED/763/1.20.1/RESOLVED/Linux，验证草稿禁用与390px布局。只针对可修改的本地测试数据根运行；不指向用户远程服。

探测成功只证明服务器状态响应和已登记客户端匹配，不启动客户端；受管启动见下一节。

## 受管会话启动（2026-10-03）

打开 `#session`，在「启动受管会话」里选择运行方式（仅入服观察，或按已保存模型与目标自主运行）与时限，勾选确认后提交。启动是 Gateway 自己持有的一个有界后台任务：绑定已保存的服务器修订并先做版本探测（未登记版本具名拒绝），按时限、动作步数与下载预算收口；作业记录落盘（`GET /api/v1/dashboard/session/job`），刷新页面不会重启任务；「停止会话」会取消该任务——先释放输入再停止客户端。准备阶段的取消、时限到期与崩溃收尾由单元测试覆盖，浏览器用例只依赖真实读数。

实际浏览器复验（2026-10-03，受控 Docker）：容器内以 `--allow-player Kin` 启动的受控 1.20.1 服务器（server run 目录 `run-71`）加位于同一容器、仅宿主 `127.0.0.1:8789` 发布的 Gateway；先 `pnpm build`，再以 `MINEKIN_GATEWAY_TARGET=http://127.0.0.1:8789`、`E2E_SESSION_START_LIVE=1` 运行 `pnpm e2e e2e/session-start-live.spec.ts`。两发连续 PASS（47.3s / 48.8s）：job `ce7c970b…` 与 `87d2fac0…` 都实际入服（服务端日志逐字 `Kin joined the game` / `lost connection: Disconnected`）并在页面读到「已入服/会话进入可玩」后从面板停止，作业读数 `STOPPED_ON_REQUEST`、`inputReleaseFailed=false`、`bridgeLostReason=""`，store 全复用（0/3639）；stop receipt 为 `release=NOTHING_HELD`（观察模式不持输入租约，不冒充「已确认松键」）。首提曾因容器白名单为空被服务器拒止（`You are not white-listed on this server!`），按既有工具加 `--allow-player Kin` 重启服务器后复验，判据未放宽。局限：观察模式、单 Kin、loopback；暂停/恢复与断连后恢复不在本页。

## 目录结构

```text
src/domain/     Signal 读模型、快照/时间线/告警/身份类型、adapter 接口、中文标签、会话阶段推导
src/fixtures/   六个模拟场景（只有显式 mock 适配器才用）
src/adapters/   mockAdapter（脚本化）、gatewayAdapter（真实 fetch + fail-closed 解码）、config（URL/env 切换）
src/hooks/      useNow 时钟、TanStack Query 读数封装、身份读数与改名控制器
src/shell/      导航模型、地址片段路由、读状态文案、能力清单
src/components/ Pill / Panel / SignalValue / DataSourceBanner / ContextBar
src/panels/     总览、会话阶段、时间线、告警、身份 · 改名、数据源与缺口
e2e/            真浏览器关键流程（只读外壳 + 需 E2E_LIVE_* 才跑的真实网关/改名会话）
```

## 读模型：为什么"没有值"是一等公民

每个字段都是 `Signal<T>`：要么 `known`（带 `value` + 观测时间 + 新鲜度预算），要么 `gap`（带 `status` ∈ `unknown/unavailable/not_wired/permission_denied`、非空 `reason`、以及 `source`/`sourceRef`/`observedAt` 溯源）。渲染层只有一个 `SignalValue`，因此不存在"某个面板偷偷把缺失值当 0 或默认值显示"的路径。

新鲜度（实时 / 陈旧 / 无观测时间）由共享时钟按 `staleAfterMs` 计算，不靠文案猜测。`schemaVersion` 解码器只认 `kin-dashboard-readmodel/1.0.0`——2026-09-28 冻结的只读契约（`docs/gateway-dashboard-readonly-contract-2026-09-28.md`）；页头显示的是字节自带的那个版本串，对不上就整屏失败关闭，不会退回猜测。

## 切换数据源

优先级：URL 查询参数 > 构建期环境变量 > 默认值。

| 参数 | 环境变量 | 取值 |
| --- | --- | --- |
| `?adapter=` | `VITE_DASHBOARD_ADAPTER` | `gateway`（默认）/ `mock`；认不出的值留在 `gateway`，不会因为一次拼错就悄悄改用编造的 Kin |
| `?scenario=` | `VITE_MOCK_SCENARIO` | `healthy_run_07` `stale_observations` `bridge_disconnected` `fields_unknown` `permission_restricted` `read_failed`（仅 `mock` 有意义） |
| `?gateway=` | `VITE_GATEWAY_BASE_URL` | Gateway 基址；缺省时所有读取返回 `not_configured` |
| `?latency=` | `VITE_MOCK_LATENCY_MS` | 模拟延迟 |

`?adapter=gateway` 且未给基址时，面板不会发起任何 `/api/` 请求（e2e 用例断言请求列表为空），并整屏显示未配置/未知。`GatewayReadAdapter` 已经写出真实 `fetch`、超时/取消和契约解码，解码器对枚举、溯源字段和 `schemaVersion` 严格拒绝，因此**任何契约未冻结的字段都只能显示为未知，不可能被前端编造出来**。


## 工具链与供应链注记

- 冻结栈：React 19 + Vite 7 + TypeScript 5.9（`strict` 且开 `noUncheckedIndexedAccess`、`exactOptionalPropertyTypes`、`verbatimModuleSyntax`、`noUnusedLocals/Parameters`）、TanStack Query 5、Vitest 3 + Testing Library、Playwright 1.63、CSS Modules + token（无重型设计系统，无 SSR/Next）。
- `engines.node >=22.12`，`.nvmrc` 记 24。实测 Node 24.13.0 与 22.22.3 都能装依赖与跑测试。
- 本仓库启用了 pnpm 的 `minimumReleaseAge`（24 小时）供应链策略：当天新发布的 `@tanstack/react-query@5.104.0` 被拒绝，因此把 `@tanstack/react-query`/`query-core` 精确锁定在 `5.103.2`（`pnpm-workspace.yaml` 的 `overrides`）。等 5.104.0 满足窗口期后可解绑。
- pnpm 11 忽略 `package.json` 里的 `pnpm.*` 字段，`onlyBuiltDependencies: [esbuild]`、`verifyDepsBeforeRun: false` 必须写在 `pnpm-workspace.yaml`。
- 仓库中不放机器相关的 registry 配置：镜像与 `PLAYWRIGHT_DOWNLOAD_HOST` 属于本地环境，通过环境变量传入。

## 真实接口接入还缺什么

按阻塞顺序，D2 之后要接上真数据需要：

1. **G lane 冻结只读契约**——已于 2026-09-28 冻结并被面板解码，不再是阻塞项。当时端点 `/api/v1/dashboard/{snapshot,timeline,alerts}` 与 `.../0.1.0-proposal` 的字段名都是前端提案。需要 Core/Gateway 侧给出：稳定 `schemaVersion`、每个字段的 `source`/`sourceRef`/`observedAt`/`staleAfterMs` 语义、缺失时的 `status` 枚举。没有它，接入只能停在"解码即拒绝"。
2. **鉴权与来源策略**。默认只监听 127.0.0.1；远程需要 TLS 反代、独立管理员认证、短时配对/撤销、CSRF/origin 校验。Dashboard 绝不能拿到 Bridge token，也不能把凭据写进前端——这部分依赖 Gateway 实现，前端只预留 header 注入点。
3. **事件游标与增量流**。时间线现在是整页拉取 + 5 秒轮询；契约缺 `cursor`/`generation` 语义和 WSS 增量通道（状态快照、事件、日志尾部、告警）。WebSocket 序列化格式、最大频率、背压与断线重放窗口仍是文档里列出的"待原型决定"项。
4. **证据/封存读数端点**。`panel-evidence` 需要能引用 Core 已封存的 run evidence（hash + 元数据 + 可核验链接），才能做到"面板只引用已封装配额，不据此宣称 tested 或在线"。
5. **媒体通道**。Live View 需要真实帧源（Linux：Xvfb + FFmpeg `x11grab`；Windows 等价物）、独立媒体中继（可选 MediaMTX/WebRTC），以及"媒体断流不阻塞反射"的断流提示。前端已刻意不放任何 `<video>`，等帧源和端到端延迟测量一起做。
6. **脱敏后的 Server Profile / World Context 视图**。host/port、身份档案、服规、感知与能力开关需要按"人类可读但可审计"的粒度呈现，且不得回流到 Kin 感知；这依赖 Core 的 profile 读取接口。
7. **权限分层**。观测/配置/急停/人工接管是不同级别；现在整个面板只有观测，写操作入口需要 Gateway 的 actor/审计模型先落地。
8. **OpenAPI 客户端生成**。契约稳定后用生成器替换手写解码器，并接入 schema diff 检查，避免前端与 Gateway 各自漂移。

在这些之前，本外壳的价值是：把"缺失即未知"的表达、溯源展示与只读边界固定下来，让 G/Core 侧一冻结契约就能直接对着解码器验收。
