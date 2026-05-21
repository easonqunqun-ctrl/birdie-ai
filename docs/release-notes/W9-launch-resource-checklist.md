# W9 · 上线资源逐项核对清单（运维 / 法务 / 密钥）

用于 **生产首上 / 年复核**：与 [**W9-code-vs-plan-status**](./W9-code-vs-plan-status.md)、[**docs/17-W9任务拆分.md**](../17-W9任务拆分.md) 对齐。  
逐项打勾并由负责人签字/日期记入你们的运营 Wiki 即可。

| 序号 | 项 | 已具备 |
|------|-----|--------|
| 1 | ICP / 域名解析 | □ |
| 2 | 小程序备案 · 类目与资质 | □ |
| 3 | 微信支付商户号 · APIv3 密钥 · 商户 API 证书 | □ |
| 4 | 支付回调域名 `WECHAT_PAY_NOTIFY_URL`（HTTPS、与路由一致 `/v1/payments/wechat/notify`） | □ |
| 5 | 退款回调域名 `WECHAT_PAY_REFUND_NOTIFY_URL`（或依赖支付域名路径推导 `/v1/payments/wechat/refund-notify`） | □ |
| 6 | DeepSeek/Qwen 等 LLM Key 与预算 | □ |
| 7 | COS 桶 · CDN · 跨域与会话密钥（U-2 自检：`COS_BUCKET=… COS_REGION=… COS_SECRET_ID=… COS_SECRET_KEY=… [CDN_HOST=…] make check-cos-smoke`） | □ |
| 8 | 生产库备份策略 · Redis · 密钥轮换 | □ |
| 9 | Celery worker + **beat**（含 `expire_stale_pending_orders`） | □ |
|10 | HTTPS 合法域名（小程序后台 request / uploadFile / downloadFile / socket；staging：`https://api.birdieai.cn`） | □ |

**不必提交本勾选表到私有仓库**：可按团队惯例存 Confluence / 飞书；若入库请脱敏（无密钥、无 AppSecret 明文）。
