# P2-M8-05 · 作业派发（drill 库 / 自定义视频 → 学员 training_plan）· 启动包（W25 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.5`](../23-二期可编码规格说明书.md#45-p2-m8-05--作业派发drill-库--自定义视频--学员-training_plan)
> 前置：[`p2-m8-03-student-binding-kickoff.md`](./p2-m8-03-student-binding-kickoff.md) + DEP-03 drill 25-30 条

---

## 一、文档目的与边界

为 **P2-M8-05** 落地 W25-W30 后端 + 客户端 SOP，让教练 30s 内派发任务到学员训练 Tab。

### 边界（不做）

- 不修改 docs/22/23/03 字段
- 不实现教练 BD 工具（M8-10）
- 不实现学员看板（M8-06）

---

## 二、现状盘点

- 一期 `training_tasks` 由用户自行从训练计划生成；无教练入口
- 已有微信订阅消息基础设施（一期 ENG-09）
- M8-03 提供 active 师生关系

### 缺口（vs docs/23 §4.5 FR）

7 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ORM model | `models/coach.py` 追加 CoachAssignedTask | 0.5 PW |
| Service | `services/coach_task_service.py` | 1.5 PW |
| API | POST /v1/coach/tasks/assign / GET /v1/coach/tasks | 0.5 PW |
| 教练侧 UI | `pages/coach/task-assign/` | 1.5 PW |
| 学员侧训练 Tab 改造 | `pages/training/plan/index.tsx` 加"教练布置的"分组 | 0.5 PW |
| Migration | 共用 0020 | — |
| 通知模板 | 微信订阅消息 template_id 申请 | 0.3 PW |
| 单测 | 多个 | 0.2 PW |

**合计：~5 PW**（与 docs/23 §4.5 持平）

### 3.2 `coach_assigned_tasks` 表 schema v0.1（docs/03 §8.2.5 拟）

```sql
CREATE TABLE coach_assigned_tasks (
    id                 VARCHAR(32) PRIMARY KEY,
    coach_user_id      VARCHAR(32) NOT NULL REFERENCES users(id),
    student_user_id    VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relation_id        VARCHAR(32) NOT NULL REFERENCES coach_student_relations(id),
    source_type        VARCHAR(20) NOT NULL,    -- drill|custom_video
    drill_id           VARCHAR(32),
    custom_video_url   VARCHAR(512),
    custom_video_audit_status VARCHAR(20) DEFAULT 'pending',
    target_week        DATE NOT NULL,           -- 周一
    target_count       INTEGER NOT NULL,
    target_issue       VARCHAR(64),             -- early_extension 等
    coach_note         TEXT,
    training_task_id   VARCHAR(32),             -- 学员开始后回填
    status             VARCHAR(20) NOT NULL DEFAULT 'assigned',  -- assigned|started|done|expired
    completed_at       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_source CHECK (source_type IN ('drill','custom_video')),
    CONSTRAINT chk_source_xor CHECK ((source_type='drill' AND drill_id IS NOT NULL AND custom_video_url IS NULL) OR (source_type='custom_video' AND custom_video_url IS NOT NULL AND drill_id IS NULL)),
    CONSTRAINT chk_status CHECK (status IN ('assigned','started','done','expired'))
);
CREATE INDEX idx_cat_student_week ON coach_assigned_tasks(student_user_id, target_week DESC);
CREATE INDEX idx_cat_coach ON coach_assigned_tasks(coach_user_id, created_at DESC);
```

### 3.3 通知链路（FR-6）

```
派发成功 (T0) → 调通知 service (T+1s) → 微信订阅消息送达 (T+5-25s) → 学员点击 → 跳训练 Tab
```

整链路 ≤30s（AC-1）。订阅消息 template_id 走 M8-01 配置。

### 3.4 学员侧训练 Tab 分组

```
教练 [Coach 张] 布置的任务（2）
  • 毛巾夹臂 × 3 次 · 本周到期
  • 镜前脊柱角自录 × 1 次 · 本周到期
我的训练计划（5）
  • ...（一期 training_tasks）
```

完成同步：调一期 `POST /v1/training/tasks/{id}/complete` → service hook 写 `coach_assigned_tasks.status='done' + completed_at`。

---

## 四、字段 v0.1

### 4.1 API

```
POST /v1/coach/tasks/assign
  Body: { student_user_id, source_type, drill_id?, custom_video_url?, target_week, target_count, target_issue?, coach_note? }
GET  /v1/coach/tasks?student_id=&status=
```

### 4.2 配置

```python
COACH_TASK_NOTIFICATION_TIMEOUT_SEC: int = 30
COACH_TASK_MAX_PER_DAY: int = 50  # 每教练每日派发上限
```

---

## 五、验证数据

- E2E：教练派发 → 学员订阅消息送达 < 30s（≥90%，AC-1）
- 训练 Tab 独立分组渲染（AC-2）
- 学员完成 → `coach_assigned_tasks.status='done'` + 教练看板更新（AC-3）

---

## 六、W25-W30 周计划

| 周 | 任务 |
| --- | --- |
| W25 | schema + ORM + service |
| W26 | API + 教练侧派发 UI |
| W27 | 学员侧训练 Tab 改造 + 通知 |
| W28 | 完成同步 hook + 单测 |
| W29 | 灰度 5 对师生 + AC-1 时延实测 |
| W30 | 灰度 20 对 + 教练日上限风控 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | schema + service + 通知 |
| 客户端 | 教练 UI + 学员 Tab 分组 |
| 运营 | 微信订阅消息模板申请 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 订阅消息触达 <50%（用户未授权） | 默认派发完成即 push；fallback App 内 badge |
| R-02 | 教练上传自定义视频不合规 | M8-08 内容安全；pending 状态期间学员不可见 |
| R-03 | DEP-03 drill 库未到 30 条 | 教练只能用现有 drill；OR 自定义视频 |
| R-04 | 教练滥发任务（spam） | 日上限 50；学员可拒收/标记骚扰 |

### AC

- [ ] AC-1 派发→送达 <30s ≥90%
- [ ] AC-2 学员 Tab 独立分组
- [ ] AC-3 完成同步

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-03 师生关系 | relation_id |
| P2-M8-06 学员看板 | 消费 task 数据 |
| P2-M8-08 内容审核 | custom_video_url |
| 一期 training_tasks | 1:1 弱关联 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
