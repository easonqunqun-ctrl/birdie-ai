# 体验版一轮测试 · 操作备忘

> **目的**：在微信公众平台里发**体验版**前/后，用固定顺序跑一轮，减少「能上转但主路径炸」的情况。  
> **与正式上线区别**：体验版仍可临时开「不校验合法域名」做开发机联调；**真机验收**应以已配置 **request 合法域名**为准关项再验一遍。

---

## 当前体验版基线（2026-05-31 · M7-R1 B5）

| 项 | 值 |
|----|-----|
| **小程序版本** | **1.2.28**（构建后上传；公众平台 **选为体验版**） |
| **API** | `https://api.birdieai.cn/v1` |
| **CVM** | M7-R1 B5（`1e53615` · top 双证据）+ 1.2.27 机位预选 |
| **待验** | 本节 **§M7-R1**（含 `top_frame_mismatch` 报告文案） |

**发版后必做**：mp 后台 → **版本管理 → 1.2.28 → 选为体验版** → 真机扫码 → 重跑 face-on 样本，确认转肩读数与 B5 提示。

**AC-A1 真视频**：`test_rotation_regression_real.py` 2 passed（本地 `dtl_iron_01` + `face_on_iron_01`）；**AC-B1** 连拍 CV 见 `test_rotation_repeatability.py`（需 `take1–3` fixture）。

---

## A. 本机自动化（发版前先绿）

在仓库根目录：

```bash
# 可选：起全栈（无则跳过 health / 集成测试）
make up

# 后端
make backend-lint
make backend-test   # 含 test_analysis_soft_delete；需 Postgres/Redis 已起

# AI 引擎 · P2-M7-R1 旋转感知（发版前快测，~1min）
make ai-engine-test-rotation

# 客户端
cd client && pnpm type-check && pnpm lint
pnpm build:weapp    # 或体验环境用 pnpm build:weapp + 对应 env
```

**本次会话已在本机验证**（以你机器当时状态为准）：`pnpm tsc`、`pnpm build:weapp` 通过；若本机已 `make up`，`GET http://localhost:8000/v1/health` 为 200。

---

## B. 体验版专用环境（与正式包区分）

| 场景 | 客户端 env | 说明 |
|------|------------|------|
| 连 **HTTPS 测试域**（真机） | `client/.env.development.local` 或单独 `TARO_APP_API_BASE_URL=https://…/v1` | 域名须已在公众平台 **request 合法域名** 登记 |
| 仅开发者工具 + 本机 | 默认 `http://localhost:8000/v1` | 真机不可用 |
| 走生产 API 的体验包 | 使用 `client/.env.production` + `make client-build-weapp-prod` | 与 [go-live-weapp-fool-checklist](./go-live-weapp-fool-checklist.md) 一致 |

**后端**（体验环境）：`WECHAT_MOCK_LOGIN=false` + 真实小程序 AppID/Secret；内测可加 `QUOTA_MODE=unlimited`（见 [W8-preflight-checklist](./W8-preflight-checklist.md)）。

---

## C. 微信侧操作（需人工）

1. 微信开发者工具 → 打开工程根 **`client`**，`miniprogramRoot` → **`dist`**。  
2. **上传** → 登录公众平台 → **管理 → 版本管理 → 选为体验版** → 添加体验成员。  
3. 真机扫码打开体验版。

---

## D. 体验版 Smoke（建议按序勾）

### 账号与首页

- [ ] 登录成功（非 mock 环境须真 `code` 换 openid）
- [ ] 首页 / Tab 切换无白屏

### 分析主路径

- [ ] 拍摄或选视频 → 上传 → **等待页**（渐变、倒计时、阶段条正常）
- [ ] 报告页 loads；分享报告（若有）可被另一账号打开或脱敏页 404 行为符合预期

### 分析报告软删除（若本版已含）

- [ ] **历史列表**删除一条已完成/失败记录 → 列表消失、`total` 变少
- [ ] 同一条详情 **404**；进行中分析删除应提示不可删（或 40092）
- [ ] **公开分享链接**对已删报告为 404（先分享再删测一次）

### 会员 / 支付（按环境）

- [ ] `mock_mode=true`：模拟支付弹窗 → 确认后会员生效  
- [ ] `mock_mode=false`：拉起真实 `requestPayment`（小额）→ 「我的」会员态与订单

### P2-M7-R1 · 旋转感知 Phase A（2026-05 体验版建议勾）

前置：体验包含 M7-R1 改动（拍摄页机位引导、detect-swings 机位预选、报告「机位说明」）。

**自动化（发版前）**

```bash
make ai-engine-test-rotation
cd client && pnpm exec jest src/constants/__tests__/qualityWarnings.test.ts src/utils/__tests__/suggestedCameraAngle.test.ts src/utils/__tests__/measurabilityNotice.test.ts
```

**真机 / 体验版**

- [ ] **拍摄页** 出现「机位怎么选？」（正面测转肩 / 侧面跳过旋转）
- [ ] 上传 **侧面转播感** 视频 → 报告 **无**「转肩仅 3°/155°」类荒谬 issue 文案
- [ ] 侧面报告：TrustBadge 下有 **机位说明**（转肩类已跳过）或 **拍摄提示** 含 `rotation_reading_unreliable` 语义
- [ ] 正面 7 铁自拍：不应出现 **severity≥medium** 的 `under_rotation`（明显转肩场景）
- [ ] full_swing 进 **params 页** 后后台识别机位 → **拍摄角度默认选中** + 说明条「已识别为…，可手动调整」（与默认不同时另有 toast）
- [ ] face-on 腕 top 与肩转峰值不一致时：报告 **拍摄提示** 含「顶点时刻与转肩峰值不完全一致」（`top_frame_mismatch`）
- [ ] （可选）多挥视频 → detect-swings 后机位与创任务参数一致

**红灯**

| 现象 | 查 |
|------|-----|
| 侧面仍报转肩不足/155° X-Factor | CVM ai_engine 是否已 `publish`；V2 桶是否走新 pipeline |
| 报告仍显示「肩转 3°」 | `rotation_issue_copy` / sanitize 是否生效 |
| 无机位说明 | `report.camera_angle` + `quality_warnings` 是否回传 |

### Phase2 短杆 / 多挥（W18–W22，体验版必勾）

- [ ] 拍摄页 **ModeSelector** 可见推杆/切杆（`PHASE2_*_MODE` 已开）
- [ ] **推杆**分析 → 报告展示 PuttingReport 四维
- [ ] **切杆**分析 → 报告展示 ChippingReport
- [ ] 多段视频 → **select-swing** 页 → 分析成功
- [ ] **我的 → yardage book** 列表可读；装备页可跳转
- [ ] 教练 → **定制课程** 列表/编辑（`PHASE2_COACH_ENABLED`）

### Phase2 教练 / Pro（W23，体验版必勾）

前置：教练账号已审核通过；与至少 1 名学员 **active** 绑定；`PHASE2_COACH_*` / `PHASE2_PROS_ENABLED` 已开。

- [ ] 学员详情 → **写批注** → `analysis-annotate` 发送文字 → 学员报告页「教练点评」可见
- [ ] 教练批注页 **删除** 一条文字/参考 → 学员侧同步消失
- [ ] 批注页 **引用球手 clip** → 学员报告「教练参考素材」→ **看对比** 可进 pro-compare
- [ ] 学员详情 / recap → **布置作业** → 选推杆/切杆类目 drill → 学员 **训练 Tab**「教练布置的任务」可见
- [ ] 教练完成派发后学员 **打卡** → 教练侧任务状态变 `done`
- [ ] **教学报告**（session-recap）选学员 → 快捷「写批注/布置作业」→ 生成 LLM 汇总（可选 PDF）

### Phase2 训练 drill（W26，体验版必勾）

- [ ] 训练页展开任务 → 可见 **「教练提示」** 金边区块（推杆/切杆 drill）
- [ ] 推杆 issue 生成的计划含 putting 类目 drill（如「锁腕推杆」）
- [ ] `GET /v1/drills` 返回 **30** 条（CVM alembic ≥ 0044）

### Phase2 演化动画（W25 · M12-08，体验版可选）

前置：`PHASE2_PROS_ENABLED=true`；报告已完成且有 Pro 匹配。

- [ ] 报告 → **并排对比**（pro-compare）→ 「追平演化示意」区块可见
- [ ] 有 `evolution_poses` 的 demo clip → **SkeletonAnimation** 三态 + 「播放演化」
- [ ] 无 pose 数据 clip → 自动降级为 **雷达渐变**（不白屏、不报错）
- [ ] 文案含「示意动画，非 AI 逐帧预测」

---

## E. 红灯时快速分工

| 现象 | 优先查 |
|------|--------|
| 真机登录失败 / 401 | API 域名、HTTPS 证书、`WECHAT_MOCK_LOGIN`、合法域名 |
| 上传失败 | upload 合法域名、`MINIO_PUBLIC_ENDPOINT` 与签名 URL host |
| 支付调不起 / mock 错乱 | 后端 `WECHAT_PAY_MOCK_MODE` 与接口返回 `mock_mode`；**不要**仅靠编译期 `PAYMENT_MOCK` 决定分支 |
| 删了报告仍出现在列表 | 后端 `list_analyses` 是否带 `deleted_at IS NULL`（发版核对） |

---

## F. 线上体验验收通过后 → 提交审核（正式路径）

体验版与审核版应指向**同一套线上 API**（同一 `TARO_APP_API_BASE_URL`），避免「体验没问题、审核包连错环境」。推荐：**直接用本次上传的包走审核**，或在不改 env 的前提下重新 `make client-build-weapp-prod` 再上传一次（版本号递增）。

1. **后端**：确认本次改动已部署到线上（含 Alembic 迁移）；`GET https://你的API/v1/health` 正常。
2. **小程序包**：已用 **`make client-build-weapp-prod`**（见 [go-live-weapp-fool-checklist §4](./go-live-weapp-fool-checklist.md)）；真机至少关一次「不校验合法域名」跑通 **§D Smoke**。
3. **微信公众平台** → **管理 → 版本管理** → 在对应构建上点 **提交审核**（不是仅留在体验版）：按后台要求填**功能说明、测试账号（若需）、类目与隐私**等；详情见 [go-live-weapp-fool-checklist §1–2](./go-live-weapp-fool-checklist.md)。
4. 审核通过后按后台流程 **发布**；若需灰度，用平台提供的发布策略。

---

## G. 相关文档

- 正式上架傻瓜步骤：[go-live-weapp-fool-checklist.md](./go-live-weapp-fool-checklist.md)  
- 软删除发版档位：[analysis-soft-delete-release-pattern.md](./analysis-soft-delete-release-pattern.md)  
- 测试环境预检：[W8-preflight-checklist.md](./W8-preflight-checklist.md)
