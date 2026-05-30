# W19-B · xpay 体验版冒烟 Runbook

> 前置代码已合：`wechat_xpay.py` / `mp-push` / `production_guard` / 客户端 `requestVirtualPayment`。
> 本 runbook 用于 **体验版发版前** 一次性验通「下单 → 虚拟支付 → 发货到账」。

---

## 1. 环境自检（自动化）

```bash
# 本地 / CVM 上（填实际 env 路径）
python3 scripts/xpay_smoke_check.py --env-file ~/secrets/lingniao-prod.env \
  --api-base https://api.birdieai.cn/v1
```

**PASS 条件**：必填 xpay 变量齐全 + `GET /v1/wechat/mp-push` 签名校验返回 echostr。

---

## 2. mp 后台清单

| 项 | 位置 | 验收 |
|----|------|------|
| 消息推送 URL | 开发 → 开发管理 → 消息推送 | `https://api.birdieai.cn/v1/wechat/mp-push`，**明文模式** |
| Token | 同上 | 与 `WECHAT_MP_PUSH_TOKEN` 一致 |
| 道具 | 虚拟支付 → 道具配置 | 月度/年度 productId 与 env 一致 |
| iOS 支付 | 虚拟支付 → iOS 资金概况 | 真机 iOS 须 env=0 + 现网 appKey |

道具脚本（可选）：

```bash
python3 scripts/setup_wechat_xpay_goods.py --env 0   # 现网
python3 scripts/apply_wechat_xpay_env.py --env-file ~/secrets/lingniao-prod.env
```

---

## 3. 发版顺序

1. CVM：`WECHAT_PAY_MOCK_MODE=false` + `WECHAT_XPAY_ENABLED=true` + 全套 xpay 变量
2. `make publish-backend-cvm`（或等价重建 backend）
3. 客户端：`TARO_APP_PAYMENT_MOCK=false`、`TARO_APP_PAYMENT_ENABLED=true`
4. `pnpm build:weapp:prod` → 上传**体验版**

---

## 4. 真机冒烟（手工）

| # | 步骤 | 期望 |
|---|------|------|
| 1 | 体验版登录 → 会员页选月度套餐 | 拉起 **虚拟支付** 收银台（非普通 JSAPI） |
| 2 | 沙箱：`WECHAT_XPAY_ENV=1` + sandbox appKey | 沙箱扣款成功 |
| 3 | 现网/iOS：`WECHAT_XPAY_ENV=0` | 扣款成功 |
| 4 | 支付后 30s 内 | `GET /users/me` 会员字段生效 |
| 5 | 后端日志 | `xpay_goods_deliver_notify` → `ErrCode=0` |
| 6 | 补偿 | `POST /payments/orders/{id}/sync-from-wechat` 可补单 |

---

## 5. 常见失败

| 现象 | 处理 |
|------|------|
| 仍走 JSAPI | 确认 `WECHAT_XPAY_ENABLED=true` 且 backend 已重启 |
| 签名 268490003 | appKey 与 `WECHAT_XPAY_ENV` 不匹配 |
| 发货未到账 | mp-push 是否 200；查 CVM 日志 `xpay_goods_deliver_notify_failed` |
| iOS -15001 | mp 后台 iOS 虚拟支付未签约 |

---

## 6. 关联文档

- [`wechat-xpay-runbook.md`](./wechat-xpay-runbook.md) — 完整接入
- [`docs/02` §6.7](../02-API接口设计文档.md) — API 契约
- `backend/tests/test_wechat_xpay.py` — 单测门禁
