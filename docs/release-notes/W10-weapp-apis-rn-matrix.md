# W10 微信小程序能力 vs RN（Taro）对照

> 范围：`client/src` 内实际用到的能力 + 注释中的 `wx.*` 语义。  
> **策略**：RN 优先用 `adapters/*`、同构 `Taro.*`（若 Taro RN 已实现）、或产品降级（支付/订阅消息等）。

| 能力 / API（小程序侧） | 代码入口或说明 | RN 处理方式 |
|------------------------|----------------|-------------|
| `wx.login` / `Taro.login` | `adapters/login.ts` | `react-native-wechat-lib` + `POST /v1/auth/wechat-open-login` |
| `wx.chooseMedia`（视频） | `adapters/media.ts`，`capture.tsx` 经 adapter | `react-native-image-picker` |
| 隐私：`getPrivacySetting` / `requirePrivacyAuthorize` | `utils/privacy.ts` | 仅 weapp；RN 无操作（no-op） |
| `Taro.request`（含 401、toast） | `services/request.ts` | 同构；域名换 RN 网络配置 |
| `Taro.request` + `enableChunked`（SSE） | `utils/sseClient.ts` | RN 使用 `XMLHttpRequest` + `onprogress` 分支 |
| `Taro.uploadFile` | `analysisService.ts`、`mediaCheck.ts` | 同构；注意本地文件 URI |
| `Taro.downloadFile` | `pages/analysis/report.tsx` | RN 可用同接口或降级为 expo/fs（按 Taro RN 运行时） |
| `Taro.requestPayment` | `pages/profile/membership.tsx` | **降级**：IAP / 其它渠道（见白皮书 §8） |
| `Taro.requestSubscribeMessage` | `pages/analysis/waiting.tsx` | **降级**：改用 App 推送或引导去小程序 |
| `wx.getSystemInfoSync` / 窗口信息 | `RadarChart.tsx`、`sdkVersion.ts` | Taro RN 对等 API 或降级 |
| `Taro.previewImage` | `report.tsx` | RN：第三方图片预览或暂占位 |
| `Taro.createSelectorQuery` | `RadarChart.tsx` | RN：需替换测量方式或使用 RN 图表 |
| `Taro.createVideoContext` | `report.tsx` | RN：视频组件控制器 API 差异，需逐项测 |
| 剪贴板 `setClipboardData` | `coach/index.tsx`、`invitations.tsx` | `@react-native-clipboard/clipboard`（或由 Taro 封装） |
| `Taro.shareAppMessage` 等分享 | 代码中已禁用/注释场景 | RN：系统分享或微信 SDK Share（若接） |

**维护**：新增 `wx.` 或仅小程序 API 时，先在本表补一行再在 `adapters/` 或页面做分叉。
