# 本地单端口后台

后台构建后可直接由 Gateway 提供，不再需要长期运行 Vite 或第二个代理端口。此入口用于源码部署；尚不是包含客户端、Java 和后台资产的一键发行包。

在项目根目录安装既有依赖并构建（已有依赖可跳过安装）：

```powershell
uv sync --frozen
pnpm --dir dashboard install --frozen-lockfile
pnpm --dir dashboard build
uv run --frozen python -m gateway.server --data-root C:/你的Minekin数据目录 --kin 你的Kin标识 --dashboard-dir dashboard/dist
```

打开 `http://127.0.0.1:8787/`。根页面会转到 `/?adapter=gateway&gateway=.`，使用同源真实 API，不切到模拟数据。数据根须是已经初始化的 Minekin 根；`--kin` 是数据中的 Kin 标识，不是服务器上的玩家名称。保留既有身份和数据，不为开页面重新初始化、删除或迁移。需要已有受控 Docker 运行环境时，在相同环境中运行 Gateway，不能把宿主页面可访问当作游戏客户端可启动。

省略 `--dashboard-dir` 保持原 API-only 行为；Vite 开发方式仍可使用。Ctrl-C 关闭本 Gateway；受管会话收尾沿用已有生命周期逻辑，并非删除数据。浏览器支持状态以实际读数为准：没有媒体采集仍无 Live View，尚无技能步时没有模型成本数据。

只提供显式构建目录的 `index.html` 和有限类型的顶层 `assets/` 文件。启动时读取有限字节快照，缺失依赖/符号链接/超出预算即失败。无目录列表、仓库文件、运行数据、密钥文件、source map 或 SPA 任意路径回退；重建页面后重启 Gateway 才更新资产。不要把不可信构建目录传入此参数。默认监听 loopback，不启用公网/CORS，不增加模型调用或游戏输入权限。

验证覆盖真实 HTTP 的 HTML/JS 与 API 同源读取、旧路由、写方法拒绝、路径穿越及构建缺失；游戏和真实模型仍须另外验收。

## 可复跑的真实浏览器验收

```powershell
pnpm --dir dashboard build
pnpm --dir dashboard exec playwright test --config playwright.single-port.config.ts
```

该独立套件自己启动 loopback Gateway 和临时 SQLite 身份，不启动 Vite、不替换 fetch，也不接入用户数据根。Chromium 验证根页面转向真实 API、目标保存与刷新读回、停机显式改名与 SQLite revision、跨源写拒绝和私有文件拒绝；不点击启动/探测/模型测试。需要已安装 Playwright Chromium；端口占用时设置 `E2E_SINGLE_PORT`，不会复用未知服务。

验收夹具独有的带随机令牌退出请求会先关闭数据库再清理它自己创建的临时根；该测试控制路由不存在于产品 Gateway。异常硬杀仍可能留下系统临时目录，不能自动扫描删除其他会话数据。2026-10-04 本机 Chromium 两用例通过（真实界面和真实本地 API，未包含游戏/JVM/模型供应商）。
