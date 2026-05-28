# Phase 2 · 开发 Sprint 计划（2026-05-27 起）

> **真源**：[`docs/19` §六](../19-产品开发迭代计划-当前队列.md#六全量未闭环开发计划合并清单) · MVP 一期已 **v1.2.13 收口**  
> **刚上线**：M9 装备 / M11 学习路径 / M12 球手库 / M13 约球**后端** + Phase2 flags

---

## Sprint 排期（默认 2 周一迭代）

| Sprint | 主题 | PLAN-ID / 模块 | 交付物 | 状态 |
|--------|------|----------------|--------|------|
| **W1** | **约球客户端** | P2-M13-05 UI | `meetupService` + 列表 / 详情 / 发起页；「我的」入口可点 | **✅ Done**（`0968422`） |
| **W2** | **画像 2.0** | P2-M9-03 UI | onboarding 2.0 + 画像编辑页（对接已有 `profile-v2` API） | **✅ Done**（`5f0e9df`） |
| **W3** | **常去球馆 + 考核** | P2-M9-05 · P2-M11-04 | 球馆选择 UI；阶段考核 mock → 真实现 | **✅ Done**（`2f69ff0`） |
| **W4** | **引擎续做** | P2-M7-10 · M7-14 · M7-N1 | YAML 规则 starter + V2 路由打通 + drill 文案 D-6 | **✅ Done**（待 commit） |

**并行泳道（不占 Sprint 主表）**：U-2 COS · Q-B5 papay · O-01/O-04 性能抽测 · par-E3/par-T1

---

## W1 · 约球客户端验收

| # | 验收项 |
|---|--------|
| 1 | `PHASE2_MEETUP_ENABLED=true` 时「我的 → 约球邀请」进入列表页，不再 toast |
| 2 | 列表分「全部 / 收到的 / 发出的」，展示状态与时间 |
| 3 | 详情页：被邀请人 pending 可接受/拒绝；邀请人 pending 可撤回 |
| 4 | 接受时可填会面备注（`note` / `meet_at`，不含手机号等） |
| 5 | 发起页：`?invitee=` 传入被邀请人 id；可选留言与时间 |
| 6 | `meetupService` Jest 单测覆盖 URL / method |

---

## W2 · 画像 2.0 验收

| # | 验收项 |
|---|--------|
| 1 | `PHASE2_PROFILE_V2_ENABLED=true` 时新用户走 **6 步** onboarding |
| 2 | 完成引导写入 `profile-v2` + v1 `onboarding_completed` |
| 3 | 「我的 → 我的画像」可查看/编辑并保存 |
| 4 | 伤病勾选有二次确认；`profileV2Mapping` 单测通过 |

---

## W4 · 引擎续做验收（本批为「起跑前置」交付）

| # | 验收项 |
|---|--------|
| 1 | `ai_engine/app/pipeline/rules/v2_starter.yaml` 含 5 条 V1→V2 入门规则；互斥矩阵双向声明 |
| 2 | `ai_engine/app/pipeline/locales/zh_CN.json` 每条规则都有 `.title` + `.summary` 模板 |
| 3 | `load_rules_from_yaml()` schema 校验 + `RuleEngine` 端到端 trigger / locale 渲染单测覆盖 |
| 4 | `ai_engine/app/pipeline/real_pipeline_v2.py` 暴露 `run_real_analysis_v2`/`diagnose_v2`；main.py 按灰度桶分流 |
| 5 | V2 资源加载失败 → fallback 到 V1，不影响线上 |
| 6 | `backend/app/services/chat_service.py` video_card title 后缀对齐前端 `· 教练示范`（D-6） |

> **本批不含**：13 V1 规则全量迁移、ECS 触发率验证（M7-10 W29-W33）；features dict 外提到 `diagnose_v2` 重诊（M7-14 W34）；drill 视频拍摄（M7-N1 Phase 2.1 W14-W17）。

---

## 文档债（W1 后补）

- [`docs/02`](../02-API接口设计文档.md) 增补 M13 约球 / venues 端点（后端已落地，文档未同步）

---

## 文档变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-27 | 初始化 W1–W4 Sprint；W1 约球 UI 开工 |
| 2026-05-28 | W1 ✅（`0968422`）；W2 画像 2.0 UI 开工 |
| 2026-05-28 | W2 ✅（`5f0e9df`）：6 步 onboarding + 我的画像编辑页 |
| 2026-05-28 | W3 ✅（`2f69ff0`）：常去球馆页 + 课程详情阶段考核 UI |
| 2026-05-28 | W4 ✅（待 commit）：M7-10 YAML loader + starter 5 规则 + locale；M7-14 `real_pipeline_v2` + main.py 灰度路由；M7-N1 D-6 修复 |
