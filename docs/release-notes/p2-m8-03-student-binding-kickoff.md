# P2-M8-03 · 学员双向 opt-in 绑定 · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.3 期间，落地教练-学员双向 opt-in 师生关系
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §4.3 · P2-M8-03`](../23-二期可编码规格说明书.md#43-p2-m8-03--学员双向-opt-in-绑定coach_student_relations)
> 前置 kickoff：[`p2-m8-01-coach-profile-verification-kickoff.md`](./p2-m8-01-coach-profile-verification-kickoff.md)（**硬依赖**：M8-01 已就绪；本任务共用 0020 migration 追加 1 张表）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M8-03** 落地一份「**W22 起跑、W26 师生关系闭环**」的后端 + 客户端 SOP，明确：

- `coach_student_relations` 表 schema v0.1（pending / active / paused / ended 4 态）
- 双向 opt-in 流程：教练发起 + 学员接受
- 字段级可见性：默认所有 `user_profiles_v2` 字段对教练**不可见**，需学员显式授权
- 解除关系后历史保留（不级联删）

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22/23/06 字段 | 避免 race |
| 不实现批注 / 作业 | M8-04/05 负责 |
| 不允许一位学员同时绑 ≥2 位活跃教练 | 应用层约束（FR-5 中文规约） |
| 不入新的 PIPL 兜底 SOP | 复用一期账号注销机制 |

---

## 二、现状盘点

### 2.1 一期无师生关系模型

- backend 仅有 user / analysis 模型；无 coach-student 关联
- 客户端无邀请 / 接受 UI

### 2.2 一期可复用

- 一期 `invitations` 表（W7-T4）的双向邀请模式可借鉴
- 一期订阅消息基础设施可复用（新增"教练邀请"模板）

### 2.3 已知缺口（vs docs/23 §4.3 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 `coach_student_relations` 表 | ❌ | 新建表 |
| FR-2 教练侧 invite API | ❌ | API + UI |
| FR-3 学员侧 accept API | ❌ | API + 通知 |
| FR-4 任一方 end API | ❌ | API |
| FR-5 字段级可见性（学员授权） | ❌ | service + UI |
| FR-6 解除后历史保留 | ❌（无业务）| 设计阶段确认 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| ORM model | `backend/app/models/coach.py` 追加 CoachStudentRelation | 1 PD |
| Pydantic schema | `backend/app/schemas/coach.py` 追加 | 0.3 PD |
| Service | `backend/app/services/coach_student_service.py`（新） | invite/accept/end + 可见性 | 1.5 PD |
| Migration | `backend/alembic/versions/0020_*.py`（M8-01 共用，本任务追加表） | 1 张表 + 索引 | 0.3 PD |
| API | invite / accept / end / visibility | 6 个端点 | 1.5 PD |
| 邀请 UI（教练侧） | `client/src/pages/coach/students/invite.tsx` | 输入 user_id / 邀请码 | 1 PD |
| 接受 UI（学员侧） | 通知中心 + `pages/coach-invite/index.tsx` | 接受 / 拒绝 | 1 PD |
| 可见性 UI（学员侧） | `pages/profile/coach-visibility.tsx` | 字段级开关 | 1 PD |
| 通知模板 | 微信订阅消息 | "教练邀请" | 0.5 PD |
| 单测 | 多个 | 双向 opt-in + 可见性 | 1 PD |

**合计：~9 PD**（与 docs/23 §4.3 估时 3 PW 偏宽，含可见性 UI buffer）

### 3.2 `coach_student_relations` 表 schema v0.1

```sql
CREATE TABLE coach_student_relations (
    id              VARCHAR(32) PRIMARY KEY,           -- csr_<nanoid>
    coach_user_id   VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|active|paused|ended
    visibility_payload JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {handicap: true, body: false, ...}
    invited_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    invite_message  TEXT,
    accepted_at     TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    ended_by_user_id VARCHAR(32),                       -- 'coach'|'student' 来源谁
    pause_reason    TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_csr_status CHECK (status IN ('pending','active','paused','ended')),
    CONSTRAINT chk_csr_not_self CHECK (coach_user_id <> student_user_id)
);
CREATE UNIQUE INDEX uq_csr_active ON coach_student_relations(coach_user_id, student_user_id) WHERE status IN ('pending','active');
CREATE INDEX idx_csr_coach ON coach_student_relations(coach_user_id, status);
CREATE INDEX idx_csr_student ON coach_student_relations(student_user_id, status);
```

> UNIQUE 部分索引保证教练-学员对的 active 关系唯一；已 ended 的关系可重新 invite（新行）。

### 3.3 状态机

```
pending  ──学员 accept──>  active
pending  ──学员 reject / 60d 未响应──>  ended
active   ──任一方 pause──>  paused
paused   ──任一方 resume──>  active
active / paused  ──任一方 end──>  ended
ended    ──不变──>  (终态，历史保留)
```

### 3.4 字段级可见性

**默认行为**（FR-5）：

- 教练对学员 `user_profiles_v2` 所有字段**默认不可见**
- 学员在 `pages/profile/coach-visibility.tsx` 显式勾选哪些字段对教练可见
- 字段写入 `coach_student_relations.visibility_payload`

```jsonc
// visibility_payload 草案
{
  "handicap": true,
  "body": false,            // height/weight
  "injuries": false,        // 永远默认 false（高敏感）
  "goals": true,
  "training_preference": true,
  "frequent_venues": false
}
```

### 3.5 一学员最多 1 位活跃教练（FR 中文规约）

应用层校验：

```python
def invite_student(coach_id, student_id):
    existing = db.execute(select(CoachStudentRelation)
        .where(CoachStudentRelation.student_user_id == student_id)
        .where(CoachStudentRelation.status.in_(['pending', 'active'])))
    if existing.first():
        raise ConflictError("学员已有教练，无法绑定")
```

### 3.6 解除后历史保留

- `analysis_annotations` (M8-04) / `homework` (M8-05) / `reports` (M8-07) 等历史数据 **保留**
- 教练侧无法新增任何操作（API 检查 status='active' 才放行）
- 学员侧仍可查看历史批注（只读）

### 3.7 错误码

- `40312` 师生关系不存在 / 已结束
- `40313` 学员未授权教练查看此字段
- `40915` 学员已有活跃教练（新增）

---

## 四、字段 / 配置草案 v0.1

### 4.1 API

```
POST /v1/coach/students/invite          Body: { student_user_id?, invite_code?, message? }
POST /v1/coach/students/{id}/accept     (学员调用)
POST /v1/coach/students/{id}/reject     (学员调用)
POST /v1/coach/students/{id}/end        (任一方调用)
GET  /v1/coach/students                 (教练查看)
GET  /v1/users/me/coach                 (学员查看当前教练)
PUT  /v1/users/me/coach/{id}/visibility Body: { handicap: true, ... }
```

### 4.2 配置项

```python
PHASE2_COACH_ENABLED: bool = False
```

---

## 五、验证数据

### 5.1 单测

- service：双向 opt-in 流转；一学员 2 教练触发 40915
- API：邀请 → 接受 → 解除全链路
- 可见性：handicap=false → 教练查接口返回 40313

### 5.2 端到端

- 教练 invite → 微信通知触达 → 学员接受 → 教练可查（按可见性过滤）→ 解除后 ANNotation API 40312

---

## 六、W22-W26 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W22** | 评审；schema + 状态机；与 M8-01 共用 migration 协调 | ☑ schema review |
| **W23** | ORM + service + invite/accept API | ☑ 单测 ≥85% |
| **W24** | 教练 invite UI + 学员接受 UI + 微信通知模板申请 | ☑ 端到端 mock |
| **W25** | 可见性 UI + service | ☑ AC-2 通过 |
| **W26** | end API + 解除链路 + 灰度 5 对师生 | ☑ AC-1/2/3 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；schema + service + API |
| 客户端 | invite/accept/visibility UI |
| 隐私 / 合规 | docs/06 §13.2 字段级可见性复核 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 学员误授权 injuries 字段对教练可见 | UI 默认 false + 二次 Modal 提示"高敏感"（与 M9-03 同等约束） |
| R-02 | 微信通知延迟 → 学员错过邀请 | 客户端"我的"页面 banner 提示待处理邀请 |
| R-03 | 一学员可绑多教练误用 | 严格应用层 + DB 部分 UNIQUE 索引保护 |
| R-04 | 解除后教练误操作能引发数据问题 | service 层所有写操作首先校验 status=active；fallback 40312 |

### 7.3 AC 兜底（复述 docs/23 §4.3）

- [ ] **AC-1**：双向 opt-in + 单方解除全链路打通
- [ ] **AC-2**：字段级可见性默认拒绝；学员显式开关后教练才看得到
- [ ] **AC-3**：解除后教练 API 返 40312

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M8-01 资质审核 | 共用 0020 migration |
| P2-M8-02 身份切换 | 切到 coach 后才能 invite |
| P2-M8-04~10 | 业务功能依赖 status='active' |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；双向 opt-in + 字段级可见性 + 1 学员 1 活跃教练 |
