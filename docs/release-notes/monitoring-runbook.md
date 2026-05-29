# 监控告警响应 Runbook（P2-W15-C）

> **位置**：`docs/release-notes/monitoring-runbook.md`
> **配套**：
> - `infra/monitoring/prometheus.yml` · scrape config
> - `infra/monitoring/prometheus-alerts.yml` · 7 条 ai_engine 告警
> - `infra/monitoring/alertmanager.yml` · 路由到 webhook-echo
> - `infra/monitoring/README.md` · 监控栈启动 / 端口转发
>
> **维护契约**：每加 1 条 alert，必须同步在本 runbook 加 1 节"响应步骤"。无 runbook 不许进 prod。

---

## 0. 一句话原则

**告警是动作，不是噪音。** 任何收到的 alert 必须能在 5min 内决定"做什么"，否则就是"该删该改阈值"。

---

## 1. 监控栈拓扑（W15-A 落地）

```
┌──────────────┐  /metrics/prom  ┌────────────┐
│  ai_engine   │ ──────────────▶ │ Prometheus │
│  :9000       │   每 30s 抓一次  │  :9090     │
└──────────────┘                  └────┬───────┘
                                        │ alert fired
                                        ▼
                                  ┌────────────┐
                                  │Alertmanager│
                                  │  :9093     │
                                  └────┬───────┘
                                        │ webhook
                                        ▼
                                  ┌──────────────┐
                                  │ webhook-echo │  ← W18+ 替换为企业微信群机器人
                                  │  :9094       │
                                  └──────────────┘
```

**端口都是 `127.0.0.1` 绑定**：外网摸不到，要看面板必须 SSH 端口转发：

```bash
ssh -i ~/.ssh/id_ed25519_birdie_golf -L 9090:127.0.0.1:9090 \
                                     -L 9093:127.0.0.1:9093 \
                                     -L 9094:127.0.0.1:9094 \
                                     ubuntu@1.13.198.172
# 然后浏览器开 http://localhost:9090 / :9093 / :9094
```

---

## 2. 7 条告警的响应表

每条 alert 标准结构：**Trigger（看到什么）→ Verify（先证伪）→ Mitigate（先止血）→ RootCause（再定位）→ Document（事后归档）**。

### 2.1 P0 / `AiEngineV2ErrorRateHigh`

- **Trigger**：v2_error_rate > 10%，持续 10m。
- **Verify**：
  ```bash
  ssh ubuntu@1.13.198.172 'docker exec xiaoniao-ai-engine \
    curl -s http://127.0.0.1:9000/metrics | python3 -m json.tool'
  ```
  看 `v2_count` / `v2_errors`，分母 < 5 时告警是噪音（直接 silence 30m 等流量起来）。
- **Mitigate**：
  - 立即把 V2 灰度降回 0：
    ```bash
    docker exec xiaoniao-redis redis-cli SET ai:engine:rollout_pct 0
    ```
  - 这把所有新流量切回 V1，给排查留时间。
- **RootCause**：
  - 看最近 1h ai_engine 日志：`docker logs --since 1h xiaoniao-ai-engine | grep -E '(ERROR|Exception)' | head -50`
  - 三大常见根因：① YAML rule 文件被 build 漏掉 → `docker exec xiaoniao-ai-engine ls /app/app/rules/` 应该有 7 个；② mediapipe OOM（CVM 4G 内存）→ `dmesg | tail -20` 看 OOM-kill；③ DB 写回 timeout → `docker logs xiaoniao-postgres --since 1h | grep -i lock`
- **Document**：触发 → 修复 → 复盘进 `docs/release-notes/p2-phase2-sprint-plan.md` 故障表。

### 2.2 P0 / `AiEngineV2FallbackBurst`

- **Trigger**：5m 内 V2 → V1 兜底 > 5 次。
- **Verify**：
  ```bash
  docker exec xiaoniao-ai-engine ls /app/app/rules /app/app/locales/zh-CN
  ```
  rules 应有 7 个 yml；locales 应有 9 个 yml。
- **Mitigate**：通常是 build 缺资源，重 build：
  ```bash
  cd /home/ubuntu/lingniao-golf
  docker compose up -d --build ai_engine
  ```
- **RootCause**：W7 起 V2 兜底走的是 `_enrich_v2_fallback`，触发条件：`load_locale_pack` 抛 `LocalePackError` / `RuleEngine.__init__` 抛 `RuleSyntaxError`。看 `docker logs xiaoniao-ai-engine | grep -E '(LocalePackError|RuleSyntaxError)'`。
- **Document**：rule yml 改动需走 `make backend-revision`（虽然 ai_engine 没 alembic，但要在 PR 描述里注明改了哪个 yml）。

### 2.3 P1 / `AiEngineProbeFailureHigh`

- **Trigger**：v2_probe_error_rate > 5%，持续 15m。W13-C 修复后预期常态 < 0.5%。
- **Verify**：分桶看哪种错占大头：
  ```bash
  curl -s http://localhost:9090/api/v1/query?query=ai_engine_v2_probe_errors_5xx_after_retries
  curl -s http://localhost:9090/api/v1/query?query=ai_engine_v2_probe_errors_4xx
  curl -s http://localhost:9090/api/v1/query?query=ai_engine_v2_probe_errors_binary_missing
  curl -s http://localhost:9090/api/v1/query?query=ai_engine_v2_probe_errors_unknown
  ```
- **Mitigate**：根据分桶分别处理：
  - **5xx 主导**：MinIO/nginx 抖动 → 看下面 2.4 单独的 alert，可能 W13-C rewrite 没生效。
  - **4xx 主导**：URL 过期 / bucket 权限问题 → 检查 `MINIO_PUBLIC_ENDPOINT` 配置，cdn 缓存策略，`signed_url_expires`。
  - **binary_missing**：ai_engine 镜像本身没 ffprobe，重 build 看 Dockerfile 是不是 alpine 没装。
  - **unknown**：抓最近一条 `v2_probe_failed reason=unknown` 日志，看 stderr 是不是新分类需要补 `_classify_probe_error`。
- **Document**：参考 `docs/release-notes/minio-ffprobe-5xx-rca.md`。

### 2.4 P1 / `AiEngineProbeMinioFiveXxResurfaced`

- **Trigger**：W13-C 已修，1h 内 5xx_after_retries 增量 > 0 — 是个**回归告警**。
- **Verify**：
  ```bash
  docker exec xiaoniao-ai-engine env | grep -E 'MINIO_ENDPOINT|MINIO_PUBLIC_ENDPOINT'
  # 期望：
  # MINIO_ENDPOINT=http://minio:9000  ← 内网
  # MINIO_PUBLIC_ENDPOINT=https://api.birdieai.cn/minio  ← 公网
  ```
  两边都得有，缺一个 rewrite 就废了。
- **Mitigate**：补全 `.env.local`，重启 ai_engine。
- **RootCause**：上线某次发布时把 `.env.local` 里的 `MINIO_PUBLIC_ENDPOINT` 删了；或新接 COS / 第三方对象存储但 video_url 不命中 rewrite（这条留 W15-D 泛化）。
- **Document**：每次出现都记进 `docs/release-notes/minio-ffprobe-5xx-rca.md` 时间线。

### 2.5 P2 / `AiEngineV2TrafficRatioDeviates`

- **Trigger**：实际 V2 流量比 - rollout_pct 绝对差 > 15%，持续 30m。
- **Verify**：
  ```bash
  docker exec xiaoniao-redis redis-cli GET ai:engine:rollout_pct
  ```
  与 metrics `rollout_pct` 应一致；不一致说明 redis 是 SoT 但 ai_engine 没拉新。
- **Mitigate**：通常无需，是观察告警。如果业务方对比例敏感，重启 ai_engine 强制重读：
  ```bash
  docker restart xiaoniao-ai-engine
  ```
- **RootCause**：① 用户基数小（W5 第一次 5% 拉满 11d 0-hit 就是这个，sticky bucketing）；② 大量 `force_v1` hint 触发；③ cold start 后还没稳定。
- **Document**：偏差超 30% 时记进周更，分析 sticky bucket 是否需要重打散。

### 2.6 P2 / `AiEngineV2LatencyP50High`

- **Trigger**：v2_avg_latency_ms > 60000ms（60s），持续 10m。
- **Verify**：`v2_count > 5` 才有意义，分母小别看。
- **Mitigate**：
  - CVM 端单 worker，CPU 节流时单次跑 90s+ 是正常的；如果是真业务慢，先把 rollout_pct 降到 50%。
- **RootCause**：① mediapipe 推理慢（看 `docker stats xiaoniao-ai-engine` 实时 CPU%）；② DB 写回阻塞（pg slow query）；③ ffprobe retry 累计 wall time（W12-3 引入，每次最多 +6s 退避）。
- **Document**：阈值上线一周后根据真实 P50 调整。

### 2.7 P2 / `AiEngineEnrichFallbackTrend`

- **Trigger**：v2_enrich_fallback_count 1h rate > 0.5/s，持续 30m。
- **Verify**：跑一次 V1/V2 diff 看哪些 issue type 被漏覆盖：
  ```bash
  docker exec xiaoniao-ai-engine python scripts/v1_v2_diff.py --recent 50
  ```
- **Mitigate**：补 YAML rule 表里的 `issue.type` 映射；不紧急，进 W17 + ENG-04 sample 收集。
- **RootCause**：V2 RuleEngine YAML 表与 V1 `diagnose_swing` 输出 type 集合有 gap，是产品力收口期可控的工程债。

---

## 3. 7 天观察检查项（W13-C 落地后）

按 **D1 / D3 / D7** 三个时间点抓 metrics 看趋势：

| 时点 | 关键指标 | 期望值（W13-C 后） | 异常处理 |
|---|---|---|---|
| **D0**（W15-A 启栈日） | v2_count / v2_probe_count | 0（暂无真实流量） | 进入 W15-B 后会有 sample 流量 |
| **D1**（次日） | v2_probe_error_rate | < 1% | > 5% → 触发 2.3 流程 |
| **D1** | v2_probe_errors_5xx_after_retries | 0 | > 0 → 触发 2.4 流程，**这是 W13-C 修复回归的 canary** |
| **D3** | v2_avg_latency_ms | 15-45s | > 60s 触发 2.6 |
| **D3** | v2_traffic_ratio vs rollout_pct | 偏差 < 10% | > 15% 触发 2.5 |
| **D7** | v2_count > v1_count（rollout_pct=100%） | True | 否则查 rollout 配置 |
| **D7** | v2_enrich_fallback_count / v2_count | < 5% | > 5% 跑 v1_v2_diff |

**周报模板**（每周二归档进 `docs/release-notes/week-NN-monitoring-snapshot.md`）：

```
## 监控周报 - W{N}

### 流量
- v1_count: {prev → curr, +Δ}
- v2_count: {prev → curr, +Δ}
- v2_traffic_ratio: {%, vs rollout_pct={%}}

### 错误
- v2_error_rate: {%, vs last week}
- v2_probe_error_rate: {%, vs last week}
- 5xx_after_retries: {curr, 应为 0}
- 4xx / binary_missing / unknown: {分桶值}

### 延迟
- v2_avg_latency_ms: {ms, vs last week}

### 触发的 alerts（本周）
- {alert_name}: {fire 次数, 解决耗时, 最终归类}

### 行动项
- [ ] ...
```

---

## 4. 接生产渠道（W18+ backlog）

`webhook-echo` 是占位收件人，看到告警 payload 就行。**未上生产前**：

1. 申请企业微信群机器人 webhook URL
2. 改 `infra/monitoring/alertmanager.yml`：
   ```yaml
   receivers:
     - name: 'wechat-bot-page'
       webhook_configs:
         - url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX'
           send_resolved: true
   ```
3. 加 alertmanager-to-wechat 适配器（payload 格式转换 — 企业微信要 markdown 类型）
4. 路由 P0 走机器人 + 短信（可选 PagerDuty / 阿里云短信）

---

## 5. 演练（推荐每月 1 次）

**人工触发 fire 验证链路通**：

```bash
# 让 v2_error_rate 临时 > 10%
docker exec xiaoniao-ai-engine python -c "
from app.metrics import metrics
for _ in range(20): metrics.incr('v2_count')
for _ in range(5):  metrics.incr('v2_errors')
print(metrics.snapshot())
"

# 等 11min 后看 alertmanager UI 是否 firing
curl -s http://localhost:9093/api/v2/alerts | python3 -m json.tool

# 看 webhook-echo 是否收到 payload
curl -s http://localhost:9094/last 2>/dev/null || \
  docker logs xiaoniao-webhook-echo --since 15m | tail -50
```

演练完一定要清账：

```bash
docker restart xiaoniao-ai-engine  # 进程级 metric 直接清零
```

---

## 6. Backlog（W15-D 之后再做）

- **W15-D**：probe `_rewrite_to_internal_url` 泛化，接 `COS_PUBLIC_BASE` / 第三方 endpoint
- **W18+**：webhook-echo 替企业微信群机器人 + alertmanager-to-wechat 适配器
- **未触发即 backlog**：W14-C V1/V2 diff 真实流量 baseline（≥ 20 真实样本后启）
