# ai_engine 监控栈（P2-W14-A）

> Prometheus + Alertmanager + Echo webhook，监控 `ai_engine /metrics/prom`（W13-D 落地）。

## 1 · 启动

```bash
# 在 CVM 仓库根目录
docker compose --profile monitoring up -d prometheus alertmanager webhook-echo

# 验证
docker ps | grep xiaoniao-prometheus     # 应 healthy
docker ps | grep xiaoniao-alertmanager   # 应 healthy
docker ps | grep xiaoniao-webhook-echo   # 应 healthy
```

**默认 profile 不会启动**——和 backend/ai_engine 主链路分离，不影响主服务发布节奏。
要常驻请在 systemd / Make target 里手动 `--profile monitoring` 起。

## 2 · 访问面板（SSH 端口转发）

监控端口**不暴露公网**，全部只 bind `127.0.0.1:`。看面板走 SSH 转发：

```bash
# 在你本机
ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 -L 9094:127.0.0.1:9094 \
    -i ~/.ssh/id_ed25519_birdie_golf ubuntu@1.13.198.172

# 浏览器：
#   http://localhost:9090/targets    Prometheus scrape 健康（ai_engine 应 UP）
#   http://localhost:9090/alerts     当前 firing 告警
#   http://localhost:9093/#/alerts   Alertmanager 路由 + 静默
#   http://localhost:9094/           echo webhook 看 alert payload 格式
```

## 3 · 告警 rule 来源

| 文件 | 内容 |
|---|---|
| `prometheus.yml` | 主配置：scrape ai_engine /metrics/prom + 加载 rule_files |
| `prometheus-alerts.yml` | W13-D 落地的 7 条 alerting rules，被 prometheus 容器 mount 进 `/etc/prometheus/rules/ai_engine.yml` |
| `alertmanager.yml` | 路由 + 抑制规则；webhook 默认指向 `webhook-echo:9094`（占位） |

## 4 · 接生产告警渠道（W19-C ✅）

默认 `alertmanager.yml` 已指向 **`wechat-webhook-bridge:9095`**（同 compose profile）。

### 方案 A · PushPlus（推荐，个人微信即可）

找不到企微「群机器人」时用此方案：

1. 浏览器打开 https://www.pushplus.plus ，**微信扫码登录**
2. 首页复制 **用户 Token**
3. CVM `.env.local` 写入：

   ```bash
   PUSHPLUS_TOKEN=你的token
   ```

4. 重启 bridge：

   ```bash
   docker compose --profile monitoring --env-file .env.local up -d wechat-webhook-bridge
   ```

5. 测试（CVM 上）：

   ```bash
   curl -s -X POST http://127.0.0.1:9095/alert \
     -H 'Content-Type: application/json' \
     -d '{"status":"firing","alerts":[{"labels":{"alertname":"TestAlert","severity":"warn","service":"ai_engine"},"annotations":{"summary":"PushPlus 通道测试"}}]}'
   ```

   微信应收到「领翼golf 监控告警」消息。

### 方案 B · 企业微信群机器人

1. **内部群**（仅本公司同事）→ 添加群机器人 → 复制 webhook key
2. CVM `.env.local`：

   ```bash
   WECOM_WEBHOOK_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

3. 重启：

   ```bash
   docker compose --profile monitoring --env-file .env.local up -d alertmanager wechat-webhook-bridge
   ```

**未配置任何 key/token 时**：bridge 仅 dry-run 打日志，不会外发。

本地调试 Alertmanager payload 格式仍可用 **`webhook-echo:9094`** — 把 `alertmanager.yml` receivers url 改回即可。

接钉钉同理（payload 格式各家不同，需另写 bridge）。

## 5 · 验证 ai_engine /metrics/prom 被 scrape

```bash
# CVM 上（在 prometheus profile 起来后）
docker exec xiaoniao-prometheus wget -qO- http://localhost:9090/api/v1/targets \
    | python3 -c "import json,sys;d=json.load(sys.stdin);
  for t in d['data']['activeTargets']:
    if 'ai_engine' in t.get('labels',{}).get('job',''):
      print(t['labels']['job'], t['health'], t['lastScrape'])"
# 期望输出：ai_engine up <timestamp>
```

## 6 · 故障排查

| 症状 | 排查 |
|---|---|
| `ai_engine` target DOWN | `docker logs xiaoniao-prometheus`；通常是 ai_engine 不在 docker network；检查 `network: xiaoniao-network` 是否一致 |
| 告警长时间不 fire | `/alerts` 页面看 expr 当前值；`/graph` 直接跑 PromQL 看数据；可能 rule `for:` 没满足 |
| webhook-echo 没收到 alert | `docker logs xiaoniao-alertmanager`；看 alertmanager 内部状态 `http://localhost:9093/#/status` |
| Prometheus OOM | mem_limit 256M 不够，加到 512M；或者拉短 retention（7d → 3d） |

## 7 · 关闭监控栈

```bash
docker compose --profile monitoring down
# 数据卷保留：prometheus_data / alertmanager_data
# 彻底清：docker volume rm xiaoniao-golf_prometheus_data xiaoniao-golf_alertmanager_data
```
