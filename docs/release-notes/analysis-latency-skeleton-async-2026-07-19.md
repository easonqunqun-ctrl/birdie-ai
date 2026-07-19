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

- backend：`tests/test_analyses_e2e.py::test_e2e_quality_failed_via_inline_precheck_in_analyze`  
- ai_engine：`tests/test_pose_parquet_roundtrip.py` + `test_produce_derived_assets_*`（`defer_skeleton=False`）
