# W9 · 代码与计划对照（仓库实测）

本文档汇总「`docs/17-W9任务拆分.md` 所述」与当前仓库实现的差异，便于上线前后自检。**不含运营灰度手册全文**（可按 W9 文档另补）。

**紧急可执行项（生产核销 / 发版前置）**：口令级验收与 **U-1～U-6** 锚点见 [**`docs/19-产品开发迭代计划-当前队列.md`**](../19-产品开发迭代计划-当前队列.md) **§二 紧急队列**。

**近况（2026-05）：** ICP / 商户号 / 正式域名齐备且已上线的团队，请参考 [**`docs/19-产品开发迭代计划-当前队列.md`**](../19-产品开发迭代计划-当前队列.md) 与 [**`docs/release-notes/W9-launch-resource-checklist.md`**](release-notes/W9-launch-resource-checklist.md)，将本文「缺口」与生产 Runbook **逐项核销**。

---

## 已对齐（代码侧）

| 主题 | 说明 |
|------|------|
| 微信登录 | 真实 code → session；mock 由 `WECHAT_MOCK_LOGIN` 控制 |
| LLM | `LLM_MOCK_MODE` / 密钥占位 → Fake；否则 OpenAI 兼容客户端流式输出 |
| 支付下单 | JSAPI prepay → 前端 `wx.requestPayment` |
| 支付回调 | **`POST /v1/payments/wechat/notify`**（验签、幂等）；勿再用文档里的 `wechat-notify` 或 `wechat/callback` 旧叫法配置域名 |
| 退款申请 + 退款结果通知 | **`POST /v1/payments/orders/{id}/apply-refund`**（JWT，付费已上线非 mock）；**`POST /v1/payments/wechat/refund-notify`**（验签解密，全额退成功 → `paid`→`refunded` + `payment_transactions(refund)` + 会员降级，与 mock 语义对齐）|
| 对象存储 | `STORAGE_PROVIDER=cos` 等分支（MinIO/COS） |
| 配额 | `QUOTA_MODE` 等配置可由环境与文档对齐 |

---

## 文档已修正路径

- **`docs/02-API接口设计文档.md`**：`§6.2` 与接口索引表、`§十` 偏差表 → 统一 **`/v1/payments/wechat/notify`**。
- **`docs/17-W9任务拆分.md`**：任务清单中的回调路径 → 同上。

---

## 缺口 / 风险（对照生产期望逐项核销）

| 项 | 现状 |
|----|------|
| 订单超时自动取消 | **已提供**：`payment_service.expire_stale_pending_orders` + Celery **`xiaoniao.expire_stale_pending_orders`**（`beat_schedule` 默认 15 分钟）；**生产需在部署侧验证 beat/cron**，见 **`docs/release-notes/CVM-canonical-deploy.md`** §0 / §调度；阈值 **`PAYMENT_PENDING_ORDER_EXPIRE_MINUTES`**（默认 `120`，`≤0` 关闭）|
| ~~退款流程~~ | **已实现（非 mock）**：申请退款 **`apply-refund`** + 异步 **`refund-notify`**（与微信 V3 「申请退款 / 退款结果通知」对齐）；叠加购、部分退等仍为 **简化策略**（以 `docs/01` §8 与工单为准迭代）|
| COS 集成自动化测试 | **契约级**：`tests/test_storage_presign_contract.py` 校验 `storage_presign_origin_base`（**非**真上传）；真桶联调仍以沙箱 + 手工 Runbook 为准 |
| `test_payments` | mock / 补丁 HTTP 偏重；商户平台沙箱与生产小额仍建议门禁外验收 |
| 部署形态 | 本地 Compose ≠ 生产：**Runbook/W9-launch-resource-checklist 需与实控环境一致** |

---

## 小程序侧此前踩坑（备忘）

| 现象 | 常见原因 |
|------|----------|
| `request:fail errcode:-207`（Cronet） | HTTPS 证书不受信（如自签）；改用 Let's Encrypt / 公有 CA |
| 「网络异常」泛提示 | `request.ts` 已映射 `-207`/超时等；根因仍以证书与合法 API 域名为准 |
| 微信公众平台「服务器域名」 | 按后台校验：**常为 `https://` + 主机名**（与开放平台 modify_domain 示例一致）；**勿带路径 `/v1`** |

HTTPS 运维：`infra/deploy/README.md`、`make issue-le-cert` / `renew-le-cert`、`docs/release-notes/W8-test-env-runbook.md`。

---

## 后续可选补齐

0. **产品迭代队列（含并行工程核销）**： [**`parallel-engineering-backlog.md`**](parallel-engineering-backlog.md) · [**`docs/19-产品开发迭代计划-当前队列.md`**](../19-产品开发迭代计划-当前队列.md)。
1. **叠加订单 / 按比例退**：当用户存在多笔叠加续费时，按需将「全额降级」细化为 **`membership_end` 回拨**（与产品/法务确认）。
2. **COS/CND 抽样验收**：沿用 checklist + 工单。
3. 灰度与告警：写入 **`CVM-canonical-deploy.md`** 或独立一页，避免仅存口述。
