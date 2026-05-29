# P2-M7-16 · 用户水平差异化文案（LLM 报告，不动评分）· 启动包（W36 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.16`](../23-二期可编码规格说明书.md#316-p2-m7-16--用户水平差异化文案llm-报告渲染阶段不动评分)
> 前置：P2-M9-04 训练偏好 + P2-M7-10 i18n + P2-M12 球手库

---

## 一、文档目的与边界

为 **P2-M7-16** 落地 W36-W40 LLM + 产品 SOP，按用户水平 3 档（新手/中等/高手）生成差异化报告文案。

### 边界（不做）

- 不改评分本身（M7-04/05 保持客观）
- 不引入对话式 LLM 重写报告（仅渲染阶段）
- 不修改 docs/22/23 字段

---

## 二、现状盘点

```
backend/app/services/llm_report_service.py
  → 单一 prompt，无 user_profile 上下文
  → 文案统一"教练化"风格
```

### 缺口（vs docs/23 §3.16 FR）

4 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Prompt 模板分层 | `services/llm/report_prompts.py` 新增 3 套 | 1 PW |
| user_profile 上下文注入 | `services/llm_report_service.py` 改 | 0.5 PW |
| 文案存 git | `services/llm/prompts/{beginner,intermediate,advanced}.md` | 0.3 PW |
| 单测 / grep | 验证 prompt 含 golf_level / drill 引用 | 0.7 PW |
| LLM 灰度 + 监控 | 1 周 5%→25% | 0.5 PW |

**合计：~3 PW**

### 3.2 3 档策略

| 档 | 触发 | 风格 | 推荐内容 |
| --- | --- | --- | --- |
| beginner | handicap_real ≥36 OR golf_level='beginner' | 鼓励 + 简练 | drill + 半挥练习 |
| intermediate | 18 ≤ handicap_real < 36 | 数据驱动 + 教练化 | drill + tempo 节奏 |
| advanced | handicap_real <18 | 数据 + 类比球手 | M12 pro_clip 对比 |

### 3.3 Prompt 模板示例

```
# advanced.md
你是一位 PGA 认证教练，正在为一位差点 {handicap_real} 的高水平球友撰写报告。
本次分析数据：
- score: {score}
- issues: {issues}
- new_features: {tempo / pressure / kinematic}

请：
1. 用数据说话（引用 ≥2 个新特征数值）
2. 至少类比 1 位职业球手（pro_clip_id={recommended_pro_clip_id}）
3. 给出 1-2 条进阶训练建议（链接 drill_id）
4. 控制在 250 字以内
```

### 3.4 上下文字段

```python
context = {
    'golf_level': user.golf_level,
    'handicap_real': user_profile_v2.handicap_real,
    'golf_age_years': user_profile_v2.golf_age_years,
    'training_preference': user_profile_v2.training_preference,  # video / text
    'preferred_drill_types': user_profile_v2.preferred_drill_types,
}
```

### 3.5 grep 单测

```python
def test_advanced_prompt_includes_pro_clip():
    prompt = build_prompt('advanced', context, analysis)
    assert 'pro_clip_id' in prompt
def test_beginner_no_advanced_vocabulary():
    prompt = build_prompt('beginner', context, analysis)
    assert 'kinematic sequence' not in prompt
```

---

## 四、字段 v0.1

无 API 改动；报告响应内嵌新 LLM 输出。

```python
LLM_PERSONALIZATION_ENABLED: bool = False
```

---

## 五、验证数据

- 同一动作错误，3 档样本 LLM 文案显著不同（人工 review）（AC-1）
- 高手档引用 ≥1 pro_clip（AC-2）
- 新手档无 advanced 术语（AC-3）

---

## 六、W36-W40 周计划

| 周 | 任务 |
| --- | --- |
| W36 | Prompt 模板 |
| W37 | 上下文注入 + 单测 |
| W38 | 内部 review + 产品 / 教研 |
| W39 | 灰度 5% |
| W40 | 灰度 25% + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| LLM Lead | prompt 设计 |
| 产品 | 文案 review |
| 后端 | 上下文 + 灰度 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 用户档位错（新手填 handicap 5） | 兜底 user.golf_level 优先 |
| R-02 | LLM 输出仍千篇一律 | grep 单测 + 多样性温度调节 |
| R-03 | 新手感到被"看轻" | 文案 review 避免"简单"等贬义词 |
| R-04 | M9-04 数据未填 | 默认 intermediate 档 |

### AC

- [ ] AC-1 3 档文案差异
- [ ] AC-2 高手引 pro_clip
- [ ] AC-3 新手无术语

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M9-04 偏好 | preferred_drill_types |
| P2-M7-10 i18n | 共用 prompt 字典 |
| P2-M12 球手库 | pro_clip_id 来源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；3 档差异化 |
