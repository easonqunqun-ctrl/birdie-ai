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

## 3. 标定本身对 V1 线上评分零影响（接入策略见 §6）

> 注：本节描述的是**改权重表那一步**的影响面。权重表随后已按 §6 接进 scoring，
> 但**仅在 V2 桶生效**，V1 生产路径仍不受影响。

`PHASE_WEIGHTS_DRIVER` 改值这一步：

- 不改变任何 V1 分析报告的分数 → 无评分漂移、不触发 `test_ecs_regression.py` 基线回归；
- 只影响 `category_weight_diff_count`（差异度计数）→ 让 W19 DoD 测试转绿。

接进 scoring 时（§6）通过 `club_aware_scoring` 开关把全部标尺限定在 V2 桶，
**V1 生产路径分数恒不变**。注：B-1（球杆维）阶段「7 铁 V1↔V2 不跳变」的严格不变量，
在 angle 维接入后放宽——见 §6 待办 #3 的灰度安全边界说明。

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

## 6. 接入评分进度

- [x] **W22 把 `phase_weights_for_category` 接进 `scoring.py`，且仅 V2 生效**（本次）：
  `score_overall(phase_scores, *, club_category=None)` 按球杆类别选相位权重。
  - **灰度门**：`run_real_analysis` 新增 `club_aware_scoring: bool = False` 开关，
    **默认 False → club_category=None → 单套 PHASE_WEIGHTS，V1 生产路径字节不变**；
    `run_real_analysis_v2` 调用时传 `club_aware_scoring=True`，用 `to_club_category(req.club_type)`
    派生类别。**球杆相位权重因此只在 V2 桶生效，跟随 `version_router` 的 5%→25%→50% 灰度爬坡**，
    不再像初版那样对全量 V1 用户即时生效（回应「为什么不直接 V2」的决策点，已收口）。
  - 行为变化范围：V2 桶内 **仅 driver / wood / hybrid / wedge** 综合分按各自相位权重重算；
    **iron / putter / 未知 → V1 单套兜底，分数不变**（iron 套 == V1 → 7 铁 V1↔V2 不跳变）。
  - 守门测试：`test_run_real_analysis_club_aware_scoring_default_false`（锁 V1 默认 False）、
    `test_v2_entry_enables_club_aware_scoring`（验 V2 入口打开开关），见 `tests/test_real_pipeline_v2.py`。
- [x] **`ideal_for_category`（M7-05 §4.2 单特征 ideal 标尺）接进 `score_phase`，同 V2-only 灰度门**：
  `score_phase(features, phase, *, club_category=None)` / `score_all_phases(..., club_category=None)`
  提供类别时 per-feature ideal 区间按球杆类别取（`ideal_for_category`），`run_real_analysis`
  在 `club_aware_scoring=True`（仅 V2）时把同一 `club_category` 一并传入。
  - 灰度安全：iron / putter / 未 override 的特征都回落 V1 ideal，**每个阶段分 == V1** →
    7 铁 V1↔V2、接入前后不跳变；仅 driver/wood/hybrid/wedge 在被 override 的特征上变化。
  - 守门测试：`test_score_phase_iron_equals_v1_gray_release_safe`、
    `test_score_phase_driver_uses_category_ideal_band`、`test_score_all_phases_threads_club_category`
    （`tests/test_scoring.py`）。
  - 注：tolerance / weight 仍取 `constants.FEATURES`，本期只标定 ideal 区间维度。
- [x] **angle 维度接进 scoring，与 category 二维合成，同 V2-only 灰度门**：
  新增 `app/pipeline/score_profiles.py`（`resolve_phase_weights` / `resolve_ideal`）把
  M7-04 机位维与 M7-05 球杆维合成单一标尺；`score_phase` / `score_overall` /
  `score_all_phases` 新增 `camera_angle` 参数走它，`run_real_analysis` 在
  `club_aware_scoring=True`（仅 V2）时把 `req.camera_angle` 一并传入。
  - **合成规则（决策记录）**：
    - **相位权重 = 增量叠加**：`V1 + (category套−V1) + (angle套−V1)`，clip≥0 后归一化。
      两维 delta 各自和为 0 → 无 clip 时天然和为 1。`iron+无机位 == V1`；
      `driver+dtl` 两维 delta 复合。**取此方案而非「category 优先盖掉 angle」**：否则
      iron 永远命中 category 套（==V1），angle 权重成死代码；增量叠加让两维都生效。
    - **per-feature ideal = 优先级 category > angle > V1**：球杆类别决定动作真实理想区间，
      机位是测量视角的次要修正；同一特征两维同时 override 时取 category。
  - **灰度安全边界变化（重要）**：真实分析 `camera_angle` 必填，故 **V2 桶内即便 iron，
    综合分也会带机位 delta，不再严格 == V1**（这是 M7-04 机位标尺的本意，且仅 V2 灰度桶生效，
    V1 生产路径 `club_aware_scoring=False` 仍字节不变）。B-1 阶段「iron 7 V1↔V2 不跳变」的
    严格不变量，自 angle 维接入起放宽为「V1 生产不变 + V2 桶按 (机位,球杆) 标尺」。
  - 守门测试：`tests/test_score_profiles.py`（11 例：增量叠加/归一化/优先级/兜底）+
    `tests/test_scoring.py` 新增机位维穿线 3 例。
- [ ] driver 报告分数纳入 V1↔V2 灰度对比，确认无异常跳变（W14-C，等 V2 真实流量 ≥20）。
- [ ] 真实 ECS 争议样本 ≥20 后，用 `scripts/calibration_regression.py` 同源思路二次校准本表。
