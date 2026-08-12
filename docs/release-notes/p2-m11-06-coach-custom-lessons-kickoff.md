# P2-M11-06 · 教练定制课程（M8 工作台可上传微课，关联学员训练计划）· 启动包（W33 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §7.6`](../23-二期可编码规格说明书.md#76-p2-m11-06--教练定制课程m8-工作台可上传微课关联学员训练计划)
> 前置：M11-01 + M8-04 + M8-08 + M11-03

---

## 一、文档目的与边界

为 **P2-M11-06** 落地 W33-W36 后端 + 客户端 SOP，让教练为特定学员定制微课，与平台 7 阶段并存于学员"学习"子页。

### 边界（不做）

- 不修改 docs/22/23 字段（lessons 表追加字段独立 migration）
- 不允许定制课程进入公开 7 阶段排行
- 不实现定制课程付费机制

---

## 二、现状盘点

- M11-01 已建 lessons 表（无 coach_id / visible_to_user_ids）
- M11-03 已实现 7 阶段树状视图（无"教练定制"专区）
- M8 工作台已有 annotations + 派发能力，无 lesson 上传

### 缺口（vs docs/23 §7.6 FR）

5 个 FR 全部新增；需追加 lessons 字段 + 教练 UI + 学员专区。

---

## 三、模块设计

### 3.1 新增 / 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Migration 0021 | `0021_m11_coach_lessons_extension.py`（新；docs/23 §7.6 标 0015，实际编号 0021） | 0.3 PW |
| Service | `services/coach_lesson_service.py` | 0.8 PW |
| API | POST /v1/coach/lessons + PUT /v1/coach/lessons/{id}/visibility | 0.5 PW |
| 教练侧 UI | `pages/coach/custom-lesson/` | 0.7 PW |
| 学员侧专区 | `pages/learning/components/CoachLessonSection.tsx`（新） | 0.5 PW |
| 内容审核 hook | 复用 M8-08 队列 | 0.1 PW |
| 单测 | tests | 0.1 PW |

**合计：~3 PW**

### 3.2 lessons 表追加字段

```sql
ALTER TABLE lessons
  ADD COLUMN coach_id VARCHAR(32),
  ADD COLUMN visible_to_user_ids JSONB DEFAULT '[]',
  ADD COLUMN is_public BOOLEAN DEFAULT TRUE;
-- coach_id IS NULL OR coach_id REFERENCES users(id)
-- is_public=false AND coach_id NOT NULL = 教练定制
CREATE INDEX idx_lessons_coach ON lessons(coach_id) WHERE coach_id IS NOT NULL;
```

### 3.3 可见性控制

```python
def list_lessons_for_student(student_id, course_id):
    return db.query(Lesson).filter(
        (Lesson.is_public == True) | 
        (Lesson.coach_id.in_(active_coach_ids_of(student_id)) & 
         Lesson.visible_to_user_ids.contains([student_id]))
    ).filter(Lesson.course_id == course_id).all()
```

### 3.4 学员侧"教练定制"专区（M11-03 UI 扩展）

```
学习路径
  ├─ 平台 7 阶段（既有）
  └─ 教练 [Coach 张] 为你定制（3 节，新）
       • 你的 early extension 专项 3 节
```

### 3.5 内容审核

定制 lesson 走 M8-08 审核队列；`audit_status` 同 annotations。

### 3.6 不污染公开 7 阶段

- 课程列表 API 强制过滤 `is_public=true`
- 阶段考核（M11-04）只覆盖公开 lessons

---

## 四、字段 v0.1

```
POST /v1/coach/lessons
  Body: { course_id?, title, video_url, drill_ids[], target_student_ids[], coach_note }
PUT  /v1/coach/lessons/{id}/visibility
  Body: { student_ids[] }
```

---

## 五、验证数据

- 教练上传 → 审核通过 → 学员侧可见（AC-1）
- 公开 7 阶段不含定制 lesson（AC-2/3）

---

## 六、W33-W36 周计划

| 周 | 任务 |
| --- | --- |
| W33 | migration + service + API |
| W34 | 教练 UI 上传 |
| W35 | 学员侧专区 + 审核联调 |
| W36 | 灰度 5 教练 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | migration + service |
| 客户端 | 教练 UI + 学员专区 |
| 合规 | 审核 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 教练上传低质内容 | M8-08 审核 + 学员可标记 |
| R-02 | visible_to_user_ids 列表过长（>1000） | 分批；OR 改 coach_lesson_visibility 子表 |
| R-03 | 与 M11-04 考核冲突 | 定制 lesson 不参与考核 |
| R-04 | 师生关系解除后定制课程残留 | 解除时 visible_to_user_ids 移除该学员 |

### AC

- [ ] AC-1 教练可上传
- [ ] AC-2 学员定制专区
- [ ] AC-3 不污染公开课

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M11-01 schema | lessons 表扩展 |
| P2-M11-03 学习 UI | 加专区 |
| P2-M8-04 + 08 | UI + 审核 |
| P2-M8-03 师生 | 可见性源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
