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

## 4 · 接生产告警渠道（待 W18+）

当前 `alertmanager.yml` `receivers.default-webhook.webhook_configs.url` 指向占位 echo
服务，告警会被 echo 出来但**不通知任何人**。

接企业微信群机器人时：

1. 在企业微信里创建群机器人，拿到 webhook key
2. 由于企业微信 webhook payload 格式与 alertmanager 默认不一致，**不能**直接把
   alertmanager url 改成 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<KEY>`
3. 需要中间一层转换。推荐：
   - 加 `alertmanager-to-wechat-bot` container（如 [wonderivan/alertmanager-wechat-bot](https://github.com/wonderivan/alertmanager-wechat-bot)）
   - 或写 5 行 FastAPI 自己转
4. 把 alertmanager.yml 的 webhook url 指向该转换服务

接钉钉同理（payload 格式各家不同）。

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
