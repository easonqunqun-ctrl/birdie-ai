# W9 · 代码与计划对照（仓库实测）

本文档汇总「`docs/17-W9任务拆分.md` 所述」与当前仓库实现的差异，便于上线前自检。**不含运营灰度手册全文**（可按 W9 文档另补）。

---

## 已对齐（代码侧）

| 主题 | 说明 |
|------|------|
| 微信登录 | 真实 code → session；mock 由 `WECHAT_MOCK_LOGIN` 控制 |
| LLM | `LLM_MOCK_MODE` / 密钥占位 → Fake；否则 OpenAI 兼容客户端流式输出 |
| 支付下单 | JSAPI prepay → 前端 `wx.requestPayment` |
| 支付回调 | **`POST /v1/payments/wechat/notify`**（验签、幂等）；勿再用文档里的 `wechat-notify` 或 `wechat/callback` 旧叫法配置域名 |
| 对象存储 | `STORAGE_PROVIDER=cos` 等分支（MinIO/COS） |
| 配额 | `QUOTA_MODE` 等配置可由环境与文档对齐 |

---

## 文档已修正路径

- **`docs/02-API接口设计文档.md`**：`§6.2` 与接口索引表、`§十` 偏差表 → 统一 **`/v1/payments/wechat/notify`**。
- **`docs/17-W9任务拆分.md`**：任务清单中的回调路径 → 同上。

---

## 缺口 / 风险（相对 W9 期望）

| 项 | 现状 |
|----|------|
| 订单超时自动取消 | 未见通用定时任务 |
| 退款流程 | 未见对接代码 |
| COS 集成自动化测试 | 偏少或无 |
| `test_payments` | mock 偏重；生产路径依赖手工 / 沙箱验证 |
| 部署形态 | 本地 Compose ≠ TKE / TencentDB；上线 Runbook 需在运维侧单独完备 |

---

## 小程序侧此前踩坑（备忘）

| 现象 | 常见原因 |
|------|-----------|
| `request:fail errcode:-207`（Cronet） | HTTPS 证书不受信（如自签）；改用 Let's Encrypt / 公有 CA |
| 「网络异常」泛提示 | `request.ts` 已映射 `-207`/超时等；根因仍以证书与合法 API 域名为准 |
| 微信公众平台「服务器域名」 | 按后台校验：**常为 `https://` + 主机名**（与开放平台 modify_domain 示例一致）；**勿带路径 `/v1`** |

HTTPS 运维：`infra/deploy/README.md`、`make issue-le-cert` / `renew-le-cert`、`docs/release-notes/W8-test-env-runbook.md`。

---

## 后续可选补齐

0. **并行工程与体验项（已纳入迭代计划）**：见 [**`parallel-engineering-backlog.md`**](parallel-engineering-backlog.md)（客户端重试 / 测试门禁 / nginx 与健康检查 / MVP 合规文档对齐等与发版链路并行）。
1. 若 W9 合同包含：**订单生命周期（超时关闭）**、**退款**，需在 `payment_service` / 定时任务 / 路由层落地。
2. 增补 **`docs/release-notes/W9-launch-resource-checklist.md`**（若仍引用该文件名）。
3. COS 上传与 CDN 域名：**清单式手工验收 + 少量契约测试**。
