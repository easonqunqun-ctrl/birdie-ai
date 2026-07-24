# 22 · App 端 Flutter 独立重写落地计划（方案 C）

> 决策日期：2026-07-20 · 状态：**已定方向，待前置项拍板后开工**
> 与本文件冲突时，工程实现以本文件为准；产品/接口契约仍以 `docs/01`、`docs/02`、白皮书为权威源。

---

## 0. 背景与决策

**结论：放弃「一套 Taro 代码同时编小程序 + RN App」，App 端改为独立 Flutter 工程重写，与向野而生同一路径。**

### 为什么放弃 Taro-RN（实测证伪）

两天实战证明 Taro 的 SCSS→RN 翻译在「1:1 复刻小程序」这个标准下不可用：

- 漏斗管线债：**1912 处 `var()`、139 处 `gap`、155 处无单位行高**、两层 sanitize；
- 卡在 **RN 0.70**（无 flex `gap`、无现代特性）；
- HMR 在精简壳里直接崩 → 只能 `dev=false` + 手动重启 → **热重载没享受到，却背上「Metro 进程一死就红黑屏」的脆工具链**；
- 关键结论：**要 1:1 就得逐页手写 RN StyleSheet**，Taro-RN「写一次两端跑」的卖点在 UI 层已名存实亡，只剩逻辑复用一个好处，却要背全部管线债。

### 量化盘点（灵鸟golf 现状，实测）

| 部分 | 规模 | Flutter 方案下的命运 |
|---|---|---|
| 纯 TS 业务逻辑（store/services/utils/types/hooks/adapters） | **~11,600 行** | 用 Dart 重写（可 1:1 对照翻译，非重新设计） |
| UI（pages+components 的 tsx+scss） | **~31,800 行** | 用 Flutter widget 重写（任何方案都要按端重写） |
| 页面数 | **~60 个**（tabBar 4 + 子页） | 分批复刻 |
| 后端端点 | **136 个** | 复用（App 只重写客户端，后端/AI 引擎不动） |
| service / store | **29 / 3** | → Dart repositories / ChangeNotifier |

### 向野而生的真正教训

向野而生把 **App 与小程序彻底解耦成两套**（`xiangye-miniprogram` 原生小程序 + `xiangye-app` Flutter），只共享后端契约。我们照抄这个解耦结构与工程范式。

---

## 1. 总原则

1. **小程序（`client/` Taro）继续正常发版，一行不动。** Flutter App 是独立新增。
2. 两端只共享 **后端 API 契约**（`docs/02`）与视觉规范（白皮书 §7.2 四色体系）。
3. **照抄** `向野而生/xiangye-app` 的架构与依赖选型（feature-first、原生 http、ChangeNotifier、fluwx）。
4. Taro-RN 资产（`client/rn-shell`、`client/src/**/*.rn.tsx`、`metro-babel-transformer.js`、`config/postcss-rn-sanitize.cjs`、`scripts/pack-rn-*`）**先冻结**，Flutter 跑通核心闭环后再清理。

---

## 2. 工程搭建

### 2.1 目录与初始化

- 新建 `灵鸟golf/app/`（Flutter 工程），与 `client/` `backend/` `ai_engine/` 平级。
- `flutter create --org cn.birdieai --project-name birdie_app app`
- 架构（照抄 xiangye-app 的 feature-first）：

```
app/lib/
  core/        # api_client, env, error, result, jwt, sse, 埋点
  data/        # models(DTO) + repositories(29 service 归域)
  features/    # 每模块自成一包：auth/ home/ analysis/ coach/ training/ profile/ ...
    <feature>/ {pages, widgets, controller(ChangeNotifier)}
  nav/         # 路由表 + tabBar shell
  theme/       # BrandColors + ThemeData（四色体系）
  widgets/     # 跨模块通用组件
```

### 2.2 依赖选型（对齐 xiangye-app + 灵鸟需要）

| 用途 | 包 |
|---|---|
| 网络 | `http`（原生，SSE 用 `http.Client().send` 拿 stream） |
| 状态 | `provider`（轻量 ChangeNotifier 封装；xiangye 用纯内置，二选一见 §5） |
| 安全存储(token) | `flutter_secure_storage` |
| 一般存储 | `shared_preferences` |
| 微信登录 | `fluwx`（**需移动应用 appid，见 §5/§6**） |
| Apple 登录 | `sign_in_with_apple` |
| 挥杆视频 | `image_picker` + `video_compress` + `video_player` |
| 分享/跳转/权限 | `share_plus` `url_launcher` `permission_handler` |
| 国际化/时间 | `intl` |
| 图片缓存 | `cached_network_image` |
| 图表(报告雷达图等) | `fl_chart`（对应现有 RadarChart/ProgressLineChart 的 `.rn.tsx`） |

### 2.3 主题（视觉 1:1 的关键）

- 把 `client/src/app.scss` 的四色体系搬成 `theme/brand_colors.dart`：
  `primary #1a237e` / `gold #c9a227` / `accent-mint #00d084` / 文本三级 / bg / border / 语义色。
- 圆角、阴影、字号阶梯（`--radius-*`、`--font-size-*`）→ 常量类。
- rpx→dp：Flutter 用逻辑像素，定义 `rpx(n) = n / 750 * screenWidth` 辅助函数（同现有 `rnScale.ts` 思路）。

### 2.4 多环境

- `.env`（dev/staging/prod）对齐 `client/.env.*`；生产 `API_BASE=https://api.birdieai.cn/v1`。
- `--dart-define` 注入环境；保留 EnvBadge 等价物（非 prod 显示环境角标）。

---

## 3. 逻辑迁移清单（TS → Dart，~11,600 行）

> 原则：**逐文件 1:1 对照翻译**，不重新设计业务逻辑；行为以现有 TS 为准，交叉核对 `docs/02`。

| 源（client/src） | 目标（app/lib） | 难点/备注 |
|---|---|---|
| `services/request.ts` | `core/api_client.dart` | JWT 注入、401 处理、错误码归一、间歇失败提示文案（`describeIntermittentRequestFailure`） |
| `store/userStore.ts` | `features/auth/auth_controller.dart` | 微信登录(fluwx)、onboarding 状态、quota、登出重置 |
| `store/chatStore.ts` | `features/coach/chat_controller.dart` | **SSE 流式**（stream 解析 delta、streaming/errored 三态、取消、重试） |
| `store/analysisStore.ts` | `features/analysis/analysis_controller.dart` | 视频上传、状态轮询、报告软删除档位 |
| `services/*.ts`（29 个） | `data/repositories/*.dart` | 按域归组（analysis/chat/coach/courses/meetup/pros/profile/payment…） |
| `types/*.ts` | `data/models/*.dart` | DTO + `fromJson/toJson`（手写或 `json_serializable`） |
| `utils/*.ts` | `core/utils/*.dart` | storage/track/format 等 |
| `adapters/*.ts` | 直接用 Flutter 原生能力替代 | share/safeArea/vibrate/camera 等 |

### 三个硬骨头（建议 M0/M1 早验证）

1. **SSE 流式对话**：`http` 的 `Client().send(Request)` 拿 `response.stream`，手写 `data:` 行解析；对照 chatStore 的 delta/结束/错误协议。
2. **微信登录 fluwx**：移动端要**微信开放平台「移动应用」**（与小程序 appid 不同）+ Universal Link；未就绪前先做 mock 登录（对齐后端 `WECHAT_MOCK_LOGIN`）。
3. **挥杆视频**：`image_picker` 拍摄/选择 → `video_compress` 压缩 → 分片/直传 COS → 触发分析。注意视频质量与挥杆识别的权衡（前期沿用现有 precheck 逻辑）。

---

## 4. 页面复刻顺序（60 页分批，按 C 端关键路径）

> 每页做法：打开小程序对应页取色/间距/字号（SCSS 为源），用 Flutter widget 复刻；先 iOS 真机比对。

- **P0 地基**：`splash` → `consent` → `login` → `onboarding`（+ 主题/api/auth 骨架）
- **P1 核心闭环**（先能用起来）：`index`(首页) → `analysis/capture`(拍摄) → `analysis/waiting` → `analysis/report`(报告) → `analysis/select-swing` `params` `history`
- **P2 AI 教练**：`coach/index`(流式对话) → `profile/chat-history`
- **P3 训练 + 我的**：`training/index` → `profile/index` + `settings` `edit` `clubs` `membership` `about` `account-deletion` `feedback`
- **P4 长尾**（教练端/社交/内容）：`courses/*` `pros/*` `meetup/*` `coach/*`（教练侧管理）、`analysis/compare` `pro-compare` `poster` `legal/*` `help/*`

---

## 5. 需要你拍板的前置项

| # | 决策 | 建议 |
|---|---|---|
| 1 | iOS 优先还是 iOS+Android 同步 | **iOS 优先**（真机已在用），Android 在 P1 后并入 |
| 2 | 微信登录：现在就接 fluwx，还是先 mock | **先 mock**（后端已有 mock 登录），并行去申请移动应用 appid |
| 3 | 状态管理：`provider` vs 纯 ChangeNotifier（照抄 xiangye） | **provider**（DX 更好、社区标准） |
| 4 | Taro-RN 资产：立即删 vs 冻结 | **冻结**，核心闭环跑通后再清 |
| 5 | 里程碑投入：全职 vs 兼顾小程序 | 影响排期（下方为单人全职估算） |

## 6. 里程碑（单人全职粗估）

| 里程碑 | 内容 | 估时 |
|---|---|---|
| **M0** | 工程+主题+api_client+auth 骨架；真机跑通（mock）登录→首页空壳 | ~0.5 周 |
| **M1** | P1 核心闭环：拍摄→上传→分析→报告 可用 | ~1.5 周 |
| **M2** | P2 AI 教练流式对话 | ~1 周 |
| **M3** | P3 训练 + 我的及子页 | ~1 周 |
| **M4** | P4 长尾（教练端/社交/内容） | ~2–3 周 |

> 到「与小程序功能对齐」约 **6–8 周**（视投入与微信资质审核）。核心可体验版（M0–M2）约 **3 周**。

## 7. 风险

- **微信移动应用资质审核**有时间成本 → 用 mock 登录并行推进，不阻塞。
- **SSE / 微信支付 / 视频压缩** 三个硬骨头，M0/M1 各拉一个最小验证。
- 后端 `backend/`、`ai_engine/` **不受影响**；小程序继续发版。
- 双份 UI 长期维护成本（已知并接受，向野而生同款代价）。

### 7.1 登录 / 支付 / UL 收口状态（App）

| 项 | 状态 | 说明 |
|---|---|---|
| Universal Links / AASA | 仓库已配 | `infra/test/static/apple-app-site-association` + nginx；详见 `infra/deploy/README.md`「App Universal Links」。微信开放平台需登记 `https://api.birdieai.cn/app/`；付费 Team 才可启用 Associated Domains entitlement。 |
| Sign in with Apple | 代码就绪 | 个人免费 Team 无法签发；付费 Team 后复制 `app/ios/Runner/Runner.entitlements.paid.example` → `Runner.entitlements`。 |
| App 正式支付 | 引导小程序 | 会员页 mock 可联调；真实通道引导微信小程序开通（IAP 另排期）。 |
| `pro-compare` | App 已对齐 | 报告页「职业对比」→ `ProComparePage`；依赖后端 `PHASE2_PROS_ENABLED`。 |

---

## 8. 开工第一步（M0，待前置项确认后执行）

1. `flutter create` 建 `app/`，落 §2.1 目录骨架。
2. `theme/brand_colors.dart` + `ThemeData`（四色体系）。
3. `core/api_client.dart`（对照 `request.ts`）+ `.env` 多环境。
4. `features/auth`：mock 登录闭环，真机跑通 consent→login→onboarding→首页空壳。
5. 交付 M0 截图给用户比对观感，再进 P1。
