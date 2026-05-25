# P2-M7-04 · 机位独立标尺 · 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，face_on / dtl 双套评分标尺 + 机位偏角检测与补偿
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.4 · P2-M7-04 · 机位独立标尺`](../23-二期可编码规格说明书.md#34-p2-m7-04--机位独立标尺face_on--dtl-双套)
> 前置 kickoff：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（**硬依赖**：ECS v2 须含 face_on + dtl 双机位样本 ≥10 段/机位，W17 第一批可用）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-04 机位独立标尺**落地一份「**W17 即可起跑（ECS 第一批到位后）、W24 双套标尺端到端就绪**」的算法 + 工程启动 SOP，让算法 + AI 工程明确：

- 一期 `camera_angle` **用户自选但未参与评分**的现状与痛点
- 双套 `PHASE_WEIGHTS_BY_ANGLE` + 双套 `ideal` 范围 v0.1 草案（W19 编码用；W21 ECS 标定后替换）
- 机位检测 / 偏角度量 / 光流补偿模块边界
- ECS v2 验证集要求（AC-2）与合成偏角测试集（AC-1）
- W17-W24 周计划 + 与 P2-M7-06 / P2-M7-14 分工

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22 / docs/23 / docs/20 任何字段 | 避免与 #18 / #19 / #20 race |
| 不实现球杆差异化标尺 | P2-M7-05 独立任务；本任务仅按 **机位** 分套 |
| 不实现完整三层置信度体系 | P2-M7-06 负责 `analysis_confidence` 全链路；本任务只输出 `camera_angle_offset_deg` + 偏角 >15° 的**最小 confidence 降档 hook** |
| 不改客户端机位选择 UI | 一期 `params.tsx` face_on / down_the_line 保留；V2 **自动检测**与用户选择不一致时以检测为准并写 warning |
| 不新增 `oblique` 客户端选项 | 算法内部可判 `oblique`；UI 仍二选一 |

### 1.3 与其他文档的关系

```
docs/23 §3.4          ← 需求真源
p2-m7-01-ecs-v2       ← 标定真值 + AC-2 验证集
本文件                 ← 模块设计 + 双套权重 v0.1 草案 + 周计划
  ↓ W24 回流
docs/05 §2.6（拟）    ← 双套 ideal 权重终稿
docs/03 §8.1（拟）    ← camera_angle_offset_deg 列
docs/02 §11.1（拟）   ← 响应字段 camera_angle_offset_deg
docs/20 §3.2（拟）    ← Calibration 主线进度
```

---

## 二、现状盘点

### 2.1 调用链与 `camera_angle` 实际用法

```
client/pages/analysis/params.tsx     用户选择 face_on | down_the_line
  ↓ POST /v1/analyses
backend swing_analyses.camera_angle  入库（用户声明值）
  ↓ AnalyzeRequest.camera_angle
ai_engine/app/pipeline/real_pipeline.py
  ↓ preprocess → pose → phases → features → scoring → diagnose
  ❌ req.camera_angle **未被读取**
  ↓
constants.PHASE_WEIGHTS（单套）+ FEATURES ideal（单套）→ score_overall
```

**结论**：用户选的机位只影响报告展示文案（`report.tsx` 📷 标签），**不参与打分**。face_on 与 dtl 同一套 ideal → 同一动作两种机位分数不可比，且 dtl 专属特征（如 swing plane）在 face_on 上被误用。

### 2.2 一期相关代码

| 文件 | 行数/要点 | V2 改造 |
| --- | --- | --- |
| `ai_engine/app/pipeline/constants.py` | 单套 `PHASE_WEIGHTS` + 15 特征单套 `ideal_min/max` | 增 `PHASE_WEIGHTS_BY_ANGLE` + `FEATURES_BY_ANGLE` |
| `ai_engine/app/pipeline/scoring.py` | `score_phase` / `score_overall` 不接收 angle | 增 `detected_angle` 参数 |
| `ai_engine/app/pipeline/diagnose.py` | `over_the_top` 注释「需 dtl，用 x_factor 代理」 | dtl 标尺下启用真实 plane 规则 |
| `ai_engine/app/pipeline/real_pipeline.py` | 未读 `req.camera_angle` | 插入 `detect_camera_angle` + warp 步骤 |
| `ai_engine/app/schemas.py` | `camera_angle: Literal["face_on","down_the_line"]` | 响应增 `camera_angle_offset_deg`（AnalyzeResult 扩展） |
| `ai_engine/tests/fixtures/real/` | 有 `face_on_*` + `dtl_*` 各 1 段（v1） | 扩 ECS 对齐样本 + 合成偏角集 |

### 2.3 已知缺口（vs docs/23 §3.4 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 机位自动检测 `{face_on, dtl, oblique}` | ❌ 无 | 新增 `camera_angle.py` |
| FR-2 输出 `camera_angle_offset_deg` | ❌ 无 DB 列 / 无响应字段 | migration 0007 + pipeline 写入 |
| FR-3 双套 `PHASE_WEIGHTS_BY_ANGLE` | ❌ 单套 | §4.1 v0.1 草案 |
| FR-4 偏角 ≤15° 光流补偿；>15° 降 confidence | ❌ 无 | `optical_flow_warp.py` + hook |
| FR-5 双机位 ideal 分别校准 | ❌ 单套 ideal | §4.2 v0.1 草案 + ECS W21 标定 |

---

## 三、模块设计

### 3.1 新增模块一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 机位检测 | `ai_engine/app/pipeline/camera_angle.py` | 关键点几何 → `{face_on, dtl, oblique}` + `offset_deg` | 3 PD |
| 光流补偿 | `ai_engine/app/pipeline/optical_flow_warp.py` | 偏角 ≤15° 轻量 warp keypoints / 可选帧 | 2 PD |
| 双套标尺 | `ai_engine/app/pipeline/angle_profiles.py` | `PHASE_WEIGHTS_BY_ANGLE` + `ideal_for_angle()` | 2 PD |
| 管线集成 | `real_pipeline.py` | 检测 → warp → scoring 选套 | 1.5 PD |
| ECS 回归 | `ai_engine/app/ecs/angle_regression.py` | AC-1 / AC-2 自动判定 | 2 PD |
| 单测 | `tests/test_camera_angle.py` 等 | 检测 + 评分波动 | 2 PD |

**合计：~12.5 PD**（与 docs/23 §3.4 估时 8 PW 一致，含 ECS 标定迭代 buffer）

### 3.2 `camera_angle.py` 检测逻辑（PoC 规格）

**输入**：`pose_result.keypoints`（MediaPipe 33 点，setup 帧 + top 帧采样）

**几何特征**（W18 PoC 实现，W19 调参）：

| 特征 | face_on 期望 | dtl 期望 |
| --- | --- | --- |
| 肩线 vs 画面水平夹角 | 近 0°（肩宽投影大） | 近 45-90° |
| 左右肩 z 深度差（若可用） | 小 | 大 |
| 髋-肩连线 vs 竖直夹角 | 中等 | 小（沿挥杆线） |

**输出**：

```python
@dataclass
class CameraAngleResult:
    detected_angle: Literal["face_on", "down_the_line", "oblique"]
    offset_deg: float          # 相对最近标准机位的偏角 [0, 90]
    confidence: float          # 检测置信度 0-1
    declared_angle: str | None # 用户声明（对比用，不参与评分选套）
    mismatch: bool             # detected != declared 且 confidence > 0.7
```

**选套规则**：评分 / 诊断使用 `detected_angle`（`oblique` 时 fallback 到 `declared_angle`，仍 oblique 则按 face_on 套 + 强制 `offset_deg` 惩罚）

### 3.3 光流补偿（FR-4）

| 偏角 | 行为 |
| --- | --- |
| `offset_deg ≤ 15` | OpenCV `calcOpticalFlowFarneback` 估计全局运动 → 轻量仿射 warp 关键点坐标（**不**重跑 MediaPipe） |
| `15 < offset_deg ≤ 30` | 不 warp；`analysis_confidence` 乘 0.6（M7-06 全链路就绪后接入统一公式） |
| `offset_deg > 30` | 不 warp；`analysis_confidence < 0.5` + engine_warning `camera_angle_large_offset` |

NFR：warp 延迟 ≤ 2s / 视频（§3.4 对齐 docs/23 NFR）

---

## 四、双套标尺 v0.1 草案

> W19 编码用初值；**禁止** face_on / dtl 直接套用同一 ideal。W21 起用 ECS v2 分桶统计替换（[`docs/20 §3.2`](../20-AI引擎产品力迭代设计.md#32-标尺与公平性calibration)）。

### 4.1 `PHASE_WEIGHTS_BY_ANGLE` v0.1

| 阶段 | face_on | dtl | 设计意图 |
| --- | --- | --- | --- |
| setup | 0.12 | 0.18 | dtl 更看脊柱角 / 站位 |
| backswing | 0.22 | 0.18 | face_on 更看躯干旋转 |
| top | 0.14 | 0.16 | dtl 略增（平面可见性） |
| downswing | 0.24 | 0.26 | dtl 略增（swing plane） |
| impact | 0.14 | 0.14 | 持平 |
| follow_through | 0.14 | 0.08 | face_on 更看收杆平衡 / 头稳 |

每套和 = 1.0（assert 与一期相同）

### 4.2 分机位 ideal 范围 v0.1（仅列 **差异特征**）

| 特征 | face_on ideal | dtl ideal | 备注 |
| --- | --- | --- | --- |
| `shoulder_rotation_top` | 30-95° | 25-90° | face_on 肩旋转可见性更好，区间略宽 |
| `x_factor` | 20-50° | 18-45° | dtl 对 X-factor 测量更敏感，上限收 |
| `spine_angle_setup` | 25-35° | 28-38° | dtl 脊柱角测量基准不同 |
| `spine_angle_impact_delta` | 0-18° | 0-15° | dtl 对 early extension 更敏感 |
| `head_lateral_shift` | 0-0.08 | 0-0.10 | face_on 头移测量更准，阈值更严 |

未列特征：**两机位共用一期 ideal**（W21 ECS 再分桶微调）。

### 4.3 用户声明 vs 自动检测

| 场景 | 行为 |
| --- | --- |
| 一致 | 静默，正常评分 |
| 不一致 + 检测 confidence ≥ 0.7 | `engine_warnings[]` 追加 `camera_angle_mismatch`（info）；报告仍用 **detected** 标尺 |
| 不一致 + 检测 confidence < 0.7 | 用 **declared** 标尺；warning `camera_angle_low_confidence` |

---

## 五、验证数据

### 5.1 ECS v2 子集（AC-2，依赖 P2-M7-01）

| 要求 | 数量 | 来源 |
| --- | --- | --- |
| face_on 已标注样本 | ≥10 段（W17 第一批） | ECS manifest `camera_angle=face_on` |
| dtl 已标注样本 | ≥10 段（W17 第一批） | ECS manifest `camera_angle=dtl` |
| 双机位同一球员同一动作 | ≥3 对（W21 理想） | ECS 扩展；AC-1 核心 |

**AC-2 判定**：`detect_camera_angle()` 在 ECS 验证集上 argmax 准确率 ≥ 95%

### 5.2 合成偏角测试集（AC-1，与 ECS **独立**）

| 类别 | 数量 | 生成方式 | 用途 |
| --- | --- | --- | --- |
| 0° 基准 | ≥3 段 | ECS face_on 原片 | AC-1 基准分 |
| 10° 偏角 | ≥3 段 | ffmpeg `rotate=10*PI/180` 或物理三脚架偏 10° 自录 | AC-1 波动 ≤5 分 |
| 20° 偏角 | ≥3 段 | 同上 20° | AC-1 边界；>15° 应触发 confidence 降档 |

存放：`ai_engine/tests/fixtures/angle/`（**不入库**，与 v2 codec fixtures 同策略）

### 5.3 与 P2-M7-02 fixtures 关系

| 维度 | M7-02 fixtures v2 | 本任务 angle fixtures |
| --- | --- | --- |
| 用途 | codec / HDR 解码回归 | 机位检测 + 偏角评分波动 |
| 可重叠 | 否（angle 集可基于 GolfDB / ECS 原片，不需 HEVC） | — |

---

## 六、接口与数据模型

### 6.1 响应字段（v0.1 草案，W24 回流 docs/02 §11.1）

```jsonc
{
  "camera_angle": "face_on",              // 一期字段：仍写用户声明值（兼容）
  "detected_camera_angle": "face_on",     // 新增：算法检测值
  "camera_angle_offset_deg": 8.5,         // FR-2
  "analysis_confidence": 0.82             // M7-06 全链路；M7-04 仅保证 offset>15° 时 <0.5
}
```

### 6.2 数据库

- 列：`swing_analyses.camera_angle_offset_deg FLOAT`（docs/03 §8.1 拟，migration `0007_swing_analyses_v2_columns`）
- `detected_camera_angle` 建议入 `engine_warnings` detail 或 `new_features_payload`（**不**新增 DB 列，降低 migration 面）

---

## 七、W17-W24 周计划

> **硬门槛**：W17 周一 ECS v2 第一批 ≥10 face_on + ≥10 dtl 可用；否则整任务顺延 1 周。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；读 `constants.py` / `scoring.py` / `diagnose.py`；ECS 子集导出脚本 | ☑ ECS angle 子集 ≥20 段清单；☑ PoC 检测伪代码 review |
| **W18** | `camera_angle.py` PoC + ECS 子集准确率摸底 | ☑ 摸底准确率 ≥85%（未达 95% 可接受，留 W21 调参） |
| **W19** | `angle_profiles.py` 双套权重 + scoring 接入；单测 | ☑ face_on/dtl 同特征不同分 ≥10 分差异（合理差异化 smoke） |
| **W20** | `optical_flow_warp.py`；合成 0/10/20° fixtures | ☑ warp ≤2s；☑ 10° 样本端到端跑通 |
| **W21** | ECS 回归 AC-2；双套 ideal v0.1 → v0.2（ECS 统计） | ☑ 机位识别 ≥95%；☑ §4.2 至少 3 特征 ideal 更新 |
| **W22** | AC-1 偏角波动；`real_pipeline` 集成 + migration | ☑ 0/10/20° 综合分波动 ≤5 分；☑ offset 写入 DB |
| **W23** | AC-3 偏角 >15° confidence hook；`engine_warnings` _MISMATCH | ☑ 20° 样本 confidence <0.5 + 报告「建议重拍」文案（依赖 M7-06 UI 或 stub） |
| **W24** | `engine_version` 灰度（P2-M7-14）；docs 回流 | ☑ AC 全达成；☑ docs/05 §2.6 增量 PR |

---

## 八、责任 / 风险 / 验收

### 8.1 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 总 owner；检测 / warp / 双套标尺 / ECS 回归 |
| AI 工程 | pipeline 集成 + migration + 单测 |
| 数据 / 教研 | ECS face_on+dtl 子集质量；W21 ideal 标定复核 |
| 客户端 | W24 报告页展示 `detected_camera_angle` + mismatch warning（小改，非阻塞 W22 后端） |

### 8.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | ECS W17 第一批 dtl 不足 10 段 | W17 启动内部自录补 dtl；顺延 W18 PoC |
| R-02 | MediaPipe 2D 关键点无法稳定分 oblique | oblique 阈值保守；fallback declared_angle |
| R-03 | 用户声明与检测不一致引发客诉 | `camera_angle_mismatch` warning + 报告脚注「已按画面自动识别机位评分」 |
| R-04 | 与 P2-M7-05 球杆标尺叠加组合爆炸 | M7-04 仅 angle 二维；M7-05 在其后叠加 club_category（docs/23 已排依赖） |

### 8.3 AC 兜底（复述 docs/23 §3.4）

- [ ] **AC-1**：同一段挥杆 0° / 10° / 20° 偏角综合分波动 ≤5 分
- [ ] **AC-2**：ECS v2 验证集机位识别准确率 ≥95%
- [ ] **AC-3**：偏角 >15° 时 `analysis_confidence` < 0.5 并触发「建议重拍」

---

## 九、附录

### 9.1 一期 `diagnose.py` 机位相关规则升级

| issue | 一期 | V2 |
| --- | --- | --- |
| `over_the_top` | x_factor 代理，不限机位 | **仅 dtl 标尺**启用；face_on 降 confidence 或不展示 |
| `flat_shoulder` / `steep_shoulder` | 单阈值 | dtl 标尺下启用 plane 相关阈值 |

### 9.2 与 P2-M7-06 / P2-M7-14 分工

| 任务 | M7-04 交付 | 下游消费 |
| --- | --- | --- |
| P2-M7-06 置信度 | `camera_angle_offset_deg` + 偏角惩罚因子 | 纳入 `analysis_confidence` 公式 |
| P2-M7-14 灰度 | 双套标尺挂 `engine_version=v2.0` | 回滚忽略 offset，单套 PHASE_WEIGHTS |

### 9.3 ECS manifest 必填字段（angle 子集）

ECS jsonl 须含（与 P2-M7-01 §四 manifest 对齐）：

```jsonc
{
  "camera_angle": "face_on",           // ground truth
  "camera_angle_offset_deg": 0,        // 标注员估计偏角，0=标准
  "club_type": "7_iron"
}
```

---

## 十、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；模块设计 + 双套标尺 v0.1 + W17-W24 周计划 |
| v0.2 | W24 收尾 | ECS 标定后的 ideal/权重终表回流 docs/05；本文件 `superseded` |
