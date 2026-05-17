# W6 引擎 · 产品化路线图（源码锚点）

> 目标：对齐 [`docs/01-MVP功能需求规格说明书.md`](../01-MVP功能需求规格说明书.md) §4（质量门 / 骨骼视频）与 **真实 pipeline**。[`parallel-engineering-backlog.md`](parallel-engineering-backlog.md) P2/W6。

## 已实现（仓库）

| 能力 | 位置 |
|------|------|
| 归一化 30fps / 720p、`quality_score`、`PoorQualityError` | [`ai_engine/app/pipeline/preprocess.py`](../../ai_engine/app/pipeline/preprocess.py) |
| MediaPipe BlazePose、`overlay_pose`、`render_skeleton_video_mp4` | [`ai_engine/app/pipeline/pose.py`](../../ai_engine/app/pipeline/pose.py)、[`visualize.py`](../../ai_engine/app/pipeline/visualize.py) |
| `real_pipeline` mock 可调 `overlay_pose` | [`ai_engine/app/pipeline/real_pipeline.py`](../../ai_engine/app/pipeline/real_pipeline.py) |

## 未完 · 队列

1. **上报链闭环**：后端 / Celery 默认分析任务在非 mock 时切 **real_pipeline**，失败回退策略与 SLA 记入 Runbook。
2. **骨架视频 FPS**：实测 `overlay_pose=true` 成片的有效帧间隔；不达标时降采样或缩短叠加长度（白皮 ≥24fps）。
3. **质量门与 MVP §4.3**：告警型问题透传到报告文案；阻断策略与产品经理拍板后对 `01` Checkbox 核销。

验收：每条需附 **_fixture 短视频 + pytest / 冒烟**（或记录在 `docs/07`）。
