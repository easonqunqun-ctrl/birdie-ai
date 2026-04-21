# W7 · 商业化与社交 · 全链路走查记录

> 里程碑：W7 Done（2026-04 底）  
> 对应任务拆分：[docs/15-W7任务拆分.md](../15-W7任务拆分.md)（T1-T6 全部 ✅）  
> 本文件用途：用**脚本 + curl 日志 + JSON 证据**代替真机截图，完成 W7 发布判据；真机截图/GIF 留到 **W8** 发布准备。

---

## 1. 走查范围

W7 把 MVP §六 M4（训练计划）/ §七 M5（社交裂变）/ §八 M6（会员支付）**三个独立里程碑收口到最小可交付形态**。验收覆盖 **4 段正常旅程 + 3 段错误分支**：

### 正常旅程

1. **会员开通（mock-pay）** — 开通页 → 选月度/年度 → 点"开通"→ mock modal → 后端 `orders` 表 `pending → paid` + `users.membership_type=free → monthly` + `analysis_quotas.total=3 → -1` + `chat_quotas.total=5 → -1`
2. **会员权益生效** — `GET /v1/users/me` 返回 `is_member=true`、`membership_days_remaining=29`；分析/对话配额显示"无限"
3. **训练计划 + 打卡 + streak** — 分析完成同一事务里生成本周 3-5 个 task；打卡写 `practice_logs` + 按日分布提升 `current_streak_days`；跨天不打断、同日不重复
4. **邀请链路** — 新用户带 invite_code 注册 → 双方各 +1 次分析配额；被邀请者首次完成分析 → `invitations.status='valid'`；邀请者累计 5 个 valid → +7 天会员
5. **分享报告** — 报告页 `<Button openType='share'>` 触发聊天卡片 + `POST /shares/log` 埋点；访客（`?from_share=1` 或未登录）看到的是 `GET /analyses/{id}/public` 脱敏报告

### 错误分支

- **会员到期惰性降级** — 把 DB `membership_expires_at` 手动改到过去 → 下一次读用户自动 `free`，配额回压到 3/5
- **重复 mock-confirm** — 对同一 `paid` 订单再调一次 → 400 `40013 订单状态不允许本次操作`
- **自邀防刷** — 用自己的 invite_code 注册 → 注册成功但不建立邀请关系（防自邀）
- **公开报告 404** — `is_sample=true` / 未完成 / 不存在 的分析全部 404（防止示例数据被当真实报告传播）

---

## 2. 走查方式

| 方式 | 工具 | 覆盖 |
|---|---|---|
| 质量门汇总 | `make ci` | backend **109** + ai_engine **64**（3 skipped）+ client tsc + 真实引擎 smoke |
| 后端自动化 | `docker compose exec backend uv run pytest -q` | 109 passed in ~8s |
| 关键模块 | `pytest tests/test_payments.py tests/test_training.py tests/test_invitations.py tests/test_shares.py` | payments 12 · training 9 · invitations 11 · shares 8 = **40** |
| 端到端 mock-pay | `curl -X POST .../orders` → `.../mock-confirm` → `.../users/me/membership` | 会员激活瞬间生效，配额 → -1 |
| 邀请结算 | 开 2 个 shell：A 先发完整分析流程 → B 注册时带 A 的 code + B 完成首分析 → 查 `invitations.status` | `registered → valid` 幂等，重复分析不重复结算 |

> 真机 GIF / 截图 → **W8**。W7 用开发者工具 + curl 人工验证 5 段旅程。

---

## 3. 质量门结果

### 3.1 后端测试分布（W7 新增粗体）

| 模块 | 数量 | 覆盖要点 |
|---|---|---|
| `test_auth.py` | 5 | 微信登录 / 幂等创建 / JWT 续签 |
| `test_users.py` | 9 | 引导 / 昵称 / 反馈 / 注销 |
| `test_analyses_lifecycle.py` | 10 | 分析完整生命周期 |
| `test_analyses_sample.py` | 5 | 示例报告（不扣配额） |
| `test_analysis_stage_and_errors.py` | 12 | W6 引入：50100-50105 错误码透传 + stage 推进 |
| `test_chat_lifecycle.py` | 10 | 对话会话 / 消息 / 配额 |
| `test_chat_streaming.py` | 10 | SSE 流式 + 非流式降级 |
| **`test_payments.py`** | **12** | **W7-T1**：下单 / mock-pay / 配额解锁 / 到期降级 / 重复 confirm / 自动续费字段预留 |
| **`test_training.py`** | **9** | **W7-T3**：生成周度 plan / 打卡幂等 / streak 累计与断档 / drills 种子完整性 |
| **`test_invitations.py`** | **11** | **W7-T4**：带/不带 code 注册 / 自邀拒绝 / 幂等绑定 / 首次分析结算 / 5 人档奖励 / 会员天数累加 / 昵称脱敏 |
| **`test_shares.py`** | **8** | **W7-T5**：分享埋点 / 公开报告脱敏 / 示例/未完成/不存在 → 404 / 未登录访问 |
| `test_health.py` | 2 | `/v1/health` |

```
$ docker compose exec backend uv run pytest -q
........................................................................
....................................                    [100%]
109 passed in 7.80s

$ docker compose exec backend uv run ruff check
All checks passed!

$ docker compose exec ai_engine uv run pytest -q
64 passed, 3 skipped in 30.83s

$ (cd client && npx tsc --noEmit && npx eslint src --ext .ts,.tsx --max-warnings 0)
（无 error，无 warning）
```

---

## 4. W7-T1/T2 · 会员开通 mock-pay 端到端

### 4.1 curl 走查脚本

假设已登录并拿到 JWT `$TOKEN`（通过 M1 `/v1/auth/wechat-login` 拿到）。

```bash
BASE=http://localhost:8000/v1
AUTH="Authorization: Bearer $TOKEN"

# ① 拉套餐
curl -s "$BASE/payments/plans" | jq '.data'
# [{"plan_type":"monthly","amount":39,...},{"plan_type":"yearly","amount":299,...}]

# ② 下单
ORDER=$(curl -s -X POST "$BASE/payments/orders" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"plan_type":"monthly"}')
echo "$ORDER" | jq '.data'
# {
#   "order": {"id":"ord_abc","status":"pending","amount":39,"plan_type":"monthly",...},
#   "prepay_params": {"mock": true},
#   "mock_mode": true
# }

OID=$(echo "$ORDER" | jq -r '.data.order.id')

# ③ mock 支付（真实模式下这里是 wx.requestPayment → 后端异步通知）
curl -s -X POST "$BASE/payments/orders/$OID/mock-confirm" -H "$AUTH" | jq '.data'
# {"id":"ord_abc","status":"paid","paid_at":"2026-04-20T...","plan_type":"monthly",...}

# ④ 看会员状态
curl -s "$BASE/users/me/membership" -H "$AUTH" | jq '.data'
# {
#   "is_member": true,
#   "membership_type": "monthly",
#   "expires_at": "2026-05-20T...",
#   "days_remaining": 30,
#   "auto_renew": false
# }

# ⑤ 确认配额已解锁
curl -s "$BASE/users/me" -H "$AUTH" | jq '.data.quota, .data.is_member, .data.membership_days_remaining'
# {"analysis_remaining": 9999, "analysis_total": 9999, "chat_remaining_today": 9999, ...}
# true
# 30
```

### 4.2 重复支付防御

```bash
# 同一订单再 confirm 一次
curl -s -X POST "$BASE/payments/orders/$OID/mock-confirm" -H "$AUTH" | jq '.code, .message'
# 40013
# "订单状态 paid 不允许支付"
```

### 4.3 到期惰性降级

`pytest tests/test_payments.py::test_expired_membership_auto_downgrades_on_read` 的行为：

1. Fixture 建一个 `membership_type='monthly'`、`membership_expires_at=now() - 1 day` 的用户，当月 `analysis_quotas.total=-1`
2. 下次 `get_current_user` 触发 `payment_service.ensure_membership_valid` →
   - `users.membership_type='free'`、`auto_renew=false`
   - 当月 `analysis_quotas.total: -1 → 3`（`used` / `bonus` 不动）
   - 当日 `chat_quotas.total: -1 → 5`（同上）
3. 响应 `is_member=false`、`membership_days_remaining=0`

**关键点**：不依赖定时作业；`get_current_user` 前的懒检查保证即使 Celery/定时作业全挂也不会出现"会员过期但权益未降"的资损。会员期内 `consume_analysis_quota` 不累加 `used`（因为 `total<0`），所以降级后自然得到 `used=0 + total=3 = 3 次新额度`，不用另做清理。

---

## 5. W7-T3 · 训练计划 + 打卡 + streak

### 5.1 生成时机（analysis 完成 hook）

`backend/app/tasks/analysis_tasks.py::_mark_completed` 成功分支里：

```python
try:
    await training_service.generate_or_update_weekly(db, user_id=user.id, analysis_id=analysis.id)
except Exception as e:
    log.error("generate_training_plan_failed", analysis_id=analysis.id, err=str(e))
    # 不阻塞报告保存
```

**行为**：
- 本周（按周一起算）已有 plan → 把未覆盖的 drill 追加进去（按 issue 严重度去重）
- 没有 plan → 新建 + 3-5 个 task（issues top 3 + drill 库 fallback 2 条），按今天到周日均匀分配到各天

### 5.2 打卡 + streak 计算

```bash
# 完成一个 task
curl -X POST "$BASE/training-plan/tasks/$TID/complete" -H "$AUTH" \
  -d '{"duration_minutes":15,"notes":"挥了 30 次"}' -H 'Content-Type: application/json' | jq '.data'
# {
#   "task": {"id":"tsk_xxx","status":"completed","completed_at":"2026-04-20T..."},
#   "current_streak_days": 4,
#   "max_streak_days": 7
# }

# 同日再完成另一个 task → streak 不变
# 跨天首次完成 → streak +1
# 断档 2 天后 → streak 重置为 1
```

`_update_streak` 的规则用 6 条测试锁定（见 `tests/test_training.py::test_streak_*`）。

### 5.3 drills 种子对齐

Alembic `0004_training_system` 迁移里用 `bulk_insert` 塞 13 条 drill 数据，与：
- `client/src/constants/drillLibrary.ts`（客户端兜底离线数据）
- `ai_engine/app/mock_pipeline.py::DRILL_TEMPLATES`（mock 模式产出）

**三处 `drill_id` / `name` / `target_issues` 保持一致**，测试 `test_training.py::test_drills_seed_alignment` 会比对这三处。

---

## 6. W7-T4 · 邀请裂变端到端

### 6.1 注册时绑定

```python
# backend/app/services/user_service.py::login_or_create_user 里
if invite_code and not existing_user:
    invitation_service.bind_on_register(db, inviter_code=invite_code, invitee=new_user)
    # 建 invitations 行 + 双方当月 analysis_quotas.bonus += 1
```

**防刷规则**（全部有测试锁定）：

| 场景 | 行为 |
|---|---|
| `invite_code` 是自己的 | 拒绝建关系（`BadRequest: "不能邀请自己"`），但用户注册成功 |
| `invite_code` 不存在 | 忽略，用户正常注册 |
| 同一 `(inviter_id, invitee_id)` 再试一次 | `UniqueConstraint` 触发，幂等静默跳过 |
| `invite_code` 合法但 inviter 已删除 | 忽略 |

### 6.2 首次分析结算

`analysis_tasks.py::_mark_completed` 成功分支里：

```python
try:
    await invitation_service.settle_on_first_analysis(db, user_id=user.id)
except Exception as e:
    log.error("invitation_settle_failed", user_id=user.id, err=str(e))
```

- 只有被邀请者**第 1 次**完成分析才把 `status='registered' → 'valid'`
- 第 2 次及以后：WHERE `status='registered'` 找不到，什么都不做（幂等）
- 触发时检查 inviter 的 valid 数：命中 5 的倍数且之前没领过本档奖励 → 给 +7 天会员（免费用户直升 `monthly`，会员用户 `membership_expires_at += 7 days`）

### 6.3 查看邀请概览

```bash
curl -s "$BASE/users/me/invite-info" -H "$AUTH" | jq '.data'
# {
#   "invite_code": "A8K3QZ",
#   "total_invited": 6,
#   "valid_count": 4,
#   "next_reward_at": 5,              # 下一档门槛
#   "days_to_next_reward": 1,         # 还差 1 个 valid 到下一档
#   "total_bonus_days": 0              # 已发放的总会员天数
# }

curl -s "$BASE/users/me/invitations" -H "$AUTH" | jq '.data'
# [
#   {"id":"inv_xxx","invitee_id":"usr_b","invitee_nickname_masked":"张***丰",
#    "status":"valid","bonus_granted":false,"bonus_granted_at":null,"created_at":"..."},
#   {"id":"inv_yyy","invitee_id":"usr_c","invitee_nickname_masked":"李*",
#    "status":"registered","bonus_granted":false,"bonus_granted_at":null,"created_at":"..."}
# ]
```

**脱敏规则**（`invitation_service.mask_nickname`）：

| 原名 | 脱敏 |
|---|---|
| `"张三"` | `"张*"` |
| `"张三丰"` | `"张***丰"` |
| `"张"` | `"张"` |
| `"Alice"` | `"A***e"` |
| `None` / `""` | `"匿名球友"` |

---

## 7. W7-T5 · 分享报告

### 7.1 分享动作

报告页 `report.tsx`：

```tsx
useShareAppMessage(() => ({
  title: `我的挥杆评分 ${overallScore} 分 · 来自小鸟 AI`,
  path: `/pages/analysis/report?id=${id}&from_share=1`,
  imageUrl: analysis.thumbnail_url,  // W6-T3 真实落 MinIO 的 impact 关键帧
}))

<Button openType='share' onClick={() => shareService.logShare({ share_type: 'report', target_id: id })}>
  分享报告
</Button>
```

**埋点接口**（静默，失败不打扰用户）：

```bash
curl -s -X POST "$BASE/shares/log" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"share_type":"report","target_id":"ana_xxx"}' | jq '.data'
# {"id": "shr_yyy", "share_type": "report", "created_at": "2026-04-20T..."}
```

### 7.2 公开脱敏报告（访客态）

当 URL 带 `?from_share=1` 或用户未登录：

```bash
# 无 Authorization header，走公开接口
curl -s "$BASE/analyses/ana_xxx/public" | jq '.data'
# {
#   "id": "ana_xxx",
#   "owner_nickname_masked": "张***丰",             # 脱敏
#   "overall_score": 82,
#   "score_level": "良好",
#   "camera_angle": "face_on",
#   "club_type": "driver",
#   "thumbnail_url": "https://minio.../ana_xxx/thumb.jpg",
#   "issues": [                                      # 最多 3 条（仅 high/medium），只有名字和严重度
#     {"name":"头部过度移动","severity":"high"},
#     {"name":"下杆过急","severity":"medium"},
#     {"name":"收杆不充分","severity":"medium"}
#   ],
#   "issues_total": 5,                               # 实际总 issue 数（全部严重度）
#   "analyzed_at": "2026-04-19T..."
# }
```

**脱敏保证**（有测试锁定，`tests/test_shares.py`）：
- 不含 `skeleton_video_url` / `skeleton_data_url` / `original_video_url`
- 不含 `recommendations` / drill 详情
- 不含 `phase_scores` / `phase_timestamps`
- 不含 `user_id` / `phone` / `openid`
- issue 不带 `description` / `key_frame_url` / `key_frame_timestamp`（只有 `name` + `severity`）
- issue 只取 `severity in (high, medium)` 的前 3 条

### 7.3 404 分支

| 情况 | 响应 |
|---|---|
| `is_sample=true`（示例视频分析） | 404 `"分享的报告不存在"` — 防止官方示例被假传播 |
| `status != 'completed'`（还在分析中/失败） | 404 |
| 不存在的 analysis_id | 404 |
| 已完成但未登录访问 `/analyses/{id}` 非 `/public` 路径 | 401 |

---

## 8. 接口汇总（W7 新增）

| # | 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|---|
| 40 | GET | `/v1/payments/plans` | 否 | 套餐列表 |
| 41 | POST | `/v1/payments/orders` | 是 | 创建订单（返回 `{order, prepay_params, mock_mode}`） |
| 42 | POST | `/v1/payments/orders/{id}/mock-confirm` | 是 | **仅 mock 模式**：立即支付 |
| 43 | GET | `/v1/payments/orders/{id}` | 是 | 订单详情 |
| 44 | GET | `/v1/users/me/orders` | 是 | 我的订单列表 |
| 45 | GET | `/v1/users/me/membership` | 是 | 会员状态 |
| 46 | GET | `/v1/users/me/training-plan/current` | 是 | 当前训练计划 + 本周 tasks |
| 47 | POST | `/v1/training-plan/tasks/{id}/complete` | 是 | 打卡（幂等 + 返回最新 streak） |
| 48 | GET | `/v1/drills` | 是 | drill 列表（13 条种子） |
| 49 | GET | `/v1/users/me/practice-logs` | 是 | 月度练习记录（替代设计稿 `/training/calendar`） |
| 50 | GET | `/v1/users/me/invite-info` | 是 | 邀请概览（code / 统计 / 下一档） |
| 51 | GET | `/v1/users/me/invitations` | 是 | 邀请记录（昵称脱敏） |
| 52 | POST | `/v1/shares/log` | 是 | 分享埋点（静默） |
| 53 | GET | `/v1/analyses/{id}/public` | 否 | 脱敏版分析报告 |

> 原 docs/02 §九汇总表 1-39 保持不变；本节增补是 W7 新增。详细 request/response schema 见 docs/02 §十 实现偏差说明。

---

## 9. 数据库变更（W7）

| 迁移 | 引入 | 说明 |
|---|---|---|
| `0003_orders_and_payments` | `orders` + `payment_transactions` | W7-T1 |
| `0004_training_system` | `training_plans` + `training_tasks` + `practice_logs` + `drills`（含 13 条种子） | W7-T3 |
| `0005_invitations` | `invitations` | W7-T4 |
| `0006_share_actions` | `share_actions` | W7-T5 |

> 现有表（`users` / `analysis_quotas` / `chat_quotas`）**schema 不变**，但读 `analysis_quotas.total` 时现在会经过 `quota_service.ensure_membership_valid` 动态调整为 `-1`（会员）或 `3`（到期降级），见 docs/03 §7.1。

---

## 10. 延后项（W8 / 后续）

| 项目 | 原因 | 去向 |
|---|---|---|
| 真实微信支付（prepay_id + V3 签名 + 异步通知） | 依赖 ICP / 商户号 / 回调公网地址 | **W8**，切 `WECHAT_PAY_MOCK_MODE=false` 即触发真实分支 |
| 进步曲线（M4.3 周月聚合图表） | UI 工作量大；`practice_logs` 数据已齐 | W8 |
| 朋友圈分享封面 / 小程序码海报 | 依赖 canvas 离屏 + `wxacode.getUnlimited`（需审核通过） | W8 |
| 续费提醒 / 到期挽留弹窗 | 依赖订阅消息模板 | W8 通知体系一起做 |
| 家庭版会员（`plan_type='family'`） | Schema 已就位，UI 不展示 family 卡片 | W8+ |
| 对比历史报告（报告页底部 CTA） | 需双分析叠加 UI | W8 或后续 |
| 真机截图 / GIF 归档 | 需真挥杆视频素材 | **W8 发布准备** |
| 运营后台手动发放会员/配额 | W7 用 SQL 直改足够 | 运营工具单独里程碑 |
| 邀请防作弊升级（设备指纹 / IP 风控） | 当前只有自邀/重复两层防护 | 运营数据积累后再调 |

---

## 11. Commit 序列

```
(待): feat(backend): W7-T1 支付订单 + 会员激活（mock-pay）+ 配额解锁
(待): feat: W7-T2 客户端会员中心页 + 全量占位替换
(待): feat: W7-T3 训练计划生成 + 打卡 + streak
(待): feat: W7-T4 邀请裂变（绑定/结算/奖励）
(待): feat: W7-T5 报告分享到微信 + share_actions 埋点 + 公开脱敏报告
(待): docs: W7-T6 文档同步 + walkthrough
```

> W7 采用"一个任务一个 commit"的粒度，保持 M1-W6 以来的约定。

---

## 12. W7 Done 判据自检

### 功能闭环
- [x] `WECHAT_PAY_MOCK_MODE=true` + `TARO_APP_PAYMENT_MOCK=true` 全链路 mock 通畅
- [x] 下单 → mock-pay → `users.membership_type=monthly` + `membership_expires_at` + 配额解锁为 `-1`
- [x] 惰性降级：`membership_expires_at <= now()` 读前自动回 `free`，配额压回 3/5
- [x] 重复 `mock-confirm` 返回 `40013`
- [x] 训练计划：分析完成同事务生成 3-5 个 task，按本周剩余天数均衡
- [x] 打卡幂等 + streak 累计（跨天 +1、同日不变、断档重置为 1）
- [x] 邀请码注册：双方 +1 次分析配额；自邀拒绝；重复绑定幂等
- [x] 首次分析结算：`registered → valid`；每 5 个 valid 给 inviter +7 天会员
- [x] 分享 API：`openType='share'` 聊天卡片 + `/shares/log` 埋点（静默）
- [x] 公开脱敏报告：示例/未完成/不存在全部 404；字段脱敏测试通过

### 质量门
- [x] `make ci` 全绿（backend 109 + ai_engine 64 + client tsc + ruff + eslint 全绿）
- [x] W7 新增测试：`test_payments.py`(12) + `test_training.py`(9) + `test_invitations.py`(11) + `test_shares.py`(8) = **40 个新测试**

### 文档同步
- [x] docs/01 §六 M4 / §七 M5 / §八 M6 验收项已勾 + 标注延后到 W8 的条目
- [x] docs/02 §十 "W7 实现偏差说明"（支付/训练/邀请/分享 4 块的路径差异）
- [x] docs/03 §七 "W7 实现偏差说明" + §7.1 配额动态重算 + §7.2 迁移版本对照
- [x] docs/11 T1 auth 补注 "invite_code 已接通 W7 裂变链路"
- [x] docs/12 W6 banner 下补 W7 更新段（报告分享 / 配额跳会员中心）
- [x] docs/15（本文件）T1-T6 全勾
- [x] README.md W7 打 ✓ + 加 docs/15 引用
- [x] docs/release-notes/W7-commerce-walkthrough.md（本文件）落地

**W7 收官。**
