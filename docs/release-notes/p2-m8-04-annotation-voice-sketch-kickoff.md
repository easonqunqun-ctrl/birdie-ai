# P2-M8-04 · 报告语音 30s + 涂鸦批注 · 启动包（W23 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.4`](../23-二期可编码规格说明书.md#44-p2-m8-04--报告语音-30s--涂鸦批注analysis_annotations)
> 前置：[`p2-m8-03-student-binding-kickoff.md`](./p2-m8-03-student-binding-kickoff.md)
> 合规：[`docs/06 §7.2`](../06-数据安全与隐私合规文档.md)（内容安全）

---

## 一、文档目的与边界

为 **P2-M8-04** 落地 W23-W28 客户端 + 后端 SOP，实现教练在学员报告上录 30s 语音 + 涂鸦 + 文字批注。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不实现作业派发（M8-05）
- 不实现学员看板（M8-06）
- 不动一期 report.tsx 用户视角（教练视角独立组件）

---

## 二、现状盘点

- 一期 report.tsx 仅展示 AI 报告，无人工批注
- 一期已有 COS 上传 + 内容安全审核基础设施
- M8-03 提供师生关系 + 字段级可见性约束

### 缺口（vs docs/23 §4.4 FR）

8 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ORM model | `backend/app/models/coach.py` 追加 AnalysisAnnotation | 0.5 PW |
| Migration | 0020 追加（M8 共用） | 0.3 PW |
| Service | `backend/app/services/coach_annotation_service.py` | 1 PW |
| API | POST/GET/DELETE annotations | 0.7 PW |
| 教练侧 UI | `pages/coach/analysis-annotate/index.tsx` 4 入口 | 1.5 PW |
| 学员侧 UI | report.tsx 加批注卡片 | 0.5 PW |
| 涂鸦 Canvas | `components/SketchCanvas.tsx`（新） | 1 PW |
| 录音组件 | `components/VoiceRecorder.tsx`（新） | 0.5 PW |
| 内容安全集成 | service 层 | 0.5 PW |
| 单测 | 多个 | 0.5 PW |

**合计：~6 PW**（与 docs/23 §4.4 持平）

### 3.2 `analysis_annotations` 表 schema v0.1（docs/03 §8.2.4 拟）

```sql
CREATE TABLE analysis_annotations (
    id              VARCHAR(32) PRIMARY KEY,
    coach_user_id   VARCHAR(32) NOT NULL REFERENCES users(id),
    student_user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id     VARCHAR(32) NOT NULL REFERENCES swing_analyses(id) ON DELETE CASCADE,
    relation_id     VARCHAR(32) NOT NULL REFERENCES coach_student_relations(id),
    annotation_type VARCHAR(20) NOT NULL,                 -- voice|text|sketch|video_ref
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    voice_url       VARCHAR(512),
    voice_duration_sec INTEGER,
    sketch_png_url  VARCHAR(512),
    text_content    TEXT,
    audit_status    VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|approved|rejected|manual_review
    audit_reason    TEXT,
    is_visible      BOOLEAN NOT NULL DEFAULT FALSE,        -- 审核通过才 true
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ann_type CHECK (annotation_type IN ('voice','text','sketch','video_ref')),
    CONSTRAINT chk_voice_duration CHECK (voice_duration_sec IS NULL OR voice_duration_sec <= 30),
    CONSTRAINT chk_audit_status CHECK (audit_status IN ('pending','approved','rejected','manual_review'))
);
CREATE INDEX idx_ann_analysis_visible ON analysis_annotations(analysis_id, is_visible);
CREATE INDEX idx_ann_coach ON analysis_annotations(coach_user_id, created_at DESC);
```

### 3.3 4 种批注入口

| Type | UI | 上限 | 审核 |
| --- | --- | --- | --- |
| voice | 录音按钮（≤30s） | DB chk + 客户端 + 接口三层 | 语音转文字 → 关键词 |
| text | 文本框 | 500 字 | 关键词 |
| sketch | Canvas 涂鸦 → PNG | <500KB | 黄反图识别 |
| video_ref | 引用素材库（drill / pro_clip） | — | drill 已审核 / pro_clip M12-01 已审核 |

### 3.4 行级权限校验（FR-8）

学员 A 只能看自己 analysis_id 上的批注；尝试访问别人的 → 40313 / 404。

```python
def get_annotations(user, analysis_id):
    analysis = get_swing_analysis(analysis_id)
    if analysis.user_id != user.id:
        raise ForbiddenError(40313)
    return db.query(AnalysisAnnotation).filter_by(analysis_id=analysis_id, is_visible=True).all()
```

### 3.5 内容安全集成（M8-08 共享）

- 上传后异步调腾讯云内容安全
- 通过 → `audit_status='approved'` + `is_visible=true`
- 拒绝 → 通知教练修改 + 不展示
- 边缘 case → manual_review 队列

### 3.6 错误码

- `40313` 学员未授权 / 不可见（M8-03 已定义）
- `40314` 教练批注音频时长超 30s
- `42910` 教练日批注配额 200（M8-08 节流）

---

## 四、字段 v0.1

### 4.1 API

```
POST /v1/coach/analyses/{analysis_id}/annotations  Body: { type, voice_url?, sketch_png_url?, text? }
GET  /v1/coach/analyses/{analysis_id}/annotations
DELETE /v1/coach/annotations/{annotation_id}
```

### 4.2 配置

```python
PHASE2_COACH_ENABLED: bool = False
COACH_ANNOTATION_DAILY_LIMIT: int = 200
```

---

## 五、验证数据

- 录制 → 上传 → 学员侧播放 ≤3s（AC-1）
- 30s 限制三层校验（AC-2）
- 内容审核命中"黄反"自动隐藏（AC-3）
- 跨学员访问返 40313 / 404（AC-4）

---

## 六、W23-W28 周计划

| 周 | 任务 |
| --- | --- |
| W23 | schema 评审 |
| W24 | model + service + API |
| W25 | SketchCanvas + VoiceRecorder 组件 |
| W26 | 教练 UI + 学员展示 |
| W27 | 内容安全集成 + 行级权限 |
| W28 | 灰度 5 对师生 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | schema + service + 行级权限 |
| 客户端 | 4 种批注 UI + Canvas + 录音 |
| 合规 | 内容安全 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | Canvas 涂鸦 RN 兼容性 | adapters/ 分叉；MVP 期小程序优先 |
| R-02 | 录音权限被拒绝 | Toast 引导；fallback 文字 |
| R-03 | 审核延迟 >3s | fail-safe pending（用户不可见） |
| R-04 | 学员错访其他人批注 | 三层校验：analysis_id 所有权 → relation_id 校验 → audit_status |

### AC

- [ ] AC-1：上传链路 <3s
- [ ] AC-2：30s 三层校验
- [ ] AC-3：内容审核生效
- [ ] AC-4：跨学员 40313/404

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-03 师生关系 | relation_id |
| P2-M8-08 上传审核 | 共用流程 |
| P2-M8-07 教学报告 | 引用 annotations |
| P2-M12-09 教练 M8 引用 | pro_swing_clips id |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；4 入口 + 30s 限制 + 行级权限 |
