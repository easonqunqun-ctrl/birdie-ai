# TestFlight → 提审下一步（领翼golf）

> 更新：2026-08-03  
> Bundle：`cn.birdieai.birdieApp` · Team：`H5ZY5QNKRW` · 构建：1.0.0+3（production，无环境角标；含出口合规 plist）

## A. TestFlight（上传完成后）

1. [App Store Connect](https://appstoreconnect.apple.com/apps) → **领翼golf** → **TestFlight**
2. 确认 iOS 构建 **3** 状态为 **Ready to Test**（Processing 通常 5–30 分钟）
3. **内部测试** → 添加自己的 Apple ID → 在 iPhone 安装 **TestFlight** → 安装「领翼golf」
4. 再验：Sign in with Apple → 拍杆出报告 → AI 教练 / 训练（右上角不应再有 staging 角标）

## B. 提审前元数据（ASC「App 信息 / 准备提交」）

| 字段 | 建议填写 |
|------|----------|
| 隐私政策 URL | `https://api.birdieai.cn/legal/privacy.html` |
| 支持 URL | `https://api.birdieai.cn/`（或官网就绪后改） |
| 类别 | 健康健美 / 体育（择一） |
| 登录说明 | 使用 **Sign in with Apple**；无需额外测试账号 |
| 审核备注 | 微信登录将在后续版本提供；当前请用 Sign in with Apple。挥杆分析需拍摄或从相册选择视频。 |
| App 隐私问卷 | 收集：用户 ID、照片/视频、产品交互、（若开启）粗略位置；用途按「App 功能」勾选 |

截图：至少 6.5"/6.7" 一组（首页、报告、教练、训练）。

## B2. 出口合规（选构建时若灰掉「完成」）

构建旁黄字 **「缺少出口合规证明」** 时：

1. 点「取消」关掉弹窗  
2. 顶部切到 **TestFlight** → 点构建 **2**（或「管理」出口合规）  
3. 问卷建议（本 App 仅 HTTPS / Sign in with Apple / 系统 TLS）：  
   - 是否使用加密？→ **是**（或按界面选「仅使用豁免加密」）  
   - 是否属于豁免？→ **是**（标准加密，非自研算法）  
4. 保存后回到 **App Store → 1.0 准备提交 → 添加构建版本**，选 2，「完成」应可点  

工程侧已在 `Info.plist` 加 `ITSAppUsesNonExemptEncryption=false`，**下一 build** 可自动跳过此问卷；**当前 build 2 仍须在 ASC 手填一次**。

## C. 提交审核

TestFlight 内测无阻后 → **App Store** 页创建版本 1.0.0 → 选构建 2 → 填写上述字段 → **提交以供审核**。

## D. 后置

- 微信开放平台移动应用 UL（真微信登录）
- 替换默认 Launch Image
