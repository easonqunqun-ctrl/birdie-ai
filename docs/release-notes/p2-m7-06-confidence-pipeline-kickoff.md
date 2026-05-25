# P2-M7-06 · 置信度上链路化 · 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1，落地三层置信度（feature / issue / overall）+ 报告页 Trust UI + 重拍引导
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.6 · P2-M7-06`](../23-二期可编码规格说明书.md#36-p2-m7-06--置信度上链路化特征--诊断--整体三层)
> 前置 kickoff：[`p2-m7-04-camera-angle-calibration-kickoff.md`](./p2-m7-04-camera-angle-calibration-kickoff.md)（**硬依赖**：`camera_angle_offset_deg` 是 overall confidence 公式输入之一）
> 主线：[`docs/20 §3.1 Trust`](../20-AI引擎产品力迭代设计.md#31-可信度trust)

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-06 置信度上链路化**落地一份「**W17 即可起跑、W22 三层置信度全链路就绪**」的算法 + 客户端启动 SOP，让算法 + AI 工程 + 客户端明确：

- 一期 `pose.visibility` 单一信号 + `quality_warnings` 文案 + 无评分置信度的现状
- 三层置信度规约：`feature_confidence` / `issue_confidence` / `analysis_confidence` 计算来源
- 报告页 Trust UI：高 / 中 / 低色块 + "建议重拍"引导
- 与 P2-M7-04（`offset_deg`）/ M7-15（用户反馈）/ M7-14（灰度）分工

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/05`](../05-AI模型技术规格文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不动一期 `quality_warnings` 机制 | 与新 `engine_warnings` / `confidence` **并存**（详 §3.5；与 [`p2-m7-02-video-reader-enhancement-kickoff.md`](./p2-m7-02-video-reader-enhancement-kickoff.md) §4.4 对齐） |
| 不新增 issue 类型 | M7-10 负责；本任务只为每 issue 加 `confidence` 字段 |
| 不改 LLM 报告渲染 | M7-16 按 confidence 做文案差异化；本任务只输出数值 |
| 不收集"重拍按钮"被点击的真实回归数据 | M7-15 负责回流 ECS 候选池；本任务只提供按钮 |

### 1.3 与其他文档的关系

```
docs/23 §3.6          ← 需求真源
docs/05 §8.8          ← 已就位的算法规格
docs/20 §3.1 Trust    ← 产品力主线（本任务是 Trust 的"全栈落地"）
p2-m7-04-camera-angle ← offset_deg 是 overall confidence 输入
本文件                 ← 三层置信度公式 v0.1 + 报告 UI + 周计划
  ↓ W22 回流
docs/02 §11.1（拟）   ← analysis_confidence / feature_confidence / issue_confidence
docs/03 §8.1 / §9.1   ← analysis_confidence 列 + JSONB schema
docs/20 §3.1          ← Trust 主线进度
```

---

## 二、现状盘点

### 2.1 一期"可信度"实际形态

```
ai_engine.pipeline.pose.PoseResult
  ↓ visibility (F, 33)  ←  MediaPipe 原生关键点可见度
  ↓ valid_mask (F,)     ←  per-frame avg visibility ≥ min_per_frame_confidence (0.5)
preprocess.quality_warnings_from_preprocess(low_light / camera_shake / partial_occlusion / low_pose_confidence)
  ↓ list[str]
AnalyzeResult.quality_warnings: list[str]
  ↓ 落库（backend 字段）
client/src/constants/qualityWarnings.ts  →  文案 + 报告页气泡
```

**结论**：

- ① **没有数值化的置信度**：用户看到的是文案（"光线偏暗"），没有"我这报告 30% / 80%"的整体可信度
- ② **没有按特征/诊断分层**：spine_angle 测得准 vs hip_rotation 测得不准，对外**完全一致**展示
- ③ **没有"建议重拍"按钮**：用户即使知道光线差，只能放弃或重新走完整上传流程

### 2.2 一期相关代码

| 文件 | 行数 / 要点 | V2 改造 |
| --- | --- | --- |
| `ai_engine/app/pipeline/pose.py` L82-101 | `PoseResult.visibility` + `mean_visibility` 已存在 | **复用**：作为 feature_confidence 输入 |
| `ai_engine/app/pipeline/pose.py` L214-216 | `valid_mask` per-frame 阈值 0.5 | **复用**：阈值不改，新增 per-feature 加权统计 |
| `ai_engine/app/pipeline/preprocess.py` `quality_warnings_from_preprocess` | low_light / camera_shake 等 4 码 | **复用**：作为 overall confidence 惩罚项 |
| `ai_engine/app/pipeline/features.py`（拟） | 每特征 extract 后无 confidence 标记 | **改造**：每特征返回 `value + confidence` 二元组 |
| `ai_engine/app/pipeline/diagnose.py` | 15 条 rule 直接产 issue，无 confidence | **改造**：每条 rule 输出 `issue.confidence` |
| `ai_engine/app/pipeline/scoring.py` | `score_overall` 不接 confidence | **改造**：增 `compute_analysis_confidence()` |
| `ai_engine/app/schemas.py` L54-75 `AnalyzeResult` | 无 confidence 字段 | **新增**：`analysis_confidence: float`（已在 docs/23 拟） |
| `client/src/constants/qualityWarnings.ts` | 文案 only | **保留**；新增 Trust 色块组件 |
| `client/src/pages/analysis/report.tsx` | 报告页无 confidence UI | **新增**：高/中/低色块 + 重拍 CTA |

### 2.3 已知缺口（vs docs/23 §3.6 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 三层置信度全链路输出 | ❌ 无 | features.py / diagnose.py / scoring.py 三处改造 |
| FR-2 诊断分档展示（>0.85 确诊 / 0.6-0.85 倾向 / <0.6 折叠） | ❌ 一刀切展示 | report.tsx UI 改造 |
| FR-3 overall < 0.5 → 报告页"建议重拍" + CTA | ❌ 无 | report.tsx + 跳转 params.tsx 复用 |
| FR-4 置信度来源透明 | 仅 quality_warnings 文案 | 报告"详情"展开 confidence breakdown |
| FR-5 高/中/低色块对齐 [`docs/20 §3.1 Trust`](../20-AI引擎产品力迭代设计.md#31-可信度trust) | ❌ 无 | UI + 文案 |

---

## 三、模块设计

### 3.1 新增/改造一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 置信度计算 | `ai_engine/app/pipeline/confidence.py`（新） | 三层公式 + 来源记录 | 2 PD |
| features 改造 | `ai_engine/app/pipeline/features.py` | 每特征返回 `(value, confidence)` | 1.5 PD |
| diagnose 改造 | `ai_engine/app/pipeline/diagnose.py` | 每 rule 算 `issue.confidence` | 1.5 PD |
| scoring 改造 | `ai_engine/app/pipeline/scoring.py` | 合成 `analysis_confidence` | 1 PD |
| schemas | `ai_engine/app/schemas.py` + `backend/app/schemas/analysis.py` | 增 confidence 字段 | 0.5 PD |
| 客户端 UI | `client/src/components/TrustBadge.tsx`（新） + `report.tsx` 改造 | 高/中/低色块 + 重拍 CTA | 2 PD |
| 单测 | `tests/test_confidence.py` 等 | 三层公式 + UI snapshot | 1.5 PD |

**合计：~10 PD**（与 docs/23 §3.6 估时 5 PW 略宽，含 UI 设计走查 buffer）

### 3.2 `confidence.py` 三层公式 v0.1

#### 3.2.1 `feature_confidence`（每特征 0-1）

```python
def feature_confidence(
    feature_name: str,
    pose: PoseResult,
    phase_frames: tuple[int, int],   # 该特征所在阶段的起止帧
    relevant_landmarks: list[int],   # 该特征用到的 MediaPipe 关键点索引
) -> float:
    """
    输入：pose.visibility[phase_frames, relevant_landmarks]
    输出：mean(visibility) × (有效帧占比) × (角度补偿因子，可选)
    """
    sub = pose.visibility[phase_frames[0]:phase_frames[1], relevant_landmarks]
    valid_frame_ratio = (sub.mean(axis=1) >= 0.5).mean()
    mean_vis = sub.mean()
    return float(mean_vis * valid_frame_ratio)
```

| 特征 | relevant_landmarks | 备注 |
| --- | --- | --- |
| `spine_angle_setup` | shoulder_l/r + hip_l/r | 4 点 |
| `x_factor` | shoulder_l/r + hip_l/r | 4 点 |
| `tempo_ratio` | wrist_l + wrist_r | 2 点（节奏靠手腕） |
| ...（W18 实现时全 15 特征补齐） |

#### 3.2.2 `issue_confidence`（每诊断 0-1）

```python
def issue_confidence(issue_type: str, evidence: dict) -> float:
    """
    每条 rule 自行声明 confidence：
    - 触发该 issue 的关键特征的 feature_confidence 加权平均
    - 阈值距离（特征值离 ideal 越远，confidence 越高）
    """
    relevant_features = ISSUE_FEATURE_DEPENDENCY[issue_type]
    feat_conf = mean([evidence[f].confidence for f in relevant_features])
    threshold_distance = compute_threshold_distance(issue_type, evidence)
    return float(feat_conf * (0.5 + 0.5 * sigmoid(threshold_distance)))
```

| 档位 | 范围 | UI 行为 |
| --- | --- | --- |
| 确诊 | > 0.85 | 红/橙色块，置顶 |
| 倾向 | 0.6 - 0.85 | 蓝色块，带"AI 倾向于认为"前缀 |
| 隐藏 | < 0.6 | 折叠到"AI 不太确定"展开区 |

#### 3.2.3 `analysis_confidence`（整体 0-1）

```python
def compute_analysis_confidence(
    pose: PoseResult,
    quality_warnings: list[str],
    camera_angle_offset_deg: float,  # 来自 P2-M7-04
    feature_confidences: dict[str, float],
) -> float:
    base = pose.mean_visibility  # 0-1
    qw_penalty = 1.0 - 0.15 * len(quality_warnings)
    angle_penalty = 1.0 if camera_angle_offset_deg <= 15 else 0.4   # 与 M7-04 §3.3 对齐
    feature_avg = mean(feature_confidences.values())
    return float(min(1.0, max(0.0, base * qw_penalty * angle_penalty * feature_avg)))
```

**典型值**：

| 场景 | base | qw_penalty | angle_penalty | feature_avg | overall |
| --- | --- | --- | --- | --- | --- |
| 标准光线室内三脚架 | 0.92 | 1.0 | 1.0 | 0.88 | **0.81** 高 |
| 略暗光 + 轻微抖动 | 0.78 | 0.70 (2 warnings) | 1.0 | 0.72 | **0.39** 低 → 重拍 |
| 偏角 20° + 正常光 | 0.85 | 1.0 | 0.4 | 0.80 | **0.27** 低 → 重拍 |

### 3.3 档位与 UI 对应

| analysis_confidence | UI 色块 | 文案 | CTA |
| --- | --- | --- | --- |
| ≥ 0.75 | 绿（mint）| "AI 高可信" | 无 |
| 0.5 - 0.75 | 金（gold）| "AI 中等可信，可参考" | 无 |
| < 0.5 | 灰 + 警告条 | "AI 难以做出可靠分析" | **重拍**按钮 → 跳 `pages/analysis/params.tsx` |

> 配色须走 `client/src/app.scss` CSS 变量（`--color-accent-mint` / `--color-gold` / `--color-warning`）；**不**硬编码 HEX（AGENTS.md §3 硬约束）。

### 3.4 重拍按钮跳转逻辑

```tsx
// client/src/pages/analysis/report.tsx 新增
{report.analysis_confidence < 0.5 && (
  <TrustWarningCard
    onRetake={() => Taro.reLaunch({
      url: '/pages/analysis/params?retake_from=' + report.analysis_id,
    })}
  />
)}
```

`params.tsx` 收 `retake_from` 时预填上一次的 `camera_angle / club_type`。

### 3.5 与一期 `quality_warnings` 的关系

| 维度 | 一期 `quality_warnings` | 二期 `analysis_confidence` |
| --- | --- | --- |
| 形态 | `list[str]` machine codes | `float` 0-1 |
| 用途 | 单点提示（4 码） | 综合可信度 |
| 关系 | **保留 + 并存**：作为 confidence 公式的"惩罚因子"输入 | 既出 confidence 也出 warnings |
| UI | 报告底部气泡（已上线） | 报告顶部色块 + 可选 CTA |

---

## 四、字段 / 配置草案 v0.1（W19 编码用）

> 与 [`docs/02 §11.1`](../02-API接口设计文档.md) / [`docs/03 §8.1`](../03-数据库设计文档.md) 拟定字段对齐；W22 回流定稿。

### 4.1 `AnalyzeResult` 字段增量

```jsonc
{
  "analysis_confidence": 0.81,              // 整体（FR-1）
  "feature_confidences": {                  // 每特征（FR-1）
    "spine_angle_setup": 0.88,
    "x_factor": 0.62,
    "tempo_ratio": 0.91
    // ... 15 特征
  },
  "issues": [
    {
      "type": "casting",
      "name": "抛杆",
      "severity": "high",
      "confidence": 0.92,                   // 每诊断（FR-1）
      "confidence_tier": "confirmed"        // confirmed / leaning / hidden
    }
  ]
}
```

### 4.2 数据库

- 列：`swing_analyses.analysis_confidence FLOAT NOT NULL DEFAULT 1.0`（[`docs/03 §8.1`](../03-数据库设计文档.md) 拟）
- 特征/诊断 confidence 写入 `new_features_payload.feature_confidences` 与 `detected_issues[].confidence` JSONB（[`docs/03 §9.1`](../03-数据库设计文档.md) 拟）

### 4.3 兼容（兜底）

| 场景 | 行为 |
| --- | --- |
| V1 引擎遗留报告（无 confidence） | `analysis_confidence = 1.0`（客户端不展示色块，**也不**展示 CTA） |
| 灰度回滚 | 同上；V1 容器输出始终 `1.0` |

---

## 五、验证数据

### 5.1 单测（必）

- `tests/pipeline/test_confidence.py`：三层公式输入/输出表（≥10 案例）
- `tests/integration/test_confidence_e2e.py`：固定 fixture（暗光 / 抖动 / 偏角）→ 期望 confidence 区间

### 5.2 故意"差视频"测试集（AC-2）

| 类别 | 数量 | 生成方式 | 期望 |
| --- | --- | --- | --- |
| 暗光 | ≥3 段 | 一期 `fixtures/quality/low_light_*.mp4` 已存在 | `analysis_confidence < 0.5` → CTA 出现 |
| 抖动 | ≥3 段 | 一期 fixtures | 同上 |
| 偏角 20° | ≥3 段 | 复用 P2-M7-04 §5.2 物理偏角集 | 同上 |

### 5.3 客服反馈基线（AC-3）

- 一期数据：导出近 30 天客服工单中"分数低无解释"占比作为基线
- 二期目标：上线 4 周后该类型工单下降 ≥50%

---

## 六、W17-W22 周计划

> **硬门槛**：P2-M7-04 W22 `camera_angle_offset_deg` 字段就绪；否则本任务 W21 W21 仅 PoC 不能进灰度。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；冻结三层公式 v0.1；与 M7-04 owner 对齐 `offset_deg` 输入 | ☑ 公式 review；☑ TrustBadge 组件设计稿 |
| **W18** | `confidence.py` PoC + `features.py` 改造（spine/x_factor/tempo 三特征先行） | ☑ 3 特征 confidence 输出；☑ 单测 ≥80% |
| **W19** | 15 特征 confidence 全覆盖 + diagnose 改造 + AnalyzeResult schema | ☑ 全 15 特征；☑ 15 issue confidence 输出 |
| **W20** | scoring.compute_analysis_confidence + 暗光/抖动测试集跑通 | ☑ AC-2 暗光/抖动 confidence < 0.5 |
| **W21** | 客户端 TrustBadge 组件 + report.tsx UI + 重拍 CTA | ☑ AC-2 CTA 点击跳转通过；☑ 设计走查通过 |
| **W22** | engine_version 灰度（M7-14）+ docs/02 / docs/03 字段回流 | ☑ AC 全勾；☑ 客服基线测量启动（4 周后再测） |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 三层公式定稿 + features/diagnose 改造 |
| AI 工程 | scoring 集成 + schema + 灰度对接 |
| 客户端 | TrustBadge 组件 + report 改造 + 重拍 CTA |
| 后端 | analysis_confidence 列入库 + ORM 同步 |
| 设计 | TrustBadge 色块走查（与 `app.scss` 变量对齐） |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | `feature_confidence` 全部偏高（MediaPipe visibility 普遍 >0.8）导致 overall 永远 >0.7 | W20 用故意差视频校准公式系数；必要时引入 `pose_jitter_std` 作为额外惩罚 |
| R-02 | 用户认为"高可信"但分数低，反而更困惑 | 文案改为"AI 高可信，分数低是真实存在的问题"；M7-16 LLM 文案差异化 |
| R-03 | 重拍 CTA 跳转丢失上下文 | `retake_from` query param 预填 club_type/camera_angle |
| R-04 | confidence 字段灰度回滚时客户端崩溃 | schema `analysis_confidence: float \| null`，前端 `?? 1.0` 兜底 |

### 7.3 AC 兜底（复述 docs/23 §3.6）

- [ ] **AC-1**：`GET /v1/analyses/{id}` 响应可观测三层 confidence（>0 ≤1）
- [ ] **AC-2**：故意暗光视频 → `analysis_confidence < 0.5` → 报告页"建议重拍" CTA 出现并可跳转
- [ ] **AC-3**：上线 4 周后"分数低无解释"客服工单下降 ≥50%

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 | 上下游消费 |
| --- | --- | --- |
| P2-M7-04 机位 | 消费 `camera_angle_offset_deg` | overall 公式 angle_penalty |
| P2-M7-10 诊断 V2 | 提供 issue_confidence 接口 | RuleEngine 实现 confidence 输出 |
| P2-M7-14 灰度 | 挂 `engine_version=v2.0` | V1 报告 confidence=1.0 |
| P2-M7-15 用户反馈 | 提供 confidence 上下文 | "踩"+ 低 confidence 优先入候选池 |
| P2-M7-16 LLM 文案 | 消费 confidence_tier | 文案模板按"确诊/倾向"分支 |

### 8.2 Trust UI 设计参考

- 色块走 `--color-accent-mint`（高）/ `--color-gold`（中）/ `--color-text-muted`（低）
- 警告条用 `--color-warning` + 12px text
- "重拍"按钮走 `--color-primary` 主 CTA（与 params.tsx 一致）
- 详 [白皮书 §7.2](../../灵鸟golf-产品设计白皮书.md) 视觉规范

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；三层公式 v0.1 + TrustBadge 设计 + W17-W22 周计划 |
| v0.2 | W22 收尾 | 公式参数 ECS 标定后回流 docs/05 §8.8；本文件 superseded |
