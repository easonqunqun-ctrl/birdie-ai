# P2-M12-07 · 教练 PGC 解说 + LLM 辅助文案 · 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.7`](../23-二期可编码规格说明书.md#87-p2-m12-07--教练-pgc-解说--llm-辅助文案)
> 前置：DEP-02 教练 BD + M8-08 内容审核

---

## 一、文档目的与边界

为 **P2-M12-07** 落地 W30-W36 教练 + LLM + 运营 SOP，让每位球手 clip 至少 3 条专业解说。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不实现解说 paywall（M8-10 种子教练免费）
- 不允许用户 UGC 直接解说（仅教练 + 运营 + LLM）

---

## 二、现状盘点

- M12-01 已建 pro_clip_annotations 表（含 narrator_role）
- M8 工作台已有批注能力
- LLM chat_service 可改造

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| API 教练写 | POST /v1/coach/pros/clips/{clip_id}/annotations | 0.5 PW |
| 教练侧 UI | `pages/coach/pgc-annotations/` | 1 PW |
| LLM 解说生成 | `services/llm/pro_annotation_prompt.py` | 1 PW |
| 学员侧展示 | `pages/pros/clips/[id].tsx` annotations 列表 | 0.5 PW |
| 内容审核 | 复用 M8-08 队列 | 0.2 PW |
| 解说 SOP | 教练运营 | 0.8 PW |

**合计：~4 PW**

### 3.2 LLM 解说 prompt

```
你是高尔夫职业教练，对 {player_name_zh}（{nationality}, 差点 {handicap}）的本次挥杆做解说。
输入：features_snapshot = {features_snapshot}, bio = {bio}
要求：
1. 200 字以内
2. 引用 ≥2 个具体特征数值
3. 关联 1 个用户可学习的训练点
4. 不夸大；中性专业风格
```

教练审稿（编辑或拒绝），通过后 narrator_role 改 coach_pgc（如教练完整重写）或保留 ai_generated。

### 3.3 ≥3 条/球手 保证

| 角色 | 数量目标 |
| --- | --- |
| coach_pgc | ≥1 |
| ai_generated（教练审过） | ≥1 |
| admin（运营） | ≥1 |

### 3.4 审核

走 M8-08 队列；audit_status 字段。

---

## 四、字段 v0.1

```
POST /v1/coach/pros/clips/{clip_id}/annotations
  Body: { narrator_role, text_content, voice_url? }
```

---

## 五、验证数据

- 每球手 ≥3 条解说（AC-1）
- 解说审核走 docs/06（AC-2）
- 学员可看到列表（AC-3）

---

## 六、W30-W36 周计划

| 周 | 任务 |
| --- | --- |
| W30-W31 | API + LLM prompt |
| W32 | 教练 UI |
| W33-W34 | 教练 / 运营写解说 |
| W35 | 学员展示 |
| W36 | 审核 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 教练 | 写解说 |
| LLM | 初稿 |
| 运营 | 队列 + 审核 |
| 后端 | API + 审核 hook |
| 客户端 | 教练 UI + 学员展示 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 教练写稿速度慢 | LLM 初稿 + 编辑模式 |
| R-02 | LLM 解说质量低 | 教练强制审；不通过不展示 |
| R-03 | 内容侵权 | 仅基于 features 描述；不引原视频内容 |
| R-04 | 球手 ≥3 条难达成 | 优先头部 5 位球手 |

### AC

- [ ] AC-1 每球手 ≥3 条
- [ ] AC-2 走审核
- [ ] AC-3 学员可见

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-01 schema | pro_clip_annotations |
| P2-M8-08 审核 | 队列共用 |
| P2-M8-10 教练 | 写 PGC 主力 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
