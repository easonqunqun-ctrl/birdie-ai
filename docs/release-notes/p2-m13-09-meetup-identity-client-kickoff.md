# P2-M13-09 · 约球实名认证（客户端补齐）· 产品设计

> 版本：v0.1（2026-05-29）  
> 上游真源：[`docs/legal/tos-m13.md`](../legal/tos-m13.md) · [`docs/02` §5C.4](../02-API接口设计文档.md#5c4-约球合规m13-09)  
> 可编码规格：[`docs/23` §9.1](../23-二期可编码规格说明书.md#91-p2-m13-09--约球实名与协议)  
> 关联缺口：后端 M13-09 守门已上线（40332/40333/40334），**客户端缺实名采集页**，导致「常去球馆 · 添加附近球馆」与「约球邀请」在正式环境不可用。

---

## 一、背景与问题

### 1.1 现状

| 层 | 状态 |
|----|------|
| 协议 / 法务 | [`tos-m13.md`](../legal/tos-m13.md) 已定义：14 岁+、手机号实名、同意增量协议 |
| 后端 | `users.birth_date` / `phone_verified_at` + `ensure_meetup_access` 已守门；`GET /meetups/safety/status` 可查询 |
| 客户端 | 仅有 `MeetupTosModal`（约球协议）；**无**微信手机号授权 + 生日采集 UI |
| 开发兜底 | `POST /meetups/safety/mock-identity` 仅 `WECHAT_MOCK_LOGIN=true` |

### 1.2 用户可见症状

1. **我的 → 常去球馆 → 添加附近球馆**：定位成功后调 `GET /venues/nearby`，返回 **40333**「请先完成手机号实名」。
2. **我的 → 约球邀请**：弹出协议窗，点「同意并继续」仍失败（`accept-tos` 前置要求 `identity_eligible`）。

### 1.3 产品决策（本设计确认）

| 决策 | 结论 | 理由 |
|------|------|------|
| 约球是否必须实名 | **是** | 线下见面安全、未成年保护、协议 [`tos-m13` §3](../legal/tos-m13.md) |
| 「附近球馆搜索」是否走同一守门 | **是（维持现状）** | `/venues/nearby` 与约球共用 venue 数据与合规域；避免未实名用户绕过约球限制仅搜馆 |
| 是否允许只填生日、暂不绑手机 | **否** | 与协议「手机号实名」不一致 |
| 未满 14 岁 | **硬拦截**，不提供监护人流程（v0.1） | 与现有 40332 一致；监护人流程见 [`docs/06` §5.2](../06-数据安全与隐私合规文档.md) backlog |

---

## 二、用户价值与范围

### 2.1 用户价值

- 完成一次实名 + 协议后，可正常使用：**约球邀请**、**附近球馆添加**、**约球活动**等 M13 能力。
- 流程清晰：知道「为什么要实名」「在哪里完成」「完成后再做什么」。

### 2.2 边界（不做）

- **不做** 身份证 OCR / 人脸核身（超出小程序约球 v0.1 范围）。
- **不做** 在 App 内展示完整手机号（仅脱敏「138****5678」可选）。
- **不拆** `/venues/nearby` 守门（若产品后续要「常去球馆免实名」，单独立项改 API 策略）。
- **不改** 挥杆分析 / AI 教练 / 训练等 **非 M13** 链路（不要求实名）。

---

## 三、合规状态机

后端已有字段，客户端按下列顺序引导：

```
                    ┌─────────────────┐
                    │  进入 M13 功能   │
                    └────────┬────────┘
                             │
                             ▼
              GET /meetups/safety/status
                             │
         ┌───────────────────┼───────────────────┐
         │ identity_eligible │                   │
         │ = false           │ = true            │
         ▼                   ▼                   │
  ┌──────────────┐   meetup_tos_accepted?       │
  │ 实名认证页    │         │                    │
  │ (本设计新增)  │    false│ true               │
  └──────┬───────┘         ▼                    ▼
         │          MeetupTosModal         正常使用 M13
         │          (已有)
         ▼
  POST verify-identity
  (birth_date + phone_code)
         │
    ┌────┴────┐
    │ age<14  │ → 40332 拦截页（不可继续）
    └────┬────┘
         ▼
  回到 status；若仍缺 TOS → 弹协议
```

**`can_use_meetup`** = `identity_eligible` ∧ 已同意 TOS（与现后端一致）。

---

## 四、入口与拦截

### 4.1 主动入口

| 入口 | 路径 | 说明 |
|------|------|------|
| 约球合规中心 | **我的 → 约球合规**（新增菜单项，`PHASE2_MEETUP_ENABLED` 时展示） | 展示状态：实名 / 年龄 / 协议；未完成项可点击继续 |
| 约球邀请 | `pages/meetup/index` | `checkSafety` 时若 `!identity_eligible` → **跳转实名页**（不再只弹 TOS） |
| 常去球馆 | `pages/profile/favorite-venues` | 捕获 **40333 / 40332 / 40334**，按码引导实名页或协议弹窗 |

### 4.2 错误码 → 用户动作

| code | 文案（后端） | 客户端动作 |
|------|--------------|------------|
| 40333 | 请先完成手机号实名 | `navigateTo` 实名认证页 |
| 40332 | 14 岁以下不开放约球功能 | 展示 **拦截说明页**（返回上一页） |
| 40334 | 请先阅读并同意约球服务协议 | 打开 `MeetupTosModal` |

---

## 五、页面设计 · 实名认证

**路由**：`pages/meetup/identity-verify`（三件套 + `app.config` 登记）

### 5.1 信息架构

```
┌─────────────────────────────────────┐
│  ←  约球安全验证                      │
├─────────────────────────────────────┤
│  为保障线下约球安全，使用约球、         │
│  附近球馆等功能前需完成验证。           │
│                                     │
│  · 年满 14 周岁                       │
│  · 绑定本人微信手机号                   │
│                                     │
│  详见《约球功能服务须知》               │
├─────────────────────────────────────┤
│  出生日期 *                           │
│  ┌─────────────────────────────┐   │
│  │  请选择（Picker date）        │   │
│  └─────────────────────────────┘   │
│  用于确认是否满 14 岁，不会公开展示。    │
├─────────────────────────────────────┤
│  微信手机号 *                         │
│  ┌─────────────────────────────┐   │
│  │  微信授权手机号（Button）      │   │
│  │  open-type="getPhoneNumber"   │   │
│  └─────────────────────────────┘   │
│  仅用于实名与账号安全，不用于营销。      │
├─────────────────────────────────────┤
│  ┌─────────────────────────────┐   │
│  │         提交验证              │   │  主 CTA · var(--color-primary)
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 5.2 交互规则

1. **出生日期**：必填；Picker 上限 = 今天 − 14 年（减少误选未成年）；下限合理即可（如 1940-01-01）。
2. **手机号**：用户须点击 **微信授权按钮**；`getPhoneNumber` 返回 `code` 暂存组件 state；未点授权则提交时 toast「请先授权微信手机号」。
3. **提交**：`POST /v1/meetups/safety/verify-identity`（见 §七）；成功 toast「验证成功」。
4. **成功后**：
   - 若 `redirect` query 存在 → 回跳来源页并 **自动重试** 原动作（如拉附近球馆）；
   - 否则若 `!can_use_meetup` → 展示/跳转协议流程；
   - 否则 `navigateBack`。
5. **40332**：服务端校验年龄后返回；页内展示红色说明 + 「返回」按钮，**不**提供申诉入口（v0.1）。

### 5.3 视觉

- 遵循 [`client/src/app.scss`](../client/src/app.scss) CSS 变量；主按钮靛蓝底白字。
- 说明文案使用 `--color-text-secondary`；禁止硬编码品牌 HEX。

---

## 六、页面设计 · 约球合规中心（可选 v0.1 简版）

**路由**：`pages/meetup/safety` 或在 `pages/profile/settings` 增加区块（推荐 **独立页**，便于从拦截 deep link）。

| 状态项 | 展示 | 未完成时 |
|--------|------|----------|
| 手机号实名 | ✓ 已验证 / 未完成 | 去验证 → identity-verify |
| 年龄 | ✓ 已满 14 岁 / 不符合 | 拦截说明 |
| 约球协议 | ✓ 已同意 yyyy-mm-dd / 未同意 | 打开 MeetupTosModal |
| 匹配偏好 | 当前偏好 | 跳转偏好设置（复用 Modal 内选项或 PATCH preferences） |

---

## 七、API 增量（待实现，契约先写 docs/02）

### 7.1 提交实名

```
POST /v1/meetups/safety/verify-identity
Authorization: Bearer …
Content-Type: application/json

{
  "birth_date": "1990-05-01",
  "phone_code": "<getPhoneNumber 返回的 code>"
}
```

**成功** `200`：`data` 同 `MeetupSafetyStatus`（`identity_eligible=true` 等）。

**失败**：

| code | 场景 |
|------|------|
| 40052 | 参数非法（日期格式、缺 code） |
| 40332 | 计算年龄 &lt; 14 |
| 502xx | 微信换号失败（code 过期等） |

**服务端处理（设计要点）**：

1. 调微信「手机号快速验证」接口，用 `phone_code` 换取手机号。
2. 写入 `users.birth_date`；设置 `users.phone_verified_at = now()`。
3. 手机号存储：**加密落库** `phone_number_enc`（新增列，Alembic）或仅保留 hash + last4（见 [`docs/06`](../06-数据安全与隐私合规文档.md)）；**禁止**明文日志。
4. 若用户已验证过，重复提交：**幂等**更新生日（不允许随意改小年龄绕过）——生日仅允许首次设置，后续改生日需客服（v0.1 禁止客户端改）。

### 7.2 现有接口（不变）

- `GET /meetups/safety/status` — 客户端门禁真源
- `POST /meetups/safety/accept-tos` — **仍要求**先 `identity_eligible`

---

## 八、微信与隐私配置

| 项 | 动作 |
|----|------|
| `app.config` | 增加 `requiredPrivateInfos: ['getPhoneNumber']`（与已有 `getLocation` 并存） |
| 公众平台隐私指引 | 勾选 **手机号**，用途：「约球功能实名验证与账号安全」 |
| 运行时 | 调 `getPhoneNumber` 前 `ensurePrivacyAuthorized('getPhoneNumber')`（`utils/privacy.ts`） |
| 用户协议 | [`privacy.tsx`](../client/src/pages/legal/privacy.tsx) 增量说明收集生日与手机号的目的与保存期限 |

同步更新 [`docs/06` §6.1](../06-数据安全与隐私合规文档.md)。

---

## 九、客户端模块划分

| 模块 | 路径 | 说明 |
|------|------|------|
| Service | `services/meetupSafetyService.ts` | 新增 `verifyIdentity({ birth_date, phone_code })` |
| 实名页 | `pages/meetup/identity-verify.{tsx,scss,config.ts}` | 本设计 §五 |
| 合规中心 | `pages/meetup/safety.{tsx,...}` | 本设计 §六（可 Phase 2） |
| 拦截 hook | `utils/meetupGate.ts` | 解析 40332/40333/40334 + status，统一 `navigateTo` |
| 改造 | `favorite-venues.tsx` | nearby 失败走 gate |
| 改造 | `meetup/index.tsx` | `!identity_eligible` 跳实名页，而非只弹 TOS |
| 改造 | `MeetupTosModal.tsx` | 打开前检查 `identity_eligible` |
| 我的 | `profile/index.tsx` | 菜单「约球合规」（`PHASE2_MEETUP_ENABLED`） |
| 单测 | `meetupSafetyService.test.ts` · `meetupGate.test.ts` | 门禁与 service |

**Adapter**：微信 `getPhoneNumber` 按钮逻辑放 `adapters/phone.ts`（与 `location.ts` / `media.ts` 同模式）。

---

## 十、验收标准（AC）

| ID | 场景 | 预期 |
|----|------|------|
| AC-1 | 未实名用户进入约球邀请 | 进入实名页，而非直接协议窗 |
| AC-2 | 完成生日 + 手机号提交 | `status.identity_eligible=true`；40333 消失 |
| AC-3 | 生日对应 &lt;14 岁 | 40332，拦截页，不可进 M13 |
| AC-4 | 实名后未同意 TOS | 弹出 MeetupTosModal；同意后 `can_use_meetup=true` |
| AC-5 | 常去球馆 · 添加附近球馆 | 全流程：定位 → 实名（若缺）→ 协议（若缺）→ 列出附近馆 |
| AC-6 | 已实名用户 | 不重复弹手机号授权（除非服务端未验证） |
| AC-7 | mock 登录 | 现有 `mock-identity` 仍可用，不破坏 CI |

---

## 十一、排期建议

| 阶段 | 内容 | 估算 |
|------|------|------|
| **R0** | 后端 `verify-identity` + 微信换号 + Alembic 手机加密列 | 1–1.5 PW |
| **R1** | 客户端实名页 + gate 改造 + 单测 | 1 PW |
| **R2** | 合规中心页 + 隐私文案 + 公众平台配置 + 真机 smoke | 0.5 PW |

**依赖**：微信公众平台开通「手机号快速验证」组件能力；体验版须更新 `requiredPrivateInfos`。

---

## 十二、风险

| ID | 风险 | 缓解 |
|----|------|------|
| R-01 | 微信 getPhoneNumber 需企业主体与认证 | 上线前在公众平台确认能力已开 |
| R-02 | 用户不愿绑手机 | 产品文案说明仅 M13 需要；核心挥杆分析不受影响 |
| R-03 | 生日自报不实 | v0.1 接受；严重纠纷留客服与法务升级路径 |
| R-04 | 与定位实名混淆 | 拦截文案区分「微信账号实名」vs「位置权限」 |

---

## 十三、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-29 | 初版：补齐 M13-09 客户端产品设计，明确与常去球馆共用守门 |
