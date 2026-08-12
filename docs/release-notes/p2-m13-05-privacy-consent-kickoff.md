# P2-M13-05 · 隐私授权链路（位置 / 性别 / 差点段独立可控）· 启动包（W28 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.5`](../23-二期可编码规格说明书.md#95-p2-m13-05--隐私授权链路位置--性别--差点段独立可控)
> 前置：DEP-05 法律意见书

---

## 一、文档目的与边界

为 **P2-M13-05** 落地 W28-W31 客户端 + 后端 + 法务 SOP，强弹隐私授权 3 个独立 toggle。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不允许跳过弹窗（合规硬约束）

---

## 二、现状盘点

- M9-01 user_profiles_v2.privacy_payload 已就位
- 一期无 M13 强弹窗

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造 + 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 弹窗组件 | `components/MeetupPrivacyConsent.tsx`（新） | 0.5 PW |
| 首次进入校验 | `pages/meetup/index.tsx` 检查 privacy_payload | 0.3 PW |
| privacy_payload 扩 | 加 location_consent / gender_consent / handicap_consent | 0.3 PW |
| 设置页 | `pages/profile/privacy/index.tsx` 加 M13 三项 | 0.4 PW |
| 单测 | tests | 0.3 PW |
| 法务协同 | 协议条款 review | 0.2 PW |

**合计：~2 PW**

### 3.2 弹窗 UI

```tsx
<MeetupPrivacyConsent>
  [✓] 位置 — 用于匹配同城球友（未授权将无法找球友）
  [✓] 性别 — 用于女性同性匹配选项（默认对陌生人不展示）
  [✓] 差点段 — 用于推荐同水平球友（不展示精确数值）
  [同意并继续]
</MeetupPrivacyConsent>
```

### 3.3 未授权降级

| 字段 | 未授权 → |
| --- | --- |
| location_consent | 匹配返 40330 |
| gender_consent | 默认不区分性别（女用户可主动选"仅同性"） |
| handicap_consent | 匹配宽松（任意差点段） |

### 3.4 撤回

设置页随时调整；变更 ≤500ms 生效。

---

## 四、字段 v0.1

```python
# user_profiles_v2.privacy_payload 追加
{
  "location_consent": false,
  "gender_consent": false,
  "handicap_consent": false,
  "gender_preference": "any" | "same" | "coach_only",
  "consent_granted_at": "..."
}
```

---

## 五、验证数据

- 强弹窗首次（AC-1）
- 法务签字（AC-2）
- 撤回生效（AC-3）

---

## 六、W28-W31 周计划

| 周 | 任务 |
| --- | --- |
| W28 | 法务协议 review |
| W29 | 弹窗 + 校验 |
| W30 | 设置页 + 单测 |
| W31 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 法务 | DEP-05 + 协议 |
| 客户端 | 弹窗 + 设置 |
| 后端 | privacy_payload |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 法务延期 | 协议先用通用模板；上线前必到位 |
| R-02 | 用户全选"否"无法用 | 引导式文案；可后修改 |
| R-03 | 弹窗疲劳 | 仅首次强弹；后续设置页 |

### AC

- [ ] AC-1 强弹窗
- [ ] AC-2 法务签字
- [ ] AC-3 撤回生效

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M9-01 privacy_payload | 数据基础 |
| P2-M13-03 匹配 | consent 校验 |
| DEP-05 法务 | 协议 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
