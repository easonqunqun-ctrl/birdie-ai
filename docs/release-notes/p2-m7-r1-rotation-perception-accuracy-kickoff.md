# P2-M7-R1 · 全挥杆 2D 感知准确度 · 研发准备清单

> **版本**：v0.1 · 2026-05-30  
> **PLAN-ID**：**P2-M7-R1**（工程子项 **ENG-Pose-01** / **ENG-Pose-02**）  
> **上游真源**：[`docs/20` §三 Trust/Calibration](../20-AI引擎产品力迭代设计.md) · [`docs/21` §4](../21-二期产品需求规划.md) · [`docs/23` §3.14](../23-二期可编码规格说明书.md#314-p2-m7-r1--全挥杆-2d-感知准确度)  
> **背景**：V2 Trust 层已落地，但 **V1 pose → features 仍是一期「两帧肩线角」模型**；线上典型误报：
> - **高估**：DTL/转播 X-Factor **155°** + `flat_shoulder` 严重  
> - **低估**：face-on 明显转肩 **3°** + `under_rotation` 严重  
> - **矛盾**：同报告 `under_rotation` + `steep_shoulder` 或 `flat_shoulder` + `over_rotation`

---

## 一、文档目的与边界

### 1.1 目的

为算法 / 后端 / 客户端 / 教研提供 **可排期、可验收** 的产品技术清单，在 **坚持单目 2D、手机拍摄** 前提下：

1. **抬 V1 测量准确度**（多帧轨迹 + 降噪 + 多估计器融合）  
2. **止血荒谬诊断**（sanity + 机位门控 + 矛盾 issue 合并）  
3. **产品契约清晰**（分机位能力表 + 拍摄引导 + 报告话术）

### 1.2 边界（本 PLAN 不做）

| 不做 | 说明 |
|------|------|
| 3D mocap / 多目硬件 | 不阻塞 MVP 2D 路线 |
| 替换整条 V2 规则引擎 | 诊断仍走 YAML；改 **输入特征** 与 **门控** |
| 推杆/切杆 pipeline 重写 | 仅 full_swing；短杆另线 M7-11/12 |
| ECS 满编标定 | 依赖 ENG-04 Trigger；本 PLAN 先 **规则 + 回归集** |

### 1.3 与 V1 / V2 关系

```text
V1/V2 共用：preprocess → pose → [本 PLAN 新增 refine + rotation_track] → features
V1 独有：diagnose.py 硬编码规则（须同步门控）
V2 独有：diagnose_v2 + _enrich_v2（须接 rotation_confidence + 全路径 sanity）
```

**原则**：Phase A（止血）必须 **V1/V2 全流量**，不能仅绑 V2 灰度桶。

---

## 二、根因分析（代码锚点）

### 2.1 当前旋转特征定义

| 特征 | 实现 | 文件 |
|------|------|------|
| `shoulder_rotation_top` | setup **单帧** vs top **单帧** 肩线 2D 角差 | `features.py::feat_shoulder_rotation_top` |
| `hip_rotation_top` | 同上，髋线 | `features.py::feat_hip_rotation_top` |
| `x_factor` | `max(0, shoulder - hip)` | `features.py::feat_x_factor` |

### 2.2 top 帧定义

- `phases.py`：`top_frame = argmin(wrist_y)` 于挥杆窗内  
- **不等于** 肩转最大时刻 → face-on 易 **低估**（3°）  
- DTL 下肩线 2D 角 **不可代表 3D 转体** → 易 **高估**（155°）

### 2.3 已有护城河（未全覆盖）

| 模块 | 能力 | 缺口 |
|------|------|------|
| `feature_measurability.py` | DTL 下旋转可测性 0.08–0.12 | 仅 `club_aware_scoring=True` + 声明 `camera_angle` 时生效 |
| `sanitize_features` | DTL 肩>100° 删 x_factor 等 | V1 路径 `camera_angle=None` 不跑 |
| `diagnose_v2` | 可测性 <0.5 跳过规则 | 依赖 `camera_angle` 参数；未用 **auto-detect** |
| `pose_denoise.py` | 5 帧 visibility 平滑 | 无骨长约束 / 无角度序列滤波 |

### 2.4 典型失败模式

| ID | 表象 | 根因 | 机位 |
|----|------|------|------|
| **F-High** | X-Factor 155°、`flat_shoulder` | 2D 肩髋角投影放大 | DTL / 转播 |
| **F-Low** | 肩转 3°、`under_rotation` | top 过早 / 肩点遮挡 / 两帧比 | face-on |
| **F-Contra** | under + steep 或 flat + over | 同一错误旋转读数分叉触发 | 任意 |
| **F-Null** | 未声明机位 | sanitize/measurability 未启用 | 用户未选 |

---

## 三、目标架构（2D 栈）

```text
L5 产品契约     拍摄引导 · 机位选择 · 能力声明 · issue 文案（不展示 absurd 度数）
L4 诊断/评分    YAML/规则 · 仅对 L3 可信特征 · 矛盾合并 · hidden tier
L3 特征工程     rotation_track 融合 · 15 维 A/B/C 档 · sanity 双尾
L2 时序 refine  pose_refine：骨长 · OneEuro · setup 多帧 baseline · top 窗口
L1 感知         MediaPipe（Phase C 可选 RTMPose/GolfPose A/B）
L0 输入         preprocess · 多挥 · 质量门（已有；Phase B 接 preprocess_v2）
```

---

## 四、15 维特征 · A/B/C 产品分档

| 档位 | 策略 | 特征（full_swing） |
|------|------|-------------------|
| **A** | 主报告叙事；face-on + DTL 分机位子集 | `downswing_sequence`, `wrist_release_*`, `tempo_ratio`, `top_wrist_position`, `head_lateral_shift`, `spine_angle_impact_delta`（分机位） |
| **B** | **仅 face_on** 承诺；DTL 不计分不诊断 | `shoulder_rotation_top`, `hip_rotation_top`, `x_factor`, `left_arm_straightness`（setup/spine 部分） |
| **C** | 内部 debug / engine_warnings；**不进用户 issue 文案** | 未通过 fusion 或 sanity 的 raw 旋转读数 |

**产品文案原则**：B/C 档失败时展示「当前机位/画面下无法可靠测量转肩」，**禁止**展示「3°」「155°」类精确度数（除非通过 sanity 且在 [15°, 110°] 内）。

---

## 五、分期交付 · 产品技术清单

### Phase A · 信任止血（4–6 周 · **Now** · 不依赖标注）

**目标**：杜绝 F-High / F-Low / F-Contra 伤害信任；**V1+V2 全路径**。

| ID | 类型 | 交付项 | 技术细节 | 文件（预期） |
|----|------|--------|----------|--------------|
| **A1** | 引擎 | **旋转 sanity 双尾** | `shoulder_rotation_top` ∉ [15,110] 或 `x_factor` ∉ [0,80] → 从 features 剔除，追加 `WARN_ROTATION_SANITY` | `feature_measurability.py` |
| **A2** | 引擎 | **sanitized 诊断输入** | `diagnose` / `diagnose_v2` 前统一跑 `sanitize_features`；**effective_camera_angle** = 声明机位 ?? auto-detect | `real_pipeline.py`, `camera_angle.py` |
| **A3** | 引擎 | **矛盾 issue 合并** | 同报告 `under_rotation`+`steep_shoulder` 或 `flat_shoulder`+`over_rotation` → 替换为 `rotation_reading_unreliable`（新 warning / 可选 hidden issue） | `diagnose.py`, `v2_starter.yaml`, `locales` |
| **A4** | 引擎 | **setup 多帧 baseline** | setup 窗内（≥3 有效帧）肩/髋线角 **median** 作 baseline，非单 key_frame | `features.py` 或 `rotation_track.py` |
| **A5** | 引擎 | **top 窗口聚合（快赢）** | backswing 窗内 `max(Δshoulder)` 与 top±5 帧 **median** 取 **max**；不改 `phases.top_frame` | `rotation_track.py` |
| **A6** | 产品 | **issue 文案契约** | locale：sanity 失败时不渲染 `{shoulder_rotation_top:.0f}°`；改固定句 | `locales/zh_CN.json`, 教研签 |
| **A7** | 客户端 | **拍摄引导 v1** | 分析前：测转肩请 **正面全身**；侧面说明「转肩类指标自动跳过」 | `pages/analysis/*`, `docs/20` §4.3 |
| **A8** | 客户端 | **能力声明条** | 报告页 TrustBadge 下：本机位已测 / 已跳过维度列表 | `report.tsx` |
| **A9** | QA | **回归包 R2 门禁** | Nelly/Rose 类 DTL + 室内 face-on 3° 用例进 CI | `tests/test_rotation_regression.py` |

**Phase A 验收（AC-A）**

- [x] AC-A2：合成 `shoulder=3` + `top_wrist>0.12` → **不**触发 `under_rotation`（`test_rotation_regression`）
- [x] AC-A3：合成 `x_factor=155` → **不**进入 issue 文案（sanitize + `test_rotation_issue_copy`）
- [x] AC-A5：矛盾对合并 + `rotation_reading_unreliable` warning（`test_diagnose` / `test_rotation_regression`）
- [x] AC-A1：R2 真视频 manifest — 本地 `test_rotation_regression_real.py` 2 passed（2026-05-31）
- [x] AC-A4：V1 桶 sanitize/计分分离（`test_rotation_regression_v1_path`）；真机 E2E ⏳ smoke

**工程量**：~2.5 PW（AI 1.5 + 客户端 0.5 + 教研 0.5）

---

### Phase B · 2D 测量升级（8–12 周 · 部分依赖 M7-09）

**目标**：合规 face-on 自拍下，A/B 档特征 **重复性 CV<15%**；与教练直觉 **方向一致率↑**。

| ID | 类型 | 交付项 | 技术细节 | 文件（预期） |
|----|------|--------|----------|--------------|
| **B1** | 引擎 | **`pose_refine` 模块** | 骨长约束（肩宽/髋宽帧间变异 >25% 降权）；One Euro 滤波肩/髋/腕 x,y；visibility<0.5 帧标记 invalid | `pipeline/pose_refine.py` |
| **B2** | 引擎 | **`rotation_track` 三估计器** | 见 §六 | `pipeline/rotation_track.py` |
| **B3** | 引擎 | **融合 + confidence** | `weighted_median(A,B)`；输出 `rotation_confidence`；写 `feature_confidences` / quality_warnings | `rotation_track.py`, `real_pipeline.py` |
| **B4** | 引擎 | **几何下界 C（交叉验证）** | `top_wrist_position` + 臂几何 → `min_plausible_shoulder_rot`；A<20 且 C>35 → 否决 A | `rotation_track.py` |
| **B5** | 引擎 | **top 双证据（可选）** | `top_wrist` vs `argmax(shoulder_rot(t))` 相差 >8 帧 → 用 backswing max，降 confidence | `phases.py` 或 `rotation_track.py` |
| **B6** | 引擎 | **M7-09 杆头 2D** | 杆头点 → refine top/impact/release 窗 | 见 M7-09 kickoff；**依赖标注** |
| **B7** | 引擎 | **preprocess_v2 灰度** | 60fps / slowmo nominal；全链路 timing 回归后切主链 | `preprocess_v2.py`, flag | ✅ router + AC-B7 timing gate |
| **B8** | 引擎 | **pose 模型 A/B（可选）** | MediaPipe vs RTMPose-m；Golf 小集 fine-tune 评估 | 独立 spike |

**Phase B 验收（AC-B）**

- [ ] AC-B1：R1 包 20 段 face-on 业余，`shoulder_rotation_top` 帧间 CV < 15%（同一人连拍 3 次）  
  - **infra ✅**：`R1_face_on_repeatability` manifest + `test_rotation_repeatability.py`（fixture 齐后自动门禁）  
- [ ] AC-B2：明显转肩 face-on 样本 `shoulder_rotation_top` ≥ 45° 或标记 `rotation_unreliable`（不得 3° 严重）  
  - **真视频 ✅**：`test_rotation_regression_real` 接 helper 断言 ≥45° 或 unreliable warning  
- [ ] AC-B3：`rotation_confidence` 与估计器分歧度相关（单测 + 5 例人工）  
- [ ] AC-B4：B6 就绪后，impact/release 特征窗口误差 < 3 帧（相对人工标定子集）  

**工程量**：~4 PW（不含 M7-09 标注）；B6 +2~3 PW

**推荐顺序**：B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8

---

### Phase C · 标定与持续进化（Trigger 并行）

| ID | 依赖 | 交付 |
|----|------|------|
| **C1** | ECS ≥50 | 阈值/权重数据驱动；发版 `calibration_regression.py` 门禁 |
| **C2** | 500+ 段标注 | GolfPose 类 fine-tune |
| **C3** | ENG-06 | 争议样本周更；F-High/F-Low 入 P0 |
| **C4** | M7-15 | in-app「这条不准」→ 样本池 |

---

## 六、Rotation Track · 技术规格（Phase B 核心）

### 6.1 输入 / 输出

```python
@dataclass(frozen=True)
class RotationTrackResult:
    shoulder_rotation_top: float | None  # None = 不可信，不参与诊断
    hip_rotation_top: float | None
    x_factor: float | None
    rotation_confidence: float  # 0–1
    estimator_a: float | None   # 肩线角轨迹 max
    estimator_b: float | None   # 胸廓/肩距 proxy
    estimator_c_min: float | None  # 几何下界
    quality_warnings: list[str]   # rotation_unreliable, estimator_disagreement, ...
```

### 6.2 估计器 A · 肩线角轨迹（升级现有）

```text
baseline_sh = median(shoulder_line_angle(t) for t in setup_window if vis_ok)
for t in backswing_window:
    delta_a(t) = abs(angle_sh(t) - baseline_sh)  # 归一 [-180,180]
shoulder_A = max(delta_a)   # 或 top±5 median
```

### 6.3 估计器 B · Face-on 胸廓 proxy（新增）

```text
mid_sh(t) = (L_sh + R_sh) / 2
mid_hip(t) = (L_hip + R_hip) / 2
torso_angle(t) = atan2(mid_sh - mid_hip)  # 2D
shoulder_B = max(abs(torso_angle(t) - torso_angle_setup))  # 度

# 备选：normalized trail-shoulder x 位移 / shoulder_width_setup
```

**DTL**：B 权重 ↓；以 A 为主但 A 仍受 measurability 门控。

### 6.4 估计器 C · 几何下界（交叉验证）

```text
若 top_wrist_position > WRIST_HIGH_THRESHOLD (e.g. 0.12)
   且 lead_arm_angle 显示已大幅抬起
→ min_plausible = f(wrist_height, arm_angle)  # 查表或线性，v0.1 保守 35°
```

### 6.5 融合伪代码

```python
def fuse_rotation(a, b, c_min, vis, camera_angle) -> RotationTrackResult:
    if vis_shoulder_mean < 0.5:
        return unreliable("low_visibility")
    if camera_angle == "down_the_line":
        return RotationTrackResult(None, None, None, 0.0, ...)  # 旋转类不测
    if a is not None and a < 20 and c_min is not None and c_min > 35:
        a = None  # 否决低估
    if a is not None and a > 110 and b is not None and b < 50:
        a = None  # 否决高估
    if a is not None and b is not None and abs(a - b) > 25:
        conf *= 0.6
        shoulder = weighted_median([a, b], weights=[w_a, w_b])
    else:
        shoulder = weighted_median([x for x in (a, b) if x is not None])
    if shoulder is not None and not (15 <= shoulder <= 110):
        return unreliable("sanity_tail")
    ...
```

### 6.6 接入点

```text
real_pipeline.run_real_analysis:
  pose → denoise_pose_result → pose_refine_pose_result   # B1
  phases = segment_phases(...)
  rot = compute_rotation_track(pose, phases, camera_angle=effective_angle)  # B2–B4
  features = extract_features(...)  # 非旋转维
  features.update(rot.as_feature_dict())  # 覆盖 shoulder/hip/x_factor
  sanitize_features(features, camera_angle=effective_angle)  # A1
```

---

## 七、诊断门控 · 规则表（Phase A 落地）

| 规则 | 条件 | 动作 |
|------|------|------|
| D1 | `effective_angle == down_the_line` | 跳过所有依赖 `shoulder/hip/x_factor` 的 issue |
| D2 | `shoulder_rotation_top is None` | 跳过 under/over/flat/steep |
| D3 | `under_rotation` 且 `shoulder < 20` 且 `top_wrist > 0.12` | 不触发 |
| D4 | 同报告 under+steep 或 flat+over | 合并 → `rotation_reading_unreliable` |
| D5 | `rotation_confidence < 0.5` | V2：`confidence_tier=hidden`；V1：不返回该 issue |

**新 locale 键（A6）**

```json
"issues.rotation_unreliable.title": "转肩数据本次无法可靠测量",
"issues.rotation_unreliable.summary": "画面机位或遮挡导致 AI 无法稳定读取转肩角度，已跳过相关诊断。建议在正面全身、光线充足下重拍。"
```

---

## 八、产品清单（教研 + 客户端）

| # | 项 | 负责人 | Phase |
|---|-----|--------|-------|
| P1 | 报告页「本报告测量范围」：A 档 ✓ / B 档仅 face-on / 已跳过列表 | 产品+客户端 | A |
| P2 | 拍摄页机位图示：face-on vs DTL 能力差异 | 产品+UI | A |
| P3 | issue 卡片：禁止 absurd 度数；sanity 失败用 P1 模板 | 教研 | A |
| P4 | Pro clip / 教练示范模式：默认不出 amateur 式 rotation issue | 产品 | A |
| P5 | 帮助页 [`score-guide`](../client/src/pages/help/score-guide) 增补「2D 转肩限制」 | 教研 | A |
| P6 | ENG-03 客服话术：用户质疑「3°/155°」标准回复 | 运营 | A |

**对用户一句话（P0 文案）**

> 小鸟 AI 重点分析下杆顺序、节奏与释放；**转肩分离需在正面全身拍摄下才可靠**，侧面或转播画面会自动跳过易误报项目。

---

## 九、测试 · 回归包

### 9.1 R1 · 用户自拍（face-on 业余）

- ≥20 段；同一人连拍 3 次 CV 测 shoulder_rotation  
- 通过：无 F-Low 严重；CV < 15%（Phase B）

### 9.2 R2 · 转播 / Pro（DTL）

- Nelly live fixture（`test_nelly_dtl_scoring.py`）  
- Rose / LPGA 侧面片（待补 manifest JSON）  
- 通过：**零** rotation issue；overall 有 `angle_limited_scoring` 或等价 warning

### 9.3 R3 · 合成 / 单元

| 用例 | 期望 |
|------|------|
| setup≈top 肩线 | `rotation_unreliable`，非 3° under |
| shoulder=160, hip=5 | sanity 剔除，非 flat 155° 文案 |
| under+steep 同集 | 仅 `rotation_unreliable` |
| face-on 合成 rot=70 | under/over 均不触发 |

### 9.4 CI 门禁

- `make ai-engine-test-rotation`（M7-R1 快测子集）  
- `.github/workflows/ai-engine-pytest.yml` 全量 pytest 含 `test_rotation_*.py`  
- ECS MR：`calibration_regression.py` 增 rotation issue 计数漂移阈值（Phase C）

---

## 十、文件变更清单（研发准备）

| 操作 | 路径 |
|------|------|
| **新增** | `ai_engine/app/pipeline/rotation_track.py` |
| **新增** | `ai_engine/app/pipeline/pose_refine.py` |
| **新增** | `ai_engine/tests/test_rotation_track.py` |
| **新增** | `ai_engine/tests/test_rotation_regression.py` |
| **新增** | `ai_engine/tests/fixtures/rotation_regression_manifest.json` |
| **修改** | `ai_engine/app/pipeline/features.py`（旋转维改调 rotation_track 或 deprecate 单帧） |
| **修改** | `ai_engine/app/pipeline/feature_measurability.py`（A1 sanity、WARN 常量） |
| **修改** | `ai_engine/app/pipeline/real_pipeline.py`（effective_camera_angle、接入链） |
| **修改** | `ai_engine/app/pipeline/diagnose.py`（D3–D4） |
| **修改** | `ai_engine/app/pipeline/rules/v2_starter.yaml` + `locales/zh_CN.json` |
| **修改** | `client/src/constants/qualityWarnings.ts` + `measurabilityNotice.ts` + `capture.tsx` / `params.tsx` |
| ~~修改~~ | ~~`engine_warnings.py`~~ → **实现**：`quality_warnings` + `rotation_issue_copy.py`（见 NFR-M7-R1-01）

**不改（Phase A）**：`version_router.py`、DB schema（除非新增 warning code 需 alembic 文档同步）

---

## 十一、排期建议

```text
Sprint R1（Phase A）：A1–A9 + AC-A 全过 → 可发版止血
Sprint R2（Phase B 前半）：B1–B4 + AC-B1–B3
Sprint R3（Phase B 后半）：B5–B7；B6/B8 与 M7-09 / 标注并行
持续：Phase C 随 ECS/ENG-06 Trigger
```

**与现有队列关系**：优先于 W27 ECS 标定（量准再标定）；与 **M7-09 杆追踪** 可并行，B6 依赖 M7-09 产出。

---

## 十二、待拍板决策（站会）

| # | 问题 | 建议默认 |
|---|------|----------|
| 1 | 旋转类是否对用户仅 face_on 开放？ | **是** |
| 2 | Phase A 是否强制 V1 跑 auto-detect sanitize？ | **是** |
| 3 | absurd 度数是否永久禁止进 issue 文案？ | **是**（通过 sanity 的除外） |
| 4 | 先 top±5 max（A5）还是直接上三估计器（B2）？ | **A5 先上，B2 紧随其后** |
| 5 | 新 warning `rotation_reading_unreliable` 是否算 `engine_warnings`？ | **否（已落地）** → `quality_warnings` + 报告拍摄提示 / `QUALITY_WARNING_COPY` |
| 6 | Pro clip 是否单独 `analysis_mode`？ | Phase A 用 flag；长期可独立 mode |

---

## 十三、相关文档

| 文档 | 关联 |
|------|------|
| [`p2-phase2-dev-queue.md`](./p2-phase2-dev-queue.md) Batch-I | 排期入口 |
| [`wait-for-triggers-checklist.md`](./wait-for-triggers-checklist.md) | M7-09 / ENG-04 |
| [`test_nelly_dtl_scoring.py`](../../ai_engine/tests/test_nelly_dtl_scoring.py) | R2 基线 |
| [`w22-driver-phase-weights-calibration.md`](./w22-driver-phase-weights-calibration.md) | 机位×球杆标尺 |

---

## 十四、Phase A 闭环状态（2026-05-30）

| 项 | 状态 |
|----|------|
| 引擎 A1–A6 + 回归 CI | ✅ `make ai-engine-test-rotation` |
| 客户端 A7–A8 + 机位 toast | ✅ Jest 11 passed |
| 文档 FR 表 / API / smoke | ✅ `docs/23` §3.14、`experience-version-smoke-runbook` §M7-R1 |
| AC-A4 V1 单测 | ✅ `test_rotation_regression_v1_path` |
| B1 pose_refine | ✅ repo + 接入 `real_pipeline` |
| B2–B3 三估计器 + 融合 | ✅ `compute_rotation_track` + 机位前置推断 |
| B4 几何下界 C | ✅ repo · `test_rotation_track` 合成否决 |
| B5 top 双证据 | ✅ repo · 腕/肩峰值 >8 帧 → backswing max + `top_frame_mismatch` |
| B7 preprocess_v2 router | ✅ repo · V2 桶 + `M7_VIDEO_READER_V2_ENABLED`（默认 off） |
| AC-B7 timing 回归 | ✅ `test_preprocess_v2_timing_regression` · fixture 齐后 green |
| AC-A1 真视频 R2 | ⏳ drop `fixtures/real/*.mp4` → `test_rotation_regression_real` |
| AC-A4 真机 E2E | ⏳ 体验版 smoke 人工勾 |
| Phase B 余量（B6–B8） | 📋 B6 等 M7-09 · B7 开 flag 前跑 timing gate · B8 pose A/B |

**发版前**：CVM `publish` ai_engine + 体验版跑 smoke §M7-R1 全勾。

---

## 十五、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.4 | 2026-05-30 | B2–B3 三估计器 + fusion + rotation_confidence；pipeline 机位前置 |
| v0.7 | 2026-05-31 | AC-B7 V1/V2 phase timing 回归 infra + manifest R3 pack |
| v0.6 | 2026-05-31 | B7 preprocess_router · V2 桶 + `M7_VIDEO_READER_V2_ENABLED` 接线 |
| v0.5 | 2026-05-31 | AC-B1 R1 manifest + repeatability test infra；AC-B2 真视频 shoulder 断言 |
| v0.4 | 2026-05-30 | B4 几何下界 C + B5 top 双证据 repo；`top_frame_mismatch` quality_warning |
| v0.3 | 2026-05-30 | AC-A1 manifest v0.2 + 真视频 skip 测试；AC-A4 V1 单测；B1 pose_refine |
| v0.2 | 2026-05-30 | Phase A repo 闭环；AC-A2/A3/A5 ✅；CI 改 `ai-engine-test-rotation`；warning 走 quality_warnings |
| v0.1 | 2026-05-30 | 初版：Phase A/B/C + rotation_track 规格 + 产品清单 + AC + 文件清单 |
