# V2 引擎灰度上调 Runbook（W24-A · P2-V2-ROLLOUT）

> **位置**：`docs/release-notes/v2-rollout-runbook.md`  
> **配套**：`ai_engine/app/version_router.py` · `POST /admin/engine-rollout` · `scripts/set_v2_rollout_pct.sh`  
> **监控**：[`monitoring-runbook.md`](./monitoring-runbook.md) §3 D1/D3/D7

---

## 1. 当前策略（2026-05）

| 阶段 | `M7_V2_ROLLOUT_PCT` | 观察窗口 | 晋级条件 |
|------|---------------------|----------|----------|
| **R0** | 5（已上线） | 7d | `v2_probe_error_rate` < 1% · 无 5xx_after_retries · 无 P0 告警 |
| **R1** | **25** | 7d | 同上 + `v2_traffic_ratio` 与 pct 偏差 < 10% |
| **R2** | **50** | 7d | 同上 + `v2_enrich_fallback_count/v2_count` < 5% |
| **R3** | 100 | — | 真实流量 diff 通过（见 [`v1-v2-diff-real-traffic.md`](./v1-v2-diff-real-traffic.md)） |

**短杆 mode**（putting/chipping）不走 V1/V2 分桶，灰度仅影响 **full_swing** 路径。

---

## 2. 配置来源（优先级）

1. **Redis** `m7:v2:rollout_pct`（admin API 写入，60s 进程缓存）
2. **环境变量** `M7_V2_ROLLOUT_PCT`（`.env.local` → ai_engine 容器 `env_file`）
3. 默认 `0`（全 V1）

生产推荐：**admin API 调 pct**（即时生效）+ `.env.local` 写同值作重启兜底。

---

## 3. 操作步骤

### 3.1 查看当前灰度

```bash
# CVM 上
bash scripts/v2_rollout_status.sh

# 本机经 SSH
DEPLOY_HOST=ubuntu@1.13.198.172 bash scripts/v2_rollout_status.sh
```

期望 JSON 含 `"rollout_pct": 5`（或当前档位）。

### 3.2 上调（例：5 → 25）

**前置**：`AI_ENGINE_ADMIN_TOKEN` 已写入 CVM `.env.local`（与 ai_engine 容器一致）。

```bash
# CVM 仓库根目录
cd ~/lingniao-golf
PCT=25 bash scripts/set_v2_rollout_pct.sh

# 或本机
DEPLOY_HOST=ubuntu@1.13.198.172 PCT=25 bash scripts/set_v2_rollout_pct.sh
```

同步把 `.env.local` 里的 `M7_V2_ROLLOUT_PCT=25` 改掉（容器重建时不回退）。

### 3.3 降级 / 回滚

降级需显式确认（防误触）：

```bash
PCT=5 FORCE=1 bash scripts/set_v2_rollout_pct.sh
```

紧急全量回 V1：`PCT=0 FORCE=1 ...`

### 3.4 7 天观察（每档晋级前必做）

SSH 端口转发后打开 Prometheus `http://localhost:9090/graph`：

| PromQL | 期望 |
|--------|------|
| `rate(v2_probe_errors_total[1h]) / rate(v2_probe_total[1h])` | < 0.01 |
| `v2_probe_errors_5xx_after_retries` | 0 |
| `v2_count / (v1_count + v2_count)` | ≈ `rollout_pct/100` ±10% |
| `rate(v2_enrich_fallback_count[1h]) / rate(v2_count[1h])` | < 0.05 |

告警响应见 [`monitoring-runbook.md`](./monitoring-runbook.md)。

---

## 4. 与 W24-B（真实流量 diff）的关系

- **W24-B 仍为 Trigger**：须 ≥20 条真实 `video_url` 样本才跑 `v1_v2_diff.py`（见 [`v1-v2-diff-real-traffic.md`](./v1-v2-diff-real-traffic.md)）。
- 灰度上调 **不依赖** diff 完成，但 **R3→100%** 前必须有一次 diff 归档。

---

## 5. 常见问题

| 现象 | 处理 |
|------|------|
| `invalid_admin_token` | 检查 `AI_ENGINE_ADMIN_TOKEN` 与 curl header |
| `confirm_required` / 40010 | 降级时加 `FORCE=1` |
| pct 改了但比例不对 | Redis 未通 → 仅 env 生效；查 `REDIS_URL` 是否进 ai_engine |
| mock_mode=true | 灰度无效，分析全走 mock v1 |

---

## 6. 变更记录

| 日期 | 档位 | 操作人 | 备注 |
|------|------|--------|------|
| 2026-05-28 | R0 · 5% | Ops | W5 CVM 首发 |
| 2026-05-30 | R0 · 5% | — | W24 runbook + 脚本就位；**R1 待 D7 指标 OK 后手动执行** |
