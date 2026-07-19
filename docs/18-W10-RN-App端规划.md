# W10 · RN App（与小程序对齐）落地规划

> 版本：v1.1  
> 日期：2026-05-03（v1.1 · 2026-07-20 增开工清单指针）  
> 前置：W8 小程序闭环、W9 正式上线（可按阶段并行）；详细工程任务见下文「链接」与本仓库实现。  
> **开工勾选真源**：[release-notes/app-m0-m1-kickoff-checklist.md](./release-notes/app-m0-m1-kickoff-checklist.md)（M0 / 帧率 Spike / M1 / 性能三项；挂 `docs/19` **Q-D1**）。

---

## 1. 文档目的

在 **不改变小程序为第一载体** 的前提下，用 **同一套 `client/` 业务源码**（Taro 3 + React Native）补齐 **原生 App**，与小程序 **功能与后端契约对齐**。

**执行顺序**：先按 [app-m0-m1-kickoff-checklist](./release-notes/app-m0-m1-kickoff-checklist.md) 完成 M0→M1（iOS 优先、支付降级），再开 [多语言计划](./release-notes/app-i18n-market-plan.md) 与 Q-D2 弹道。

---

## 2. 微信小程序侧已达成基线（App 对标）

以下内容自 W8 起已在小程序链路落地，RN 端口需逐项验收同一业务结果（交互形态可等价替换）：

- 合规：首启《用户协议》+《隐私政策》拦截；微信小程序隐私授权链路（仅限 `weapp`，App 改用系统权限 + 文案对齐）。
- 登录：真实 `wx.login` + `/v1/auth/wechat-login`。
- 核心链路：拍摄/选视频、分析、报告（含分享到好友/朋友圈钩子）、SSE 对话、训练与打卡、`/v1/events` 埋点、视频首帧经 `/v1/security/media-check` 预检。
- 功能开关：`TARO_APP_PAYMENT_*`（内测下架支付入口等与 W8/W9 对齐）。

详见 [16-W8任务拆分.md](./16-W8任务拆分.md)。

---

## 3. App 专有策略（与小程序差异）

### 3.1 登录与账号打通

| 维度 | 小程序 | RN App |
|------|--------|--------|
| 授权 | `jscode2session`（临时 code） | 微信开放平台 **移动应用 OAuth2** |
| OpenID | 小程序 openid → `users.wechat_openid` | App openid → `users.wechat_app_openid` |
| 与子程序同一用户 | 默认同 openid **不可**，须依赖 **unionid** | **须**将小程序与移动应用绑定到 **同一微信开放平台账号**，且服务端按 unionid 合并 |

服务端契约：见 `/v1/auth/wechat-open-login`（参见 [docs/02-API接口设计文档.md](./02-API接口设计文档.md)）。

### 3.2 分享能力降级策略（首版）

- **小程序**：`onShareAppMessage` / `onShareTimeline`，微信卡片与朋友圈入口。
- **App 首版（MVP）**：不追求与微信完全一致；采用 **系统分享面板**（链接/口令/海报图若后续补强）或由产品指定「仅分享到微信会话」时再接 SDK。  
  须在发版说明中明示与小程序分享形态差异。

### 3.3 支付能力降级策略（对齐 W9 节奏）

- **小程序**：微信小程序支付（`requestPayment`，W9 接入）。
- **App**：一般采用 **Apple IAP / Google Play Billing** 或独立商户协议，**≠** 直接复用小程支付参数。  
  W10 首期与 W8/W9 对齐：**沿用 `TARO_APP_PAYMENT_ENABLED=false`** 等产品开关，先在 App **隐藏付费入口**，待单独评审 App  IAP 再接。

---

## 4. 上架合规清单指针（不写死商店政策全文）

以下内容作为工程自检列表，最终以 App Store Connect / Google Play 当期政策为准：

- **iOS**：相册/麦克风/摄像头用途说明（Info.plist）；App Tracking Transparency（若有广告/三方统计）；`Privacy Manifest`/`PrivacyInfo.xcprivacy`（当依赖库要求）；ATS 仅用可信 HTTPS。
- **Android**：运行时权限、`READ_MEDIA`/存储分区策略、`targetSdkVersion` 对应行为变更。
- **隐私**：与用户可见的协议版本号与首页拦截逻辑一致（复用小程序文案源或同一版本常量）。

冒烟与提测步骤见：[release-notes/W10-rn-smoke-checklist.md](./release-notes/W10-rn-smoke-checklist.md)。

---

## 5. OpenAPI ↔ 开放平台配置

环境与密钥（模板见 [.env.example](../.env.example)）：

- `WECHAT_MINIPROGRAM_APPID` / `WECHAT_MINIPROGRAM_SECRET`
- `WECHAT_OPEN_APPID` / `WECHAT_OPEN_SECRET`（移动应用）
- 客户端：`TARO_APP_WECHAT_OPEN_APPID`（仅 RN 编译期注入，`registerApp` 用）

---

## 6. 微信专属 API ↔ RN 等价能力矩阵

见 [release-notes/W10-weapp-apis-rn-matrix.md](./release-notes/W10-weapp-apis-rn-matrix.md)（仓库维护的可 grep 快照）。

---

## 7. App 多语言（第一 + 第二梯队）

> **已入队 · 未开工**（2026-07-20）。小程序仍以简体中文服务大陆；多语言能力落在 **RN App**。

| 项 | 说明 |
|----|------|
| **计划真源** | [`release-notes/app-i18n-market-plan.md`](./release-notes/app-i18n-market-plan.md) |
| **队列 ID** | `docs/19`：**Q-D3** · **I18N-00 / T1-* / T2-*** · **PP-15** · 阶段 **E2** |
| **第一梯队** | `zh-Hans`（App）· **`en`**（美加/英联邦）· **`zh-Hant`**（港澳台/海外华人） |
| **第二梯队** | 日本 `ja` · 韩国 `ko` · 新马（英+中）· 泰国（英/中先发，`th` 后置） |
| **顺序** | **I18N-00 → T1-EN → T1-HANT → T2-SG → JP/KR → TH**（不跳过第一梯队） |
| **门禁** | RN 主链路可内测后开工 T1；**I18N-T1-EN** 过审后再排日/韩深翻 |

工程落地时：客户端 locale 框架与引擎 `locales/*.json`、LLM system prompt 语言包须同步改契约（先改 `docs/02` / 引擎 locale 约定，再写代码）。
