# AI Engine · 测试 Fixtures

这里存放 W6-T1 及后续 pipeline 单元/集成测试所需的视频素材和对应的期望输出。

## 目录结构

```
fixtures/
├── README.md                     ← 本文件（入库）
├── .gitkeep                      ← 空占位（入库）
├── generate_synthetic.sh         ← 用 ffmpeg 生成异常视频的脚本（入库）
├── download_samples.sh           ← 指引下载真实挥杆视频的脚本（入库）
├── real/                         ← 真实挥杆视频（*.mp4 不入库，手动 drop 或脚本拉）
│   ├── face_on_iron_01.mp4
│   ├── face_on_driver_01.mp4
│   └── dtl_iron_01.mp4
├── synthetic/                    ← 合成异常视频（*.mp4 不入库，运行脚本生成）
│   ├── blackscreen.mp4           ← 纯黑 3s → 触发 PoorQualityError (50102)
│   ├── static_person.mp4         ← 合成一张静态照片 → 触发 NoSwingError (50104)
│   └── no_person.mp4             ← 风景照转视频 → 触发 NoPersonError (50103)
└── expected/                     ← 每段视频对应的期望输出字段（入库，作为 golden set）
    ├── face_on_iron_01.json
    └── ...
```

## 视频不入库的原因

1. **版权**：YouTube 教学视频下载下来仅限本地开发测试，不能进仓
2. **体积**：`real/` 目录加起来可能 10-50MB，不适合 git 管理
3. **可复现性**：用脚本拉代替静态文件，降低"视频损坏/丢失导致测试挂"的概率

## 快速开工（3 种路径）

### 路径 A：GolfDB 公开数据集（推荐）

GolfDB 是 CVPR 2019 Workshop 发布的高尔夫挥杆视频库，390 段专业选手挥杆 + 8 个关键事件帧标注。

```bash
# 需要先 pip install gdown（Google Drive 下载工具）
bash download_samples.sh golfdb
```

这会下载 1-2 段样本到 `real/`。**完整数据集约 700MB**，`download_samples.sh` 默认只拉样本（~5MB）。

**GolfDB 视频是 160×160 中心裁切**，对 MediaPipe 精度略有影响（最佳输入 ≥256px），但够跑通 T1 质量门 + T2 阶段分割测试。

### 路径 B：YouTube 教学视频剪辑

```bash
# 需要 yt-dlp + ffmpeg
# 搜 "golf swing face on slow motion iron 1080p"，挑一段干净的 3-5 秒
yt-dlp -f "best[height<=1080]" "https://www.youtube.com/watch?v=XXX" -o tmp_full.mp4
ffmpeg -ss 00:01:23 -t 3 -i tmp_full.mp4 -c copy real/face_on_iron_01.mp4
rm tmp_full.mp4
```

推荐频道（质量高、视角标准）：
- **Me and My Golf** — 大量 face-on 慢动作
- **Rick Shiels** — iron/driver 对比多
- **TXG（Tour Experience Golf）** — 专业教学级慢动作

### 路径 C：自录视频

用 iPhone / Android 在练习场录 3-5 秒挥杆，1080p 60fps。face-on 视角最理想（摄像机正对球员正面，约 2-3 米距离）。

## 合成异常视频

```bash
bash generate_synthetic.sh
```

会在 `synthetic/` 下生成三个异常视频，用于 T1 质量门的失败分支测试。

## 期望输出（expected/）

当 T2 完成后，用脚本对每段 `real/*.mp4` 跑一次 pipeline 并**手工审核**关键字段（阶段时间戳、主 issue），存入 `expected/<video_name>.json`。之后单元测试会把真实输出与这个 golden set 对比，防止算法回归。

示例：

```json
{
  "video": "face_on_iron_01.mp4",
  "duration_sec": 3.2,
  "expected_phases": ["setup", "backswing", "top", "downswing", "impact", "follow_through"],
  "expected_overall_score_range": [70, 95],
  "expected_main_issue_types": ["casting"],
  "notes": "专业选手示范视频，应无明显 issue；若出现 high severity 说明算法过于敏感"
}
```

## 运行测试

```bash
# 在 ai_engine/ 根目录
uv run pytest tests/ -v

# 没有视频也能跑（会 skip 掉需要 fixtures 的用例）
uv run pytest tests/ -v -k "not needs_fixture"
```

测试层面用 `@pytest.mark.skipif` + `conftest.py::require_real_fixture` 检测文件存在，缺失就 **skip 而非 fail**，保证 CI 在没有 fixture 的环境下也能过。
