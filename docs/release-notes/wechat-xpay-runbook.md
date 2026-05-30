# 微信小程序虚拟支付（xpay）接入 Runbook

> 适用：**领翼golf** 小程序 iOS 合规售卖虚拟会员（AI 分析 / 教练 / 训练权益）。
> 审核驳回原因通常为「虚拟产品未走小程序虚拟支付」；接好本链路后再提审。

---

## 1. 前置条件

| 项 | 说明 |
|----|------|
| 虚拟支付商户 | 小程序后台 **虚拟支付 → 开通**（你已在申请/审核中） |
| 道具配置 | **虚拟支付 → 基础配置 → 道具配置**，新增月度/年度两个道具，价格与 `PLAN_PRICING` 一致（¥39 / ¥299） |
| offerId / appKey | 开通后在 **基础配置** 页复制 **offerId**、**现网 appKey**、**沙箱 appKey** |
| 消息推送 | **开发 → 开发管理 → 消息推送**：URL 填 `https://api.birdieai.cn/v1/wechat/mp-push`，Token 与 `.env` 中 `WECHAT_MP_PUSH_TOKEN` 一致 |
| 基础库 | 客户端 `wx.requestVirtualPayment` 需基础库 ≥ **2.19.2** |

---

## 2. 环境变量（CVM `.env.local`）

```bash
# 关闭 JSAPI mock，启用虚拟支付（二者配合使用）
WECHAT_PAY_MOCK_MODE=false
WECHAT_XPAY_ENABLED=true

# 米大师 / 虚拟支付
WECHAT_XPAY_OFFER_ID=           # mp 基础配置 offerId
WECHAT_XPAY_APP_KEY=            # 现网 appKey
WECHAT_XPAY_SANDBOX_APP_KEY=    # 沙箱 appKey（联调 env=1 时用）
WECHAT_XPAY_ENV=0               # 0 现网 1 沙箱
WECHAT_XPAY_PRODUCT_MONTHLY=    # 月度道具 productId
WECHAT_XPAY_PRODUCT_YEARLY=     # 年度道具 productId

# 消息推送（xpay_goods_deliver_notify）
WECHAT_MP_PUSH_TOKEN=           # 与小程序后台消息推送 Token 一致
# 若后台选「明文模式」可不填 AES Key；兼容/安全模式再填：
# WECHAT_MP_PUSH_ENCODING_AES_KEY=
```

**说明**：启用 `WECHAT_XPAY_ENABLED` 后，小程序端 **不再** 走 `wx.requestPayment`（JSAPI），改走 `wx.requestVirtualPayment`（道具直购 `short_series_goods`）。委托代扣自动续费在虚拟支付模式下 **暂不可用**，需手动续费。

---

## 3. 发版顺序

1. **道具 + 消息推送** 在 mp 后台配好（审核通过前可先沙箱 `WECHAT_XPAY_ENV=1` 联调）。
2. **后端** 部署含 xpay 的版本，`make deploy-check-env` 通过。
3. **客户端** `TARO_APP_PAYMENT_MOCK=false`、`TARO_APP_PAYMENT_ENABLED=true`，上传体验版。
4. 真机：会员页下单 → 应拉起 **虚拟支付** 收银台（非普通微信支付半屏）。
5. 支付成功后：微信推送 `xpay_goods_deliver_notify` → 后端激活会员；客户端 `sync-from-wechat` 作补偿。

---

## 4. 联调 / 冒烟

```bash
# 后端单测（签名 + 发货推送）
cd backend && uv run pytest tests/test_wechat_xpay.py -q

# 查单补偿（需真实 openid + 已支付订单）
# POST /v1/payments/orders/{id}/sync-from-wechat  （JWT）
```

**沙箱**：`WECHAT_XPAY_ENV=1` + `WECHAT_XPAY_SANDBOX_APP_KEY`；道具须在沙箱环境单独配置。

**常见错误**

| 现象 | 排查 |
|------|------|
| 签名错误 268490003 | appKey 与 env 不匹配；signData 字段多余或 JSON 键序变化 |
| session_key 过期 268490009 | 下单前须 fresh `wx.login()`，随 `create_order` 传 `wx_login_code` |
| 发货未到账 | 查消息推送 URL 是否 200 + `{"ErrCode":0}`；查后端日志 `xpay_goods_deliver_notify` |
| 仍走 JSAPI | 确认 `WECHAT_XPAY_ENABLED=true` 且已重启 backend |

---

## 7. iOS 虚拟支付（Apple 支付）

**报错**：`当前商户尚未开启iOS支付`（errCode `-15001`）

**原因**：Android/Windows 虚拟支付开通 ≠ iOS 已签约。iOS 须单独在 mp 后台完成 Apple 支付签约。

**开通步骤**（须管理员扫码登录 [mp.weixin.qq.com](https://mp.weixin.qq.com/)）：

1. **虚拟支付 → iOS 资金概况** → 按指引完成签约（二级商户 / Apple 小程序合作伙伴计划）
2. 确认 **小程序简称** 已配置（设置 → 基本设置 → 小程序简称；Apple 展示名要求）
3. CVM `.env.local` 保持 **`WECHAT_XPAY_ENV=0`**（iOS **不支持沙箱 env=1**）
4. 道具须在 **现网 env=0** 发布（`scripts/setup_wechat_xpay_goods.py --env 0`）
5. 真机要求：iOS ≥ 15、微信 ≥ 8.0.68

**联调注意**：体验版/真机 iOS 一律用现网 appKey + env=0；Android 联调可暂用沙箱 env=1。

---

## 5. 提审注意

- 会员页价格与 mp **道具价格** 必须一致。
- 体验版需能完整走通「选套餐 → 虚拟支付 → 会员生效」。
- iOS 虚拟商品 **禁止** 再用普通 `wx.requestPayment` 售卖会员。

---

## 6. 相关代码

| 模块 | 路径 |
|------|------|
| 签名 / 查单 | `backend/app/integrations/wechat_xpay.py` |
| 下单 / 到账 | `backend/app/services/payment_service.py` |
| 发货推送 | `backend/app/api/v1/wechat_push.py` |
| 客户端支付 | `client/src/adapters/payment.ts` |
| API 契约 | `docs/02-API接口设计文档.md` §6.7 |
