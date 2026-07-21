# P2-M7-R1-B7 · preprocess_v2 灰度 Staging Runbook

> **前置**：`preprocess_router.py` 已上线（默认 **off**）；V2 分析桶已开（CVM `M7_V2_ROLLOUT_PCT=100`）。  
> **本 runbook**：在 **staging** 打开 `M7_VIDEO_READER_V2_ENABLED` 前的检查、开启、验收、回滚。  
> **关联**：[`p2-m7-r1-rotation-perception-accuracy-kickoff.md`](./p2-m7-r1-rotation-perception-accuracy-kickoff.md) · [`v2-rollout-runbook.md`](./v2-rollout-runbook.md)

---

## 1. 行为说明

| 开关 | 路径 | preprocess |
|------|------|------------|
| `M7_VIDEO_READER_V2_ENABLED=false`（默认） | V2 桶 analyze | V1 · 30fps |
| `M7_VIDEO_READER_V2_ENABLED=true` | V2 桶 analyze | V2 · 60fps / HEVC / 慢动作 |
| 任意 | V1 桶 · detect-swings | **始终 V1**（与 params 机位预选一致） |

日志字段：`preprocess_done` · `preprocess_reader=v1|v2`；V2 预处理 `engine_warnings` 写入报告。

---

## 2. 开启前门禁（必须全绿）

```bash
# 本地 / CI
make ai-engine-test-rotation

# AC-B7：真视频 V1 vs V2 阶段时刻 Δt ≤ 0.25s（缺 fixture 则 skip）
cd ai_engine && uv run pytest tests/test_preprocess_v2_timing_regression.py -v
```

**真视频**：在 `ai_engine/tests/fixtures/real/` 放置 `face_on_iron_01.mp4` 后，上式应 **PASSED**（非 skip）。

**小程序**：体验版 ≥ **1.2.30**（capture 2.3s 门禁 + params detect-swings 失败提示），见 [`experience-version-smoke-runbook.md`](./experience-version-smoke-runbook.md)。

---

## 3. Staging 开启步骤（CVM）

### 3.1 写入 env（不提交仓库）

在 CVM `~/secrets/lingniao-prod.env`（或当前 `ENV_FILE`）追加：

```bash
# P2-M7-R1-B7 · preprocess_v2（仅 V2 analyze 路径）
M7_VIDEO_READER_V2_ENABLED=true
```

`detect-swings` **不受**此 flag 影响；无需改客户端。

### 3.2 发版

```bash
DEPLOY_HOST=ubuntu@1.13.198.172 ENV_FILE=~/secrets/lingniao-prod.env make ship-cvm
```

### 3.3 验收（引擎）

```bash
ssh ubuntu@1.13.198.172 'docker logs xiaoniao-ai-engine --since=10m 2>&1 | grep -E "preprocess_v2_enabled|preprocess_reader=v2" | tail -5'
```

提交一次 **V2 桶** full_swing 分析，日志应出现：

- `preprocess_v2_enabled`
- `preprocess_done` · `preprocess_reader=v2`

### 3.4 验收（产品 · 建议勾）

- [ ] face-on 7 铁：报告正常出分，无新增 50101/50105 尖刺  
- [ ] 慢动作 / HEVC 样本（若有）：能完成分析或给出 50120 明确失败  
- [ ] 阶段时间戳（top/impact）与开 flag 前同视频对比，肉眼无「整段错位」  
- [ ] `engine_warnings` 含 `slowmo_detected` / `nominal_fps_used` 时文案可读  

---

## 4. 回滚（≤ 2 分钟）

**仅关 flag，无需 revert 代码**：

```bash
# CVM env
M7_VIDEO_READER_V2_ENABLED=false

make ship-cvm   # 或 docker compose up -d --force-recreate ai_engine
```

验证：`preprocess_reader=v1` 恢复。

---

## 5. 监控与告警

| 信号 | 动作 |
|------|------|
| `50101` / `50120` 10min 内较基线 +50% | 先关 flag，查 ai_engine 日志 `detect_swings_failed` / `PreprocessError` |
| `v2_enrich_fallback_count` 升高 | 与 V2 路由无关时查 YAML；与 preprocess 无关 |
| 分析 latency P95 +30% | 60fps 预期略涨；若翻倍查 ffmpeg 转码日志 |

---

## 6. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-31 | v0.1 首版；B7 router + AC-B7 timing gate 已 repo |
