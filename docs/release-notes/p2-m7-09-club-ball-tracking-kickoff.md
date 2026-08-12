# P2-M7-09 · 杆 / 球追踪（best-effort · YOLO 微调）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.9`](../23-二期可编码规格说明书.md#39-p2-m7-09--杆--球追踪best-effort--yolo-微调)
> 前置：P2-M7-01 ECS v2 + M7-14 灰度

---

## 一、文档目的与边界

为 **P2-M7-09** 落地 W26-W38 best-effort SOP，引入 YOLO 微调实现杆头 / 杆身识别，输出 swing plane 拟合。**球识别二期不做**。

### 边界（不做）

- 不实现球识别（小目标 + 高速 + 小白球 ROI 不成立）
- 不强求识别成功率 ≥90%（best-effort）
- 不修改 docs/22/23/05 字段

---

## 二、现状盘点

- 一期无任何 object detection（pose-only）
- 一期无 YOLO 训练 / 推理基础设施

### 缺口（vs docs/23 §3.9 FR）

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 数据标注 SOP | 200 段视频 + LabelMe + 人力 | 4 PW（外包 + 算法review） |
| YOLO 训练 | `ai_engine/training/yolo_club/` | 3 PW |
| Pipeline 集成 | `ai_engine/pipeline/club_tracking.py`（新） | 1.5 PW |
| Swing plane 拟合 | `ai_engine/pipeline/swing_plane.py`（新） | 1.5 PW |
| JSONB schema | `new_features_payload.club_tracking` | 0.3 PW |
| 报告 UI 标签 | `pages/analysis/report.tsx` 加 "看到了杆 · 打磨中" | 0.5 PW |
| 单测 / Buffer | — | 1.2 PW |

**合计：~12 PW**（与 docs/23 §3.9 持平）

### 3.2 模型规格

- 基础：YOLOv8-nano
- 微调数据：200 段视频每 10 帧标 1 张 ≈ 6000 标注图（白盒）
- Class：club_head / club_shaft（无 ball）
- 模型 ≤30MB；CPU 推理 ≤3s（10s @30fps）

### 3.3 静默回退

```python
def track_club(video, pose):
    try:
        if not settings.ENABLE_CLUB_TRACKING:
            return None
        detections = yolo.detect_all_frames(video)
        if confidence_low(detections):
            return None  # 静默回退
        plane = fit_swing_plane(detections)
        return {'club_tracking': {'visible': True, 'plane': plane, ...}}
    except Exception:
        logger.exception('club tracking failed')
        return None
```

### 3.4 UI 提示

报告页：
- 识别成功 → 显示"🏌️ 看到了杆 · 此功能仍在打磨"
- 识别失败 → 不显示任何错误

### 3.5 集成 Trust（M7-06）

杆 tracking confidence 低 → 不计入 analysis_confidence 主链；仅作 best-effort 信号。

---

## 四、字段 v0.1

```jsonc
{
  "new_features_payload": {
    "club_tracking": {
      "visible": true,
      "detection_confidence": 0.78,
      "club_head_trajectory": [[x1,y1,t1],...],
      "swing_plane": {"angle_deg": 52.3, "fit_r2": 0.81},
      "engine_version": "v2.1"
    }
  }
}
```

```python
ENABLE_CLUB_TRACKING: bool = False  # W34 灰度起 True
```

---

## 五、验证数据

- ECS v2 标杆 ≥200 段，杆识别准确率 ≥70%（AC-1）
- 静默回退不影响主流程（AC-2）
- 报告"打磨中"标签可见（AC-3）

---

## 六、W26-W38 周计划

| 周 | 任务 |
| --- | --- |
| W26-W28 | 标注 SOP + 200 段标注 |
| W29-W31 | YOLO 训练 baseline |
| W32-W33 | swing plane 拟合 + pipeline 集成 |
| W34 | 静默回退 + UI 标签 |
| W35-W36 | ECS 验证 + 灰度 5% |
| W37-W38 | 灰度 25% + 监控 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | YOLO 训练 + plane 拟合 |
| 数据 | 标注外包管理 |
| AI 工程 | pipeline 集成 |
| 客户端 | UI 标签 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 标注延期 | 外包二级备选 + 算法预筛 |
| R-02 | 准确率 <70% | best-effort：静默回退；不算 AC 失败 |
| R-03 | 模型 >30MB | 量化 INT8 |
| R-04 | 推理超 3s | downsample 帧率；超时回退 |

### AC

- [ ] AC-1 ≥70% 杆识别准确率
- [ ] AC-2 静默回退
- [ ] AC-3 "打磨中"标签

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-07 阶段 | 提供 impact 帧 |
| P2-M7-14 灰度 | engine_version |
| P2-M7-06 Trust | 不计入主置信 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；YOLO 微调 + 静默回退 |
