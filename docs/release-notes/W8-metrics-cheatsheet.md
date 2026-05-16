# W8 核心指标速查（events 表 SQL）

> **用途**：W8 内测期每天早晚各跑一次下列 SQL，看关键漏斗是否正常 + 错误是否在收敛。
> 直接连测试环境 Postgres 执行即可（`docker compose -f docker-compose.yml -f docker-compose.test.yml exec postgres psql -U postgres xiaoniao`）。
>
> 所有时间按 **Asia/Shanghai** 时区（PG 默认 UTC，用 `AT TIME ZONE 'Asia/Shanghai'` 显式转）。
>
> 事件白名单见 `backend/app/services/event_service.py::EVENT_NAMES`：
> `page_view` / `analysis_submit` / `analysis_done` / `share_report` / `pay_success` / `error_report`

---

## 1. 日活（DAU）— 按天去重用户

```sql
SELECT
  (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
  COUNT(DISTINCT user_id) AS dau
FROM events
WHERE name = 'page_view'
  AND user_id IS NOT NULL
  AND created_at >= NOW() - INTERVAL '14 days'
GROUP BY 1
ORDER BY 1 DESC;
```

**看什么**：每日真实登录用户数；突降（>30%）先看是不是客户端埋点中断。

---

## 2. 分析漏斗（submit → done 转化率）

```sql
WITH daily AS (
  SELECT
    (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
    COUNT(*) FILTER (WHERE name = 'analysis_submit') AS submits,
    COUNT(*) FILTER (WHERE name = 'analysis_done')   AS dones
  FROM events
  WHERE name IN ('analysis_submit', 'analysis_done')
    AND created_at >= NOW() - INTERVAL '14 days'
  GROUP BY 1
)
SELECT
  day,
  submits,
  dones,
  CASE WHEN submits = 0 THEN NULL
       ELSE ROUND(100.0 * dones / submits, 1) END AS done_rate_pct
FROM daily
ORDER BY day DESC;
```

**看什么**：submit → done 比例 < 90% 说明 AI 引擎或 MinIO 链路有异常；`dones > submits` 是正常的（老报告也会被回访）。

---

## 3. 分享次数 + 分享率

```sql
WITH daily AS (
  SELECT
    (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
    COUNT(*) FILTER (WHERE name = 'share_report') AS shares,
    COUNT(*) FILTER (WHERE name = 'analysis_done') AS dones
  FROM events
  WHERE name IN ('share_report', 'analysis_done')
    AND created_at >= NOW() - INTERVAL '14 days'
  GROUP BY 1
)
SELECT
  day,
  shares,
  dones,
  CASE WHEN dones = 0 THEN NULL
       ELSE ROUND(100.0 * shares / dones, 1) END AS share_rate_pct
FROM daily
ORDER BY day DESC;
```

**看什么**：每日分享数绝对值 + 分享率。与 `share_actions` 表比对应当一致（允许偶尔埋点 flush 延迟 1-2 条差异）。

---

## 4. 错误上报 TOP 10（按消息聚合）

```sql
SELECT
  COALESCE(payload->>'scope', 'unknown') AS scope,
  payload->>'message'                    AS message,
  COUNT(*)                               AS occurrences,
  MAX(created_at) AT TIME ZONE 'Asia/Shanghai' AS last_seen
FROM events
WHERE name = 'error_report'
  AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY occurrences DESC
LIMIT 10;
```

**看什么**：24h 窗口内错误的头部分布。`scope=app.onError` 通常是运行期 JS 异常；`scope=app.onUnhandledRejection` 是 Promise 拒绝。

---

## 5. 支付成功次数（mock vs real）

```sql
SELECT
  (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
  COALESCE(payload->>'mode', 'unknown') AS mode,
  COUNT(*) AS pay_success_cnt
FROM events
WHERE name = 'pay_success'
  AND created_at >= NOW() - INTERVAL '14 days'
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
```

**看什么**：W8 内测期 `mode=mock` 应占 100%（真实支付 W9 上线）。一旦 `mode=real` 有行 = 白名单用户已经走过真实支付测试。

---

## 6. 单用户行为路径（debug 某个用户时用）

```sql
-- 把 :uid 换成具体 user_id（usr_xxx）
SELECT
  (created_at AT TIME ZONE 'Asia/Shanghai') AS ts,
  name,
  payload
FROM events
WHERE user_id = :uid
  AND created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at ASC;
```

**看什么**：还原该用户最近 24h 内的操作路径；配合客服 / 内测 bug 复现链路追溯很有用。

---

## 附：一键体检面板（每日拉一行汇总）

```sql
WITH today AS (
  SELECT name
  FROM events
  WHERE created_at >= date_trunc('day', NOW() AT TIME ZONE 'Asia/Shanghai')
)
SELECT
  (SELECT COUNT(DISTINCT user_id) FROM events
    WHERE name = 'page_view'
      AND user_id IS NOT NULL
      AND created_at >= date_trunc('day', NOW() AT TIME ZONE 'Asia/Shanghai')) AS dau_today,
  (SELECT COUNT(*) FROM today WHERE name = 'analysis_submit') AS submits_today,
  (SELECT COUNT(*) FROM today WHERE name = 'analysis_done')   AS dones_today,
  (SELECT COUNT(*) FROM today WHERE name = 'share_report')    AS shares_today,
  (SELECT COUNT(*) FROM today WHERE name = 'pay_success')     AS pays_today,
  (SELECT COUNT(*) FROM today WHERE name = 'error_report')    AS errors_today;
```

**解读**：一行看完今日活跃 / 提交 / 完成 / 分享 / 支付 / 错误六个维度；异常（比如 `errors_today > submits_today`）立即进入第 4 节做头部错误定位。

---

## W9 后续

- 真实支付上线后追加 `payment_fail` 事件（目前只埋成功）
- 当 DAU > 200 时，建议把本表拆两张：
  - `events_raw`（原始 7 天热数据，当前结构）
  - `events_archive`（冷数据按月分区，删 TTL > 30d 数据）
- 看板工具选型待定：Grafana（成本低）/ Metabase（易用）/ Redash（SQL 友好），W9 启动时一次评估。
