# V1 / V2 引擎一致性 diff · 真实流量校准 runbook（P2-W14-C）

> 关联：W6 ENG-A3（diff 脚本）/ W13-D（告警阈值校准）

## 0 · 现状（2026-05-29 体检）

| 项 | 实际 | 备注 |
|---|---|---|
| `swing_analyses` 表总量 | 95（89 completed + 6 failed） | CVM staging |
| `video_url` 含**真实** MinIO 路径 | **0** | 全部是 `https://x/v.mp4` dummy 占位 |
| `ai_engine` sample fixture URL 可达 | ❌ | `xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4` → "视频下载失败 50101" |
| 真实用户视频上传记录 | **0** | 即使开 100% V2，也没真流量喂进去 |

**结论**：W14-C 当前无法跑出有意义的 diff 数字。原因是 staging 还没接真实用户；89 条数据全是开发期 sample fixture，video_url 字段被 dummy 化。本文档作为**触发条件清晰的 runbook**，等 W18+ 真实用户接入后立即可用。

## 1 · 跑 diff 的触发条件

| 节点 | 触发 | 必须先做 |
|---|---|---|
| **触发 1** | CVM 出现 ≥ 20 条 `video_url` 含 `https://api.birdieai.cn/minio/xiaoniao-videos/uploads/` 前缀的真实 completed 报告 | 体验版上线 + 至少 3 个非 PM 用户上传 |
| **触发 2** | W13-D `AiEngineEnrichFallbackTrend` 告警 fire | 立即跑 diff 验证 V2 enrichment 漏覆盖范围 |
| **触发 3** | V2 灰度从 100% 临时降到 50%/0% 排障前 | 留下 diff 报告作为回滚证据 |
| **触发 4** | 每月 30 号定期跑（W18 之后） | 趋势观察 + 阈值 drift 检测 |

## 2 · 跑 diff 的标准操作（5 步）

### 2.1 在 CVM 拉真实 video_url

```bash
ssh -i ~/.ssh/id_ed25519_birdie_golf ubuntu@1.13.198.172

# CVM 上：拉最近 20 条真实 completed 报告（过滤 dummy URL）
docker exec xiaoniao-postgres psql -U xiaoniao -d xiaoniao -t -A -F"," -c "
SELECT id, video_url
FROM swing_analyses
WHERE status='completed'
  AND video_url IS NOT NULL
  AND video_url LIKE 'https://api.birdieai.cn/minio/%'
ORDER BY created_at DESC
LIMIT 20;" > /tmp/samples_raw.csv

echo "analysis_id,video_url" > /tmp/samples.csv
cat /tmp/samples_raw.csv >> /tmp/samples.csv

# 拷进 ai_engine 容器
docker cp /tmp/samples.csv xiaoniao-ai-engine:/tmp/samples.csv
```

### 2.2 容器内跑 diff（强制走内网 URL 享受 W13-C 0 跳）

```bash
docker exec xiaoniao-ai-engine /app/.venv/bin/python /app/scripts/v1_v2_diff.py \
    --engine-url http://localhost:9000 \
    --input-csv /tmp/samples.csv \
    --out-csv /tmp/v1_v2_diff_$(date +%Y%m%d).csv \
    --report-md /tmp/v1_v2_diff_$(date +%Y%m%d).md
```

注意：脚本会对**同一个 video_url** 分别调一次 `/analyze` v1 + v2，相当于 40 次推理。
单次 ~20s × 40 ≈ **13 分钟**（CVM 单 worker）；高负载窗口避开。

### 2.3 拉报告本机

```bash
docker cp xiaoniao-ai-engine:/tmp/v1_v2_diff_$(date +%Y%m%d).md - \
    | ssh -i ~/.ssh/id_ed25519_birdie_golf ubuntu@1.13.198.172 cat - \
    > ~/v1_v2_diff.md

# 或：
docker exec xiaoniao-ai-engine cat /tmp/v1_v2_diff_*.md
```

### 2.4 看 4 个关键指标

| 指标 | 期望 | 不达标行动 |
|---|---|---|
| `score_exact_match_rate` | **100%** | 评分链路改动了；查 `ai_engine/app/scoring/` recent commits |
| `issue_types_exact_match_rate` | ≥ 70% | < 70%：V2 enrichment YAML 漏覆盖大；跑 W14-D `probe` 模块化后看 fallback bucket |
| `issue_types_jaccard_p50` | ≥ 0.85 | < 0.85：阈值精度问题；查 `v2_starter.yaml` thresholds |
| `issue_types_jaccard_p10` | ≥ 0.5 | < 0.5：最差 10% 样本 V1/V2 几乎不一致；列出 `v1_only_top` / `v2_only_top` 排序逐条对 |

### 2.5 把报告写进本目录归档

```bash
# 本机
mv ~/v1_v2_diff.md docs/release-notes/v1-v2-diff-real-traffic-$(date +%Y%m%d).md
git add docs/release-notes/v1-v2-diff-real-traffic-*.md
git commit -m "docs(w14-c): 真实流量 V1/V2 diff $(date +%Y%m%d) baseline"
```

## 3 · 跑完后的阈值校准（接 W13-D 告警）

跑完拿到 baseline 后回 `infra/monitoring/prometheus-alerts.yml`，校准两条告警：

### 3.1 `AiEngineEnrichFallbackTrend`

```yaml
# 当前阈值（W13-D 初版，凭直觉）
expr: rate(ai_engine_v2_enrich_fallback_count[1h]) > 0.5
```

如果 baseline `1 - issue_types_exact_match_rate` 长期稳定在 **X%**，
合理阈值应是 `X% × 平均流量 (req/s)`。例如 staging 平均 0.1 req/s，X=20%：
阈值应改为 `> 0.02`。**别用直觉拍**——用真数据。

### 3.2 `AiEngineV2ErrorRateHigh`

```yaml
expr: ai_engine_v2_error_rate > 0.1
```

W14-C 跑完后看 V2 客户端错误率，应**永远** < 1%（V2 fallback 走 V1 不算 error）。
如果 baseline > 5%，10% 阈值就是漏报。降到 5%。

## 4 · 已知风险与 backlog

### 4.1 sample fixture URL 死掉
- 现状：`SAMPLE_VIDEO_URL=https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4` 已 404
- 影响：任何"无真实流量时的烟测"都跑不通
- 建议（W15+）：
  - 把 sample 视频上传到当前 MinIO `xiaoniao-videos/samples/`
  - `SAMPLE_VIDEO_URL` 默认 `http://minio:9000/xiaoniao-videos/samples/swing_demo.mp4`（容器内）或 `https://api.birdieai.cn/minio/xiaoniao-videos/samples/swing_demo.mp4`（公网，给客户端"试用"）
  - 顺便和 W13-C `_rewrite_to_internal_url` 兼容

### 4.2 数据库 89 条 video_url 全是 dummy
- 原因：开发期 sample_fixture 直接写库占位
- 影响：DB 查询"统计真实用户行为"全是噪声
- 建议（W15+）：加 `swing_analyses.is_sample bool` 字段或 `analyzed_at` 区分 dev / 真实

### 4.3 跑完 diff 报告没 archive 流程
- 现状：脚本输出到 `/tmp/`，容器重启就丢
- 建议（W15+）：
  - 加 `scripts/v1_v2_diff_archive.sh`：跑完自动 `docker cp` 到宿主 `/var/log/xiaoniao/diff/`
  - 接 `prometheus pushgateway` 把 `score_exact_match_rate` 等指标 push 进去做趋势

## 5 · 现在做了的事

- ✅ 验证 `v1_v2_diff.py` 脚本本身在 CVM 容器内**可执行**（哪怕 sample URL 死掉也只是 `client_error`，不崩 + 报告正常输出）
- ✅ 形成**触发条件清晰**的 runbook（4 个 trigger 都能机械执行）
- ✅ 把 W13-D 两条阈值告警的校准入口指清楚（不让"凭直觉拍阈值"成为 review 阻力）
- ❌ **没**强行跑出 baseline 数字——staging 0 真实流量时**任何"对 89 条 dummy 跑出来的 diff 数字"都是噪声**，写进文档反而误导后续阈值校准
