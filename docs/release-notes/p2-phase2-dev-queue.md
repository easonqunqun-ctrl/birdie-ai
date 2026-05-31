# Phase 2 · 开发队列（W21 起 · 可执行总表）

> 版本：v0.1 · 2026-05-30  
> 产品真源：[`docs/21`](../21-二期产品需求规划.md) · 可编码 FR：[`docs/23`](../23-二期可编码规格说明书.md)  
> 已交付 Sprint：[`p2-phase2-sprint-plan.md`](./p2-phase2-sprint-plan.md) W1–W20  
> **等触发**（样本/拍摄/商户）：[`wait-for-triggers-checklist.md`](./wait-for-triggers-checklist.md)

---

## 一、怎么用这张表

| 列 | 含义 |
|----|------|
| **Sprint** | 建议迭代编号（约 2 周一 Sprint，可并行） |
| **PLAN-ID** | 站会引用；与 `docs/19` §6.3 互链 |
| **可做** | **Now** = 无外部依赖可开工；**Trigger** = 等样本/拍摄/商户；**Ops** = 发版/运营 |
| **状态** | ✅ Done · 🔧 代码在库待验 · 📋 Planned · ⏳ Trigger |

> **说明**：W18–W20 多项已在 repo/CVM 落地，但 docs/21 部分仍标 📋——以本表「代码审计」列为准。

---

## 二、代码审计 · 二期模块真实状态（2026-05-30）

| 模块 | 代码锚点 | 审计结论 |
|------|----------|----------|
| **M7-11 推杆引擎** | `ai_engine/.../putting/*` + 10 条诊断 | ✅ CVM 已发 |
| **M7-12 切杆引擎** | `ai_engine/.../chipping/*` + main 路由 | ✅ 单测齐；CVM 已发 |
| **M7-13 多挥** | detect-swings + select-swing | ✅ |
| **M10-01 推杆 UI** | `ModeSelector` · `PuttingReport` · `params.tsx` | 🔧 已实现；体验版 smoke 待验 |
| **M10-02 切杆 UI** | `ChippingReport` · mode 分支 | 🔧 同上 |
| **M10-03 yardage** | API + `yardage-book/index` + inference | 🔧 已实现；编辑流 polish 可排 |
| **M10-04 drill 库** | Alembic `0041`–`0044` + category | ✅ **30 条**；tips 齐；**视频**仍空 |
| **M10-05 训练类目** | `issue_category.py` + training_service | 🔧 后端已接；LLM prompt 抽测待验 |
| **M11-06 定制课** | coach/courses/* | ✅ W18-E |
| **M8 批注 + M12-09** | `analysis-annotate` + ProClipPicker | 🔧 页面在库；真机+素材 smoke |
| **M12-08 演化动画** | `SkeletonAnimation` · pro-compare | ✅ W25 |
| **M9-02 装备 UI** | `profile/clubs.tsx` | 🔧 在库 |
| **监控 PushPlus** | bridge + CVM token | ✅ |

---

## 三、主队列（按推荐开发顺序）

### Batch-A · 发版收口（优先，1 Sprint）

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W21-A** | P2-W21-A | **Git 合流 + 体验版** | commit + push；CLI 上传 **1.2.18** | Ops | **✅ Done** |
| **W21-B** | P2-W21-B | **Phase2 体验版 Smoke** | 见 [`experience-version-smoke-runbook`](./experience-version-smoke-runbook.md) §D Phase2 | Ops | **🔧 真机待验** |
| **W21-C** | P2-W21-C | **xpay 真机冒烟** | `xpay_smoke_check.py` | Ops | **🔧 脚本 OK · 真机待验** |
| **W21-D** | P2-W21-D | **CVM git 整理** | `REMOTE_GIT_PULL=no` rsync 发版 | Ops | **📋 待整理** |
| **W21-E** | DOC-P2-01 | **docs/21/23 状态回填** | 已合入 | Now | **✅ Done** |

---

### Batch-B · 短杆闭环抛光（引擎已就绪）

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W22-A** | P2-M10-01-smoke | 推杆 mode E2E | params→分析→PuttingReport；50123 toast | Now | **✅ 代码 · smoke 待验** |
| **W22-B** | P2-M10-02-smoke | 切杆 mode E2E | 同上 + wedge 联动 | Now | **✅ 代码 · smoke 待验** |
| **W22-C** | P2-M7-13-thumb | 多挥候选缩略图 | backend/ffmpeg 按区间抽帧；select-swing 展示 thumb | Now | **✅ 代码已合** |
| **W22-D** | P2-M10-03-polish | yardage 编辑闭环 | yardage-book 页 PUT 自填码数 + 反推展示 polish | Now | **✅ 代码已合** |
| **W22-E** | P2-M10-05-smoke | 训练计划短杆 drill | putting issue → putting drill 端到端 pytest + 1 条 jest | Now | **✅ pytest+jest** |

---

### Batch-C · 教练与 Pro 体验

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W23-A** | P2-M8-05 | 教练批注 smoke | analysis-annotate 文字批注 CRUD 真机路径 | Now | **🔧 删除+单测；真机待验** |
| **W23-B** | P2-M12-09 | Pro clip 引用 smoke | ProClipPicker → 学员侧展示引用卡 | Now | **🔧 组件单测；真机待验** |
| **W23-C** | P2-M8-06 | 作业布置 polish | `task-assign` UX + 与 training 任务联动验收 | Now | **✅ 类目筛选+联动** |
| **W23-D** | P2-M8-session | 课后 recap | `session-recap` 与批注/作业串联 smoke | Now | **✅ 快捷入口+runbook** |

---

### Batch-D · 增长与引擎观测

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W24-A** | P2-V2-ROLLOUT | V2 灰度上调 | CVM `M7_V2_ROLLOUT_PCT` 5→25→50；盯 Prometheus 7d | Now | **🔧 R0 维持 · R1 待 7d** |
| **W24-B** | P2-W14-C-exec | 真实流量 diff | 满足 runbook 触发后跑 `v1_v2_diff.py` | Trigger | ⏳ |
| **W24-C** | P2-MON-05 | `make publish-monitoring-cvm` | 发版脚本同步 infra/monitoring（可选） | Now | **✅ Done** |
| **W24-D** | ENG-06-exec | 争议样本周更 | 首版 [`eng-06-W24-2026-05-29.md`](./eng-06-W24-2026-05-29.md) | Now | **✅ Done** |

---

### Batch-E · M12 演化动画（纯前端，可独立）

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W25-A** | P2-M12-08-01 | 骨骼插值 util | `poseInterpolate.ts` + `posInterpolate.ts` + jest | Now | **✅ Done** |
| **W25-B** | P2-M12-08-02 | SkeletonAnimation 组件 | pro-compare 演化区块 + 三态切换 | Now | **✅ Done** |
| **W25-C** | P2-M12-08-03 | 失败降级 | 无 pose → DualRadarChart morphProgress | Now | **✅ Done** |

Kickoff：[`p2-m12-08-evolution-animation-kickoff.md`](./p2-m12-08-evolution-animation-kickoff.md)

---

### Batch-F · 内容与教研（部分可先做文案）

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **W26-A** | P2-M10-04-copy | drill 文案质检 | 全库 tips（0043 短杆 + **0044 全挥杆**） | Now | **✅ Done** |
| **W26-B** | P2-M10-04-video | 13+ 专属示范视频 | 拍摄 → MinIO → `DRILL_VIDEO_ALIGNED_IDS` | Trigger | ⏳ |
| **W26-C** | P2-M10-04-seed | drill 补至 30 | Alembic 0043+**0044**（**30 条**） | Now | **✅ Done** |

---

### Batch-I · 全挥杆 2D 感知准确度（优先于 ECS 标定）

> Kickoff：[`p2-m7-r1-rotation-perception-accuracy-kickoff.md`](./p2-m7-r1-rotation-perception-accuracy-kickoff.md) · FR：[`docs/23` §3.14](../23-二期可编码规格说明书.md#314-p2-m7-r1--全挥杆-2d-感知准确度)

| Sprint | PLAN-ID | 事项 | 交付物 | 可做 | 状态 |
|--------|---------|------|--------|------|------|
| **R1** | P2-M7-R1-A | Phase A 止血 | sanity + auto-detect sanitize + 矛盾合并 + setup/top 窗口 + R2 CI | Now | ✅ repo · 待真视频 + smoke |
| **R2** | P2-M7-R1-B1 | pose_refine + rotation_track 融合 | `pose_refine.py` + `rotation_track.py` + AC-B | Now | ✅ B1–B5 repo · AC-B1 infra · AC-B2 真视频 |
| **R3** | P2-M7-R1-B2 | top 双证据 + preprocess_v2 灰度 | 接 M7-09 后 refine impact 窗 | Now / Trigger | ✅ B5 + B7 router · flag off |

**并行**：R1 与 W24 V2 灰度可并行；**R1 必须在 R2 之前发版**（先止血再抬准度）。

---

### Batch-G · 引擎标定与追踪（等样本）

| Sprint | PLAN-ID | 事项 | 触发条件 | 可做 | 状态 |
|--------|---------|------|----------|------|------|
| **W27-A** | P2-M7-11-cal | 推杆 ideal ECS | ECS 推杆 ≥10 + 教练评分 | Trigger | ⏳ |
| **W27-B** | P2-M7-12-cal | 切杆 ideal ECS | ECS 切杆 ≥10 | Trigger | ⏳ |
| **W27-C** | P2-M7-09 | 杆/球 YOLO 追踪 | 标注集 + 权重 | Trigger | ⏳ |
| **W27-D** | ENG-04-full | ECS v1 满编 | 授权样本 ≥50 | Trigger | ⏳ |

---

### Batch-H · 商户 / 合规 / RN（二期边界外或长周期）

| Sprint | PLAN-ID | 事项 | 阻塞 | 可做 | 状态 |
|--------|---------|------|------|------|------|
| — | Q-B5 | 委托扣费 / papay 签约 | 微信商户模板 | Trigger | ⏳ |
| — | Q-D1 | RN App 里程碑 | 人力 | 并行 | 📋 |
| — | U-2 | COS 真桶验收 | 运维 | Ops | 📋 |

---

## 四、推荐执行顺序（给排期会）

```text
W21 发版收口（体验版 + smoke + git + 文档回填）
  → W22 短杆/多挥/yardsge 抛光（Now，引擎/UI 已在库）
  → W23 教练/Pro 批注 smoke
  → W24 V2 灰度 + 监控发版脚本 + ENG-06
  → W25 M12-08 演化动画
  → W26 drill 文案/seed（视频等拍摄 Trigger）
  → R1–R3 M7-R1 2D 感知准确度（Batch-I，优先于 ECS 标定）
  → W27+ ECS/追踪（样本 Trigger 并行）
```

**并行泳道**（不占主 Sprint）：U-2 COS · Q-B5 papay · Q-D1 RN · 拍摄团队 W26-B · **Batch-I R1 止血**

---

## 五、验收门禁（每个 Sprint 结束）

1. 改动同步 [`docs/02`](../02-API接口设计文档.md) / [`docs/23`](../23-二期可编码规格说明书.md) FR 状态列  
2. 客户端 `services/`/`components/` 改动 → Jest（`docs/07` §2.1）  
3. 体验版相关 → 更新 [`experience-version-smoke-runbook.md`](./experience-version-smoke-runbook.md) 勾选  
4. CVM 发版 → `make publish-backend-cvm`（git 冲突时 `REMOTE_GIT_PULL=no`）

---

## 六、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-30 | 初版：W21–W27 可开发项全量入队；代码审计修正 M10-01/02/03、M7-12 等「已在库」状态 |
| v0.2 | 2026-05-30 | W21–W25 状态回填；W26-A/C 0043 drill tips+seed（29 条） |
| v0.4 | 2026-05-30 | Batch-I R1 Phase A → ✅ repo · 待体验版 smoke |
| v0.3 | 2026-05-30 | Batch-I P2-M7-R1 全挥杆 2D 感知准确度队列 + kickoff 互链 |
