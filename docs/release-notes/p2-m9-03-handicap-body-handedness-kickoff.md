# P2-M9-03 · 真实差点 + 身体数据 + 利手 onboarding 2.0 · 启动包（W19 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，扩展 onboarding 从 3 题到 6 题，落地 handicap / body / handedness / injuries 字段链路
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §5.3 · P2-M9-03`](../23-二期可编码规格说明书.md#53-p2-m9-03--真实差点--身体数据--利手字段)
> 前置 kickoff：[`p2-m9-01-user-profiles-v2-kickoff.md`](./p2-m9-01-user-profiles-v2-kickoff.md)（**硬依赖**：`user_profiles_v2` 表 + `privacy_payload` 字段就绪）
> 合规：[`docs/06 §13.1 M9 画像 2.0 新增敏感字段`](../06-数据安全与隐私合规文档.md)

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M9-03 onboarding 2.0**落地一份「**W19 即可起跑（依赖 M9-01 数据模型）、W21 6 题 onboarding 上线**」的客户端 + 后端 SOP，让客户端 + 后端 + 隐私安全明确：

- 一期 3 题 onboarding（level / goals / freq）的现状与"画像太浅"痛点
- onboarding 2.0 6 题扩展（追加 handicap / body / handedness / injuries 4 题）
- 已知伤病字段（敏感等级"高"）二次确认 + LLM 透传禁令
- 每题可跳过（保不流失老用户）+ 任意时间在"画像设置"修改 / 清空

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/06`](../06-数据安全与隐私合规文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不动一期 3 题（level/goals/freq） | 与新 4 题**追加**而非替换 |
| 不实现装备清单题 | M9-02 负责（独立 UI 组件） |
| 不实现目标 / 训练偏好题 | M9-04 负责 |
| 不实现常去球馆题 | M9-05 负责 |
| 不实现教练侧可见性勾选 UI | M9-06 负责 |

> M9-02/04/05 都是"独立题型"，本任务只**复用**一期 onboarding 3 题框架并追加 4 题；M9-04/05/06 在 W22+ 接入同一框架。

### 1.3 与其他文档的关系

```
docs/23 §5.3          ← 需求真源
docs/06 §13.1         ← 已知伤病字段合规（已就位）
docs/01 §3.2          ← 一期 onboarding 文档（待追加 v2.0 增量提示）
p2-m9-01              ← 数据模型 + privacy_payload 5 个 consent
本文件                 ← onboarding UI 6 题流程 + 二次确认 + 隐私链路
  ↓ W21 回流
docs/01 §3.2          ← v2.0 增量
docs/02 §11.3         ← PUT /v1/users/me/profile-v2 接口字段细化
```

---

## 二、现状盘点

### 2.1 一期 onboarding 实际形态

```
client/src/pages/onboarding/index.tsx L11-12
  → Step 1 / 2 / 3，TOTAL_STEPS = 3
client/src/pages/onboarding/index.tsx L33-36
  → canGoNext: step=1 需 level；step=2 需 ≥1 goal；step=3 需 freq
client/src/pages/onboarding/index.tsx L47-70 handleSubmit
  → userService.completeOnboarding({ golf_level, primary_goals, weekly_practice_frequency })
  → /api/v1/users/me PATCH
backend models/user.py L28-31
  → golf_level / primary_goals (JSONB) / weekly_practice_frequency / onboarding_completed
```

**结论**：一期 3 题仅采集**粗粒度**档位（4 档 level）+ 软性偏好（goals），**没有**真实差点、身体数据（影响挥杆建议）、利手（影响左右镜像）、伤病（影响 drill 推荐安全性）。

### 2.2 一期相关代码

| 文件 | 行数 / 要点 | V2 改造 |
| --- | --- | --- |
| `client/src/pages/onboarding/index.tsx` L11-12 | `Step = 1\|2\|3` + `TOTAL_STEPS = 3` | **改造**：`Step = 1..6` + `TOTAL_STEPS = 6` |
| `client/src/pages/onboarding/index.tsx` L77 `handleSkip` | 跳过全部 → onboarding_completed=true | **改造**：单题跳过 + 全部跳过两种 |
| `client/src/services/userService.ts` `completeOnboarding` | PATCH /users/me | **新增** `updateProfileV2(payload)` 走 [`docs/02 §11.3`](../02-API接口设计文档.md) `PUT /v1/users/me/profile-v2` |
| `client/src/constants/golf.ts` | LEVELS / GOALS / FREQS 常量 | **新增** `HANDICAP_RANGES` / `INJURY_OPTIONS` 常量 |
| `client/src/pages/profile/edit.tsx` | 一期"编辑档案" | **改造**：增 4 个新字段编辑入口 |
| `backend/app/api/v1/users.py`（拟） | PATCH /users/me | **新增** `PUT /v1/users/me/profile-v2` 端点 |
| `backend/app/services/user_profile_v2_service.py`（M9-01 已新建） | CRUD + privacy_payload 校验 | **复用** |

### 2.3 已知缺口（vs docs/23 §5.3 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 onboarding 3→6 题 | ❌ 仅 3 题 | UI 改造 + 4 题组件 |
| FR-2 每题可跳过 | 仅"全部跳过" | 每题独立"跳过本题"按钮 |
| FR-3 已知伤病二次确认 | ❌ 无 | 二次 Modal 确认 |
| FR-4 字段写入 `user_profiles_v2.privacy_payload` | ❌ 无 | service 联动 M9-01 |
| FR-5 任意时间可修改 / 清空 | 仅 level/goals/freq 可编辑 | `profile/edit.tsx` 改造 |

---

## 三、模块设计

### 3.1 新增/改造一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| onboarding UI 改造 | `client/src/pages/onboarding/index.tsx` | 6 题流程 + 单题跳过 | 1.5 PD |
| 新题组件 | `client/src/components/onboarding/HandicapStep.tsx` 等 4 个 | handicap / body / handedness / injuries | 2 PD |
| 编辑页改造 | `client/src/pages/profile/edit.tsx` | 4 新字段入口 + 清空操作 | 1 PD |
| 后端 API | `backend/app/api/v1/users.py` | `PUT /v1/users/me/profile-v2` | 1 PD |
| 后端 schema | `backend/app/schemas/user_profile_v2.py`（M9-01 已建） | PATCH 语义 + 部分字段更新 | 0.5 PD |
| 单测 | 客户端 jest snapshot + 后端 pytest | 跳过 / 二次确认 / privacy 校验 | 1 PD |
| LLM grep 单测（AC-3） | `backend/tests/test_llm_no_injury.py` | grep `chat_prompt.py` 渲染输出 | 0.5 PD |

**合计：~7.5 PD**（与 docs/23 §5.3 估时 2 PW 偏宽；6 题 UI + 4 个组件 + 二次确认是工作量主体）

### 3.2 6 题流程

| Step | 题目 | 一期 / 二期 | 字段 | 可跳过 |
| --- | --- | --- | --- | --- |
| 1 | 你目前的高尔夫水平？ | 一期 | `golf_level` | ✅ |
| 2 | 你最想提升的方向？ | 一期 | `primary_goals` | ✅ |
| 3 | 平均练球频率？ | 一期 | `weekly_practice_frequency` | ✅ |
| 4 | **你的差点（可选官方/自评）？** | **二期新** | `handicap_official` / `handicap_self` / `handicap_source` | ✅ |
| 5 | **你的身体数据 + 利手？** | **二期新** | `height_cm` / `weight_kg` / `handedness` | ✅ |
| 6 | **你有已知伤病吗？**（高敏感） | **二期新** | `known_injuries` | ✅（默认跳过） |

> 一期 onboarding 3 题保留位置 1-3；新 4 题位置 4-6。Step 4-5 同时收集 3-4 个相关字段，避免 8+ 题的疲劳感。

### 3.3 各题 UI 草案

#### 3.3.1 Step 4：差点

- 单选 tab：「官方差点」/「自评水平」/「我不太确定，跳过」
- 「官方差点」：数字输入框 -10.0 ~ 54.0 + source dropdown (`rcga` / `usga` / `other`)
- 「自评水平」：滑块 0-36+ 或 5 段（< 10 / 10-18 / 18-25 / 25-36 / 36+）
- "我不太确定" → 跳过本题

#### 3.3.2 Step 5：身体 + 利手

- 三列输入：身高（cm）/ 体重（kg）/ 利手（right / left / switch）
- 任一字段可空（应用层不强校验）
- 跳过本题 → 三字段全空

#### 3.3.3 Step 6：已知伤病（**高敏感**）

- 文案前置警告：「为帮助 AI 教练规避高风险动作，可选填以下信息。**这些数据仅用于训练建议生成，不会出现在 AI 聊天上下文中。**」
- 多选 checkbox：腰部 / 肩部 / 肘关节 / 手腕 / 膝盖 / 髋关节 / 颈部 / 其他
- 提交前 **二次 Modal 确认**："你即将保存 X 项伤病信息，确认提交？" + 「确认」「再考虑下」
- 默认行为：用户没主动点"下一步"则视为跳过

### 3.4 单题跳过 vs 全部跳过

| 操作 | UI 入口 | 行为 |
| --- | --- | --- |
| **单题跳过** | 每题底部"跳过这题"链接 | 当前题字段不入库；进入下一题 |
| **全部跳过** | onboarding 顶部"以后再说"链接（一期已有） | `onboarding_completed=true`；4 个新字段全部空 |
| **完成全部** | Step 6 提交 | 所有非跳过字段入库 + `onboarding_completed=true` |

### 3.5 已知伤病字段隔离（AC-3 硬约束）

**docs/06 §13.1**：`known_injuries` **禁止透传至外部 LLM API**。落地方式：

1. `backend/app/services/chat_prompt.py` 渲染 prompt 时 **不**注入 `known_injuries`
2. 单测 `tests/test_llm_no_injury.py`：构造 user 有 injuries 的场景，调用 `build_chat_context()` → grep 结果文本不含 `known_injuries` 任何枚举值
3. 训练建议生成由 `backend/app/services/training_plan_service.py` 单独读取，仅传给本地 drill 推荐算法，**不**走 LLM

---

## 四、字段 / 配置草案 v0.1

### 4.1 `PUT /v1/users/me/profile-v2` 接口

```
Request: { "handicap_self": 18.5, "handedness": "right", "height_cm": 175, ... }
Response: { "ok": true, "updated_fields": ["handicap_self", "handedness", "height_cm"] }
```

PATCH 语义：仅更新请求体内出现的字段；显式置 null 触发清空。

### 4.2 privacy_payload 联动

每个字段写入时同步更新 `privacy_payload`：

```jsonc
// 用户填了 handicap_self
"handicap_self": 18.5
// 同步更新 privacy_payload.handicap_consent = true

// 用户填了 known_injuries（伤病）
"known_injuries": ["lower_back"]
// 同步更新 privacy_payload.injury_consent = true
```

清空字段时 `consent` 同步置 false。

### 4.3 客户端常量

```ts
// client/src/constants/profileV2.ts（新）
export const HANDICAP_RANGES = [
  { id: 'sub_10', label: '< 10（高手）', value: 8 },
  { id: '10_18', label: '10-18', value: 14 },
  // ...
]
export const INJURY_OPTIONS = [
  { id: 'lower_back', label: '腰部' },
  { id: 'shoulder', label: '肩部' },
  // ...
]
export const HANDEDNESS_OPTIONS = [
  { id: 'right', label: '右手' },
  { id: 'left', label: '左手' },
  { id: 'switch', label: '换手' },
]
```

---

## 五、验证数据

### 5.1 客户端单测

- `pages/onboarding/__tests__/index.test.tsx`：
  - 一期 3 题路径不破坏（向下兼容）
  - 单题跳过 → 当前题字段不入提交 payload
  - 全部跳过 → 4 新字段空
  - Step 6 提交前必出二次 Modal

### 5.2 后端单测

- `tests/test_user_profile_v2_api.py`：
  - PUT 部分字段更新（PATCH 语义）
  - 显式 null 触发清空
  - 显式 null → privacy_payload 对应 consent 置 false

### 5.3 LLM 透传 grep 单测（AC-3 硬门槛）

- `tests/test_llm_no_injury.py`：
  ```python
  user.known_injuries = ["lower_back", "shoulder"]
  ctx = build_chat_context(user, session)
  assert "lower_back" not in ctx
  assert "shoulder" not in ctx
  assert "腰部" not in ctx
  assert "肩部" not in ctx
  ```

### 5.4 onboarding 完成率（NFR ≥40%）

- 埋点：`onboarding_step_{1..6}_completed` / `onboarding_step_{1..6}_skipped` / `onboarding_completed`
- 上线后 2 周采样：6 题全完成率 ≥40%（NFR）
- 单题完成率：Step 1-3 ≥80%（保兼容）；Step 4-6 ≥40%（新题正常跳过率）

---

## 六、W19-W21 周计划

> **硬门槛**：W19 起 M9-01 `user_profiles_v2` 表与 `privacy_payload` 字段就绪。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W19** | 本文件评审；HandicapStep / BodyStep / InjuryStep 组件 design 走查 | ☑ 3 个新题 UI 设计稿；☑ 二次 Modal 文案 review |
| **W20** | onboarding/index.tsx 改造 Step 6 + 3 个新题组件实现；jest 单测 | ☑ 6 题端到端跑通；☑ 单题跳过测试通过 |
| **W21** | 后端 `PUT /v1/users/me/profile-v2` API + privacy_payload 联动；LLM grep 单测；profile/edit.tsx 改造 | ☑ AC-1/2/3/4 全勾；☑ docs/01 §3.2 增量 PR；☑ docs/02 §11.3 字段细化 PR |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 Lead | onboarding UI 改造 + 4 题组件 + edit.tsx 改造 |
| 后端 | profile-v2 API + privacy_payload 联动 + LLM grep 单测 |
| 设计 | 二次 Modal 文案 + 高敏感警告色块走查（走 `app.scss` --color-warning） |
| 隐私 / 合规 | docs/06 §13.1 复核；LLM 透传 grep 测试用例评审 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 老用户上次 onboarding 3 题已完成，二期再弹 6 题被吐槽 | `onboarding_completed=true` 老用户**不**再弹 onboarding；profile/edit.tsx 提示"画像 2.0 4 个新字段，去补全？" |
| R-02 | 已知伤病字段被 LLM 误用引发法律风险 | docs/06 §13.1 硬约束 + grep 单测 + code review checklist |
| R-03 | 6 题流失率过高（完成率 < 30%） | 单题跳过让 onboarding_completed=true 不挂 onsignal；运营文案 A/B |
| R-04 | 利手 = left 对镜像未做端到端验证 | 一期 ai_engine `face_on` 镜像未读 handedness；M7-04 W22 才接入；本任务 W21 只入库不消费 |
| R-05 | 二次 Modal 干扰 UI 体验（用户烦） | 仅 Step 6 伤病字段触发二次确认；其他题无 Modal |

### 7.3 AC 兜底（复述 docs/23 §5.3）

- [ ] **AC-1**：onboarding 6 题，每题可跳过
- [ ] **AC-2**：已知伤病二次确认 UI 生效
- [ ] **AC-3**：已知伤病字段在 LLM prompt 中不出现（grep 单测验证）
- [ ] **AC-4**：修改 / 清空全链路可用

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 | 下游消费 |
| --- | --- | --- |
| P2-M9-01 数据模型 | 消费 `user_profiles_v2` + `privacy_payload` | 数据地基 |
| P2-M9-02 装备清单 | UI 框架可复用 | onboarding Step 7（W22+ 独立） |
| P2-M9-04 目标 + 偏好 | UI 框架可复用 | onboarding Step 8（W22+ 独立） |
| P2-M9-05 常去球馆 | UI 框架可复用 | onboarding Step 9（W22+ 独立） |
| P2-M9-06 教练侧可见 | `coach_visible_fields` 由 M9-06 UI 勾选 | 本任务不涉及 |
| P2-M7-16 LLM 文案 | `handicap_self` / `training_preference` | 文案差异化（W30+） |

### 8.2 老用户迁移策略

- `onboarding_completed=true` 用户：**不**再弹 onboarding，profile/edit.tsx 顶部 banner "补全画像，AI 教练更懂你 →"
- `onboarding_completed=false` 用户（新注册）：W21 上线后直接走 6 题流程
- 灰度：feature flag `phase2_profile_v2_enabled` 控制 banner / 6 题展示，默认 false；W22 起灰度 25% → 100%

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；6 题流程 + 二次 Modal + LLM grep 单测 + 老用户迁移策略 |
| v0.2 | W21 收尾 | docs/01 §3.2 / docs/02 §11.3 回流后；本文件 superseded |
