# W6 引擎 · 产品化路线图（源码锚点）

> 目标：对齐 [`docs/01-MVP功能需求规格说明书.md`](../01-MVP功能需求规格说明书.md) §4（质量门 / 骨骼视频）与 **真实 pipeline**。[`parallel-engineering-backlog.md`](parallel-engineering-backlog.md) P2/W6。  
> **产品力与评分迭代（话术、ECS、三线）**：见 [`docs/20-AI引擎产品力迭代设计.md`](../20-AI引擎产品力迭代设计.md)（白皮书 §5.2.1）。

## 已实现（仓库）

| 能力 | 位置 |
|------|------|
| 归一化 30fps / 720p、`quality_score`、`PoorQualityError` | [`ai_engine/app/pipeline/preprocess.py`](../../ai_engine/app/pipeline/preprocess.py) |
| MediaPipe BlazePose、`overlay_pose`、`render_skeleton_video_mp4` | [`ai_engine/app/pipeline/pose.py`](../../ai_engine/app/pipeline/pose.py)、[`visualize.py`](../../ai_engine/app/pipeline/visualize.py) |
| `real_pipeline` mock 可调 `overlay_pose` | [`ai_engine/app/pipeline/real_pipeline.py`](../../ai_engine/app/pipeline/real_pipeline.py) |

## 未完 · 队列

1. **上报链闭环**：后端 / Celery 默认分析任务在非 mock 时切 **real_pipeline**，失败回退策略与 SLA 记入 Runbook。
2. **骨架视频 FPS**：`render_skeleton_video` 经 `resolve_skeleton_output_fps` 保证编码 ≥24fps，成片经 ffprobe 验收（**v1.2.3** ✅）；真机流畅度抽测仍 ⏳
3. **质量门与 MVP §4.3**：告警型问题透传到报告文案；阻断策略与产品经理拍板后对 `01` Checkbox 核销。
4. **`docs/20` 已入库可执行项**：验收见 [`docs/01` §4.5](../01-MVP功能需求规格说明书.md#45-ai-引擎产品力对齐-docs20)；排期 **ENG-01～ENG-06** 见 [`docs/19` §6.3](../19-产品开发迭代计划-当前队列.md#63-主表plan-id)。

验收：每条需附 **_fixture 短视频 + pytest / 冒烟**（或记录在 `docs/07`）。

## 生产 / 预发切换速记

| 步骤 | 说明 |
|------|------|
| ai_engine 容器 | 设置 **`AI_ENGINE_MOCK_MODE=false`**（及所需模型权重挂载），使 `POST /analyze` 走 [`real_pipeline.py`](../../ai_engine/app/pipeline/real_pipeline.py)。 |
| backend | 仅消费 `AI_ENGINE_URL` / `AI_ENGINE_TIMEOUT`；无需为 mock 单独改代码。 |
| Celery | worker 与 **beat** 常驻；beat 已含分析任务调度与支付/会员周边周期任务（见 `app/celery_app.py`）。 |
| 回归 | `make backend-test` + [`docs/release-notes/mvp-o01-o04-par-runbook.md`](mvp-o01-o04-par-runbook.md) 真机上传条目（与 O-01/O-04 交叉）。 |
