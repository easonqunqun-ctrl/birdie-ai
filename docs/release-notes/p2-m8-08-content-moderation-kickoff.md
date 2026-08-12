# P2-M8-08 · 教练上传素材审核（语音/视频/文字走 docs/06 内容安全）· 启动包（W25 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.8`](../23-二期可编码规格说明书.md#48-p2-m8-08--教练上传素材审核语音--视频--文字走-docs06-内容安全)
> 前置：M8-04 / M8-05 / [`docs/06 §7.2`](../06-数据安全与隐私合规文档.md)

---

## 一、文档目的与边界

为 **P2-M8-08** 落地 W25-W28 后端 SOP，复用一期"腾讯云内容安全"基础设施，对教练所有 UGC（语音/视频/图片/文字）做异步审核。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不改一期内容安全 client 封装
- 不实现备用供应商切换（R-XX 列入风险）

---

## 二、现状盘点

### 2.1 一期能力

```
backend/app/services/content_safety_service.py
  → 腾讯云 IMS/ATS/TMS 三合一封装（图/音/文）
  → 当前主用：chat_messages 文本审核
```

### 2.2 缺口（vs docs/23 §4.8 FR）

- 教练 4 类素材尚未挂审核 hook
- 没有 manual_review 队列管理后台
- 没有 fail-safe pending 默认策略

---

## 三、模块设计

### 3.1 改造 + 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Hook 注入 | `services/coach_annotation_service.py` + `coach_task_service.py` | 0.5 PW |
| 异步任务 | `services/content_moderation_tasks.py`（celery / asyncio） | 0.5 PW |
| Manual review 队列 | `models/moderation_queue.py`（新表） | 0.5 PW |
| Admin UI | `backend/admin/moderation/`（fastapi-admin） | 0.5 PW |
| 单测 | tests | — |

**合计：~2 PW**

### 3.2 审核流程

```
教练上传 → service 写 audit_status='pending' is_visible=false
       → 触发异步 task → 腾讯云 API
       → 通过：audit_status='approved' is_visible=true
       → 拒绝：audit_status='rejected' + 通知教练
       → 边缘：audit_status='manual_review' + 入队列
                                             → 后台 24h 人工
```

### 3.3 `moderation_queue` 表 v0.1（追加 docs/03）

```sql
CREATE TABLE moderation_queue (
    id              VARCHAR(32) PRIMARY KEY,
    target_table    VARCHAR(64) NOT NULL,  -- analysis_annotations | coach_assigned_tasks
    target_id       VARCHAR(32) NOT NULL,
    media_type      VARCHAR(20) NOT NULL,  -- image | audio | video | text
    media_url       VARCHAR(512),
    ai_risk_label   VARCHAR(64),
    ai_risk_score   FLOAT,
    reviewer_user_id VARCHAR(32),
    reviewer_action VARCHAR(20),           -- approve | reject
    reviewer_note   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ,
    sla_deadline_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);
CREATE INDEX idx_moderation_pending ON moderation_queue(reviewed_at, sla_deadline_at) WHERE reviewed_at IS NULL;
```

### 3.4 Fail-safe 策略（FR-5）

- 腾讯云 API 5xx → `audit_status='pending'` + 入 manual_review 队列
- 即使 API 全挂，**默认不展示**（is_visible=false）；不会出现"未审核内容直发学员"
- 监控：审核 success rate <95% 触发 Sentry 告警

### 3.5 误杀 / 漏过抽样

- 每周抽 100 条 manual_review 样本人工复核
- 误杀率 ≤1% / 漏过率 ≤0.5%（NFR）
- 季度 review 调阈值

---

## 四、字段 v0.1

无新 API；行内 `audit_status` 字段已在 M8-04 / M8-05 各表定义。

### 4.1 配置

```python
CONTENT_MODERATION_PROVIDER: str = "tencent"   # tencent | aliyun（备用）
CONTENT_MODERATION_TIMEOUT_SEC: int = 3
CONTENT_MODERATION_SLA_HOURS: int = 24
```

---

## 五、验证数据

- 单测：fixture 黄反图 → rejected（AC-1）
- 单测：fixture 边缘案 → manual_review；24h 内处理（AC-2）
- 模拟腾讯 API 5xx → fail-safe pending + 不可见（AC-3）

---

## 六、W25-W28 周计划

| 周 | 任务 |
| --- | --- |
| W25 | manual_review 表 + admin UI |
| W26 | hook 注入 M8-04 / M8-05 |
| W27 | 异步 task + fail-safe |
| W28 | 抽样复核流程 + Sentry 告警 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | hook + 异步 + 队列 |
| 合规 | 抽样复核 SOP |
| 管理员 | manual_review 24h SLA |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 腾讯云额度耗尽 | 备用阿里云供应商灰度切换 |
| R-02 | 24h SLA 超时（无人值班） | 周末 on-call；超时进 Sentry |
| R-03 | 误杀率高 | 抽样 + 阈值微调；教练申诉通道 |
| R-04 | fail-safe 误推 pending | 默认不可见；不展示给学员 |

### AC

- [ ] AC-1 黄反图 → 自动拒
- [ ] AC-2 manual_review 24h 内
- [ ] AC-3 fail-safe pending

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-04 批注 | 共享审核流 |
| P2-M8-05 派发 | custom_video 审核 |
| docs/06 §7.2 | 复用一期内容安全 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；hook + 队列 + fail-safe |
