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
| **W4** | **引擎续做** | P2-M7-10 · M7-14 · M7-N1 | YAML 规则 starter + V2 路由打通 + drill 文案 D-6 | **✅ Done**（`e618a77`） |
| **W5** | **引擎深耕** | P2-M7-10 · M7-14 | V1→V2 全量 14 规则迁 YAML；features dict 外提让 V2 真正重诊 | **✅ Done**（`6afffda` · backend hotfix `a37499a`） |
| **W6** | **V2 灌溉** | ENG-A1 · ENG-A2 · ENG-A3 | metrics 观测 + redis 热改 pct + 离线 V1/V2 diff 脚本 | 🚧 In Progress |

**并行泳道（不占 Sprint 主表）**：U-2 COS · Q-B5 papay · O-01/O-04 性能抽测 · par-E3/par-T1

**线上灰度状态**：W5 部署后 V2 pct=5（`.env.local`，CVM 容器内验证 1000 user_id → 49 命中 V2 ≈ 4.9%）。

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

## W5 · 引擎深耕验收

| # | 验收项 |
|---|--------|
| 1 | `v2_starter.yaml` 扩到 14 条规则，覆盖 V1 `_RULES` 全部 issue（`grip_weak` 占位除外） |
| 2 | 每条规则带 `phase_anchor`（setup/backswing/top/downswing/impact/follow_through），schema 校验非法值 |
| 3 | `locales/zh_CN.json` 14 条 `.title` + `.summary` 模板齐全 |
| 4 | 互斥矩阵：`early_extension`↔`loss_of_posture`、`over_rotation`↔`under_rotation`、`flat_shoulder`↔`steep_shoulder`、`loss_of_posture`↔`sway_slide` 全部双向 |
| 5 | `real_pipeline.run_real_analysis(diagnose_fn=...)` 可注入诊断实现；`run_real_analysis_v2` 注入 `diagnose_v2` 真正用 YAML 重诊 |
| 6 | `diagnose_v2` 接受 `PhaseSegmentResult` 并按 `phase_anchor` 填 `key_frame_timestamp` |
| 7 | V2 资源加载失败 → `diagnose_fn=None` → 回落 V1 `diagnose` |
| 8 | 新增单测：YAML 全集与 V1 `_RULES` 类型集合对齐、phase_anchor / locale summary 全覆盖、key_frame_timestamp 端到端 |

> **仍留 backlog**：ECS 影子流量比对（M7-10 W34 AC-1）；P2-M7-02 engine_warnings + P2-M7-06 issue_confidence 三层模型（W34）。

---

## W6 · V2 灌溉验收

> **目标**：让 V2 灰度可观测、可热改、可定量对比，**为推 50% → 100% 铺路**。

| # | 验收项 |
|---|--------|
| 1 | `ai_engine` 内进程级计数器：`v1_count` / `v2_count` / `v2_errors` / `v1_errors`；新增 `GET /metrics` 返回 JSON（含 pct + 各计数 + uptime_s） |
| 2 | `analyze_done` structlog 字段含 `engine_version`（已在 W4 落地）；本批补 `engine_v2_fallback` warning（V2 资源加载失败回落 V1 时） |
| 3 | `ai_engine/pyproject.toml` 新增 `redis>=5,<6`；`set_rollout_pct` 写 Redis 成功（不再 `ModuleNotFoundError`），多容器场景下 60s TTL 内全 ai_engine 实例对齐 |
| 4 | `/admin/engine-rollout` 端点支持可选 `X-Admin-Token` 鉴权（环境变量 `AI_ENGINE_ADMIN_TOKEN` 配置；未配则保持向后兼容允许内网调用） |
| 5 | `scripts/v1_v2_diff.py`：输入 N 个 swing_analysis_id → 各以 `force_engine_version` 强制跑 V1 / V2 → 输出 diff CSV（issues 类型集合 / 各 issue severity / overall_score）+ 一致率汇总 |
| 6 | 单测：metrics 计数器 race-safe、Redis 路径 mock 注入、`/admin/engine-rollout` 鉴权 401/200 路径 |
| 7 | 生产 smoke：`curl http://ai_engine:9100/metrics` 看到 v1/v2 计数随真实流量增长；CVM 内 `python -c "set_rollout_pct(5)"` 写入 Redis 成功 |

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
| 2026-05-28 | W4 ✅（`e618a77`）：M7-10 YAML loader + starter 5 规则 + locale；M7-14 `real_pipeline_v2` + main.py 灰度路由；M7-N1 D-6 修复 |
| 2026-05-28 | W5 ✅（`6afffda`）：YAML 全量 14 规则 + `phase_anchor` + `diagnose_fn` 注入；V2 通过 features 真正重诊。backend hotfix `a37499a` 修 W3 `lessons.py` import 错路径 |
| 2026-05-28 | W5 部署：`make publish-backend-cvm`；`.env.local` 加 `M7_V2_ROLLOUT_PCT=5`，V2 灰度 5% 生效；W6 V2 灌溉开工 |
