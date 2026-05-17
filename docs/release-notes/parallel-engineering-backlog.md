# 并行工程与体验补齐 backlog（已纳入迭代计划）

> **目的**：在 **不阻断** 当前主干（微信小程序分析 / 对话 / 训练 / 支付与 **CVM 单链路发版**）的前提下，明确可并行推进的工程与体验项，避免与热点救火抢同一 MR。  
> **发版主轴**：过渡期约定见 **`docs/release-notes/CVM-canonical-deploy.md`** §0（rsync / `publish-backend-cvm` / `tmux` 单次 `compose`）；后续 Git 切换见同文档 §0「下一版切 Git」。  
> **产品规格对照**：MVP 逐项验收仍以 **`docs/01-MVP功能需求规格说明书.md`** 为准；本文 **不替代** MVP，仅补充「工程与健康度」泳道。  
> **总表**：未完项优先级与源码锚点汇总见 **`docs/19-产品开发迭代计划-当前队列.md`**。

---

## 优先级说明

| 标签 | 含义 |
|------|------|
| **P1** | 建议近两轮迭代内排到开发；与稳定性 / 合规 / 上线信心强相关 |
| **P2** | 可与 W8 能力（订阅消息、分享海报等）对齐或顺延；或依赖 W6 真实引擎 |

---

## 核销快照 · P1（2026-05-13）

| 序号 | 项 | 状态 | 备注 |
|------|-----|------|------|
| E1 | 上传失败后自动重试 + request_id | **Done（代码侧）** | `client/src/services/analysisService.ts`（退避上限与 HTTP 判别）|
| E2 | 等待页阈值 60s / 120s 文案 | **Done** | `client/src/pages/analysis/waiting.tsx` MVP 阈值与贴士 |
| E3 | 网络 Toast 与 `request.ts` 对齐 | **Partial** | 持续随新 `-20x`/`timeout` case 增补 |
| T1 | 后端 pytest（关键路径） | **Partial / 演进中** | 含 `payments` / quota / streaming 门禁；按需扩展 |
| T2 | 改接口同步 docs/02 | **纪律项** | 随 PR；无「完成」勾选 |
| T3 | CI backend 门禁 | **Done（smoke）** | `.github/workflows/backend-pytest-smoke.yml`；全量仍为 `make backend-test` |
| O1 | nginx unhealthy | **文档 + 口述** | 见 `CVM-canonical-deploy` §8；遇个案再核销 |
| O2 | Runbook 一页 | **Done（文档侧）** | `CVM-canonical-deploy.md` §0 |
| O3 | MinIO/COS 变量 | **Done（文档侧）** | §0「环境变量速查」|

---

## P1 · 客户端稳定性与体验

| 序号 | 项 | 说明 / 对齐 |
|------|-----|-------------|
| E1 | 上传失败后 **自动重试**（含退避）、失败上限与可复制 **request_id** | MVP：`01` M2 §4.2 延后 W8「上传失败重试」；与 `analysisService`/MinIO 直传链路一致 |
| E2 | **等待页**「时间较长」阈值与 MVP 体感对齐（文档曾记 60s vs 实现 120s） | MVP：`01` M2 §4.2 `[~]` 项 |
| E3 | 错误与网络类 Toast **语义统一**（与 `request.ts` 映射表一致） | 减少「泛网络异常」误判 |

---

## P1 · 测试与门禁

| 序号 | 项 | 说明 / 对齐 |
|------|-----|-------------|
| T1 | **后端**：为近期易回归路径增补 pytest（分析列表 / 配额 / chat / payment 契约） | 降低发版后怕 |
| T2 | **契约**：改动接口时 **`docs/02-API接口设计文档.md`** 同步（仓库守则） | |
| T3 | CI：在现有 RN check 基础上，评估 **backend 测试**最小门禁（任选：lint only / 选定模块 pytest） | 与 `Makefile`/`AGENTS.md` 一致即可 |

---

## P1 · 运维与观测

| 序号 | 项 | 说明 / 对齐 |
|------|-----|-------------|
| O1 | **nginx `unhealthy`** 根因：`healthcheck`、upstream、`resolver`/容器 IP | 对齐 `docs/release-notes/CVM-canonical-deploy.md` **§8**；**Runbook 口令表**见同文档 **§0「发版与排障口令」** |
| O2 | 发版 **Runbook 一页**：`tmux`、禁止并行 `compose`、失败时 `pgrep`/回滚口令 | 已写入 **`CVM-canonical-deploy.md`** §0「发版与排障口令」 |
| O3 | **MinIO/COS**：内外网 URL、ai_engine 拉取视频、`MINIO_ENDPOINT`/`PUBLIC` | 已写入 **`CVM-canonical-deploy.md`** §0「环境变量速查」 |

---

## P2 · 产品与合规补齐（与 MVP Checkbox 对齐）

| 序号 | 项 | 说明 / 对齐 |
|------|-----|-------------|
| C1 | **账号注销**全流程验收：`01` §3.4 四项（冷静期 / 到期清理 / 再进为新用户） | **Open**：逐条勾选 `01` + 验收纪要 |
| C2 | **会员过期与降级**：`01` §3.5 与代码路径（惰性校验等）逐项对照 | **Open**：与 `ensure_membership_valid` 对齐 doc |
| C3 | **示例视频 §3.6** 与 M2 「示例」已勾选条目 **文档对齐** | **Open** |

**C1–C3 · 对照登记（源码入口，不作为替代验收）**：账号注销 **`client/src/pages/profile/account-deletion.tsx`** · **`backend/app/services/account_deletion_service.py`**；会员过期惰性降级 **`payment_service.ensure_membership_valid`**（读用户时触发）；示例报告 **`id=sample`** 及列表过滤见 **`analysis_service` / `training` API**。

---

## P2 · M3/M4/M5/M6 顺延能力（按计划仍属 W8 / W7）

以下内容 **刻意不拆细任务**：已有 **`docs/16-W8任务拆分.md`**、**`docs/15-W7任务拆分.md`**、`01` 中 W8 标注可作源；并行开发时 **领子任务再在对应拆分文档增补 issue 级勾选**。

- **W8**：分析完成 **订阅消息**（`waiting`/`membership` 已接线拉模板，`TARO_APP_SUBSCRIBE_TPL_*` 配后用）、**分享海报 / 小程序码**、上传 SLA 真机、**微信支付委托扣费**（若合规需要）等。
- **W8**：训练 **进步曲线** UI。
- ~~**W7**：对话 **会话列表** UI~~ **→ 已并入主线**（`profile/chat-history` + `/chat/sessions`）；以 `docs/01` 勾选为准。
- **W6**：服务端 **视频质量预检**、骨骼叠加 **≥24fps**（**`docs/14-W6任务拆分.md`**；引擎侧预处理与 `visualize` 见 **`docs/release-notes/W6-engine-productization-roadmap.md`**）。

---

## P2 / W9 · 商业与工单（与交付合同对齐时再排）

- **订单超时自动关闭**：代码 + Celery 任务 ✅；Compose 增补 **`celery-beat`** 服务 ✅；仍须在 **目标环境核验 beat 与健康度**。
- **微信退款**：真实 **`apply-refund` + `refund-notify`** ✅（非 mock）；叠加订阅 / 按比例退仍以工单迭代。
- 细节仍为 **`docs/release-notes/W9-code-vs-plan-status.md`**。

---

## 并行纪律（团队约定）

1. **一件事一 PR**（`docs/10-Git协作规范.md`）。
2. 牵涉 **契约 / DB** 必须先改 **`docs/02`** / **`docs/03`** 再改代码（`AGENTS.md`）。
3. **占位页**不按想象扩功能：训练/教练等若与白皮书排期冲突，先走文档变更再动代码。
4. 高热 **线上救火** MR 尽量不夹带本文 E/T/O/C 条目，便于回滚。

---

## 文档变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-13 | P1/E/T/O 核销快照；W7 会话列表标 Done；关联 W9 退款/beet、`docs/19`、W6/W10 roadmap 文档 |
| 2026-05-16 | 初始化：纳入并行工程 backlog，与用户对齐「列入计划」 |
