# 等触发清单 · Wait-for-Triggers Checklist

> **位置**：`docs/release-notes/wait-for-triggers-checklist.md`
> **配套**：`docs/19-产品开发迭代计划-当前队列.md` §6.3 主表
> **W17-E 收口**：把所有"工程已就位但等真实条件再上"的项**集中到一份**，
> 避免分散在多个 sprint plan 里失联。

---

## 0. 一句话原则

**工程上 ready 不等于产品上 ready。** 这份清单列出"代码合并了 / 测试过了 / 但要等某个**外部触发条件**才能上"的项。每条都明确：
1. 触发条件是什么（**可观测的**）
2. 触发后做什么（**清单步骤**）
3. 触发证据怎么记（**落到哪个 doc**）

---

## 1. 总览（按 PLAN-ID 排序）

| PLAN-ID | 工程状态 | 触发条件 | 触发后动作 | 责任人 |
|---|---|---|---|---|
| **O-01** | 已完成 | 体验版用户 ≥ 100 / 周活 ≥ 30 | 跑 NPS 调研 + 上「邀请有礼」运营 | 运营 |
| **O-04** | 已完成 | 教练 SaaS 上线（W19+） | 切「教练抽审」入口 | 产品 |
| **P-02** | 已完成（评估脚本就位） | 真实非高尔夫视频上传 ≥ 5 例 | 跑 `precheck_threshold_eval.py` → 调阈值 + 提 PR | AI 工程 |
| **W14-C** | runbook 就位 | V1/V2 真实流量分析 ≥ 20 case | 跑 v1_v2_diff.py + 出周报 | AI 工程 |
| **Q-B5** | 工程就位 | 商户产品自动续费签约通过 | 接 papay sign 流程 | 产品 + 财务 |
| **Q-D1** | 工程就位 | RN 端首发版本 (M3+) | 跑 client-check-rn 全栈 | 客户端工程 |
| **ENG-04** | 标定集 + 回归脚本就位 | 争议样本累计 ≥ 20 | 替换标定集 → 跑 `calibration_regression.py` F1 门禁 + 调 yaml | AI 工程 |
| **ENG-06** | 模板就位 | v2_count ≥ 5 且 1 条争议反馈/周 | 周更模板 → eng-06 系列 docs | 运营 + AI 工程 |
| **W18+** | 监控栈就位 | webhook-echo → 企业微信群机器人 | 改 alertmanager.yml receivers | DevOps |
| **W18+** | probe rewrite + 自检脚本就位 | 切 COS / OSS / 第三方对象存储 | 改 env → 跑 `cos_switch_selfcheck.py` 校验 → 重启 | DevOps |
| **W19+** | 朋友圈封面 layout 就位 | —（**已迁入 W19-A 开发计划**） | 实现 drawPosterTimeline + 接 poster.tsx | 客户端工程 |
| **M7-11-cal** | 推杆 pipeline 链路就位（W22-W25） | ECS 推杆 ≥10 段人工标注就位 | 回填 `putting/constants.py` ideal 区间 + 验 AC-3（与教练人评 r≥0.7） | AI 工程 |
| **M7-11-dx** | 推杆诊断 5 条已上 | M7-09 杆/球追踪 or 手腕角序列特征就位 | 补 putter-lift / 手腕翻折 / 回摆过短 / 减速/瞄准偏移 等诊断 | AI 工程 |
| **M7-12-cal** | 切杆 pipeline 链路就位 | ECS 切杆 ≥10 段人工标注就位 | 回填 `chipping/constants.py` ideal + 验 AC-2（r≥0.65） | AI 工程 |
| **M7-13-ui** | 多挥识别引擎链路就位（W28-W29） | —（**已迁入 W18-D 开发计划**） | 客户端 `select-swing.tsx` + detect-swings API（W18-C）+ `selected_swing_index` 回传（W18-B ✅） | 客户端 + AI 工程 |
| **M11-06-auth** | 教练定制课程写 API 就位（白名单） | —（**已迁入 W18-E**；M8-01 已合，`PHASE2_COACH_ENABLED` 开即走 active 教练校验） | 教练端课程编辑 UI（W18-E）；白名单仅 seed 兜底 | 后端 + 客户端 |
| **M10-04-videos** | drill 库 25 条 + category 就位 | DEP-02 教练 BD + DEP-03 拍摄团队交付 12–17 段示范视频 | 回填 `drills.video_url` + `DRILL_VIDEO_ALIGNED_IDS` 灰度名单 | 教研 + 运营 |
| **M7-01-ecs** | ECS v2 标定集骨架 | ≥50 段全挥杆 + 推杆/切杆各 ≥10 段教练标注 | 训练 ECS v2 + 回填 ideal/threshold | AI 工程 |
| **M7-07-nn** | NN 本体占位（W23–W30） | 标定集 + ML 基建（GPU/训练管线） | 替换 rule-based 分段/评分子模块 | AI 工程 |
| **M7-08-features** | 新特征设计 doc 就位 | ECS 特征相关性验收 | 接入 V2 feature 矩阵 | AI 工程 |
| **M7-09-tracking** | YOLO 杆/球追踪 stub | 标注集 + 微调权重 | 替换 wrist-proxy 杆面/触球特征 | AI 工程 |
| **M7-15-feedback** | 反馈池 schema stub | 产品定反馈 UX + 存储合规 | 启用 in-app 纠错回流 | 产品 + AI 工程 |
| **M7-16-llm** | LLM 个性化 prompt stub | DeepSeek/Qwen key + 隐私评审 | 报告话术个性化 | AI 工程 |
| **M14-store** | RN 1:1 / IAP 备忘 doc | App Store + 安卓市场资质 + Apple IAP 合同 | 上架发版 runbook 执行 | 运营 + 客户端 |

---

## 2. 详细触发条 + 检查表

### 2.1 O-01 · NPS 调研 + 邀请有礼运营

**触发条件**（必须**同时**满足，**任一**指标在 Prometheus 看到）：
- [ ] 体验版总用户数 ≥ 100
- [ ] 周活跃用户数（distinct user_id 7d 内任意 API call）≥ 30

**触发后动作**：
1. 在 `users.created_at` 选最近 30d 的用户，发 `wechat_subscribe_message` 邀请 NPS
2. 在 in-app 启「邀请好友双方各得 1 次免费分析」运营
3. 跑 v3 数据看板，记 NPS 分数 + 留存

**触发证据**：
- 落 `docs/release-notes/o-01-nps-launch-W{N}.md`
- 进 `docs/19` §四 完成度回填

### 2.2 O-04 · 教练抽审入口切真

**触发条件**：
- [ ] 教练 SaaS 后台上线（W19+ 计划，依赖 par-E1-coach 系列）
- [ ] 至少 3 名教练完成入驻测试

**触发后动作**：
1. `meetup_service` 解锁「教练抽审」分支
2. AI 报告页底部「请教练复核」按钮 → 走 educator API
3. 抽审样本进 ENG-06 周更

### 2.3 P-02 · 非高尔夫视频拒绝阈值调优

**触发条件**：
- [ ] 真实用户上传非高尔夫视频 ≥ 5 例（看 ENG-02 metrics `pre_check_rejected_count`）

**触发后动作**：
1. 抽这 5 例 video，人工补 `label`（block/pass）列成 CSV，跑 `ai_engine/scripts/precheck_threshold_eval.py`（**✅ 已就位**，纯逻辑 `app/pipeline/precheck_eval.py`，单测 `tests/test_precheck_eval.py`）：
   ```bash
   # 容器内
   python scripts/precheck_threshold_eval.py \
       --input-csv samples_labeled.csv \
       --out-csv reports/precheck_eval.csv \
       --report-md reports/precheck_eval.md
   ```
2. 报告直接给混淆矩阵：**FP=误杀**（拦了正常视频，伤体验）/ **FN=漏拦**（放过该拦的，浪费配额），并按 `error_code` 分桶定位调哪个硬门槛
3. 调 `app/pipeline/precheck.py`（沿用 `preprocess.py` 的硬门槛常量）阈值 + 提 PR

### 2.4 W14-C · V1/V2 Diff 真实流量

**触发条件**：
- [ ] 真实流量 V1 + V2 对比样本 ≥ 20（CVM 上 V2 流量比例 ≥ 50% 且 v2_count ≥ 20）

**触发后动作**：跑 `docs/release-notes/v1-v2-diff-real-traffic.md` runbook
1. ssh CVM → `docker exec xiaoniao-ai-engine python scripts/v1_v2_diff.py --recent 20`
2. 输出 csv → 落 `docs/release-notes/v1-v2-diff-W{N}-{date}.csv`
3. 标记发散最大的 5 条 → 进 ENG-06 周更样本

### 2.5 Q-B5 · 自动续费签约

**触发条件**：
- [ ] 商户号申请「自动续费扣款」产品权限通过
- [ ] 商户后台拿到 `papay` 模板 ID

**触发后动作**：
1. 在 `payment_service.py` 接 `papay_contract_id` 写入流程
2. `pages/profile/membership.tsx` 接「开通自动续费」按钮
3. 跑 `test_payments.py` 22 个用例 + 真机一笔扣款冒烟

### 2.6 Q-D1 · RN 端首发

**触发条件**：
- [ ] M3+ 客户端 RN 端排期启动
- [ ] taro-native-shell W18+ 升级到 RN 0.74+

**触发后动作**：
1. `make client-bootstrap-rn-shell`
2. `make client-check-rn` 全栈过
3. 真机（iOS + Android 各一台）冒烟
4. App Store / Google Play 上传

### 2.7 ENG-04 · 标定集回归

**触发条件**：
- [ ] 争议样本累计 ≥ 20 条（来自 ENG-06 周报汇总）

**触发后动作**（脚本 **✅ 已就位**：纯逻辑 `app/ecs/calibration.py`，CLI `scripts/calibration_regression.py`，单测 `tests/test_calibration.py`，CI 端到端冒烟跑随仓库分发的 stub 标定集）：
1. 把 20 条样本（真实授权 + 人工标注 `expected_issues`）替换 `tests/ecs/v1/calibration_manifest.json` 的 clips，并重生成 baseline：
   ```bash
   python scripts/calibration_regression.py \
       --manifest tests/ecs/v1/calibration_manifest.json \
       --out-baseline tests/ecs/v1/calibration_baseline.json
   ```
2. 改 yaml 阈值后跑回归门禁（任一 issue 类型 F1 跌幅 > 5% → **退出码 1，block PR**）：
   ```bash
   python scripts/calibration_regression.py \
       --manifest tests/ecs/v1/calibration_manifest.json \
       --baseline tests/ecs/v1/calibration_baseline.json \
       --report-md reports/calibration_regression.md
   ```
3. 调 yaml 阈值后，标定 F1 必须**全员**回到 baseline（门禁绿灯）

> **注**：当前 `calibration_manifest.json` 是**合成 Pose 行为快照 stub**（非授权人工标注），与既有 `manifest.json` / `baseline_snapshot.json`（scoring 漂移）的合成约定一致——只为把 F1 harness 端到端跑通 + CI 防回归。触发后用真实授权样本替换。本线与 `app/ecs/regression.py`（scoring 漂移）**正交**。

### 2.8 ENG-06 · 争议样本周更

**触发条件**：
- [ ] 当周 `v2_count ≥ 5`（保证有讨论基础）
- [ ] 当周收到至少 1 条争议反馈（in-app / 教练 / 客服任一）

**触发后动作**：见 `docs/release-notes/eng-06-disputed-sample-weekly-template.md`

### 2.9 W18+ webhook-echo 替企业微信群机器人

**触发条件**：
- [ ] 申请到企业微信群机器人 webhook URL
- [ ] 测试群已建好

**触发后动作**：见 `docs/release-notes/monitoring-runbook.md` §4

### 2.10 W18+ probe rewrite 接 COS

**触发条件**：
- [ ] 业务侧决定从 MinIO 切到腾讯云 COS / 阿里云 OSS / 七牛 KODO 之一

**触发后动作**（自检脚本 **✅ 已就位**：`ai_engine/scripts/cos_switch_selfcheck.py`，纯逻辑可单测 `tests/test_cos_switch_selfcheck.py`）：
1. 在 `.env.local` 加（多对用 `;` 分隔）：
   ```
   EXTRA_INTERNAL_URL_REWRITES=https://cos.example.com=http://internal-cos:443
   ```
2. **重启前**先离线自检（不发网络，只校验 env 改写配置 + 退出码门禁）——typo / 漏域名会让公网 URL 悄悄不改写、重现 W13-C 5xx：
   ```bash
   # 容器内：用真实 .env 校验一条 COS 示例 URL 会被改写到内网，否则退出码 1
   python scripts/cos_switch_selfcheck.py \
       --url 'https://cos.ap-guangzhou.myqcloud.com/birdie/uploads/x.mp4' \
       --expect-internal 'http://internal-cos:443' --require-match
   # what-if：不动真实 env，先试候选配置
   python scripts/cos_switch_selfcheck.py --rewrites '<候选 EXTRA_INTERNAL_URL_REWRITES>' \
       --url '<示例公网 URL>' --require-match --strict-config
   ```
3. 重启 ai_engine
4. 验证 `v2_probe_errors_5xx_after_retries` 仍为 0
5. 单测已覆盖泛化路径（rewrite 逻辑 + 本自检脚本），切换本身**不需要改代码**

### 2.11 W19+ 朋友圈封面海报

**触发条件**：
- [ ] 产品决定 v1.x 把朋友圈封面接入 share 链路

**触发后动作**：
1. 实现 `client/src/utils/posterCanvasTimeline.ts`（drawPosterTimeline）
2. `pages/analysis/poster.tsx` 加「分享变体」切换器（wxa / timeline）
3. layout 工具 + 22/22 单测已就位

### 2.12 M7-11-cal · 推杆特征 ideal 区间 ECS 标定

**触发条件**：
- [ ] ECS 采集到推杆视频 ≥10 段，且每段有教练人评分（0-100）

**触发后动作**：
1. 跑现有 pipeline 抽取 4 特征（pendulum/head/face/tempo）落 CSV
2. 用人评分回归校准 `ai_engine/app/pipeline/putting/constants.py` 里 4 特征的 `ideal_min/ideal_max/tolerance`（当前为归一化 v0.1 占位）
3. 验 **AC-3**：putting overall 与教练人评 **r≥0.7**；不达标继续调

> **注**：当前 ideal 阈值是 kickoff §3.2 px 草案改写的归一化占位，**未用任何假数据污染**（沿用 W14-C 原则）。

### 2.13 M7-11-dx · 推杆诊断剩余规则

**触发条件**（任一）：
- [x] M7-09 杆头/球追踪就位（提供杆头轨迹、putter-lift 信号）<!-- 部分：lift 仍用腕代理 -->
- [x] 新增手腕角时序特征（wrist hinge series）<!-- TRIGGERED 2026-05-30 W20-A -->

**触发后动作**：
1. 在 `ai_engine/app/pipeline/putting/diagnose.py` 补 kickoff §3.5 草案剩余项：杆头抬起 / 手腕翻折 / 回摆过短 / 减速击球 / 瞄准偏移
2. 每条配阈值 + 单测；现有 5 条（钟摆/头部/杆面/急/慢）已上线

> **W20-A Done**：`signals.py` 提取 5 个时序信号 + diagnose 共 10 条 rule；`putter_lift` 仍用主腕 y 代理，M7-09 到位后可替换。

### 2.14 M7-12-cal · 切杆特征 ideal 区间 ECS 标定

**触发条件**：
- [ ] ECS 采集到切杆视频 ≥10 段，且每段有教练人评分

**触发后动作**：
1. 跑 pipeline 抽取 3 特征落 CSV
2. 校准 `ai_engine/app/pipeline/chipping/constants.py` ideal 区间（当前 v0.1 占位）
3. 验 **AC-2**：overall 与教练人评 **r≥0.65**

### 2.15 M7-13-ui · 多挥候选 UI + 缩略图

**触发条件**（任一）：
- [ ] 产品确认 select-swing 交互稿（kickoff §3.4）
- [ ] M10 训练扩展页排期就位（与推杆/切杆 UI 同批）

**触发后动作**：
1. 客户端新增 `pages/analysis/select-swing.tsx`：展示 `swing_candidates` + 试挥标签 + 默认勾选第一段非试挥
2. AI 工程 / 后端：ffmpeg 按候选区间抽帧缩略图（kickoff W30）
3. 分析请求回传 `selected_swing_index`；已有引擎字段 `swing_candidates` / `50122` 无需再改

> 引擎侧 W28-W29（`multi_swing.py` + full_swing 路由 + 50122 + 单测）已合；UI 与 ECS 准确率验收（AC-1/AC-3）等真实样本。

### 2.16 M11-06-auth · 教练定制课程 UI + 认证切流

**触发条件**（任一）：
- [ ] M8-01 教练认证 API + 角色字段就位
- [ ] 教练端课程编辑页排期（M8-05/06 作业与看板同批）

**触发后动作**：
1. `COACH_COURSE_USER_IDS` 白名单切 `User.is_coach` / JWT claim 校验
2. 客户端教练端：创建 / 编辑 / 发布定制课程 UI（对接已有写端点）
3. 学员侧课程详情标注「教练定制」来源（`created_by_user_id` 非空）

> 写 API（M11-06）已合；当前仅 seed 教练 user_id 白名单可写。

---

## 3. 维护契约

- **每月 1 次**（每月 1 号）：扫一遍本表，把已触发的项移到 `docs/19` §四 完成度
- **触发即更新**：发现某条触发了，立即在该条加 `<!-- TRIGGERED at YYYY-MM-DD -->` 标记 + 落对应执行 doc
- **不要扩散**：新加"等触发"的项**只**进本表，不要散落在 sprint plan 里

---

## 4. 反模式（不要做）

- ❌ 等触发条件**永远不可观测**（如「等用户体验好」「等市场成熟」）
- ❌ 触发后动作**没有 owner**（"看情况再说"）
- ❌ 工程未就位就放进本清单（本清单只接"代码已合，等条件"，不接"还没开发"）
- ❌ 一条多触发条件**全部**满足才动作（除非真的有依赖；否则拆成多条）
