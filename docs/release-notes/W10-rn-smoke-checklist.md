# W10 React Native App 冒烟 / 内测清单

> ⚠️ **已废弃（2026-07-20）**：Taro-RN 路线已放弃，App 端改用独立 Flutter 工程 `app/`（见 [`docs/22`](../22-App-Flutter独立重写落地计划.md)）。本文档仅作历史归档。

> 与小程序核心链路对齐；真机为主，模拟器为辅。  
> 前置：后端已部署且 `POST /v1/auth/wechat-open-login` 可用；客户端 `TARO_APP_API_BASE_URL` 指向该环境；`TARO_APP_WECHAT_OPEN_APPID` 与开放平台移动应用一致。  
> **分期开工勾选**（M0/M1/Spike/性能）：见 [**`app-m0-m1-kickoff-checklist.md`**](app-m0-m1-kickoff-checklist.md)；本文件为总冒烟表，二者互补。

## 1. 环境与包体

- [ ] iOS：TestFlight 或 Ad Hoc 包可安装；首次打开不闪退。
- [ ] Android：内测 APK/AAB 可安装；权限弹窗符合应用商店说明（相机、相册、网络）。
- [ ] 环境标识：本地/测试 API 域名与小程序测试包一致（避免连错库）。

## 2. 登录与账号

- [ ] 微信授权拉起成功，登录后进入首页或 onboarding（新用户）。
- [ ] 与同一开放平台主体下小程序用户 **unionid 合并**（若后端已配置）：用 App 登录后数据与小程序侧一致。
- [ ] Token 失效后触发重新登录（与小程序行为一致即可）。

## 3. 分析主路径

- [ ] 拍摄/相册选视频（`react-native-image-picker`）→ 参数页 → 上传 → 等待页 → 报告页。
- [ ] 报告视频播放、关键帧/雷达图与小程序一致（允许 UI 像素差）。
- [ ] 弱网/失败提示可理解，可重试。

## 4. AI 教练（SSE）

- [ ] 教练页发送消息，**流式**逐字出现（`sseClient` RN 分支）。
- [ ] 中断、重进会话后历史与小程序一致（依赖同一后端）。

## 5. 会员 / 支付（降级）

- [ ] App 内 **不依赖** 小程序 `wx.requestPayment`；走文档约定（IAP / H5 / 仅展示等）。
- [ ] mock 或沙箱支付流程可完整走通（与当前后端开关一致）。

## 6. 隐私与合规

- [ ] 首次启动展示隐私/用户协议入口（与上架材料一致）。
- [ ] 账号注销入口可到达（与小程序政策一致）。

## 7. 回归对比（与小程序同账号）

任选 2～3 条与小程序交叉验证：登录、一次完整分析、一条教练对话、个人资料只读展示。

## 8. 自动化门禁（CI / 本地 `make test`）与人工项对照

| 清单小节 | 自动化已覆盖 | 仍需人工 |
|----------|--------------|----------|
| 环境与包体能跑通 RN JS | **`make client-check-rn`**（`pnpm build:rn` + 日志门禁 `error src/` / `Unable to resolve`，且 **`pnpm type-check`**）证明 bundle 与 TS 不致静默失败 | App 安装形态（TestFlight / APK）、权限文案、环境与域名配置仍须真机勾选 §1 |
| 登录与 OAuth | **`make backend-test`** 含 **`/v1/auth/wechat-open-login`** 等契约与合并用例（容器内 pytest） | 微信开放平台、`code` 实机授权、Universal Link / Android 签名 §2 |
| 分析主路径 / 雷达 | 构建通过包含报告页占位 **`RadarChart.rn.tsx`**（非 Canvas）；上传链路与 UI 对齐须另测 | 实拍/选片、播放器与雷达「视觉对齐」§3 |
| SSE 教练 | 暂无统一自动化替代 | §4 |
| 支付 | 同上 | §5 |

宿主仓库：首次执行 **`make client-bootstrap-rn-shell`**（或 **`pnpm setup:rn-shell`**）拉取 **`taro-native-shell@0.70.0`** 至 **`client/rn-shell`**。**Pods / `yarn ios` / 开放平台** 不在上述门禁内，详见 **[`client/RN_SHELL.md`](../../client/RN_SHELL.md)**（`rn-shell` 克隆后可能被上游 README 覆盖，以 `RN_SHELL.md` 为准）。
