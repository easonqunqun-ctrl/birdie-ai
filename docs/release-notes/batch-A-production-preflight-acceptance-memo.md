# Batch-A 发版前置核销 · 验收纪要

> **执行日期**：2026-05-21  
> **环境**：CVM staging（`ubuntu@1.13.198.172` / `api.birdieai.cn`）  
> **对应队列**：[`docs/19` §二 U-1～U-5](../19-产品开发迭代计划-当前队列.md#二紧急队列生产核销--发版前置) · **Batch-A**

---

## 1. 结论摘要

| ID | 事项 | 结果 | 备注 |
|----|------|------|------|
| **U-1** | Celery beat + `expire_stale_pending_orders` | ✅ **通过** | beat 在线；近 30min 捕获 2 条派发；`PAYMENT_PENDING_ORDER_EXPIRE_MINUTES=120` |
| **U-2** | 对象存储真桶 | ✅ **通过（MinIO）** | staging `STORAGE_PROVIDER=minio`；presign + bucket 列表 OK；COS 四元组未配 → 脚本跳过（生产切 COS 时再跑 `make check-cos-smoke`） |
| **U-3** | HTTPS + 小程序合法域名 | ✅ **通过** | LE 证书至 2026-08-11；DNS → `1.13.198.172`；`/v1/health` 200；登记清单：`https://api.birdieai.cn`（**request + uploadFile + downloadFile**，2026-05-21 产品确认；详见 [go-live-weapp-fool-checklist §1](./go-live-weapp-fool-checklist.md)） |
| **U-4** | 支付/退款回调路径 | ✅ **通过** | notify 路径正确；refund 已由 NOTIFY 推导，**已显式写入 `.env.local`**；live POST 均 200（空 body 返回验签失败属预期） |
| **U-5** | 部署形态 / Git 对齐 | ⚠️ **部分通过** | Git 已 `ff-only` 至 `cfa4f47`；运行中 backend/worker/beat 仍为 **docker commit 热更镜像**（sha256 无 tag）；关键热修代码已核验在容器内 |

**整体判定**：**Batch-A 可支撑体验版 / staging 继续测试**；U-5 正式镜像 rebuild 可作为下一运维窗口单独执行（见 §4 余量）。

---

## 2. 执行命令与证据

### 2.1 一键预检（本机）

```bash
ENV=secrets/cvm.env.local BACKEND_ENV=secrets/cvm.env.local make check-preflight
```

输出：U-0 heal 跳过 · U-4 通过（refund 推导警告，已 remediate）· U-3 全 host 通过 · U-2 COS 跳过 · U-1 三段 ✓。

### 2.2 CVM 远端补充

```bash
# Git 对齐
ssh ubuntu@1.13.198.172 'cd ~/lingniao-golf && git pull --ff-only origin main'
# → cfa4f47 fix(poster): 删除不存在的 styles/common 导入

# 退款回调显式配置（消除 U-4 警告）
# .env.local 追加：
# WECHAT_PAY_REFUND_NOTIFY_URL=https://api.birdieai.cn/v1/payments/wechat/refund-notify

# 热修代码在容器内
docker exec xiaoniao-backend grep -c query_transaction_by_out_trade_no /app/app/integrations/wechat_pay_v3.py  # → 1
docker exec xiaoniao-backend grep -c _parse_notify_days /app/app/tasks/payment_tasks.py                      # → 2

# MinIO presign
docker exec xiaoniao-backend python -c "from app.integrations.minio import get_minio_storage; ..."
# → presign_ok url=https://api.birdieai.cn/minio/xiaoniao-videos-test fields=7

# 真支付 PEM
docker exec xiaoniao-backend test -r /secrets/apiclient_key.pem && echo pem_ok
```

### 2.3 健康快照（2026-05-21T14:36Z）

```json
{
  "status": "ok",
  "env": "staging",
  "services": { "backend": "ok", "database": "ok", "redis": "ok", "ai_engine": "ok" },
  "ai_engine": { "reachable": true, "mock_mode": false }
}
```

---

## 3. 已执行的 remediate

1. **CVM `.env.local`**：追加 `WECHAT_PAY_REFUND_NOTIFY_URL=https://api.birdieai.cn/v1/payments/wechat/refund-notify`（与 notify 同源；后端重启非必须，运行时原可推导）。
2. **Git**：CVM 仓库从 `12cc38c` fast-forward 至 `cfa4f47`（poster 客户端 + 文档；**无后端镜像变更**）。
3. **本地备份**：`secrets/cvm.env.local` 已 scp 同步。

---

## 4. 余量 / 下一运维窗口

| 项 | 说明 | 优先级 |
|----|------|--------|
| **U-5 正式 rebuild** | 将 sha256 热更镜像替换为 `docker compose up -d --build` 产物；CVM 历史有 buildx `futex_wait` 挂起风险，建议低峰 + 监控 | P1 运维 |
| **U-2 COS 真桶** | 生产切 `STORAGE_PROVIDER=cos` 后跑 `COS_BUCKET=… make check-cos-smoke` | 生产前 |
| **微信公众平台域名** | 已登记 `https://api.birdieai.cn`（request + uploadFile + **downloadFile**，2026-05-21 产品确认） | ✅ 已配置 |
| **par-C2/C3 产品签字** | 会员过期 / 示例视频验收纪要 Draft 待复核 | Batch-F |

---

## 5. 关联文档

- [`docs/19-产品开发迭代计划-当前队列.md`](../19-产品开发迭代计划-当前队列.md) §二 · §6.6 Batch-A
- [`cvm-release-smooth-runbook.md`](./cvm-release-smooth-runbook.md) §七·补
- [`CVM-canonical-deploy.md`](./CVM-canonical-deploy.md)
- [`secrets/README.md`](../../secrets/README.md)

---

*维护：后续 Batch-A 重跑时更新「执行日期」与 §2 证据块，勿删历史 remediate 记录。*
