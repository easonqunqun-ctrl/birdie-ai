# 分析链路提速 · 内联预检 + 骨骼异步（2026-07-19）

## 变更

1. **去掉 Celery 单独 `POST /precheck`**  
   质量硬门槛改在 `preprocess_video` / `preprocess_video_v2` 下载后、ffmpeg 前做同源快速扫描（≤5s）。  
   `/precheck` 端点仍保留，供运维抽检。

2. **骨骼叠加视频默认异步**（`DEFER_SKELETON_VIDEO=true`）  
   `/analyze` 先出分数 + 缩略图 + 关键帧 + pose parquet，并上传 `normalized/{id}.mp4`。  
   报告 `completed` 后 Celery 调 `POST /derive-skeleton` 补骨骼 URL。  
   紧急回滚：ai_engine 设 `DEFER_SKELETON_VIDEO=false`。

3. **客户端**：报告页若见 `engine_warnings.code=skeleton_pending`，短轮询最多 ~30s 刷新骨骼切换。

## 体验预期

- waiting → 报告：**更早**看到分数与问题（少一次预检下载 + 跳过同步骨骼编码 数秒）  
- 「骨骼叠加」可能晚几秒出现；期间默认播原片

## 自测

- backend：`tests/test_analyses_e2e.py::test_e2e_quality_failed_via_inline_precheck_in_analyze` · `tests/test_skeleton_async_dispatch.py`  
- ai_engine：`tests/test_pose_parquet_roundtrip.py` · `tests/test_derive_skeleton.py` · `tests/test_early_quality_skip_stability.py`  
- client：`src/utils/__tests__/skeletonPendingPoll.test.ts`

## 修复（review 收口）

| 项 | 处理 |
|----|------|
| derive 原片重转码帧错位 | **已禁**：归一化缺失直接 failed |
| normalized 桶膨胀 | 骨骼上传成功后 `delete_object(normalized/{id}.mp4)` |
| 源片早检误拦抖动 | 早检 `skip_stability=True`；抖动仍在转码后硬拦 |
| 误派发骨骼任务 | 仅 `skeleton_pending=true` 时 `delay` |
| 报告轮询重置 tries | `skeletonPendingPoll` + effect 不依赖 warnings 数组 |
| CVM 热更回退风险 | 须正式 `compose build` backend/worker/beat（见发版） |
