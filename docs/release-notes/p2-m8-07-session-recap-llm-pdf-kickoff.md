# P2-M8-07 · 教学报告（多学员 LLM 汇总 + PDF 导出 + 水印）· 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.7`](../23-二期可编码规格说明书.md#47-p2-m8-07--教学报告多学员汇总-llm--pdf-导出--教练账号水印)
> 前置：[`p2-m8-04-annotation-voice-sketch-kickoff.md`](./p2-m8-04-annotation-voice-sketch-kickoff.md)

---

## 一、文档目的与边界

为 **P2-M8-07** 落地 W30-W35 后端 + LLM + 客户端 SOP，让教练一节课多学员一键 LLM 汇总 + 导出 PDF。

### 边界（不做）

- 不修改 docs/22/23/03/02 字段
- 不实现学员侧推送 PDF（家长群手动转发）
- 不做 PDF 编辑器（仅 LLM + 手工 note）

---

## 二、现状盘点

- 一期已有 LLM（DeepSeek 默认）+ chat_service.py
- 一期无 PDF 生成；无对象存储签名 URL 工具
- M8-04 提供 annotations；M8-06 提供 students dashboard

### 缺口（vs docs/23 §4.7 FR）

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ORM model | `models/coach.py` 追加 CourseSessionRecap | 0.5 PW |
| Service | `services/coach_recap_service.py` | 1.5 PW |
| LLM prompt | `services/llm/coach_recap_prompt.py` | 1 PW |
| PDF 生成 | `services/pdf/recap_pdf.py`（用 weasyprint） | 1.5 PW |
| API | POST /v1/coach/sessions/recap + /export-pdf | 0.5 PW |
| 教练侧 UI | `pages/coach/session-recap/` | 1 PW |
| Migration | 共用 0020 | — |
| 单测 | — | 0.5 PW |

**合计：~6.5 PW**

### 3.2 `course_session_recaps` schema v0.1（docs/03 §8.2.6 拟）

```sql
CREATE TABLE course_session_recaps (
    id                VARCHAR(32) PRIMARY KEY,
    coach_user_id     VARCHAR(32) NOT NULL REFERENCES users(id),
    session_date      DATE NOT NULL,
    student_ids       JSONB NOT NULL DEFAULT '[]',     -- ["uid1","uid2"]
    analysis_ids      JSONB NOT NULL DEFAULT '[]',     -- ["aid1","aid2"]
    ai_summary        TEXT,
    ai_summary_model  VARCHAR(32),                     -- deepseek-v3
    coach_manual_notes TEXT,
    pdf_url           VARCHAR(512),
    pdf_url_expires_at TIMESTAMPTZ,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft|finalized|exported
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_recap_status CHECK (status IN ('draft','finalized','exported'))
);
CREATE INDEX idx_recap_coach_date ON course_session_recaps(coach_user_id, session_date DESC);
```

### 3.3 LLM 汇总 prompt 关键约束

```
[硬约束] 必须为每位学员单独写 2-3 句具体观察（含 issue 名 + 数据），禁止"整体表现不错"类空话。
[输入] 学员 A 的分析 {analysis_A}：issues=[early_extension(score:62), reverse_pivot(score:71)]
       学员 B 的分析 {analysis_B}：...
[输出格式]
  ## 课程概述
  ## 学员 A 的本次表现 + 改进建议
  ## 学员 B 的本次表现 + 改进建议
  ...
  ## 下次课程建议
```

输出时间 ≤15s（NFR）。

### 3.4 PDF 水印

- 教练 display_name + coach_id 后 6 位 + "灵鸟golf · {生成时间}"
- 半透明 30% + 45° 重复布局，覆盖正文
- 防 PDF 被去水印传播（基础防护）

### 3.5 签名 URL TTL

- COS 签名 URL TTL 24h
- 过期 GET → 403；客户端引导教练重新导出
- DB `pdf_url_expires_at` 记录，UI 灰显过期 PDF

---

## 四、字段 v0.1

### 4.1 API

```
POST /v1/coach/sessions/recap
  Body: { session_date, student_ids, analysis_ids, coach_manual_notes? }
  Resp: { recap_id, ai_summary, status }
POST /v1/coach/sessions/{recap_id}/export-pdf
  Resp: { pdf_url, pdf_url_expires_at }
GET  /v1/coach/sessions/recaps?page=&size=
```

---

## 五、验证数据

- 4 学员模拟数据：LLM 输出引用每人 issue（AC-2）
- PDF 含水印 + 24h 过期 403（AC-1/3）
- LLM 链路 ≤15s P95；PDF ≤10s

---

## 六、W30-W35 周计划

| 周 | 任务 |
| --- | --- |
| W30 | schema + service + LLM prompt |
| W31 | weasyprint PDF + 水印 |
| W32 | API + 教练 UI |
| W33 | LLM 输出 grep 校验（学员名 + issue 名必出现） |
| W34 | 灰度 5 教练 + AC 验收 |
| W35 | 灰度 20 教练 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | schema + service + PDF |
| LLM | prompt 设计 + grep |
| 客户端 | 选学员 + 编辑 UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | LLM 写空话 | grep 学员名 + issue 名 ≥1 次/人；不通过则 fallback "教练手工编写"模板 |
| R-02 | PDF 中文字体问题 | weasyprint 配 Noto Sans CJK |
| R-03 | LLM 超时 | 15s 超时 → fallback 模板填空 |
| R-04 | PDF 被传播 | 水印 + 24h TTL；不存敏感原视频 |

### AC

- [ ] AC-1 PDF 带水印
- [ ] AC-2 LLM 引用每人具体 issue
- [ ] AC-3 24h 过期 403

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-04 批注 | 引用 annotations |
| P2-M8-06 学员看板 | 选学员入口 |
| P2-M7-16 LLM 文案 | 复用 personalization 模板 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
