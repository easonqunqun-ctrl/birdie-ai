# P2-M14-02 · App Store 上架（含审核物料 / 隐私清单） · 启动包（W38 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §10.2`](../23-二期可编码规格说明书.md#102-p2-m14-02--app-store-上架含审核物料--隐私清单)
> 前置：M14-01 完成 + DEP-04 法务

---

## 一、文档目的与边界

为 **P2-M14-02** 落地 W38-W42 RN 工程 + 产品 + 法务 SOP，让 iOS 用户 3 天内可下载，并按 iOS 14.5+ ATT 框架展示隐私授权弹窗。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不做 Apple IAP（→ M14-04）

---

## 二、现状盘点

- 公司 Apple Developer 账号需注册（DEP-04）
- 一期已有 docs/06 隐私协议
- 一期 ATT 框架未实现（小程序无此概念）

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 任务清单

| 任务 | 责任 | 工程量 |
| --- | --- | --- |
| Apple Developer 注册 | 法务 + 产品 | 0.5 PW |
| 审核物料（图标 / 截图 / 描述 中英） | 产品 + 设计 | 1 PW |
| PrivacyInfo.xcprivacy（对齐 docs/06） | RN 工程 + 法务 | 1 PW |
| ATT 框架 | RN 工程 | 0.5 PW |
| Apple 审核团队预沟通 | 产品 + 法务 | 0.5 PW |
| 拒因预案 + 复审 | 产品 + RN 工程 | 1.5 PW |

**合计：~5 PW**

### 3.2 PrivacyInfo.xcprivacy 清单（对齐 docs/06）

```xml
<key>NSPrivacyCollectedDataTypes</key>
<array>
  <dict>
    <key>NSPrivacyCollectedDataType</key>
    <string>NSPrivacyCollectedDataTypePhoneNumber</string>
    <key>NSPrivacyCollectedDataTypeLinked</key>
    <true/>
    <key>NSPrivacyCollectedDataTypePurposes</key>
    <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
  </dict>
  <!-- ... user_profiles_v2 / video / 位置 等 -->
</array>
```

### 3.3 ATT

```objc
[ATTrackingManager requestTrackingAuthorizationWithCompletionHandler:^(ATTrackingManagerAuthorizationStatus status) {
  // 拒绝 → 第三方追踪 SDK 不上报 IDFA
}];
```

### 3.4 常见拒因预案

| 拒因 | 预案 |
| --- | --- |
| 4.3 重复 App | 中英差异化截图 / 描述 |
| 5.1.1 隐私 | PrivacyInfo + 协议中文版置顶 |
| 3.1.1 引导外部支付 | M14-04 跳转话术法务签字 |
| 1.1 内容安全 | M8-08 审核流程展示 |
| 5.1.2 健康类敏感 | 高尔夫定位为体育，避免医疗用语 |

---

## 四、字段 v0.1

- 无新接口 / 数据模型

---

## 五、验证数据

- 包通过审核（AC-1）
- 3 天内可下载（AC-2）
- 隐私清单准确（AC-3）

---

## 六、W38-W42 周计划

| 周 | 任务 |
| --- | --- |
| W38 | DEP-04 注册账号 + 物料制作 |
| W39 | PrivacyInfo + ATT 实现 |
| W40 | 苹果团队预沟通 + 首次提审 |
| W41 | 复审 / 拒因修复 |
| W42 | Phased Release 10% → 50% |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| RN 工程 | 包 / PrivacyInfo / ATT |
| 产品 | 物料 + 预沟通 |
| 法务 | DEP-04 + 协议 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 首次被拒 | 预留 ≥2 轮复审 |
| R-02 | DEP-04 延期 | 提前 W36 启动注册 |
| R-03 | 引导外部支付被拒（M14-04） | 法务 + 预沟通双签 |
| R-04 | 健康敏感 | 文案 / 截图避免医疗用语 |

### AC

- [ ] AC-1 审核通过
- [ ] AC-2 3 天可下载
- [ ] AC-3 隐私清单准确

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| M14-01 | 前置 |
| M14-04 | IAP 决策 |
| docs/06 §13.5 | 隐私同步 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
