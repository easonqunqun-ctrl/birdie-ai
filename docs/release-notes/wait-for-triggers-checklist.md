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
| **P-02** | 已完成 | 真实非高尔夫视频上传 ≥ 5 例 | 调 ENG-02 阈值 + 提 PR | AI 工程 |
| **W14-C** | runbook 就位 | V1/V2 真实流量分析 ≥ 20 case | 跑 v1_v2_diff.py + 出周报 | AI 工程 |
| **Q-B5** | 工程就位 | 商户产品自动续费签约通过 | 接 papay sign 流程 | 产品 + 财务 |
| **Q-D1** | 工程就位 | RN 端首发版本 (M3+) | 跑 client-check-rn 全栈 | 客户端工程 |
| **ENG-04** | 标定集就位 | 争议样本累计 ≥ 20 | 进 ECS 标定回归 + 跑 yaml 调参 | AI 工程 |
| **ENG-06** | 模板就位 | v2_count ≥ 5 且 1 条争议反馈/周 | 周更模板 → eng-06 系列 docs | 运营 + AI 工程 |
| **W18+** | 监控栈就位 | webhook-echo → 企业微信群机器人 | 改 alertmanager.yml receivers | DevOps |
| **W18+** | probe rewrite 就位 | 切 COS / OSS / 第三方对象存储 | 改 EXTRA_INTERNAL_URL_REWRITES env | DevOps |
| **W19+** | 朋友圈封面 layout 就位 | 产品决定接入 timeline 海报 | 实现 drawPosterTimeline + 接 poster.tsx | 客户端工程 |

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
1. 抽这 5 例 video，跑 `ai_engine/scripts/precheck_threshold_eval.py`（待写）
2. 对比"AI 拒绝"vs"人工标注"，看 false positive / negative
3. 调 `pre_check.py` 阈值 + 提 PR

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

**触发后动作**：
1. 把 20 条样本入 `docs/20` ECS 标定集
2. 跑 `ai_engine/scripts/calibration_regression.py`（待写）
3. 任何 issue 类型 F1 score 跌幅 > 5% → block PR
4. 调 yaml 阈值后，标定 F1 必须**全员**回到 baseline

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

**触发后动作**：
1. 在 `.env.local` 加：
   ```
   EXTRA_INTERNAL_URL_REWRITES=https://cos.example.com=http://internal-cos:443
   ```
2. 重启 ai_engine
3. 验证 `v2_probe_errors_5xx_after_retries` 仍为 0
4. 9/9 单测应该不需要改（已覆盖泛化路径）

### 2.11 W19+ 朋友圈封面海报

**触发条件**：
- [ ] 产品决定 v1.x 把朋友圈封面接入 share 链路

**触发后动作**：
1. 实现 `client/src/utils/posterCanvasTimeline.ts`（drawPosterTimeline）
2. `pages/analysis/poster.tsx` 加「分享变体」切换器（wxa / timeline）
3. layout 工具 + 22/22 单测已就位

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
