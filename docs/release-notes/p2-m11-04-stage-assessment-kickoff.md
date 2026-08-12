# P2-M11-04 · 阶段考核（关卡式 + M7 评分达标自动升阶）· 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §7.4`](../23-二期可编码规格说明书.md#74-p2-m11-04--阶段考核关卡式--m7-评分达标自动升阶)
> 前置：[`p2-m11-03-learning-path-ui-kickoff.md`](./p2-m11-03-learning-path-ui-kickoff.md) + M7-04~07 + M10-01/02

---

## 一、文档目的与边界

为 **P2-M11-04** 落地 W30-W34 后端 + 客户端 SOP，实现"考核 lesson + M7 评分 ≥ 阈值自动升阶"关卡式体验。

### 边界（不做）

- 不实现证书海报（M11-05）
- 不引入 LLM 评分（M7 评分为准）
- 不允许人工绕过（避免课程灌水）

---

## 二、现状盘点

- M11-01 已建 user_course_progress 表（含 pass_analysis_id / passed_at）
- M11-03 已建学习路径 UI（升阶后需主动刷新）
- M7 评分 score 已就位（一期）

### 缺口（vs docs/23 §7.4 FR）

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/course_assessment_service.py` | 1 PW |
| API | POST /v1/lessons/{lesson_id}/attempt | 0.3 PW |
| Hook | swing_analysis 完成回调 → 关联 lesson_attempt | 0.5 PW |
| 通关动画组件 | `components/StagePassedAnimation.tsx`（新） | 0.7 PW |
| 重考 UI | `pages/learning/lesson/[id].tsx` "再考一次" | 0.3 PW |
| 单测 | tests | 0.2 PW |

**合计：~3 PW**

### 3.2 考核 lesson 标记

```jsonc
{
  "lesson_id": "...",
  "lesson_type": "assessment",
  "pass_criteria": {
    "type": "engine_score",
    "engine_mode": "full_swing",
    "phase": "overall",
    "min_score": 80,
    "max_attempts_per_day": 3
  }
}
```

### 3.3 考核提交流程

```
用户提交考核视频 → 一期 /v1/analyses 创建 swing_analysis
  → 客户端额外带 ?lesson_id=...
  → 后端 callback (analysis done) → assessment_service.check_pass(analysis, lesson)
  → 满足 → upsert user_course_progress(status='passed', pass_analysis_id, passed_at)
        → 触发通关推送 + 缓存失效
  → 不满足 → status='attempted' + attempt_count++ + LLM 简短反馈
```

### 3.4 升阶判定

```python
def maybe_upgrade_stage(user_id: str, course_id: str):
    course = get_course(course_id)
    all_lessons = get_lessons_by_course(course_id)
    progress = get_user_progress_by_lessons(user_id, [l.id for l in all_lessons])
    if all(p.status == 'passed' for p in progress):
        # 颁发证书 + 解锁下一阶
        award_certificate(user_id, course_id)
        emit_event('stage_passed', user_id, stage=course.stage)
```

### 3.5 防作弊

- attempt_count 累加；同 lesson 同日 ≥3 次警告 + 当日上限
- mode 必须与 pass_criteria.engine_mode 一致（防"打 putter 通关 full_swing"）

---

## 四、字段 v0.1

```
POST /v1/lessons/{lesson_id}/attempt
  Body: { swing_analysis_id }
  Resp: { passed: bool, score: number, feedback: string, attempts_used: int, max_attempts: int }
```

---

## 五、验证数据

- 考核 lesson + swing_analysis ≥80 → passed（AC-1）
- 通关动画 + 推送（AC-2）
- 未达标可重考；attempts++（AC-3）

---

## 六、W30-W34 周计划

| 周 | 任务 |
| --- | --- |
| W30 | service + API + hook |
| W31 | 通关动画 |
| W32 | 重考 UI + 防作弊 |
| W33 | 单测 + 灰度 |
| W34 | 监控 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | service + 升阶 |
| 客户端 | 动画 + 重考 UI |
| 教研 | 通关阈值制定 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 80 阈值过严，通关率 <30% | 教研按数据调阈；初值 70 |
| R-02 | 用户作弊（用别人视频） | 一期 video metadata 校验；M7-06 confidence 阈值 |
| R-03 | 通关推送疲劳 | 微信订阅消息只在阶段通关推送，lesson 通关只 in-app |
| R-04 | 考核视频上传配额 | 走一期 analysis_quotas；不额外计费 |

### AC

- [ ] AC-1 ≥80 自动升阶
- [ ] AC-2 通关动画
- [ ] AC-3 可重考

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M11-01 schema | pass_analysis_id |
| P2-M11-03 UI | 升阶后刷新 |
| P2-M11-05 证书 | 阶段通关触发 |
| 一期 swing_analyses | 评分源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；考核 + 升阶 |
