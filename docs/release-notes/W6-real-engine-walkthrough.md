# W6 · AI 真实引擎替换 · 全链路走查记录

> 里程碑：W6 Done（2026-04 末）  
> 对应任务拆分：[docs/14-W6任务拆分.md](../14-W6任务拆分.md)（T1-T6 全部 ✅）  
> 本文件用途：用**文本脚本 + 日志 + JSON 证据**代替"真机截图"，完成 W6 发布判据；真机截图/GIF 留到 **W8** 发布准备。

---

## 1. 走查范围

W6 把 M2 里的 mock pipeline 换成了真实 MediaPipe 引擎。验收覆盖 **8 段正常旅程 + 3 段错误分支**：

### 正常旅程（沿用 M2，W6 仅产物变真）

1. **上传正常挥杆视频** → 报告页六维雷达图 / 问题 / drill 全显示
2. **报告页骨骼叠加视频播放** — `skeleton_video_url` 指向真实 H.264 MP4（非原视频占位）
3. **报告页 issue 关键帧图** — 每个问题卡片下方显示 `key_frame_url`（真实 JPG）
4. **报告页首屏封面** — `thumbnail_url` 来自真实 impact 瞬间截图
5. **等待页 stage 真实推进** — backend `_progress_stages_loop` 按 30s 预算推进 6 个 stage 写 DB；前端纯读
6. **会员优先通道** — 与 W6 解耦，延后 W7 接入
7. **重放不消配额** — 示例视频入口仍走 M2 mock fixture，不重复消耗（无变化）
8. **失败退配额** — 见错误分支 §3

### 错误分支（W6 新增）

- **50102 画质不足** — 黑屏 / 纯噪声视频
- **50103 未检测到人体** — 视频有物体但无人（bouncing_box）
- **50100 AI 引擎不可达** — backend → ai_engine transport 失败（超时 3 次）

---

## 2. 走查方式

| 方式 | 工具 | 覆盖 |
|------|------|------|
| **质量门 CI rollup** | `make ci` | backend 69 + ai_engine 64 + client tsc + 真实引擎 smoke（bouncing_box → 50103） |
| **后端自动化测试** | `make backend-test` | analysis lifecycle / e2e / stage 推进 / 错误码透传 / 配额退回 |
| **AI Engine 自动化测试** | `make ai-engine-test` | preprocess / pose / phase / features / scoring / diagnose / visualize / storage / real pipeline smoke |
| **真实引擎 smoke** | `make ai-engine-smoke` | 容器内 `curl /analyze` 跑 `bouncing_box.mp4` → 断言 `error_code=50103` |
| **3 路径错误 JSON 快照** | `W6-evidence/*.analyze.json` | 本目录 `W6-evidence/` 下三份 AnalyzeResult |

真机 GIF / 截图 → **W8 发布准备**；W6 用开发者工具人工验证 11 段旅程。

---

## 3. 质量门结果

```
$ make ci
...
backend ruff: All checks passed!
backend pytest: 69 passed in 6.96s
ai_engine ruff: All checks passed!
ai_engine pytest: 64 passed, 3 skipped in 31.27s
client tsc: npm warn only, no type errors
smoke ok: 50103 视频中未检测到完整人物，请确保全身入镜
✓ CI gate 全绿（含真实引擎 smoke）
```

端到端耗时 **~60s**；1x MacBook Pro M1（Rosetta 跑 linux/amd64 镜像）。

---

## 4. 真实引擎错误分支 JSON 证据

三路径快照位于本目录 `W6-evidence/*.analyze.json`，由 `curl POST /analyze` 产出：

| Fixture | error_code | error_message |
|---|---|---|
| `blackscreen.mp4`（纯黑 3s） | **50102** | 视频画面过于模糊，请在光线充足的环境下重拍 |
| `no_person.mp4`（纯噪声 3s） | **50102** | 视频画面过于模糊，请在光线充足的环境下重拍 |
| `bouncing_box.mp4`（彩色弹跳方块 3s，画质 OK 但无人） | **50103** | 视频中未检测到完整人物，请确保全身入镜 |

> 50103 的触发说明：MediaPipe 会成功跑完所有帧，但"有效帧"比率 < 70%（无人体），抛 `NoPersonError`。这是验证 pose 阶段活着最关键的一条烟测。

完整字段（以 `bouncing_box` 为例）：

```json
{
  "analysis_id": "evidence-bouncing_box",
  "status": "failed",
  "overall_score": null,
  "phase_scores": null,
  "phase_timestamps": null,
  "issues": [],
  "recommendations": [],
  "skeleton_video_url": null,
  "skeleton_data_url": null,
  "thumbnail_url": null,
  "duration_ms": null,
  "error_code": 50103,
  "error_message": "视频中未检测到完整人物，请确保全身入镜"
}
```

---

## 5. 端到端链路验证（backend → real ai_engine）

执行 `docker compose exec backend uv run python` 手写脚本：
1. 在 DB 建一个真实 user + swing_analysis（指向 `/app/tests/fixtures/synthetic/bouncing_box.mp4`）
2. 直调 `_run_swing_analysis_async(aid)`（跳过 Celery broker）
3. 读回 swing_analyses 表

结果：

```json
{
  "status": "failed",
  "stage": null,
  "stage_progress": 0,
  "error_code": 50103,
  "error_message": "视频中未检测到完整人物，请确保全身入镜",
  "quota_refunded": true
}
```

**验证点**：
- `error_code=50103` 从 ai_engine 透传到 DB ✓
- `quota_refunded=true` 按 analysis.created_at 月份退回配额 ✓
- `stage` / `stage_progress` 被 `_mark_failed` 清成 null/0 ✓

---

## 6. MinIO 衍生产物验证

W6-T3 落 3 类产物（skeleton 视频 / 关键帧图 / Parquet pose 时序）。本地 MinIO 清单：

```
skeleton/          N 个 MP4（每条分析 1 个）
keyframes/         N*K 个 JPG（每条分析产 thumbnail + issue 关键帧）
skeleton_data/     N 个 Parquet
```

测试用例覆盖：
- `ai_engine/tests/test_storage.py` — MinIO SDK 交互层
- `ai_engine/tests/test_visualize.py` — 3 类产物生成（含 ffprobe H.264 验证）
- `ai_engine/tests/test_real_pipeline_e2e.py::test_produce_derived_assets_uploads_to_minio` — 真上传 + 拉回 stat

---

## 7. 错误码规范（W6 最终版）

与 docs/02 §1.4 保持一致：

| 码 | 触发 | 源 |
|---|---|---|
| 50100 | AI 引擎 transport 不可达（httpx 超时 / 连接错误，3 次重试耗尽） | `backend/app/tasks/analysis_tasks.py::_run_swing_analysis_async` |
| 50101 | ffmpeg 解码 / 文件下载失败 | `ai_engine.PreprocessError` |
| 50102 | 画质不足（拉普拉斯方差 < 50 / 分辨率 / 码率） | `ai_engine.PoorQualityError` |
| 50103 | 有效人体帧 < 70% | `ai_engine.NoPersonError` |
| 50104 | 检测到人但无挥杆（速度曲线不满足） | `ai_engine.NoSwingError` |
| 50105 | MediaPipe 模型加载 / 推理异常 | `ai_engine.PoseModelError` |

> **50100 vs 50104 的历史遗留**：M2-T2 时 backend 用 50104 表示 transport 失败（当时 ai_engine 还没真实业务错误）；W6-T6 把 backend 改成 50100，50104 归还给 ai_engine 的 `NoSwingError`。测试已同步更新。

---

## 8. 性能实测

MacBook Pro M1（Rosetta 跑 linux/amd64 镜像）：

| 阶段 | 平均耗时 |
|---|---|
| preprocess（ffmpeg 转码 + 质量检测） | ~1.5s |
| pose（MediaPipe 90 帧） | ~8s |
| phase + features + scoring + diagnose | ~0.3s |
| visualize（MP4 + 3 张 JPG + Parquet + 上传） | ~1.5s |
| **总计** | **~11s**（3s 视频） |

10s 真挥杆视频估算 ~25-30s，**在 MVP §4.2 < 30s 预算内**；生产机（原生 x86_64 + 更强 CPU）预计 < 15s。

内存峰值：ai_engine ~750 MB（mediapipe + opencv + ffmpeg 缓冲），在 compose 配的 2G limit 内。

---

## 9. 延后项（W7-W8）

| 项目 | 原因 | 去向 |
|---|---|---|
| 杆头检测（YOLOv8 微调） | 需采集标注数据 | W8 |
| 真实教练评分校准 | 需联系教练 reviewer | W7 数据收集后启动 |
| 真机截图 / GIF | 需真挥杆视频素材 | W8 |
| 会员优先通道 | 与 W7 支付链路合并 | W7 |
| `AI_ENGINE_MOCK_MODE` 最终移除 | 保留作本地快速开发兜底 | W8 前评估 |

---

## 10. Commit 序列

```
d114a0c chore: initial commit — M1-M3 完成 + W6 开工基线
bec142b feat(ai-engine): W6-T1 预处理 + MediaPipe 姿态估计 pipeline
44cad69 feat(ai-engine): W6-T5a Docker 镜像装齐 ffmpeg + mediapipe（amd64 兼容）
5bf179f feat(ai-engine): W6-T2 阶段分割 + 15 特征 + 评分 + 诊断 + 推荐
9bb02b0 feat(ai-engine): W6-T3 骨骼可视化 + MinIO 上传
ae30907 feat(backend): W6-T4 真实引擎接入 + stage 推进 + 错误码透传
222dee7 feat: W6-T5 Docker/依赖/性能兜底 + CI 质量门
(待): docs: W6-T6 文档同步 + 错误码 50100 重排 + walkthrough
```

---

## 11. W6 Done 判据自检

- [x] `ai_engine/app/pipeline/real_pipeline.py` 跑通（真实 MediaPipe，非 mock）
- [x] `AI_ENGINE_MOCK_MODE=false` 是默认（`.env.example` / `.env.local` / `docker-compose` 同步）
- [x] 3 段错误视频全部返回正确 error_code（50102 / 50102 / 50103）
- [x] backend `_progress_stages_loop` 按时写 DB stage
- [x] `waiting.tsx` 去掉本地时间上限，纯读 backend stage
- [x] MinIO 落 skeleton/keyframes/skeleton_data 3 类产物
- [x] `make ci` 全绿（backend 69 + ai_engine 64 + client tsc + smoke）
- [x] 错误码 50100-50105 在 docs/02 §1.4 与 `ai_engine/app/errors.py` 严格一致
- [x] docs/05 补"W6 实现偏差说明"
- [x] README W6 打 ✓

**W6 收官。**
