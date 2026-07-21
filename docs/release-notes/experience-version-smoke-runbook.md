# 体验版一轮测试 · 操作备忘

> **目的**：在微信公众平台里发**体验版**前/后，用固定顺序跑一轮，减少「能上转但主路径炸」的情况。  
> **与正式上线区别**：体验版仍可临时开「不校验合法域名」做开发机联调；**真机验收**应以已配置 **request 合法域名**为准关项再验一遍。

---

## 当前线上基线（2026-07-21 · 1.2.44 已上传）


| 项                | 值                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **小程序版本**        | **1.2.44**（DevTools CLI 已上传；约 1.3 MB）                                                          |
| **Git / CVM**    | `main@f114b3a` · API health ok · ai_engine 短段过滤已随 release-cvm 上线                                              |
| **本版变更（1.2.44）** | ① params/select-swing 底栏改回 `fixed` 防「开始分析」叠球杆 ② 上传完成后点开始不再死等机位识别，超时直进 waiting ③ 过滤近零时长伪试挥段 |
| **当前任务**         | ① mp 选体验版/提审用 **1.2.44**（仅人工） ② 真机复测三图问题                                                                 |

> **上一版基线（1.2.43）**：登录页「暂不登录，先逛逛」。
> **CLI 上传坑（重要）**：改用 `cli upload --project client/dist`。

**下一步（仅人工）**：体验版/提审用 **1.2.44**；真机确认参数页底栏、点开始后不卡双 loading、无 0:00 伪试挥。

### Batch-J 增量（1.2.36 · 约 10 分钟）

- [x] 报告页见 **「本周主攻」** 卡片 +「去练这个动作」
- [x] 公测期报告页见 **价值感知卡**（每日最多一次）→ 进会员中心
- [x] 训练打卡成功 → 弹窗「去拍摄 / 稍后再说」
- [x] 历史对比页见 **晒进步** 卡 + 分享 / 海报入口
- [x] API 健康预检：`[pp-j0-preflight-2026-07-18.md](./pp-j0-preflight-2026-07-18.md)` ✅ 2026-07-18

> **在哪勾选？** 用 Cursor / VS Code 打开 **本文件**，点 `- [ ]` 左侧方框，或把 `[ ]` 改成 `[x]`。



### 1.2.35 · 公测免费 P0（体验版 · 约 15 分钟）

> 真机须为**体验版或正式版**；**关闭**「不校验合法域名」。



#### 确认

- [ ] 关于/设置页版本号 **1.2.36**（若仍见 1.2.35：确认已选为体验版并重新进入小程序）
- [ ] API 为 `api.birdieai.cn`（非 localhost）



#### 公测免费

- [ ] 登录后首页见 **公测免费** 金色 banner
- [ ] 英雄区配额文案 **公测期·不限次**
- [ ] **我的 → 会员中心** 见公测说明（mint 色 banner）
- [ ] 连续上传 / 对话 **不弹**「次数用完」（或 quota 显示 -1）



#### 1.2.34 · AI 教练合规（回归）

- [ ] **未登录** → **AI 教练** Tab → **不自动**跳登录页
- [ ] 可见：欢迎语、**示例对话（预览）**、快捷问题、输入框



#### 结论

- [ ] **P0 全绿** → 记验收日期，更新本文件

---



### 线上待验 P0（1.2.34 正式版 · 历史 · 约 20 分钟）

> 真机须为**已发布正式版**（非开发版）；**关闭**「不校验合法域名」。



#### 确认

- [ ] 关于/设置页版本号 **1.2.34**
- [ ] API 为 `api.birdieai.cn`（非 localhost）



#### 1.2.34 · AI 教练合规

- [ ] **未登录** → **AI 教练** Tab → **不自动**跳登录页
- [ ] 可见：欢迎语、**示例对话（预览）**、快捷问题、输入框
- [ ] 点快捷问题 → 填入输入框（不强制登录）
- [ ] 点 **「登录发送」** → 弹窗引导登录 → 可选继续浏览
- [ ] 顶栏 **登录** → 主动进入登录页



#### 1.2.33 · 全挥杆 / 诊断（线上仍须验）

- [ ] capture 首屏 **「立即拍摄」** 可见
- [ ] params **「开始分析」** 不必等 detect 结束
- [ ] **单段挥杆** → 不进 select-swing
- [ ] **差挥杆**报告 → 有 issue / drill / 弱项（非「没有明显问题」）
- [ ] **我的 → 我的画像** 正常（无 500）



#### 结论

- [ ] **P0 全绿** → 记验收日期，更新本文件；继续勾下方 P1 / Phase2 §D

---



### 1.2.33 真机 Smoke 快捷勾选（明细 · P0+P1 · 与线上 P0 重叠部分可跳过）



#### 发版前确认（历史）

- [x] 公众平台已发布 **1.2.34**（由 1.2.33 迭代）
- [ ] 真机 **关闭**「不校验合法域名」



#### P0 · 本版必验（1.2.32 + 1.2.33）

- [ ] capture 首屏 **「立即拍摄」** 可见（无「机位怎么选？」大块）
- [ ] params **「开始分析」** 不必等 detect 结束即可点
- [ ] 识别中点「开始分析」→ 正常提交，不丢参
- [ ] 相册 **2.0–2.2s** 视频 → toast 拦截，不进 params
- [ ] **<2.3s** → params 红色阻断「视频时长过短」
- [ ] **单段挥杆** → 不进 select-swing
- [ ] **差挥杆**报告 → 无「没有明显问题」；有 issue / drill / 弱项提示
- [ ] **真多挥** → select-swing → 分析成功
- [ ] **我的 → 我的画像** 正常打开（无 500）



#### P1 · 全挥杆主路径

- [ ] 登录成功；Tab 无白屏
- [ ] 全挥上传 → 等待页 → 报告完整
- [ ] params 机位默认选中 +「已识别为…」说明条
- [ ] 侧面报告无 absurd 转肩文案；有机位说明或拍摄提示



#### P2 · Phase2（有素材再勾）

- [ ] ModeSelector 推杆/切杆；PuttingReport / ChippingReport
- [ ] yardage book 可读；训练 Tab「教练提示」金边块
- [ ] 训练 Tab 卡片宽度正常



#### P3 · 教练 / Pro（需教练账号 · 可选）

- [ ] 批注 CRUD；Pro clip 引用；布置作业 + 打卡
- [ ] pro-compare 演化动画或雷达降级



#### 结论

- [ ] **P0+P1 全绿** → 与顶部「线上待验 P0」一并关项
- [ ] 失败项已记录（步骤 / 视频类型 / 截图）

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


| 场景                  | 客户端 env                                                                  | 说明                                                                     |
| ------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| 连 **HTTPS 测试域**（真机） | `client/.env.development.local` 或单独 `TARO_APP_API_BASE_URL=https://…/v1` | 域名须已在公众平台 **request 合法域名** 登记                                          |
| 仅开发者工具 + 本机         | 默认 `http://localhost:8000/v1`                                            | 真机不可用                                                                  |
| 走生产 API 的体验包        | 使用 `client/.env.production` + `make client-build-weapp-prod`             | 与 [go-live-weapp-fool-checklist](./go-live-weapp-fool-checklist.md) 一致 |


**后端**（体验环境）：`WECHAT_MOCK_LOGIN=false` + 真实小程序 AppID/Secret；内测可加 `QUOTA_MODE=unlimited`（见 [W8-preflight-checklist](./W8-preflight-checklist.md)）。

---



## C. 微信侧操作（需人工）

1. 微信开发者工具 → 打开工程根 `client`，`miniprogramRoot` → `dist`。
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
- [ ] **capture 页**：选 2.0–2.2s 视频 → toast 拦截，不进 params（1.2.30+）
- [ ] **短视频**：<2.3s 或引擎 50101 时长 → params **红色阻断条**「视频时长过短」
- [ ] （可选）多挥视频 → detect-swings 后机位与创任务参数一致

**红灯**


| 现象                     | 查                                               |
| ---------------------- | ----------------------------------------------- |
| 侧面仍报转肩不足/155° X-Factor | CVM ai_engine 是否已 `publish`；V2 桶是否走新 pipeline   |
| 报告仍显示「肩转 3°」           | `rotation_issue_copy` / sanitize 是否生效           |
| 无机位说明                  | `report.camera_angle` + `quality_warnings` 是否回传 |




### Phase2 短杆 / 多挥（W18–W22，体验版必勾）

- [ ] 拍摄页 **ModeSelector** 可见推杆/切杆（`PHASE2_*_MODE` 已开）
- [ ] **推杆**分析 → 报告展示 PuttingReport 四维
- [ ] **切杆**分析 → 报告展示 ChippingReport
- [ ] 多段视频 → **select-swing** 页 → 分析成功
- [ ] **我的 → yardage book** 列表可读；装备页可跳转
- [ ] 教练 → **定制课程** 列表/编辑（`PHASE2_COACH_ENABLED`）



### Phase2 教练 / Pro（W23，体验版必勾）

前置：教练账号已审核通过；与至少 1 名学员 **active** 绑定；`PHASE2_COACH_`* / `PHASE2_PROS_ENABLED` 已开。

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


| 现象              | 优先查                                                                         |
| --------------- | --------------------------------------------------------------------------- |
| 真机登录失败 / 401    | API 域名、HTTPS 证书、`WECHAT_MOCK_LOGIN`、合法域名                                    |
| 上传失败            | upload 合法域名、`MINIO_PUBLIC_ENDPOINT` 与签名 URL host                            |
| 支付调不起 / mock 错乱 | 后端 `WECHAT_PAY_MOCK_MODE` 与接口返回 `mock_mode`；**不要**仅靠编译期 `PAYMENT_MOCK` 决定分支 |
| 删了报告仍出现在列表      | 后端 `list_analyses` 是否带 `deleted_at IS NULL`（发版核对）                           |


---



## F. 线上体验验收通过后 → 提交审核（正式路径）

体验版与审核版应指向**同一套线上 API**（同一 `TARO_APP_API_BASE_URL`），避免「体验没问题、审核包连错环境」。推荐：**直接用本次上传的包走审核**，或在不改 env 的前提下重新 `make client-build-weapp-prod` 再上传一次（版本号递增）。

1. **后端**：确认本次改动已部署到线上（含 Alembic 迁移）；`GET https://你的API/v1/health` 正常。
2. **小程序包**：已用 `make client-build-weapp-prod`（见 [go-live-weapp-fool-checklist §4](./go-live-weapp-fool-checklist.md)）；真机至少关一次「不校验合法域名」跑通 **§D Smoke**。
3. **微信公众平台** → **管理 → 版本管理** → 在对应构建上点 **提交审核**（不是仅留在体验版）：按后台要求填**功能说明、测试账号（若需）、类目与隐私**等；详情见 [go-live-weapp-fool-checklist §1–2](./go-live-weapp-fool-checklist.md)。
4. 审核通过后按后台流程 **发布**；若需灰度，用平台提供的发布策略。

---



## G. 相关文档

- 正式上架傻瓜步骤：[go-live-weapp-fool-checklist.md](./go-live-weapp-fool-checklist.md)  
- 软删除发版档位：[analysis-soft-delete-release-pattern.md](./analysis-soft-delete-release-pattern.md)  
- 测试环境预检：[W8-preflight-checklist.md](./W8-preflight-checklist.md)

