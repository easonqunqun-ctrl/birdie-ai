# P2-M7-10 · 诊断规则 V2 引擎（RuleEngine + 规则 15→25-30 + i18n 抽离）· 启动包（W28 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.10`](../23-二期可编码规格说明书.md#310-p2-m7-10--诊断规则-v2-引擎抽象-ruleengine--规则-15--25-30--i18n-抽离)
> 前置：P2-M7-08 + P2-M7-14 灰度

---

## 一、文档目的与边界

为 **P2-M7-10** 落地 W28-W34 算法 SOP，重写诊断规则为可配置 RuleEngine，规则扩到 25-30 条，文案 i18n 抽离。

### 边界（不做）

- 不改一期 15 规则触发条件（仅迁移格式）
- 不引入 LLM 诊断（M7-16 单独）
- 不修改 docs/22/23 字段

---

## 二、现状盘点

```
ai_engine/app/pipeline/diagnose.py
  → 15 条 if-else 硬编码规则
  → 文案与规则代码混合
  → 无 confidence 字段；无 engine_version tag
  → 隐式互斥（先 trigger 的 issue 抑制后面）
```

### 缺口（vs docs/23 §3.10 FR）

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| RuleEngine | `ai_engine/app/pipeline/rule_engine.py`（新） | 1.5 PW |
| 规则配置 | `ai_engine/app/pipeline/rules/*.yaml`（25-30 个文件） | 2 PW |
| i18n 字典 | `ai_engine/app/pipeline/locales/zh_CN.json` | 0.5 PW |
| 互斥矩阵 | `rules/mutual_exclusion.yaml` | 0.3 PW |
| 单测 | `tests/test_rule_engine.py`（覆盖率 ≥90%） | 1 PW |
| 文案教研 / Buffer | — | 0.7 PW |

**合计：~6 PW**（与 docs/23 §3.10 持平）

### 3.2 RuleEngine 设计

```yaml
# rules/early_extension.yaml
name: early_extension
display_name_key: issues.early_extension
severity_func: hip_distance_to_setup_normalized
conditions:
  - feature: hip_distance_to_setup
    operator: ">"
    threshold: 0.15
  - feature: spine_tilt_deg
    operator: "<"
    threshold: 20
mutually_exclusive_with: [reverse_pivot]
confidence_floor: 0.5
engine_version_tag: v2.0
```

### 3.3 严重度动态

```python
def severity(rule, features):
    threshold = rule['conditions'][0]['threshold']
    actual = features[rule['conditions'][0]['feature']]
    ratio = (actual - threshold) / threshold
    return clamp(ratio, 0, 1)  # 0..1
```

### 3.4 i18n 抽离

```python
# 规则只产 issue_type + payload
{'type': 'early_extension', 'severity': 0.78, 'confidence': 0.85, 'payload': {'hip_dist': 0.21}}

# 渲染时（chat/report）
issue_text = i18n.t(f'issues.{issue["type"]}.title', lang='zh_CN', **issue['payload'])
```

### 3.5 新规则清单（≥10 个新 issue type）

| issue_type | 含义 | 触发条件 |
| --- | --- | --- |
| lift_off_back_foot | 后脚抬起 | 后脚 y 偏移 > 10cm |
| casting_late | 释杆过晚 | 杆头加速时间点 > 80% downswing |
| chicken_wing | 鸡翅膀 | 左肘外展 > 30° in follow |
| over_the_top | 越顶 | 杆头 plane 偏内 |
| reverse_spine_angle | 反向脊柱 | 上杆顶点脊柱向目标侧倾 |
| ... | 4-5 个 | — |

---

## 四、字段 v0.1

```jsonc
{
  "detected_issues": [
    {
      "type": "early_extension",
      "severity": 0.78,
      "confidence": 0.85,
      "rule_engine_version": "v2.0",
      "payload": {"hip_dist": 0.21}
    }
  ]
}
```

---

## 五、验证数据

- ECS v2 标杆，新规则触发率 ≥25%（AC-1）
- 文案产品+教研双签（AC-2）
- 改 i18n 不发版引擎（grep / hot reload AC-3）
- 单测覆盖率 ≥90%

---

## 六、W28-W34 周计划

| 周 | 任务 |
| --- | --- |
| W28 | RuleEngine 框架 |
| W29-W30 | 迁移 15 旧规则 → YAML |
| W31-W32 | 新增 10-15 规则 + 互斥矩阵 |
| W33 | i18n 字典 + 文案教研 |
| W34 | 灰度 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | RuleEngine + 规则 |
| 教研 | 文案 + 互斥 |
| 产品 | 文案双签 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 规则误判率上升 | 灰度逐条；每条单测 |
| R-02 | 文案与规则脱节 | i18n grep CI |
| R-03 | 25 条规则配 30 条互斥过复杂 | 矩阵自动校验 |
| R-04 | 规则严重度计算偏差 | severity 单测 ≥10 case/rule |

### AC

- [ ] AC-1 规则 ≥25
- [ ] AC-2 文案双签
- [ ] AC-3 i18n 与代码解耦

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-08 新特征 | 规则消费 |
| P2-M7-14 灰度 | rule_engine_version |
| P2-M7-16 LLM 文案 | i18n 共用 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；RuleEngine + 25-30 规则 |
