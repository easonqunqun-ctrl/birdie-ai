# App Store / iOS 账号清单（领翼golf）

> 与向野而生共用组织账号；本应用独立 Bundle ID。  
> Team ID：`H5ZY5QNKRW`（Beijing Siwujie Holdings Co., Ltd.）  
> Bundle ID：`cn.birdieai.birdieApp`  
> 显示名：领翼golf

---

## 工程侧（仓库已对齐）

| 项 | 状态 |
|----|------|
| `DEVELOPMENT_TEAM` | `H5ZY5QNKRW` |
| Sign in with Apple + Associated Domains | `app/ios/Runner/Runner.entitlements` |
| AASA | `H5ZY5QNKRW.cn.birdieai.birdieApp` → `https://api.birdieai.cn/.well-known/apple-app-site-association` |
| 服务端 `APPLE_BUNDLE_ID` | 须为 `cn.birdieai.birdieApp`（勿用旧 `com.xiaoniaoai.app`） |

---

## 你需要在浏览器完成（约 15 分钟）

### 1. 确认用组织账号登录

[developer.apple.com/account](https://developer.apple.com/account) → 顶部应为 **Organization** / Team `H5ZY5QNKRW`（勿选个人 Personal Team）。

### 2. 创建 App ID（若尚未有）

1. [Identifiers](https://developer.apple.com/account/resources/identifiers/list) → **+** → App IDs → App  
2. Description：`Birdie AI`（勿用中文）  
3. Bundle ID（Explicit）：`cn.birdieai.birdieApp`  
4. Capabilities 勾选：
   - **Sign In with Apple**
   - **Associated Domains**
5. Register  

> 向野而生是 `cn.wildism.xiangyeApp`，本 App 是另一条 Identifier，互不覆盖。  
> **2026-08-01**：已在组织 Team `H5ZY5QNKRW` 下创建（Description=`Birdie AI`）。

### 3. Xcode 签名

1. 用组织账号登录 Xcode → Settings → Accounts  
2. 打开 `app/ios/Runner.xcworkspace`  
3. Signing & Capabilities → Team 选 **H5ZY5QNKRW**  
4. 真机/Archive 一次，确认自动描述文件含 Sign in with Apple

### 4. App Store Connect（上架时）

1. [App Store Connect](https://appstoreconnect.apple.com/) → 我的 App → **+** → **新建 App**  
2. 平台：勾选 **iOS**  
3. 名称：`领翼golf`  
4. 主要语言：**简体中文**  
5. Bundle ID：选 `cn.birdieai.birdieApp`（若列表没有，等 Identifier 同步几分钟后再试）  
6. SKU：`birdie-ios-001`  
7. 用户访问权限：**完全访问**  
8. 创建  

> 真机闭环验收：2026-08-02 通过（登录 / 首页 / 拍摄出报告 / 原片播放 / 教练 / 训练）。

### 5. 微信开放平台（真微信登录）— **上线后做**

移动应用 Universal Links：`https://api.birdieai.cn/app/`（与 AASA paths 一致）。  
当前策略：先 TestFlight / 上架，用 **Sign in with Apple**；微信登录后补。

### 6. 打 IPA → TestFlight（当前主线）

前置：§4 App Store Connect 应用已创建。  
**2026-08-02**：ASC 已有应用；IPA **1.0.0+2** 已用 Transporter 上传（含 WechatOpenSDK 90208 修复）。  
下一步见 [`app-store-testflight-next.md`](./app-store-testflight-next.md)。

```bash
cd app
bash scripts/ios-archive.sh
```

或 Xcode：`app/ios/Runner.xcworkspace` → Product → Archive → Distribute App → App Store Connect。

**上传**：用 **Transporter** 拖入 `.ipa`，或 Xcode Organizer → Distribute。  
上传后 ASC → TestFlight 等 Processing（约 5–30 分钟），再加内部测试员。

审核备注可写：登录使用 **Sign in with Apple**；微信登录后续版本提供。

隐私政策 URL（ASC 正式提审必填）：`https://api.birdieai.cn/legal/privacy.html`（仓库 `infra/test/static/legal/privacy.html`，随 CVM nginx 发布）。  
启动图仍是 Flutter 默认占位，建议上架前换成品牌 Launch Image（非阻塞 TestFlight）。

---

## 对照：同公司双 App

| | 向野而生 | 领翼golf |
|--|----------|----------|
| Team | `H5ZY5QNKRW` | 同左 |
| Bundle | `cn.wildism.xiangyeApp` | `cn.birdieai.birdieApp` |
| UL 域名 | `api.wildism.cn` / `www.wildism.cn` | `api.birdieai.cn` |
