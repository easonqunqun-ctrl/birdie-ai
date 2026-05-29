# P2-M7-11 · 推杆 mode 独立 pipeline · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.11`](../23-二期可编码规格说明书.md#311-p2-m7-11--推杆-mode-独立-pipeline)
> 前置：P2-M7-07 阶段 V2 + P2-M7-14 灰度 + 联动 P2-M10-01 UI

---

## 一、文档目的与边界

为 **P2-M7-11** 落地 W22-W28 算法 + 客户端 SOP，建立 putting 独立 pipeline（与 full_swing 共享视频读取 + pose，特征 / 评分 / 诊断独立）。

### 边界（不做）

- 不修改一期 full_swing pipeline
- 不实现切杆（M7-12）
- 不重建 pose 模型；复用 MediaPipe

---

## 二、现状盘点

```
ai_engine/app/main.py
  → 一期单 mode：full_swing（隐式 default）
ai_engine/app/pipeline/
  → features.py / phases.py / scoring.py / diagnose.py 全为 full_swing
```

### 缺口（vs docs/23 §3.11 FR）

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| putting 子包 | `ai_engine/app/pipeline/putting/{__init__,features,phases,scoring,diagnose}.py` | 3 PW |
| main.py 路由 | `ai_engine/app/main.py` 改 | 0.5 PW |
| 推杆诊断规则 | 8-10 条放 putting/rules.yaml | 0.7 PW |
| ECS putting 子集 | 标定 ≥10 段 | 1 PW |
| 错误码 50123 | `ai_engine/app/errors.py` | 0.2 PW |
| 单测 | tests | 0.6 PW |

**合计：~6 PW**（与 docs/23 §3.11 持平）

### 3.2 putting 专属特征

| 特征 | 计算 | ideal |
| --- | --- | --- |
| `pendulum_stability` | 双肩 y 坐标方差 (整个挥动) | < 5px |
| `head_stability` | 鼻关键点位移方差 | < 100px² |
| `face_alignment` | 推杆面（杆身/手腕）与挥动方向 angle | < 5° |
| `tempo_ratio` | back/forward stroke 时长比 | 2.0-2.5 |

### 3.3 4 阶段

`setup → backstroke → impact → follow`

边界条件：
- backstroke 起点：手腕速度第一次 >5px/frame
- impact：手腕速度峰值
- follow：速度衰减 <2px/frame

### 3.4 评分权重

```python
PUTTING_PHASE_WEIGHTS = {'setup': 0.15, 'backstroke': 0.25, 'impact': 0.35, 'follow': 0.25}
PUTTING_FEATURE_WEIGHTS = {
    'pendulum_stability': 0.30,
    'head_stability': 0.30,   # 钟摆+头部 占 60%
    'face_alignment': 0.25,
    'tempo_ratio': 0.15,
}
```

### 3.5 8 条推杆诊断规则（draft）

| issue | 触发 |
| --- | --- |
| putting_head_moved | head_stability > 200 |
| putting_face_open | face_alignment > 10° at impact |
| putting_decel_stroke | follow 速度 < backstroke 80% |
| putting_wrist_hinge | 手腕角度变化 > 8° |
| putting_short_backstroke | backstroke 长度 < 期望 50% |
| putting_aim_off | setup 杆面与目标方向 > 5° |
| putting_rushed_tempo | tempo_ratio < 1.5 |
| putting_lift_putter | 推杆头 y 抬高 > 阈值 |

### 3.6 错误码 50123

mode='putting' + club_type='driver' / 'iron_X' → `EngineError(code=50123, msg='推杆模式建议选 putter')`

---

## 四、字段 v0.1

```
POST /v1/analyses Body: { mode: 'putting' }
Response: { analysis_mode: 'putting', putting_features: {...}, putting_score: 78, putting_issues: [...] }
```

---

## 五、验证数据

- ECS putting ≥10 段，r ≥0.7 与教练人评（AC-3）
- 全链路打通 mode=putting → 报告（AC-1）
- 50123 触发 + 友好提示（AC-2）

---

## 六、W22-W28 周计划

| 周 | 任务 |
| --- | --- |
| W22 | 子包骨架 + features |
| W23 | phases + scoring |
| W24 | 8 条诊断 |
| W25 | main.py 路由 + 错误码 |
| W26 | ECS 10 段标定 + 相关性 |
| W27 | 灰度 5% + 与 M10-01 联调 |
| W28 | 灰度 25% + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | putting 算法 |
| AI 工程 | 路由 + 错误码 |
| 教研 | 推杆教练标定 |
| 客户端 | 联动 M10-01 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | ECS putting 样本不足 | 灰度延迟；先发 5 段 baseline |
| R-02 | pose 在推杆动作上 visibility 低 | 加 face_on only 提示 |
| R-03 | 推杆评分与教练判断偏差大 | r<0.7 不上线；调权重 |
| R-04 | 50123 误判 | club_type='putter' 强制 mode='putting'（默认） |

### AC

- [ ] AC-1 mode=putting 链路通
- [ ] AC-2 50123 错配
- [ ] AC-3 r ≥0.7

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-07 阶段 | 共享 phase 框架 |
| P2-M7-14 灰度 | engine_version=v2.0 |
| P2-M10-01 UI | 联动 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
