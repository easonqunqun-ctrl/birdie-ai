# P2-M9-01 · user_profiles_v2 + user_clubs 数据模型 · 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，落地 M9 画像 2.0 全部 6 任务的数据地基
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §5.1 · P2-M9-01`](../23-二期可编码规格说明书.md#51-p2-m9-01--user_profiles_v2--user_clubs-数据模型)
> 前置：[`docs/22 §四 DEP-08 字段级隐私授权落地评审`](../22-二期开发迭代计划.md)

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M9-01 user_profiles_v2 + user_clubs 数据模型**落地一份「**W17 即可起跑、W19 模型 + Alembic 就绪**」的后端 SOP，让后端明确：

- 一期 `users` 表的字段边界与"为何不扩列而新建表"
- `user_profiles_v2` 一对一扩展规约 + 字段级 `privacy_payload` 设计
- `user_clubs` 14 支上限（应用层校验）规约
- 与 M9-02 ~ M9-06 / M7-05 / M11 / M13 的下游消费关系
- 上线策略：CREATE TABLE 零 downtime；feature flag `phase2_profile_v2_enabled` 灰度

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/03`](../03-数据库设计文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不动一期 `users` 表 schema | 保一期接口契约不变；后续 GDPR 字段级清理能精准定位 |
| 不实现 onboarding UI | P2-M9-03 负责 6 题流程；本任务只建表 |
| 不实现教练侧只读视图 | P2-M9-06 负责；本任务只在表 schema 上预留 `coach_visible_fields` payload |
| 不实现装备清单 UI | P2-M9-02 负责；本任务只建 `user_clubs` 表 |
| 不引入 ORM 自动迁移 | 严格走 Alembic（AGENTS.md §5 硬约束） |

### 1.3 与其他文档的关系

```
docs/23 §5.1          ← 需求真源
docs/03 §8.3.1 / §8.3.2 ← 表结构真源（拟）
docs/06 §13.1         ← 敏感字段合规约束（已就位）
本文件                 ← 模型 / migration / 灰度策略 SOP
  ↓ W19 回流
docs/03 §8.3          ← v0.1 → v1.0 转正
docs/02 §11.3         ← 接口字段（M9-02/03/04/05 接入后再回流）
```

---

## 二、现状盘点

### 2.1 一期 `users` 表已有字段

来自 `backend/app/models/user.py` L12-103：

| 字段类别 | 一期字段 |
| --- | --- |
| 身份 | `id` / `wechat_openid` / `wechat_app_openid` / `wechat_unionid` |
| 资料 | `nickname` / `avatar_url` |
| 高尔夫档案（轻量） | `golf_level` ∈ {beginner/elementary/intermediate/advanced}, `primary_goals` JSONB, `weekly_practice_frequency`, `onboarding_completed` |
| 会员 | `membership_type` / `membership_started_at` / `membership_expires_at` / `auto_renew` / `papay_contract_id` |
| 邀请 | `invite_code` / `invited_by_user_id` |
| 统计缓存 | `total_analyses` / `total_practices` / `best_score` / `current_streak_days` 等 |
| 账号注销 | `account_deletion_scheduled_at`（PIPL 承诺 7-30 日清理） |
| 软删除 | `deleted_at` |

**结论**：一期 `users` 表是"小程序登录 + 简单档案 + 会员"模型；**没有**真实差点 / 身体数据 / 利手 / 已知伤病 / 常去球馆 / 装备等深度档案字段。

### 2.2 一期相关代码

| 文件 | 行数 / 要点 | V2 改造 |
| --- | --- | --- |
| `backend/app/models/user.py` L12-103 | `User` ORM model | **不动** |
| `backend/app/models/user.py` L80-103 `__table_args__` | golf_level / weekly_frequency CHECK 约束 | **不动**；新表自有 CHECK |
| `backend/app/schemas/user.py`（拟） | UserProfile schema | **新增** `UserProfileV2` schema |
| `backend/alembic/versions/` 当前 head | `0016_feedback.py` | **新增** 拟 `0008_m9_user_profiles_v2.py`（docs/23 §5.1 规划）；实际落地编号按 alembic head 续编（W17 W17 决定） |
| `backend/app/services/user_service.py`（拟） | 现有 user 服务 | **新增** UserProfileV2Service |
| `client/src/store/userStore.ts` | 当前 user 信息 store | **后续**：M9-03 起逐步消费 v2 字段 |

### 2.3 已知缺口（vs docs/23 §5.1 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 `user_profiles_v2` 一对一扩展 `users` | ❌ 无表 | 新建表 + FK + UNIQUE(user_id) |
| FR-2 `user_clubs` 表，每用户最多 14 支 | ❌ 无表 | 新建表 + 应用层校验 |
| FR-3 字段级 `privacy_payload` 独立同意位 | ❌ 无 | JSONB 字段 + 服务层校验 |
| FR-4 一期 `users.golf_level` 复用 | ✅ 已有 | 仅在 docs 标"沿用" |

### 2.4 docs/03 §8.7 vs 实际 alembic head

- docs/23 §5.1 引用「Alembic 迁移 `0008_m9_user_profiles_v2.py`（对齐 docs/03 §8.7）」
- 当前 alembic head：`0016_feedback.py`
- **本任务落地时**：实际编号 = `0017_m9_user_profiles_v2.py`（按 alembic upgrade 链路续编），docs/03 §8.7 的 `0008` 命名规约保留为"M9 阶段第 1 个迁移"的逻辑编号，在迁移文件 docstring 内交叉引用
- 不在本 kickoff 修复 docs/03 §8.7（属 docs/23 收尾 commit 范围）

---

## 三、模块设计

### 3.1 新增/改造一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| ORM model | `backend/app/models/user_profile_v2.py`（新） | `UserProfileV2` + `UserClub` 类 | 1 PD |
| Pydantic schema | `backend/app/schemas/user_profile_v2.py`（新） | Create / Update / Read schema | 0.5 PD |
| Service | `backend/app/services/user_profile_v2_service.py`（新） | CRUD + privacy_payload 校验 | 1 PD |
| Migration | `backend/alembic/versions/0017_*.py` | CREATE TABLE 双表 + 索引 + FK | 0.5 PD |
| 单测 | `backend/tests/test_user_profile_v2.py` 等 | model + service + migration | 1 PD |
| Feature flag | `backend/app/config.py` | `PHASE2_PROFILE_V2_ENABLED: bool = False` | 0.2 PD |

**合计：~4 PD**（与 docs/23 §5.1 估时 3 PW 略宽，含 migration / privacy_payload 校验 buffer）

### 3.2 `user_profiles_v2` 表 schema v0.1

```sql
CREATE TABLE user_profiles_v2 (
    user_id                 VARCHAR(32) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    -- 真实差点（M9-03）
    handicap_official       NUMERIC(4,1),         -- -10.0 ~ 54.0
    handicap_self           NUMERIC(4,1),
    handicap_source         VARCHAR(20),          -- 'rcga'|'usga'|'self'
    -- 身体数据（M9-03，敏感等级"高"）
    height_cm               INTEGER,
    weight_kg               INTEGER,
    handedness              VARCHAR(10),          -- 'right'|'left'|'switch'
    known_injuries          JSONB DEFAULT '[]'::jsonb,   -- ["lower_back","right_elbow",...]；详 docs/06 §13.1
    -- 目标 / 偏好（M9-04）
    mid_long_goals          JSONB DEFAULT '[]'::jsonb,
    training_preference     VARCHAR(20),          -- 'video'|'text'|'mixed'
    weekly_target_sessions  INTEGER,
    -- 常去球馆（M9-05，M13 前置）
    favorite_course_ids     JSONB DEFAULT '[]'::jsonb,
    -- 隐私授权（FR-3 字段级）
    privacy_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 教练侧只读视图授权（M9-06）
    coach_visible_fields    JSONB DEFAULT '[]'::jsonb,  -- 用户主动勾选可见字段列表
    -- 审计
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_handedness CHECK (handedness IS NULL OR handedness IN ('right','left','switch')),
    CONSTRAINT chk_handicap_official CHECK (handicap_official IS NULL OR (handicap_official BETWEEN -10 AND 54)),
    CONSTRAINT chk_handicap_self CHECK (handicap_self IS NULL OR (handicap_self BETWEEN -10 AND 54)),
    CONSTRAINT chk_training_preference CHECK (training_preference IS NULL OR training_preference IN ('video','text','mixed'))
);
CREATE INDEX idx_user_profiles_v2_updated_at ON user_profiles_v2(updated_at);
```

### 3.3 `user_clubs` 表 schema v0.1

```sql
CREATE TABLE user_clubs (
    id              VARCHAR(32) PRIMARY KEY,         -- ucb_<nanoid>
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    club_type       VARCHAR(20) NOT NULL,             -- 与 client/types/api.ts ClubType 一致
    nickname        VARCHAR(40),                       -- 用户自定义昵称（如"老搭子"）
    self_yardage_m  INTEGER,                           -- 用户自评距离（米）
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,    -- 是否在用
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_self_yardage_m CHECK (self_yardage_m IS NULL OR (self_yardage_m BETWEEN 0 AND 400))
);
CREATE INDEX idx_user_clubs_user_id ON user_clubs(user_id);
CREATE INDEX idx_user_clubs_user_active ON user_clubs(user_id, is_active);
-- 14 支上限走应用层（user_profile_v2_service.add_club()）
```

### 3.4 `privacy_payload` 字段级同意位规约（FR-3）

```jsonc
{
  "handicap_consent": true,
  "body_consent": true,             // height/weight
  "injury_consent": false,          // 已知伤病；高敏感（docs/06 §13.1）
  "location_consent": true,         // 常去球馆
  "coach_visible_consent": false    // 教练侧总开关；详 M9-06
}
```

服务层校验：

- 读取字段前先校验对应 `*_consent` 为 true，否则返回 null
- 写入时仅当 consent 为 true 才入库；consent 为 false 时清空对应列
- LLM 调用走 `chat_prompt.py` 时**禁止**透传 `known_injuries`（[`docs/06 §13.1`](../06-数据安全与隐私合规文档.md) 硬约束，AC-3）

### 3.5 与一期 `users.golf_level` 关系

| 字段 | 位置 | 用途 |
| --- | --- | --- |
| `golf_level` (一期) | `users` | 粗粒度档位（4 档），首页 / 教学路径推荐用 |
| `handicap_official` / `handicap_self` (二期) | `user_profiles_v2` | 精确差点；评分文案 / 课程推荐 / M13 约球 |

**冲突解决**：M9-03 UI 同时收集 `golf_level` (旧 4 档) 与 `handicap_self` (新数值)；后端**两边都存**，不同步覆盖。

---

## 四、字段 / 配置草案 v0.1

### 4.1 Migration `0017_m9_user_profiles_v2.py`

```python
"""M9 P2-M9-01 user_profiles_v2 + user_clubs 数据模型

逻辑编号：docs/03 §8.7 规划 0008（M9 首个迁移）；
实际落库编号：0017（按 alembic head 续编，head=0016）
"""
revision = "0017"
down_revision = "0016"

def upgrade():
    op.create_table("user_profiles_v2", ...)
    op.create_table("user_clubs", ...)

def downgrade():
    op.drop_table("user_clubs")
    op.drop_table("user_profiles_v2")
```

### 4.2 配置项

```python
# backend/app/config.py
PHASE2_PROFILE_V2_ENABLED: bool = False  # 默认 false；M9-02 UI 上线时切 true
```

### 4.3 Pydantic schema 草案

```python
class UserProfileV2Read(BaseModel):
    user_id: str
    handicap_official: Optional[Decimal]
    handicap_self: Optional[Decimal]
    handicap_source: Optional[Literal["rcga","usga","self"]]
    height_cm: Optional[int]
    weight_kg: Optional[int]
    handedness: Optional[Literal["right","left","switch"]]
    known_injuries: list[str] = []
    mid_long_goals: list[str] = []
    training_preference: Optional[Literal["video","text","mixed"]]
    favorite_course_ids: list[str] = []
    privacy_payload: dict[str, bool] = {}
    coach_visible_fields: list[str] = []
```

---

## 五、验证数据

### 5.1 单测（AC-2）

- `tests/test_user_profile_v2_model.py`：
  - 双表 ORM 实例化 + relationships
  - CHECK 约束触发（handicap > 54 → IntegrityError）
- `tests/test_user_profile_v2_service.py`：
  - privacy_payload 校验（consent=false → 读返回 null）
  - `add_club()` 第 15 支触发 `BadRequestError`
- 覆盖率 ≥85%

### 5.2 Migration 跑通（AC-3）

- staging：`alembic upgrade head` 跑通 ≤5s
- 回滚：`alembic downgrade -1` 跑通 ≤5s + 表已删
- `pg_dump` 对比 schema 与 §3.2 / §3.3 一致

### 5.3 跨表关联检验

- 删除 `users` 行 → `user_profiles_v2` / `user_clubs` 行联动删除（ON DELETE CASCADE）

---

## 六、W17-W19 周计划

> 短小任务（3 PW）；不阻塞 M9 后续 UI 任务。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；冻结 `user_profiles_v2` / `user_clubs` schema v0.1；与 M9-03/04/05/06 owner 对齐字段消费方式 | ☑ schema review 通过；☑ FR-3 privacy_payload 字段 5 个 consent 确认 |
| **W18** | ORM model + Pydantic schema + service 框架 + 单测 ≥85% | ☑ model 与 schema 1:1；☑ service `add_club()` 14 支上限单测通过 |
| **W19** | Migration 0017 + staging 跑通 + 回滚验证 | ☑ AC-1/2/3 全勾；☑ docs/03 §8.3 v0.1 → v1.0 PR 提交（与 #20 收尾合并） |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；ORM + service + migration |
| 隐私 / 安全 | privacy_payload 5 个 consent 字段 review；LLM 透传 grep 单测脚本 |
| 算法（M7-16） | 提前 review `training_preference` 字段含义 |
| 客户端 | W19 拿到 schema 后 mock；M9-02/03 W20+ 接入 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 老 `users.golf_level` 与新 `handicap_official` 双写不一致 | M9-03 UI 同时收两值；服务层不联动覆盖；展示按场景择优 |
| R-02 | `known_injuries` 字段在客服 / 教练运营场景被误用 | docs/06 §13.1 已硬约束；W19 加 grep 单测验证 LLM prompt 内无 `known_injuries` |
| R-03 | `user_clubs` 应用层 14 支上限被绕过 | service `add_club()` 校验 + DB CHECK ≤14 触发器（W19 评估是否必要） |
| R-04 | Alembic 实际编号 0017 与 docs/03 §8.7 规划 0008 不一致引发文档混乱 | migration 文件 docstring 内交叉引用；§2.4 已明示 |
| R-05 | `privacy_payload` JSON schema 没有强校验 | service 层用 Pydantic 强类型；DB 层 JSONB 不约束（性能优先） |

### 7.3 AC 兜底（复述 docs/23 §5.1）

- [ ] **AC-1**：docs/03 §8.3.1 / §8.3.2 v0.1 → v1.0 转正 PR
- [ ] **AC-2**：ORM model + Pydantic schema 代码就位，单测覆盖率 ≥85%
- [ ] **AC-3**：Alembic 迁移 staging 跑通 + 回滚验证

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 | 下游消费 |
| --- | --- | --- |
| P2-M9-02 装备清单 UI | `user_clubs` 表 + service.add_club() | UI 调 API 增删 |
| P2-M9-03 真实差点身体利手 | `user_profiles_v2.handicap_* / height_cm / weight_kg / handedness / known_injuries` | onboarding 6 题 |
| P2-M9-04 目标 + 训练偏好 | `mid_long_goals / training_preference / weekly_target_sessions` | onboarding 续题 |
| P2-M9-05 常去球馆 | `favorite_course_ids` | M13 约球前置 |
| P2-M9-06 教练侧只读视图 | `coach_visible_fields` | M8 教练看板 |
| P2-M7-05 球杆标尺 | `user_clubs.club_type` 数据 | 评分文案"按你的 X 评分" |
| P2-M7-16 LLM 文案 | `handicap_self / training_preference` | 文案差异化 |
| P2-M11 课程推荐 | `mid_long_goals` | 学习路径个性化 |
| P2-M13 约球匹配 | `favorite_course_ids / handicap_self` | 匹配算法 |

### 8.2 一期 `golf_level` 4 档与二期 `handicap_self` 映射建议

| golf_level | handicap_self 建议 | 用途 |
| --- | --- | --- |
| beginner | 36+ 或 null | 用户未做精确差点估计时 fallback |
| elementary | 25-35 | 精确差点缺失时默认值 |
| intermediate | 15-24 | 精确差点缺失时默认值 |
| advanced | < 15 | 精确差点缺失时默认值 |

仅 UI 引导用，不双向覆盖。

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；表 schema v0.1 + privacy_payload 设计 + W17-W19 周计划 |
| v0.2 | W19 收尾 | docs/03 §8.3 转正后 PR；本文件 superseded |
