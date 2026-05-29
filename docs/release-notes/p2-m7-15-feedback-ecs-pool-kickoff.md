# P2-M7-15 · 用户报告"顶/踩"反馈回流到 ECS 候选池 · 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.5 期间，建立"用户反馈 → ECS 候选池 → admin 审核 → ECS v2 正式集"闭环
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.15 · P2-M7-15`](../23-二期可编码规格说明书.md#315-p2-m7-15--用户报告顶--踩反馈回流到-ecs-候选池)
> 前置 kickoff：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（ECS 候选池流转）+ [`p2-m7-14-engine-version-ab-kickoff.md`](./p2-m7-14-engine-version-ab-kickoff.md)（engine_version 标签）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-15** 落地一份「**W30 即可起跑（依赖 M7-04~14 已稳态）、W34 闭环跑通**」的算法 + 后端 + 客户端 SOP，让三端明确：

- 一期 `feedbacks` 表（自由文本意见）与本任务"按报告维度的顶/踩"的区别
- `analysis_feedbacks` 新表 + `POST /v1/analyses/{id}/feedback` 接口
- "优质回馈样本"判定规则（vote 与分数一致 / 不一致的双向数据）
- admin 审核 UI MVP（最小列表 + approve / reject）
- 7 天 SLA 审核 + 闭环到 ECS v2 正式集

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) 字段 | 避免与 #18 / #19 / #20 race |
| 不动一期 `feedbacks` 表 | 自由文本反馈仍走 `feedbacks`，本任务**追加** `analysis_feedbacks` 新表 |
| 不实现"按报告自由文本评论"完整社区化 | MVP 期只做"顶/踩 + 可选 ≤140 字短文本" |
| 不实现自动入 ECS v2 | 必须 admin 人工审核（保证数据质量） |
| 不引入第三方 admin 后台 | 自建 `/admin/ecs-candidate` 简单列表 |

---

## 二、现状盘点

### 2.1 一期反馈实际形态

```
backend/app/models/feedback.py L21-44
  → Feedback 表（user_id / content TEXT / contact ≤128 / created_at）
  → CHECK content 长度 1-500
  → 同 user_id 60s 反垃圾
```

**结论**：一期 `feedbacks` 是**全局意见反馈**（"产品建议 / bug 报告"），**没有**与具体报告关联，**没有**结构化的 vote 字段，**不能**用于 ECS 候选池筛选。

### 2.2 已知缺口（vs docs/23 §3.15 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 报告页"顶/踩"按钮 + 可选短文本 | ❌ 无 | report.tsx 加按钮 + Modal |
| FR-2 `POST /v1/analyses/{id}/feedback` | ❌ 无 | 新增接口 + analysis_feedbacks 表 |
| FR-3 优质回馈自动进 ECS 候选池 | ❌ 无 | 服务层自动判定规则 |
| FR-4 admin 审核 UI MVP | ❌ 无 | `/admin/ecs-candidate` 列表 + 按钮 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 数据模型 | `backend/app/models/analysis_feedback.py`（新） | analysis_feedbacks + ecs_candidate_pool 表 | 1 PD |
| Migration | `backend/alembic/versions/00XX_*.py`（实际编号 W30 时定） | 2 张表 + 索引 | 0.5 PD |
| Service | `backend/app/services/analysis_feedback_service.py`（新） | 写入 + 优质回馈判定 | 1 PD |
| API | `POST /v1/analyses/{id}/feedback` + admin endpoints | 用户 + admin | 1 PD |
| Admin UI | `client/src/pages/admin/ecs-candidate.tsx`（新，仅 admin 可达） | 列表 + approve/reject | 1.5 PD |
| 报告页 UI | `client/src/pages/analysis/report.tsx` | 顶/踩按钮 + Modal | 1 PD |
| 单测 | model + service + API | feedback / 候选池判定 | 1 PD |

**合计：~7 PD**（与 docs/23 §3.15 估时 3 PW 偏宽，含 admin UI buffer）

### 3.2 `analysis_feedbacks` 表 v0.1

```sql
CREATE TABLE analysis_feedbacks (
    id              VARCHAR(32) PRIMARY KEY,
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id     VARCHAR(32) NOT NULL REFERENCES swing_analyses(id) ON DELETE CASCADE,
    vote            VARCHAR(10) NOT NULL,                  -- 'up'|'down'
    comment         VARCHAR(140),                            -- 可选短文本
    engine_version  VARCHAR(20),                             -- 反馈时报告的引擎版本（M7-14）
    analysis_score  INTEGER,                                 -- 反馈时报告综合分（冗余便于查询）
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_af_vote CHECK (vote IN ('up','down'))
);
CREATE UNIQUE INDEX uq_af_user_analysis ON analysis_feedbacks(user_id, analysis_id);
CREATE INDEX idx_af_analysis ON analysis_feedbacks(analysis_id, vote);
CREATE INDEX idx_af_engine_version ON analysis_feedbacks(engine_version, vote);
```

> **幂等**：UNIQUE(user_id, analysis_id) 保证同一用户同一报告只算最新一次（UPSERT 语义）。

### 3.3 `ecs_candidate_pool` 表 v0.1

```sql
CREATE TABLE ecs_candidate_pool (
    id              VARCHAR(32) PRIMARY KEY,
    analysis_id     VARCHAR(32) NOT NULL REFERENCES swing_analyses(id) ON DELETE CASCADE UNIQUE,
    candidate_reason VARCHAR(40) NOT NULL,                  -- 见 §3.4
    feedback_id     VARCHAR(32) REFERENCES analysis_feedbacks(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|approved|rejected|imported
    review_notes    TEXT,
    reviewer_user_id VARCHAR(32) REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    imported_to_ecs_id VARCHAR(64),                          -- ECS v2 manifest 行 id（imported 后填）
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ecp_status CHECK (status IN ('pending','approved','rejected','imported'))
);
CREATE INDEX idx_ecp_status_created ON ecs_candidate_pool(status, created_at);
```

### 3.4 优质回馈判定规则（FR-3）

| 触发条件 | candidate_reason | 价值 |
| --- | --- | --- |
| `vote=up` 且 `analysis_score >= 80` | `high_score_up` | "高分被赞"——AI 真正抓准了顶尖动作 |
| `vote=down` 且 `analysis_score >= 80` | `high_score_down` | "高分被踩"——AI 高估，需要补反例 |
| `vote=down` 且 `analysis_score <= 40` 且有 comment | `low_score_explained_down` | "低分被踩 + 用户解释"——AI 误判，需要标定 |
| `vote=up` 且 `analysis_score <= 40` | `low_score_up` | "低分被赞"——AI 低估，用户认可问题描述 |
| 其他 | 不入候选池 | — |

服务层每次写入 `analysis_feedbacks` 后异步检查这些规则，符合则 INSERT 到 `ecs_candidate_pool`（status=pending）。

### 3.5 admin 审核 UI MVP

- 路由：`/admin/ecs-candidate`（仅 admin role 可达；JWT scope `admin` 校验）
- 列表字段：analysis_id / 缩略图 / vote / score / candidate_reason / comment / created_at
- 操作：approved（写入 ECS v2 manifest 候选）/ rejected（不入）/ 详情查看
- 7 天 SLA：超期未审条目顶部高亮

### 3.6 与 ECS v2 manifest 联动

- approved 行触发 `tools/ecs_v2_import.py`（W30 实现），将 video URL + metadata 追加到 ECS v2 manifest
- `imported_to_ecs_id` 字段回填 → status=imported
- 失败可重试

---

## 四、字段 / 配置草案 v0.1

### 4.1 `POST /v1/analyses/{id}/feedback`

```
Request: { "vote": "up", "comment": "节奏判断很准" }
Response: { "id": "af_xxx", "vote": "up", "candidate_pool_id": "ecp_yyy" | null }
```

`candidate_pool_id` 非 null 时表示进入候选池。

### 4.2 配置项

```python
PHASE2_USER_FEEDBACK_ENABLED: bool = False  # 默认 false；W31 灰度 100% 后切 true
```

### 4.3 报告页 UI 草案

- 报告底部"这份报告对你有帮助吗？" + 👍 / 👎 按钮（emoji 仅在用户端，AGENTS.md 仅限定 AI 回复）
- 点击后弹"想多说几句吗？（可选）"短文本 Modal（≤140 字）
- 已反馈用户：按钮高亮显示当前选择

---

## 五、验证数据

### 5.1 单测

- model：UNIQUE(user_id, analysis_id) 幂等
- service：4 种规则触发判定单测
- API：vote=up + score=85 → 候选池 1 行

### 5.2 端到端演练（AC-3）

- 模拟 100 条反馈 → 至少 30 条进候选池 → admin 审核 10 条 approved → 10 条 import 到 ECS v2 manifest
- ECS v2 W22 起在跑；本任务接入后**新增** 10 条来自用户反馈的样本

---

## 六、W30-W34 周计划

> **硬门槛**：M7-04 / M7-06 / M7-14 已在 W22-W26 灰度 100%；ECS v2 W22 起在迭代。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W30** | 本文件评审；冻结 vote / candidate_reason 枚举 | ☑ schema review；☑ admin UI 设计稿 |
| **W31** | 数据模型 + Migration + service + API | ☑ POST feedback API 端到端 smoke |
| **W32** | 报告页 UI 改造 + jest 单测 | ☑ 顶/踩按钮 + Modal 上线灰度 5% |
| **W33** | admin 审核 UI + 7 天 SLA 标记 | ☑ AC-2 通过 |
| **W34** | ECS v2 import 链路 + 至少 1 轮端到端跑通 | ☑ AC-1/2/3 全勾；☑ 候选池 → ECS 流程文档化 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；表 + service + API |
| 客户端 | 报告页 UI + admin UI |
| 算法 | ECS v2 import 脚本 + 候选池规则评审 |
| 运营 / admin | 7 天 SLA 审核 + 边界 case 反馈 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 用户大量恶意"踩" | 同 user_id 60s 反垃圾；同一报告幂等（UPSERT） |
| R-02 | 候选池审核积压 | 7 天 SLA 监控；积压 >100 条告警 |
| R-03 | comment 文本含敏感词 | 走 [`docs/06 §7.2`](../06-数据安全与隐私合规文档.md) 内容安全过滤 |
| R-04 | 反馈表与 swing_analyses 关联失败（报告软删除场景） | ON DELETE CASCADE；软删除场景 service 层过滤 deleted_at |

### 7.3 AC 兜底（复述 docs/23 §3.15）

- [ ] **AC-1**：报告页顶/踩入口上线（灰度 100%）
- [ ] **AC-2**：ECS 候选池表 + admin UI 上线 + 7 天 SLA 监控
- [ ] **AC-3**：至少 1 轮"候选池 → ECS v2 正式集"端到端跑通

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务关系 |
| --- | --- |
| P2-M7-01 ECS v2 | 提供 manifest import 接口；本任务追加候选池数据 |
| P2-M7-06 置信度 | 低 confidence 报告"踩"权重更高（W34 评估） |
| P2-M7-14 engine_version | 反馈数据带 engine_version 标签便于按版本回归 |
| P2-M7-04/05/07/08/10 | 各任务 V2 实施时可消费候选池数据迭代标尺 |

### 8.2 candidate_reason 详解

| 取值 | 触发条件 | ECS 用途 |
| --- | --- | --- |
| `high_score_up` | up + score>=80 | 正例验证集 |
| `high_score_down` | down + score>=80 | 反例（疑似过分） |
| `low_score_explained_down` | down + score<=40 + comment | 误判候选 |
| `low_score_up` | up + score<=40 | 用户低估值认知差异样本 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；表 schema + 4 种候选池触发规则 + admin UI MVP |
