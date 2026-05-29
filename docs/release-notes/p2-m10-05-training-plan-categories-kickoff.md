# P2-M10-05 · 训练计划生成支持短杆/推杆类目 · 启动包（W32 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §6.5`](../23-二期可编码规格说明书.md#65-p2-m10-05--训练计划生成支持短杆--推杆类目)
> 前置：P2-M10-04 + P2-M9-04 偏好

---

## 一、文档目的与边界

为 **P2-M10-05** 落地 W32-W36 后端 + LLM SOP，让训练计划按推杆/切杆 issue 自动派对应类目 drill。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不打破一期 training_plans / training_tasks 结构

---

## 二、现状盘点

```
backend/app/services/training_plan_service.py
  → 算法基于 detected_issues 推 drill
  → drill 选择不带 category 维度
  → LLM prompt 无 user preferences 字段
```

### 缺口（vs docs/23 §6.5 FR）

4 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| issue → category 映射 | `services/training_plan_service.py` 改 | 0.5 PW |
| 映射表 | `services/training/issue_to_category.yaml`（新） | 0.3 PW |
| LLM prompt 注入 preferences | `services/llm/training_plan_prompt.py` | 0.5 PW |
| 训练页 category 筛选 | `pages/training/plan/index.tsx` | 0.7 PW |
| 单测 | tests | 0.5 PW |
| 灰度 | feature flag | 0.5 PW |

**合计：~3 PW**

### 3.2 issue → category 映射示例

```yaml
putting_face_open: putting
putting_head_moved: putting
chipping_chunked: chipping
chipping_thin: chipping
early_extension: full_swing
chicken_wing: full_swing
# ...
```

### 3.3 LLM prompt 增量

```
[用户偏好]
- preferred_drill_types: {video, text}
- focus_categories: {putting / full_swing}

[策略]
推杆 issue 优先派 putting drill；切杆同理。其他 issue 派 full_swing。
若用户偏好 video → 优先 ALIGNED_IDS 列表；偏好 text → 文字步骤即可。
```

### 3.4 训练页筛选 UI

```tsx
<SegmentedControl
  options={['全部', '全挥杆', '推杆', '切杆']}
  onChange={cat => setFilterCategory(cat)}
/>
```

---

## 四、字段 v0.1

无新表；仅算法 + UI 改造。

---

## 五、验证数据

- 推杆 issue 训练计划 ≥1 推杆 drill（AC-1）
- 切杆 issue 同理（AC-2）
- 训练页可按 category 切换（AC-3）
- issue 与 drill 命中率 ≥80%

---

## 六、W32-W36 周计划

| 周 | 任务 |
| --- | --- |
| W32 | 映射表 + 算法改造 |
| W33 | LLM prompt 改造 |
| W34 | 训练页筛选 UI |
| W35 | 单测 + 灰度 |
| W36 | AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | 算法 |
| LLM | prompt |
| 客户端 | 筛选 UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 映射表覆盖不全 | 默认 full_swing |
| R-02 | LLM 偏好误读 | grep 单测 |
| R-03 | 推杆 drill 不足 | M10-04 ≥5 条；不足报警 |
| R-04 | 用户切换 category 后丢任务 | 状态持久 |

### AC

- [ ] AC-1 推杆 issue ≥1 推杆 drill
- [ ] AC-2 切杆 issue 同理
- [ ] AC-3 category 切换

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M10-04 drill 类目 | 数据基础 |
| P2-M9-04 偏好 | LLM 输入 |
| 一期 training_plan | 主算法 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
