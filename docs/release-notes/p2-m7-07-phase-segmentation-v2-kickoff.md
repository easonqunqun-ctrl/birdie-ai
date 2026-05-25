# P2-M7-07 · 阶段分割算法 V2 · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.2 期间，落地多信号融合 + 轻量 NN + V1 fallback 的阶段分割算法
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.7 · P2-M7-07`](../23-二期可编码规格说明书.md#37-p2-m7-07--阶段分割算法-v2多信号融合--轻量神经网络--v1-fallback)
> 前置：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（训练数据）+ [`p2-m7-14-engine-version-ab-kickoff.md`](./p2-m7-14-engine-version-ab-kickoff.md)（灰度）

---

## 一、文档目的与边界

为 **P2-M7-07** 落地一份「**W22 起跑、W30 V2 阶段分割灰度上线**」的算法 SOP，明确：

- 一期 `phases.py` 启发式纯几何的边界（试挥误判 / 慢挥被丢弃）
- 多信号融合 + 1D CNN/Transformer-tiny 设计
- V1 fallback 链路与 `segmentation_method` 字段
- ECS v2 训练集 + 一期 NoSwingError Top 100 回归

### 边界（不做）

- 不修改 docs/22/23/05 字段；不改 `phase_scores` 主结构（追加 `segmentation_method` 字段）
- 不实现完整 Transformer（保持 ≤10MB CPU 友好）
- 不在本任务训练杆 / 球追踪辅助信号（依赖 M7-09 选做）

---

## 二、现状盘点

### 2.1 一期 phases.py

```
ai_engine/app/pipeline/phases.py
  → 纯启发式：腕速度 + 手位置 + 髋旋转
  → MIN_DURATION_SEC = 2.0
  → 失败抛 NoSwingError → error_code 50100
```

**痛点**：慢挥（≥1.5s）被判 too short；试挥（无 impact）误入正式记录；多挥视频只识别第一次。

### 2.2 缺口（vs docs/23 §3.7 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 多信号融合 | 单信号 | 加 wrist speed + pose + hip rotation + (optional) club |
| FR-2 完整性检测 | ❌ | top→impact→follow 链路约束 |
| FR-3 MIN_DURATION_SEC 1.5 | 2.0 | 配置项调整 |
| FR-4 1D CNN/Transformer-tiny | ❌ | 新模型 |
| FR-5 启发式硬约束 | 部分 | 加 ordering 约束 |
| FR-6 V1 fallback | ❌ | 链路设计 |
| FR-7 ECS v2 + 10K 一期回流训练 | ❌ | 训练数据 pipeline |

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 多信号融合 | `ai_engine/app/pipeline/phases_v2.py`（新） | 2 PW |
| NN 训练 / 推理 | `ai_engine/app/pipeline/segmenter_nn.py`（新） | 4 PW |
| Fallback 链路 | `phases.py` 改 | 0.5 PW |
| 训练数据 pipeline | `tools/seg_train_data.py`（新） | 2 PW |
| ECS 回归 | `tests/regression/test_phases_v2.py` | 1 PW |
| 单测 | 多个 | 1.5 PW |
| Buffer | — | 1 PW |

**合计：~12 PW**（与 docs/23 §3.7 持平）

### 3.2 多信号融合输入

| 信号 | 数据源 | 用途 |
| --- | --- | --- |
| Wrist speed | pose.keypoints[wrist] 帧间速度 | 击球点检测 |
| Pose visibility 趋势 | pose.visibility per-frame | 关键帧 robust |
| Hip rotation speed | pose.keypoints[hip] 角度变化 | top 检测 |
| Foot pressure proxy | 双脚 y 偏移 | 重心转移阶段 |
| Club bbox (optional, M7-09) | YOLO 微调 | 杆头位置峰 |

### 3.3 1D CNN 设计草案

- Input: 每帧 33×3 keypoints + visibility (33d) = 132d
- Window: 30 frames (~1s @30fps)
- Conv1D layers: 64→128→64 channels
- Output: 6 phase logits per frame → softmax
- Loss: cross-entropy + smoothness regularizer
- Size: <10MB（INT8 quantized）

### 3.4 Fallback 链路

```python
def segment_phases_v2(pose):
    try:
        result_nn = segmenter_nn.infer(pose)
        if result_nn.confidence >= 0.6 and validate_hard_constraints(result_nn):
            return PhaseResult(method='v2_nn', ...)
    except Exception:
        pass
    # fallback
    return segment_phases_v1(pose)  # 一期启发式
```

### 3.5 启发式硬约束

```python
def validate_hard_constraints(result):
    return (
        result.setup_end < result.top_frame < result.impact_frame < result.follow_end
        and (result.impact_frame - result.setup_end) >= 30  # ≥1s
    )
```

---

## 四、字段 v0.1

### 4.1 `swing_analyses.phase_scores` JSONB 追加

```jsonc
{
  "phase_scores": {
    "setup": {...},
    // ... 一期既有
    "segmentation_method": "v2_nn"  // 'v1_heuristic' | 'v2_nn'
  }
}
```

不需 migration，JSONB 内追加字段。

### 4.2 配置项

```python
M7_V2_SEGMENT_NN_ENABLED: bool = False  # W22 灰度起为 True
M7_V2_SEGMENT_MIN_DURATION_SEC: float = 1.5  # 从 2.0 调整
```

---

## 五、验证数据

- 训练：ECS v2 ≥500 段（标注）+ 一期生产数据 ≥10K 段（弱标签）
- 验证：ECS v2 holdout ≥100 段；AC-1 IoU ≥0.8 准确率 ≥90%
- 回归：一期 NoSwingError Top 100 在 V2 上 ≥70% 成功（AC-2）
- 单测：试挥不入正式记录 ≥85%（AC-3）

---

## 六、W22-W30 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| W22 | 评审；ECS v2 训练集 + 一期标签回流 pipeline | ☑ 数据准备 |
| W23-W24 | 多信号融合 + NN 模型架构定稿 + 训练 baseline | ☑ baseline IoU ≥0.75 |
| W25-W26 | NN 训练 + 模型量化 | ☑ NN ≤10MB；IoU ≥0.8 |
| W27 | Fallback 链路 + 硬约束 | ☑ AC-4 通过 |
| W28 | ECS holdout 验证 + 一期 NoSwing Top 100 回归 | ☑ AC-1/2 通过 |
| W29 | 试挥/慢挥单测；灰度 5% | ☑ AC-3 通过 |
| W30 | 灰度 25% + 监控 | ☑ 失败率 ≤V1 基线 1.5x |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 总 owner；模型 + 融合 |
| AI 工程 | pipeline 集成 + 量化 + fallback |
| 数据 | ECS 标注 + 回流标签 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | NN 训练数据不足 | 一期生产数据弱标签 ≥10K；fallback v1 保底 |
| R-02 | 模型大小 >10MB | INT8 量化；裁剪 channels |
| R-03 | 慢挥用户 1.5-2.0s 影响 | MIN_DURATION 1.5 + 测试一组 1.5-2.0s 视频 |
| R-04 | 模型推理失败导致超时 | 30s timeout + fallback v1 |

### 7.3 AC

- [ ] AC-1：ECS IoU ≥0.8 准确率 ≥90%
- [ ] AC-2：一期 NoSwing Top 100 ≥70% 成功
- [ ] AC-3：试挥不入正式记录 ≥85%
- [ ] AC-4：NN 失败自动回退 V1

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-01 ECS v2 | 训练 + 验证集 |
| P2-M7-08 新特征 | 依赖本任务的阶段边界 |
| P2-M7-09 杆/球追踪 | 可选辅助信号 |
| P2-M7-14 灰度 | engine_version 挂 v2.0 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；多信号 + 1D CNN + fallback + 训练 pipeline |
