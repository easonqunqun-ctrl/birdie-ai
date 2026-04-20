# W3-W4 · 核心分析链路 · 全链路走查记录

> 里程碑：M2 Done（2026-04）  
> 对应任务拆分：[docs/12-M2任务拆分.md](../12-M2任务拆分.md)  
> 本文件用途：用**文本脚本 + 日志证据**代替"真机截图"，完成 docs/11-M1任务拆分.md 附录·B 里"微信开发者工具全链路走查"的要求。正式发布前（W8）再补真实截图。

---

## 1. 走查范围

按 MVP §4.1-4.3 + §3.6 覆盖以下 8 段核心旅程：

1. **登录** — `mock code` 微信登录拿 Token
2. **新用户引导** — 3 步 onboarding（角度/球杆/目标）
3. **首页 CTA** — 开始分析 / 示例视频体验
4. **拍摄** — `capture` 页引导 + 视频选择 + 客户端校验
5. **参数** — `params` 页角度/球杆选择 + 上传直传 MinIO
6. **等待** — `waiting` 页轮询 + 阶段进度 + 小贴士
7. **报告** — `report` 页 6 区域（视频 / 评分 / 雷达 / 问题 / 建议 / 底部操作）
8. **历史** — `history` 页分页 + 下拉刷新 + 上拉加载

---

## 2. 走查方式

三种证据并用：

| 方式 | 工具 | 覆盖 |
|------|------|------|
| **后端 E2E 脚本** | `bash docs/api-examples/analyses-lifecycle.sh` | 步骤 1-8 的后端 API 层面 |
| **后端自动化测试** | `make backend-test`（37 用例） | 所有成功 + 失败分支 |
| **前端构建产物** | `pnpm build:weapp` → `client/dist/pages/analysis/*` | 5 个分析页全产出（wxml/wxss/js/json） |

真机 GIF/截图留到 **W8 发布准备** —— 届时 UI 微调与真实 AI 引擎（W6）都会再过一轮。

---

## 3. 后端 E2E 脚本结果

执行命令：

```bash
# 前置：make up 起齐所有容器
bash docs/api-examples/analyses-lifecycle.sh
```

**实际关键输出**（2026-04 验证）：

```
==> 0. GET /analyses/sample —— 预期 200 + 固定示例报告（不需要 Token）
{
  "id": "sample",
  "status": "completed",
  "overall_score": 78,
  "score_level": "good",
  "weakest": ["downswing"],
  "issues_count": 2,
  "recommendations_count": 2
}

==> 1. 微信登录（mock code=pytest_XXXX）
token = eyJhbGciOi...

==> 2a. POST /analyses/upload-token 超大文件 → 预期 400 + code=40005 ✅
==> 2b. POST /analyses/upload-token 时长 1.5s → 预期 400 + code=40004 ✅
==> 2c. POST /analyses/upload-token 正常请求 → 预期 200 ✅

==> 3. 直传 MinIO（presigned POST） → 204 ✅

==> 4. POST /analyses 创建分析任务 → pending ✅

==> 5. 轮询 /analyses/{id}/status（celery worker 消费中）
   stage: preprocessing → analyzing → completed（实测 2.8s）

==> 6. GET /analyses/{id} —— 预期 200 + 完整报告 ✅
   {
     "id": "ana_...",
     "status": "completed",
     "overall_score": 75,
     "score_level": "good",
     "phase_scores_keys": ["setup", "backswing", "top", "downswing", "impact", "follow_through"],
     "issues_count": 3,
     "recommendations_count": 2,
     "analyzed_at": "2026-04-20T..."
   }

==> 7a. GET /analyses?page=1&page_size=10 全部 ✅
==> 7b. GET /analyses?club_type=iron_7 筛选 ✅

✅ M2-T1+T2+T6 全链路通过（sample → 登录 → 上传 → celery → 报告 → 列表）
```

---

## 4. 自动化测试覆盖（37 passed）

```
tests/test_analyses_e2e.py  ............ 6 passed
  ├─ happy_path_writes_full_report         (完整链路 + 落库)
  ├─ engine_failed_refunds_quota           (AI 引擎失败，配额退回)
  ├─ timeout_exhausts_retries_and_refunds  (3 次超时，退配额)
  ├─ flaky_succeeds_after_retry            (首次失败，重试成功)
  ├─ multiple_analyses_independent         (并发独立)
  └─ worker_idempotent_on_terminal         (已 completed 任务幂等)

tests/test_analyses_lifecycle.py ...... 10 passed
  ├─ 超大文件 / 时长不足 → 40004/40005
  ├─ upload_id 不存在 / 不属于自己 / 对象未上传
  ├─ 正常路径扣配额
  ├─ status pending + report 409
  ├─ 分页 + club_type 过滤 + is_sample 排除
  └─ 跨用户 report 403

tests/test_analyses_sample.py  .......... 5 passed  (M2-T6 新增)
  ├─ 匿名可拉
  ├─ 完整报告结构
  ├─ 幂等（连续两次一致）
  ├─ 带 Token 一致
  └─ 不在历史列表

tests/test_auth.py + test_users.py + test_health.py ... 16 passed

========= 37 passed in 0.93s =========
```

---

## 5. 前端构建产物核对

```
client/dist/pages/analysis/
├─ capture.{js,json,wxml,wxss}
├─ params.{js,json,wxml,wxss}
├─ waiting.{js,json,wxml,wxss}
├─ report.{js,json,wxml,wxss}
└─ history.{js,json,wxml,wxss}
```

5 个页面各自 4 个必要产物都在位，webpack 编译无 warning：

```
> pnpm type-check    ✅
> pnpm lint          ✅
> pnpm build:weapp   ✅ Compiled successfully in 1.24s
```

---

## 6. 手动验证点清单（开发机）

以下在本地 macOS 上用微信开发者工具执行过（非真机）：

- [x] 登录 → Token 持久化
- [x] 首次打开 `capture` 页，顶部"首次拍摄提示" banner 出现；二次进入消失（`hasSeenAnalysisGuide` 生效）
- [x] 从相册选 10s 视频 → 进入 `params`，选 `face_on` + `iron_7` → 上传进度条平滑推进 → 成功跳 `waiting`
- [x] `waiting` 页 stage 从 "preprocessing" 平滑走到 "completed"（即便后端只返回两个真实 stage，前端本地时间模拟避免了"瞬跳"）
- [x] "你知道吗"小贴士每 5s 轮换一次，12 条无重复循环
- [x] `report` 页：评分 75，雷达图 6 维，弱项 `downswing` 标红；视频播放、0.5x/1x/1.5x 速度切换；点击"抛杆"问题卡片 → 视频 seek 到 1.8s
- [x] `history` 页：下拉刷新 → 首页 3 条 + "查看全部" 一致；上拉 20 条后追加分页
- [x] **示例视频**：首页底部"先看一份示例报告"入口 → 跳 `report?id=sample` → 顶部金色 banner "这是演示报告"；配额无变化；历史列表不出现 sample

---

## 7. 已登记延后项

以下在 M2 **不做**，继续挂靠各自里程碑，避免发版压力（与 [docs/12](../12-M2任务拆分.md) 附录表同步）：

| 条目 | 挂载里程碑 |
|------|-----------|
| 分享卡片生成 | **M5/W7** |
| 会员对比历史 | **W7** |
| "问 AI 教练"带上下文 | **M3/W5** |
| "加入训练计划"真连 | **M4/W5** |
| 微信服务通知（分析完成） | **W5** |
| 断点续传 | **W8** |
| 真实骨骼叠加视频 | **W6** |
| 真实质量预检 | **W6** |
| 腾讯云 COS 适配 | **W8** |
| 真机截图/GIF 录制 | **W8** |

---

## 8. 结论

**W3-W4 核心分析链路达标**：端到端可跑，关键分支有测试，文档与代码对齐。
下一个里程碑：**W5 AI 对话教练（M3）**。
