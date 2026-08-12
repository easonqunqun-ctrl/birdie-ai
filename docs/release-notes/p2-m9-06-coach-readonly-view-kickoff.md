# P2-M9-06 · 教练侧只读视图（学员主动授权才可见）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §5.6`](../23-二期可编码规格说明书.md#56-p2-m9-06--教练侧只读视图学员主动授权才可见)
> 前置：P2-M8-03 学员双向 opt-in 绑定 + P2-M9-01 user_profiles_v2
>
> **补录说明**：本篇是 [`p2-63-kickoff-rollout`](../../.cursor/plans/p2-63-kickoff-rollout_566c0403.plan.md) Wave-1~5 漏列 M9-06 的补录，于 review 阶段定位。归类入 Wave-3（与 M8 教学闭环同 Phase 2.3）。

---

## 一、文档目的与边界

为 **P2-M9-06** 落地 W26-W30 后端 + 客户端 SOP，在 M9 画像 2.0 / M8 教练工作台基础上，**新增字段级可见性控制**，确保学员对自身敏感字段（差点 / 装备 / 已知伤病等）拥有 opt-in 控制权。

### 1.2 边界（不做）

- 不修改 docs/22/23/06 字段
- 不实现"教练侧主动请求查看"的反向请求流（v0.2.x backlog）
- 不允许已知伤病字段绕过"显式开启"步骤

---

## 二、现状盘点

| 现状 | 文件 |
| --- | --- |
| `user_profiles_v2` 表已规划（P2-M9-01） | 待 #20 合并 |
| `coach_student_relations.visibility_payload` JSONB 字段已规划（M8-03） | 待 #20 合并 |
| 一期 docs/06 §13.1-13.2 隐私清单已就位 | docs/06 |
| 一期教练侧无字段级可见性 UI / API | — |
| 错误码 `40313` 占位待 docs/02 §1.4 合入 | docs/02 |

### 缺口

5 个 FR 全部新增，1 个新 API（PUT visibility）+ 现有 `GET dashboard` 增加过滤。

---

## 三、模块设计

### 3.1 新增 / 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 学员侧 字段级开关 UI | `client/src/pages/coach/binding/visibility-settings.tsx`（新） | 0.5 PW |
| 后端 PUT visibility API | `backend/app/api/v1/users/coach_relations.py`（扩） | 0.3 PW |
| 教练侧 dashboard 过滤 | `backend/app/services/coach_dashboard.py`（扩） | 0.5 PW |
| 教练侧 UI 渲染"已隐藏" | `client/src/pages/coach/students/dashboard.tsx`（扩） | 0.3 PW |
| 已知伤病二次确认弹窗 | `client/src/components/PrivacySensitiveConfirm.tsx`（新） | 0.3 PW |
| 关系解除 visibility 重置 hook | `backend/app/services/coach_student_service.py`（扩） | 0.3 PW |
| 单测 + e2e | tests/ | 0.5 PW |

**合计：~3 PW**（与 docs/22 §5.3 估时一致）

### 3.2 visibility_payload schema

```jsonc
// coach_student_relations.visibility_payload
{
  "handicap_real": true,       // 真实差点
  "clubs": true,                // 装备清单
  "body_metrics": false,        // 身体数据（默认拒绝）
  "handedness": true,
  "injury_known": false,        // 已知伤病（默认拒绝；需显式开启）
  "goals": true,
  "training_preference": true,
  "frequent_venues": false,
  "_default": false             // 白名单制度兜底
}
```

### 3.3 过滤函数

```python
def filter_student_profile(profile: UserProfileV2, visibility: dict) -> dict:
    """按 visibility_payload 过滤；未授权字段返回 null 或 <已隐藏>。"""
    result = {}
    for field in PROFILE_FIELDS:
        if visibility.get(field, visibility.get('_default', False)):
            result[field] = getattr(profile, field)
        else:
            result[field] = None  # 或 "<已隐藏>"
    return result
```

### 3.4 关系解除 hook

```python
def on_coach_student_relation_terminated(relation_id):
    """关系解除 → visibility_payload 全部重置为 false，再绑定时需重新授权。"""
    relation = get_relation(relation_id)
    relation.visibility_payload = {'_default': False}  # 全部置空
    db.commit()
    audit_log('visibility_reset', relation_id=relation_id, reason='relation_terminated')
```

---

## 四、字段 v0.1

### API

```
PUT /v1/users/me/coach/{relation_id}/visibility
  Body: { "handicap_real": true, "clubs": true, ... }
  → 200 OK { updated_at }

GET /v1/coach/students/{student_id}/dashboard
  → 200 OK 响应中未授权字段 = null 或 "<已隐藏>"
  → 403 40313 学员未授权教练查看此字段（按字段抛出，可选；MVP 直接返回 null 更友好）
```

### 数据模型

复用 [`docs/03 §8.2.3`](../03-数据库设计文档.md#823-coach_student_relations) `coach_student_relations.visibility_payload` JSONB，**无新表 / 无新迁移**。

### 错误码

- `40313` 学员未授权教练查看此字段（与 docs/02 §1.4 已规划）

---

## 五、验证数据

- 学员开关 UI 上线（AC-1）
- 教练侧 dashboard 接口 / UI 双重验证未授权字段不可见（AC-2）
- 已知伤病字段：默认 false + 显式开启二次确认弹窗（AC-3）
- 关系解除 → visibility_payload 全部 reset（AC-4）
- 字段级过滤耗时 < 50ms / 学员（NFR-1）

---

## 六、W26-W30 周计划

| 周 | 任务 |
| --- | --- |
| W26 | visibility_payload schema 评审 + 后端 API |
| W27 | 教练侧 dashboard 过滤函数 + 单测 |
| W28 | 学员侧字段级开关 UI |
| W29 | 已知伤病二次确认弹窗 + 关系解除 hook |
| W30 | e2e 测试 + AC 验收 + 灰度 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | API + 过滤函数 + 关系解除 hook |
| 客户端 | 学员设置 UI + 教练侧"已隐藏"渲染 |
| 法务 | 默认拒绝白名单清单评审 |
| QA | 字段级 e2e |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 学员误开启敏感字段 | 已知伤病强制二次确认；默认 false |
| R-02 | 教练侧界面不知字段被隐藏 → 误诊 | UI 明示"该字段已隐藏" + 提示学员授权 |
| R-03 | 关系解除后字段权限未及时清空 | 关系解除 hook 强制同步 + 审计日志 |
| R-04 | 过滤耗时过长（学员 N 个字段） | 单次过滤 < 50ms；列表 LIMIT 100 学员 |
| R-05 | visibility 字段与 docs/06 §13.1 字段清单不一致 | DEP-05 法务签字 + 字段清单 cross-check |

### AC

- [ ] AC-1 学员字段级可见性 UI 上线
- [ ] AC-2 未授权字段教练侧不可见（接口 + UI 双重验证）
- [ ] AC-3 已知伤病默认拒绝 + 显式开启二次确认
- [ ] AC-4 关系解除后 visibility 全部重置

---

## 八、附录

### 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M8-03 学员双向 opt-in 绑定 | 前置（visibility_payload 字段来源） |
| P2-M9-01 user_profiles_v2 | 前置（被过滤的字段定义） |
| P2-M8-06 学员看板 | dashboard 接口集成点 |
| P2-M13-05 隐私授权 | 同期演进的 opt-in 框架（不同语义：M9-06 是字段级 / M13-05 是模块级） |
| DEP-05 法务 | 默认拒绝白名单评审 |

### Changelog 反查

- docs/23 §5.6 真源（待 #20 合并后生效）
- docs/02 §11.2 教练工作台接口（visibility API 锚点）
- docs/03 §8.2.3 coach_student_relations 表（visibility_payload 字段）
- docs/06 §13.1 + §13.2 隐私敏感字段清单

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版（补录漏列任务） |
