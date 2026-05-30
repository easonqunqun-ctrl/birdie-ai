# 职业镜头候选 manifest（pro_clip_score_rank.py）

## 合规（必读）

- **大师赛 / Augusta / PGA Tour 转播** 为商业版权内容，**不能**抓进产品库或体验版，即使用于内测也须单独授权。
- 本目录默认只放 **CC / 自有 sample / 书面授权** 条目；入库前产品+法务确认 `license_status` 与 `source_credit`。
- 引擎高分 ≠ 巡回赛水平；慢动作教学片也可能因机位/节奏被低估。

## 扩展 manifest

复制 `pro_clip_candidates.csv`，追加列：

| 列 | 说明 |
|----|------|
| candidate_id | 唯一 ID |
| player_name | 展示名（勿冒充未授权球星） |
| video_url | ai_engine 可访问的 https URL |
| video_path | 可选；配合 `--serve-local` 本地目录相对路径 |
| club_type | 如 iron_7 |
| camera_angle | face_on / down_the_line |
| source_credit | 必填，版权归属 |
| source_url | 必填，溯源页 |
| license_status | public_clip / authorized / partnership |
| notes | 备注 |

## 跑分

```bash
cd ai_engine
uv run python scripts/pro_clip_score_rank.py \
  --engine-url http://localhost:9100 \
  --input-csv scripts/data/pro_clip_candidates.csv
```

外站 URL 须 ai_engine 容器能访问（CVM 上可对已上传 MinIO 的 clip 跑）。

## 替换 Demo Pro 占位

```bash
cd backend
uv run python ../tools/scripts/apply_pro_clip_winner.py \
  --rank-csv ../ai_engine/reports/pro_clip_rank.csv --dry-run
```

Wikimedia 等外站 URL **不能**直接作 pro_clip `video_url`（域名白名单）；须先上传到 `api.birdieai.cn/minio/...` 再 `--video-url`。
