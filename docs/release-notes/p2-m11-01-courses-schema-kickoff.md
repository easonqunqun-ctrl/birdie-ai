# P2-M11-01 · 课程数据模型（courses / lessons / user_course_progress / course_certificates）· 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，落地 M11 课程体系 全部 6 任务的数据地基
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §7.1 · P2-M11-01`](../23-二期可编码规格说明书.md#71-p2-m11-01--课程数据模型courses--lessons--user_course_progress--course_certificates)
> 前置：[`docs/22 §四 DEP-08 字段级隐私授权落地评审`](../22-二期开发迭代计划.md)

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M11-01 课程数据模型**落地一份「**W17 即可起跑、W19 4 表 + Alembic 就绪**」的后端 SOP，让后端明确：

- 一期"动作库 `drills`"和"训练计划 `training_plans`"与二期"课程 `courses`"的边界
- 4 张表 schema v0.1（courses / lessons / user_course_progress / course_certificates）
- 7 阶（stage 1-7）+ 会员可见性（is_member_only）+ 通关证书复用一期 M5 海报合成
- 与 M11-02~06 / M8-06（教练定制课程）下游消费关系

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/03`](../03-数据库设计文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不动一期 `drills` / `training_plans` 表 | M11 课程通过 `lesson.drill_ids` JSONB 引用 drills，不双写 |
| 不实现课程内容（视频 / 配文 / 测验） | P2-M11-02 教研主导（≈40 节） |
| 不实现学习路径 UI | P2-M11-03 负责 |
| 不实现阶段考核逻辑 | P2-M11-04 负责（评分达标自动升阶） |
| 不实现证书海报合成 | 复用一期 M5 海报合成框架；M11-05 负责证书 design |
| 不实现教练定制课程后台 | P2-M11-06 + M8-05 联动 |

### 1.3 与其他文档的关系

```
docs/23 §7.1          ← 需求真源
docs/03 §8.4.1 ~ §8.4.4 ← 4 表结构（拟）
本文件                 ← 模型 / migration / 与 drills / lessons 链接 SOP
  ↓ W19 回流
docs/03 §8.4          ← v0.1 → v1.0
docs/02 §11.5         ← /v1/courses 接口字段细化（M11-03 接入后再回流）
```

---

## 二、现状盘点

### 2.1 一期 training 系统 vs 二期 courses 系统

| 维度 | 一期 `drills` + `training_plans` | 二期 `courses` + `lessons` |
| --- | --- | --- |
| 形态 | 动作库（13 条）+ 自然周计划 | 7 阶课程（约 40 节）+ 持续进度 |
| 颗粒度 | 单动作（5-15min） | 单课时（含视频 + drill + 测验，10-30min） |
| 入口 | "本周训练" tab | "学习路径"首页"你在第 N 阶" |
| 收尾 | 打卡日志 `practice_logs` | 课程通关 + 证书 `course_certificates` |
| 关系 | M11 lessons **复用** drills（lesson.drill_ids JSONB 数组） | drills 是 lessons 的"小颗粒练习"组件 |

**结论**：M11 是更高层的"教学路径"封装；不替代一期 drills/training_plans，而是 **聚合 + 进阶**。

### 2.2 一期相关代码

| 文件 | 行数 / 要点 | V2 影响 |
| --- | --- | --- |
| `backend/app/models/training.py` `Drill` L32-77 | drills 表（id / target_issues / steps / video_url 等） | **不动**；lessons 通过 `drill_ids` JSONB 引用 |
| `backend/app/models/training.py` `TrainingPlan` | 自然周训练计划 | **不动**；M11-04 阶段考核完成后**可选**生成 training_task（待 W23 评估） |
| `client/src/constants/drillLibrary.ts` | 13 条 drill seed 数据 | **不动**；M11-02 lessons 引用现有 drill_id |
| `backend/alembic/versions/` 当前 head | `0016` | 新增 `0018_m11_courses_schema.py`（M9-01 用 0017）；docs/23 §7.1 规划编号 `0010` 见 §2.4 |

### 2.3 已知缺口（vs docs/23 §7.1 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 `courses` 表 + stage 1-7 + is_member_only | ❌ 无 | 新建表 + CHECK 约束 |
| FR-2 `lessons` 表 + video_url + drill_ids + pro_clip_ids + quiz_payload + pass_criteria | ❌ 无 | 新建表 + JSONB |
| FR-3 `user_course_progress` 状态机 | ❌ 无 | 新建表 + 4 态 enum |
| FR-4 `course_certificates` 表 | ❌ 无 | 新建表 + cert_url（M5 海报合成产出） |
| FR-5 ORM + Pydantic schema + 0018 migration | ❌ 无 | 全新代码 |

### 2.4 编号说明

- docs/23 §7.1 规划 `Alembic 迁移 0010 同步`
- 实际 alembic head 已到 `0016`；M9-01 占 0017
- 本任务实际编号 `0018_m11_courses_schema.py`，docs/03 §8.7 逻辑编号 0010 在 migration docstring 内交叉引用

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| ORM model | `backend/app/models/course.py`（新） | 4 张表类 | 1.5 PD |
| Pydantic schema | `backend/app/schemas/course.py`（新） | Create/Update/Read | 0.5 PD |
| Service 框架 | `backend/app/services/course_service.py`（新） | 课程查询 + 进度推进 + 升阶判定 | 1 PD |
| Migration | `backend/alembic/versions/0018_*.py` | 4 张表 + 索引 + FK | 0.5 PD |
| 单测 | `backend/tests/test_course_model.py` 等 | 4 表 + 状态机 + 升阶 | 1 PD |
| Feature flag | `backend/app/config.py` | `PHASE2_COURSES_ENABLED: bool = False` | 0.2 PD |

**合计：~4.7 PD**（与 docs/23 §7.1 估时 3 PW 持平）

### 3.2 `courses` 表 schema v0.1

```sql
CREATE TABLE courses (
    id              VARCHAR(32) PRIMARY KEY,         -- crs_<nanoid>
    code            VARCHAR(40) NOT NULL UNIQUE,     -- 'stage_3_iron_basics'
    title           VARCHAR(100) NOT NULL,
    subtitle        VARCHAR(200),
    cover_url       VARCHAR(512),
    stage           SMALLINT NOT NULL,                -- 1-7
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_member_only  BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT,
    learning_objectives JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ["建立标准站位","掌握节奏"]
    estimated_minutes INTEGER NOT NULL DEFAULT 60,
    created_by_user_id VARCHAR(32) REFERENCES users(id),    -- M11-06 教练定制时填
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_courses_stage CHECK (stage BETWEEN 1 AND 7)
);
CREATE INDEX idx_courses_stage ON courses(stage, sort_order) WHERE is_published = TRUE;
CREATE INDEX idx_courses_member ON courses(is_member_only, stage);
```

### 3.3 `lessons` 表 schema v0.1

```sql
CREATE TABLE lessons (
    id              VARCHAR(32) PRIMARY KEY,           -- lsn_<nanoid>
    course_id       VARCHAR(32) NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    code            VARCHAR(40) NOT NULL UNIQUE,
    title           VARCHAR(100) NOT NULL,
    sort_order      INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 15,
    video_url       VARCHAR(512),
    transcript      TEXT,
    drill_ids       JSONB NOT NULL DEFAULT '[]'::jsonb,    -- ["drill_towel_arm","drill_impact_bag"]，引用 drills.id
    pro_clip_ids    JSONB NOT NULL DEFAULT '[]'::jsonb,    -- M12 球手镜头 id，引用 pro_swing_clips.id（M12-01）
    quiz_payload    JSONB DEFAULT NULL,                     -- {questions: [...]} 测验结构
    pass_criteria   JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {analysis_score_min: 75, quiz_score_min: 80}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_lessons_course_id ON lessons(course_id, sort_order);
CREATE UNIQUE INDEX uq_lessons_course_sort ON lessons(course_id, sort_order);
```

**关键约束**：

- `drill_ids` JSONB 数组 → 应用层校验所有 id 存在于 `drills` 表
- `pro_clip_ids` JSONB 数组 → 应用层校验所有 id 存在于 `pro_swing_clips` 表（M12-01 提供）
- `pass_criteria` 二选一或都用：`analysis_score_min`（M7 评分） / `quiz_score_min`（测验得分）

### 3.4 `user_course_progress` 表 schema v0.1

```sql
CREATE TABLE user_course_progress (
    id              VARCHAR(32) PRIMARY KEY,           -- ucp_<nanoid>
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id       VARCHAR(32) NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'not_started',  -- not_started/in_progress/passed/failed
    last_score      INTEGER,                            -- 最近一次评分 / 测验得分
    attempts        INTEGER NOT NULL DEFAULT 0,
    passed_at       TIMESTAMPTZ,
    failed_reasons  JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ucp_status CHECK (status IN ('not_started','in_progress','passed','failed'))
);
CREATE UNIQUE INDEX uq_ucp_user_lesson ON user_course_progress(user_id, lesson_id);
CREATE INDEX idx_ucp_user_passed ON user_course_progress(user_id, status) WHERE status = 'passed';
```

### 3.5 `course_certificates` 表 schema v0.1

```sql
CREATE TABLE course_certificates (
    id              VARCHAR(32) PRIMARY KEY,           -- crt_<nanoid>
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id       VARCHAR(32) NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    stage           SMALLINT NOT NULL,
    cert_url        VARCHAR(512),                       -- 海报图 URL（M5 海报合成产出）
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,                        -- 极端情况撤销
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_cc_stage CHECK (stage BETWEEN 1 AND 7)
);
CREATE UNIQUE INDEX uq_cc_user_course ON course_certificates(user_id, course_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_cc_user_issued ON course_certificates(user_id, issued_at DESC);
```

### 3.6 状态机：`user_course_progress.status`

```
not_started  ──触发学习──>  in_progress
in_progress  ──测验/评分达标──>  passed
in_progress  ──测验失败/分数不达标──>  failed
failed       ──重新提交──>  in_progress
passed       ──终态──>  (不变)
```

升阶判定（M11-04 负责）：

- 一阶所有 lessons.status='passed' → 用户阶段 +1
- 触发 course_certificates 生成（M5 海报合成）

---

## 四、字段 / 配置草案 v0.1

### 4.1 Migration

```python
# backend/alembic/versions/0018_m11_courses_schema.py
"""逻辑编号 docs/03 §8.7 = 0010；实际编号 0018（head=0016, M9-01 占 0017 续编）"""
revision = "0018"
down_revision = "0017"
```

### 4.2 配置项

```python
PHASE2_COURSES_ENABLED: bool = False  # 默认 false；M11-03 学习路径 UI 上线时切 true
```

### 4.3 与 drills / pro_clips 软关联

- `lessons.drill_ids` JSONB 数组，引用 `drills.id`；**不**在 DB 加 FK（drills 是 seed 表，drill_id 字符串引用足够）
- `lessons.pro_clip_ids` JSONB 数组，引用 `pro_swing_clips.id`（M12-01 提供）；同上不加 FK
- 应用层 `course_service.validate_lesson_dependencies()` 校验，发布课程（is_published=true）时阻塞

---

## 五、验证数据

### 5.1 单测（AC-2）

- `tests/test_course_model.py`：
  - 4 表 ORM 实例化 + relationships
  - CHECK 约束（stage 1-7 / status enum）触发
  - `uq_ucp_user_lesson` 唯一约束触发
- `tests/test_course_service.py`：
  - status 状态机转换
  - drill_ids 校验失败 → BadRequestError
- 覆盖率 ≥85%

### 5.2 Migration 跑通（AC-3）

- staging：`alembic upgrade head` ≤8s
- 回滚：`alembic downgrade -1` ≤8s + 4 表已删
- 验证 ON DELETE CASCADE 链路（删 course → lessons/progress/certificates 联动删除）

### 5.3 与 drills 表兼容

- 单测：插入 lesson 引用所有 13 条现有 drill_id → 校验通过
- 单测：插入 lesson 引用不存在的 drill_id → 校验失败

---

## 六、W17-W19 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；冻结 4 表 schema v0.1；与 M11-02~06 / M8-06 owner 对齐字段消费方式 | ☑ 4 表 schema review；☑ status 状态机评审 |
| **W18** | ORM model + Pydantic schema + service 框架 + 单测 ≥85% | ☑ 4 表完整；☑ 状态机单测 |
| **W19** | Migration 0018 + staging 跑通 + 回滚验证 + drill_ids 校验链路 | ☑ AC-1/2/3 全勾；☑ docs/03 §8.4 转正 PR 提交 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；ORM + service + migration |
| 教研 / 内容 | 提前 review `learning_objectives` / `pass_criteria` 字段含义 |
| 客户端 | W19 拿到 schema 后 mock；M11-03 W22+ 接入 |
| 设计 | course_certificates `cert_url` 海报模板 design（W21 M11-05 启动前） |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | drill_ids JSONB 数组不在 DB 加 FK，导致 drill 删除后 lesson 引用悬空 | drills 是 seed 表（实际不删，is_active=false）；service 加 active 过滤 |
| R-02 | course `is_published=true` 后被改 stage 引发用户进度错位 | 已发布课程**禁止**改 stage；service 层硬约束 |
| R-03 | pro_clip_ids 引用 M12-01 表尚未就位 | M12-01 与本任务同 Wave-1 起包；W19 W19 同时就位才能联调 |
| R-04 | course_certificates `cert_url` 海报合成性能瓶颈 | 复用一期 M5 海报合成（已上线）；同步生成转异步 |
| R-05 | docs/03 §8.7 规划 0010 vs 实际 0018 编号不一致 | migration docstring 交叉引用；§2.4 已明示 |

### 7.3 AC 兜底（复述 docs/23 §7.1）

- [ ] **AC-1**：docs/03 §8.4 v0.1 → v1.0 转正
- [ ] **AC-2**：ORM model + Pydantic schema 代码就位，单测覆盖率 ≥85%
- [ ] **AC-3**：Alembic 迁移 staging 跑通 + 回滚验证

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 | 下游消费 |
| --- | --- | --- |
| P2-M11-02 7 阶课程内容生产 | 4 表 schema + seed 接口 | 教研填 ≈40 节内容 |
| P2-M11-03 学习路径 UI | API `/v1/courses` + `/v1/users/me/courses/progress` | 首页"你在第 N 阶" |
| P2-M11-04 阶段考核 | `pass_criteria` 字段 + status 状态机 | 评分达标自动升阶 |
| P2-M11-05 证书 / 勋章 | `course_certificates.cert_url` | 海报合成 + 分享 |
| P2-M11-06 教练定制课程 | `courses.created_by_user_id` | M8 教练后台上传微课 |
| P2-M8-05 作业派发 | `lessons.id` 可作为 training_task 来源 | 教练派发作业可指定 lesson |

### 8.2 与一期 training_plans 共存

| 路径 | 数据流 |
| --- | --- |
| 自动周计划（一期） | M7 报告 → issue → recommend → drill → TrainingTask（不变） |
| 学习路径（二期） | 用户进 stage X → 选 course → 学 lesson → 测验 → 升阶 |
| 教练作业（M8-05） | 教练在 M8 后台选 lesson 或自定义视频 → TrainingTask（混合） |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；4 表 schema v0.1 + status 状态机 + W17-W19 周计划 |
| v0.2 | W19 收尾 | docs/03 §8.4 转正后 PR；本文件 superseded |
