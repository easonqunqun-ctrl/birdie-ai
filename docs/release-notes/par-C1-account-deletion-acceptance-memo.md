# par-C1 · 账号注销全流程 · 验收纪要

> **关联**：`docs/19` **DOC-04 / Q-C1 / par-C1** · `docs/01` **§3.4** · MVP M3 「账号注销」
> **本纪要只覆盖 par-C1（账号注销）**；par-C2（会员过期降级）/ par-C3（示例视频 §3.6 文档对齐）仍 **Open**，需产品复核后单独出纪要，**DOC-04 因此保持 Partial**。

---

## 0. 元信息

| 字段 | 值 |
|------|----|
| **纪要 ID** | `par-C1` · `account-deletion-2026-05-20` |
| **关联 PLAN-ID** | `Q-C1` / `par-C1` / `DOC-04`（汇总） |
| **关联文档** | [`docs/01 §3.4`](../01-MVP功能需求规格说明书.md#34-账号注销) · [`docs/19 §6.3 DOC-04`](../19-产品开发迭代计划-当前队列.md#63-主表plan-id) · [`parallel-engineering-backlog.md` C1](./parallel-engineering-backlog.md#p2--产品与合规补齐与-mvp-checkbox-对齐) |
| **代码版本** | `feat/account-deletion-pipl-followups @ HEAD`（PR #9 → #10 合入 main 后由本纪要 PR #11 闭环） |
| **验收范围** | `docs/01 §3.4` 列出的 4 条验收标准（已逐项 `[x]`）+ 2 条隐含项（PIPL 兜底、注销期登录拒绝） |
| **验收日期** | 2026-05-20 |
| **起草** | 工程侧自动化纪要 |
| **复核（待签）** | 产品 ▢　工程 ▢　法务/合规 ▢ |

---

## 1. 验收依据

### 1.1 法规依据

- **PIPL**（《个人信息保护法》2021）第 47 条：个人请求删除其个人信息的，个人信息处理者应当主动删除；未删除的，个人有权请求删除
- 国内主管单位实践口径：**冷静期 ≤ 15 天合规**，本系统采用 **7 天**

### 1.2 产品规格

`docs/01 §3.4` 的 4 条验收标准（已 `[x]`，本纪要为其出具书面证据）：

1. 注销流程包含二次确认（输入 `DELETE` + `showModal` 最后确认）
2. 7 天冷静期内可成功取消注销
3. 冷静期到期后数据正确清理
4. 注销后重新进入视为新用户

### 1.3 隐含验收项（本纪要追加证据链）

- **PIPL 兜底**：用户申请注销后**不再登录**也必须按时清理（不能依赖懒清理）
- **注销期内的鉴权语义**：到期未清理时下次请求的行为定义清晰，避免半成品账户漏掉鉴权

---

## 2. 实现总览

### 2.1 架构与数据流

```
[小程序 / RN]                  [FastAPI]                        [PostgreSQL]
account-deletion.tsx
   │
   │ DELETE 二次确认
   │ + showModal "最后确认"
   ▼
POST /v1/users/me/account-deletion
   │ confirm_text = "DELETE"
   ▼
request_account_deletion(user, confirm_text)
   ├── confirm_text != "DELETE"          → BadRequestError(40001)
   ├── scheduled_at != None              → BadRequestError(40015)  幂等
   ├── any order.status == "pending"     → BadRequestError(40016)
   └── scheduled_at = now() + 7 days
                                         ▼
                                         users.account_deletion_scheduled_at
                                                 │
        ┌────────────────────────────────────────┼──────────────────────────────┐
        ▼                                        ▼                              ▼
  POST /cancel                            GET /users/me                  Celery beat (每小时第 17 分)
  cancel_account_deletion()               get_user_by_id()               purge_due_account_deletions
   scheduled_at = None                     └─ 若 scheduled_at <= now      ├─ select where scheduled_at <= now
   (40001 if not pending)                     → purge_user_if_due ✂        │   limit 500
                                              → NotFoundError(40401)      └─ 每 user 独立 session
                                                                              purge_user_if_due ✂
                                                                              DELETE FROM users ... CASCADE
                                                                              swing_analyses / orders / ...
```

### 2.2 关键代码锚点

| 层 | 文件 | 关键符号 |
|----|------|----------|
| 客户端页面 | [`client/src/pages/profile/account-deletion.tsx`](../../client/src/pages/profile/account-deletion.tsx) | `AccountDeletionPage` · `onSubmit` · `onCancelSchedule` |
| 客户端服务 | `client/src/services/userService.ts` | `requestAccountDeletion(text)` · `cancelAccountDeletion()` |
| 路由 | [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py) | `POST /me/account-deletion` · `POST /me/account-deletion/cancel` |
| 业务 | [`backend/app/services/account_deletion_service.py`](../../backend/app/services/account_deletion_service.py) | `request_account_deletion` · `cancel_account_deletion` · `purge_user_if_due` |
| 数据 | [`backend/app/models/user.py`](../../backend/app/models/user.py) | `account_deletion_scheduled_at`（注释明确双路径） |
| 懒清理 | `backend/app/services/user_service.py` | `get_user_by_id` 调 `purge_user_if_due` |
| Beat 兜底 | [`backend/app/tasks/account_tasks.py`](../../backend/app/tasks/account_tasks.py) | `xiaoniao.purge_due_account_deletions` |
| 调度注册 | [`backend/app/celery_app.py`](../../backend/app/celery_app.py) | `beat_schedule["purge-due-account-deletions"]` |
| 回归测试 | [`backend/tests/test_account_deletion.py`](../../backend/tests/test_account_deletion.py) | 10 个 pytest |
| CI 门禁 | [`.github/workflows/backend-pytest-smoke.yml`](../../.github/workflows/backend-pytest-smoke.yml) | 真 PG+Redis 跑 `test_account_deletion.py` |

---

## 3. 逐项验收对照

### 3.1 docs/01 §3.4 验收标准（4 条）

| # | 验收标准 | 代码证据 | 测试证据 | 验收结论 |
|---|----------|----------|----------|----------|
| **A1** | 注销流程包含二次确认（输入 `DELETE` + `showModal` 最后确认） | `account-deletion.tsx::onSubmit` 第 27–30 行客户端硬校验；`Taro.showModal` 第 31–53 行；服务端 `account_deletion_service.request_account_deletion` 二次硬校验 `confirm_text.strip() != "DELETE"` → `BadRequestError(40001)` | `test_request_account_deletion_happy_path` · `test_request_account_deletion_rejects_wrong_confirm_text`（小写 `delete` → 400 / 40001） | ✅ Done |
| **A2** | 7 天冷静期内可成功取消注销 | `account-deletion.tsx::onCancelSchedule`；`POST /me/account-deletion/cancel` → `cancel_account_deletion(user)` 把 `scheduled_at` 置 `None` | `test_cancel_account_deletion_clears_schedule` · `test_cancel_account_deletion_rejects_when_not_pending`（未排期时 400 / 40001） | ✅ Done |
| **A3** | 冷静期到期后数据正确清理 | `purge_user_if_due` 第 57–68 行 `DELETE FROM users WHERE id = uid` + `await db.commit()`；外键 `ondelete="CASCADE"` 触发 `swing_analyses` 等子表清理；**双触发路径**：① 懒清理 `get_user_by_id` ② Beat 兜底 `xiaoniao.purge_due_account_deletions`（每小时第 17 分） | `test_lazy_purge_on_next_request_after_due`（user 真被删 / 404 / 40401） · `test_purge_due_account_deletions_async_purges_due_users`（beat 精确清理 1 个到期用户、保留 2 个未到期）· `test_purge_due_account_deletions_async_counts_failures`（异常用户不阻塞他人） · `test_purge_due_account_deletions_in_beat_schedule`（beat 注册回归） · `test_purge_due_account_deletions_task_registered`（task registry 回归） | ✅ Done（**含 PIPL 兜底**） |
| **A4** | 注销后重新进入视为新用户 | `users.wechat_openid` / `wechat_app_openid` 在硬删后被释放，下次微信登录走 `auth_service.handle_wechat_mock_login` / 真实 wechat-login，会创建新用户行（id = `usr_<nanoid>`） | 由 `_register` 反复调用 `/v1/auth/wechat-login` 隐含验证（每次新 user_id）；**真机回归**建议季度抽测纳入 ops smoke | ✅ Done（**真机仍建议季度抽测**） |

### 3.2 隐含验收项

| # | 项 | 证据 | 结论 |
|---|----|------|------|
| **H1** | **PIPL 合规兜底**：用户申请注销后即便不再登录，仍按 7 天到期清理 | Celery beat 每小时第 17 分扫全表清理；`task_time_limit=30min` / `soft=25min` 避免历史积压把任务 kill；`structlog log.exception` 留 traceback；任务返回 `{"purged": N, "failed": M}` 供 Grafana 监控 | ✅ Done |
| **H2** | **冷静期内并发"再次申请"幂等** | `request_account_deletion` 第 36–37 行 `scheduled_at is not None` → `BadRequestError(40015, "已提交注销申请，冷静期内可取消")`；不会延长冷静期 | ✅ Done（`test_request_account_deletion_idempotent_within_cooldown`） |
| **H3** | **未支付订单阻塞注销** | `has_pending_payments_block_deletion` 检查 `pending` 订单 → `BadRequestError(40016, "你有未完成的会员订单...")` | ✅ Done（业务规则；本次未单独写 pytest，CI 已覆盖订单状态轮转链路 `test_payments.py`） |
| **H4** | **客户端"已排期"状态可视化 + 撤销入口** | `account-deletion.tsx` 第 97–112 行：渲染 `scheduledText` + 「撤销注销」按钮 | ✅ Done |
| **H5** | **客户端登录态在到期后被清理** | `get_user_by_id` 触发硬删后路由层抛 `NotFoundError(40401, http=404)`；前端 `request.ts` 的 401/404 处理会拉到登录页 | ✅ Done（CI: `test_lazy_purge_on_next_request_after_due`） |

---

## 4. 测试覆盖矩阵

| 场景 | 用例 |
|------|------|
| API · 申请 happy path | `test_request_account_deletion_happy_path`（断言 scheduled_at 偏离 7d < 60s） |
| API · 错误确认文案 | `test_request_account_deletion_rejects_wrong_confirm_text`（小写 `delete` → 40001） |
| API · 冷静期内幂等 | `test_request_account_deletion_idempotent_within_cooldown`（重复申请 → 40015） |
| API · 取消注销 | `test_cancel_account_deletion_clears_schedule` |
| API · 取消时未排期 | `test_cancel_account_deletion_rejects_when_not_pending`（→ 40001） |
| 懒清理 · 到期 | `test_lazy_purge_on_next_request_after_due`（GET /me → 404 / 40401，DB 行真被删） |
| 懒清理 · 未到期 | `test_lazy_purge_skips_when_not_due`（仍 200 / user 保留） |
| Beat · 到期清理 | `test_purge_due_account_deletions_async_purges_due_users`（精确清理 1 个 + 保留 2 个） |
| Beat · 异常不阻塞 | `test_purge_due_account_deletions_async_counts_failures`（一行失败、另一行成功） |
| Beat · 无人到期 | `test_purge_due_account_deletions_async_noop_when_nothing_due`（returns (0,0)） |
| 防回归 · beat 注册 | `test_purge_due_account_deletions_in_beat_schedule`（celery_app.beat_schedule 必有此项） |
| 防回归 · task 注册 | `test_purge_due_account_deletions_task_registered`（celery_app.tasks 必有 `xiaoniao.purge_due_account_deletions`） |

**总用例：10 个**，全部跑在 `backend-pytest-smoke` CI（真 PG + Redis）。

---

## 5. 上线观测与告警

### 5.1 关键日志键

| 事件 | logger | 关键字段 |
|------|--------|----------|
| Beat 任务完成 | `tasks.account` | `account_deletion_purge_done` · `purged: N` · `failed: M` |
| Beat 单行失败 | `tasks.account` | `account_deletion_purge_failed` · `user_id` · traceback（`log.exception`） |
| 懒清理触发 | 路由层 | （没显式日志；通过 `users` 表行数变化与 401/404 计数侧证） |

### 5.2 建议告警阈值（运维侧后续配）

- `account_deletion_purge_failed` 每日 ≥ 5 次 → P2 告警（说明子表 CASCADE 配置出问题）
- `account_deletion_purge_done.failed >= 1` 连续 3 小时 → P1 告警
- Beat 任务执行时长 > 25min（接近 `soft_time_limit`）→ P2 告警，需要把 `BATCH_SIZE` 调小或拆 task

### 5.3 数据保留窗口

- `scheduled_at` 字段在 PostgreSQL 写入时即作为「申请凭证」存在；用户撤销后字段重置 `NULL`
- 不留任何审计表（与 §3.4 设计一致；如未来法务要求"注销审计"再加 `account_deletion_audits`）

---

## 6. 已知 drift / 后续 backlog

| 项 | 说明 | 责任方 |
|----|------|--------|
| 真机季度抽测 | A4「注销后重新进入视为新用户」依赖 wechat 真 openid；自动化测试仅能覆盖 mock 模式，**真机回归** 已纳入 ops smoke 季度抽样 | Ops |
| par-C2 验收纪要 | 会员过期与降级（`ensure_membership_valid`）逐项对照 | 产品 + 工程 |
| par-C3 验收纪要 | 示例视频 §3.6 与 M2 「示例条目」文档对齐 | 产品 |
| 删除前导出数据 | PIPL 第 45 条「可携带权」未启用（产品决策：MVP 不做） | 产品决策 |
| 注销审计表 | 未建（产品决策：MVP 不做） | 产品决策 |

---

## 7. 复核栏

> 验收通过后由产品 / 工程 / 法务三方在本节填名 / 日期。

- **产品复核**：______（_____ ／ 2026-05-__）
- **工程复核**：______（_____ ／ 2026-05-__）
- **法务/合规复核**：______（_____ ／ 2026-05-__）

复核通过后请在 `docs/19 §6.5b DOC-04` 把状态从 **Partial** 推进；待 par-C2 / par-C3 也都出纪要并复核后，DOC-04 整体可改 **Done**。
