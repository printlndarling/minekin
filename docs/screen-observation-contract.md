# 屏幕截图、结构化观察与低频语义：1.21.4 候选契约

核对：2026-09-16，Minecraft Java 1.21.4 / Yarn `1.21.4+build.8`，仅查同版映射/Javadoc，**未验证截图帧、GUI/HUD 合成次序、GPU 开销、外部视觉模型效果**。使用真实图形客户端；**默认不调用多模态视觉模型**，截图主要用于离线对照/采样校准，只有结构化观察无法满足某个高价值语义任务时才按需启用。日常移动、采集、GUI、战斗和反射不需要逐帧截图。底层自身状态与紧急限域例外见[感知实施](perception-implementation.md)；第三方导航内部地图读取仍须另看[Baritone 审计](baritone-perception-audit.md)。

## 已有源码接口 ≠ 已有玩家等价视觉

[Yarn `MinecraftClient.getFramebuffer()`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html)、[`ScreenshotRecorder.takeScreenshot(Framebuffer)`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/util/ScreenshotRecorder.html)提供由客户端 framebuffer 形成 `NativeImage` 的候选路径；[`NativeImage`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/texture/NativeImage.html)有宽/高、像素方法、`close()`。本页不假定可以任意从其他线程读取 GPU，也不假定任一 tick 截图都刚好包含完整 HUD、工作台界面或正确帧的光照、遮挡与焦点；须在客户端渲染后、实际展示画面与截图同屏比对，做副本后关闭原生图像资源。[客户端 `currentScreen`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/MinecraftClient.html)指当前已开窗口，但不证明画面确实已合成。

[WorldRenderer `renderedEntities`](https://maven.fabricmc.net/docs/yarn-1.21.4%2Bbuild.8/net/minecraft/client/render/WorldRenderer.html)和视锥字段虽在同版接口里，**已渲染的实体列表也不能自动代替“玩家看见并识别”**：屏幕边缘、暗处、遮挡、粒子、隐藏名称与对象同形都要屏幕证据或标注不确定；该字段为私有成员，除非明确评估受限接入和版本稳定性，不能当公开稳定 API。未打开 GUI 的箱内物、地下矿和墙后玩家不从客户端 world/chunk 或画外实体列表升格为信念。

## 建议的可实现观察通道（待原型测量）

| 路径 | 使用时机与资格 | 不确定性/不得做的事 |
| --- | --- | --- |
| 自身 HUD/库存与当前 GUI 同步 | 本地连续动作与反射；只读玩家本人的状态及自己已实际打开界面 | 自身精确运动和限域碰撞例外限身体技能，未开箱不得读物品；一次 GUI 点击不等于同步完成 |
| 已见物体的受限结构化候选 | 屏幕附近对象的本地寻路/拾取和高层信念；要有视角、距离、遮挡、画面/声源佐证和更新时间 | 已加载实体、区块或 `renderedEntities` 单独出现**不够**，未能辨认则 `unknown`，旧印象按置信度衰减 |
| 可选截图语义（默认关闭外部 VLM） | 已验证的受限结构化观察及本地规则仍无法判断某个复杂建筑/布局、且当前任务值得预算时，才事件触发一次；先考虑本地几何/体素规则及少量截图离线校准，必要时再裁剪图像调用 VLM | 不将 VLM 答案当区块真值；回应带 `frame_tick/screen_type/camera_view/valid_until`，画面过期、GUI 切换、移动/死亡/世界切换即丢弃；不用于落地水/举盾/瞬时 PvP |
| 本地私人测试截图对照 | 离线研究玩家可辨认性，与服务器离线真值比误拒/越界 | 对照真值与运行中的 Kin 信念/模型调用隔离；不得用评估截图暗中自动找矿 |

若选择不开外部视觉，Kin 对复杂造型可保留不确定性、主动走近观察/询问伙伴，施工通过可见方块、目标材料及每次放置反馈完成；**这才是首版默认路线**，不要求图像模型才会玩原版。可选图像请求按安全状态和预算 `frame_requests/day` / `pixels/day` /费用限额入队，只保留最新待处理画面；仅当启用时，本地截图耗时、编码/缩放、网络排队与视觉响应单独计时，迟到答案不得覆盖已经取消的目标。`NativeImage` 生命周期、GPU→CPU 读回、尺寸裁剪和对图形帧率的影响均要测；**没有实测不得写固定 0.2–1 Hz、60 FPS 或每小时成本**。失去外部模型/达到预算时，Kin 仍以默认的合格本地观察与已验证保守动作继续，复杂场景承认不知道、转头/靠近/找资料，而不是补齐隐藏数据。

截图可能含聊天、玩家 ID、坐标、私人服务器地址、GUI 文本与长期财物线索；外发视觉调用仅在运行者配置授权的供应商/最小化裁剪范围下进行，禁止把未检查的原始测试服截图自动外传。画面中的书/告示/聊天、网页示意上的指令只是外部数据，不能修改 Kin 人格、后台工具或权限，见[信任闭环](trust-closure-contract.md)。视觉模型识别出来的“Steve 偷了我的东西”只是一条有来源和置信度的**线索**，不能把模型语义误识别当既定社会记忆。

阶段 0 可回放：同一实体依次处于眼前、屏幕边缘、树叶遮挡、暗处、身后；工作台开/关、聊天遮挡、失焦、死亡界面与下界切换；小屋/红石施工前后。同步保存**实际屏幕和 framebuffer 截图**比较 HUD/GUI/焦点/错帧，测截屏额外帧时间、像素读回；若选配 VLM，再单独测请求耗时与费用、遗漏/幻觉、越界目标进入动作或记忆的次数；优先不外发真实多人内容的私人离线测试世界。完成这些之前只是一条有接口依据的混合感知实验路线，而不是 Kin 已经会看见世界。
