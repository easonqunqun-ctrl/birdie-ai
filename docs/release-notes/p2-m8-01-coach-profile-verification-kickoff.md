# P2-M8-01 · coach_profiles / coach_verifications + 资质审核后台 · 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.0-2.1 期间，落地教练数据模型 + 资质审核流程，是 M8 教练工作台 10 任务的数据地基
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §4.1 · P2-M8-01`](../23-二期可编码规格说明书.md#41-p2-m8-01--coach_profiles--coach_verifications-数据模型--资质审核后台)
> 合规：[`docs/06 §13.2`](../06-数据安全与隐私合规文档.md)（教练侧合规）
> 前置：DEP-02（教练 BD）、DEP-08（隐私授权评审）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M8-01** 落地一份「**W17 即可起跑、W21 资质审核流程上线**」的后端 + 产品 SOP，明确：

- 当前空白：无教练数据模型，无教练审核流程
- `coach_profiles` + `coach_verifications` 双表 schema v0.1
- 资质材料 AES-256 加密 + 访问审计（docs/06 §四）
- 资质审核 24h SLA + 服务通知模板
- M8-03 ~ M8-10 共用 Alembic migration `0011_m8_coach_core.py`（实际 0020 / 0021，详 §2.4）

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22/23/03/06 字段 | 避免与 #18/#19/#20 race |
| 不实现教练身份切换 UI | M8-02 负责 |
| 不实现学员双向 opt-in | M8-03 负责 |
| 不实现批注 / 作业等业务功能 | M8-04~10 各自负责 |
| 不引入第三方资质核验 API（如人脸识别） | MVP 期人工审核 |

### 1.3 与其他文档的关系

```
docs/23 §4.1          ← 需求真源
docs/03 §8.2.1 / §8.2.2 ← 双表 schema（拟）
docs/06 §13.2 / §四    ← 加密 + 访问审计
docs/02 §11.2         ← 接口（拟）
```

---

## 二、现状盘点

### 2.1 当前完全空白

- `backend/app/models/` 无 coach_* 模型
- `backend/alembic/versions/` 无教练相关 migration
- `client/src/pages/` 无教练侧入口
- 一期 `users` 表是统一身份；二期教练**复用** user_id

### 2.2 一期可复用

| 文件 | 用途 |
| --- | --- |
| `backend/app/models/user.py` | User 表（教练复用 user_id） |
| `backend/app/models/base.py` Base + TimestampMixin | 复用 |
| `backend/app/storage/` | 对象存储（资质材料走加密 bucket） |
| 一期订阅消息（W3-W4 已上线）| 复用模板基础设施，新增"教练审核完成"模板 ID |

### 2.3 已知缺口（vs docs/23 §4.1 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 `coach_profiles` 表 | ❌ | 新建 |
| FR-2 `coach_verifications` 表 | ❌ | 新建 |
| FR-3 用户侧申请页 | ❌ | UI + API |
| FR-4 Admin 后台 | ❌ | UI + API |
| FR-5 状态变更通知 | ❌ | 新模板 ID |
| FR-6 AES-256 加密存储 + 访问审计 | ❌ | 加密 bucket + 审计日志 |

### 2.4 编号说明

- docs/23 §4.1 规划 `Alembic 0011_m8_coach_core.py`（与 M8-03~08 共用）
- 实际 alembic head：0016；M9-01 占 0017，M11-01 占 0018，M12-01 占 0019
- 本任务实际编号：`0020_m8_coach_core.py`（M8-01/02/03 共用），docs/03 §8.7 逻辑编号 0011 在 docstring 内交叉引用

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| ORM model | `backend/app/models/coach.py`（新） | CoachProfile + CoachVerification | 1 PD |
| Pydantic schema | `backend/app/schemas/coach.py`（新） | Apply / Read / Review | 0.5 PD |
| Service | `backend/app/services/coach_service.py`（新） | apply / review / status 切换 | 1.5 PD |
| Migration | `backend/alembic/versions/0020_m8_coach_core.py` | 2 张表（M8-03 W23 时会扩到 3 张） | 0.5 PD |
| 用户 API | `/v1/coach/profile/apply` / `/me` | 申请 + 查询 | 1 PD |
| Admin API | `/v1/admin/coach/verifications` | 待审列表 + 审核 | 1 PD |
| Admin UI MVP | `client/src/pages/admin/coach-verifications.tsx` | 列表 + 审核操作 | 1.5 PD |
| 用户申请页 | `client/src/pages/coach/apply.tsx` | 上传资质 + 表单 | 1.5 PD |
| 加密存储 | `backend/app/storage/encrypted.py` 拓展 | AES-256 加密 + 审计 | 1 PD |
| 通知模板 | 微信订阅消息申请 | 新模板"教练审核完成" | 0.5 PD |
| 单测 | 多个 | 全链路 | 1 PD |

**合计：~11 PD**（与 docs/23 §4.1 估时 4 PW 偏宽；含加密 / 审计 / Admin UI buffer）

### 3.2 `coach_profiles` 表 schema v0.1

```sql
CREATE TABLE coach_profiles (
    user_id         VARCHAR(32) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name    VARCHAR(60) NOT NULL,
    avatar_url      VARCHAR(512),
    level           VARCHAR(20) NOT NULL,                  -- 'pga'|'china_pga'|'regional'|'club_pro'
    bio             TEXT,
    certifications  JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{type, number, issued_at, ...}]
    specialties     JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ['driver','short_game',...]
    service_cities  JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ['深圳','广州']
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|active|rejected|paused
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at     TIMESTAMPTZ,
    rejected_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cp_status CHECK (status IN ('pending','active','rejected','paused')),
    CONSTRAINT chk_cp_level CHECK (level IN ('pga','china_pga','regional','club_pro'))
);
CREATE INDEX idx_cp_status ON coach_profiles(status, applied_at);
```

### 3.3 `coach_verifications` 表 schema v0.1

```sql
CREATE TABLE coach_verifications (
    id              VARCHAR(32) PRIMARY KEY,
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    materials       JSONB NOT NULL DEFAULT '[]'::jsonb,
        -- [{type:'pga_cert', url_enc:'cos://...enc', uploaded_at, sha256}, ...]
    review_status   VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|approved|rejected|need_more
    reviewer_user_id VARCHAR(32) REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_cv_status CHECK (review_status IN ('pending','approved','rejected','need_more'))
);
CREATE INDEX idx_cv_status_submitted ON coach_verifications(review_status, submitted_at);
CREATE INDEX idx_cv_user ON coach_verifications(user_id, submitted_at DESC);
```

> 每次申请 / 复审独立一行（FR-2）；被驳回用户重新提交时**创建新行**，coach_profile.status 保持 'rejected'（AC-4）。

### 3.4 资质材料加密存储

```python
# backend/app/storage/encrypted.py
def upload_certification(user_id: str, file_bytes: bytes, file_type: str) -> dict:
    """AES-256-GCM 加密 → COS encrypted/coach-cert/ bucket
       返回 { url_enc, sha256, encrypted_at }
       审计写 cert_access_log 表（W21 评估是否独立表 / 共用 event_logs）"""
    ...
```

读取时按 user_id 校验访问权限（仅 admin / 用户本人 / 审核员）。

### 3.5 资质审核 24h SLA

- Admin Web 看板按提交时间排序（FIFO）
- 超过 24h 未审核条目自动高亮 + 微信群通知 admin
- SLA 报表：每月统计 24h 内审核率，目标 ≥90%

### 3.6 微信订阅消息新模板

- 模板：「教练审核完成」（仅在用户授权订阅后发送）
- 触发：`review_status` 变更到 approved / rejected
- 内容：审核结果 + 简要原因 + 后续步骤

---

## 四、字段 / 配置草案 v0.1

### 4.1 API（docs/02 §11.2 拟）

```
POST /v1/coach/profile/apply       Body: { display_name, level, bio, specialties, ... }
GET  /v1/coach/profile/me
PUT  /v1/coach/profile/me

POST /v1/coach/verifications       Body: multipart files
GET  /v1/coach/verifications/me

# Admin
GET  /v1/admin/coach/verifications?status=pending
POST /v1/admin/coach/verifications/{id}/review   Body: { decision, notes }
```

错误码：

- `40310` 当前账号不是已审核教练
- `40311` 资质审核被驳回（需重新提交）

### 4.2 配置项

```python
PHASE2_COACH_ENABLED: bool = False  # 默认 false；W21 灰度 5 位种子教练 → 50 → 全量
```

### 4.3 灰度策略（FR + 风险 R-02）

- W21：5 位种子教练（DEP-02 BD）
- 3 天稳定后：开 50 位
- 再 7 天稳定：全量开放

---

## 五、验证数据

### 5.1 单测

- model：CHECK 约束 (level / status / review_status) 触发
- service：审核流转 pending→approved / rejected / need_more 全覆盖
- API：申请 / 查询 / 审核 端到端

### 5.2 加密存储验证

- 上传资质 → COS 对象元数据含 `x-amz-server-side-encryption: AES256` 或自实现加密标记
- 读取需走 service 层 + 鉴权
- 审计日志记录每次访问

### 5.3 SLA 验证

- 注入 100 条申请，模拟 50 条 24h 内审核 → SLA 报表显示 50%
- 触发自动告警（>24h 未审）

---

## 六、W17-W21 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 评审；冻结 schema；与 M8-02/03 owner 对齐 0020 migration | ☑ schema review；☑ 微信新模板申请提交 |
| **W18** | ORM model + Pydantic schema + service 框架 | ☑ 单测 ≥85% |
| **W19** | 加密存储 + 用户申请页 + 用户 API | ☑ 申请端到端 |
| **W20** | Admin API + Admin UI MVP | ☑ 审核流转端到端 |
| **W21** | SLA 监控 + 微信通知 + 灰度 5 位种子 | ☑ AC-1/2/3/4 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；schema + service + API |
| 客户端 | 用户申请页 + Admin UI |
| 隐私 / 合规 | 加密存储 + 访问审计 + docs/06 §13.2 复核 |
| 教练 BD（DEP-02） | 5 位种子教练招募 |
| 产品 | 微信新模板文案 + 审核 SOP |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 微信新模板申请延期 | 走小程序 service message fallback；模板 ID 申请并行 W17 启动 |
| R-02 | 5 位种子教练 BD 滞后 | DEP-02 必须 W20 前到位；否则灰度顺延 |
| R-03 | 资质材料加密性能差（大图） | 走 COS Server-Side Encryption；自实现加密时只对 metadata 加密 |
| R-04 | 审核员 24h SLA 难保证 | 双人轮值 + 自动催办；月度 SLA 报表追溯 |
| R-05 | docs/03 §8.7 规划 0011 vs 实际 0020 | docstring 交叉引用；§2.4 已明示 |

### 7.3 AC 兜底（复述 docs/23 §4.1）

- [ ] **AC-1**：资质审核 24h SLA ≥90%
- [ ] **AC-2**：加密落库 + 审计日志可查
- [ ] **AC-3**：状态变更通知触达率 ≥95%
- [ ] **AC-4**：审核被拒可重新提交（新行 + status 保持 'rejected'）

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M8-02 身份切换 | 依赖 coach_profiles.status='active' |
| P2-M8-03 学员绑定 | 共用 0020 migration（追加 coach_student_relations） |
| P2-M8-04~10 | 业务功能均依赖 M8-01 资质就绪 |
| P2-M8-10 教练 BD 工具 | 数据源 |
| DEP-02 教练 BD | 5 位种子教练 |

### 8.2 资质类型枚举

```jsonc
{
  "certifications": [
    {"type": "pga_class_a", "number": "12345", "issued_at": "2020-01-15", "country": "USA"},
    {"type": "china_pga", "number": "67890", "issued_at": "2023-06-20"},
    {"type": "regional_assoc", "association": "广东省高协", "number": "...", ...},
    {"type": "club_pro", "venue": "深圳某球会", "since": "2015"}
  ]
}
```

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；双表 schema + 加密存储 + 24h SLA + 灰度 5 位种子 |
