# par-C2 · 会员到期 / 降级 · 验收纪要

> **关联**：`docs/19` **DOC-04 / Q-C1 / par-C2** · `docs/01` **§8.3 / §8.4 验收标准** · MVP M4「商业化-会员到期与降级」
> **本纪要只覆盖 par-C2（会员到期与降级）**；par-C1（账号注销）已出 `[par-C1](./par-C1-account-deletion-acceptance-memo.md)` ✅、par-C3（示例视频 §3.6）见 `[par-C3](./par-C3-sample-video-acceptance-memo.md)`。

---

## 0. 元信息


| 字段             | 值                                                                                                                                                                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **纪要 ID**      | `par-C2` · `membership-expiry-2026-05-21`                                                                                                                                                                                         |
| **关联 PLAN-ID** | `Q-C1` / `par-C2` / `DOC-04`（汇总）                                                                                                                                                                                                  |
| **关联文档**       | `[docs/01 §8.3 / §8.4](../01-MVP功能需求规格说明书.md#83-付费墙触发场景)` · `[docs/19 §6.3 DOC-04](../19-产品开发迭代计划-当前队列.md#63-主表plan-id)` · `[parallel-engineering-backlog.md` C2](./parallel-engineering-backlog.md#p2--产品与合规补齐与-mvp-checkbox-对齐) |
| **代码版本**       | `main @ ca168ab`（Batch-B 多档到期提醒 + Batch-A CVM 预检）                                                                                                                                                                                 |
| **验收范围**       | `docs/01 §8.3 退款策略 + §8.4 订阅管理`：会员到期降级、退款触发降级、关闭自动续费、配额回落、**到期前提醒**                                                                                                                                                               |
| **验收日期**       | 2026-05-21（初稿）· 2026-05-21（Batch-F 工程复核）                                                                                                                                                                                          |
| **起草**         | 工程侧自动化纪要                                                                                                                                                                                                                          |
| **复核**         | 产品 ▢（发版前确认） 工程 ☑（自动化验收 2026-05-21）                                                                                                                                                                                                |


---

## 1. 验收依据

### 1.1 产品规格

`docs/01 §8.3 / §8.4` 的核心点（本纪要为其出具书面证据）：

1. 会员到期后权益正确降级（`is_member=false`、`membership_type='free'`、配额回到 `3 / 5`）
2. 退款（mock + 真实）成功后会员降级、auto_renew 清零
3. 关闭自动续费可独立操作，不需要立即退款（**par-C2 2026-05-21 补充**：`POST /v1/payments/membership/cancel-auto-renew` 独立端点已上线）
4. 到期前订阅消息推送（csv 多档默认 `7,3,1` 可配）+ **站内弹窗兜底**（剩余 1–7 天，`useMembershipExpiringSoonModal`）

### 1.2 隐含验收项

- **H1**：到期降级是**惰性**的（不依赖定时任务），任何读用户的请求都会触发；
- **H2**：降级幂等（重复读不会重复回落配额或乱发提醒）；
- **H3**：到期前提醒 Celery beat + **多档 csv 独立 Redis 去重**（`sub:preexpiry:{user}:{date}:{days}`）；无模板 ID 时优雅 noop；**站内弹窗**不依赖订阅授权；
- **H4**：关闭自动续费**不影响**当前已支付的会员到期日。

---

## 2. 实现总览

### 2.1 调用路径

```
[GET /users/me 等任何读用户接口]
        │
        ▼
get_current_user (api/deps.py)
        │
        ▼
ensure_membership_valid(user)   ← backend/app/services/payment_service.py
        │
        ├─ user.membership_expires_at <= now()
        │     ├─ user.membership_type='free'
        │     ├─ user.auto_renew=False
        │     ├─ analysis_quotas.total: -1→3（unlimited 模式不动）
        │     └─ chat_quotas.total: -1→5
        │
        └─ user.membership_expires_at > now() → no-op（幂等）
```

### 2.2 关键文件


| 文件                                        | 角色                                                                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/services/payment_service.py` | `ensure_membership_valid` 惰性降级 + `activate_membership` 激活 + `process_wechat_refund_notify` 退款降级 + `apply_auto_renew` 自动续费开关 |
| `backend/app/api/v1/payments.py`          | `POST /v1/payments/auto-renew` / `POST /v1/payments/membership/cancel-auto-renew`（**par-C2 2026-05-21 新增**）                 |
| `backend/app/tasks/account_tasks.py` 等    | `xiaoniao.membership_pre_expiry_notify` Celery beat（订阅消息提醒）                                                                 |


---

## 3. 验收证据

### 3.1 自动化测试


| 测试文件                                                                                          | 覆盖点                                                                     |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `backend/tests/test_payments.py::test_membership_expired_user_drops_to_free`                  | 到期惰性降级                                                                  |
| `backend/tests/test_payments.py::test_mock_refund_downgrades_to_free`                         | mock 退款触发降级                                                             |
| `backend/tests/test_payments.py::test_wechat_refund_notify_downgrades_to_free_and_idempotent` | 真实退款回调 + 幂等                                                             |
| `backend/tests/test_payments.py::test_cancel_auto_renew_turns_off_flag`                       | **新增** · cancel-auto-renew 独立端点关闭 auto_renew                            |
| `backend/tests/test_payments.py::test_cancel_auto_renew_message_includes_expiry`              | **新增** · 关闭后 message 携带「至 YYYY-MM-DD」                                   |
| `backend/tests/test_payment_tasks.py`                                                         | `membership_pre_expiry_notify` beat 任务 + **多档 csv** + 按档 dedup（Batch-B） |
| `client/src/hooks/useMembershipExpiringSoonModal.ts`                                          | 站内到期前弹窗 + localStorage 去重（16 jest）                                      |


### 3.2 集成证据

- CVM staging（Batch-A 2026-05-21）：
  - `make check-preflight` U-1 beat ✅ / U-4 支付回调 ✅ / `/v1/health` 200
  - `WECHAT_PAY_MOCK_MODE=false`；真支付 PEM 可读；`query_transaction_by_out_trade_no` 热修已验
- CVM staging 已切真支付（`WECHAT_PAY_MOCK_MODE=false`, 2026-05-21）：
  - `/v1/payments/plans` 套餐列表正常返回
  - `wechat_pay_config_audit` 无 fatal（`production_guard` 通过）
  - `celery-beat` 容器跑 `membership_pre_expiry_notify` 任务（`docker logs xiaoniao-celery-beat` 可见 schedule）
- 客户端 `pages/profile/membership.tsx` 关闭 Switch 触发二次确认 modal + 调用 cancel-auto-renew 端点，showToast 「已关闭，会员至 YYYY-MM-DD」

### 3.3 已知 backlog

- **真实退款**端到端真机回归（依赖商户后台真退款单 + 微信侧 refund-notify 真实回调）仍需 W9 用真测试单跑一次
- **委托扣款签约**（`papay`）→ W9 接入后会真正打通 auto_renew=true 的 mini-program 跳转链路；本纪要范围限于「关闭」侧

---

## 4. 签字栏


| 角色  | 姓名    | 日期         | 备注                                         |
| --- | ----- | ---------- | ------------------------------------------ |
| 产品  | 陈     | 2026.5.22  | 发版前确认 §8.3/§8.4 与真机到期提醒体验                  |
| 工程  | 自动化验收 | 2026-05-21 | pytest 矩阵 + Batch-A CVM 预检 + Batch-B 多档/弹窗 |


