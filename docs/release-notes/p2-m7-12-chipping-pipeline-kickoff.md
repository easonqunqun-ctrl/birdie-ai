# P2-M7-12 · 切杆 mode 独立 pipeline · 启动包（W24 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.12`](../23-二期可编码规格说明书.md#312-p2-m7-12--切杆-mode-独立-pipeline)
> 前置：[`p2-m7-11-putting-pipeline-kickoff.md`](./p2-m7-11-putting-pipeline-kickoff.md)（共享子包模式） + 联动 M10-02

---

## 一、文档目的与边界

为 **P2-M7-12** 落地 W24-W30 算法 + 客户端 SOP，建立 chipping 独立 pipeline，复用 M7-11 的子包模式。

### 边界（不做）

- 不修改 full_swing / putting
- 不实现"低飞/挑高"等高级切杆类型识别（M7-13 之后）

---

## 二、现状盘点

依赖 M7-11 已落 putting 子包模式。本任务复用相同骨架。

### 缺口（vs docs/23 §3.12 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| chipping 子包 | `ai_engine/app/pipeline/chipping/{features,phases,scoring,diagnose}.py` | 2 PW |
| main.py 路由扩 | 短改 | 0.2 PW |
| 切杆诊断规则 | 6-8 条 chipping/rules.yaml | 0.5 PW |
| ECS chipping 子集 | ≥10 段 | 0.8 PW |
| 单测 | tests | 0.5 PW |

**合计：~4 PW**

### 3.2 chipping 特征

| 特征 | 计算 | ideal |
| --- | --- | --- |
| `half_swing_amplitude` | 手位到耳的距离 / 全挥 ratio | 0.3-0.6 |
| `face_open_angle` | 杆面相对挥动方向 angle | 5-15°（轻微开） |
| `contact_point_quality` | 击球瞬间手位 / 球位 / 脚位三角 | 评分 0-100 |

### 3.3 4 阶段

`setup → backswing → impact → follow`（半挥幅度）

### 3.4 6 条诊断规则

| issue | 触发 |
| --- | --- |
| chipping_over_swing | half_swing_amplitude > 0.7 |
| chipping_decel | follow 速度 < backswing 70% |
| chipping_scoop | 击球前手位领先杆头 |
| chipping_chunked | 手位下沉 > 8cm 之前 impact |
| chipping_thin | 杆头平面过高 |
| chipping_alignment_off | 脚位 vs 杆面 > 10° |

---

## 四、字段 v0.1

复用 M7-11 schema 模式；mode='chipping'。

---

## 五、验证数据

- ECS chipping ≥10 段，r ≥0.65（AC-2）
- mode=chipping 链路通（AC-1）

---

## 六、W24-W30 周计划

| 周 | 任务 |
| --- | --- |
| W24 | 子包骨架 + features |
| W25 | phases + scoring |
| W26 | 6 条诊断 |
| W27 | main.py 路由 + 单测 |
| W28 | ECS 标定 + 相关性 |
| W29 | 灰度 5% 与 M10-02 联调 |
| W30 | 灰度 25% + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | chipping 算法 |
| AI 工程 | 路由 |
| 教研 | 切杆标定 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 半挥幅度判别复杂 | 多 ECS 样本调阈值 |
| R-02 | r <0.65 | 不上线；调权重 |
| R-03 | 切杆与推杆混淆 | mode + club_type 双向校验 |

### AC

- [ ] AC-1 mode=chipping 链路通
- [ ] AC-2 r ≥0.65
- [ ] AC-3 客户端能选切杆模式（联动 M10-02）

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-07 阶段 | 共享框架 |
| P2-M7-11 putting | 复用子包模式 |
| P2-M10-02 UI | 联动 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
| v0.1-w24w27 | 2026-05-29 | **W24-W27 落地**：chipping 子包（constants/features/phases/scoring/diagnose/pipeline）+ 3 特征 + 4 阶段 + 6 条诊断 + `main.py` `mode=chipping` 路由 + 50123（wedge 双向校验）+ schema `mode`/`analysis_mode` 扩 chipping + 单测。ideal 占位待 ECS（§2.14，AC-2 r≥0.65）。backend 透传 mode 归 M10-02。 |
