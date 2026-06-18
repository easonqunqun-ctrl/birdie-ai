# P2-M9-05 · 常去球馆字段（M13 约球前置）· 启动包（W23 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.3 期间，落地"常去球馆"字段 + 隐私链路（不调 GPS）
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §5.5 · P2-M9-05`](../23-二期可编码规格说明书.md#55-p2-m9-05--常去球馆字段为-m13-约球前置)
> 前置 kickoff：[`p2-m9-01-user-profiles-v2-kickoff.md`](./p2-m9-01-user-profiles-v2-kickoff.md)（`favorite_course_ids` 字段就绪）
> 合规：[`docs/06 §13.4.1`](../06-数据安全与隐私合规文档.md)（位置/联系信息合规规约）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M9-05** 落地一份「**W23 即可起跑、W25 字段上线 + grep 验证无 GPS 调用**」的客户端 + 后端 SOP：

- 常去球馆字段在 onboarding/画像编辑的 UI 落地
- 球馆数据源来自 M13-02（球馆 / 练习场名录）
- **不**调用微信 `scope.userLocation`（合规硬约束）
- 位置敏感独立同意位 `privacy_payload.location_consent`
- M13 约球入口隐藏 / 提示策略

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22 / docs/23 / docs/06 字段 | 避免与 #18/#19/#20 race |
| 不实现 GPS 定位 | 硬约束（docs/06 §13.4.1） |
| 不实现球馆名录冷启 | M13-02 负责 |
| 不实现 M13 匹配算法 | M13-03 负责 |

---

## 二、现状盘点

### 2.1 一期对位置的处理

- `client/src/` 内**没有**任何 `Taro.getLocation` / `scope.userLocation` 调用（grep 验证）
- 一期产品不涉及"附近球友"等位置类功能
- M13 上线后**首次**引入"位置锚点"，采用"用户手动填常去球馆"策略，规避 GPS

### 2.2 已知缺口（vs docs/23 §5.5 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 画像追加"常去球馆"字段 | ❌ | UI + service |
| FR-2 数据源 M13 venues 表 | ❌（M13-02 W26+） | M13-02 W26 完成后接入 |
| FR-3 `privacy_payload.location_consent` | ❌ | M9-01 已规划字段；本任务联动 |
| FR-4 不调 GPS | ✅ 一期未调 | grep 单测保护 |
| FR-5 用户可清空 / 修改 | ❌ | edit 页 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| Onboarding 题组件 | `client/src/components/onboarding/VenuesStep.tsx`（新） | 多选球馆 | 1 PD |
| Profile 编辑入口 | `client/src/pages/profile/edit.tsx` 改造 | 常去球馆字段 | 0.5 PD |
| 球馆选择组件 | `client/src/components/venues/VenuesPicker.tsx`（新） | 多选 + 搜索（依赖 M13-02 API） | 1 PD |
| 后端 schema | 复用 M9-01 user_profiles_v2 service | `favorite_venue_ids` JSONB 更新 | 0.3 PD |
| LLM/M13 联动 | course_service / M13 service | 字段为空时降级 | 0.5 PD |
| 单测 | grep `scope.userLocation` | AC-2 硬保护 | 0.5 PD |

**合计：~3.8 PD**（与 docs/23 §5.5 估时 2 PW 持平）

### 3.2 VenuesStep 设计

- 顶部："你常去哪个练习场 / 球场？（至少 1 个用于约球匹配）"
- 多选列表：从 `GET /v1/venues?city={user_city}` 取（M13-02 提供）
  - 用户的 city 从 wechat profile 自动获取（小程序基础库），**不**调 GPS
  - 用户也可手动切换城市
- 搜索框：拼音搜索
- 跳过按钮："我没有固定球馆，跳过" → M13 入口提示"先填球馆"

### 3.3 与 M13 约球入口联动

```tsx
// M13 约球入口（W26+）
if (profile.favorite_course_ids.length === 0) {
  return <EmptyState text="先填常去球馆，才能匹配球友" onClick={goToProfileEdit} />
}
```

### 3.4 GPS 调用 grep 保护（AC-2）

```bash
# CI 加 lint：禁止 client/src/ 内引入 Taro.getLocation 或 scope.userLocation
! rg "Taro\.getLocation|scope\.userLocation" client/src/
```

放进 `.github/workflows/client-lint.yml`，触发即 fail。

---

## 四、字段 / 配置草案 v0.1

字段命名约定：`favorite_course_ids` (docs/23 §5.5) / `favorite_venue_ids`（本任务 §3.1 命名）择一。

> **W23 评审时统一**：建议采用 docs/23 拟定的 `favorite_course_ids`。本 kickoff 后续以 docs/23 为准。

### 4.1 API

```
PUT /v1/users/me/profile-v2  Body: { favorite_course_ids: ["vn_xxx", "vn_yyy"] }
```

### 4.2 配置项

```python
PHASE2_PROFILE_V2_ENABLED: bool = False
```

---

## 五、验证数据

### 5.1 单测

- 客户端 jest：VenuesStep 多选 + 跳过
- 后端 pytest：favorite_course_ids 写入 + 清空
- **CI lint**：grep GPS API 调用 → 0 命中（AC-2）

### 5.2 联动测试

- 设置 1 个球馆 → M13 入口可达
- 清空 → M13 入口隐藏 + 引导文案

---

## 六、W23-W25 周计划

> **硬门槛**：M13-02 球馆名录 W26 完成；本任务可先 W23 起 schema + UI，W26 后接 venues API。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W23** | 评审；VenuesStep 设计稿；与 M13-02 venues API contract 对齐 | ☑ contract 评审；☑ UI 设计 |
| **W24** | VenuesStep + edit 页 + CI lint grep 规则 | ☑ AC-2 lint 通过；☑ UI 端到端 mock |
| **W25** | 联调 M13-02（如已完成）+ 灰度 | ☑ AC-1/3 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | VenuesStep + edit + GPS grep |
| 后端 | service 联动；M13-02 venues API 提供方 |
| 合规 | 复核 docs/06 §13.4.1；CI lint 规则 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | M13-02 球馆名录延期 → VenuesStep 没数据 | UI 加"手动输入球馆名称" fallback；保留为 free-text |
| R-02 | 用户用微信小程序 city 字段不准（如出差） | 顶部加"切换城市"按钮 |
| R-03 | 隐私改 false 后再切 true 引发字段闪现 | service 层每次读时校验 consent，未通过返回空数组 |
| R-04 | CI lint grep 误伤（注释里也有"getLocation"字样） | 加 `--type ts --type tsx` 限制；豁免注释行 |

### 7.3 AC 兜底（复述 docs/23 §5.5）

- [ ] **AC-1**：画像设置可填多个常去球馆
- [ ] **AC-2**：CI lint 验证不调 `scope.userLocation`
- [ ] **AC-3**：清空字段后 M13 入口隐藏 / 引导

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M9-01 数据模型 | favorite_course_ids 字段已就绪 |
| P2-M13-02 球馆名录 | 提供 venues API + 数据源 |
| P2-M13-03 约球匹配 | 消费 favorite_course_ids 作为锚点 |
| P2-M13-05 隐私授权 | 共享 location_consent 同意位 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；VenuesStep + GPS grep CI 保护 + 与 M13-02 对接 |
