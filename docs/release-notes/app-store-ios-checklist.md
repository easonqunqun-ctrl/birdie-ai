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

---

## 你需要在浏览器完成（约 15 分钟）

### 1. 确认用组织账号登录

[developer.apple.com/account](https://developer.apple.com/account) → 顶部应为 **Organization** / Team `H5ZY5QNKRW`（勿选个人 Personal Team）。

### 2. 创建 App ID（若尚未有）

1. [Identifiers](https://developer.apple.com/account/resources/identifiers/list) → **+** → App IDs → App  
2. Description：`领翼golf` / `Birdie Golf`  
3. Bundle ID（Explicit）：`cn.birdieai.birdieApp`  
4. Capabilities 勾选：
   - **Sign In with Apple**
   - **Associated Domains**
5. Register  

> 向野而生是 `cn.wildism.xiangyeApp`，本 App 是另一条 Identifier，互不覆盖。

### 3. Xcode 签名

1. 用组织账号登录 Xcode → Settings → Accounts  
2. 打开 `app/ios/Runner.xcworkspace`  
3. Signing & Capabilities → Team 选 **H5ZY5QNKRW**  
4. 真机/Archive 一次，确认自动描述文件含 Sign in with Apple

### 4. App Store Connect（上架时）

1. [App Store Connect](https://appstoreconnect.apple.com/) → 我的 App → **+**  
2. 名称：`领翼golf`  
3. Bundle ID：选 `cn.birdieai.birdieApp`  
4. SKU 建议：`birdie-ios-001`

### 5. 微信开放平台（真微信登录）

移动应用 Universal Links：`https://api.birdieai.cn/app/`（与 AASA paths 一致）。

---

## 对照：同公司双 App

| | 向野而生 | 领翼golf |
|--|----------|----------|
| Team | `H5ZY5QNKRW` | 同左 |
| Bundle | `cn.wildism.xiangyeApp` | `cn.birdieai.birdieApp` |
| UL 域名 | `api.wildism.cn` / `www.wildism.cn` | `api.birdieai.cn` |
