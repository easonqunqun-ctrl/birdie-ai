# W22 · driver 相位权重标定

> **位置**：`docs/release-notes/w22-driver-phase-weights-calibration.md`
> **代码**：`ai_engine/app/pipeline/club_profiles.py::PHASE_WEIGHTS_DRIVER`
> **测试**：`ai_engine/tests/test_club_profiles.py::test_driver_vs_iron_differs_in_at_least_3_phases`

---

## 1. 背景

P2-M7-05 落了 5 套 `PHASE_WEIGHTS_BY_CATEGORY`，但 driver 那套是 **v0.1 编码初值**，
与 iron 基线只有 `downswing` 一个相位差异 ≥0.03，达不到 W19 DoD「driver vs iron 至少
3 个相位差异 ≥0.03」。该 DoD 测试此前以 `xfail(strict)` 挂起，等本次标定。

## 2. 这次「标定」是什么 / 不是什么

- **是**：基于高尔夫领域知识，把 driver 的相位权重调到与 iron 有产品意义上的区分度，
  满足 W19 DoD，并与 wood/hybrid/iron 构成单调梯度。
- **不是**：真实 ECS 数据驱动的标定。数据驱动标定需要争议样本累计 ≥20（ENG-04 触发条，
  见 `wait-for-triggers-checklist.md` §2.7），目前未满足。本次为**领域知识初值**，
  真实数据到位后二次校准回填。

## 3. 关键事实：当前对线上评分零影响

`phase_weights_for_category` / `PHASE_WEIGHTS_DRIVER` **目前只在 `club_profiles.py`
内部被引用，尚未接入 scoring / diagnose 链路**（kickoff 计划的「(angle, category) 二维
组合由 scoring.py 接入」属后续步骤）。因此本次改权重：

- 不改变任何实际分析报告的分数 → 无评分漂移、不触发 `test_ecs_regression.py` 基线回归；
- 只影响 `category_weight_diff_count`（差异度计数）→ 让 W19 DoD 测试转绿。

接入评分链路时，需把 driver 报告分数纳入灰度对比（参考 kickoff R-02：7 铁 V1↔V2 不跳变
的同类约定），届时再评估 driver 用户分数变化是否符合预期。

## 4. 权重对照

iron 基线（= V1 单套 `PHASE_WEIGHTS`）：`setup .15 / backswing .20 / top .15 / downswing .25 / impact .15 / follow_through .10`

| 相位 | iron | driver（W22） | 差 | 取向依据 |
|---|---|---|---|---|
| setup | 0.15 | **0.11** | −0.04 | 球架高、站位容错大，setup 精度权重相对低 |
| backswing | 0.20 | **0.23** | +0.03 | 宽上杆 / takeaway 路径是开球木力量来源 |
| top | 0.15 | 0.15 | 0 | 顶点满肩转与铁杆同档 |
| downswing | 0.25 | **0.29** | +0.04 | 下杆速度 / 顺序是开球木距离核心（≥0.25 兼容现有测试） |
| impact | 0.15 | **0.12** | −0.03 | 球架高、上升击球，触球点精度权重相对低 |
| follow_through | 0.10 | 0.10 | 0 | 与基线一致 |

- 和 = 1.00（模块加载断言守门）。
- 差异 ≥0.03 的相位：setup / backswing / downswing / impact → **4 个**（DoD 要求 ≥3）。
- driver vs wedge 仍 ≥3 相位差异（setup/backswing/downswing/impact），未回退。
- 梯度（越激进越偏 downswing、越省 setup）：`driver > wood > hybrid > iron`，单调成立。

## 5. 验收

- `test_driver_vs_iron_differs_in_at_least_3_phases` 撤销 xfail 后转绿。
- `make ai-engine-test` 全套绿。

## 6. 待办（接入评分时）

- [ ] W22 把 `phase_weights_for_category` 接进 scoring.py（(angle, category) 二维组合）。
- [ ] driver 报告分数纳入 V1↔V2 灰度对比，确认无异常跳变。
- [ ] 真实 ECS 争议样本 ≥20 后，用 `scripts/calibration_regression.py` 同源思路二次校准本表。
