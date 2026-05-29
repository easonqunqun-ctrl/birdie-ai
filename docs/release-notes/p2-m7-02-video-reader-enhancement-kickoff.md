# P2-M7-02 · 视频读取增强 · 启动包（W14 起跑）

> 版本：v0.1.1（2026-05-25）
> 适用范围：二期 Phase 2.0 → Phase 2.1 期间 AI 引擎视频读取链路 V2 改造的工程启动 SOP
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.2 · P2-M7-02 · 视频读取增强`](../23-二期可编码规格说明书.md#32-p2-m7-02--视频读取增强)
> 平行 kickoff：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（ECS v2 标定集，**数据驱动**；本文件**工程驱动**）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-02 视频读取增强**（HEVC / 10-bit HDR / 慢动作元数据 / 多档帧率归一化）落地一份「**W14 即可起跑、W17 进入 Phase 2.1 时整条 pipeline 端到端就绪**」的工程启动 SOP，让 AI 工程 + DevOps + 测试三方明确：

- 现有 `ai_engine/app/pipeline/preprocess.py` 与 `precheck.py` 的能力边界（**不是从零写**）
- 缺口对应到 docs/23 §3.2 哪几个 FR（**1:1 映射**），不重写需求
- `engine_warnings[]` 字段 v0.1 草案（先在本文件起草，回流到 docs/02 §11.1 / docs/03 §8.1 后撤回此处）
- Dockerfile 升级路径与镜像膨胀控制
- 测试视频集采集规范（**与 ECS v2 全不重叠**，独立用途）
- W14-W17 4 周可执行任务拆分 + 责任分配

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不动客户端上传链路 | 由 P2-M7-15（客户端 SDK）/ P2-M7-03（错误码 + 文案）覆盖；本文件仅 server-side |
| 不动算法（PoseEstimator / PhaseSplitter） | 容器/编码不变（H.264 yuv420p）；**fps 从 30 升到 60**，须走 `engine_version` 灰度（见 §10.3 / R-03） |
| 不预留 client / wxma 端拍摄按钮策略 | 由 P2-M7-15 客户端 SDK 升级覆盖 |
| 不涉及 ECS v2 数据采集 | 由 P2-M7-01 kickoff 覆盖；本文件用的回归视频集与 ECS v2 在用途与采集源上**完全独立** |
| 不修改 docs/22 / docs/23 / docs/20 任何字段 | 避免与 PR #18 / #19 / #20 race；本文件**只引用**，需求/字段变更由那 3 个 PR 收口 |

### 1.3 与其他文档的关系

```
docs/23 §3.2          ← 需求真源（FR / AC / NFR / 接口契约）
  ↑ 1:1 引用
本文件                 ← 工程启动 SOP（现状 / 任务拆分 / 周计划 / 风险）
  ↓ 完成后回流到
docs/05 §8.1（拟）    ← 技术规格（实际权重表、码表、机型矩阵附录）
docs/02 §11.1（拟）   ← engine_warnings[] 字段终稿 + 50120 错误码文案
docs/03 §8.1（拟）    ← engine_warnings JSONB 列终稿
```

> **forward reference 治理**：docs/23 §3.2 引用了 `docs/05 §8.1` / `docs/02 §11.1` / `docs/03 §8.1`，这 3 处目前是**占位**。本启动包**不**生成那 3 份文档的最终态，仅在 §4 给出 `engine_warnings[]` 字段 v0.1 草案，等 W17 PR 合入时由 P2-M7-02 owner 一次性回流；本文件届时打 `superseded` 标记。

---

## 二、现状盘点（ai_engine 视频读取链路 v1）

### 2.1 入口与调用链

```
POST /precheck (FastAPI)
  ↓
app/pipeline/precheck.py::run_precheck
  ↓
app/pipeline/preprocess.py::_materialize_input  (curl 下载 / 本地 cp)
  ↓
app/pipeline/preprocess.py::_ffprobe            (width/height/r_frame_rate/duration)
  ↓
app/pipeline/preprocess.py::_quick_scan_quality (cv2 采样 ≤5s, 不转码)
  ↓
app/pipeline/preprocess.py::enforce_quality_gates / quality_warnings_from_scan

POST /analyze (Celery worker)
  ↓
…同上前 3 步
  ↓
app/pipeline/preprocess.py::_ffmpeg_normalize   (30fps / 720p / H.264 yuv420p / -an)
  ↓
app/pipeline/preprocess.py::_scan_quality       (全量遍历 normalized.mp4)
  ↓
PreprocessResult → real_pipeline.py 后续算法
```

### 2.2 当前能力（已具备，**不**改动）

- **基础设施齐全**：ffmpeg / ffprobe / OpenCV / 工作目录管理 / curl 下载（含 MinIO 容器内直连改写）/ 质量门
- **precheck-preprocess 共用阈值**：`enforce_quality_gates` / `_ScanStats` / `composite_quality_score` 三处共用，V2 改造可继承
- **Dockerfile 基线**：`python:3.11-slim-bookworm` + `apt-get install ffmpeg`
  - Debian bookworm 官方 ffmpeg 4.4.x（GPL-built）**默认编入** libx265 / libvpx / libdav1d / libzimg（zscale 依赖库）
  - **行动项**：W14 起跑首日运行 §5.1 探针脚本确认实际容器 build flag，**不**假设
- **质量门 warning code 机制**：`quality_warnings_from_scan` 已返回 `["low_light", "camera_shake", ...]` 字符串列表；V2 阶段 **`quality_warnings` 保持一期不变**，`engine_warnings[]` 仅承载解码/归一化语义（见 §4.4）

### 2.3 关键文件与行数

| 文件 | 行数 | V2 改造预期 |
| --- | --- | --- |
| `ai_engine/app/pipeline/preprocess.py` | 660 | 主要改造对象，新增 `_ffmpeg_normalize_v2` / `_ffprobe_extended`，**保留** v1 函数走灰度 |
| `ai_engine/app/pipeline/precheck.py` | 89 | 几乎不动，仅 _ScanStats 字段扩展时同步 |
| `ai_engine/Dockerfile` | 49 | 增 `libzimg2` apt 包 + 复核脚本 ARG |
| `ai_engine/tests/test_preprocess.py` | （未读） | V1 行为冻结，新增 `test_video_reader_v2.py` 独立测试集 |
| `ai_engine/tests/fixtures/real/v2/` | （视频不入库） | 新增 7 类 v2 fixtures（详 §6） |

### 2.4 已知缺口（vs docs/23 §3.2 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 HEVC / VP9 解码 | ⚠️ 依赖 Debian ffmpeg 默认 build，**未显式验证** | W14 内运行 §5.1 探针；如缺 codec 则升级 ffmpeg 来源 |
| FR-2 24/30/60/120/240 fps 统一归一化到 **60fps** 时间轴 | ❌ `TARGET_FPS = 30` 硬编码 | 改为 `TARGET_FPS = 60`，并加 `_normalize_to_real_timeline` 处理慢动作 |
| FR-3 10-bit HDR → sRGB | ❌ 无 zscale filter | `_ffmpeg_normalize_v2` 加 `-vf zscale=t=linear,tonemap=hable,zscale=p=bt709:t=bt709:m=bt709,format=yuv420p` 链 |
| FR-4 慢动作元数据识别 | ❌ ffprobe 仅取 `r_frame_rate`，未读 `nominal_fps` / `nb_frames` / mov edit list | `_ffprobe_extended` 增加 `nominal_fps` 字段（mov 容器走 `tags:`，mp4 走 `nominal_frame_rate`） |
| FR-5 竖屏短边按设备分层（720 / 1080） | ❌ 硬编码 `TARGET_SHORT_SIDE = 720` | 对齐 docs/05 §2.2 推荐机型矩阵：旗舰机型走 1080，老机型走 720（W17 矩阵就位后切换） |
| FR-6 音频通道保留（供 M8 教练语音批注对齐） | ❌ `-an` 硬丢音轨 | V2 改 `-c:a aac -b:a 64k`（不上传到对象存储，但保留于 normalized.mp4 内部，供 M8 streamtrim） |
| 接口契约 `engine_warnings[]` | ❌ 当前仅返回 `quality_warnings` 字符串列表 | 升级为 `{code, level, detail}` 对象数组，详 §4 |
| 错误码 50120 | ❌ 未定义（codec 失败目前走 50101 `PreprocessError`） | 新增 `DecodeError(50120)` 专管 codec 不支持；50101 保留给下载/损坏（详 §3.1） |

---

## 三、增强项清单（与 docs/23 §3.2 FR 1:1 对齐）

> 工程量估计 = 1 PD（人日），含**编码 + 单测 + 自测**，不含真机回归（真机回归归 §7）

| FR | 改造点 | 文件 | 工程量 | Owner |
| --- | --- | --- | --- | --- |
| FR-1 | Dockerfile codec 复核 + 缺失补齐 | `ai_engine/Dockerfile` + `scripts/ai-engine/check-ffmpeg-codecs.sh`（新增） | 0.5 PD | DevOps |
| FR-2 | `TARGET_FPS = 60` + 60fps 时间轴帧映射 | `preprocess.py::_ffmpeg_normalize_v2` | 1 PD | AI 工程 |
| FR-3 | zscale filter chain + HDR 探针 | `preprocess.py::_ffmpeg_normalize_v2` + `_ffprobe_extended`（读 color_primaries / transfer） | 1.5 PD | AI 工程 |
| FR-4 | mov / mp4 慢动作元数据读取 + 真实时长校正 | `preprocess.py::_ffprobe_extended` + `_normalize_to_real_timeline` | 2 PD | AI 工程 |
| FR-5 | 短边分层（依赖 §6 推荐机型矩阵） | `preprocess.py::TARGET_SHORT_SIDE_BY_TIER` 表 | 0.5 PD | AI 工程 |
| FR-6 | 音轨保留（仅 normalized.mp4 内部） | `_ffmpeg_normalize_v2` 去掉 `-an`，加 `-c:a aac -b:a 64k` | 0.5 PD | AI 工程 |
| engine_warnings[] | collector + JSONB schema | `preprocess.py::_collect_engine_warnings` + 写库（`real_pipeline.py`） | 1.5 PD | AI 工程 |
| 错误码 50120 | `errors.py` 新增 `DecodeError` + 中文文案 | `ai_engine/app/errors.py` | 0.5 PD | AI 工程 |
| 单测 + 回归脚本 | `tests/test_video_reader_v2.py` | `ai_engine/tests/` | 2 PD | AI 工程 + 测试 |

**合计：~10 PD**（与 docs/23 §3.2 估时 8 PW 内嵌测试人力一致，剩余 1-2 PD 留 buffer + 真机回归 review）

### 3.1 `50101` vs `50120` 拆分（W15 编码前必须对齐）

一期 `PreprocessError` 已占用 **50101**，ffmpeg 解码失败与 curl 下载失败**共用**此码。P2-M7-02 须按场景拆分，避免 AC-3 与现有行为冲突：

| 场景 | 错误码 | 异常类 | 用户文案（草案） |
| --- | --- | --- | --- |
| curl 下载失败 / 超时 | 50101 | `PreprocessError`（保持） | 「视频下载失败，请检查网络后重试」 |
| 容器损坏 / ffprobe 无法读 | 50101 | `PreprocessError`（保持） | 「视频处理失败，请重新上传」 |
| codec 不支持 / HEVC·HDR·VP9 转码失败 | **50120** | `DecodeError`（新增） | 「视频格式暂不支持」 |

**连带改动**（W17 前完成）：

- `backend/app/tasks/analysis_tasks.py`：退配额段从 `50101-50105` 扩到含 `50120`（与 docs/23 §11.4 50120-50123 段一致）
- `client/src/constants/analysisEngineErrors.ts`：**50120 映射归 P2-M7-03**（M7-02 只负责 engine 侧抛码；AC-3 客户端文案由 M7-03 收口）

---

## 四、`engine_warnings[]` 字段 v0.1 草案

> **位置**：本字段 v0.1 草案**先在本文件落定**，避免阻塞 W14 编码起跑。W17 PR 合入时，由 P2-M7-02 owner 一次性回流到 `docs/02 §11.1` + `docs/03 §8.1`，本节届时改为 forward 引用并打 `superseded` 标记。

### 4.1 Schema（JSONB 数组，每项一个对象）

```jsonc
{
  "engine_warnings": [
    {
      "code": "decode_codec_fallback",        // 必填，snake_case，全局唯一
      "level": "info",                          // 必填：info | warn | fatal
      "detail": {                               // 选填，code-specific 上下文
        "from_codec": "hevc",
        "to_codec": "h264",
        "duration_ms": 1280
      },
      "ts": "2026-05-25T10:30:15Z"             // 必填，warning 生成时间（UTC ISO 8601）
    }
  ]
}
```

### 4.2 v0.1 码表（W14-W17 内固化）

| code | level | 触发条件 | 用途 |
| --- | --- | --- | --- |
| `decode_codec_fallback` | info | HEVC / VP9 容器走 ffmpeg 软解（vs 硬解） | 性能监控；不告警用户 |
| `fps_normalized_from_240` | info | mov `nominal_fps` ∈ {120, 240} 且按真实时间轴折算 | 报告页可选展示「检测到慢动作」 |
| `fps_normalized_from_24` | info | 24fps 电影模式归一化到 60fps（dup-frame） | 同上 |
| `hdr_to_sdr_converted` | info | `color_primaries=bt2020` 且通过 zscale 转 bt709 | 报告页可选展示「检测到 HDR」 |
| `frame_rate_rounded` | info | 非整数 fps（如 29.97）四舍五入到 60fps 时间轴 | 调试用 |
| `audio_track_present` | info | 音轨存在且已保留（供 M8 教练批注） | M8 上线后用 |
| `decode_failed` | fatal | ffmpeg / ffprobe 退码 ≠ 0 且非超时 | **触发 50120 错误码**，pipeline 中止 |

> **不在本表的 code 一律不允许写入** —— W17 PR 合入 docs/02 §11.1 时由 PM/AI Lead 守门。

### 4.3 数据库写入策略

- 字段位置：`swing_analyses.engine_warnings` JSONB 列（详 docs/03 §8.1 拟）
- 默认值：`[]`（V1 行为兼容；V1 引擎写入空数组）
- 大小约束：单条 analysis 内 `engine_warnings` ≤ 32 项；超出截断并记 Sentry
- 不索引（查询走 `analysis_id` 主键），但需在 `GET /v1/analyses/{id}` 响应中**全量返回**

### 4.4 与 `quality_warnings` 的关系

V2 阶段 **两套字段并存、不合并**：

| 字段 | 类型 | 语义 | 一期行为 |
| --- | --- | --- | --- |
| `quality_warnings` | `list[str]` | 画质/姿态软提示（`low_light`, `camera_shake` 等） | **保持不变** |
| `engine_warnings` | `list[{code, level, detail, ts}]` | 解码/归一化/codec 降级 | V1 写 `[]` |

客户端已映射 `quality_warnings` → 报告页提示；`engine_warnings` 首版仅落库 + API 返回，UI 展示留 Phase 2.1 迭代。

---

## 五、Dockerfile 升级

### 5.1 ffmpeg 能力探针脚本（W14 首日跑）

```bash
# scripts/ai-engine/check-ffmpeg-codecs.sh
#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-ai_engine:dev}"

echo "=== ffmpeg version ==="
docker run --rm "$IMAGE" ffmpeg -version | head -3

echo ""
echo "=== HEVC / H.265 decoder ==="
docker run --rm "$IMAGE" ffmpeg -codecs 2>/dev/null | grep -E "hevc|h265" | head -5

echo ""
echo "=== VP9 decoder ==="
docker run --rm "$IMAGE" ffmpeg -codecs 2>/dev/null | grep -E "vp9" | head -3

echo ""
echo "=== zscale filter (libzimg) ==="
docker run --rm "$IMAGE" ffmpeg -filters 2>/dev/null | grep -E "zscale|tonemap" | head -5

echo ""
echo "=== tonemap filter ==="
docker run --rm "$IMAGE" ffmpeg -filters 2>/dev/null | grep -E "^.+tonemap" | head -3
```

期望输出（Debian bookworm 默认 build 应已满足）：

```
hevc                  Codec (decoders: hevc)
vp9                   Codec (decoders: vp9 libvpx-vp9)
zscale                V->V       Apply Zscale on the input video.
tonemap               V->V       Conversion to/from different dynamic ranges.
```

### 5.2 缺失补齐方案

| 探针结果 | 处置 |
| --- | --- |
| 全部命中 | 无需改 Dockerfile；只需在 README 加固"已验证 codec 矩阵"段 |
| 缺 libzimg / zscale | `apt-get install libzimg2 libzimg-dev`，镜像 ~+15MB |
| 缺 libvpx | `apt-get install libvpx7`，~+5MB |
| 全部缺（极小概率） | 切换 base image 到 `linuxserver/ffmpeg` 或 jellyfin static build，镜像 +180-200MB，**逼近 NFR 上限**，需 PM 复核 |

### 5.3 镜像膨胀控制（NFR 对齐）

- NFR 上限：**≤ +200MB**
- 监控点：W14 探针后基线 → W17 完工后对比，记录到本文件 §10 变更记录
- 兜底：如膨胀超限，先回退到 `apt` 单包补齐（libzimg2 ~15MB），暂缓 VP9（VP9 在国内挥杆视频生态占比 < 5%，可推迟到 v2.1）

---

## 六、测试视频集（fixtures v2 扩充）

> **与 P2-M7-01 ECS v2 关系**：
> - ECS v2（80+ 段）用途 = 算法**标定**（PHASE_WEIGHTS / ideal 范围 / 双盲打分）
> - 本节 fixtures（≥30 段）用途 = 解码**回归**（codec / HDR / 慢动作格式覆盖 + 推荐机型矩阵）
> - **两套视频集不重叠**：ECS v2 必须是真挥杆 + 教练打分；fixtures v2 可以是非完整挥杆（重点是格式覆盖，比如纯 HDR 风景 5s 也能验证 zscale）

### 6.1 fixtures v2 矩阵

| 类别 | 数量 | 设备 | 命名规范 | 用途 |
| --- | --- | --- | --- | --- |
| HEVC（H.265） | ≥5 | iPhone 15 / 14 默认 | `real/v2/hevc_iphone15_<club>_<idx>.mov` | FR-1 |
| HEVC 10-bit HDR | ≥5 | iPhone 15 Pro HDR / 华为 Mate 60 HDR | `real/v2/hdr_<device>_<club>_<idx>.mov` | FR-1 + FR-3 |
| VP9 | ≥3 | YouTube 1080p 60fps `.webm`（教练公开内容） | `real/v2/vp9_yt_<club>_<idx>.webm` | FR-1 |
| 240fps 慢动作 | ≥5 | iPhone 慢动作模式 / Samsung Super Slow-mo | `real/v2/slowmo240_<device>_<club>_<idx>.mov` | FR-2 + FR-4 |
| 120fps 高帧率 | ≥3 | 安卓 120fps（OnePlus / Pixel） | `real/v2/highfps120_<device>_<club>_<idx>.mp4` | FR-2 |
| 24fps 电影模式 | ≥3 | iPhone 电影模式（默认 24fps） | `real/v2/cinematic24_<device>_<club>_<idx>.mov` | FR-2（低帧率 dup-frame 验证） |
| 推荐机型矩阵 | ≥6 | iPhone 15 / 华为 Mate 60 / 小米 / 三星等（docs/05 §2.2 拓展） | `real/v2/device_matrix_<device>_<idx>.mov` | AC-1 |

**总计 ≥30 段**（codec 类 ≥24 + 机型矩阵 ≥6）；与 ECS v2 不可重用。AC-1 真机回归直接遍历 `real/v2/device_matrix_*` + 上述 6 类样本。

### 6.2 采集来源（合规）

| 路径 | 适用 | 备注 |
| --- | --- | --- |
| 内部自录 | 全部类别 | 优先；员工挥杆 + 教练助理协作，签内部数据使用同意书（同 P2-M7-01 kickoff §六 数据安全与法务模板） |
| GolfDB 公开数据集 | 暂无 HEVC / HDR 样本 | GolfDB 全部为 160×160 H.264，**不**满足 v2 fixtures 需求 |
| YouTube 教练公开内容 | VP9 / 电影模式 | 仅做**本地测试**，**不**入库（与 v1 fixtures 同策略） |
| 用户上传样本 | ❌ 禁用 | 用户视频不可挪作 fixtures，合规线 |

### 6.3 fixtures README v2 增量（W14 内 PR）

在 `ai_engine/tests/fixtures/README.md` 末尾追加：

```markdown
## v2 视频读取增强 fixtures（P2-M7-02 起）

`fixtures/real/v2/` 在 v1（GolfDB face_on / dtl 各 1 段，仍放 `real/` 根目录）基础上扩充 7 类：
- hevc_*  HEVC / H.265 容器
- hdr_*   10-bit HDR（bt2020）
- vp9_*   VP9 编解码
- slowmo240_*  240fps 慢动作
- highfps120_* 120fps 高帧率
- cinematic24_* 24fps 电影模式
- device_matrix_*  推荐机型矩阵（AC-1）

采集来源：员工自录（优先） / GolfDB / 教练公开内容（仅本地）
**所有视频不入库**；运行 `bash download_samples.sh v2-manifest` 查看当前清单
```

---

## 七、单测 / 回归脚本规划

### 7.1 单测（新增 `tests/test_video_reader_v2.py`）

```python
# 用例骨架（W16 实现）
@pytest.mark.needs_fixture
def test_hevc_decode_emits_codec_fallback_warning(hevc_sample):
    result = preprocess_video_v2(hevc_sample, ...)
    assert any(w["code"] == "decode_codec_fallback" for w in result.engine_warnings)
    assert result.normalized_video_path.exists()

@pytest.mark.needs_fixture
def test_slowmo_240fps_real_timeline_recovery(slowmo240_sample):
    result = preprocess_video_v2(slowmo240_sample, ...)
    source_real_duration = 1.0  # 240fps × 1s 慢动作 = 1s 真实时间
    assert abs(result.duration_sec - source_real_duration) < 0.2
    assert any(w["code"] == "fps_normalized_from_240" for w in result.engine_warnings)

@pytest.mark.needs_fixture
def test_hdr_to_sdr_conversion(hdr_sample):
    result = preprocess_video_v2(hdr_sample, ...)
    primaries = _ffprobe_color(result.normalized_video_path).color_primaries
    assert primaries in ("bt709", "smpte170m")
    assert any(w["code"] == "hdr_to_sdr_converted" for w in result.engine_warnings)

def test_corrupted_video_triggers_50120():
    with pytest.raises(DecodeError) as exc_info:
        preprocess_video_v2(CORRUPTED_VIDEO_PATH, ...)
    assert exc_info.value.code == 50120

def test_v1_behaviour_frozen():
    """V1 pipeline 必须与 V2 共存，灰度回滚兜底"""
    result_v1 = preprocess_video(LEGACY_GOLFDB_SAMPLE, ...)
    assert result_v1.fps == 30  # V1 行为不变
```

### 7.2 回归脚本（W17 真机回归）

`scripts/ai-engine/regression-v2.py`：
1. 遍历 `fixtures/real/v2/` 下所有视频
2. 跑 `preprocess_video_v2`
3. 输出 markdown 矩阵：`视频 | 解码成功 | engine_warnings | duration_sec | normalized 体积`
4. AC 自动判定：
   - HEVC ≥5 段全通过 → ✅ AC-2
   - 10-bit HDR ≥5 段全通过 → ✅ AC-2
   - 240fps ≥5 段全通过 → ✅ AC-2
   - 推荐机型矩阵 ≥30 段通过率 ≥95% → ✅ AC-1

### 7.3 CI 策略

- **不**跑 v2 fixtures（视频不入库，CI 容器无样本）
- 新增 `make ai-engine-test-v2` target，本地 + 真机回归专用
- v1 `make ai-engine-test` 继续跑（V1 行为冻结，回归保护）

---

## 八、W14-W17 周计划

| 周 | 周一-周三 | 周四-周五 | DoD（Definition of Done） |
| --- | --- | --- | --- |
| **W14** | 本文件评审 + DevOps 跑 §5.1 ffmpeg 探针；AI 工程读完 preprocess.py 全 660 行 | 起 `ai_engine/tests/fixtures/README.md` v2 增量 PR；AI 工程出 `_ffprobe_extended` PoC（HEVC metadata 读取） | ☑ 探针结果入本文件 §10；☑ fixtures README v2 PR 已开 |
| **W15** | fixtures 采集首批：员工自录 HEVC ≥3 + 240fps ≥3；AI 工程实现 `_ffmpeg_normalize_v2` HEVC/zscale 链 | DevOps 验证 Dockerfile 探针，记镜像膨胀基线；AI 工程实现 `engine_warnings` collector | ☑ 首批 6 段 fixtures 落到本地 `real/v2/`；☑ HEVC sample 端到端跑通；☑ Dockerfile 膨胀报告入 §10 |
| **W16** | AI 工程实现 `_normalize_to_real_timeline`（FR-4） + 单测 5 个用例；fixtures 第二批：HDR ≥3 + VP9 ≥3 | 内部 dogfood：员工拍 5 段 iPhone 15 真挥杆，全链路验证 | ☑ 5 个新单测全绿；☑ HDR sample 转 sRGB 验证通过；☑ dogfood 100% 通过率 |
| **W17** | 真机回归（`real/v2/` 全量 ≥30 段，含 `device_matrix_*` ≥6）；新增 50120 错误码 PR（§3.1 拆分规则）+ `ai-engine:v2.0-ffmpeg` 镜像 tag | engine_warnings collector 回流 `docs/03 §8.1` + `docs/02 §11.1` PR；本文件改 `superseded` 标记 | ☑ AC-1/2/3 全部达成（§3.2 验收口径）；☑ 文档回流 PR 合入；☑ Phase 2.1 接力书签可挂 |

---

## 九、责任 / 风险 / 验收

### 9.1 责任

| 角色 | 责任 |
| --- | --- |
| AI 工程 Lead | 总 owner；preprocess.py V2 改造、单测、engine_warnings collector、文档回流 |
| DevOps | Dockerfile 升级、ffmpeg 探针、镜像膨胀监控 |
| 测试工程 | fixtures v2 采集（与 AI 工程协同）、W17 真机回归脚本、AC 自动判定 |
| PM | 周会跟踪 W14-W17 4 个 DoD；W17 文档回流 PR 守门 |

### 9.2 风险（3 项 + 兜底）

| ID | 风险 | 概率 | 影响 | 兜底 |
| --- | --- | --- | --- | --- |
| R-01 | Debian ffmpeg 缺关键 codec（libzimg / libvpx） | 低 | 镜像膨胀超 NFR 200MB | 先单包补齐，VP9 推迟到 v2.1（国内挥杆视频 VP9 占比 < 5%） |
| R-02 | 真机 HEVC / HDR 样本多样性不足（仅 iPhone 15 系列覆盖） | 中 | 推荐机型矩阵代表性不足 | W14-W15 主动联系 5-8 名内部员工跨机型自录；W17 矩阵中明示「华为/小米 HDR 待 v2.1 扩」 |
| R-03 | TARGET_FPS 30→60 打破 V1 行为，灰度需 `engine_version` 兼容 | 高 | V1 报告与 V2 报告同环境共存时分数对比失真 | 双轨灰度：① `engine_version` 字段（P2-M7-14）；② Docker 镜像 tag `ai-engine:v2.0-ffmpeg`（docs/23 §3.2 灰度/回滚），回滚可只切镜像不动代码 |

### 9.3 AC 兜底（复述 docs/23 §3.2，不重新发明）

- [ ] **AC-1**：推荐机型矩阵 ≥30 段真机回归通过率 ≥95%
- [ ] **AC-2**：HEVC / 10-bit HDR / 240fps 各至少 5 段 sample 通过完整 pipeline
- [ ] **AC-3**：解码失败时返回 `50120` 错误码，客户端展示中文文案"视频格式暂不支持"

---

## 十、附录

### 10.1 W14 探针运行记录（待填）

| 探针项 | 期望 | 实际 | 行动 |
| --- | --- | --- | --- |
| HEVC decoder | ✅ | 待填 | 缺失则 §5.2 补齐 |
| VP9 decoder | ✅ | 待填 | 缺失则 §5.2 补齐 |
| zscale filter | ✅ | 待填 | 缺失则 `apt install libzimg2` |
| tonemap filter | ✅ | 待填 | 一般随 zscale 一起 |
| 当前镜像大小（GB） | 基线 | 待填 | 用于 §5.3 膨胀比对 |
| Dockerfile 改后镜像大小（GB） | 基线 + ≤0.2GB | 待填 | 超限触发 R-01 兜底 |

### 10.2 ECS v2 vs fixtures v2 用途对照表

| 维度 | ECS v2（P2-M7-01） | fixtures v2（P2-M7-02 本文件） |
| --- | --- | --- |
| 用途 | 算法**标定**（PHASE_WEIGHTS / ideal 范围 / 双盲打分） | 解码**回归**（codec / HDR / 慢动作格式覆盖） |
| 数量 | ≥80 段 | ≥30 段（codec ≥24 + 机型矩阵 ≥6） |
| 内容要求 | 真挥杆 + 4 球杆类别 + 双盲打分 | **不需要**真挥杆；HDR 风景 5s 也合规 |
| 法务 | 内部自录 / 教练授权（合规等级高） | 同 P2-M7-01 模板 |
| 入库 | 否（MinIO + 标定 JSONL） | 否（fixtures/real/v2/ 本地） |
| Owner | 数据 + BD | AI 工程 + 测试 |
| Phase | W14-W17 持续采集 → Phase 2.1 持续扩 | W14-W17 一次性采足 ≥30 段，后续按需扩 |

### 10.3 v1 行为兼容矩阵（灰度参考）

| 行为 | V1 | V2 | 兼容策略 |
| --- | --- | --- | --- |
| 输出 fps | 30 | 60 | 强依赖 `engine_version` 字段；V1 与 V2 报告**不可直接比较**分数 |
| 输出 codec | H.264 yuv420p | H.264 yuv420p | 不变 |
| 短边 | 720 | 720（旗舰机 1080，W17 切换） | V2 输出可后向兼容 V1 后续 pipeline |
| 音轨 | 丢（-an） | 保留（aac 64k 内嵌） | normalized.mp4 体积 +5-10%；不上传到对象存储 |
| `engine_warnings[]` | `[]` | 可能多条 | V1 引擎也写 `[]`，前向兼容 |
| 错误码 | 50101-50105 | 新增 50120 | V1 不会产生 50120，前向兼容 |

---

## 十一、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版，W14 起跑前置 SOP |
| v0.1.1 | 2026-05-25 | review 修复 6 处：§1.2 任务号/fps 表述；§2.4 FR-5 联动对象；§3.1 50101/50120 拆分表；§4.4 quality_warnings 并存；§6 fixtures 路径统一为 `real/v2/` + 增 device_matrix 类（≥30 段对齐 AC-1）；§6.2 M7-01 章节引用；R-03 补 Docker 镜像 tag |
| v0.1 后续 | W14 内 | 补 §10.1 探针运行记录 |
| v0.2 | W17 收尾 | 镜像膨胀实测、AC 达成情况、`engine_warnings` v0.1 草案回流至 docs/02 §11.1 后改 `superseded` 标记 |
