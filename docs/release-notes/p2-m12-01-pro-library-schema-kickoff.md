# P2-M12-01 · 职业球手对比库数据模型（6 张表）· 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.0-2.1 期间，落地 M12 职业球手对比库 全部 10 任务的数据地基
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §8.1 · P2-M12-01`](../23-二期可编码规格说明书.md#81-p2-m12-01--数据模型6-张表)
> 合规：版权来源 `license_status` 三态（public_clip / authorized / partnership），`source_credit` 必填
> 关联：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（**软依赖**：M12 球手镜头与 ECS v2 标定集共享部分原片来源）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M12-01 球手 6 张表数据模型**落地一份「**W17 即可起跑、W19 6 表 + Alembic 就绪**」的后端 SOP，让后端 + 合规明确：

- 当前没有任何球手对比相关表，是 M12 模块的**完全新建数据地基**
- 6 表 schema v0.1（pro_players / pro_swing_clips / pro_clip_annotations / pro_topics / user_pro_favorites / user_pro_match_history）
- `license_status` 三态（public_clip / authorized / partnership）+ `source_credit` 合规硬约束
- `features_snapshot` JSONB 与 M7 V2 新特征字段一一对应（`new_features_payload` 复用）
- 与 M12-02~10 / M11-02（lesson.pro_clip_ids）/ M8-09（教练 M8 引用）下游消费

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/03`](../03-数据库设计文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不入库任何真实球手镜头数据 | P2-M12-02 负责（"第一批 10-20 位"）；本任务只建空表 |
| 不实现匹配算法 | P2-M12-04 负责 |
| 不实现叠加播放 / 雷达图 UI | P2-M12-05 负责 |
| 不引入版权采集 / 授权管理后台 | 长期议题；MVP 期靠 `license_status` 字段 + 运营手工 |
| 不限制本任务 schema 与 M7 V2 新特征字段的同步周期 | M7 V2 字段陆续上线时，本表 `features_snapshot` 字段 **追加** 而非重建 |

### 1.3 与其他文档的关系

```
docs/23 §8.1          ← 需求真源
docs/03 §8.5.1~§8.5.6 ← 6 表结构（拟）
docs/03 §9.1          ← new_features_payload JSONB schema（M7 V2 字段权威）
本文件                 ← 模型 / migration / 合规 SOP
  ↓ W19 回流
docs/03 §8.5          ← v0.1 → v1.0
docs/02 §11.6         ← /v1/pros 接口字段细化（M12-03 接入后再回流）
```

---

## 二、现状盘点

### 2.1 当前完全空白

- `backend/app/models/` 无 pro_* 模型
- `backend/alembic/versions/` 无球手相关 migration
- `client/src/types/` 无 pro_player / pro_clip 类型
- 一期 swing_analyses 只存"普通用户"分析；与球手数据**完全无关**

### 2.2 一期相关依赖（可复用）

| 文件 | 行数 / 要点 | M12 复用 |
| --- | --- | --- |
| `ai_engine/app/pipeline/constants.py` `FEATURES` | 一期 15 特征元数据 | **复用**：`pro_swing_clips.features_snapshot` 字段对齐这 15 特征 + M7-08 新增 5 特征 |
| `ai_engine/app/pipeline/scoring.py` | 单挥杆评分 | **复用**：球手镜头入库时同样跑评分管线，存 `overall_score` |
| `backend/app/models/base.py` | `Base / TimestampMixin / SoftDeleteMixin` | **复用** |
| `backend/app/models/user.py` | 一期 User 表 | **关联**：user_pro_favorites / user_pro_match_history 外键到 users.id |

### 2.3 已知缺口（vs docs/23 §8.1 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 6 张表落地 | ❌ 无 | 新建表 |
| FR-2 `license_status` 三态 | ❌ 无 | CHECK 约束 |
| FR-3 `source_credit` + `source_url` NOT NULL | ❌ 无 | NOT NULL 约束 |
| FR-4 `features_snapshot` JSONB 与 M7 V2 一一对应 | ❌ 无 | JSONB schema 草案（与 docs/03 §9.1 对齐） |
| FR-5 ORM + Pydantic + Alembic 0009 migration | ❌ 无 | 全新代码；实际编号 0019（详 §2.4） |

### 2.4 编号说明

- docs/23 §8.1 规划 `Alembic 迁移 0009_m12_pro_library_schema.py`
- 实际 alembic head 已到 `0016`；M9-01 占 0017，M11-01 占 0018
- 本任务实际编号 `0019_m12_pro_library_schema.py`，docs/03 §8.7 逻辑编号 0009 在 migration docstring 内交叉引用

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| ORM model | `backend/app/models/pro_library.py`（新） | 6 表类 | 2 PD |
| Pydantic schema | `backend/app/schemas/pro_library.py`（新） | Create/Update/Read | 0.7 PD |
| Service 框架 | `backend/app/services/pro_library_service.py`（新） | 查询 / 收藏 / 匹配记录 | 1 PD |
| Migration | `backend/alembic/versions/0019_*.py` | 6 表 + 索引 + FK + CHECK | 0.8 PD |
| 单测 | `backend/tests/test_pro_library_*.py` | 6 表 + license/source 约束 | 1 PD |
| Feature flag | `backend/app/config.py` | `PHASE2_PROS_ENABLED: bool = False` | 0.2 PD |

**合计：~5.7 PD**（与 docs/23 §8.1 估时 4 PW 略宽，含 6 表 ORM + service buffer）

### 3.2 6 表 schema v0.1

#### 3.2.1 `pro_players` 球手主表

```sql
CREATE TABLE pro_players (
    id              VARCHAR(32) PRIMARY KEY,            -- pp_<nanoid>
    name            VARCHAR(60) NOT NULL,                -- "罗里·麦克罗伊"
    name_en         VARCHAR(80),                          -- "Rory McIlroy"
    nationality     VARCHAR(3),                            -- ISO 3166-1 alpha-3
    handedness      VARCHAR(10) NOT NULL,                 -- 'right'|'left'
    height_cm       INTEGER,
    avatar_url      VARCHAR(512),
    short_bio       TEXT,
    license_status  VARCHAR(20) NOT NULL DEFAULT 'public_clip',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pp_license CHECK (license_status IN ('public_clip','authorized','partnership')),
    CONSTRAINT chk_pp_handedness CHECK (handedness IN ('right','left'))
);
CREATE INDEX idx_pp_active_sort ON pro_players(is_active, sort_order);
```

#### 3.2.2 `pro_swing_clips` 球手镜头

```sql
CREATE TABLE pro_swing_clips (
    id              VARCHAR(32) PRIMARY KEY,            -- psc_<nanoid>
    pro_player_id   VARCHAR(32) NOT NULL REFERENCES pro_players(id) ON DELETE CASCADE,
    club_type       VARCHAR(20) NOT NULL,                -- 与 client/types/api.ts ClubType 对齐
    camera_angle    VARCHAR(20) NOT NULL,                -- face_on/down_the_line
    video_url       VARCHAR(512) NOT NULL,
    thumbnail_url   VARCHAR(512),
    duration_ms     INTEGER,
    fps             INTEGER,
    -- 评分快照（跑一期 / V2 评分管线后落库）
    overall_score   INTEGER,                              -- 用一期/V2 引擎评分（同等口径，便于对比）
    engine_version  VARCHAR(20) NOT NULL DEFAULT 'v1',  -- 与 M7-14 swing_analyses.engine_version 对齐
    features_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb, -- 与 docs/03 §9.1 new_features_payload 对齐
    phase_timestamps JSONB,                                -- 阶段时间戳
    -- 版权
    license_status  VARCHAR(20) NOT NULL,                -- 与 pro_players.license_status 默认同源；可单条覆盖
    source_credit   VARCHAR(200) NOT NULL,               -- "Source: PGA Tour Highlights (YouTube)"
    source_url      VARCHAR(512) NOT NULL,               -- 原始来源 URL（如 YouTube）
    captured_year   SMALLINT,
    description     TEXT,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_psc_camera CHECK (camera_angle IN ('face_on','down_the_line')),
    CONSTRAINT chk_psc_license CHECK (license_status IN ('public_clip','authorized','partnership'))
);
CREATE INDEX idx_psc_player ON pro_swing_clips(pro_player_id, club_type);
CREATE INDEX idx_psc_published ON pro_swing_clips(is_published, club_type) WHERE is_published = TRUE;
```

#### 3.2.3 `pro_clip_annotations` 教练 PGC 解说

```sql
CREATE TABLE pro_clip_annotations (
    id              VARCHAR(32) PRIMARY KEY,
    clip_id         VARCHAR(32) NOT NULL REFERENCES pro_swing_clips(id) ON DELETE CASCADE,
    author_user_id  VARCHAR(32) NOT NULL REFERENCES users(id),       -- 教练/官方运营
    annotation_type VARCHAR(20) NOT NULL,                              -- 'text'|'voice'|'sketch'
    content         TEXT,
    time_marker_ms  INTEGER,                                            -- 该批注挂在视频哪一帧
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_visible      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pca_type CHECK (annotation_type IN ('text','voice','sketch'))
);
CREATE INDEX idx_pca_clip ON pro_clip_annotations(clip_id, time_marker_ms);
```

#### 3.2.4 `pro_topics` 每周精选

```sql
CREATE TABLE pro_topics (
    id              VARCHAR(32) PRIMARY KEY,            -- pt_<nanoid>
    code            VARCHAR(40) NOT NULL UNIQUE,         -- 'week_2026_W42'
    title           VARCHAR(100) NOT NULL,
    subtitle        VARCHAR(200),
    banner_url      VARCHAR(512),
    summary         TEXT,
    clip_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 一组 pro_swing_clips.id
    week_starts_at  DATE,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pt_published ON pro_topics(is_published, week_starts_at DESC);
```

#### 3.2.5 `user_pro_favorites` 用户收藏

```sql
CREATE TABLE user_pro_favorites (
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clip_id         VARCHAR(32) NOT NULL REFERENCES pro_swing_clips(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note            TEXT,
    PRIMARY KEY (user_id, clip_id)
);
CREATE INDEX idx_upf_user ON user_pro_favorites(user_id, created_at DESC);
```

#### 3.2.6 `user_pro_match_history` "和你最像的"匹配历史

```sql
CREATE TABLE user_pro_match_history (
    id              VARCHAR(32) PRIMARY KEY,
    user_id         VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id     VARCHAR(32) NOT NULL REFERENCES swing_analyses(id) ON DELETE CASCADE,
    matched_clip_id VARCHAR(32) NOT NULL REFERENCES pro_swing_clips(id) ON DELETE CASCADE,
    match_score     NUMERIC(5,2) NOT NULL,                -- 0-100 相似度分
    match_details   JSONB NOT NULL DEFAULT '{}'::jsonb,   -- 维度细分（如 tempo 90, plane 78 ...）
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_upmh_user ON user_pro_match_history(user_id, created_at DESC);
CREATE INDEX idx_upmh_analysis ON user_pro_match_history(analysis_id);
```

### 3.3 `features_snapshot` JSONB schema 草案

与 [`docs/03 §9.1 new_features_payload`](../03-数据库设计文档.md) 对齐，**一一同名**：

```jsonc
{
  // 一期 15 特征
  "spine_angle_setup": 31.2,
  "knee_flexion_setup": 158,
  "shoulder_rotation_top": 95,
  // ...
  // M7-08 新增 5 特征（W22+ 才会有数据）
  "tempo_subsegment_ratio": 0.68,
  "weight_transfer_ratio": 0.87,
  "kinetic_chain_delay_ms": 110,
  "head_stability_variance": 0.012,
  "rhythm_consistency": 0.89
}
```

> **关键不变量**：球手镜头入库时跑评分管线，将 `features` 整体写入 `features_snapshot`；老镜头随 M7 V2 上线**不**自动重算，需运营触发 reanalyze（M12-02 W22+ 评估）。

### 3.4 ON DELETE CASCADE 链路

```
pro_players  --DEL-->  pro_swing_clips  --DEL-->  pro_clip_annotations
                                          --DEL-->  user_pro_favorites
                                          --DEL-->  user_pro_match_history
```

users 删除时：

```
users  --DEL-->  user_pro_favorites
       --DEL-->  user_pro_match_history
pro_clip_annotations.author_user_id 走 ON DELETE RESTRICT（不允许删教练时丢解说）
```

---

## 四、字段 / 配置草案 v0.1

### 4.1 Migration

```python
# backend/alembic/versions/0019_m12_pro_library_schema.py
"""逻辑编号 docs/03 §8.7 = 0009；实际编号 0019（M9-01=0017, M11-01=0018 续编）"""
revision = "0019"
down_revision = "0018"
```

### 4.2 配置项

```python
PHASE2_PROS_ENABLED: bool = False  # 默认 false；M12-03 资源库 tab UI 上线时切 true
```

### 4.3 `license_status` 三态语义

| 取值 | 来源类型 | 上线行为 | 法律风险 |
| --- | --- | --- | --- |
| `public_clip` | YouTube / 官方公开短视频 | source_credit 显式标注 + URL 跳转原片 | 中（合理使用 + 引用） |
| `authorized` | 已获作者书面授权（个人或机构） | 显示授权来源；保留授权证明 | 低 |
| `partnership` | 与赛事 / 球手深度合作 | 联合品牌露出；可下载本地播放 | 低（合同约定） |

> MVP 期 W22 前**只**入 `public_clip` 类样本，规避审核成本（M12-02 W22 起 PoC）。

---

## 五、验证数据

### 5.1 单测（AC-2）

- `tests/test_pro_library_model.py`：
  - 6 表 ORM 实例化 + relationships
  - CHECK 约束（license_status / camera_angle / annotation_type / handedness）触发
  - source_credit / source_url NOT NULL 触发
- `tests/test_pro_library_service.py`：
  - 收藏 / 取消收藏幂等
  - 匹配历史插入 + 查询
- 覆盖率 ≥85%

### 5.2 Migration 跑通（AC-3）

- staging：`alembic upgrade head` ≤10s
- 回滚：`alembic downgrade -1` ≤10s + 6 表已删
- 验证 ON DELETE CASCADE 链路（删 pro_player → 联动删除 4 张关联表）

### 5.3 features_snapshot 与 new_features_payload 对齐校验

- 单测：构造 `pro_swing_clip.features_snapshot` → 与 `swing_analyses.new_features_payload` 字段名 set 比对，差集为空（W22 M7-08 新字段就位后再补单测）

---

## 六、W17-W19 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；冻结 6 表 schema v0.1；与 M12-02~10 / M11-01 owner 对齐字段消费 | ☑ 6 表 schema review；☑ license_status 三态评审；☑ 合规复核 PoC 法律风险 |
| **W18** | ORM model + Pydantic schema + service 框架 + 单测 ≥85% | ☑ 6 表完整；☑ license/source 约束单测通过 |
| **W19** | Migration 0019 + staging 跑通 + 回滚验证 + cascade 链路验证 | ☑ AC-1/2/3 全勾；☑ docs/03 §8.5 转正 PR 提交 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 Lead | 总 owner；ORM + service + migration |
| 算法 | features_snapshot schema 与 M7 V2 字段对齐评审 |
| 合规 / 法务 | license_status 三态 + source_credit 模板 + PGA 公开镜头合理使用边界 |
| 教研 / 内容 | 提前 review `pro_topics` 周精选格式 |
| 客户端 | W19 拿到 schema 后 mock；M12-03 W22+ 接入 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | YouTube 公开镜头被原作者投诉版权 | source_credit 显式标注 + 投诉 24h 内下架（流程对齐 [`docs/06 §13.2`](../06-数据安全与隐私合规文档.md)） |
| R-02 | M7-08 新特征 W22+ 上线，老镜头 features_snapshot 缺新字段 | 客户端按字段存在性兜底；运营 W22+ 批量 reanalyze |
| R-03 | pro_clip_annotations.author_user_id 删除链路引发"教练删账户但解说还在" | author 走 RESTRICT；教练注销时 annotation 改 author_user_id=null |
| R-04 | features_snapshot JSONB 无字段强约束，写入脏数据 | 服务层用 Pydantic 校验；DB JSONB 不约束（性能） |
| R-05 | 编号 0019 vs docs/03 §8.7 规划 0009 | docstring 交叉引用；§2.4 已明示 |

### 7.3 AC 兜底（复述 docs/23 §8.1）

- [ ] **AC-1**：docs/03 §8.5 v0.1 → v1.0 转正
- [ ] **AC-2**：6 张表 + 索引 + 约束完整就位
- [ ] **AC-3**：Alembic 迁移 staging 跑通 + 回滚验证

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 | 下游消费 |
| --- | --- | --- |
| P2-M12-02 第一批 10-20 位球手入库 | 6 表 schema + service.add_clip() | 运营导入数据 |
| P2-M12-03 资源库 tab UI | API `/v1/pros` + `/v1/pros/{id}/clips` | 浏览 / 标签筛选 |
| P2-M12-04 匹配算法 | `features_snapshot` + `user_pro_match_history` 表 | 匹配结果写入 |
| P2-M12-05 并排叠加 + 雷达图 | 双 `features_snapshot` 字段 | 维度对比 |
| P2-M12-06 每周精选 | `pro_topics` 表 | banner + 一组 clips |
| P2-M12-07 教练 PGC 解说 | `pro_clip_annotations` 表 | 教练撰写解说 |
| P2-M12-08 追平演化动画 | `features_snapshot` 历史快照 | 客户端动画 |
| P2-M12-09 教练 M8 引用 | `pro_swing_clips.id` 可在 M8 批注里引用 | 教练 / 学员看板 |
| P2-M12-10 收藏一键训练任务 | `user_pro_favorites` + `lessons.pro_clip_ids` 联动 | 加入训练计划 |
| P2-M11-01 课程数据模型 | `lessons.pro_clip_ids` 引用 `pro_swing_clips.id` | 课程引用球手镜头 |
| P2-M7-15 用户反馈 | （间接）匹配结果"踩" → 回流候选池 | 长期 |

### 8.2 合规模板

```
source_credit 示例：
- "Source: PGA Tour 官方频道（YouTube：https://youtu.be/xxx）"
- "Source: 球手 Rory McIlroy 个人 Instagram（@rorymcilroy）"
- "Source: 国信高尔夫学院授权（authorized）"
```

公开镜头投诉处理流程：

1. 收到投诉 → 24h 内 `is_published=false` + `is_active=false`
2. 法务复核 → 7d 内决定永久下架或恢复
3. 永久下架 → `DELETE FROM pro_swing_clips WHERE id=...`（CASCADE 链路触发清理 annotations / favorites / match_history）

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；6 表 schema v0.1 + license_status 三态 + W17-W19 周计划 |
| v0.2 | W19 收尾 | docs/03 §8.5 转正后 PR；本文件 superseded |
